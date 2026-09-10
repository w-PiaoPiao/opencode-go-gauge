package io.github.yphyphyph.gogauge.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.yphyphyph.gogauge.GoGaugeApp
import io.github.yphyphyph.gogauge.data.model.AccountInfo
import io.github.yphyphyph.gogauge.data.model.AccountsOverviewData
import io.github.yphyphyph.gogauge.data.model.AppSettings
import io.github.yphyphyph.gogauge.data.model.DashboardData
import io.github.yphyphyph.gogauge.data.model.PageResult
import io.github.yphyphyph.gogauge.data.model.SessionStat
import io.github.yphyphyph.gogauge.data.model.SyncProgress
import io.github.yphyphyph.gogauge.data.model.UsageRecordRow
import io.github.yphyphyph.gogauge.data.repository.DashboardRepository
import io.github.yphyphyph.gogauge.data.remote.OpenCodeApiException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/**
 * Shared ViewModel for all pages — ports the frontend state machine of app.js v2.0.0
 * (dashboard data, paging, settings, 多用户登录状态/切换, auto sync timer).
 */
class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val repo: DashboardRepository = GoGaugeApp.instance.repository
    private val scope = viewModelScope
    private val prefs = app.getSharedPreferences("gousage-prefs", android.content.Context.MODE_PRIVATE)

    // ---- UI preferences (app.js localStorage parity, persisted) ----
    var lang by mutableStateOf(prefs.getString("lang", "zh") ?: "zh")
        private set
    var darkMode by mutableStateOf(prefs.getBoolean("dark", false))
        private set
    var currency by mutableStateOf(prefs.getString("currency", "CNY") ?: "CNY")
        private set

    val s: Strings get() = if (lang == "en") EnStrings else ZhStrings

    // ---- app state ----
    var showLogin by mutableStateOf(false)
        private set

    /** 登录流程意图: "add"=添加新用户 / "relogin"=重登当前用户 (desktop open_login(mode) parity). */
    var pendingLoginMode by mutableStateOf("relogin")
        private set

    /** 登录流程来源: "opencode" / "commandcode" (desktop open_login(provider) parity). */
    var pendingLoginProvider by mutableStateOf("opencode")
        private set
    var loggedIn by mutableStateOf(false)
        private set
    var dashboard by mutableStateOf<DashboardData?>(null)
        private set
    /**
     * dashboard 数据版本号 — 每次成功加载自增.
     *
     * 供需要"底层数据变了才重查"的页面 (账户总览) 当 LaunchedEffect key:
     * 直接用 dashboard 对象会让任何一次配额到达/进度更新都触发整套重查.
     */
    var dashboardVersion by mutableIntStateOf(0)
        private set
    var progress by mutableStateOf(SyncProgress())
        private set
    /** 仅同步运行位 — 见 init 中说明; 供下拉刷新等高频读取点使用. */
    var syncing by mutableStateOf(false)
        private set

    // ---- 多账号状态 (desktop /api/accounts parity) ----
    var accounts by mutableStateOf<List<AccountInfo>>(emptyList())
        private set
    var activeAccountId by mutableIntStateOf(0)
        private set

    /** 已登录账号数 (顶栏计数与列表口径一致). */
    val loggedInCount: Int get() = accounts.count { it.hasToken }

    // ---- 账户总览面板 (desktop /api/accounts/overview parity, v2.1.0) ----
    var overview by mutableStateOf<AccountsOverviewData?>(null)
        private set

    // ---- home page ----
    var homeRange by mutableStateOf("today")
        private set
    // ---- stats page ----
    var statsRange by mutableStateOf("7d")
        private set
    var modelDim by mutableStateOf("input")
        private set

    // ---- records page ----
    var records by mutableStateOf<PageResult<UsageRecordRow>?>(null)
        private set
    var recordsError by mutableStateOf<String?>(null)
        private set
    var recordsPage by mutableIntStateOf(1)
        private set
    var recordsFilter by mutableStateOf<String?>(null)
        private set
    var models by mutableStateOf<List<String>>(emptyList())
        private set
    var sessions by mutableStateOf<PageResult<SessionStat>?>(null)
        private set
    var sessionsError by mutableStateOf<String?>(null)
        private set
    var sessionsPage by mutableIntStateOf(1)
        private set

    // ---- settings ----
    var settings by mutableStateOf(AppSettings())
        private set
    var datadir by mutableStateOf("")
        private set
    var account by mutableStateOf<AccountInfo?>(null)
        private set

    var updateStatus by mutableStateOf("")
        private set

    private var autoSyncJob: Job? = null
    private var quotaRefreshJob: Job? = null
    private var runningAutoSyncKey: String? = null

    // 账户总览: 序号守卫丢弃过期响应 + 5s 静默重拉 (desktop ovSeq/ovRetryTimer parity)
    private var ovSeq = 0
    private var ovRetryJob: Job? = null
    private var overviewVisible = false

    init {
        scope.launch {
            repo.progress.collectLatest { progress = it }
        }
        // 只把 running 这一位单独暴露成布尔 state: 五个页面的下拉刷新都读它,
        // 而 Compose 的状态失效粒度是对象级的 —— 若直接读整个 SyncProgress,
        // 每次 page/inserted 更新都会让整屏重组 (一次全量同步上百次).
        // distinctUntilChanged 保证只在真正翻转时才写, 订阅者不受粒度影响.
        scope.launch {
            repo.progress
                .map { it.running }
                .distinctUntilChanged()
                .collectLatest { syncing = it }
        }
        // Quota arrives asynchronously (30s cache): refresh the dashboard when it lands
        scope.launch {
            repo.quota.collectLatest { q ->
                if (loggedIn && dashboard != null) loadDashboard(currentDashRange())
            }
        }
        checkState()
        refreshSettings()
    }

    // ------------------------------------------------------------------
    // Login / state (多账号版)
    // ------------------------------------------------------------------

    fun checkState() {
        scope.launch {
            account = repo.account()
            refreshAccounts()
            loggedIn = repo.countLoggedInAccounts() > 0
            datadir = getApplication<Application>().filesDir.absolutePath
            if (loggedIn) {
                showLogin = false
                loadDashboard()
                // first run with empty db → auto full sync (desktop parity);
                // read the persisted sync state from the DB, not the still-async dashboard
                val syncState = repo.syncState()
                if (syncState.lastSyncAt == null && syncState.totalRecords == 0) {
                    fullSync()
                }
            } else {
                showLogin = true
            }
        }
    }

    fun startLogin(mode: String, provider: String = "opencode") {
        pendingLoginMode = if (mode in listOf("add", "relogin")) mode else "relogin"
        pendingLoginProvider = provider
        showLogin = true
    }

    /**
     * 登录成功按模式落库 (desktop on_login_success):
     * add=新建账号(同 provider+token 去重为既有账号)并切换; relogin=更新当前活跃账号凭证.
     */
    fun completeLogin(token: String, workspaceHint: String) {
        scope.launch {
            repo.loginSuccess(token, workspaceHint, pendingLoginMode, pendingLoginProvider)
            loggedIn = true
            showLogin = false
            // checkState 内部已判断"首次登录 (无同步记录) 自动全量同步",
            // 这里不再额外 startSync("full"): 之前会触发两次全量同步 (第二次虽被
            // running 守卫挡下, 仍会多跑一次 loadDashboard)
            checkState()
        }
    }

    // ------------------------------------------------------------------
    // 多账号管理 (desktop 设置页用户管理 + 顶栏切换器 parity)
    // ------------------------------------------------------------------

    private fun refreshAccounts() {
        scope.launch {
            accounts = repo.accounts()
            activeAccountId = repo.activeAccountId()
            account = repo.account()
        }
    }

    /** 切换活跃账号后统一刷新面板与分页数据. */
    fun switchAccount(id: Int) {
        scope.launch {
            if (!repo.switchAccount(id)) return@launch
            resetPagedData()
            checkState()
        }
    }

    fun renameAccount(id: Int, name: String, onDone: (Boolean) -> Unit = {}) {
        scope.launch {
            val ok = repo.renameAccount(id, name)
            if (ok) refreshAccounts()
            onDone(ok)
        }
    }

    /** 删除账号及其本地数据; 无剩余已登录账号时回欢迎页 (desktop delete remaining==0 口径). */
    fun deleteAccount(id: Int) {
        scope.launch {
            repo.deleteAccount(id)
            resetPagedData()
            checkState()
        }
    }

    /** 退出登录当前活跃账号 (清其数据保留行); 其他已登录账号自动接管活跃位. */
    fun logoutActive() {
        scope.launch {
            repo.logout()
            resetPagedData()
            checkState()
        }
    }

    private fun resetPagedData() {
        dashboard = null
        records = null
        sessions = null
        recordsPage = 1
        sessionsPage = 1
        models = emptyList()
    }

    // ------------------------------------------------------------------
    // Dashboard
    // ------------------------------------------------------------------

    fun loadDashboard(range: String = homeRange) {
        scope.launch {
            try {
                // Desktop parity: every dashboard load kicks a background quota refresh
                // (30s cache + re-entry guard inside ensureQuota).
                repo.ensureQuotaAsync(scope)
                dashboard = repo.loadDashboard(range)
                dashboardVersion++
            } catch (e: CancellationException) {
                throw e // viewModelScope 取消时正常退出, 不当加载失败记录
            } catch (e: Exception) {
                android.util.Log.e("GoGauge", "loadDashboard failed range=$range", e)
            }
        }
    }

    /**
     * 仅在缓存数据与目标 range 不一致时重载.
     *
     * 首页与统计页共用同一个 dashboard 对象但各自的 range 状态独立: 之前在统计页
     * 切到 "30d" 后回到首页, 首页会直接用 30d 的数据渲染, 而高亮的却是 "today".
     * DashboardData.range 记录了数据对应的周期, 以此为判据即可.
     */
    fun ensureDashboard(range: String) {
        if (dashboard?.range != range) loadDashboard(range)
    }

    // ------------------------------------------------------------------
    // Accounts overview (desktop v2.1.0 账户总览面板 parity)
    // ------------------------------------------------------------------

    /** 页面可见性: 离开总览页后停止 5s 静默重拉循环. */
    fun setOverviewVisible(visible: Boolean) {
        overviewVisible = visible
        if (!visible) ovRetryJob?.cancel()
    }

    /**
     * 加载账户总览: 为每个已登录账号触发后台配额刷新 (非活跃账号凭证直读 accounts 表,
     * 不阻塞响应), 再聚合本地数据立即渲染; 有配额未就绪时 5s 后静默重拉,
     * 直到补齐或离开页面 (desktop loadOverview + ovRetryTimer parity).
     */
    fun loadOverview(quiet: Boolean = false) {
        val seq = ++ovSeq
        scope.launch {
            try {
                val loggedIn = repo.accounts().filter { it.hasToken }
                loggedIn.forEach { acc ->
                    launch { repo.ensureQuotaFor(acc.id) }
                }
                val data = repo.accountsOverview()
                if (seq != ovSeq) return@launch  // 丢弃过期响应 (快速切换页面时旧请求)
                overview = data
                val missing = data.accounts.any { it.quota == null }
                ovRetryJob?.cancel()
                if (missing && overviewVisible) {
                    ovRetryJob = scope.launch {
                        delay(5000)
                        if (seq == ovSeq && overviewVisible) loadOverview(true)
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                android.util.Log.e("GoGauge", "loadOverview failed", e)
            }
        }
    }

    // ------------------------------------------------------------------
    // Sync
    // ------------------------------------------------------------------

    /**
     * Run a sync in the background. Never holds the pull-refresh spinner hostage to the
     * full network chain: quota refreshes asynchronously (its flow reloads the dashboard
     * when it lands) and the dashboard is reloaded from the DB once the sync finishes.
     * This is Android parity for the desktop's async /api/sync, which queues the work on
     * a server thread and returns immediately so cached data stays visible.
     */
    fun startSync(mode: String) {
        scope.launch {
            repo.ensureQuotaAsync(scope)
            repo.syncUsage(mode)
            loadDashboard()
        }
    }

    /**
     * Manual refresh: render the cached dashboard instantly, then run the incremental
     * sync + quota refresh in the background. Previously this awaited the whole
     * sequential chain (quota → sync → dashboard), so a slow opencode.ai response made
     * the refresh spinner spin for up to ~90s even on a good network.
     */
    /** 当前 dashboard 数据对应的周期; 无数据时回退首页默认 (避免刷新把统计页打回首页周期). */
    private fun currentDashRange(): String = dashboard?.range ?: homeRange

    fun refreshNow() {
        android.util.Log.i("GoGauge", "refreshNow called")
        // 用当前已加载的 range 重载: 之前无条件用 homeRange, 在统计页刷新会把
        // 数据换成首页周期
        if (repo.progress.value.running) {
            loadDashboard(currentDashRange())
            return
        }
        // Instant paint from the local DB — do not block the spinner on network calls.
        loadDashboard(currentDashRange())
        startSync("incremental")
    }

    private fun fullSync() = startSync("full")

    fun isSyncing(): Boolean = syncing

    // ------------------------------------------------------------------
    // Records paging
    // ------------------------------------------------------------------

    fun loadRecords() {
        scope.launch {
            try {
                val page = repo.recordsPage(recordsPage, 10, recordsFilter, null)
                records = page
                // Model list is only needed for the filter dropdown; cache it after first load.
                if (models.isEmpty()) models = repo.listModels()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // 这里只读 Room, 抛出的是 SQLiteException 一类. 原先捕获
                // OpenCodeApiException (纯 DB 路径永远不会抛它) 等于没接住,
                // 异常会逃出 viewModelScope 直接崩溃
                android.util.Log.e("GoGauge", "loadRecords failed", e)
                recordsError = e.message ?: "加载失败"
            }
        }
    }

    fun changeRecordsFilter(model: String?) {
        recordsFilter = model
        recordsPage = 1
        loadRecords()
    }

    fun recordsPrev() {
        if (recordsPage > 1) {
            recordsPage--
            loadRecords()
        }
    }

    fun recordsNext() {
        recordsPage++
        loadRecords()
    }

    fun loadSessions() {
        scope.launch {
            try {
                sessions = repo.sessionsPage(sessionsPage, 10, null)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // 同 loadRecords: 该路径只读 Room, 需接住 SQLiteException
                android.util.Log.e("GoGauge", "loadSessions failed", e)
                sessionsError = e.message ?: "加载失败"
            }
        }
    }

    fun sessionsPrev() {
        if (sessionsPage > 1) {
            sessionsPage--
            loadSessions()
        }
    }

    fun sessionsNext() {
        sessionsPage++
        loadSessions()
    }

    // ------------------------------------------------------------------
    // Ranges / dims
    // ------------------------------------------------------------------

    fun changeHomeRange(r: String) {
        homeRange = r
        loadDashboard(r)
    }

    fun changeStatsRange(r: String) {
        statsRange = r
        loadDashboard(r)
    }

    fun changeModelDim(d: String) {
        modelDim = d
        // re-render chart from cached data
    }

    // ------------------------------------------------------------------
    // Settings
    // ------------------------------------------------------------------

    fun refreshSettings() {
        scope.launch {
            settings = repo.settings()
            restartAutoSync()
        }
    }

    fun saveSettings(patch: AppSettings) {
        scope.launch {
            settings = repo.saveSettings(patch)
            restartAutoSync()
        }
    }

    fun changeLang(l: String) {
        lang = if (l == "en") "en" else "zh"
        prefs.edit().putString("lang", lang).apply()
    }

    fun changeDarkMode(on: Boolean) {
        darkMode = on
        prefs.edit().putBoolean("dark", on).apply()
    }

    fun changeCurrency(c: String) {
        currency = c
        prefs.edit().putString("currency", c).apply()
    }

    fun checkUpdate() {
        scope.launch {
            updateStatus = s.checkingUpdate
            try {
                val info = repo.checkUpdate(
                    getApplication<Application>().packageManager
                        .getPackageInfo(getApplication<Application>().packageName, 0).versionName ?: "0.1.0"
                )
                updateStatus = if (info.hasUpdate) "${s.updateFound} ${info.latest}" else s.updateNone
            } catch (e: Exception) {
                // 展示真实原因 (desktop: 把具体错误带给前端展示)
                updateStatus = e.message?.trim()?.takeIf { it.isNotEmpty() } ?: s.updateFailed
            }
        }
    }

    // ------------------------------------------------------------------
    // Auto sync (app.js restartAutoSync parity)
    // ------------------------------------------------------------------

    fun restartAutoSync() {
        val key = if (settings.autoSync) "on:${settings.syncIntervalSec}" else "off"
        if (autoSyncJob?.isActive == true && runningAutoSyncKey == key) return
        autoSyncJob?.cancel()
        runningAutoSyncKey = key
        if (!settings.autoSync) return
        val sec = (settings.syncIntervalSec.coerceAtLeast(30)) * 1000L
        autoSyncJob = scope.launch {
            while (true) {
                delay(sec)
                if (!repo.progress.value.running) startSync("incremental")
            }
        }
    }
}
