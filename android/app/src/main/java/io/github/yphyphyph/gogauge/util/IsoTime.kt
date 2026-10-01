package io.github.yphyphyph.gogauge.util

import java.time.Instant
import java.time.OffsetDateTime

/**
 * 宽容 ISO-8601 解析 — 全项目唯一的 ISO 时间串入口。
 *
 * 不能直接用 `Instant.parse`: 它使用的 ISO_INSTANT 在 Android 13 及以下
 * (libcore 基于 OpenJDK ≤ 11) 只接受字面 "Z", 形如
 * "2026-09-02T11:31:04.353+00:00" 会抛 DateTimeParseException
 * (JDK-8166138, JDK 12 才修复; 实测 API 33 失败 / API 35 通过)。
 * 先按 Instant 解析, 失败再按带偏移的 ISO 日期时间解析; 无时区/非法串返回 null。
 */
fun parseIsoInstant(raw: String?): Instant? {
    if (raw.isNullOrBlank()) return null
    return try {
        Instant.parse(raw)
    } catch (e: Exception) {
        try {
            OffsetDateTime.parse(raw).toInstant()
        } catch (e2: Exception) {
            null
        }
    }
}
