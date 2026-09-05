package io.github.yphyphyph.gogauge.data.model

/** Aggregated totals — mirrors db.totals() output (desktop). */
data class Totals(
    val requestCount: Int = 0,
    val sessionCount: Int = 0,
    val totalInputTokens: Long = 0L,     // input + cache read + cache write
    val uncachedInputTokens: Long = 0L,
    val totalReasoningTokens: Long = 0L,
    val cacheHitTokens: Long = 0L,
    val cacheWriteTokens: Long = 0L,
    val totalOutputTokens: Long = 0L,
    val totalCostUsd: Double = 0.0,
    val hitRate: Double = 0.0,           // percent
) {
    val totalTokens: Long
        get() = totalInputTokens + totalOutputTokens + totalReasoningTokens
}

/** One day aggregate — mirrors db.daily_stats output (desktop). */
data class DailyStat(
    val date: String,
    val totalInputTokens: Long,
    val uncachedInputTokens: Long,
    val totalReasoningTokens: Long,
    val cacheHitTokens: Long,
    val cacheWriteTokens: Long,
    val totalOutputTokens: Long,
    val totalCostUsd: Double,
    val requestCount: Int,
    val hitRate: Double,
)

/** One hour of today — mirrors db.today_trend output (desktop). */
data class HourStat(
    val hour: String,
    val input: Long,
    val output: Long,
    val reasoning: Long,
)

/** Per-model aggregate — mirrors db.model_stats output (desktop). */
data class ModelStat(
    val model: String,
    val requestCount: Int,
    val sessionCount: Int,
    val totalInputTokens: Long,
    val uncachedInputTokens: Long,
    val totalReasoningTokens: Long,
    val cacheHitTokens: Long,
    val cacheWriteTokens: Long,
    val totalOutputTokens: Long,
    val totalCostUsd: Double,
    val hitRate: Double,
)

/** Sync metadata — mirrors db.get_sync_state output (desktop). */
data class SyncState(
    val lastSyncAt: String? = null,
    val lastSyncStatus: String? = null,
    val lastSyncError: String? = null,
    val lastInsertedCount: Int = 0,
    val deepestPageFetched: Int = -1,
    val totalRecords: Int = 0,
    val oldestRecordAt: String? = null,
    val newestRecordAt: String? = null,
)

/** In-flight sync progress — mirrors server._sync_state (desktop); account = 正在同步的账号名. */
data class SyncProgress(
    val running: Boolean = false,
    val mode: String = "",
    val page: Int = 0,
    val inserted: Int = 0,
    val phase: String = "idle", // idle | quota | usage | done | error
    val message: String = "",
    val account: String = "",
)

/** App settings — mirrors db._DEFAULT_SETTINGS (desktop). */
data class AppSettings(
    val syncIntervalSec: Int = 300,   // 1/5/15/30 min
    val windowDays: Int? = 60,        // 30/60/90/180, null = all
    val autoSync: Boolean = true,
    val showAccountsPanel: Boolean = false,  // 账户总览面板开关 (v2.1.0)
)

/** Dashboard bundle — mirrors GET /api/dashboard (desktop). */
data class DashboardData(
    val loggedIn: Boolean,
    val quota: QuotaResult?,
    val totals: Totals,
    val today: Totals,
    val daily: List<DailyStat>,
    val trend: List<DailyStat>,
    val todayTrend: List<HourStat>,
    val models: List<ModelStat>,
    val sync: SyncState,
    val progress: SyncProgress,
    val range: String,
    val usdCny: Double,
    val serverTime: String,
)

/** Account info — mirrors db._account_dict (desktop v2.0.0 + provider v2.1.0). */
data class AccountInfo(
    val id: Int = 0,
    val name: String,
    val workspaceId: String,
    val resolvedWorkspaceId: String?,
    val hasToken: Boolean,
    val provider: String = PROVIDER_OPENCODE,
)

/** 单账号总览卡片数据 — mirrors server.py /api/accounts/overview 的 accounts[i] (desktop v2.1.0). */
data class AccountOverview(
    val id: Int,
    val name: String,
    val active: Boolean,
    /** 配额缓存槽当前值; null = 尚未就绪 (后台刷新中) */
    val quota: QuotaResult?,
    val today: Totals,
    val todayTrend: List<HourStat>,
    val daily7: List<DailyStat>,
    val lastSyncAt: String?,
    val lastSyncStatus: String?,
)

/** 账户总览聚合 — mirrors GET /api/accounts/overview 响应体 (desktop v2.1.0). */
data class AccountsOverviewData(
    val accounts: List<AccountOverview>,
    val usdCny: Double,
)
