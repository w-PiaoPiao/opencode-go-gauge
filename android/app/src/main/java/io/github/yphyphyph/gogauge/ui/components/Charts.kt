package io.github.yphyphyph.gogauge.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.github.mikephil.charting.charts.BarChart
import com.github.mikephil.charting.charts.LineChart
import com.github.mikephil.charting.charts.PieChart
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.BarData
import com.github.mikephil.charting.data.BarDataSet
import com.github.mikephil.charting.data.BarEntry
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.data.PieData
import com.github.mikephil.charting.data.PieDataSet
import com.github.mikephil.charting.data.PieEntry
import com.github.mikephil.charting.formatter.IndexAxisValueFormatter
import com.github.mikephil.charting.formatter.ValueFormatter
import com.github.mikephil.charting.highlight.Highlight
import com.github.mikephil.charting.listener.OnChartValueSelectedListener
import io.github.yphyphyph.gogauge.data.model.DailyStat
import io.github.yphyphyph.gogauge.data.model.HourStat
import io.github.yphyphyph.gogauge.data.model.ModelStat
import io.github.yphyphyph.gogauge.ui.Strings
import io.github.yphyphyph.gogauge.ui.theme.GgChart
import io.github.yphyphyph.gogauge.util.Fmt

private fun Color.toArgbInt(): Int = android.graphics.Color.argb(
    (this.alpha * 255).toInt(), (this.red * 255).toInt(), (this.green * 255).toInt(), (this.blue * 255).toInt()
)

/**
 * Chart wrappers for MPAndroidChart — equivalents of the desktop Chart.js charts.
 * Charts are View-based, wrapped via AndroidView; `update` re-applies data on recomposition
 * (theme/language/currency switches re-render automatically).
 */

/** Today's 24h input/output bar chart — desktop chartToday. */
@Composable
fun TodayBarChart(
    data: List<HourStat>,
    s: Strings,
    labelColor: Color,
    gridLineColor: Color,
    animate: Boolean = false,
    modifier: Modifier = Modifier,
) {
    // Rebuild the dataset only when the data or labels change; recomposition (theme,
    // syncing, progress updates) then reuses the cached BarData instead of rebuilding.
    val barData = remember(data, s) {
        val inEntries = data.mapIndexed { i, h -> BarEntry(i.toFloat(), h.input.toFloat()) }
        val outEntries = data.mapIndexed { i, h -> BarEntry(i.toFloat(), h.output.toFloat()) }
        val dsIn = BarDataSet(inEntries, s.input).apply {
            color = GgChart.Input.toArgbInt()
            setDrawValues(false)
        }
        val dsOut = BarDataSet(outEntries, s.output).apply {
            color = GgChart.Output.toArgbInt()
            setDrawValues(false)
        }
        BarData(dsIn, dsOut).apply {
            barWidth = 0.35f
            isHighlightEnabled = false
        }
    }
    val hourLabels = remember(data) { data.map { it.hour } }
    AndroidView(
        modifier = modifier.fillMaxWidth().height(250.dp),
        factory = { ctx ->
            BarChart(ctx).apply { description.isEnabled = false }
        },
        update = { chart ->
            chart.legend.isEnabled = true
            chart.legend.textSize = 11f
            chart.legend.textColor = labelColor.toArgbInt()
            chart.xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                setDrawGridLines(false)
                textSize = 10f
                textColor = labelColor.toArgbInt()
                labelCount = 8
                granularity = 1f
                valueFormatter = IndexAxisValueFormatter(hourLabels)
            }
            chart.axisLeft.apply {
                textSize = 10f
                textColor = labelColor.toArgbInt()
                gridColor = gridLineColor.toArgbInt()
                valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float) = Fmt.tokens(value.toLong())
                }
            }
            chart.axisRight.isEnabled = false
            if (chart.data !== barData) {
                chart.data = barData
                // 图表动画开关 (默认关): 仅在新数据换代时播放, 重组/主题切换不重复动画
                if (animate) chart.animateY(400)
            }
            chart.invalidate()
        },
    )
}

/**
 * Model usage doughnut — desktop chartModel (v2.2.0 图例排除交互 parity).
 *
 * 图例常驻全量 top 模型: 点击图例项或扇区 = 全局排除/恢复该模型 (总卡/Token 构成/
 * 排行/趋势一起变); 被排除项扇区隐藏、图例项画删除线, 再点即加回. 数值统一在图例
 * 展示 (窄屏 + 小扇区时扇区数值标签必然互相重叠, MPAndroidChart 无法按扇区控制),
 * 扇区只用颜色区分. MPAndroidChart 内置图例不支持删除线与点击回调, 故禁用并在
 * Compose 侧自绘 (Chart.js 原生体验).
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ModelPieChart(
    models: List<ModelStat>,
    dim: String,
    excludedModels: Set<String>,
    onToggleModel: (String) -> Unit,
    s: Strings,
    labelColor: Color,
    currency: String,
    usdCny: Double,
    animate: Boolean = false,
    modifier: Modifier = Modifier,
) {
    val palette = remember {
        listOf(
            GgChart.Input, GgChart.Output, GgChart.Reasoning, GgChart.Cache, GgChart.Cost, GgChart.Extra,
        ).map { it.toArgbInt() }
    }
    val fmt: (Double) -> String = if (dim == "cost") { v -> Fmt.money(v, currency, usdCny) } else { v -> Fmt.tokens(v) }
    // 全量 top6 定序: 颜色与图例都按全量排序的索引分配 —— 排除某项不改变其余项颜色
    val top = remember(models, dim) { models.sortedByDescending { getVal(it, dim) }.take(6) }
    // Rebuild slices only when models/dim/exclusions change; 扇区只画参与统计的模型,
    // 占比随排除自动归一.
    val pieData = remember(top, dim, excludedModels) {
        val visible = top.withIndex().filter { it.value.model !in excludedModels }
        val entries = visible.map { PieEntry(getVal(it.value, dim).toFloat(), it.value.model) }
        val ds = PieDataSet(entries, "").apply {
            colors = visible.map { palette[it.index % palette.size] }
            sliceSpace = 2f
            // 扇区数值标签在窄屏 + 小扇区上必然互相重叠 (MPAndroidChart 无法按扇区
            // 控制是否绘制): 数值统一放到下方自绘图例展示
            setDrawValues(false)
        }
        PieData(ds)
    }
    Column(modifier.fillMaxWidth()) {
        AndroidView(
            modifier = Modifier.fillMaxWidth().height(230.dp),
            factory = { ctx ->
                PieChart(ctx).apply {
                    description.isEnabled = false
                    setDrawEntryLabels(false)
                    holeRadius = 60f
                    isRotationEnabled = true
                    setNoDataText("")  // 全部模型被排除时不留英文占位提示
                }
            },
            update = { chart ->
                // 扇区点击 = 排除/恢复该模型 (与图例点击同一路径; 手机上点扇区更直觉)
                chart.setOnChartValueSelectedListener(object : OnChartValueSelectedListener {
                    override fun onValueSelected(e: Entry?, h: Highlight?) {
                        val label = (e as? PieEntry)?.label ?: return
                        chart.highlightValues(null)
                        onToggleModel(label)
                    }

                    override fun onNothingSelected() {}
                })
                if (chart.data !== pieData) {
                    chart.data = pieData
                    if (animate) chart.animateY(400)
                }
                chart.legend.isEnabled = false  // 图例在 Compose 侧自绘 (删除线 + 点击)
                chart.invalidate()
            },
        )
        // 图例: 常驻全量 top, 点击切换排除; 被排除项删除线 + 降透明度; 数值随名称展示
        FlowRow(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 6.dp),
            horizontalArrangement = Arrangement.Center,
        ) {
            top.forEachIndexed { i, m ->
                val excluded = m.model in excludedModels
                Row(
                    modifier = Modifier
                        .clickable { onToggleModel(m.model) }
                        // 触控目标 ≥44dp: 原实现 ~25dp, 图例密集时容易点错相邻模型
                        .defaultMinSize(minHeight = 44.dp)
                        .padding(horizontal = 7.dp, vertical = 5.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        Modifier
                            .size(8.dp)
                            .background(Color(palette[i % palette.size]), CircleShape),
                    )
                    Spacer(Modifier.width(5.dp))
                    Text(
                        m.model,
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        textDecoration = if (excluded) TextDecoration.LineThrough else null,
                        color = if (excluded) labelColor.copy(alpha = 0.55f) else labelColor,
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        fmt(getVal(m, dim)),
                        fontSize = 10.sp,
                        maxLines = 1,
                        color = labelColor.copy(alpha = if (excluded) 0.45f else 0.75f),
                    )
                }
            }
        }
    }
}

/**
 * 模型排行/饼图的取值口径 (三端一致):
 * - input: **含缓存命中的总输入** (未命中 + 缓存命中)。缓存命中通常占绝大多数,
 *   只取 uncachedInputTokens 会让数值严重偏低
 * - output: 总输出 token
 * - cost: 金额
 */
private fun getVal(m: ModelStat, dim: String): Double = when (dim) {
    "output" -> m.totalOutputTokens.toDouble()
    "cost" -> m.totalCostUsd
    else -> m.totalInputTokens.toDouble()
}

/** "2026-09-01" -> "9/1" (手机窄屏省宽度); 解析失败回退原串后 5 位. */
private fun shortDate(iso: String): String = try {
    val d = java.time.LocalDate.parse(iso)
    "${d.monthValue}/${d.dayOfMonth}"
} catch (e: Exception) {
    iso.takeLast(5)
}

/**
 * 24h 迷你趋势 — desktop sparklineSvg parity: 纯 Canvas 折线 + 12% 透明度填充,
 * 无图表实例, 随账号卡片轻量渲染.
 */
@Composable
fun Sparkline(
    values: List<Long>,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val n = values.size
        if (n == 0) return@Canvas
        val maxV = (values.maxOrNull() ?: 0L).coerceAtLeast(1L).toFloat()
        val w = size.width
        val h = size.height
        val pad = 2.dp.toPx()
        val step = if (n > 1) w / (n - 1) else w
        val points = values.mapIndexed { i, v ->
            Offset(i * step, h - pad - (v / maxV) * (h - 2 * pad))
        }
        val linePath = Path().apply {
            moveTo(points.first().x, points.first().y)
            for (i in 1 until points.size) lineTo(points[i].x, points[i].y)
        }
        drawPath(
            Path().apply {
                addPath(linePath)
                lineTo(w, h)
                lineTo(0f, h)
                close()
            },
            color = color.copy(alpha = 0.12f),
        )
        drawPath(
            linePath,
            color = color,
            style = Stroke(width = 1.6.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round),
        )
    }
}

/**
 * Usage trend 3-line — desktop chartTrend (cost left, requests right, tokens hidden axis).
 *
 * MPAndroidChart 只有左右两轴, 无法像桌面 (Chart.js 的 y2 = display:false 隐藏轴) 给
 * 总 TOKEN 独立比例: 直接挂左轴时 1e9 量级的 token 会把费用轴刻度顶到 ¥2686751200
 * 这类荒谬值 (费用线同时被压成平线). 这里按费用轴量程归一化 token 线 (峰值对齐,
 * 视觉走向与桌面一致), 费用/请求双轴刻度保持真实可读.
 */
@Composable
fun TrendLineChart(
    trend: List<DailyStat>,
    s: Strings,
    labelColor: Color,
    gridLineColor: Color,
    currency: String,
    usdCny: Double,
    animate: Boolean = false,
    modifier: Modifier = Modifier,
) {
    // Rebuild the series only when data or labels change; not on every recomposition.
    val lineData = remember(trend, s) {
        val mk = { i: Int, v: Double -> Entry(i.toFloat(), v.toFloat()) }
        val costDs = LineDataSet(trend.mapIndexed { i, d -> mk(i, d.totalCostUsd) }, s.totalCost).apply {
            color = GgChart.Input.toArgbInt()
            lineWidth = 2f
            setDrawCircles(false)
            setDrawValues(false)
            axisDependency = com.github.mikephil.charting.components.YAxis.AxisDependency.LEFT
        }
        val reqDs = LineDataSet(trend.mapIndexed { i, d -> mk(i, d.requestCount.toDouble()) }, s.totalRequests).apply {
            color = GgChart.Output.toArgbInt()
            lineWidth = 2f
            setDrawCircles(false)
            setDrawValues(false)
            enableDashedLine(8f, 6f, 0f)
            axisDependency = com.github.mikephil.charting.components.YAxis.AxisDependency.RIGHT
        }
        val tokenValues = trend.map {
            (it.totalInputTokens + it.totalOutputTokens + it.totalReasoningTokens).toDouble()
        }
        val costMax = trend.maxOfOrNull { it.totalCostUsd } ?: 0.0
        val tokenMax = tokenValues.maxOrNull() ?: 0.0
        val tokenScale = when {
            tokenMax <= 0.0 -> 0.0
            costMax > 0.0 -> costMax / tokenMax  // 归一化到费用轴量程 (峰值对齐)
            else -> 1.0  // 费用全 0: 轴上只有 token 一条线, 原样画
        }
        val tokDs = LineDataSet(trend.mapIndexed { i, _ -> mk(i, tokenValues[i] * tokenScale) }, s.totalTokens).apply {
            color = GgChart.Reasoning.toArgbInt()
            lineWidth = 2f
            setDrawCircles(false)
            setDrawValues(false)
            axisDependency = com.github.mikephil.charting.components.YAxis.AxisDependency.LEFT
        }
        LineData(costDs, reqDs, tokDs)
    }
    // 手机窄屏: "09-01" 8 个标签必粘连 -> 短格式 "9/1" + 减少标签数
    val dateLabels = remember(trend) { trend.map { shortDate(it.date) } }
    AndroidView(
        modifier = modifier.fillMaxWidth().height(260.dp),
        factory = { ctx ->
            LineChart(ctx).apply { description.isEnabled = false }
        },
        update = { chart ->
            chart.legend.isEnabled = true
            chart.legend.textSize = 11f
            chart.legend.textColor = labelColor.toArgbInt()
            chart.xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                setDrawGridLines(false)
                textSize = 10f
                textColor = labelColor.toArgbInt()
                setLabelCount(5, false)
                granularity = 1f
                valueFormatter = IndexAxisValueFormatter(dateLabels)
            }
            chart.axisLeft.apply {
                textSize = 10f
                textColor = labelColor.toArgbInt()
                gridColor = gridLineColor.toArgbInt()
                valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float) = Fmt.money(value.toDouble(), currency, usdCny)
                }
            }
            chart.axisRight.apply {
                isEnabled = true
                textSize = 10f
                textColor = labelColor.toArgbInt()
                setDrawGridLines(false)
            }
            if (chart.data !== lineData) {
                chart.data = lineData
                if (animate) chart.animateY(400)
            }
            chart.invalidate()
        },
    )
}
