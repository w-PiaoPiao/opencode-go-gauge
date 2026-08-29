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
}
