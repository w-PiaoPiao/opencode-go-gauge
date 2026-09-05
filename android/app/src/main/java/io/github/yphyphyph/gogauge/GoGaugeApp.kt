package io.github.yphyphyph.gogauge

import android.app.Application
import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import io.github.yphyphyph.gogauge.data.db.AppDatabase
import io.github.yphyphyph.gogauge.data.db.ensureSeedRows
import io.github.yphyphyph.gogauge.data.remote.CommandCodeApi
import io.github.yphyphyph.gogauge.data.remote.ExchangeApi
import io.github.yphyphyph.gogauge.data.remote.OpenCodeApi
import io.github.yphyphyph.gogauge.data.remote.UpdateApi
import io.github.yphyphyph.gogauge.data.repository.DashboardRepository
import io.github.yphyphyph.gogauge.sync.SyncWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit

class GoGaugeApp : Application() {

    lateinit var database: AppDatabase
        private set
    lateinit var repository: DashboardRepository
        private set
    val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        instance = this
        database = AppDatabase.get(this)
        repository = DashboardRepository(
            db = database,
            api = OpenCodeApi(),
            ccApi = CommandCodeApi(),
            exchangeApi = ExchangeApi(),
            updateApi = UpdateApi(),
        )
        appScope.launch { database.ensureSeedRows() }
        scheduleBackgroundSync(this)
    }

    private fun scheduleBackgroundSync(context: Context) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        // Android minimum periodic interval is 15 minutes (platform limit);
        // foreground timers handle the 1/5/15/30 min intervals precisely.
        val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            "gousage-background-sync",
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    companion object {
        lateinit var instance: GoGaugeApp
            private set
    }
}
