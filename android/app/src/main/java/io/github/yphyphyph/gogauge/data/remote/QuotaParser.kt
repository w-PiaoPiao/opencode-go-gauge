package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.QuotaWindow
import io.github.yphyphyph.gogauge.util.parseIsoInstant
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.time.LocalDateTime
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
        parseIsoInstant(raw)?.let { return it.toString() }
        return try {
            LocalDateTime.parse(raw).atZone(ZoneOffset.UTC).toInstant().toString()
        } catch (e: Exception) {
            raw
        }
    }

    private fun secondsUntil(isoText: String, nowMillis: Long): Int {
        if (isoText.isBlank()) return 0
        val target = parseIsoInstant(isoText)?.toEpochMilli() ?: return 0
        return maxOf(0L, (target - nowMillis) / 1000L).toInt()
    }

    /** 规范 ISO-Z 值; [isoFromText] 解析失败时原样透传, 周期字段要挡掉这类脏值. */
    private fun isoOrNull(raw: String): String? {
        val text = isoFromText(raw)
        return if (text.endsWith("Z") && text.contains("T")) text else null
    }

    /**
     * 订阅计费周期起止 (``access.startsAt`` / ``endsAt``) — desktop ``parse_go_period`` parity.
     *
     * 月 meter 只有 resetsAt, 周期起点必须取 startsAt: Go 月度周期按自然月
     * (实测 10-08 → 11-08 共 31 天), 「下次重置 - 30 天」回推会得到未来起点,
     * 「本周期」筛选随即变成空集.
     */
    fun parseGoPeriod(payload: JsonElement?): Pair<String?, String?> {
        val obj = payload as? JsonObject ?: return null to null
        val access = obj["access"] as? JsonObject ?: return null to null
        return isoOrNull(access["startsAt"].asText()) to isoOrNull(access["endsAt"].asText())
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
