package io.github.yphyphyph.gogauge.data.model

/** One usage record — mirrors opencode_api/commandcode_api UsageRecord (desktop). */
data class UsageRecord(
    val usgId: String,
    val createdAt: String,
    val model: String,
    val provider: String,
    val inputTokens: Int,
    val outputTokens: Int,
    val reasoningTokens: Int,
    val cacheReadTokens: Int,
    val cacheWrite5mTokens: Int,
    val cacheWrite1hTokens: Int,
    val costRaw: Long,         // unit 1e-8 USD (Int 会在单条 > $21.47 时溢出归零)
    val keyId: String,
    val sessionId: String,
    val plan: String? = null,
    // commandcode: meta.totalCost 已是 USD (costRaw 占位 0), 直接覆盖 costUsd
    val costUsdOverride: Double? = null,
) {
    val costUsd: Double
        get() = costUsdOverride ?: costRaw / 100_000_000.0
}

/**
 * One aggregated chart bucket — mirrors commandcode_api.UsageChartBucket (desktop).
 * 对应 /internal/usage/charts 的 (模型 × 5min 时间桶) 全周期聚合; tokens_in 已含缓存读。
 */
data class UsageChartBucket(
    val model: String,
    val provider: String,
    val timeBucket: String,    // UTC "yyyy-MM-dd HH:mm:ss"
    val requests: Int,
    val inputCost: Double,
    val outputCost: Double,
    val cacheCost: Double,
    val totalCost: Double,
    val creditsTotal: Double,
    val tokensIn: Int,
    val tokensOut: Int,
    val tokensTotal: Int,
    val cacheReadTokens: Int,
    val cacheCreationTokens: Int,
)

/** Row for the usage-records list — mirrors db.usage_records_page output (desktop). */
data class UsageRecordRow(
    val usgId: String,
    val createdAt: String,
    val model: String,
    val provider: String?,
    val inputTokens: Long,
    val outputTokens: Long,
    val reasoningTokens: Long,
    val cacheReadTokens: Long,
    val cacheWriteTokens: Long,
    val costUsd: Double,
    val sessionId: String?,
    val plan: String?,
    val keyId: String? = null,
    val keyName: String? = null,
)

/** One aggregated session — mirrors db.session_stats_page output (desktop). */
data class SessionStat(
    val sessionId: String,
    val requestCount: Int,
    val totalInputTokens: Long,      // incl. cache read + write
    val uncachedInputTokens: Long,
    val totalOutputTokens: Long,
    val totalReasoningTokens: Long,
    val totalCostUsd: Double,
    val lastAt: String,
    val keyId: String? = null,
    val keyName: String? = null,
)

/** Paginated result with total count. */
data class PageResult<T>(
    val records: List<T>,
    val total: Int,
)
