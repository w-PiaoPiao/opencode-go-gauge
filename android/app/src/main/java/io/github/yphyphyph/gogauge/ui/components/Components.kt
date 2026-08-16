package io.github.yphyphyph.gogauge.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.yphyphyph.gogauge.ui.theme.Gg
import io.github.yphyphyph.gogauge.ui.theme.GgDark

/**
 * Shared mobile-first components. Layout adapted from desktop style.css:
 * cards full-width, larger type, ≥48dp touch targets.
 */

/** Card container — desktop .card */
@Composable
fun GgCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = RoundedCornerShape(14.dp)
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(shape)
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, MaterialTheme.colorScheme.outline, shape)
            .padding(vertical = 4.dp),
    ) {
        content()
    }
}

/** Card header — desktop .card-h */
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

/** Hint text — desktop .hint */
@Composable
fun Hint(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

/** KPI card — desktop .kpi (accent bar + label + big number + sub) */
@Composable
fun KpiCard(
    label: String,
    value: String,
    sub: String,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(14.dp))
            .padding(start = 14.dp, end = 12.dp, top = 12.dp, bottom = 10.dp),
    ) {
        // accent bar via Box behind content
        Box(
            Modifier
                .width(3.dp)
                .height(0.dp),
        )
        Text(label, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(2.dp))
        Text(
            value,
            fontSize = 22.sp,
            lineHeight = 26.sp,
            fontWeight = FontWeight.Bold,
            color = accent,
            fontFamily = io.github.yphyphyph.gogauge.ui.theme.NumFontFamily,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            sub,
            fontSize = 11.sp,
            lineHeight = 15.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontFamily = io.github.yphyphyph.gogauge.ui.theme.NumFontFamily,
        )
    }
}

/** Quota progress card — desktop .ub (full-width, thicker bar) */
@Composable
fun QuotaCard(
    label: String,
    usedPercent: Double,
    remainingText: String,
    resetText: String,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(14.dp))
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
                fontFamily = io.github.yphyphyph.gogauge.ui.theme.NumFontFamily,
            )
        }
        Spacer(Modifier.height(10.dp))
        // thicker progress bar (12dp vs desktop 8px) for readability
        Box(
            Modifier
                .fillMaxWidth()
                .height(12.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Box(
                Modifier
                    .fillMaxWidth(usedPercent.coerceIn(0.0, 100.0).toFloat() / 100f)
                    .height(12.dp)
                    .clip(CircleShape)
                    .background(accent),
            )
        }
        Spacer(Modifier.height(8.dp))
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                "${usedPercent.toInt()}%",
                fontSize = 11.5.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                resetText,
                fontSize = 11.5.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                fontFamily = io.github.yphyphyph.gogauge.ui.theme.NumFontFamily,
            )
        }
    }
}

/** Pill row — desktop .pill-row / .pill (min touch 44dp height) */
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
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        options.forEach { (value, label) ->
            val active = value == selected
            Box(
                Modifier
                    .clip(RoundedCornerShape(7.dp))
                    .background(if (active) MaterialTheme.colorScheme.surface else Color.Transparent)
                    .clickable { onSelect(value) }
                    .padding(horizontal = 13.dp, vertical = 9.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    label,
                    fontSize = 13.sp,
                    fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (active) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** Accent colors per KPI class — desktop .kpi.c-* */
object Accent {
    val violet: Color @Composable get() = MaterialTheme.colorScheme.primary
    val blue: Color @Composable get() = Gg.Blue
    val green: Color @Composable get() = Gg.Green
    val amber: Color @Composable get() = Gg.Amber
    val cyan: Color @Composable get() = Gg.Cyan
    val slate: Color @Composable get() = Gg.Slate
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
    val trackColor = MaterialTheme.colorScheme.surfaceVariant
    val density = LocalDensity.current
    val offsetPx = with(density) { (state.distanceFraction * 96).dp.roundToPx() }
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
