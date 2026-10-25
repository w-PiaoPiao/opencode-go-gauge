package io.github.yphyphyph.gogauge.ui.components

import io.github.yphyphyph.gogauge.data.model.DailyStat
import io.github.yphyphyph.gogauge.data.model.ModelTrendSeries

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
