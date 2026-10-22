package io.github.yphyphyph.gogauge.ui.components

import io.github.yphyphyph.gogauge.data.model.DailyStat
import io.github.yphyphyph.gogauge.data.model.ModelTrendSeries
import org.junit.Assert.assertEquals
import org.junit.Test

/** 统计页纯计算 — 夹具与桌面 app/web/app.js (c866440 / aa389b7 / df22e97) 语义逐条对齐. */
class StatsMathTest {

    private fun day(
        date: String,
        requests: Int = 0,
        cost: Double = 0.0,
        input: Long = 0L,
        output: Long = 0L,
    ) = DailyStat(
        date = date,
        totalInputTokens = input,
        uncachedInputTokens = input,
        totalReasoningTokens = 0L,
        cacheHitTokens = 0L,
        cacheWriteTokens = 0L,
        totalOutputTokens = output,
        totalCostUsd = cost,
        requestCount = requests,
        hitRate = 0.0,
    )

    @Test
    fun `heatmap summary peak follows selected metric`() {
        val days = listOf(
            day("2026-10-01", requests = 1, cost = 0.5),
            day("2026-10-02", requests = 2, cost = 0.2),
            day("2026-10-03", requests = 0, cost = 0.9), // 成本峰值日可以没有请求
            day("2026-10-04", requests = 3, cost = 0.1),
            day("2026-10-05", requests = 4, cost = 0.3),
        )
        val byCost = heatmapSummary(days, "cost")
        assertEquals("2026-10-03", byCost.peakDate)
        assertEquals(0.9, byCost.peakValue, 1e-9)
        val byReq = heatmapSummary(days, "requests")
        assertEquals("2026-10-05", byReq.peakDate)
        assertEquals(4.0, byReq.peakValue, 1e-9)
        // 连续天数与指标无关: 10-01..02 (10-03 断) / 10-04..05 当前连续
        assertEquals(2, byCost.longestStreak)
        assertEquals(2, byCost.currentStreak)
        assertEquals(2, byReq.longestStreak)
    }

    @Test
    fun `current streak starts from yesterday when today has no usage`() {
        val days = listOf(
            day("2026-10-01", requests = 1),
            day("2026-10-02", requests = 1),
            day("2026-10-03", requests = 1),
            day("2026-10-04", requests = 0),
        )
        val s = heatmapSummary(days, "tokens")
        assertEquals(3, s.currentStreak)
        assertEquals(3, s.longestStreak)
    }

    @Test
    fun `no usage at all yields zero streaks`() {
        val days = listOf(day("2026-10-01"), day("2026-10-02"))
        val s = heatmapSummary(days, "tokens")
        assertEquals(0, s.currentStreak)
        assertEquals(0, s.longestStreak)
        assertEquals(0.0, s.peakValue, 1e-9)
    }

    @Test
    fun `usage trend trims only leading empty days`() {
        val trend = listOf(
            day("d0"),
            day("d1"),
            day("d2", requests = 2),
            day("d3"), // 中间空日保留
            day("d4", requests = 1),
        )
        assertEquals(2, usageTrendLeadIndex(trend))
        // 第一天就有量: 不裁剪
        assertEquals(0, usageTrendLeadIndex(listOf(day("d0", input = 1))))
        // 全窗口无数据: -1 (调用方保持原样)
        assertEquals(-1, usageTrendLeadIndex(listOf(day("d0"), day("d1"))))
    }

    @Test
    fun `model trend lead ignores excluded models and uses any dimension`() {
        val series = listOf(
            ModelTrendSeries("a", input = listOf(0, 0, 5), output = listOf(0, 0, 0), cost = listOf(0.0, 0.0, 0.0)),
            ModelTrendSeries("b", input = listOf(0, 3, 0), output = listOf(0, 0, 0), cost = listOf(0.0, 0.0, 0.0)),
        )
        val days = listOf("d0", "d1", "d2")
        assertEquals(1, modelTrendLeadIndex(days, series, emptySet()))
        assertEquals(2, modelTrendLeadIndex(days, series, setOf("b")))
        assertEquals(-1, modelTrendLeadIndex(days, series, setOf("a", "b")))
        // 只有费用也算有量 (与当前维度无关)
        val costOnly = listOf(
            ModelTrendSeries("c", input = listOf(0, 0), output = listOf(0, 0), cost = listOf(0.0, 0.5)),
        )
        assertEquals(1, modelTrendLeadIndex(listOf("d0", "d1"), costOnly, emptySet()))
    }
}
