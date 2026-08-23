package io.github.yphyphyph.gogauge.ui.components

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
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
fun TodayBarChart(data: List<HourStat>, s: Strings, labelColor: Color, gridLineColor: Color, modifier: Modifier = Modifier) {
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
            if (chart.data !== barData) chart.data = barData
            chart.invalidate()
        },
    )
}

/** Model usage doughnut — desktop chartModel. */
@Composable
fun ModelPieChart(
    models: List<ModelStat>,
    dim: String,
    s: Strings,
    labelColor: Color,
    currency: String,
    usdCny: Double,
    modifier: Modifier = Modifier,
) {
    val palette = remember {
        listOf(
            GgChart.Input, GgChart.Output, GgChart.Reasoning, GgChart.Cache, GgChart.Cost, GgChart.Extra,
        ).map { it.toArgbInt() }
    }
    // Rebuild slices only when models/dim/formatting changes.
    val pieData = remember(models, dim, currency, usdCny) {
        val sorted = models.sortedByDescending { getVal(it, dim) }
        val top = sorted.take(6)
        val fmt: (Double) -> String = if (dim == "cost") { v -> Fmt.money(v, currency, usdCny) } else { v -> Fmt.tokens(v) }
        val entries = top.map { PieEntry(getVal(it, dim).toFloat(), it.model) }
        val ds = PieDataSet(entries, "").apply {
            colors = palette
            sliceSpace = 2f
            valueTextSize = 11f
            valueFormatter = object : ValueFormatter() {
                override fun getFormattedValue(value: Float) = fmt(value.toDouble())
            }
        }
        PieData(ds)
    }
    AndroidView(
        modifier = modifier.fillMaxWidth().height(230.dp),
        factory = { ctx ->
            PieChart(ctx).apply {
                description.isEnabled = false
                setDrawEntryLabels(false)
                holeRadius = 60f
                isRotationEnabled = true
            }
        },
        update = { chart ->
            // Always (re)apply the value label color so theme switches stay in sync;
            // the dataset itself is cached and only reassigned when it actually changes.
            pieData.dataSet.valueTextColor = labelColor.toArgbInt()
            if (chart.data !== pieData) chart.data = pieData
            chart.legend.isEnabled = true
            chart.legend.textSize = 11f
            chart.legend.textColor = labelColor.toArgbInt()
            chart.legend.orientation = com.github.mikephil.charting.components.Legend.LegendOrientation.HORIZONTAL
            chart.legend.verticalAlignment = com.github.mikephil.charting.components.Legend.LegendVerticalAlignment.BOTTOM
            chart.legend.horizontalAlignment = com.github.mikephil.charting.components.Legend.LegendHorizontalAlignment.CENTER
            chart.invalidate()
        },
    )
}

private fun getVal(m: ModelStat, dim: String): Double = when (dim) {
    "output" -> m.totalOutputTokens.toDouble()
    "cost" -> m.totalCostUsd
    else -> m.uncachedInputTokens.toDouble()
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
            if (chart.data !== lineData) chart.data = lineData
            chart.invalidate()
        },
    )
}
