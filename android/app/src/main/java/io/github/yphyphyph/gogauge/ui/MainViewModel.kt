package io.github.yphyphyph.gogauge.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.yphyphyph.gogauge.GoGaugeApp
import io.github.yphyphyph.gogauge.data.backup.BackupManager
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
import io.github.yphyphyph.gogauge.data.remote.UpdateDownloader
import io.github.yphyphyph.gogauge.data.remote.UpdateInfo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

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
    /** 当前处于未登录态 (欢迎页语义; 由 checkState 维护). */
    var showLogin by mutableStateOf(false)
        private set

    /**
     * 用户已发起登录流程 (登录页打开中) — 与 [showLogin] 分离:
     * showLogin 表示"当前未登录", loginRequested 表示"正在登录".
     * 设置页发起的添加账号直接进登录页, 不再绕经欢迎页, 也不依赖欢迎页按钮
     * 覆盖 pendingLoginMode/Provider (desktop 独立登录窗语义 parity).
     */
    var loginRequested by mutableStateOf(false)
        private set

    /** 登录流程意图: "add"=添加新用户 / "relogin"=重登当前用户 (desktop open_login(mode) parity). */
    var pendingLoginMode by mutableStateOf("relogin")
        private set

    /** 登录流程来源: "opencode" / "commandcode" (desktop open_login(provider) parity). */
    var pendingLoginProvider by mutableStateOf("opencode")
        private set

    /** 粘贴 Cookie 登录的状态反馈 (""=空闲; 供登录方式对话框显示校验中/失败). */
    var pasteLoginStatus by mutableStateOf("")
        private set
    var loggedIn by mutableStateOf(false)
        private set
    var dashboard by mutableStateOf<DashboardData?>(null)
        private set
    /** 日历热力图逐日数据 (近 18 周)。 */
    var heatmapDays by mutableStateOf<List<io.github.yphyphyph.gogauge.data.model.DailyStat>>(emptyList())
        private set

    /** 热力图指标: cost / requests / tokens。 */
    var heatmapDim by mutableStateOf("cost")
        private set

    // ---- 导出/导入 (v2.2.0b, SAF) ----
    var backupBusy by mutableStateOf(false)
        private set
    var backupMessage by mutableStateOf("")
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

    /** 总览加载失败信息; 首次加载失败时 UI 显示错误+重试, 而不是永久转圈. */
    var overviewError by mutableStateOf<String?>(null)
        private set

    // ---- home page ----
    var homeRange by mutableStateOf("today")
        private set
    // ---- stats page ----
    var statsRange by mutableStateOf("7d")
        private set
    var modelDim by mutableStateOf("input")
        private set
    /**
     * 统计页排除的模型 (环形图图例点击切换).
     *
     * 只作用于统计页口径 —— 首页恒全量 (desktop state.excludedModels +
     * "排除仅作用于统计页, 切首页仍全量" parity). 切换账号时清空 (模型集不同).
     */
    var excludedModels by mutableStateOf<Set<String>>(emptySet())
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

    // ---- 更新包下载 (desktop /api/update/download + open parity) ----
    /** 最近一次检查结果 (含下载直链与 SHA-256 摘要; 见 [updateDownloadable]). */
    private var lastUpdateInfo by mutableStateOf<UpdateInfo?>(null)

    /** 是否展示"下载更新"入口: 有可用更新且 release 带本平台 APK 资产. */
    val updateDownloadable: Boolean
        get() = lastUpdateInfo?.hasUpdate == true && !lastUpdateInfo?.downloadUrl.isNullOrBlank()

    /** 更新包状态 (idle / downloading / ready / error). */
    var updateDownload by mutableStateOf<UpdateDownloadState>(UpdateDownloadState.Idle)
        private set

    private var autoSyncJob: Job? = null
    private var quotaRefreshJob: Job? = null
    private var runningAutoSyncKey: String? = null

    // 账户总览: 序号守卫丢弃过期响应 + 5s 静默重拉 (desktop ovSeq/ovRetryTimer parity)
    private var ovSeq = 0
    private var ovRetryJob: Job? = null
    private var overviewVisible = false

    // 请求序号守卫 (只在 Main 线程读写): 切页/刷新/配额到达会并发发起同一份状态
    // 的加载, 后落地者无条件覆盖会让 UI 显示与口径不符的数据 (Pill 高亮 A 显示 B)
    private var dashSeq = 0
    private var recordsSeq = 0
    private var sessionsSeq = 0

    // settings 写库串行化: 快速连续切换开关时防止在途写库互相覆盖
    private val settingsMutex = Mutex()

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
                if (loggedIn && dashboard != null) loadDashboard(currentDashRange(), currentExcluded())
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
                // 旧版 Android 存量数据回填 (local_date=NULL; 幂等, 先修再读让历史立即计入统计)
                repo.backfillLegacyLocalDatesIfNeeded()
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
        pasteLoginStatus = ""
        loginRequested = true
    }

    /** 取消登录 (登录页返回): 回到欢迎页 (未登录) 或主界面 (已登录添加账号场景)。 */
    fun cancelLogin() {
        loginRequested = false
        pasteLoginStatus = ""
    }

    /**
     * 粘贴 Cookie 直接登录 — desktop /api/accounts/add-token parity:
     * 先拉一次配额校验凭证可用, 通过才落库并进入应用 (错误经 [pasteLoginStatus] 反馈)。
     */
    fun pasteLogin(token: String, provider: String, onDone: (Boolean) -> Unit = {}) {
        val trimmed = token.trim()
        if (trimmed.isEmpty()) {
            pasteLoginStatus = s.cookieEmpty
            onDone(false)
            return
        }
        pasteLoginStatus = s.cookieChecking
        scope.launch {
            if (!repo.validateToken(trimmed, provider)) {
                pasteLoginStatus = s.cookieInvalid
                onDone(false)
                return@launch
            }
            repo.loginSuccess(trimmed, "", "add", provider)
            pasteLoginStatus = ""
            loginRequested = false
            showLogin = false
            onDone(true)
            checkState()
        }
    }

    /**
     * 登录成功按模式落库 (desktop on_login_success):
     * add=新建账号(同 provider+token 去重为既有账号)并切换; relogin=更新当前活跃账号凭证.
     */
    fun completeLogin(token: String, workspaceHint: String) {
        scope.launch {
            repo.loginSuccess(token, workspaceHint, pendingLoginMode, pendingLoginProvider)
            loggedIn = true
            loginRequested = false
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
        // 残留筛选/错误必须一起清: 新账号模型集不同, 旧筛选会让列表显示"暂无记录"
        recordsFilter = null
        recordsError = null
        sessionsError = null
        models = emptyList()
        excludedModels = emptySet()  // 新账号模型集不同: 旧的排除项一并清掉 (desktop parity)
    }

    // ------------------------------------------------------------------
    // Dashboard
    // ------------------------------------------------------------------

    /**
     * @param exclude 统计页排除的模型集; 首页调用方传空集 (首页恒全量口径).
     *   数据按 (range, exclude) 双元组与目标比对, 任一不符才重载.
     */
    fun loadDashboard(range: String = homeRange, exclude: Set<String> = emptySet()) {
        val seq = ++dashSeq
        scope.launch {
            try {
                // Desktop parity: every dashboard load kicks a background quota refresh
                // (30s cache + re-entry guard inside ensureQuota).
                repo.ensureQuotaAsync(scope)
                val data = repo.loadDashboard(range, exclude)
                if (seq != dashSeq) return@launch // 丢弃过期响应, 防口径串写
                dashboard = data
                dashboardVersion++
                loadHeatmap()
            } catch (e: CancellationException) {
                throw e // viewModelScope 取消时正常退出, 不当加载失败记录
            } catch (e: Exception) {
                android.util.Log.e("GoGauge", "loadDashboard failed range=$range", e)
            }
        }
    }

    /** 日历热力图数据重算 (随 dashboard 重载联动刷新)。 */
    private fun loadHeatmap() {
        scope.launch {
            try {
                heatmapDays = repo.heatmapDaily()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                android.util.Log.e("GoGauge", "loadHeatmap failed", e)
            }
        }
    }

    fun changeHeatmapDim(d: String) {
        heatmapDim = d
    }

    // ------------------------------------------------------------------
    // Export / import (v2.2.0b, SAF — 无存储权限)
    // ------------------------------------------------------------------

    private val app: Application get() = getApplication()

    fun exportCsv(uri: android.net.Uri) = runBackup { BackupManager.exportCsv(app, uri); s.exportDone }

    fun exportBackup(uri: android.net.Uri) = runBackup { BackupManager.exportBackup(app, uri); s.exportDone }

    fun importBackup(uri: android.net.Uri) = runBackup {
        val r = BackupManager.importBackup(app, uri)
        s.importDone.format(r.recordsAdded) + if (r.accountsAdded > 0) " (+${r.accountsAdded})" else ""
    }

    private fun runBackup(block: suspend () -> String) {
        if (backupBusy) return
        scope.launch {
            backupBusy = true
            backupMessage = ""
            try {
                backupMessage = block()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                android.util.Log.e("GoGauge", "backup failed", e)
                backupMessage = "${e.message?.takeIf { it.isNotBlank() } ?: s.exportFailed}"
            } finally {
                backupBusy = false
            }
        }
    }

    /** 首页口径: 恒全量 (排除只作用于统计页 — desktop parity). */
    fun ensureHomeDashboard() = ensureDashboard(homeRange, emptySet())

    /** 统计页口径: 带当前排除集. */
    fun ensureStatsDashboard() = ensureDashboard(statsRange, excludedModels)

    /**
     * 仅在缓存数据与目标口径不一致时重载.
     *
     * 首页与统计页共用同一个 dashboard 对象但各自的 range/排除集独立: 之前在
     * 统计页切到 "30d" 后回到首页, 首页会直接用 30d 的数据渲染, 而高亮的却是
     * "today". DashboardData 记录了数据对应的 (range, excluded), 以此为判据即可.
     */
    private fun ensureDashboard(range: String, exclude: Set<String>) {
        if (dashboard?.range != range || dashboard?.excluded != exclude) loadDashboard(range, exclude)
    }

    /** 图例点击: 切换模型排除并全局重聚合 (desktop onModelLegendClick parity).
     *  扇区/图例的即时反馈由 UI 直接用 [excludedModels] 渲染, 数值等本次重载落地. */
    fun toggleModelExclusion(model: String) {
        excludedModels = if (model in excludedModels) excludedModels - model else excludedModels + model
        loadDashboard(statsRange, excludedModels)
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
        if (!quiet) overviewError = null
        scope.launch {
            try {
                val loggedIn = repo.accounts().filter { it.hasToken }
                loggedIn.forEach { acc ->
                    launch { repo.ensureQuotaFor(acc.id) }
                }
                val data = repo.accountsOverview()
                if (seq != ovSeq) return@launch  // 丢弃过期响应 (快速切换页面时旧请求)
                overview = data
                overviewError = null
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
                // 失败必须写状态: 否则 overview 恒为 null, UI 永久停在 spinner,
                // 唯一的出路是手动点刷新
                if (seq == ovSeq) overviewError = e.message ?: "加载失败"
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
            // 保持当前页面的口径 (range + 排除集): 无条件用默认值会把统计页刷新
            // 换成首页周期的全量数据
            loadDashboard(currentDashRange(), currentExcluded())
            reloadPagedData() // 同步落地: 记录/会话列表跟着更新
        }
    }

    /**
     * 记录/会话列表重查 (下拉刷新与同步落地后调用)。
     *
     * 只在该页数据已被加载过 (records/sessions != null) 时执行, 避免为从未
     * 打开过的页面做无谓查询; 用户正停留在记录页时, 下拉刷新转圈结束后列表
     * 即是最新数据 (此前 refreshNow 只重载 dashboard, 记录页列表纹丝不动).
     */
    private fun reloadPagedData() {
        if (records != null) {
            recordsPage = 1
            loadRecords()
        }
        if (sessions != null) {
            sessionsPage = 1
            loadSessions()
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

    /** 当前 dashboard 数据对应的排除集 (统计页口径; 首页则为空集). */
    private fun currentExcluded(): Set<String> = dashboard?.excluded ?: emptySet()

    fun refreshNow() {
        android.util.Log.i("GoGauge", "refreshNow called")
        // 用当前已加载的 range + 排除集重载: 之前无条件用 homeRange, 在统计页刷新
        // 会把数据换成首页周期
        if (repo.progress.value.running) {
            loadDashboard(currentDashRange(), currentExcluded())
            reloadPagedData()
            return
        }
        // Instant paint from the local DB — do not block the spinner on network calls.
        loadDashboard(currentDashRange(), currentExcluded())
        reloadPagedData()
        startSync("incremental")
    }

    private fun fullSync() = startSync("full")

    fun isSyncing(): Boolean = syncing

    // ------------------------------------------------------------------
    // Records paging
    // ------------------------------------------------------------------

    fun loadRecords() {
        val seq = ++recordsSeq
        scope.launch {
            try {
                val page = repo.recordsPage(recordsPage, 10, recordsFilter, null)
                if (seq != recordsSeq) return@launch // 快速翻页: 丢弃过期响应, 防错页
                records = page
                recordsError = null
                // Model list is only needed for the filter dropdown; cache it after first load.
                if (models.isEmpty()) models = repo.listModels()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // 这里只读 Room, 抛出的是 SQLiteException 一类. 原先捕获
                // OpenCodeApiException (纯 DB 路径永远不会抛它) 等于没接住,
                // 异常会逃出 viewModelScope 直接崩溃
                android.util.Log.e("GoGauge", "loadRecords failed", e)
                if (seq == recordsSeq) recordsError = e.message ?: "加载失败"
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
        val seq = ++sessionsSeq
        scope.launch {
            try {
                val page = repo.sessionsPage(sessionsPage, 10, null)
                if (seq != sessionsSeq) return@launch // 快速翻页: 丢弃过期响应
                sessions = page
                sessionsError = null
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // 同 loadRecords: 该路径只读 Room, 需接住 SQLiteException
                android.util.Log.e("GoGauge", "loadSessions failed", e)
                if (seq == sessionsSeq) sessionsError = e.message ?: "加载失败"
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
        loadDashboard(r, emptySet())  // 首页恒全量
    }

    fun changeStatsRange(r: String) {
        statsRange = r
        loadDashboard(r, excludedModels)
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
        // 乐观更新: 开关立即响应; 连续快速切换两个开关时, 后一次修改基于已含前
        // 一次改动的 settings 构造, 不会被在途写库的旧值覆盖 (此前会静默回滚)
        settings = patch
        scope.launch {
            settingsMutex.withLock {
                try {
                    repo.saveSettings(settings) // 写库时取"当前最新"而非闭包参数
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    android.util.Log.e("GoGauge", "saveSettings failed", e)
                    settings = repo.settings() // 写库失败: 回滚为库中实际值
                }
            }
            restartAutoSync()
        }
    }

    fun changeLang(l: String) {
        lang = if (l == "en") "en" else "zh"
        prefs.edit().putString("lang", lang).apply()
        // 小组件/磁贴/常驻通知的文案在数据组装时确定, 语言切换后立即重绘
        io.github.yphyphyph.gogauge.widget.Updaters.dispatch(getApplication())
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
            updateDownload = UpdateDownloadState.Idle
            try {
                val info = repo.checkUpdate(
                    getApplication<Application>().packageManager
                        .getPackageInfo(getApplication<Application>().packageName, 0).versionName ?: "0.1.0"
                )
                lastUpdateInfo = info
                updateStatus = if (info.hasUpdate) "${s.updateFound} ${info.latest}" else s.updateNone
            } catch (e: Exception) {
                // 展示真实原因 (desktop: 把具体错误带给前端展示)
                updateStatus = e.message?.trim()?.takeIf { it.isNotEmpty() } ?: s.updateFailed
            }
        }
    }

    /** 下载更新包到应用私有目录 (校验 GitHub SHA-256 摘要后置为可安装). */
    fun downloadUpdate() {
        val info = lastUpdateInfo ?: return
        val url = info.downloadUrl
        if (!info.hasUpdate || url.isNullOrBlank()) return
        val app = getApplication<Application>()
        scope.launch {
            updateDownload = UpdateDownloadState.Downloading(0)
            try {
                val file = UpdateDownloader.download(
                    app, url, info.assetName ?: "GoGauge-update.apk", info.digest,
                ) { p -> updateDownload = UpdateDownloadState.Downloading(p) }
                updateDownload = UpdateDownloadState.Ready(file.absolutePath, file.name)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                val raw = e.message.orEmpty()
                val msg = if ("SHA-256" in raw) s.updateSignatureFail else raw.ifBlank { s.updateFailed }
                updateDownload = UpdateDownloadState.Error(msg)
            }
        }
    }

    /** 触发系统安装器; 未授权"安装未知应用"时跳转系统授权页. */
    fun installUpdate() {
        val ready = updateDownload as? UpdateDownloadState.Ready ?: return
        val app = getApplication<Application>()
        if (!UpdateDownloader.canInstall(app)) {
            updateStatus = s.grantInstall
            UpdateDownloader.openInstallSettings(app)
            return
        }
        try {
            UpdateDownloader.install(app, java.io.File(ready.path))
        } catch (e: Exception) {
            updateDownload = UpdateDownloadState.Error(e.message ?: s.updateFailed)
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

/** 更新包下载状态 — desktop /api/update/download/status 的本地等价. */
sealed interface UpdateDownloadState {
    data object Idle : UpdateDownloadState
    data class Downloading(val percent: Int) : UpdateDownloadState
    data class Ready(val path: String, val name: String) : UpdateDownloadState
    data class Error(val message: String) : UpdateDownloadState
}
