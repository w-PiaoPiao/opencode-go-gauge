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
            result.ok -> Result.success()
            result.error == "未登录" -> Result.success() // nothing to do; stop scheduling retries
            else -> Result.retry()
        }
    }
}
