package io.github.yphyphyph.gogauge.widget

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import io.github.yphyphyph.gogauge.MainActivity
import io.github.yphyphyph.gogauge.R
import io.github.yphyphyph.gogauge.data.db.AppDatabase
import io.github.yphyphyph.gogauge.util.Fmt
import kotlin.math.roundToInt

/**
 * 常驻通知 (v2.2.0b, 设置开关默认关) — 低优先级 ongoing 通知显示三窗口余量 +
 * 今日费用, 随 quota_snapshots 更新 ([Updaters] 在快照变化时调用 [refresh])。
 */
object PersistentNotification {

    private const val CHANNEL_ID = "gousage_persistent"
    private const val NOTIF_ID = 42

    suspend fun refresh(context: Context) {
        val db = AppDatabase.get(context)
        if (!db.settingsDao().getSettings().persistentNotification) {
            cancel(context)
            return
        }
        // 33+ 运行时权限未授予时静默取消 (设置页开启开关时会请求权限)
        if (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            cancel(context)
            return
        }

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "GoGauge", NotificationManager.IMPORTANCE_MIN).apply {
                    setShowBadge(false)
                },
            )
        }

        val data = WidgetData.load(context)
        val windows = data.rows.mapNotNull { r -> r.used?.let { "${r.label} ${it.roundToInt()}%" } }
            .joinToString("  ·  ")
        val today = "${Fmt.money(data.todayCostUsd, "USD", 1.0)} · ${Fmt.int(data.todayRequests)}"
        val text = if (windows.isEmpty()) today else "$windows  ·  $today"

        val contentPi = PendingIntent.getActivity(
            context, 0,
            Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = Notification.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notif)
            .setContentTitle(data.accountName)
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(contentPi)
            .setCategory(Notification.CATEGORY_STATUS)
        notify(context, builder.build())
    }

    private fun notify(context: Context, notification: Notification) {
        try {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.notify(NOTIF_ID, notification)
        } catch (_: SecurityException) {
            // 通知权限被用户中途收回: 忽略
        }
    }

    fun cancel(context: Context) {
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.cancel(NOTIF_ID)
    }
}
