package io.github.yphyphyph.gogauge.data.repository

import io.github.yphyphyph.gogauge.data.model.UsageRecord
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/**
 * created_at (服务端 ISO, 可能带 Z/偏移) -> 本地日 "yyyy-MM-dd".
 *
 * 与 SQLite 的 date(created_at, 'localtime') 等价 (同一系统时区), 但落库成实体列,
 * 使日界过滤能走 idx_usage_account_localdate. 解析失败返回 null, 查询侧仍可用
 * COALESCE 回退 (这类行极少, 不影响索引整体收益).
 */
internal fun localDateOf(createdAt: String): String? = try {
    Instant.parse(createdAt.replace("Z", "+00:00"))
        .atZone(ZoneId.systemDefault())
        .toLocalDate()
        .format(DateTimeFormatter.ISO_LOCAL_DATE)
} catch (e: Exception) {
    null
}

private val UTC_BUCKET_FMT: DateTimeFormatter =
    DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")

/**
 * time_bucket (UTC "yyyy-MM-dd HH:mm:ss", charts 表的桶格式) -> 本地日 "yyyy-MM-dd".
 *
 * 与 SQLite date(time_bucket, 'localtime') 等价. 格式与 created_at 的 ISO 串不同,
 * 故单独解析 (先按 UTC 解读再转到系统时区).
 */
internal fun localDateOfBucket(timeBucket: String): String? = try {
    java.time.LocalDateTime.parse(timeBucket, UTC_BUCKET_FMT)
        .toInstant(java.time.ZoneOffset.UTC)
        .atZone(ZoneId.systemDefault())
        .toLocalDate()
        .format(DateTimeFormatter.ISO_LOCAL_DATE)
} catch (e: Exception) {
    null
}

fun UsageRecord.toEntity(syncedAt: String) = io.github.yphyphyph.gogauge.data.db.UsageRecordEntity(
    usgId = usgId,
    createdAt = createdAt,
    model = model,
    provider = provider,
    inputTokens = inputTokens,
    outputTokens = outputTokens,
    reasoningTokens = reasoningTokens,
    cacheReadTokens = cacheReadTokens,
    cacheWrite5mTokens = cacheWrite5mTokens,
    cacheWrite1hTokens = cacheWrite1hTokens,
    costRaw = costRaw,
    costUsd = costUsd,
    keyId = keyId,
    sessionId = sessionId,
    plan = plan,
    syncedAt = syncedAt,
    localDate = localDateOf(createdAt),
)
