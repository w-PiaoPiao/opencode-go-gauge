package io.github.yphyphyph.gogauge.data.repository

import io.github.yphyphyph.gogauge.data.model.UsageRecord

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
)
