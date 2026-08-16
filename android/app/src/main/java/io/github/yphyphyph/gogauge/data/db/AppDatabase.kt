package io.github.yphyphyph.gogauge.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.withTransaction
import java.time.Instant

/**
 * GoGauge database — schema mirrors desktop db.py exactly.
 */
@Database(
    entities = [
        AccountEntity::class,
        UsageRecordEntity::class,
        SyncStateEntity::class,
        SettingsEntity::class,
    ],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun usageDao(): UsageDao
    abstract fun syncDao(): SyncDao
    abstract fun settingsDao(): SettingsDao

    companion object {
        @Volatile
        private var instance: AppDatabase? = null

        fun get(context: Context): AppDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "gousage.db",
                ).build().also { instance = it }
            }
    }
}

/** Seed singleton rows on first open — mirrors db._init_schema seeding (desktop). */
suspend fun AppDatabase.ensureSeedRows() = withTransaction {
    val now = Instant.now().toString()
    openHelper.writableDatabase.execSQL(
        "INSERT OR IGNORE INTO account (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)" +
            " VALUES (1, 'Default', 'Default', NULL, '', ?, ?)",
        arrayOf(now, now),
    )
    openHelper.writableDatabase.execSQL("INSERT OR IGNORE INTO usage_sync_state (id) VALUES (1)")
    openHelper.writableDatabase.execSQL(
        "INSERT OR IGNORE INTO settings (id, payload, updated_at) VALUES (1, '{}', ?)",
        arrayOf(now),
    )
}
