package io.github.yphyphyph.gogauge.util

import java.text.DecimalFormat
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * Formatting helpers — 1:1 ports of app.js (desktop frontend).
 * Locale-independent numeric formatting (desktop used en-US grouping).
 */
object Fmt {

    private val intFmt = DecimalFormat("#,##0")

    /** 1.2B / 3.4M / 5.6k / 123 — port of fmtTokens. */
    fun tokens(n: Number): String {
        val v = n.toDouble()
        return when {
            v >= 1e9 -> String.format("%.2fB", v / 1e9)
            v >= 1e6 -> String.format("%.2fM", v / 1e6)
            v >= 1e3 -> String.format("%.1fk", v / 1e3)
            else -> java.lang.Long.toString(Math.round(v))
        }
    }

    /** Thousands-separated integer — port of fmtInt. */
    fun int(n: Number): String = intFmt.format(n.toLong())

    /** Money — port of fmtMoney (desktop). */
    fun money(usd: Double, currency: String, usdCny: Double): String {
        val v = usd
        if (currency == "CNY") {
            val c = v * usdCny
            return "¥" + if (c >= 1) String.format("%.2f", c) else String.format("%.4f", c)
        }
        if (v >= 1) return "$" + String.format("%.2f", v)
        if (v > 0) return "$" + String.format("%.4f", v)
        return "$0"
    }

    /** Duration d/h/m — port of fmtDur. */
    fun dur(sec: Long, dUnit: String, hUnit: String, mUnit: String, soon: String): String {
        val s = sec.coerceAtLeast(0)
        val d = s / 86400
        val h = (s % 86400) / 3600
        val m = (s % 3600) / 60
        return when {
            d > 0 -> "$d $dUnit $h $hUnit"
            h > 0 -> "$h $hUnit $m $mUnit"
            m > 0 -> "$m $mUnit"
            else -> soon
        }
    }

    /** Full datetime — port of fmtDateTime. */
    fun dateTime(iso: String?): String {
        if (iso.isNullOrBlank()) return "—"
        return try {
            val dt = ZonedDateTime.parse(iso).withZoneSameInstant(ZoneId.systemDefault())
            dt.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
        } catch (e: Exception) {
            "—"
        }
    }

    /** Short datetime MM-dd HH:mm — port of fmtDateTimeShort. */
    fun dateTimeShort(iso: String?): String {
        if (iso.isNullOrBlank()) return "—"
        return try {
            val dt = ZonedDateTime.parse(iso).withZoneSameInstant(ZoneId.systemDefault())
            dt.format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
        } catch (e: Exception) {
            "—"
        }
    }

    /** Relative time — port of fmtRelative. */
    fun relative(iso: String?, justNow: String, minAgo: String, hrAgo: String, dayAgo: String, never: String): String {
        if (iso.isNullOrBlank()) return never
        return try {
            val t = Instant.parse(iso).toEpochMilli()
            val diff = (System.currentTimeMillis() - t) / 1000.0
            when {
                diff < 60 -> justNow
                diff < 3600 -> "${Math.floor(diff / 60).toLong()} $minAgo"
                diff < 86400 -> "${Math.floor(diff / 3600).toLong()} $hrAgo"
                else -> "${Math.floor(diff / 86400).toLong()} $dayAgo"
            }
        } catch (e: Exception) {
            never
        }
    }

    /** Mask long workspace id — port of maskWs (desktop). */
    fun maskWs(ws: String): String =
        if (ws.length > 12) ws.substring(0, 8) + "…" else ws
}
