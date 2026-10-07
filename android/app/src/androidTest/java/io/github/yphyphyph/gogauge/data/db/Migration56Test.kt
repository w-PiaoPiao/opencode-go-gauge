package io.github.yphyphyph.gogauge.data.db

import android.content.Context
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.sqlite.db.SupportSQLiteOpenHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * MIGRATION_5_6 (quota_snapshots 建表) — 真实 SQLite 上直调 Migration.migrate:
 * 验证建表 SQL 语法与写读可用。项目 exportSchema=false 无 schema JSON,
 * 不能用 MigrationTestHelper 的 Room schema 等价校验 (编译期 KSP 已保证
 * 实体与 SQL 一致性由 schema 校验兜底的另一路径: 全新安装由 Room 自己建表)。
 */
@RunWith(AndroidJUnit4::class)
class Migration56Test {

    private fun openV5Db(name: String): SupportSQLiteDatabase {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val config = SupportSQLiteOpenHelper.Configuration.builder(context)
            .name(name)
            .callback(object : SupportSQLiteOpenHelper.Callback(5) {
                override fun onCreate(db: SupportSQLiteDatabase) {
                    // 最小 v5 库: 迁移只新建 quota_snapshots, 不依赖既有表
                }

                override fun onUpgrade(db: SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
            })
            .build()
        return FrameworkSQLiteOpenHelperFactory().create(config).writableDatabase
    }

    @Test
    fun migrationCreatesSnapshotTableAndWritesRoundTrip() = runBlocking {
        val db = openV5Db("migration-test-5-6.db")
        try {
            AppDatabase.MIGRATION_5_6.migrate(db)

            db.execSQL(
                "INSERT INTO quota_snapshots (account_id, provider, percent_5h, percent_week, percent_month," +
                    " reset_5h, reset_week, reset_month, month_remaining_amount, period_start, period_end, updated_at)" +
                    " VALUES (1, 'opencode', 42.0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-10-07T00:00:00Z')"
            )
            db.query("SELECT * FROM quota_snapshots WHERE account_id = 1").use { c ->
                assertTrue(c.moveToFirst())
                assertEquals(1, c.getInt(c.getColumnIndexOrThrow("account_id")))
                assertEquals(42.0, c.getDouble(c.getColumnIndexOrThrow("percent_5h")), 0.001)
                assertTrue(c.isNull(c.getColumnIndexOrThrow("percent_month")))
            }
        } finally {
            db.close()
        }
    }
}
