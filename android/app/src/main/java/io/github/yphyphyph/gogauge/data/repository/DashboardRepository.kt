package io.github.yphyphyph.gogauge.data.repository

import io.github.yphyphyph.gogauge.data.model.AccountInfo
import io.github.yphyphyph.gogauge.data.model.AccountOverview
import io.github.yphyphyph.gogauge.data.model.AccountsOverviewData
import io.github.yphyphyph.gogauge.data.model.DashboardData
import io.github.yphyphyph.gogauge.data.model.PageResult
import io.github.yphyphyph.gogauge.data.model.QuotaResult
import io.github.yphyphyph.gogauge.data.model.SessionStat
import io.github.yphyphyph.gogauge.data.model.SyncProgress
import io.github.yphyphyph.gogauge.data.model.SyncState
import io.github.yphyphyph.gogauge.data.model.UsageRecord
import io.github.yphyphyph.gogauge.data.model.UsageRecordRow
import io.github.yphyphyph.gogauge.data.remote.AuthException
import io.github.yphyphyph.gogauge.data.remote.ExchangeApi
import io.github.yphyphyph.gogauge.data.remote.OpenCodeApi
import io.github.yphyphyph.gogauge.data.remote.OpenCodeApiException
import io.github.yphyphyph.gogauge.data.remote.UpdateApi
import io.github.yphyphyph.gogauge.data.remote.UpdateInfo
import io.github.yphyphyph.gogauge.data.db.AppDatabase
import io.github.yphyphyph.gogauge.data.db.MonthlyCycle
import io.github.yphyphyph.gogauge.data.db.SyncDao
import io.github.yphyphyph.gogauge.data.db.UsageDao
import io.github.yphyphyph.gogauge.data.model.AppSettings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.time.format.DateTimeFormatter

/** Sync outcome — mirrors server.py sync_usage return dict. */
data class SyncResult(
    val ok: Boolean,
    val error: String? = null,
    val inserted: Int = 0,
    val pages: Int = 0,
    val partial: Boolean = false,
    val failedPages: Int = 0,
)

/**
 * Dashboard repository — ports of server.py v2.0.0 (多账号同步引擎, 配额按账号分槽缓存)
 * plus db.py aggregations, exposed as a single service to ViewModels.
 *
 * 未显式传 accountId 的接口一律作用于活跃账号 (desktop db 兼容约定).
 */
class DashboardRepository(
    private val db: AppDatabase,
    private val api: OpenCodeApi,
    private val exchangeApi: ExchangeApi,
    private val updateApi: UpdateApi,
) {
    private val usageDao: UsageDao get() = db.usageDao()
    private val syncDao: SyncDao get() = db.syncDao()

    // ------------------------------------------------------------------
    // Caches (server.py parity — quota 按账号分槽)
    // ------------------------------------------------------------------

    private class QuotaCache {
        @Volatile var at = 0.0
        @Volatile var data: QuotaResult? = null
    }

    /** {account_id: slot} — desktop _quota_cache: dict[int, dict]. */
    private val quotaCache = HashMap<Int, QuotaCache>()
    private val quotaMutex = Mutex()
    private val syncMutex = Mutex()  // 同步单飞守卫: check-then-set 原子化

    /** 防重入: 同一账号同一时刻只允许一个刷新协程 — desktop _quota_refreshing: set[int]. */
    private val quotaRefreshing = mutableSetOf<Int>()
    private val _quota = MutableStateFlow<QuotaResult?>(null)
    val quota: StateFlow<QuotaResult?> = _quota.asStateFlow()

    private class ExchangeCache {
        @Volatile var at = 0.0
        @Volatile var usdCny = 7.2
    }
    private val exchangeCache = ExchangeCache()
    private val exchangeMutex = Mutex()
    private val EXCHANGE_TTL = 6 * 3600.0
    private val QUOTA_CACHE_TTL = 30.0

    // ------------------------------------------------------------------
    // Sync state (server.py _sync_state parity)
    // ------------------------------------------------------------------

    private val _progress = MutableStateFlow(SyncProgress())
    val progress: StateFlow<SyncProgress> = _progress.asStateFlow()

    private fun setProgress(transform: (SyncProgress) -> SyncProgress) {
        _progress.value = transform(_progress.value)
    }

    // ------------------------------------------------------------------
    // Active account helpers
    // ------------------------------------------------------------------

    suspend fun activeAccountId(): Int = syncDao.getActiveAccountId()

    suspend fun accounts(): List<AccountInfo> = syncDao.listAccounts()

    suspend fun countLoggedInAccounts(): Int = syncDao.countLoggedInAccounts()

    suspend fun account(): AccountInfo? = syncDao.getAccount()

    suspend fun switchAccount(accountId: Int): Boolean {
        val ok = syncDao.setActiveAccount(accountId)
        if (ok) _quota.value = null
        return ok
    }

    private fun clearQuotaSlot(accountId: Int) {
        synchronized(quotaCache) { quotaCache.remove(accountId) }
    }

    suspend fun renameAccount(accountId: Int, name: String): Boolean = syncDao.renameAccount(accountId, name)

    /** 返回剩余账号数 (desktop /api/accounts/delete remaining 口径). */
    suspend fun deleteAccount(accountId: Int): Int {
        val remaining = syncDao.deleteAccount(accountId)
        clearQuotaSlot(accountId)  // 账号已删除, 配额缓存一并清除
        _quota.value = null
        return remaining
    }

    /** 登录成功按模式落库: add=新建账号(同 token 去重)并切换; relogin=更新活跃账号凭证. */
    suspend fun loginSuccess(token: String, workspaceHint: String, mode: String) {
        if (mode == "add") syncDao.addAccount(token, workspaceHint, switch = true)
        else syncDao.saveToken(token, workspaceHint.trim().ifEmpty { "Default" })
        _quota.value = null
    }

    // ------------------------------------------------------------------
    // Quota refresh (server.py _ensure_quota_async parity, per-account slots)
    // ------------------------------------------------------------------

    /** Refresh active account's quota in the background if cache is stale; non-blocking. */
    fun ensureQuotaAsync(scope: CoroutineScope) {
        scope.launch { ensureQuota() }
    }

    suspend fun ensureQuota() {
        ensureQuotaFor(activeAccountId())
    }

    /**
     * 刷新任意账号 (含非活跃账号) 的配额缓存 — desktop v2.1.0 _ensure_quota_async(aid) parity:
     * 凭证直接从 accounts 表读取, 供账户总览面板使用; 30s 缓存 + 防重入.
     */
    suspend fun ensureQuotaFor(accountId: Int) {
        if (accountId == 0) return
        val now = System.currentTimeMillis() / 1000.0
        val slot = synchronized(quotaCache) { quotaCache[accountId] }
        if (slot?.data != null && now - slot.at < QUOTA_CACHE_TTL) return
        quotaMutex.withLock {
            if (accountId in quotaRefreshing) return
            val token = syncDao.getTokenFor(accountId)
            if (token.isEmpty()) return
            quotaRefreshing.add(accountId)
        }
        try {
            // failure also writes cache (null data) so the UI doesn't retry every load
            val target = synchronized(quotaCache) { quotaCache.getOrPut(accountId) { QuotaCache() } }
            val token = syncDao.getTokenFor(accountId)
            val hint = syncDao.getWorkspaceHintFor(accountId)
            target.at = System.currentTimeMillis() / 1000.0
            target.data = try {
                api.fetchQuota(token, hint)
            } catch (e: Exception) {
                android.util.Log.e("GoGauge", "quota refresh failed", e)
                null
            }
            if (accountId == activeAccountId()) _quota.value = target.data
            // 配额拉取成功后持久化月度窗口的重置时间 (供「本月」筛选推算周期起点,
            // desktop server._record_monthly_reset parity); 失败不影响配额返回.
            target.data?.takeIf { it.success }?.windows?.firstOrNull { it.label == "Monthly" }?.let { w ->
                try {
                    db.settingsDao().saveMonthlyReset(accountId, formatResetUtc(w.resetAt))
                } catch (e: Exception) {
                    android.util.Log.w("GoGauge", "saveMonthlyReset failed", e)
                }
            }
            android.util.Log.i(
                "GoGauge",
                "quota refreshed acc=$accountId success=" + (target.data?.success) + " err=" + (target.data?.error),
            )
        } finally {
            quotaRefreshing.remove(accountId)
        }
    }

    /**
     * Quota resetAt (Instant ISO) -> UTC "yyyy-MM-dd HH:mm:ss" —
     * desktop record_monthly_reset 存储格式 parity; 解析失败返回 null (不落库).
     */
    private fun formatResetUtc(resetAt: String): String? = try {
        java.time.LocalDateTime.ofInstant(java.time.Instant.parse(resetAt), java.time.ZoneOffset.UTC)
            .format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
    } catch (e: Exception) {
        null
    }

    private suspend fun usdCny(): Double {
        val now = System.currentTimeMillis() / 1000.0
        if (now - exchangeCache.at < EXCHANGE_TTL) return exchangeCache.usdCny
        return exchangeMutex.withLock {
            if (now - exchangeCache.at < EXCHANGE_TTL) return exchangeCache.usdCny
            try {
                val rate = exchangeApi.fetchUsdCny()
                if (rate > 0) exchangeCache.usdCny = rate
            } catch (e: Exception) {
                // keep old value on failure (server.py parity)
            }
            exchangeCache.at = System.currentTimeMillis() / 1000.0
            exchangeCache.usdCny
        }
    }

    // ------------------------------------------------------------------
    // Dashboard bundle (server.py /api/dashboard parity — 活跃账号视角)
    // ------------------------------------------------------------------

    suspend fun loadDashboard(range: String): DashboardData {
        val aid = activeAccountId()
        val token = syncDao.getTokenFor(aid)
        val quota = if (token.isNotEmpty()) _quota.value else null
        val now = java.time.LocalDateTime.now()
            .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
        // 「本月」= 当前月度重置周期: 从持久化的下次月度重置时间推算周期起点 (desktop parity);
        // 无配额记录时为 null, DAO 层回退滚动 30 天.
        val cycleStart = if (range == "month") {
            MonthlyCycle.start(db.settingsDao().getMonthlyReset(aid), MonthlyCycle.nowUtc())
        } else null
        // Run the independent DB/exchange queries concurrently to cut first-paint latency.
        return coroutineScope {
            val totalsDeferred = async { usageDao.totals(range, aid, cycleStart) }
            val todayDeferred = async { usageDao.totals("today", aid) }
            val dailyDeferred = async { usageDao.dailyStats(7, aid) }
            val trendDeferred = async { usageDao.dailyStats(30, aid) }
            val todayTrendDeferred = async { usageDao.todayTrend(aid) }
            val modelsDeferred = async { usageDao.modelStats(range, aid, cycleStart) }
            val syncDeferred = async { syncDao.getSyncStateFor(aid) }
            val usdCnyDeferred = async { usdCny() }
            DashboardData(
                loggedIn = token.isNotEmpty(),
                quota = quota,
                totals = totalsDeferred.await(),
                today = todayDeferred.await(),
                daily = dailyDeferred.await(),
                trend = trendDeferred.await(),
                todayTrend = todayTrendDeferred.await(),
                models = modelsDeferred.await(),
                sync = syncDeferred.await(),
                progress = _progress.value,
                range = range,
                usdCny = usdCnyDeferred.await(),
                serverTime = now,
            )
        }
    }

    // ------------------------------------------------------------------
    // Accounts overview (server.py GET /api/accounts/overview parity — v2.1.0)
    // ------------------------------------------------------------------

    /**
     * 账户总览面板数据: 仅返回已登录账号, 聚合各自配额缓存 / 今日合计 / 24h 趋势 / 7 日统计.
     * 配额缺失的账号由调用方先触发后台刷新 (ensureQuotaFor), 本次先返回缓存值.
     */
    suspend fun accountsOverview(): AccountsOverviewData {
        val activeId = activeAccountId()
        val loggedIn = accounts().filter { it.hasToken }
        val list = loggedIn.map { acc ->
            val aid = acc.id
            val slot = synchronized(quotaCache) { quotaCache[aid] }
            coroutineScope {
                val todayDeferred = async { usageDao.totals("today", aid) }
                val trendDeferred = async { usageDao.todayTrend(aid) }
                val dailyDeferred = async { usageDao.dailyStats(7, aid) }
                val syncDeferred = async { syncDao.getSyncStateFor(aid) }
                val syncState = syncDeferred.await()
                AccountOverview(
                    id = aid,
                    name = acc.name,
                    active = aid == activeId,
                    quota = slot?.data,
                    today = todayDeferred.await(),
                    todayTrend = trendDeferred.await(),
                    daily7 = dailyDeferred.await(),
                    lastSyncAt = syncState.lastSyncAt,
                    lastSyncStatus = syncState.lastSyncStatus,
                )
            }
        }
        return AccountsOverviewData(accounts = list, usdCny = usdCny())
    }

    // ------------------------------------------------------------------
    // Sync engine (server.py v2.0.0 sync_usage parity — 多账号轮询)
    // ------------------------------------------------------------------

    suspend fun syncUsage(mode: String): SyncResult {
        // incremental 轮询所有已登录账号; full 仅作用于活跃账号 (desktop parity)
        val targets: List<Pair<Int, String>> = if (mode == "full") {
            val aid = activeAccountId()
            if (aid != 0 && syncDao.getTokenFor(aid).isNotEmpty()) {
                listOf(aid to (account()?.name ?: "#$aid"))
            } else emptyList()
        } else {
            accounts().filter { it.hasToken }.map { it.id to it.name }
        }
        if (targets.isEmpty()) return SyncResult(ok = false, error = "未登录")
        // check-then-set 原子化: WorkManager / 前台定时器 / 下拉刷新 / 登录后 fullSync
        // 可能并发进入, 无锁会双同步并互踩进度状态 (desktop 对应有 _sync_lock)
        syncMutex.withLock {
            if (_progress.value.running) return SyncResult(ok = false, error = "已有同步任务进行中")
            _progress.value = SyncProgress(running = true, mode = mode, phase = "usage")
        }

        val windowDays = db.settingsDao().getSettings().windowDays

        try {
            var totalInserted = 0
            var pages = 0
            var anyError = ""
            var partial = false

            for ((aid, name) in targets) {
                setProgress { it.copy(account = name) }
                val result = syncOneAccount(aid, name, mode, windowDays)
                totalInserted += result.inserted
                pages += result.pages
                if (!result.ok) {
                    anyError = result.error ?: "同步失败"
                    if (mode == "incremental") {
                        val msg = "[$name] $anyError"
                        failSync(msg, anyError)
                        return SyncResult(ok = false, error = anyError, inserted = totalInserted)
                    }
                }
                if (result.partial) partial = true
            }

            return if (partial || (mode != "incremental" && anyError.isNotEmpty())) {
                val msg = if (anyError.isNotEmpty()) "部分账号同步异常" else "完成, 但部分页面拉取失败"
                setProgress { it.copy(phase = "done", message = msg) }
                SyncResult(ok = true, partial = true, inserted = totalInserted, pages = pages)
            } else {
                val msg = "同步完成, 新增 $totalInserted 条"
                setProgress { it.copy(phase = "done", message = msg) }
                SyncResult(ok = true, inserted = totalInserted, pages = pages)
            }
        } catch (e: Exception) {
            failSync(e.message ?: "同步失败", e.message)
            return SyncResult(ok = false, error = e.message)
        } finally {
            setProgress { it.copy(running = false, account = "") }
        }
    }

    /**
     * 同步单个账号的用量记录 (原单账号逻辑, 显式传入账号上下文) —
     * desktop server._sync_one_account parity.
     */
    private suspend fun syncOneAccount(
        accountId: Int,
        name: String,
        mode: String,
        windowDays: Int?,
    ): SyncResult {
        val token = syncDao.getTokenFor(accountId)
        if (token.isEmpty()) return SyncResult(ok = false, error = "未登录")
        var workspaceId = syncDao.getWorkspaceHintFor(accountId)

        try {
            // ensure workspace id is resolved
            try {
                val resolved = api.resolveWorkspaceId(workspaceId, token)
                if (!workspaceId.startsWith("wrk_")) {
                    workspaceId = resolved
                    syncDao.saveResolvedWorkspace(accountId, resolved, Instant.now().toString())
                }
            } catch (e: AuthException) {
                val msg = "工作区解析失败: ${e.message}"
                syncDao.updateSyncStateAndTotals(accountId, "error", msg, 0)
                setProgress { it.copy(phase = "error", message = msg) }
                return SyncResult(ok = false, error = e.message)
            } catch (e: OpenCodeApiException) {
                val msg = "工作区解析失败: ${e.message}"
                syncDao.updateSyncStateAndTotals(accountId, "error", msg, 0)
                setProgress { it.copy(phase = "error", message = msg) }
                return SyncResult(ok = false, error = e.message)
            }

            var totalInserted = 0
            val maxPages = if (mode == "full") 2000 else 5
            var page = 0
            var emptyBatches = 0
            var failedPages = 0
            var windowBoundaryReached = false

            while (page < maxPages) {
                val batchPages = (page until minOf(page + 5, maxPages)).toList()
                setProgress { it.copy(page = page) }

                val results = fetchBatch(token, workspaceId, batchPages)

                var batchInserted = 0
                var batchFullPages = 0
                var batchFailed = 0
                for (p in batchPages.sorted()) {
                    val result = results[p]
                    if (result == null) {
                        batchFailed++
                        continue
                    }
                    if (result.isEmpty()) continue // empty page: end of data
                    // sync range: stop when the page's earliest record predates the window boundary
                    if (mode == "full" && windowDays != null) {
                        val earliest = result.minOfOrNull { it.createdAt } ?: ""
                        if (earliest.isNotEmpty()) {
                            try {
                                val et = Instant.parse(earliest)
                                val boundary = Instant.now().minus(windowDays.toLong(), ChronoUnit.DAYS)
                                if (et.isBefore(boundary)) windowBoundaryReached = true
                            } catch (e: Exception) {
                                // ignore unparseable dates (desktop parity)
                            }
                        }
                    }
                    val inserted = usageDao.insertUsageRecords(
                        result.map { r ->
                            val entity = r.toEntity(Instant.now().toString())
                            entity.copy(accountId = accountId)
                        },
                        accountId,
                    )
                    totalInserted += inserted
                    batchInserted += inserted
                    if (result.size >= 50) batchFullPages++
                    setProgress { it.copy(inserted = totalInserted) }
                }

                page += 5

                if (windowBoundaryReached) break
                if (batchFailed > 0) {
                    failedPages += batchFailed
                    if (mode == "incremental") {
                        val msg = "网络请求失败 (IncompleteRead/超时)"
                        syncDao.updateSyncStateAndTotals(
                            accountId, "error", "[$name] 第 ${page - 4} 页拉取失败: $msg", totalInserted,
                        )
                        setProgress { it.copy(phase = "error", message = "[$name] 第 ${page - 4} 页拉取失败: $msg") }
                        return SyncResult(ok = false, error = msg, inserted = totalInserted)
                    }
                }
                // this batch had no full pages → reached the end
                if (batchFullPages == 0) break
                // incremental: two consecutive all-old batches → stop
                if (mode == "incremental" && batchInserted == 0) {
                    emptyBatches++
                    if (emptyBatches >= 2) break
                } else {
                    emptyBatches = 0
                }
            }

            // prune records outside the window (independent of this run's inserts)
            if (windowDays != null) {
                usageDao.pruneOldRecords("-${windowDays} days", accountId)
            }

            // 顺带刷新该账号的 key 显示名称缓存 — 多账号合并写入 (key_id 全局唯一),
            // 单账号失败不影响已有缓存 (desktop server.py v2.0.0 parity)
            try {
                val names = api.fetchKeyNames(token, workspaceId)
                if (names.isNotEmpty()) {
                    val merged = HashMap(db.settingsDao().getKeyNames())
                    merged.putAll(names)
                    db.settingsDao().saveKeyNames(merged)
                }
            } catch (e: Exception) {
                android.util.Log.w("GoGauge", "fetchKeyNames failed", e)
            }

            if (failedPages > 0) {
                val msg = "完成, 但 $failedPages 页拉取失败 (数据不完整, 可再次全量同步补全)"
                syncDao.updateSyncStateAndTotals(accountId, "partial", msg, totalInserted)
                return SyncResult(ok = true, partial = true, failedPages = failedPages, inserted = totalInserted, pages = page)
            }
            syncDao.updateSyncStateAndTotals(accountId, "ok", null, totalInserted)
            return SyncResult(ok = true, inserted = totalInserted, pages = page)
        } catch (e: Exception) {
            syncDao.updateSyncStateAndTotals(accountId, "error", e.message, 0)
            return SyncResult(ok = false, error = e.message)
        }
    }

    private suspend fun failSync(phaseMsg: String, errMsg: String?) {
        setProgress { it.copy(phase = "error", message = phaseMsg) }
    }

    /** Concurrently fetch up to 5 pages; null = failed page. */
    private suspend fun fetchBatch(
        token: String,
        workspaceId: String,
        pages: List<Int>,
    ): Map<Int, List<UsageRecord>?> = coroutineScope {
        pages.map { p ->
            async {
                try {
                    p to api.fetchUsagePage(token, workspaceId, p)
                } catch (e: Exception) {
                    p to null
                }
            }
        }.awaitAll().toMap()
    }

    fun syncAllAsync(scope: CoroutineScope, mode: String) {
        scope.launch {
            ensureQuota()
            syncUsage(mode)
        }
    }

    // ------------------------------------------------------------------
    // Pages / settings / account (server.py API parity — 活跃账号)
    // ------------------------------------------------------------------

    suspend fun recordsPage(page: Int, pageSize: Int, model: String?, days: Int?): PageResult<UsageRecordRow> {
        val aid = activeAccountId()
        val (records, total) = usageDao.usageRecordsPage(page, pageSize, model, days, aid)
        // 注入缓存的 key 显示名称 (desktop server.py /api/usage/records parity)
        val names = db.settingsDao().getKeyNames()
        val enriched = if (names.isEmpty()) records
        else records.map { r ->
            val n = r.keyId?.let(names::get)
            if (n != null) r.copy(keyName = n) else r
        }
        return PageResult(enriched, total)
    }

    suspend fun sessionsPage(page: Int, pageSize: Int, days: Int?): PageResult<SessionStat> {
        val aid = activeAccountId()
        val (records, total) = usageDao.sessionStatsPage(page, pageSize, days, aid)
        // 注入 key 名称 + 无 session 的拆分行按 key 分组, 前端据此显示"未归属"
        // (desktop server.py /api/usage/sessions parity)
        val names = db.settingsDao().getKeyNames()
        val enriched = records.map { st ->
            val keyGroup = !st.keyId.isNullOrEmpty() && st.sessionId.startsWith("key_")
            val n = st.keyId?.let(names::get)
            st.copy(
                sessionId = if (keyGroup) "" else st.sessionId,
                keyName = n?.takeIf { it.isNotEmpty() },
            )
        }
        return PageResult(enriched, total)
    }

    suspend fun listModels(): List<String> = usageDao.listModels(activeAccountId())

    /** Persisted sync progress/state (desktop get_sync_state parity). */
    suspend fun syncState(): SyncState = syncDao.getSyncState()

    suspend fun settings(): AppSettings = db.settingsDao().getSettings()

    suspend fun saveSettings(patch: AppSettings): AppSettings = db.settingsDao().saveSettings(patch)

    /**
     * 退出登录当前活跃账号 (清其数据, 保留账号行).
     * 退出前记录账号 id, 退出后清理其配额缓存槽 — 防止残留旧配额 (desktop v2.1.0 fix parity).
     */
    suspend fun logout() {
        val aid = activeAccountId()
        syncDao.clearAccount()
        if (aid != 0) clearQuotaSlot(aid)
        _quota.value = null
    }

    @Deprecated("Use loginSuccess(token, hint, mode)", ReplaceWith("loginSuccess(token, workspaceHint, \"relogin\")"))
    suspend fun saveLogin(token: String, workspaceHint: String) = loginSuccess(token, workspaceHint, "relogin")

    suspend fun checkUpdate(currentVersion: String): UpdateInfo = updateApi.checkUpdate(currentVersion)
}
