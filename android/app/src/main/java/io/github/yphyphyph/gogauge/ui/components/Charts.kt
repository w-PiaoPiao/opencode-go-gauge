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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import io.github.yphyphyph.gogauge.data.model.ModelTrendData
import io.github.yphyphyph.gogauge.data.model.ModelTrendSeries
import io.github.yphyphyph.gogauge.ui.Strings
import io.github.yphyphyph.gogauge.ui.theme.GgChart
import io.github.yphyphyph.gogauge.util.Fmt
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import java.util.Locale
import kotlin.math.roundToInt

private fun Color.toArgbInt(): Int = android.graphics.Color.argb(
    (this.alpha * 255).toInt(), (this.red * 255).toInt(), (this.green * 255).toInt(), (this.blue * 255).toInt()
)

/**
 * 环形图/堆叠趋势共享调色板 (同模型两图同色): 与桌面 MODEL_PALETTE 同序.
 * 第 6 槽珊瑚为扩展位 (环形图没有的模型续后使用).
 */
private val MODEL_COLORS = listOf(
    GgChart.Input, GgChart.Output, GgChart.Reasoning, GgChart.Cache, GgChart.Cost, GgChart.Extra,
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
    totalMode: Boolean = false,
    modifier: Modifier = Modifier,
) {
    // Rebuild the dataset only when the data or labels change; recomposition (theme,
    // syncing, progress updates) then reuses the cached BarData instead of rebuilding.
    // totalMode (v2.2.1a): 输出不再单列, 只画「总 TOKEN 消耗」一根柱 (未缓存输入 +
    // 缓存读 + 缓存写 + 输出 + 推理, 与首页「总 TOKEN 消耗」卡完全同口径) —
    // desktop c7f841c 含缓存口径 parity.
    val barData = remember(data, s, totalMode) {
        if (totalMode) {
            val totalEntries = data.mapIndexed { i, h -> BarEntry(i.toFloat(), h.totalTokens.toFloat()) }
            val dsTotal = BarDataSet(totalEntries, s.totalTokens).apply {
                color = GgChart.Extra.toArgbInt()  // 桌面 total 柱取 --primary (此处同色: 珊瑚)
                setDrawValues(false)
            }
            BarData(dsTotal).apply {
                barWidth = 0.5f
                isHighlightEnabled = false
            }
        } else {
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
    val palette = remember { MODEL_COLORS.map { it.toArgbInt() } }
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
                    // 中心孔透出卡片底色 (暗色块上必须是暗底, 默认白孔在暗块上刺眼)
                    setHoleColor(android.graphics.Color.TRANSPARENT)
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
            mode = LineDataSet.Mode.CUBIC_BEZIER
            setDrawCircles(false)
            setDrawValues(false)
            axisDependency = com.github.mikephil.charting.components.YAxis.AxisDependency.LEFT
        }
        val reqDs = LineDataSet(trend.mapIndexed { i, d -> mk(i, d.requestCount.toDouble()) }, s.totalRequests).apply {
            color = GgChart.Output.toArgbInt()
            lineWidth = 2f
            mode = LineDataSet.Mode.CUBIC_BEZIER
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
            mode = LineDataSet.Mode.CUBIC_BEZIER
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

/** 单模型序列 30 天总量 (按维度) — 堆叠趋势的排序键. */
private fun ModelTrendSeries.totalFor(dim: String): Double = when (dim) {
    "output" -> output.sumOf { it.toDouble() }
    "cost" -> cost.sum()
    else -> input.sumOf { it.toDouble() }
}

/**
 * 模型用量趋势 (按天归一的堆叠面积) — desktop chartModelTrend aa389b7 / df22e97 parity.
 *
 * MPAndroidChart 的折线不支持堆叠, 这里改用 Canvas 手绘: 每天合计归一到 100%,
 * 看的是构成变化而非绝对量 (绝对量由同页「用量趋势」承担)。层间连接用直线而不是
 * Catmull-Rom 平滑 —— 稀疏尖峰数据下平滑会过冲 (画出负值/高于真实峰值的假峰);
 * 桌面用 monotone 保形插值避免过冲, 直线同样不会过冲 (视觉上更硬朗一点)。
 *
 * 交互: 点击某天显示提示框 (占比 + 原始值), 只列当天该维度有用量的模型
 * (desktop df22e97 tooltip filter); 当天全为 0 时提示框整体不绘制。
 * 图例保持整段窗口的模型集, 不随悬停日变化 (用于识别/切换系列)。
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ModelTrendChart(
    data: ModelTrendData,
    models: List<ModelStat>,
    dim: String,
    excludedModels: Set<String>,
    labelColor: Color,
    gridLineColor: Color,
    currency: String,
    usdCny: Double,
    animate: Boolean = false,
    modifier: Modifier = Modifier,
) {
    // 配色顺序: 环形图全量 top6 (与 ModelPieChart 同排序) → 位置即调色板索引
    val order = remember(models, dim) {
        models.sortedByDescending { getVal(it, dim) }
            .take(MODEL_COLORS.size)
            .map { it.model }
            .withIndex()
            .associate { (i, m) -> m to i }
    }
    // 本图模型集: 30 天有量的模型, 按 (环形图顺序, 自身总量) 排序取前 6
    val ranked = remember(data, dim, excludedModels, order) {
        data.series
            .filter { it.model !in excludedModels }
            .map { it to it.totalFor(dim) }
            .filter { it.second > 0.0 }
            .sortedWith(
                compareBy<Pair<ModelTrendSeries, Double>> { order[it.first.model] ?: Int.MAX_VALUE }
                    .thenByDescending { it.second }
            )
            .take(MODEL_COLORS.size)
    }
    // 前置空档不画 (desktop parity): 从可见模型第一天有量的开始; 中间/末尾的 0 保留
    val from = remember(data, excludedModels) {
        modelTrendLeadIndex(data.days, data.series, excludedModels).coerceAtLeast(0)
    }
    val days = remember(data, from) { if (from > 0) data.days.drop(from) else data.days }
    val labels = remember(days) { days.map { shortDate(it) } }
    val names = remember(ranked) { ranked.map { it.first.model } }
    // 每天原始值 (已裁剪) — input=含缓存总输入 / output / cost, 与环形图维度口径一致
    val rawValues = remember(ranked, dim, from, days) {
        ranked.map { (series, _) ->
            val full = when (dim) {
                "output" -> series.output.map { it.toDouble() }
                "cost" -> series.cost
                else -> series.input.map { it.toDouble() }
            }
            val sliced = full.drop(from)
            List(days.size) { i -> sliced.getOrElse(i) { 0.0 } }
        }
    }
    // 按天归一: 每天合计=100%; 基数只取参与绘制的模型 (与环形图 top6 内部占比同口径)
    val pctValues = remember(rawValues, days) {
        val totals = List(days.size) { i -> rawValues.sumOf { it.getOrElse(i) { 0.0 } } }
        rawValues.map { values ->
            List(days.size) { i -> if (totals[i] > 0.0) (values[i] / totals[i] * 100.0).toFloat() else 0f }
        }
    }
    val colors = remember(ranked, order) {
        ranked.map { (series, _) ->
            MODEL_COLORS[(order[series.model] ?: (MODEL_COLORS.size - 1)) % MODEL_COLORS.size]
        }
    }
    val fmtRaw: (Double) -> String = remember(dim, currency, usdCny) {
        if (dim == "cost") {
            { v -> Fmt.money(v, currency, usdCny) }
        } else {
            { v -> Fmt.tokens(v.toLong()) }
        }
    }
    var selected by remember(days) { mutableStateOf(-1) }

    val textMeasurer = rememberTextMeasurer()
    val axisStyle = TextStyle(fontSize = 9.sp, color = labelColor)
    val tipBg = MaterialTheme.colorScheme.surface
    val tipBorder = MaterialTheme.colorScheme.outline
    val tipTextColor = MaterialTheme.colorScheme.onSurface

    Column(modifier) {
        Canvas(
            Modifier
                .fillMaxWidth()
                .height(210.dp)
                .pointerInput(labels) {
                    detectTapGestures { offset ->
                        val count = labels.size
                        if (count == 0) return@detectTapGestures
                        val left = 40.dp.toPx()
                        val top = 8.dp.toPx()
                        val plotW = size.width.toFloat() - left - 8.dp.toPx()
                        val plotH = size.height.toFloat() - top - 20.dp.toPx()
                        if (plotW <= 0f || plotH <= 0f) return@detectTapGestures
                        if (offset.x < left || offset.x > left + plotW || offset.y < top || offset.y > top + plotH) {
                            selected = -1
                            return@detectTapGestures
                        }
                        val i = if (count == 1) 0 else ((offset.x - left) / plotW * (count - 1)).roundToInt()
                        val idx = i.coerceIn(0, count - 1)
                        selected = if (selected == idx) -1 else idx
                    }
                },
        ) {
            val n = days.size
            if (n == 0) return@Canvas
            val left = 40.dp.toPx()
            val right = 8.dp.toPx()
            val top = 8.dp.toPx()
            val bottom = 20.dp.toPx()
            val plotW = size.width - left - right
            val plotH = size.height - top - bottom
            if (plotW <= 0f || plotH <= 0f) return@Canvas
            fun xAt(i: Int): Float = if (n == 1) left + plotW / 2f else left + plotW * i / (n - 1)
            fun yAt(pct: Float): Float = top + plotH * (1f - (pct / 100f).coerceIn(0f, 1f))

            // y 轴固定 0~100% (堆叠面积按天归一)
            listOf(0, 25, 50, 75, 100).forEach { p ->
                val y = yAt(p.toFloat())
                drawLine(gridLineColor, Offset(left, y), Offset(left + plotW, y), strokeWidth = 1f)
                val layout = textMeasurer.measure(AnnotatedString("$p%"), axisStyle)
                drawText(
                    layout,
                    topLeft = Offset(left - layout.size.width - 4.dp.toPx(), y - layout.size.height / 2f),
                )
            }
            // x 轴日期 (最多 6 个, 窄屏防粘连)
            val tickCount = minOf(6, n)
            val tickIdx = (0 until tickCount).map { k ->
                if (tickCount == 1) 0 else ((n - 1) * k / (tickCount - 1.0)).roundToInt()
            }.distinct()
            tickIdx.forEach { i ->
                val layout = textMeasurer.measure(AnnotatedString(labels[i]), axisStyle)
                val x = (xAt(i) - layout.size.width / 2f).coerceIn(0f, size.width - layout.size.width)
                drawText(layout, topLeft = Offset(x, top + plotH + 4.dp.toPx()))
            }
            // 堆叠面积: 从下往上画, 每层是「本层顶边 ↔ 上一层顶边」之间的区域
            val cumulative = FloatArray(n)
            pctValues.forEachIndexed { k, pcts ->
                val prev = cumulative.copyOf()
                for (i in 0 until n) cumulative[i] += pcts[i]
                val area = Path().apply {
                    moveTo(xAt(0), yAt(cumulative[0]))
                    for (i in 1 until n) lineTo(xAt(i), yAt(cumulative[i]))
                    for (i in n - 1 downTo 0) lineTo(xAt(i), yAt(prev[i]))
                    close()
                }
                drawPath(area, color = colors[k].copy(alpha = 0.85f))
                // 层顶细线 (desktop borderWidth 1), 让相邻同色系层可分辨
                val edge = Path().apply {
                    moveTo(xAt(0), yAt(cumulative[0]))
                    for (i in 1 until n) lineTo(xAt(i), yAt(cumulative[i]))
                }
                drawPath(edge, color = colors[k], style = Stroke(width = 1.dp.toPx()))
            }
            // 选中日: 竖线 + 提示框 (只列当天该维度有用量的模型; 当天全 0 则不画)
            if (selected in 0 until n) {
                val x = xAt(selected)
                drawLine(
                    labelColor.copy(alpha = 0.35f),
                    Offset(x, top),
                    Offset(x, top + plotH),
                    strokeWidth = 1.dp.toPx(),
                )
                val lines = mutableListOf(labels[selected])
                names.forEachIndexed { k, name ->
                    val raw = rawValues[k].getOrElse(selected) { 0.0 }
                    if (raw > 0.0) {
                        val pct = pctValues[k].getOrElse(selected) { 0f }
                        lines += "$name  ${String.format(Locale.US, "%.1f", pct)}% · ${fmtRaw(raw)}"
                    }
                }
                if (lines.size > 1) {
                    val tipStyle = TextStyle(fontSize = 9.sp, color = tipTextColor)
                    val layouts = lines.map { textMeasurer.measure(AnnotatedString(it), tipStyle) }
                    val lineH = layouts.maxOf { it.size.height } + 2.dp.toPx()
                    val boxW = layouts.maxOf { it.size.width } + 12.dp.toPx()
                    val boxH = lineH * lines.size + 8.dp.toPx()
                    val bx = (x + 8.dp.toPx())
                        .let { if (it + boxW > size.width) x - boxW - 8.dp.toPx() else it }
                        .coerceIn(2.dp.toPx(), maxOf(2.dp.toPx(), size.width - boxW - 2.dp.toPx()))
                    val by = (top + 2.dp.toPx())
                        .coerceIn(2.dp.toPx(), maxOf(2.dp.toPx(), size.height - boxH - 2.dp.toPx()))
                    drawRoundRect(
                        color = tipBg.copy(alpha = 0.97f),
                        topLeft = Offset(bx, by),
                        size = Size(boxW, boxH),
                        cornerRadius = CornerRadius(6.dp.toPx()),
                    )
                    drawRoundRect(
                        color = tipBorder.copy(alpha = 0.5f),
                        topLeft = Offset(bx, by),
                        size = Size(boxW, boxH),
                        cornerRadius = CornerRadius(6.dp.toPx()),
                        style = Stroke(width = 1.dp.toPx()),
                    )
                    layouts.forEachIndexed { li, layout ->
                        drawText(layout, topLeft = Offset(bx + 6.dp.toPx(), by + 4.dp.toPx() + lineH * li))
                    }
                }
            }
        }
        // 图例: 整段窗口的模型集 (与桌面一致; 模型多时自动换行)
        if (names.isNotEmpty()) {
            FlowRow(
                Modifier.fillMaxWidth().padding(top = 2.dp, start = 2.dp, end = 2.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                names.forEachIndexed { k, name ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(7.dp).background(colors[k], CircleShape))
                        Spacer(Modifier.width(4.dp))
                        Text(name, fontSize = 10.sp, color = labelColor, maxLines = 1)
                    }
                }
            }
        }
    }
}
