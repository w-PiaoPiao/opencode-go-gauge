package io.github.yphyphyph.gogauge.data.db

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 自动全量校准到期判定 (sync-fix 设计规范 §1 E):
 * - 键缺失 (账号从未成功全量, 含新账号) → due;
 * - 时间串解析失败 (脏数据/旧格式) → due;
 * - 距上次成功全量严格超过 AUTO_FULL_SYNC_DAYS (7 天) → due; 新鲜 → 不 due。
 *
 * 依赖 DB 的 [SettingsDao.fullSyncDue] 只做"读 payload + 调用本纯函数"两层,
 * 这里覆盖全部判定语义, 无需起 Room。
 */
class FullSyncCadenceTest {

    private val now = java.time.Instant.parse("2026-11-17T08:00:00Z").toEpochMilli()
    private val dayMs = 24L * 3600L * 1000L

    private fun isoAgeDays(days: Long, extraMinutes: Long = 0): String =
        java.time.Instant.ofEpochMilli(now - days * dayMs - extraMinutes * 60_000L).toString()

    // ------------------------------------------------------------------
    // 缺失 / 脏数据 → due
    // ------------------------------------------------------------------

    @Test
    fun `missing mark is due`() {
        assertTrue(FullSyncCadence.isDue(null, now))
        assertTrue(FullSyncCadence.isDue("", now))
        assertTrue(FullSyncCadence.isDue("   ", now))
    }

    @Test
    fun `unparseable mark is due`() {
        // 宁可多跑一次全量, 也不能因脏数据跳过校准
        assertTrue(FullSyncCadence.isDue("not-a-date", now))
        assertTrue(FullSyncCadence.isDue("2026/11/10 00:00:00", now))
    }

    // ------------------------------------------------------------------
    // 新鲜 → 不 due
    // ------------------------------------------------------------------

    @Test
    fun `fresh mark is not due`() {
        assertFalse(FullSyncCadence.isDue(isoAgeDays(0), now))       // 刚刚全量过
        assertFalse(FullSyncCadence.isDue(isoAgeDays(1), now))
        assertFalse(FullSyncCadence.isDue(isoAgeDays(6), now))
        assertFalse(FullSyncCadence.isDue(isoAgeDays(6, extraMinutes = 23 * 60), now))
    }

    @Test
    fun `legacy iso with utc offset is parsed`() {
        // parseIsoInstant 兼容 "+00:00" 偏移形态 (老版本/其它端写入)
        val last = java.time.Instant.ofEpochMilli(now - dayMs).toString().replace("Z", "+00:00")
        assertFalse(FullSyncCadence.isDue(last, now))
    }

    // ------------------------------------------------------------------
    // 过期 → due (含周期边界)
    // ------------------------------------------------------------------

    @Test
    fun `expired mark is due`() {
        assertTrue(FullSyncCadence.isDue(isoAgeDays(8), now))
        assertTrue(FullSyncCadence.isDue(isoAgeDays(30), now))
    }

    @Test
    fun `mark just past period boundary is due`() {
        // 与 desktop/HarmonyOS 同口径: 严格"超过" 7 天才到期; 恰好 7 天仍算新鲜
        assertFalse(FullSyncCadence.isDue(isoAgeDays(7), now))
        assertTrue(FullSyncCadence.isDue(isoAgeDays(7, extraMinutes = 1), now))
        assertTrue(FullSyncCadence.isDue(isoAgeDays(7, extraMinutes = 60), now))
    }

    @Test
    fun `custom period days is honored`() {
        assertFalse(FullSyncCadence.isDue(isoAgeDays(2), now, days = 3))
        // 恰好 3 天不 due (严格超过才到期)
        assertFalse(FullSyncCadence.isDue(isoAgeDays(3), now, days = 3))
        assertTrue(FullSyncCadence.isDue(isoAgeDays(3, extraMinutes = 5), now, days = 3))
        assertTrue(FullSyncCadence.isDue(isoAgeDays(10), now, days = 3))
    }

    @Test
    fun `non-positive period is always due`() {
        assertTrue(FullSyncCadence.isDue(isoAgeDays(0), now, days = 0))
        assertTrue(FullSyncCadence.isDue(isoAgeDays(0), now, days = -1))
    }

    @Test
    fun `default calibration period is seven days`() {
        assertEquals(7, FullSyncCadence.AUTO_FULL_SYNC_DAYS)
        // 默认参数与常量一致: 6 天不 due / 超过 7 天才 due
        assertFalse(FullSyncCadence.isDue(isoAgeDays(6), now))
        assertFalse(FullSyncCadence.isDue(isoAgeDays(7), now))
        assertTrue(FullSyncCadence.isDue(isoAgeDays(8), now))
    }

    @Test
    fun `future mark is not due`() {
        // 本机时钟回拨/其它端时钟超前: 未来时间串不算过期, 不触发全量
        assertFalse(FullSyncCadence.isDue(isoAgeDays(-1), now))
    }
}
