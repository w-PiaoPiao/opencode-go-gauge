package io.github.yphyphyph.gogauge.widget

import android.content.Context
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import io.github.yphyphyph.gogauge.data.db.AppDatabase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * 配额小组件 receiver — 系统周期轮询 (quota_widget_info.xml 的 updatePeriodMillis)
 * 与添加小组件时回调; 数据刷新主链路由 quota_snapshots 变化驱动 (GoGaugeApp 注入)。
 */
class QuotaWidgetReceiver : GlanceAppWidgetReceiver() {

    override val glanceAppWidget: GlanceAppWidget = QuotaWidget()

    override fun onDeleted(context: Context, appWidgetIds: IntArray) {
        super.onDeleted(context, appWidgetIds)
        // 清理各小组件的账号选择配置 (settings payload 键 widget_account:{id})
        CoroutineScope(Dispatchers.IO).launch {
            appWidgetIds.forEach { AppDatabase.get(context).settingsDao().removeWidgetAccount(it) }
        }
    }
}
