package io.github.yphyphyph.gogauge.data.model

/** One usage record — mirrors opencode_api.UsageRecord (desktop). */
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
    val costRaw: Int,          // unit 1e-8 USD
    val keyId: String,
    val sessionId: String,
    val plan: String? = null,
) {
    val costUsd: Double get() = costRaw / 100_000_000.0
}

/** Row for the usage-records list — mirrors db.usage_records_page output (desktop). */
data class UsageRecordRow(
    val usgId: String,
    val createdAt: String,
    val model: String,
    val provider: String?,
    val inputTokens: Int,
    val outputTokens: Int,
    val reasoningTokens: Int,
    val cacheReadTokens: Int,
    val cacheWriteTokens: Int,
    val costUsd: Double,
    val sessionId: String?,
    val plan: String?,
)

/** One aggregated session — mirrors db.session_stats_page output (desktop). */
data class SessionStat(
    val sessionId: String,
    val requestCount: Int,
    val totalInputTokens: Int,       // incl. cache read + write
    val uncachedInputTokens: Int,
    val totalOutputTokens: Int,
    val totalReasoningTokens: Int,
    val totalCostUsd: Double,
    val lastAt: String,
)

/** Paginated result with total count. */
data class PageResult<T>(
    val records: List<T>,
    val total: Int,
)
