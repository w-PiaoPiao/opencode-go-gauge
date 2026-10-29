package io.github.yphyphyph.gogauge.ui.components

import io.github.yphyphyph.gogauge.data.model.DailyStat
import io.github.yphyphyph.gogauge.data.model.ModelTrendSeries
import kotlin.math.floor

/**
 * 统计页纯计算 — 对齐桌面 app/web/app.js 的 c866440 / aa389b7 / df22e97 语义.
 *
 * 这些函数不依赖 Compose, 单测直接覆盖: 热力图摘要 (峰值/连续天数)、两条趋势图的
 * 前置无数据裁剪、模型趋势的第一个有量日.
 */

/** 热力图摘要 (desktop heatmapSummaryHtml parity): 峰值随所选指标, 连续天数只看「当天有请求」. */
data class HeatmapSummary(
    val peakValue: Double,
    val peakDate: String,
    val currentStreak: Int,
    val longestStreak: Int,
)

/** 热力图指标取值 — desktop metricValue parity (cost / requests / tokens). */
fun dailyMetricValue(d: DailyStat, metric: String): Double = when (metric) {
    "cost" -> d.totalCostUsd
    "requests" -> d.requestCount.toDouble()
    else -> (d.totalInputTokens + d.totalOutputTokens + d.totalReasoningTokens).toDouble()
}

/**
 * 热力图分档锚点 — desktop heatmapBreaks parity.
 *
 * 只在「有量日」上取分位: 窗口里大量 0 值会把分位压到 0 附近, 取出来的锚点毫无区分度.
 * p50 / p75 / p90 三个锚点切出 4 个非零档 —— 一个异常峰值再高也只占满色那一档,
 * 不会像「按峰值线性归一」那样把其余日子全挤进最低档 (档 3 甚至整档空置).
 * 有量日不足 8 天时分位不稳, 退回等比四档.
 */
fun heatmapBreaks(values: List<Double>): List<Double> {
    val on = values.filter { it > 0 }.sorted()
    if (on.size < 8) {
        val max = maxOf(values.maxOrNull() ?: 0.0, 1.0)
        return listOf(max * 0.25, max * 0.5, max * 0.75)
    }
    fun q(p: Double): Double {
        val i = p * (on.size - 1)
        val lo = floor(i).toInt()
        val hi = minOf(lo + 1, on.size - 1)
        return on[lo] + (on[hi] - on[lo]) * (i - lo)
    }
    return listOf(q(0.5), q(0.75), q(0.9))
}

/**
 * 逐日档位 0..4 — desktop levelOf parity.
 *
 * 0 = 无数据; 1..4 按 [heatmapBreaks] 的锚点递增. 有请求但该指标为 0 的日子
 * (免费模型 / 空转请求) 落最低可见档 1 —— 它不属于「没数据」, 画成空白会丢信息.
 */
fun heatmapLevels(values: List<Double>, active: List<Boolean>): List<Int> {
    val breaks = heatmapBreaks(values)
    return values.mapIndexed { i, v ->
        when {
            v > 0 -> minOf(4, 1 + breaks.count { v > it })
            active.getOrElse(i) { false } -> 1
            else -> 0
        }
    }
}

/**
 * 热力图摘要: 峰值 (随指标, 带日期) / 当前连续 / 最长连续.
 *
 * 连续天数按「当天有请求」判定, 与指标无关 —— 免费模型可能成本为 0, 按成本算会把
 * 连续天数误判成断掉; 当前连续在最后一天 (今天) 为 0 时即中断, 与热力图今天的
 * 格子一致 (desktop 同口径).
 */
fun heatmapSummary(days: List<DailyStat>, metric: String): HeatmapSummary {
    var peakValue = -1.0
    var peakDate = ""
    days.forEach { d ->
        val v = dailyMetricValue(d, metric)
        if (v > peakValue) {
            peakValue = v
            peakDate = d.date
        }
    }
    val on = days.map { it.requestCount > 0 }
    var longest = 0
    var run = 0
    on.forEach { v ->
        run = if (v) run + 1 else 0
        if (run > longest) longest = run
    }
    // 当前连续: 从最后一天回溯, 今天为 0 即中断
    var i = on.lastIndex
    var current = 0
    while (i >= 0 && on[i]) {
        current += 1
        i -= 1
    }
    return HeatmapSummary(maxOf(peakValue, 0.0), peakDate, current, longest)
}

/**
 * 用量趋势的第一个有量日下标 — desktop chartTrend 的 firstOn: 请求/成本/Token
 * 任一非零即算有量; 全窗口无数据返回 -1 (调用方按原样画, 保持平线表现).
 */
fun usageTrendLeadIndex(trend: List<DailyStat>): Int = trend.indexOfFirst { d ->
    d.requestCount > 0 || d.totalCostUsd > 0.0 ||
        d.totalInputTokens + d.totalOutputTokens + d.totalReasoningTokens > 0
}

/**
 * 模型趋势的第一个有量日下标 — 只看可见模型 (排除集是用户显式过滤), 判定用
 * input/output/cost 任一非零 (与当前维度无关, 换维度时起点不跳).
 * 全窗口无数据返回 -1.
 */
fun modelTrendLeadIndex(
    days: List<String>,
    series: List<ModelTrendSeries>,
    excludedModels: Set<String>,
): Int {
    val visible = series.filter { it.model !in excludedModels }
    if (visible.isEmpty()) return -1
    for (i in days.indices) {
        val any = visible.any { s ->
            s.input.getOrElse(i) { 0L } + s.output.getOrElse(i) { 0L } > 0L ||
                s.cost.getOrElse(i) { 0.0 } > 0.0
        }
        if (any) return i
    }
    return -1
}
