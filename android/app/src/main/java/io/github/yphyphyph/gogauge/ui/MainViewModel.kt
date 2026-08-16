package io.github.yphyphyph.gogauge.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.yphyphyph.gogauge.GoGaugeApp
import io.github.yphyphyph.gogauge.data.model.AppSettings
import io.github.yphyphyph.gogauge.data.model.DashboardData
import io.github.yphyphyph.gogauge.data.model.PageResult
import io.github.yphyphyph.gogauge.data.model.SessionStat
import io.github.yphyphyph.gogauge.data.model.SyncProgress
import io.github.yphyphyph.gogauge.data.model.UsageRecordRow
import io.github.yphyphyph.gogauge.data.repository.DashboardRepository
import io.github.yphyphyph.gogauge.data.remote.OpenCodeApiException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * Shared ViewModel for all pages — ports the frontend state machine of app.js
 * (dashboard data, paging, settings, login state, auto sync timer).
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
    var loggedIn by mutableStateOf(false)
        private set
    var dashboard by mutableStateOf<DashboardData?>(null)
        private set
    var loading by mutableStateOf(false)
        private set
    var progress by mutableStateOf(SyncProgress())
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
    var recordsPage by mutableIntStateOf(1)
        private set
    var recordsFilter by mutableStateOf<String?>(null)
        private set
    var models by mutableStateOf<List<String>>(emptyList())
        private set
    var sessions by mutableStateOf<PageResult<SessionStat>?>(null)
        private set
    var sessionsPage by mutableIntStateOf(1)
        private set

    // ---- settings ----
    var settings by mutableStateOf(AppSettings())
        private set
    var datadir by mutableStateOf("")
        private set
    var account by mutableStateOf(io.github.yphyphyph.gogauge.data.model.AccountInfo("Default", "Default", null, false))
        private set

    var updateStatus by mutableStateOf("")
        private set

    private var autoSyncJob: Job? = null
    private var quotaRefreshJob: Job? = null

    init {
        scope.launch {
            repo.progress.collectLatest { progress = it }
        }
        // Quota arrives asynchronously (30s cache): refresh the dashboard when it lands
        scope.launch {
            repo.quota.collectLatest { q ->
                android.util.Log.i("GoGauge", "quota flow: loggedIn=$loggedIn dash=${dashboard != null} q=$q")
                if (loggedIn && dashboard != null) loadDashboard()
            }
        }
        checkState()
        refreshSettings()
    }

    // ------------------------------------------------------------------
    // Login / state
    // ------------------------------------------------------------------

    fun checkState() {
        scope.launch {
            val acc = repo.account()
            account = acc
            loggedIn = acc.hasToken
            datadir = getApplication<Application>().filesDir.absolutePath
            if (acc.hasToken) {
                showLogin = false
                loadDashboard()
                // first run with empty db → auto full sync (desktop parity)
                if (repo.progress.value.phase == "idle" && repo.progress.value.running.not()) {
                    val sync = repo.account()
                    @Suppress("UNUSED_VARIABLE")
                    val dbEmpty = dashboard?.sync?.totalRecords == null
                    if (dbEmpty) fullSync()
                }
            } else {
                showLogin = true
            }
        }
    }

    fun onLoginSuccess() {
        scope.launch {
            loggedIn = true
            showLogin = false
            checkState()
            fullSync()
        }
    }

    /** Called by LoginScreen after the auth cookie is captured. */
    fun completeLogin(token: String, workspaceHint: String) {
        scope.launch {
            repo.saveLogin(token, workspaceHint)
            loggedIn = true
            showLogin = false
            refreshSettings()
            startSync("full")
        }
    }

    // ------------------------------------------------------------------
    // Dashboard
    // ------------------------------------------------------------------

    fun loadDashboard(range: String = homeRange) {
        scope.launch {
            loading = true
            try {
                // Desktop parity: every dashboard load kicks a background quota refresh
                // (30s cache + re-entry guard inside ensureQuota).
                repo.ensureQuotaAsync(scope)
                dashboard = repo.loadDashboard(range)
            } catch (e: Exception) {
                android.util.Log.e("GoGauge", "loadDashboard failed range=$range", e)
            } finally {
                loading = false
            }
        }
    }

    // ------------------------------------------------------------------
    // Sync
    // ------------------------------------------------------------------

    fun startSync(mode: String) {
        scope.launch {
            repo.syncAllAsync(scope, mode)
            // poll until idle (desktop pollUntilIdle parity)
            while (repo.progress.value.running) {
                delay(2500)
                loadDashboard()
            }
            loadDashboard()
        }
    }

    /** Manual refresh: incremental sync + force quota refresh (desktop top-bar refresh parity). */
    fun refreshNow() {
        android.util.Log.i("GoGauge", "refreshNow called")
        if (repo.progress.value.running) {
            loadDashboard()
            return
        }
        scope.launch {
            repo.ensureQuotaAsync(scope)
            startSync("incremental")
        }
    }

    private fun fullSync() = startSync("full")

    fun isSyncing(): Boolean = progress.running

    // ------------------------------------------------------------------
    // Records paging
    // ------------------------------------------------------------------

    fun loadRecords() {
        scope.launch {
            try {
                val page = repo.recordsPage(recordsPage, 10, recordsFilter, null)
                records = page
                models = repo.listModels()
            } catch (e: OpenCodeApiException) {
                // ignore
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
            } catch (e: OpenCodeApiException) {
                // ignore
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
        loadDashboard()
    }

    fun changeStatsRange(r: String) {
        statsRange = r
        loadDashboard()
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
            account = repo.account()
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

    fun logout() {
        scope.launch {
            repo.logout()
            loggedIn = false
            showLogin = true
            dashboard = null
            records = null
            sessions = null
        }
    }

    fun relogin() {
        logout()
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
                updateStatus = s.updateFailed
            }
        }
    }

    // ------------------------------------------------------------------
    // Auto sync (app.js restartAutoSync parity)
    // ------------------------------------------------------------------

    fun restartAutoSync() {
        autoSyncJob?.cancel()
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
