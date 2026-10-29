package io.github.yphyphyph.gogauge.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
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
import io.github.yphyphyph.gogauge.ui.theme.LocalHeatRamp
import io.github.yphyphyph.gogauge.ui.theme.NumFontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import io.github.yphyphyph.gogauge.ui.Strings
import io.github.yphyphyph.gogauge.util.Fmt
import java.time.LocalDate
import kotlin.math.ceil

/**
 * 日历热力图 (v2.2.0b) — GitHub contribution 风格: 周列 × 7 行,
 * 颜色梯度取暖橙主题 token, 指标可切 (费用/请求/Token)。
 * 点击某格选中并在下方显示当日明细; 窄屏横向滚动。
 *
 * 分档口径与桌面 heatmapBreaks 一致: 有量日的 p50/p75/p90 三个锚点切 4 档,
 * 而不是按峰值线性归一 —— 后者遇到一个异常峰值就把其余日子全压进最低档。
 */
@Composable
fun CalendarHeatmap(
    days: List<DailyStat>,
    metric: String, // "cost" | "requests" | "tokens"
    currency: String,
    usdCny: Double,
    s: Strings,
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

    val values = remember(days, metric) { days.map { dailyMetricValue(it, metric) } }
    val levels = remember(days, metric) {
        heatmapLevels(days.map { dailyMetricValue(it, metric) }, days.map { it.requestCount > 0 })
    }
    // 峰值日单独描边: 颜色已封顶在档 4, 不再靠"再加一档颜色"来表达记录日
    val peakIdx = remember(days, metric) {
        values.indices.filter { values[it] > 0 }.maxByOrNull { values[it] } ?: -1
    }
    val firstDate = LocalDate.parse(days.first().date)
    // 首格按星期几对齐行位 (周一为首行): 前面留空格
    val leadingBlanks = (firstDate.dayOfWeek.value + 6) % 7
    val columns = ceil((leadingBlanks + days.size) / 7.0).toInt()

    val tile = MaterialTheme.colorScheme.surfaceVariant
    val outline = MaterialTheme.colorScheme.outline
    val trackText = MaterialTheme.colorScheme.onSurfaceVariant
    val heatStops = LocalHeatRamp.current
    val ringColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
    // 档 0 = 空档 tile, 1..4 沿注入的五档色阶
    fun levelColor(level: Int) =
        if (level <= 0) tile else heatStops[(level - 1).coerceAtMost(heatStops.lastIndex)]

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
                    val x = col * step
                    val y = row * step
                    drawRoundRect(
                        color = levelColor(levels[idx]),
                        topLeft = Offset(x, y),
                        size = Size(cell.toPx(), cell.toPx()),
                        cornerRadius = CornerRadius(r, r),
                    )
                    if (idx == peakIdx) {
                        // 描边压在格外的 1dp 上 (格间距 2dp), 不与邻格填充重叠
                        drawRoundRect(
                            color = ringColor,
                            topLeft = Offset(x - 1.dp.toPx(), y - 1.dp.toPx()),
                            size = Size(cell.toPx() + 2.dp.toPx(), cell.toPx() + 2.dp.toPx()),
                            cornerRadius = CornerRadius(r + 1.dp.toPx(), r + 1.dp.toPx()),
                            style = Stroke(width = 1.dp.toPx()),
                        )
                    }
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
                // 强度图例 (少 → 多): 从空档起 5 格, 与桌面 .hm-legend 一致
                Text("少", fontSize = 10.sp, color = trackText)
                repeat(5) { i ->
                    Spacer(Modifier.width(3.dp))
                    androidx.compose.foundation.layout.Box(
                        Modifier
                            .size(9.dp)
                            .clip(RoundedCornerShape(2.dp))
                            .background(levelColor(i)),
                    )
                }
                Spacer(Modifier.width(3.dp))
                Text("多", fontSize = 10.sp, color = trackText)
            }
        }
        // 摘要 (峰值/当前连续/最长连续) — desktop heatmapSummaryHtml parity
        Spacer(Modifier.height(10.dp))
        HeatmapSummaryRow(days = days, metric = metric, s = s, currency = currency, usdCny = usdCny)
    }
}

/** 热力图档位不在这里算颜色: 5 档色阶由 theme 的 LocalHeatRamp 注入 (亮暗各一套),
 *  档 0 取 surfaceVariant. 分档见 StatsMath.heatmapLevels. */

/** 热力图摘要行 (desktop heatmapSummaryHtml parity): 峰值随所选指标, 连续天数只看「当天有请求」. */
@Composable
private fun HeatmapSummaryRow(
    days: List<DailyStat>,
    metric: String,
    s: Strings,
    currency: String,
    usdCny: Double,
) {
    val summary = remember(days, metric) { heatmapSummary(days, metric) }
    val peakText = when (metric) {
        "cost" -> Fmt.money(summary.peakValue, currency, usdCny)
        "requests" -> Fmt.int(summary.peakValue.toLong())
        else -> Fmt.tokens(summary.peakValue.toLong())
    }
    fun streakText(n: Int): String = (if (n == 1) s.hmDayOne else s.hmDays).format(n)
    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp)) {
        HeatmapStat("${s.hmPeak} · ${summary.peakDate.takeLast(5)}", peakText, Modifier.weight(1f))
        HeatmapStat(s.hmCurStreak, streakText(summary.currentStreak), Modifier.weight(1f))
        HeatmapStat(s.hmMaxStreak, streakText(summary.longestStreak), Modifier.weight(1f))
    }
}

@Composable
private fun HeatmapStat(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(
            label,
            fontSize = 10.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            value,
            fontSize = 15.sp,
            fontWeight = FontWeight.SemiBold,
            fontFamily = NumFontFamily,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
