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

/**
 * One hour of today — mirrors db.today_trend output (desktop).
 *
 * ``input`` 为未缓存输入; cacheRead/cacheWrite 供首页「含缓存」口径求和
 * (v2.2.1a, desktop c7f841c parity)。
 */
data class HourStat(
    val hour: String,
    val input: Long,
    val output: Long,
    val reasoning: Long,
    val cacheRead: Long = 0L,
    val cacheWrite: Long = 0L,
) {
    /** 含缓存总 TOKEN 消耗 (与 Totals.totalTokens 同口径): 未缓存输入 + 缓存读 + 缓存写 + 输出 + 推理. */
    val totalTokens: Long get() = input + cacheRead + cacheWrite + output + reasoning
}

/** 单个模型的等长日序列 (缺日补 0) — mirrors model_daily_stats.series 元素. */
data class ModelTrendSeries(
    val model: String,
    val input: List<Long>,
    val output: List<Long>,
    val cost: List<Double>,
)

/** 模型用量趋势数据源 — mirrors db.model_daily_stats {days, series} (桌面 /api/model_trend). */
data class ModelTrendData(
    val days: List<String>,
    val series: List<ModelTrendSeries>,
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
    /**
     * GOAT (commandcode): 全周期聚合请求数 (明细接口仅 24h/100 条, 直接用
     * totalRecords 显示会偏小) — desktop sync.chart_requests parity.
     * 非 commandcode 或 charts 未就绪时为 null。
     */
    val chartRequests: Int? = null,
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

/** App settings — mirrors db._DEFAULT_SETTINGS (desktop) + Android 专属键. */
data class AppSettings(
    val syncIntervalSec: Int = 300,   // 1/5/15/30 min
    val windowDays: Int? = 60,        // 30/60/90/180, null = all
    val autoSync: Boolean = true,
    val showAccountsPanel: Boolean = false,  // 账户总览面板开关 (v2.1.0)
    /** 图表动画开关 (默认关闭: 低配设备上每次刷新重建动画是掉帧大头; desktop chart_animation parity). */
    val chartAnimation: Boolean = false,
    /** 常驻通知开关 (v2.2.0b, Android 专属): 低优先级 ongoing 通知显示三窗口余量。 */
    val persistentNotification: Boolean = false,
    /**
     * 区分 DeepSeek 峰谷 (v2.2.2, desktop ds_peak_split parity): 统计页把 deepseek
     * flash 拆成「峰」「谷」两条; 只改统计口径, 不动同步数据。
     */
    val dsPeakSplit: Boolean = false,
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
    /**
     * 本份数据对应的排除模型集 (desktop /api/dashboard 的 excluded_models 回显 parity).
     *
     * totals/daily/trend 按此集合重聚合; models 恒为全量 (环形图图例需保留被排除
     * 模型以便点击加回). 容器比较用于判断"当前数据是否为目标口径"。
     */
    val excluded: Set<String> = emptySet(),
    /**
     * 本份数据的 models 是否按峰谷分档 (desktop v2.2.2): 首页 false / 统计页 true。
     * 首页与统计页共用 dashboard 对象, 切换时以此判据决定是否重载 (同一 range 下
     * 两者口径不同, 只看 range+excluded 会复用错误数据)。
     */
    val peakSplit: Boolean = false,
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
