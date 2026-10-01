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
 * 图例常驻全量 top 模型: 点击某项 = 全局排除/恢复该模型 (总卡/Token 构成/排行/趋势
 * 一起变); 被排除项扇区隐藏、图例项画删除线, 再点即加回. MPAndroidChart 的内置
 * 图例不支持删除线与点击回调, 故禁用内置图例、在 Compose 侧自绘 (Chart.js 原生体验).
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
    // 全量 top6 定序: 颜色与图例都按全量排序的索引分配 —— 排除某项不改变其余项颜色
    val top = remember(models, dim) { models.sortedByDescending { getVal(it, dim) }.take(6) }
    // Rebuild slices only when models/dim/formatting/exclusions change; 扇区只画参与
    // 统计的模型, 占比随排除自动归一.
    val pieData = remember(top, dim, currency, usdCny, excludedModels) {
        val fmt: (Double) -> String = if (dim == "cost") { v -> Fmt.money(v, currency, usdCny) } else { v -> Fmt.tokens(v) }
        val visible = top.withIndex().filter { it.value.model !in excludedModels }
        val entries = visible.map { PieEntry(getVal(it.value, dim).toFloat(), it.value.model) }
        val ds = PieDataSet(entries, "").apply {
            colors = visible.map { palette[it.index % palette.size] }
            sliceSpace = 2f
            valueTextSize = 11f
            valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float) = fmt(value.toDouble())
            }
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
                // Always (re)apply the value label color so theme switches stay in sync;
                // the dataset itself is cached and only reassigned when it actually changes.
                pieData.dataSet.valueTextColor = labelColor.toArgbInt()
                if (chart.data !== pieData) {
                    chart.data = pieData
                    if (animate) chart.animateY(400)
                }
                chart.legend.isEnabled = false  // 图例在 Compose 侧自绘 (删除线 + 点击)
                chart.invalidate()
            },
        )
        // 图例: 常驻全量 top, 点击切换排除; 被排除项删除线 + 降透明度
        FlowRow(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 6.dp),
            horizontalArrangement = Arrangement.Center,
        ) {
            top.forEachIndexed { i, m ->
                val excluded = m.model in excludedModels
                Row(
                    modifier = Modifier
                        .clickable { onToggleModel(m.model) }
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
                        textDecoration = if (excluded) TextDecoration.LineThrough else null,
                        color = if (excluded) labelColor.copy(alpha = 0.55f) else labelColor,
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

/** Usage trend 3-line dual-axis — desktop chartTrend (cost left, requests right, tokens hidden axis). */
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
        val tokDs = LineDataSet(trend.mapIndexed { i, d -> mk(i, (d.totalInputTokens + d.totalOutputTokens + d.totalReasoningTokens).toDouble()) }, s.totalTokens).apply {
            color = GgChart.Reasoning.toArgbInt()
            lineWidth = 2f
            setDrawCircles(false)
            setDrawValues(false)
            axisDependency = com.github.mikephil.charting.components.YAxis.AxisDependency.LEFT
        }
        LineData(costDs, reqDs, tokDs)
    }
    val dateLabels = remember(trend) { trend.map { it.date.substring(5) } }
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
                labelCount = 8
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
