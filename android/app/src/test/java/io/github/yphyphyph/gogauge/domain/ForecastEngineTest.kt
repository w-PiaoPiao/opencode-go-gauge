package io.github.yphyphyph.gogauge.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * ForecastEngine 纯函数单测 — 四组口径:
 * 数据充足 / 不足、opencode % 换算、GOAT $ 直读、5h 速率外推。
 */
class ForecastEngineTest {

    private fun days(vararg costs: Double): List<ForecastEngine.DayCost> =
        costs.mapIndexed { i, c -> ForecastEngine.DayCost("2026-09-%02d".format(i + 1), c) }

    private val nowMs = 1_759_000_000_000L // 固定时刻, 结果可断言

    private fun opencodeInput(
        daily: List<ForecastEngine.DayCost> = days(5.0, 0.0, 10.0, 3.0, 2.0, 0.0, 10.0),
        usedPct: Double = 50.0,
        periodCost: Double = 20.0,
        recent2h: Double = 4.0,
        used5h: Double = 20.0,
        usedWeek: Double = 30.0,
    ) = ForecastEngine.Input(
        dailyCosts = daily,
        periodStartMs = nowMs - 15L * 86_400_000,
        periodEndMs = nowMs + 15L * 86_400_000,
        monthUsedPercent = usedPct,
        monthRemainingPercent = 100.0 - usedPct,
        monthRemainingAmount = null, // opencode: 无金额口径
        fiveHourCapAmount = null,
        weekCapAmount = null,
        fiveHourUsedPercent = used5h,
        weekUsedPercent = usedWeek,
        periodCostUsd = periodCost,
        recent2hCost = recent2h,
    )

    private fun goatInput(
        daily: List<ForecastEngine.DayCost> = days(5.0, 0.0, 10.0, 3.0, 2.0, 0.0, 10.0),
        monthRemaining: Double = 35.0,
        cap5h: Double = 14.0,
        used5h: Double = 20.0,
    ) = ForecastEngine.Input(
        dailyCosts = daily,
        periodStartMs = nowMs - 15L * 86_400_000,
        periodEndMs = nowMs + 15L * 86_400_000,
        monthUsedPercent = 50.0,
        monthRemainingPercent = 50.0,
        monthRemainingAmount = monthRemaining, // GOAT: 直读月池 × 剩余%
        fiveHourCapAmount = cap5h,
        weekCapAmount = 35.0,
        fiveHourUsedPercent = used5h,
        weekUsedPercent = 30.0,
        periodCostUsd = 20.0,
        recent2hCost = 4.0,
    )

    // ---- 1. 数据充足: opencode % 换算路径 ----

    @Test
    fun `opencode percent conversion from period cost`() {
        val f = ForecastEngine.forecast(opencodeInput(), nowMs)
        // usdPerPercent = 20 / 50 = 0.4 → 月剩余 = 0.4 × 50 = $20
        assertEquals(20.0, f.monthRemainingUsd!!, 0.01)
        // 日均 = (5+0+10+3+2+0+10)/7 ≈ 4.286 → 月还能用 ≈ 20/4.286 ≈ 4.67 天
        assertEquals(4.67, f.monthDaysLeft!!, 0.1)
        // 今日预算 = 20 / 15 天 ≈ 1.33
        assertEquals(1.33, f.dailyBudgetUsd!!, 0.01)
        assertFalse(f.degraded)
    }

    // ---- 2. GOAT $ 直读路径 ----

    @Test
    fun `goat reads remaining amount directly`() {
        val f = ForecastEngine.forecast(goatInput(), nowMs)
        assertEquals(35.0, f.monthRemainingUsd!!, 0.01)
        // 5h: GOAT 用真实 cap → 剩余 = 14 × 80% = $11.2; 近 2h $4 → 速率 $2/h → 5.6h → 336 分钟
        assertEquals(336L, f.fiveHourExhaustInMin!!)
        // 周: 35 × 70% = $24.5 → 24.5/4.286 ≈ 5.72 天
        assertEquals(5.72, f.weekDaysLeft!!, 0.1)
    }

    // ---- 3. 数据不足: 退化标记 + 天数类为空 ----

    @Test
    fun `insufficient data degrades forecast`() {
        // 全 0 消耗: avg=0 → 天数类不可算
        val f1 = ForecastEngine.forecast(opencodeInput(daily = days(0.0, 0.0, 0.0)), nowMs)
        assertTrue(f1.degraded)
        assertNull(f1.monthDaysLeft)
        assertNull(f1.projectedPeriodCostUsd)
        // GOAT 直读金额不受历史影响, 预算仍可算
        val f2 = ForecastEngine.forecast(goatInput(daily = days(0.0, 0.0, 0.0)), nowMs)
        assertTrue(f2.degraded)
        assertNotNull(f2.dailyBudgetUsd)
        assertEquals(35.0, f2.monthRemainingUsd!!, 0.01)
        // 只有 1 个非零日 (<2): 同样退化
        val f3 = ForecastEngine.forecast(opencodeInput(daily = days(5.0, 0.0, 0.0)), nowMs)
        assertTrue(f3.degraded)
    }

    // ---- 4. % 换算的放弃条件 ----

    @Test
    fun `skips conversion when usage below 1 percent`() {
        // 已用 0.5% + 无金额口径 → 除数噪声放大, 放弃换算 → 月剩余 null
        val f = ForecastEngine.forecast(opencodeInput(usedPct = 0.5), nowMs)
        assertNull(f.monthRemainingUsd)
        assertNull(f.monthDaysLeft)
    }

    @Test
    fun `no conversion without period cost`() {
        // 已耗 $ 为 0 (周期刚开始) → 换算无依据
        val f = ForecastEngine.forecast(opencodeInput(usedPct = 30.0, periodCost = 0.0), nowMs)
        assertNull(f.monthRemainingUsd)
    }

    // ---- 5. 5h 速率外推 ----

    @Test
    fun `five hour exhaust minutes from recent rate`() {
        // opencode: usdPerPercent=0.4, 5h 剩余 = 0.4 × 80 = $32 → 32/(4/2) = 16h = 960 分钟 (>300)
        val f = ForecastEngine.forecast(opencodeInput(), nowMs)
        assertEquals(960L, f.fiveHourExhaustInMin!!)
    }

    @Test
    fun `five hour null without recent activity`() {
        val f = ForecastEngine.forecast(opencodeInput(recent2h = 0.0), nowMs)
        assertNull(f.fiveHourExhaustInMin)
    }

    // ---- 6. 周期终末不输出预算 ----

    @Test
    fun `no daily budget in final half day`() {
        val input = goatInput().copy(periodEndMs = nowMs + 6L * 3600_000) // 剩 0.25 天
        val f = ForecastEngine.forecast(input, nowMs)
        assertNull(f.dailyBudgetUsd)
    }
}
