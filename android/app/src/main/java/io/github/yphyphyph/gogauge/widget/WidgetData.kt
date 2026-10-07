package io.github.yphyphyph.gogauge.widget

import android.content.Context
import io.github.yphyphyph.gogauge.data.db.AppDatabase
import io.github.yphyphyph.gogauge.data.model.PROVIDER_COMMANDCODE

/**
 * 小组件 / 磁贴 / 常驻通知共用的数据组装 — 快照表 + 当日合计, 活跃账号视角。
 *
 * 全部读 Room, 无进程内配额缓存依赖: 这三个入口都在 app 进程外 (RemoteViews /
 * QuickSettings / 通知栏) 或独立生命周期渲染, 快照表是唯一可靠的持久数据源。
 */
object WidgetData {

    /** 一行窗口数据 (已用 %)。 */
    data class Row(val label: String, val used: Double?)

    data class Data(
        val accountName: String,
        val todayCostUsd: Double,
        val todayRequests: Int,
        val rows: List<Row>,
        /** 快照更新时刻 (epoch ms); 从未拉到配额为 null。 */
        val updatedAtMs: Long?,
    ) {
        val hasSnapshot: Boolean get() = rows.any { it.used != null }
    }

    /** 窗口短标签 (小组件空间有限, 不用统计页的全称)。 */
    private fun rowLabels(lang: String): List<String> =
        if (lang == "zh") listOf("5h", "周", "月") else listOf("5h", "Wk", "Mo")

    /** 当前界面语言 (与 MainViewModel 的 gousage-prefs 键一致)。 */
    private fun lang(context: Context): String =
        context.getSharedPreferences("gousage-prefs", Context.MODE_PRIVATE)
            .getString("lang", "zh") ?: "zh"

    /**
     * 装载展示数据。[appWidgetId] 传入时按该小组件的配置选账号 ("active"/"account:{id}"),
     * 为 null (磁贴/常驻通知) 时恒用活跃账号。
     */
    suspend fun load(context: Context, appWidgetId: Int? = null): Data {
        val db = AppDatabase.get(context)
        val lang = lang(context)
        val syncDao = db.syncDao()

        val aid = if (appWidgetId != null) {
            when (val mode = db.settingsDao().getWidgetAccount(appWidgetId)) {
                "active", "" -> syncDao.getActiveAccountId()
                else -> mode.removePrefix("account:").toIntOrNull() ?: syncDao.getActiveAccountId()
            }
        } else {
            syncDao.getActiveAccountId()
        }

        val accounts = syncDao.listAccounts()
        val name = accounts.firstOrNull { it.id == aid }?.name ?: "GoGauge"
        if (aid == 0 || accounts.firstOrNull { it.id == aid }?.hasToken != true) {
            return Data(name, 0.0, 0, emptyList(), null)
        }

        val provider = syncDao.getAccountProvider(aid)
        val chartsFirst = provider == PROVIDER_COMMANDCODE && db.chartDao().chartsReady(aid) != null
        val today = if (chartsFirst) db.chartDao().totals("today", aid) else db.usageDao().totals("today", aid)

        val snap = db.quotaSnapshotDao().forAccount(aid)
        val labels = rowLabels(lang)
        val rows = listOf(
            Row(labels[0], snap?.percent5h),
            Row(labels[1], snap?.percentWeek),
            Row(labels[2], snap?.percentMonth),
        )
        return Data(
            accountName = name,
            todayCostUsd = today.totalCostUsd,
            todayRequests = today.requestCount,
            rows = rows,
            updatedAtMs = snap?.let { s ->
                io.github.yphyphyph.gogauge.util.parseIsoInstant(s.updatedAt)?.toEpochMilli()
            },
        )
    }
}
