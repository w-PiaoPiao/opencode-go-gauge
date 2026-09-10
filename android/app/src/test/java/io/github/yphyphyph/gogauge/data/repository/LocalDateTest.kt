package io.github.yphyphyph.gogauge.data.repository

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/**
 * localDate 派生测试 (MIGRATION_3_4 引入的物化本地日列).
 *
 * 该列的存在是为了让日界过滤能走 idx_usage_account_localdate: 原先
 * substr(datetime(created_at,'localtime'),1,10) 让索引失效且 SQLite 拒绝
 * 把 localtime 表达式建进索引. 这里锁定"写入列 == 查询侧 SQLite 口径".
 */
class LocalDateTest {

    private val zone: ZoneId = ZoneId.systemDefault()

    @Test
    fun `parses ISO instant with Z suffix`() {
        // 2026-09-10T02:30:00Z 在东八区属于 09-10 当天
        val iso = "2026-09-10T02:30:00Z"
        val expected = Instant.parse(iso).atZone(zone).toLocalDate().toString()
        assertEquals(expected, localDateOf(iso))
    }

    @Test
    fun `utc midnight maps to the correct local day`() {
        // 这一条是日界的关键: UTC 00:00 在 UTC+8 已经是当天 08:00
        val iso = "2026-09-10T00:00:00Z"
        val expected = Instant.parse(iso).atZone(zone).toLocalDate()
            .format(DateTimeFormatter.ISO_LOCAL_DATE)
        assertEquals(expected, localDateOf(iso))
    }

    @Test
    fun `handles offset form without Z`() {
        assertEquals(
            localDateOf("2026-09-10T00:00:00+00:00"),
            localDateOf("2026-09-10T00:00:00Z"),
        )
    }

    @Test
    fun `returns null for unparseable input`() {
        assertNull(localDateOf(""))
        assertNull(localDateOf("not-a-date"))
    }

    @Test
    fun `bucket format parses as UTC then converts`() {
        // charts 桶为 UTC "yyyy-MM-dd HH:mm:ss" (无 T/Z), 与 created_at 的 ISO 形式不同
        val bucket = "2026-09-10 20:00:00"
        val expected = java.time.LocalDateTime.parse(
            bucket, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"),
        ).toInstant(java.time.ZoneOffset.UTC).atZone(zone).toLocalDate().toString()
        assertEquals(expected, localDateOfBucket(bucket))
    }

    @Test
    fun `bucket and instant helpers agree on the same moment`() {
        // 同一时刻的两种表示必须得到同一个本地日
        assertEquals(
            localDateOf("2026-09-10T20:00:00Z"),
            localDateOfBucket("2026-09-10 20:00:00"),
        )
    }

    @Test
    fun `bucket returns null for unparseable input`() {
        assertNull(localDateOfBucket(""))
        assertNull(localDateOfBucket("2026/09/10"))
    }
}
