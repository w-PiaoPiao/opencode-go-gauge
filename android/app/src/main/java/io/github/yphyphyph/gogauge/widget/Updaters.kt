package io.github.yphyphyph.gogauge.widget

import android.content.Context
import androidx.glance.appwidget.updateAll
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * 快照变化 → 三个进程外入口的统一刷新分发 (v2.2.0b)。
 * GoGaugeApp 把 [DashboardRepository.onSnapshotsChanged] 指到 [dispatch]:
 * 小组件 Glance update / 磁贴 requestListeningState / 常驻通知重绘。
 * 各入口独立容错, 单个失败不影响其余。
 */
object Updaters {

    private val scope = CoroutineScope(Dispatchers.Default)

    fun dispatch(context: Context) {
        scope.launch {
            runCatching { QuotaWidget().updateAll(context) }
                .onFailure { android.util.Log.w("GoGauge", "widget update failed", it) }
        }
        runCatching { QuotaTileService.requestUpdate(context) }
            .onFailure { android.util.Log.w("GoGauge", "tile update failed", it) }
        scope.launch {
            runCatching { PersistentNotification.refresh(context) }
                .onFailure { android.util.Log.w("GoGauge", "notification update failed", it) }
        }
    }
}
