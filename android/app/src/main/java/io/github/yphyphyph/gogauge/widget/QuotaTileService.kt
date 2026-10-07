package io.github.yphyphyph.gogauge.widget

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

/**
 * 配额快捷磁贴 (v2.2.0b) — 显示月度 + 5h 窗口余量 (进程外 QuickSettings 渲染,
 * 读 quota_snapshots); 点按打开主界面。
 *
 * 刷新: onStartListening (用户展开快捷面板) + 快照变化时 requestListeningState
 * (WidgetUpdaters)。
 */
class QuotaTileService : TileService() {

    private val scope = CoroutineScope(Dispatchers.IO)

    override fun onStartListening() {
        super.onStartListening()
        refresh()
    }

    override fun onTileAdded() {
        super.onTileAdded()
        refresh()
    }

    /** IO 读库后回主线程更新磁贴状态。 */
    private fun refresh() {
        val tile = qsTile ?: return
        scope.launch {
            val data = WidgetData.load(this@QuotaTileService)
            // 复用 WidgetData 的本地化短标签 (5h/周/月)
            val summary = data.rows.mapNotNull { r -> r.used?.let { "${r.label} ${it.roundToInt()}%" } }
                .joinToString(" · ").ifEmpty { "—" }
            Handler(Looper.getMainLooper()).post {
                val t = qsTile ?: return@post
                t.state = if (data.hasSnapshot) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
                // Tile 副文案位: subtitle (31+) / stateDescription (29+) / contentDescription (24+)
                if (Build.VERSION.SDK_INT >= 31) t.subtitle = summary
                else if (Build.VERSION.SDK_INT >= 29) t.stateDescription = summary
                else t.contentDescription = summary
                t.updateTile()
            }
        }
    }

    override fun onClick() {
        super.onClick()
        val intent = Intent(this, io.github.yphyphyph.gogauge.MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        // API 31+ 只接受 PendingIntent 版本, Intent 版本已废弃
        if (Build.VERSION.SDK_INT >= 31) {
            val pi = android.app.PendingIntent.getActivity(
                this, 0, intent, android.app.PendingIntent.FLAG_IMMUTABLE,
            )
            startActivityAndCollapse(pi)
        } else {
            @Suppress("DEPRECATION")
            startActivityAndCollapse(intent)
        }
    }

    companion object {
        /** 请求系统回调 onStartListening — 快照变化后由 WidgetUpdaters 调用。 */
        fun requestUpdate(context: Context) {
            TileService.requestListeningState(
                context,
                ComponentName(context, QuotaTileService::class.java),
            )
        }
    }
}
