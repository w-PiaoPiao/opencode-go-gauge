package io.github.yphyphyph.gogauge.data.repository

import io.github.yphyphyph.gogauge.data.model.DashboardData
import io.github.yphyphyph.gogauge.data.model.PageResult
import io.github.yphyphyph.gogauge.data.model.QuotaResult
import io.github.yphyphyph.gogauge.data.model.SessionStat
import io.github.yphyphyph.gogauge.data.model.SyncProgress
import io.github.yphyphyph.gogauge.data.model.UsageRecord
import io.github.yphyphyph.gogauge.data.model.UsageRecordRow
import io.github.yphyphyph.gogauge.data.remote.AuthException
import io.github.yphyphyph.gogauge.data.remote.ExchangeApi
import io.github.yphyphyph.gogauge.data.remote.OpenCodeApi
import io.github.yphyphyph.gogauge.data.remote.OpenCodeApiException
import io.github.yphyphyph.gogauge.data.remote.UpdateApi
import io.github.yphyphyph.gogauge.data.remote.UpdateInfo
import io.github.yphyphyph.gogauge.data.db.AppDatabase
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
import java.time.ZoneId
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
 * Dashboard repository — ports of server.py (sync engine, quota/exchange caches)
 * plus db.py aggregations, exposed as a single service to ViewModels.
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
    // Caches (server.py parity)
    // ------------------------------------------------------------------

    private class QuotaCache {
        @Volatile var at = 0.0
        @Volatile var data: QuotaResult? = null
    }
    private val quotaCache = QuotaCache()
    private val quotaMutex = Mutex()
    private var quotaRefreshing = false
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
    // Quota refresh (server.py _ensure_quota_async parity)
    // ------------------------------------------------------------------

    /** Refresh quota in the background if cache is stale; non-blocking for dashboard. */
    fun ensureQuotaAsync(scope: CoroutineScope) {
        scope.launch { ensureQuota() }
    }

    suspend fun ensureQuota() {
        val now = System.currentTimeMillis() / 1000.0
        if (quotaCache.data != null && now - quotaCache.at < QUOTA_CACHE_TTL) return
        quotaMutex.withLock {
            if (quotaRefreshing) return
            val token = syncDao.getToken()
            if (token.isEmpty()) return
            quotaRefreshing = true
        }
        try {
            // failure also writes cache (null data) so the UI doesn't retry every load
            val token = syncDao.getToken()
            val hint = syncDao.getWorkspaceHint()
            quotaCache.at = System.currentTimeMillis() / 1000.0
            quotaCache.data = try {
                api.fetchQuota(token, hint)
            } catch (e: Exception) {
                android.util.Log.e("GoGauge", "quota refresh failed", e)
                null
            }
            _quota.value = quotaCache.data
            android.util.Log.i("GoGauge", "quota refreshed: success=" + (quotaCache.data?.success) + " err=" + (quotaCache.data?.error))
        } finally {
            quotaRefreshing = false
        }
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
    // Dashboard bundle (server.py /api/dashboard parity)
    // ------------------------------------------------------------------

    suspend fun loadDashboard(range: String): DashboardData {
        val token = syncDao.getToken()
        val quota = if (token.isNotEmpty()) _quota.value else null
        val now = java.time.LocalDateTime.now()
            .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
        return DashboardData(
            loggedIn = token.isNotEmpty(),
            quota = quota,
            totals = usageDao.totals(range),
            today = usageDao.totals("today"),
            daily = usageDao.dailyStats(7),
            trend = usageDao.dailyStats(30),
            todayTrend = usageDao.todayTrend(),
            models = usageDao.modelStats(range),
            sync = syncDao.getSyncState(),
            progress = _progress.value,
            range = range,
            usdCny = usdCny(),
            serverTime = now,
        )
    }

    // ------------------------------------------------------------------
    // Sync engine (server.py sync_usage parity)
    // ------------------------------------------------------------------

    suspend fun syncUsage(mode: String): SyncResult {
        val token = syncDao.getToken()
        if (token.isEmpty()) return SyncResult(ok = false, error = "未登录")
        if (_progress.value.running) return SyncResult(ok = false, error = "已有同步任务进行中")

        var workspaceId = syncDao.getWorkspaceHint()
        val windowDays = db.settingsDao().getSettings().windowDays

        _progress.value = SyncProgress(running = true, mode = mode, phase = "usage")

        try {
            // ensure workspace id is resolved
            try {
                val resolved = api.resolveWorkspaceId(workspaceId, token)
                if (!workspaceId.startsWith("wrk_")) {
                    workspaceId = resolved
                    syncDao.saveResolvedWorkspace(resolved, Instant.now().toString())
                }
            } catch (e: AuthException) {
                failSync("工作区解析失败: ${e.message}", e.message)
                return SyncResult(ok = false, error = e.message)
            } catch (e: OpenCodeApiException) {
                failSync("工作区解析失败: ${e.message}", e.message)
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
                    val inserted = usageDao.insertUsageRecords(result.map { it.toEntity(Instant.now().toString()) })
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
                        failSync("第 ${page - 4} 页拉取失败: $msg", msg)
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
                usageDao.pruneOldRecords("-${windowDays} days")
            }

            if (failedPages > 0) {
                val msg = "完成, 但 $failedPages 页拉取失败 (数据不完整, 可再次全量同步补全)"
                syncDao.updateSyncStateAndTotals("partial", msg, totalInserted)
                setProgress { it.copy(phase = "done", message = msg) }
                _progress.value = _progress.value.copy(running = false)
                return SyncResult(ok = true, partial = true, failedPages = failedPages, inserted = totalInserted, pages = page)
            }
            val msg = "同步完成, 新增 $totalInserted 条"
            syncDao.updateSyncStateAndTotals("ok", null, totalInserted)
            setProgress { it.copy(phase = "done", message = msg) }
            _progress.value = _progress.value.copy(running = false)
            return SyncResult(ok = true, inserted = totalInserted, pages = page)
        } catch (e: Exception) {
            syncDao.updateSyncStateAndTotals("error", e.message, 0)
            failSync(e.message ?: "同步失败", e.message)
            return SyncResult(ok = false, error = e.message)
        } finally {
            _progress.value = _progress.value.copy(running = false)
        }
    }

    private suspend fun failSync(phaseMsg: String, errMsg: String?) {
        setProgress { it.copy(phase = "error", message = phaseMsg) }
        if (errMsg != null) syncDao.updateSyncStateAndTotals("error", errMsg, 0)
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
    // Pages / settings / account (server.py API parity)
    // ------------------------------------------------------------------

    suspend fun recordsPage(page: Int, pageSize: Int, model: String?, days: Int?): PageResult<UsageRecordRow> {
        val (records, total) = usageDao.usageRecordsPage(page, pageSize, model, days)
        return PageResult(records, total)
    }

    suspend fun sessionsPage(page: Int, pageSize: Int, days: Int?): PageResult<SessionStat> {
        val (records, total) = usageDao.sessionStatsPage(page, pageSize, days)
        return PageResult(records, total)
    }

    suspend fun listModels(): List<String> = usageDao.listModels()

    suspend fun settings(): AppSettings = db.settingsDao().getSettings()

    suspend fun saveSettings(patch: AppSettings): AppSettings = db.settingsDao().saveSettings(patch)

    suspend fun logout() = syncDao.clearAccount()

    /** Save login token + workspace hint — port of db.save_token (desktop). */
    suspend fun saveLogin(token: String, workspaceHint: String) {
        syncDao.saveToken(
            token.trim(),
            workspaceHint.trim().ifEmpty { "Default" },
            Instant.now().toString(),
        )
    }

    suspend fun checkUpdate(currentVersion: String): UpdateInfo = updateApi.checkUpdate(currentVersion)

    suspend fun account() = syncDao.getAccount()
}
