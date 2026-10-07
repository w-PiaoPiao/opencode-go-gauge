package io.github.yphyphyph.gogauge.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.yphyphyph.gogauge.data.model.DailyStat
import io.github.yphyphyph.gogauge.ui.theme.Gg
import io.github.yphyphyph.gogauge.ui.theme.NumFontFamily
import io.github.yphyphyph.gogauge.util.Fmt
import java.time.LocalDate
import kotlin.math.ceil
import kotlin.math.max

/**
 * 日历热力图 (v2.2.0b) — GitHub contribution 风格: 周列 × 7 行,
 * 颜色梯度取暖橙主题 token, 指标可切 (费用/请求/Token)。
 * 点击某格选中并在下方显示当日明细; 窄屏横向滚动。
 */
@Composable
fun CalendarHeatmap(
    days: List<DailyStat>,
    metric: String, // "cost" | "requests" | "tokens"
    currency: String,
    usdCny: Double,
    modifier: Modifier = Modifier,
) {
    val cell = 11.dp
    val gap = 2.dp
    val step = cell + gap
    var selected by remember(days) { mutableStateOf<String?>(null) }

    if (days.isEmpty() || days.all { it.requestCount == 0 }) {
        // 无数据在调用方兜底, 这里防御空集
        return
    }

    val values = days.map { metricValue(it, metric) }
    val maxValue = max(values.max(), 1.0)
    val firstDate = LocalDate.parse(days.first().date)
    // 首格按星期几对齐行位 (周一为首行): 前面留空格
    val leadingBlanks = (firstDate.dayOfWeek.value + 6) % 7
    val columns = ceil((leadingBlanks + days.size) / 7.0).toInt()

    val tile = MaterialTheme.colorScheme.surfaceVariant
    val outline = MaterialTheme.colorScheme.outline
    val trackText = MaterialTheme.colorScheme.onSurfaceVariant

    Column(modifier) {
        Row(
            Modifier
                .horizontalScroll(rememberScrollState())
                .padding(horizontal = 14.dp),
        ) {
            // 7 行行标 (一/三/五)
            Column(Modifier.padding(end = 4.dp)) {
                listOf(0, 1, 2, 3, 4, 5, 6).forEach { row ->
                    androidx.compose.foundation.layout.Box(Modifier.size(cell + gap)) {
                        if (row % 2 == 0) {
                            Text(
                                listOf("一", "三", "五", "日")[row / 2],
                                fontSize = 8.sp,
                                color = trackText,
                                modifier = Modifier.padding(top = 0.dp),
                            )
                        }
                    }
                }
            }
            Canvas(
                Modifier
                    .width(step * columns)
                    .height(step * 7 + 24.dp)
                    .pointerInput(days, metric) {
                        detectTapGestures { offset ->
                            val col = (offset.x / (cell.toPx() + gap.toPx())).toInt()
                            val row = (offset.y / (cell.toPx() + gap.toPx())).toInt()
                            val idx = col * 7 + row - leadingBlanks
                            selected = days.getOrNull(idx)?.date
                        }
                    },
            ) {
                val step = (cell + gap).toPx()
                val r = cell.toPx() / 4f
                days.forEachIndexed { idx, _ ->
                    val pos = leadingBlanks + idx
                    val col = pos / 7
                    val row = pos % 7
                    val v = values[idx]
                    val color = heatColor(v / maxValue, tile)
                    val x = col * step
                    val y = row * step
                    drawRoundRect(
                        color = color,
                        topLeft = Offset(x, y),
                        size = Size(cell.toPx(), cell.toPx()),
                        cornerRadius = CornerRadius(r, r),
                    )
                    if (days[idx].date == selected) {
                        drawRoundRect(
                            color = outline,
                            topLeft = Offset(x, y),
                            size = Size(cell.toPx(), cell.toPx()),
                            cornerRadius = CornerRadius(r, r),
                            style = Stroke(width = 1.5.dp.toPx()),
                        )
                    }
                }
            }
        }

        // 选中日明细 / 图例
        Spacer(Modifier.height(8.dp))
        val sel = days.firstOrNull { it.date == selected }
        Row(
            Modifier.padding(horizontal = 14.dp),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        ) {
            if (sel != null) {
                Text(
                    "${sel.date}  ·  ${Fmt.money(sel.totalCostUsd, currency, usdCny)}  ·  " +
                        "${Fmt.int(sel.requestCount)} · ${Fmt.tokens(sel.totalInputTokens + sel.totalOutputTokens + sel.totalReasoningTokens)}",
                    fontSize = 12.sp,
                    fontFamily = NumFontFamily,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                // 强度图例 (少 → 多)
                Text("少", fontSize = 10.sp, color = trackText)
                repeat(5) { i ->
                    Spacer(Modifier.width(3.dp))
                    androidx.compose.foundation.layout.Box(
                        Modifier
                            .size(9.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(heatColor((i + 1) / 5.0, tile)),
                    )
                }
                Spacer(Modifier.width(3.dp))
                Text("多", fontSize = 10.sp, color = trackText)
            }
        }
    }
}

private fun metricValue(d: DailyStat, metric: String): Double = when (metric) {
    "cost" -> d.totalCostUsd
    "requests" -> d.requestCount.toDouble()
    else -> (d.totalInputTokens + d.totalOutputTokens + d.totalReasoningTokens).toDouble()
}

/** 值强度 (0-1) → 颜色: 空档 tile, 其余沿暖橙梯度加深。 */
private fun heatColor(intensity: Double, empty: androidx.compose.ui.graphics.Color): androidx.compose.ui.graphics.Color {
    if (intensity <= 0.0) return empty
    // 插值: 浅橙 (#F0D9C4) → 主题橙 (#C15F3C) → 砖红
    val stops = listOf(
        Gg.PrimarySoft,
        androidx.compose.ui.graphics.Color(0xFFDD7E4F),
        Gg.Primary,
        androidx.compose.ui.graphics.Color(0xFF9C3F22),
    )
    val t = intensity.coerceIn(0.0, 1.0) * (stops.size - 1)
    val i = t.toInt().coerceAtMost(stops.size - 2)
    val f = (t - i).toFloat()
    return androidx.compose.ui.graphics.lerp(stops[i], stops[i + 1], f)
}
