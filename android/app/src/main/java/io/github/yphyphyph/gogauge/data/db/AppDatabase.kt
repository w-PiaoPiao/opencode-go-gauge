package io.github.yphyphyph.gogauge.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.room.withTransaction
import java.time.Instant

/**
 * GoGauge database — schema mirrors desktop db.py v2.0.0 exactly.
 */
@Database(
    entities = [
        AccountEntity::class,
        UsageRecordEntity::class,
        SyncStateEntity::class,
        SettingsEntity::class,
        UsageChartEntity::class,
    ],
    version = 4,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun usageDao(): UsageDao
    abstract fun syncDao(): SyncDao
    abstract fun settingsDao(): SettingsDao
    abstract fun chartDao(): ChartDao

    companion object {
        @Volatile
        private var instance: AppDatabase? = null

        /**
         * v2 → v3 GOAT (commandcode) 迁移 — 桌面 db.py 迁移 4 + usage_charts 建表 parity:
         * 1) accounts 补 provider 列 (存量 opencode 回填默认值)
         * 2) usage_charts (模型 × 5min 桶全周期聚合) 建表 + 索引
         */
        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "ALTER TABLE `accounts` ADD COLUMN `provider` TEXT NOT NULL DEFAULT 'opencode'"
                )
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `usage_charts` (" +
                        "`account_id` INTEGER NOT NULL, " +
                        "`model` TEXT NOT NULL, " +
                        "`provider` TEXT, " +
                        "`time_bucket` TEXT NOT NULL, " +
                        "`requests` INTEGER NOT NULL DEFAULT 0, " +
                        "`input_cost` REAL NOT NULL DEFAULT 0, " +
                        "`output_cost` REAL NOT NULL DEFAULT 0, " +
                        "`cache_cost` REAL NOT NULL DEFAULT 0, " +
                        "`total_cost` REAL NOT NULL DEFAULT 0, " +
                        "`credits_total` REAL NOT NULL DEFAULT 0, " +
                        "`tokens_in` INTEGER NOT NULL DEFAULT 0, " +
                        "`tokens_out` INTEGER NOT NULL DEFAULT 0, " +
                        "`tokens_total` INTEGER NOT NULL DEFAULT 0, " +
                        "`cache_read_tokens` INTEGER NOT NULL DEFAULT 0, " +
                        "`cache_creation_tokens` INTEGER NOT NULL DEFAULT 0, " +
                        "`synced_at` TEXT NOT NULL, " +
                        "PRIMARY KEY (`account_id`, `model`, `time_bucket`))"
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `idx_charts_account_time`" +
                        " ON `usage_charts` (`account_id`, `time_bucket`)"
                )
            }
        }

        /**
         * v3 → v4 日界索引 — 对齐桌面 db.py 迁移 6.
         *
         * 背景: 所有周期过滤原先写作 substr(datetime(created_at,'localtime'),1,10),
         * 函数包裹索引列使 SQLite 无法范围扫描, 每个周期查询都退化为按账号全表扫
         * (dashboard 一次刷新 6 条, commandcode 翻倍). SQLite 也拒绝把 localtime
         * 表达式建进索引 ("non-deterministic use of datetime() in an index"),
         * 因此改为物化 local_date 列并在写入时计算.
         *
         * 1) 两表补 local_date 列
         * 2) 存量回填 (date(...,'localtime') 与 Room 侧本地日口径一致)
         * 3) 建 (account_id, local_date) / (account_id, model) 索引
         */
        val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE `usage_records` ADD COLUMN `local_date` TEXT")
                db.execSQL("ALTER TABLE `usage_charts` ADD COLUMN `local_date` TEXT")
                db.execSQL(
                    "UPDATE `usage_records` SET `local_date` = date(`created_at`, 'localtime')" +
                        " WHERE `local_date` IS NULL"
                )
                db.execSQL(
                    "UPDATE `usage_charts` SET `local_date` = date(`time_bucket`, 'localtime')" +
                        " WHERE `local_date` IS NULL"
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `idx_usage_account_localdate`" +
                        " ON `usage_records` (`account_id`, `local_date`)"
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `idx_usage_account_model`" +
                        " ON `usage_records` (`account_id`, `model`)"
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `idx_charts_account_localdate`" +
                        " ON `usage_charts` (`account_id`, `local_date`)"
                )
            }
        }

        /**
         * v1 → v2 多账号迁移 — 语义与 desktop db._init_schema 迁移 1/2/3 一一对应:
         * 1) account 单行表 → accounts 多行表 (仅当目标为空时拷贝, 保证幂等)
         * 2) usage_records 补 account_id 列 + 复合索引
         * 3) usage_sync_state 由 id 主键重建为 account_id 主键 (数据无损搬运)
         */
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `accounts` (" +
                        "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                        "`name` TEXT NOT NULL DEFAULT 'Default', " +
                        "`workspace_id` TEXT NOT NULL DEFAULT 'Default', " +
                        "`resolved_workspace_id` TEXT, " +
                        "`token` TEXT NOT NULL DEFAULT '', " +
                        "`created_at` TEXT NOT NULL, " +
                        "`updated_at` TEXT NOT NULL)"
                )
                db.execSQL(
                    "INSERT INTO `accounts` (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)" +
                        " SELECT id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at FROM `account`" +
                        " WHERE NOT EXISTS (SELECT 1 FROM `accounts`)"
                )
                db.execSQL("DROP TABLE IF EXISTS `account`")
                db.execSQL("ALTER TABLE `usage_records` ADD COLUMN `account_id` INTEGER NOT NULL DEFAULT 1")
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `idx_usage_account_time` ON `usage_records` (`account_id`, `created_at`)"
                )
                // 补 provider 列 (记录来源快照): 部分历史 v1 建表已含该列,
                // 以 PRAGMA 幂等判断, 两种形态都安全 (desktop db._init_schema 迁移 4 parity)
                var hasProviderColumn = false
                db.query("PRAGMA table_info(usage_records)").use { cursor ->
                    while (cursor.moveToNext()) {
                        if (cursor.getString(1) == "provider") hasProviderColumn = true
                    }
                }
                if (!hasProviderColumn) {
                    db.execSQL("ALTER TABLE `usage_records` ADD COLUMN `provider` TEXT")
                }
                db.execSQL("ALTER TABLE `usage_sync_state` RENAME TO `usage_sync_state_legacy`")
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `usage_sync_state` (" +
                        "`account_id` INTEGER PRIMARY KEY NOT NULL, " +
                        "`last_sync_at` TEXT, " +
                        "`last_sync_status` TEXT, " +
                        "`last_sync_error` TEXT, " +
                        "`last_inserted_count` INTEGER NOT NULL DEFAULT 0, " +
                        "`deepest_page_fetched` INTEGER NOT NULL DEFAULT -1, " +
                        "`total_records` INTEGER NOT NULL DEFAULT 0, " +
                        "`oldest_record_at` TEXT, " +
                        "`newest_record_at` TEXT)"
                )
                db.execSQL(
                    "INSERT INTO `usage_sync_state` (account_id, last_sync_at, last_sync_status, last_sync_error," +
                        " last_inserted_count, deepest_page_fetched, total_records, oldest_record_at, newest_record_at)" +
                        " SELECT id, last_sync_at, last_sync_status, last_sync_error," +
                        " last_inserted_count, deepest_page_fetched, total_records, oldest_record_at, newest_record_at" +
                        " FROM `usage_sync_state_legacy`"
                )
                db.execSQL("DROP TABLE `usage_sync_state_legacy`")
            }
        }

        fun get(context: Context): AppDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "gousage.db",
                )
                    .addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4)
                    .build().also { instance = it }
            }
    }
}

/**
 * Seed singleton rows on first open — mirrors db._init_schema seeding (desktop v2.0.0):
 * 全新库种子默认空账号 (未登录态); 同步状态行由 ensureStateRow 在登录/添加时补齐.
 */
suspend fun AppDatabase.ensureSeedRows() = withTransaction {
    val now = Instant.now().toString()
    // provider 为 v3 新增 NOT NULL 列且 Room 建表不写 Kotlin 默认值:
    // 裸 INSERT 必须显式带 provider, 否则全新安装首启动即触发约束失败
    openHelper.writableDatabase.execSQL(
        "INSERT OR IGNORE INTO accounts (id, name, workspace_id, resolved_workspace_id, token, provider, created_at, updated_at)" +
            " VALUES (1, 'Default', 'Default', NULL, '', 'opencode', ?, ?)",
        arrayOf(now, now),
    )
    openHelper.writableDatabase.execSQL(
        "INSERT OR IGNORE INTO usage_sync_state (account_id, deepest_page_fetched) VALUES (1, -1)"
    )
    openHelper.writableDatabase.execSQL(
        "INSERT OR IGNORE INTO settings (id, payload, updated_at) VALUES (1, '{}', ?)",
        arrayOf(now),
    )
}
