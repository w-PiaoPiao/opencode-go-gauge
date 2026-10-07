package io.github.yphyphyph.gogauge.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import io.github.yphyphyph.gogauge.GoGaugeApp

/**
 * Background incremental sync worker (WorkManager, min 15-min period).
 * Skips silently when not logged in; retries on transient failures.
 */
class SyncWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val repo = GoGaugeApp.instance.repository
        val result = repo.syncUsage("incremental")
        return when {
            result.ok -> {
                // 同步引擎只拉明细不拉配额: 补一轮配额刷新把 quota_snapshots 更新,
                // 否则 app 长期退后台时小组件/磁贴/常驻通知一直显示旧余量
                repo.refreshAllQuotas()
                Result.success()
            }
            // 永久性失败 (未登录/鉴权失效/已有同步在跑) 不重试: 否则 WorkManager
            // 会按指数退避无限重试一个不会自愈的错误, 白白耗电与流量
            !result.retryable -> Result.success()
            else -> Result.retry()
        }
    }
}
