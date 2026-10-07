package io.github.yphyphyph.gogauge.widget

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.GlanceTheme
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.LinearProgressIndicator
import androidx.glance.appwidget.action.actionStartActivity
import androidx.glance.appwidget.provideContent
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.Row
import androidx.glance.layout.Spacer
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.fillMaxWidth
import androidx.glance.layout.height
import androidx.glance.layout.padding
import androidx.glance.layout.width
import androidx.glance.text.FontWeight
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider
import io.github.yphyphyph.gogauge.MainActivity
import io.github.yphyphyph.gogauge.util.Fmt
import kotlin.math.roundToInt

/**
 * 配额小组件 (v2.2.0b, Glance/RemoteViews) — 三窗口迷你进度条 + 今日费用/请求数。
 * 数据源 = quota_snapshots + usage 当日聚合 ([WidgetData]); 点击打开主界面。
 */
class QuotaWidget : GlanceAppWidget() {

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val data = WidgetData.load(context)
        val openIntent = android.content.Intent(context, MainActivity::class.java)
            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
        provideContent {
            GlanceTheme {
                Content(data, openIntent)
            }
        }
    }

    @Composable
    private fun Content(data: WidgetData.Data, openIntent: android.content.Intent) {
        Column(
            modifier = GlanceModifier
                .fillMaxSize()
                .padding(12.dp)
                .clickable(actionStartActivity(openIntent)),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // header: 账号名 + 今日合计
            Row(modifier = GlanceModifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    data.accountName,
                    style = TextStyle(
                        fontSize = 13.sp, fontWeight = FontWeight.Bold,
                        color = GlanceTheme.colors.onSurface,
                    ),
                    maxLines = 1,
                    modifier = GlanceModifier.defaultWeight(),
                )
                Text(
                    "${Fmt.money(data.todayCostUsd, "USD", 1.0)} · ${Fmt.int(data.todayRequests)}",
                    style = TextStyle(
                        fontSize = 12.sp,
                        color = GlanceTheme.colors.onSurfaceVariant,
                    ),
                )
            }
            Spacer(GlanceModifier.height(8.dp))

            if (!data.hasSnapshot) {
                Text(
                    "—",
                    style = TextStyle(fontSize = 12.sp, color = GlanceTheme.colors.onSurfaceVariant),
                )
            } else {
                data.rows.forEach { row ->
                    QuotaBar(row.label, row.used)
                    Spacer(GlanceModifier.height(6.dp))
                }
            }
        }
    }

    /** 一行: 短标签 + 迷你进度条 + 已用百分比。 */
    @Composable
    private fun QuotaBar(label: String, used: Double?) {
        Row(
            modifier = GlanceModifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                label,
                style = TextStyle(
                    fontSize = 11.sp, color = GlanceTheme.colors.onSurfaceVariant,
                ),
                modifier = GlanceModifier.width(24.dp),
            )
            LinearProgressIndicator(
                progress = ((used ?: 0.0).coerceIn(0.0, 100.0) / 100.0).toFloat(),
                modifier = GlanceModifier.defaultWeight().height(6.dp),
                color = GlanceTheme.colors.primary,
                backgroundColor = ColorProvider(Color.Transparent),
            )
            Spacer(GlanceModifier.width(8.dp))
            Text(
                used?.let { "${it.roundToInt()}%" } ?: "—",
                style = TextStyle(
                    fontSize = 11.sp, color = GlanceTheme.colors.onSurface,
                ),
                modifier = GlanceModifier.width(32.dp),
            )
        }
    }
}
