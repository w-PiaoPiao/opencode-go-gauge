package io.github.yphyphyph.gogauge.util

import org.junit.Assert.assertEquals
import org.junit.Test

class FmtTest {

    @Test
    fun tokensAbbreviation() {
        assertEquals("1.20B", Fmt.tokens(1.2e9))
        assertEquals("3.45M", Fmt.tokens(3_450_000))
        assertEquals("5.6k", Fmt.tokens(5600))
        assertEquals("999", Fmt.tokens(999))
        assertEquals("0", Fmt.tokens(0))
        assertEquals("-5", Fmt.tokens(-5)) // desktop JS Math.round parity
    }

    @Test
    fun intGrouping() {
        assertEquals("1,234,567", Fmt.int(1234567))
        assertEquals("0", Fmt.int(0))
    }

    @Test
    fun moneyCny() {
        assertEquals("¥7.20", Fmt.money(1.0, "CNY", 7.2))
        assertEquals("¥0.0072", Fmt.money(0.001, "CNY", 7.2))
        assertEquals("¥0.0000", Fmt.money(0.0000001, "CNY", 7.2))
    }

    @Test
    fun moneyUsd() {
        assertEquals("$1.00", Fmt.money(1.0, "USD", 7.2))
        assertEquals("$0.1235", Fmt.money(0.12345, "USD", 7.2)) // half-up rounding
        assertEquals("$0", Fmt.money(0.0, "USD", 7.2))
    }

    @Test
    fun duration() {
        assertEquals("2 天 3 小时", Fmt.dur(2 * 86400 + 3 * 3600, "天", "小时", "分钟", "即将重置"))
        assertEquals("1 小时 30 分钟", Fmt.dur(5400, "天", "小时", "分钟", "即将重置"))
        assertEquals("5 分钟", Fmt.dur(300, "天", "小时", "分钟", "即将重置"))
        assertEquals("即将重置", Fmt.dur(0, "天", "小时", "分钟", "即将重置"))
        assertEquals("即将重置", Fmt.dur(-10, "天", "小时", "分钟", "即将重置"))
    }

    @Test
    fun relativeTime() {
        val now = System.currentTimeMillis()
        assertEquals("刚刚", Fmt.relative(java.time.Instant.ofEpochMilli(now - 10_000).toString(), "刚刚", "分钟前", "小时前", "天前", "从未同步"))
        assertEquals("3 分钟前", Fmt.relative(java.time.Instant.ofEpochMilli(now - 180_000).toString(), "刚刚", "分钟前", "小时前", "天前", "从未同步"))
        assertEquals("2 小时前", Fmt.relative(java.time.Instant.ofEpochMilli(now - 7_200_000).toString(), "刚刚", "分钟前", "小时前", "天前", "从未同步"))
        assertEquals("1 天前", Fmt.relative(java.time.Instant.ofEpochMilli(now - 90_000_000).toString(), "刚刚", "分钟前", "小时前", "天前", "从未同步"))
        assertEquals("从未同步", Fmt.relative(null, "刚刚", "分钟前", "小时前", "天前", "从未同步"))
    }

    @Test
    fun maskWorkspace() {
        assertEquals("wrk_abcd…", Fmt.maskWs("wrk_abcdefghijklmnop")) // slice(0,8) + ellipsis
        assertEquals("wrk_123", Fmt.maskWs("wrk_123"))
    }
}
