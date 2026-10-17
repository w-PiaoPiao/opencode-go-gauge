package io.github.yphyphyph.gogauge.data.db

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * 月度重置周期起点推算 — mirrors desktop db.monthly_cycle_start 行为:
 * 「本月」= 当前月度重置周期 (最近激活的 $10 付费期间), 起点 = 下次重置 - 30 天,
 * 重置时刻已过则取该时刻 (精确周期边界).
 */
class MonthlyCycleTest {

    private val now = "2026-08-29 12:00:00"

    @Test
    fun `reset in future - cycle start is reset minus 30 days`() {
        assertEquals("2026-08-24 12:00:00", MonthlyCycle.start("2026-09-23 12:00:00", now))
    }

    @Test
    fun `reset in past - cycle start is the reset instant itself`() {
        assertEquals("2026-08-19 12:00:00", MonthlyCycle.start("2026-08-19 12:00:00", now))
    }

    @Test
    fun `reset beyond 30 days - never returns a future start`() {
        // Go 月度按自然月 (实测 10-08 → 11-08 = 31 天): reset-30 天仍落在未来,
        // 未来起点会让「本周期」筛选恒为空 → 回退 null 走滚动 30 天.
        assertNull(MonthlyCycle.start("2026-09-29 12:00:00", now))  // 重置在 31 天后
        // 恰满 30 天: 起点 = now, 不算未来, 仍按回推返回.
        assertEquals("2026-08-29 12:00:00", MonthlyCycle.start("2026-09-28 12:00:00", now))
    }

    @Test
    fun `null or blank reset falls back to null`() {
        assertNull(MonthlyCycle.start(null, now))
        assertNull(MonthlyCycle.start("", now))
        assertNull(MonthlyCycle.start("   ", now))
    }

    @Test
    fun `unparseable reset falls back to null`() {
        assertNull(MonthlyCycle.start("2026/09/23 12:00", now))
        assertNull(MonthlyCycle.start("not-a-date", now))
    }

    @Test
    fun `nowUtc matches storage format`() {
        val nowUtc = MonthlyCycle.nowUtc()
        assertEquals(19, nowUtc.length)
        assertEquals('-', nowUtc[4])
        assertEquals(' ', nowUtc[10])
        assertEquals(':', nowUtc[13])
    }

    // ------------------------------------------------------------------
    // startWithPeriod: 真实计费周期 (commandcode) — desktop monthly_cycle_start parity
    // ------------------------------------------------------------------

    // 2026-08-29 12:00:00 UTC = 上方 now 字符串的毫秒值
    private val nowMs = java.time.LocalDateTime.parse(now, FMT)
        .atZone(java.time.ZoneOffset.UTC).toInstant().toEpochMilli()

    @Test
    fun `active period - start used directly`() {
        // 周期已开始且未结束: 直接返回记录的真实起点, 不做顺延
        assertEquals(
            "2026-08-20 01:03:43",
            MonthlyCycle.startWithPeriod(
                "2026-08-20 01:03:43", "2026-09-20 01:03:43", null, nowMs,
            ),
        )
    }

    @Test
    fun `future period start - never returned`() {
        // 起点在未来 (接口给出尚未开始的周期 / 本机时钟落后于服务端): 返回它会让
        // 「本周期」筛选恒为空 (local_date >= 未来日期 筛出 0 条) → 回退滚动 30 天
        assertNull(
            MonthlyCycle.startWithPeriod(
                "2026-09-02 01:03:43", "2026-10-02 01:03:43", null, nowMs,
            ),
        )
    }

    @Test
    fun `missing period end - falls back to null`() {
        // 终点缺失: 无法顺延过期周期, 回退滚动 30 天 (避免把上个周期拉进「本月」)
        assertNull(MonthlyCycle.startWithPeriod("2026-08-20 01:03:43", null, null, nowMs))
    }

    @Test
    fun `natural month span rolls by calendar month`() {
        // 31 天自然月周期 (实测 Go 月度 10-08 → 11-08) 按日历月推进: 用固定跨度反复
        // 顺延会累积漂移, 日号必须随锚点保持 (now = 2026-08-29 12:00)
        assertEquals(
            "2026-08-08 01:03:43",
            MonthlyCycle.startWithPeriod(
                "2026-01-08 01:03:43", "2026-02-08 01:03:43", null, nowMs,
            ),
        )
    }

    @Test
    fun `month end anchor is not degraded`() {
        // 锚点 01-31: 逐月累加会丢锚点 (02-28 → 03-28, 此后永远停在 28 号), 必须从
        // 原始起点一次算出 (plusMonths). 周期序列 01-31 → 02-28 → 03-31 → 04-30 →
        // 05-31 → 06-30 → 07-31 → 08-31; now = 08-29 落在 [07-31, 08-31) 内.
        assertEquals(
            "2026-07-31 00:00:00",
            MonthlyCycle.startWithPeriod(
                "2026-01-31 00:00:00", "2026-02-28 00:00:00", null, nowMs,
            ),
        )
    }

    @Test
    fun `expired period - rolls forward by span`() {
        // 周期 8/1-8/15 (跨度 14 天), now 已在 8/29: 顺延到覆盖 now 的最近周期起点
        assertEquals(
            "2026-08-29 12:00:00",
            MonthlyCycle.startWithPeriod(
                "2026-08-01 12:00:00", "2026-08-15 12:00:00", null, nowMs,
            ),
        )
    }

    @Test
    fun `inverted period - falls back to null`() {
        // end <= start: 数据非法 → null (调用方回退滚动 30 天)
        assertNull(
            MonthlyCycle.startWithPeriod(
                "2026-09-01 00:00:00", "2026-08-01 00:00:00", null, nowMs,
            ),
        )
    }

    @Test
    fun `no period bounds - falls back to monthly reset rule`() {
        assertEquals(
            "2026-08-24 12:00:00",
            MonthlyCycle.startWithPeriod(null, null, "2026-09-23 12:00:00", nowMs),
        )
    }

    @Test
    fun `nothing recorded - returns null`() {
        assertNull(MonthlyCycle.startWithPeriod(null, null, null, nowMs))
    }

    companion object {
        private val FMT = java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
    }
}
