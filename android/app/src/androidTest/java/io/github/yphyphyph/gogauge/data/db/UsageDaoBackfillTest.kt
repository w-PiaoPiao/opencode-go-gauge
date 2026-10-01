package io.github.yphyphyph.gogauge.data.db

import android.content.Context
import androidx.room.Room
import androidx.sqlite.db.SimpleSQLiteQuery
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith
import java.time.Instant
import java.time.ZoneId

/**
 * local_date 回填的 SQL 口径验证 (真实 SQLite):
 * 旧版 Android 写入的行 local_date 为 NULL, 回填结果必须与 Kotlin 侧
 * localDateOf (Instant -> 系统时区 -> 本地日) 完全一致。
 */
@RunWith(AndroidJUnit4::class)
class UsageDaoBackfillTest {

    private fun openDb(): AppDatabase =
        Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext<Context>(),
            AppDatabase::class.java,
        ).build()

    @Test
    fun backfillMatchesKotlinLocalDateOf() = runBlocking {
        val db = openDb()
        try {
            val dao = db.usageDao()
            val createdAts = listOf(
                "2026-09-02T11:31:04.353Z", // 带毫秒
                "2026-09-02T23:59:59Z",     // 跨本地日边界 (UTC+8 为次日)
                "2026-01-01T00:00:00Z",
            )
            dao.upsertAll(
                createdAts.mapIndexed { i, ts ->
                    UsageRecordEntity(
                        usgId = "bf-$i",
                        createdAt = ts,
                        model = "m",
                        inputTokens = 1,
                        outputTokens = 0,
                        accountId = 1,
                        localDate = null, // 模拟旧版解析失败
                    )
                },
            )
            assertEquals(3, dao.backfillNullLocalDates())
            // 幂等: 再跑一次没有 NULL 行可更新
            assertEquals(0, dao.backfillNullLocalDates())

            val rows = dao.recordsRaw(
                SimpleSQLiteQuery("SELECT * FROM usage_records ORDER BY usg_id")
            )
            assertEquals(3, rows.size)
            rows.forEach { row ->
                val expected = Instant.parse(row.createdAt)
                    .atZone(ZoneId.systemDefault()).toLocalDate().toString()
                assertNotNull("local_date must be filled for ${row.createdAt}", row.localDate)
                assertEquals("local_date mismatch for ${row.createdAt}", expected, row.localDate)
            }
        } finally {
            db.close()
        }
    }

    @Test
    fun backfillSkipsGarbageRows() = runBlocking {
        val db = openDb()
        try {
            val dao = db.usageDao()
            dao.upsertAll(
                listOf(
                    UsageRecordEntity(
                        usgId = "short", createdAt = "bad", model = "m",
                        inputTokens = 1, outputTokens = 0, accountId = 1, localDate = null,
                    ),
                ),
            )
            // 长度不足 19 的行不参与回填 (避免把 local_date 置成 NULL 之外的东西)
            assertEquals(0, dao.backfillNullLocalDates())
            val row = dao.recordsRaw(SimpleSQLiteQuery("SELECT * FROM usage_records WHERE usg_id = 'short'"))
            assertEquals(null, row.first().localDate)
        } finally {
            db.close()
        }
    }
}
