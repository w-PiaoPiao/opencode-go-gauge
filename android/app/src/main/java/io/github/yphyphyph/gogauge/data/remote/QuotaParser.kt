package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.QuotaWindow
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

/**
 * Quota parser — 1:1 port of opencode_api.py (desktop, 2026-09 控制台改版后).
 *
 * ``GET /console/api/go/status`` 的 access.meters.{fiveHour,week,month} 各含
 * limitMicroCents / usedMicroCents (单位为 1e-8 USD, 值可能是数字或字符串),
 * 以及可选 resetsAt; 月额度无 resetsAt 时重置时间取 access.endsAt。
 * 旧 dashboard HTML 解析已随改版下线。
 */
object QuotaParser {

    private const val LABEL_ROLLING = "5h Rolling"
    private const val LABEL_WEEKLY = "Weekly"
    private const val LABEL_MONTHLY = "Monthly"

    private fun JsonElement?.asDouble(default: Double = 0.0): Double {
        val text = (this as? JsonPrimitive)?.content ?: return default
        if (text.isEmpty() || text == "null") return default
        return text.toDoubleOrNull() ?: default
    }

    private fun JsonElement?.asText(): String {
        val text = (this as? JsonPrimitive)?.content ?: return ""
        return if (text == "null") "" else text
    }

    private fun clampPercent(v: Double): Double = v.coerceIn(0.0, 100.0)

    private fun round2(v: Double): Double = Math.round(v * 100) / 100.0

    /** ISO 时间串规范为 ``...Z`` (无时区按 UTC 处理, 解析失败原样返回). */
    private fun isoFromText(raw: String): String {
        if (raw.isBlank()) return ""
        try {
            return Instant.parse(raw).toString()
        } catch (e: Exception) {
            // 继续尝试带偏移与无时区两种形态
        }
        try {
            return OffsetDateTime.parse(raw).toInstant().toString()
        } catch (e: Exception) {
            // 继续尝试无时区
        }
        return try {
            LocalDateTime.parse(raw).atZone(ZoneOffset.UTC).toInstant().toString()
        } catch (e: Exception) {
            raw
        }
    }

    private fun secondsUntil(isoText: String, nowMillis: Long): Int {
        if (isoText.isBlank()) return 0
        return try {
            val target = Instant.parse(isoText).toEpochMilli()
            maxOf(0L, (target - nowMillis) / 1000L).toInt()
        } catch (e: Exception) {
            0
        }
    }

    /**
     * Parse quota windows from ``/console/api/go/status`` JSON.
     * 三个窗口按 5h/weekly/monthly 顺序; 缺少某 meter 或 limit<=0 时跳过该项。
     */
    fun parseGoStatus(payload: JsonElement?, nowMillis: Long = System.currentTimeMillis()): List<QuotaWindow> {
        val obj = payload as? JsonObject ?: return emptyList()
        val access = obj["access"] as? JsonObject ?: return emptyList()
        val meters = access["meters"] as? JsonObject ?: return emptyList()
        val periodEnd = isoFromText(access["endsAt"].asText())
        val windows = mutableListOf<QuotaWindow>()
        val pairs = listOf(
            LABEL_ROLLING to "fiveHour",
            LABEL_WEEKLY to "week",
            LABEL_MONTHLY to "month",
        )
        for ((label, key) in pairs) {
            val meter = meters[key] as? JsonObject ?: continue
            val limit = meter["limitMicroCents"].asDouble()
            val usedRaw = meter["usedMicroCents"].asDouble()
            if (limit <= 0) continue
            val used = clampPercent(usedRaw / limit * 100.0)
            val resetAt = isoFromText(meter["resetsAt"].asText()).ifEmpty { periodEnd }
            windows += QuotaWindow(
                label = label,
                used = round2(used),
                remaining = round2(100.0 - used),
                total = 100.0,
                unit = "%",
                resetAt = resetAt,
                resetInSec = secondsUntil(resetAt, nowMillis),
            )
        }
        return windows
    }
}
