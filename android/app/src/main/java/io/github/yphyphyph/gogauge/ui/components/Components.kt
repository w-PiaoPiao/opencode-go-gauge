package io.github.yphyphyph.gogauge.ui.components

import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.pulltorefresh.PullToRefreshState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.yphyphyph.gogauge.ui.theme.CaptionLabel
import io.github.yphyphyph.gogauge.ui.theme.Gg
import io.github.yphyphyph.gogauge.ui.theme.GgDark
import io.github.yphyphyph.gogauge.ui.theme.NUM_FEATURE_SETTINGS
import io.github.yphyphyph.gogauge.ui.theme.NumFontFamily

/**
 * Shared mobile-first components — Claude 官方令牌体系:
 * 画布上的色调卡 + 发丝线, 内嵌砖块, 语义色数值, 暗色数据块。
 * 圆角: 卡 12 / 砖块 8 / pill 全圆。
 */

val GgCardShape = RoundedCornerShape(12.dp)

/** Card container — 色调卡 #F5F0E8 + 发丝线 (官方 model-comparison-card 模式) */
@Composable
fun GgCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = GgCardShape
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(shape)
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, MaterialTheme.colorScheme.outline, shape)
            .padding(vertical = 6.dp),
    ) {
        content()
    }
}

/** Card header */
@Composable
fun CardHeader(
    title: String,
    trailing: (@Composable () -> Unit)? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 16.dp, end = 12.dp, top = 12.dp, bottom = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, style = MaterialTheme.typography.titleSmall)
        if (trailing != null) trailing()
    }
}

/** Hint text */
@Composable
fun Hint(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/** KPI 卡 — 暖白卡 + 发丝线 (与 GgCard 同语言) + caption 标签 + 语义色数值 */
@Composable
fun KpiCard(
    label: String,
    value: String,
    sub: String,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    val shape = RoundedCornerShape(12.dp)
    Column(
        modifier = modifier
            .clip(shape)
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, MaterialTheme.colorScheme.outline, shape)
            .padding(start = 14.dp, end = 12.dp, top = 12.dp, bottom = 10.dp),
    ) {
        Text(
            label,
            style = CaptionLabel,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(3.dp))
        Text(
            value,
            fontSize = 24.sp,
            lineHeight = 28.sp,
            fontWeight = FontWeight.Bold,
            color = accent,
            fontFamily = NumFontFamily,
            style = LocalTextStyle.current.copy(fontFeatureSettings = NUM_FEATURE_SETTINGS),
        )
        Spacer(Modifier.height(2.dp))
        Text(
            sub,
            fontSize = 12.sp,
            lineHeight = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontFamily = NumFontFamily,
        )
    }
}

/** 编辑式数据网格 — 内嵌砖块 + 语义色小点 + 墨色数值 (首页概览/统计构成共用); 行内等高 */
data class EditorialCell(val label: String, val value: String, val sub: String, val accent: Color)

@Composable
fun EditorialGrid(cells: List<EditorialCell>, modifier: Modifier = Modifier) {
    Column(modifier) {
        cells.chunked(2).forEach { row ->
            Row(Modifier.fillMaxWidth().height(IntrinsicSize.Max)) {
                row.forEachIndexed { i, cell ->
                    Column(
                        Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .padding(start = if (i == 1) 10.dp else 0.dp)
                            .padding(top = 10.dp, bottom = 2.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant)
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                Modifier
                                    .size(5.dp)
                                    .background(cell.accent, CircleShape),
                            )
                            Spacer(Modifier.width(6.dp))
                            Text(
                                cell.label,
                                style = CaptionLabel,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Spacer(Modifier.height(4.dp))
                        Text(
                            cell.value,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = NumFontFamily,
                            style = LocalTextStyle.current.copy(fontFeatureSettings = NUM_FEATURE_SETTINGS),
                        )
                        if (cell.sub.isNotEmpty()) {
                            Text(
                                cell.sub,
                                fontSize = 12.sp,
                                lineHeight = 16.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontFamily = NumFontFamily,
                            )
                        }
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/** Quota progress card — 细条 + 渐变填充 (桌面端渐变条的官方暖色版) */
@Composable
fun QuotaCard(
    label: String,
    usedPercent: Double,
    remainingText: String,
    resetText: String,
    accent: Color,
    accentEnd: Color? = null,
    modifier: Modifier = Modifier,
) {
    val shape = GgCardShape
    val progress by animateFloatAsState(
        targetValue = (usedPercent.coerceIn(0.0, 100.0) / 100.0).toFloat(),
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioNoBouncy,
            stiffness = Spring.StiffnessLow,
        ),
        label = "quotaProgress",
    )
    val fill = if (accentEnd != null && accentEnd != accent) {
        Brush.horizontalGradient(listOf(accent, accentEnd))
    } else {
        Brush.horizontalGradient(listOf(accent, accent))
    }
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(shape)
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, MaterialTheme.colorScheme.outline, shape)
            .padding(16.dp),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(
                remainingText,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = NumFontFamily,
                style = LocalTextStyle.current.copy(fontFeatureSettings = NUM_FEATURE_SETTINGS),
            )
        }
        Spacer(Modifier.height(10.dp))
        Box(
            Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.surfaceContainerHighest),
        ) {
            Box(
                Modifier
                    .fillMaxWidth(progress)
                    .height(8.dp)
                    .clip(CircleShape)
                    .background(fill),
            )
        }
        Spacer(Modifier.height(8.dp))
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                "${usedPercent.toInt()}%",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                resetText,
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontFamily = NumFontFamily,
            )
        }
    }
}

/** Segmented control — 官方 active-tab 模式: 容器 cream-strong, 选中 = 画布色 + 墨字 */
@Composable
fun PillRow(
    options: List<Pair<String, String>>, // (value, label)
    selected: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .horizontalScroll(rememberScrollState())
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHighest)
            .padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        options.forEach { (value, label) ->
            val active = value == selected
            val interactionSource = remember { MutableInteractionSource() }
            val pressed by interactionSource.collectIsPressedAsState()
            val scale by animateFloatAsState(
                targetValue = if (pressed) 0.97f else 1f,
                animationSpec = spring(stiffness = Spring.StiffnessHigh),
                label = "pillPress",
            )
            Box(
                Modifier
                    .scale(scale)
                    .clip(RoundedCornerShape(8.dp))
                    .background(
                        when {
                            active -> MaterialTheme.colorScheme.surface
                            else -> Color.Transparent
                        },
                    )
                    .clickable(interactionSource = interactionSource, indication = null) { onSelect(value) }
                    // 触控目标 ≥44dp: 单手/小屏下容易点空
                    .defaultMinSize(minHeight = 44.dp)
                    .padding(horizontal = 13.dp, vertical = 9.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    label,
                    fontSize = 13.sp,
                    fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (active) MaterialTheme.colorScheme.onSurface
                    else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** Accent colors per KPI class — 官方语义色映射 */
object Accent {
    val violet: Color @Composable get() = MaterialTheme.colorScheme.primary
    val blue: Color @Composable get() = io.github.yphyphyph.gogauge.ui.theme.Gg.Blue
    val green: Color @Composable get() = io.github.yphyphyph.gogauge.ui.theme.Gg.Green
    val amber: Color @Composable get() = io.github.yphyphyph.gogauge.ui.theme.Gg.Amber
    val cyan: Color @Composable get() = io.github.yphyphyph.gogauge.ui.theme.Gg.Cyan
    val slate: Color @Composable get() = io.github.yphyphyph.gogauge.ui.theme.Gg.Slate
}

/** Dark-aware accent helper */
@Composable
fun isDark(): Boolean = MaterialTheme.colorScheme.background == GgDark.Bg

/* ================= 下拉刷新指示器 ================= */
/*
 * Custom pull-to-refresh indicator.
 *
 * material3 1.3.2's built-in PullToRefreshDefaults.Indicator does not render on this
 * Compose 1.8.2 stack (verified: the indicator slot works, the default component draws
 * nothing). This is a drop-in Material-style replacement:
 * - while pulling: a progress arc whose sweep follows the pull distance
 * - while refreshing: an indeterminate spinner
 * - the whole circle rides down with the finger (distanceFraction)
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GgPullIndicator(
    state: PullToRefreshState,
    isRefreshing: Boolean,
    modifier: Modifier = Modifier,
) {
    val color = MaterialTheme.colorScheme.primary
    val trackColor = MaterialTheme.colorScheme.surfaceContainerHighest
    val density = LocalDensity.current
    val offsetPx = with(density) { (state.distanceFraction * 96).dp.roundToPx() }
    // Only render while pulling or refreshing — otherwise the circle sits on top of the
    // page content permanently (distanceFraction == 0 when idle).
    if (isRefreshing || state.distanceFraction > 0f) {
        Box(
            modifier
                .offset { IntOffset(0, offsetPx) }
                .size(44.dp)
                .shadow(3.dp, CircleShape)
                .background(MaterialTheme.colorScheme.surface, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            if (isRefreshing) {
                CircularProgressIndicator(
                    modifier = Modifier.size(28.dp),
                    color = color,
                    strokeWidth = 3.dp,
                )
            } else {
                CircularProgressIndicator(
                    progress = { state.distanceFraction.coerceIn(0f, 1f) },
                    modifier = Modifier.size(28.dp),
                    color = color,
                    strokeWidth = 3.dp,
                    trackColor = trackColor,
                )
            }
        }
    }
}
