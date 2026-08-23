package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.QuotaWindow
import java.time.Instant
import java.time.temporal.ChronoUnit

/**
 * Quota dashboard HTML parser — 1:1 port of opencode_api.py (desktop).
 * Parses rollingUsage / weeklyUsage / monthlyUsage JS literals for usagePercent + resetInSec.
 * Field order varies (usagePercent first or resetInSec first) — both handled.
 */
object QuotaParser {

    private const val LABEL_ROLLING = "5h Rolling"
    private const val LABEL_WEEKLY = "Weekly"
    private const val LABEL_MONTHLY = "Monthly"

    // usagePercent first
    private val ROLLING_PCT_FIRST = Regex(
        """rollingUsage:\s*\${'$'}R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)""" +
            """[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"""
    )
    // resetInSec first
    private val ROLLING_RESET_FIRST = Regex(
        """rollingUsage:\s*\${'$'}R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)""" +
            """[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"""
    )
    private val WEEKLY_PCT_FIRST = Regex(
        """weeklyUsage:\s*\${'$'}R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)""" +
            """[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"""
    )
    private val WEEKLY_RESET_FIRST = Regex(
        """weeklyUsage:\s*\${'$'}R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)""" +
            """[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"""
    )
    private val MONTHLY_PCT_FIRST = Regex(
        """monthlyUsage:\s*\${'$'}R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)""" +
            """[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"""
    )
    private val MONTHLY_RESET_FIRST = Regex(
        """monthlyUsage:\s*\${'$'}R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)""" +
            """[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}"""
    )

    private class WindowRe(val pctFirst: Regex, val resetFirst: Regex)

    private val PAIRS = listOf(
        Pair(LABEL_ROLLING, WindowRe(ROLLING_PCT_FIRST, ROLLING_RESET_FIRST)),
        Pair(LABEL_WEEKLY, WindowRe(WEEKLY_PCT_FIRST, WEEKLY_RESET_FIRST)),
        Pair(LABEL_MONTHLY, WindowRe(MONTHLY_PCT_FIRST, MONTHLY_RESET_FIRST)),
    )

    private fun clampPercent(v: Double): Double = v.coerceIn(0.0, 100.0)

    private fun parseWindow(pctRe: Regex, resetRe: Regex, html: String): Pair<Double, Int>? {
        val m = pctRe.find(html)
        if (m != null) {
            return m.groupValues[1].toDouble() to m.groupValues[2].toDouble().toInt()
        }
        val m2 = resetRe.find(html)
        if (m2 != null) {
            return m2.groupValues[2].toDouble() to m2.groupValues[1].toDouble().toInt()
        }
        return null
    }

    /** Parse quota windows from dashboard HTML. now = UTC epoch millis. */
    fun parseQuotaHtml(html: String, nowMillis: Long = System.currentTimeMillis()): List<QuotaWindow> {
        val now = Instant.ofEpochMilli(nowMillis)
        val windows = mutableListOf<QuotaWindow>()
        for ((label, re) in PAIRS) {
            val parsed = parseWindow(re.pctFirst, re.resetFirst, html) ?: continue
            val used = clampPercent(parsed.first)
            val resetIn = parsed.second.coerceAtLeast(0)
            val resetAt = now.plus(resetIn.toLong(), ChronoUnit.SECONDS).toString()
            windows += QuotaWindow(
                label = label,
                used = used,
                remaining = (100.0 - used).round1(),
                total = 100.0,
                unit = "%",
                resetAt = resetAt,
                resetInSec = resetIn,
            )
        }
        return windows
    }

    private fun Double.round1(): Double = Math.round(this * 10) / 10.0
}
