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
    val costRaw: Long,         // unit 1e-8 USD (Int 会在单条 > $21.47 时溢出归零)
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
