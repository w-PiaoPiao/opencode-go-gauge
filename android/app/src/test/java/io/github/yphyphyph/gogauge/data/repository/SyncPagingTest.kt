package io.github.yphyphyph.gogauge.data.repository

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 同步翻页停止/截断判定 — 锁定 sync-fix 设计规范 §1 B/C 的硬性语义:
 * 1. 增量命中 since 边界 → 自然停止, 不算截断;
 * 2. 页数预算耗尽且游标未耗尽/未到边界 → truncated (收尾 partial 且**不推进**游标);
 * 3. 游标耗尽 → 非截断 (ok 收尾可安全前移游标);
 * 4. since 已知时禁止「连续两批 0 新增」早停 (会停在已知数据段、越不过缺口);
 * 5. 距上次全量成功超过校准周期的账号在增量轮次升级为 full (§1 E)。
 */
class SyncPagingTest {

    /** 任意基准毫秒 (since 边界)。 */
    private val since = 1_760_000_000_000L

    // ------------------------------------------------------------------
    // reachedSince: 增量是否已从最新连续翻到 since 边界
    // ------------------------------------------------------------------

    @Test
    fun `reached since when page oldest is at or before since`() {
        assertTrue(SyncPaging.reachedSince("incremental", since, since))
        assertTrue(SyncPaging.reachedSince("incremental", since, since - 1))
        assertTrue(SyncPaging.reachedSince("incremental", since, since - 3_600_000L))
        // 本页最早记录还比 since 新 -> 窗口尚未连续拉全, 必须继续翻
        assertFalse(SyncPaging.reachedSince("incremental", since, since + 1))
    }

    @Test
    fun `reached since requires known since and incremental mode`() {
        // since 未知 (账号无游标): 让位给"连续两批 0 新增"兜底, 不做 since 判定
        assertFalse(SyncPaging.reachedSince("incremental", null, since - 1))
        // 页内记录时间串全不可解析: 不能当作已触达边界
        assertFalse(SyncPaging.reachedSince("incremental", since, null))
        // full 模式没有 since 概念
        assertFalse(SyncPaging.reachedSince("full", since, since - 1))
    }

    // ------------------------------------------------------------------
    // truncated: 页数预算耗尽 ≠ 追平
    // ------------------------------------------------------------------

    @Test
    fun `page budget exhausted with cursor alive is truncated`() {
        // 场景: 休眠后追平缺口, 翻满 1000 页仍没到 since 边界且游标还有下一页
        assertTrue(
            SyncPaging.truncated(
                page = 1000, maxPages = 1000,
                exhausted = false, windowBoundaryReached = false, reachedSince = false,
            ),
        )
        // 旧预算 10 页时同样会截断 (回归点: 不能因页数>=上限就静默当成功)
        assertTrue(
            SyncPaging.truncated(
                page = 10, maxPages = 10,
                exhausted = false, windowBoundaryReached = false, reachedSince = false,
            ),
        )
    }

    @Test
    fun `cursor exhausted is not truncated`() {
        // 真正到底: 数据完整, ok 收尾可前移游标
        assertFalse(
            SyncPaging.truncated(
                page = 1000, maxPages = 1000,
                exhausted = true, windowBoundaryReached = false, reachedSince = false,
            ),
        )
    }

    @Test
    fun `reached since boundary is not truncated`() {
        // 增量翻到 since 边界 = 正常自然停止点 (即使恰好也翻满了预算)
        assertFalse(
            SyncPaging.truncated(
                page = 1000, maxPages = 1000,
                exhausted = false, windowBoundaryReached = false, reachedSince = true,
            ),
        )
    }

    @Test
    fun `full window boundary and below-budget are not truncated`() {
        // 全量命中同步范围窗口边界: 该页保留后停止, 数据完整
        assertFalse(
            SyncPaging.truncated(
                page = 1000, maxPages = 1000,
                exhausted = false, windowBoundaryReached = true, reachedSince = false,
            ),
        )
        // 还没翻满预算: 继续翻, 不是截断
        assertFalse(
            SyncPaging.truncated(
                page = 999, maxPages = 1000,
                exhausted = false, windowBoundaryReached = false, reachedSince = false,
            ),
        )
    }

    // ------------------------------------------------------------------
    // 「连续两批 0 新增」兜底: 仅 since 未知时可用
    // ------------------------------------------------------------------

    @Test
    fun `two empty batches stop only when since unknown`() {
        assertTrue(SyncPaging.stopOnEmptyBatches("incremental", null, 2))
        assertFalse(SyncPaging.stopOnEmptyBatches("incremental", null, 1))
        // since 已知时禁止早停 —— 已知数据段会提前触发该兜底, 越不过缺口 (本次 bug 放大器)
        assertFalse(SyncPaging.stopOnEmptyBatches("incremental", since, 2))
        assertFalse(SyncPaging.stopOnEmptyBatches("incremental", since, 99))
        // full 模式没有这条停止规则
        assertFalse(SyncPaging.stopOnEmptyBatches("full", null, 2))
    }

    @Test
    fun `empty batch counter increments on zero insert and resets otherwise`() {
        assertEquals(1, SyncPaging.updateEmptyBatches(inserted = 0, emptyPages = 0))
        assertEquals(2, SyncPaging.updateEmptyBatches(inserted = 0, emptyPages = 1))
        assertEquals(0, SyncPaging.updateEmptyBatches(inserted = 7, emptyPages = 2))
    }

    // ------------------------------------------------------------------
    // oldestMillis: 页内最早记录时间 (since 边界判定输入)
    // ------------------------------------------------------------------

    @Test
    fun `oldest millis picks earliest parseable timestamp`() {
        val records = listOf(
            "2026-11-17T08:00:00Z",
            "2026-11-15T00:00:00.000Z",
            "2026-11-16T12:34:56+00:00",
        )
        assertEquals(
            java.time.Instant.parse("2026-11-15T00:00:00Z").toEpochMilli(),
            SyncPaging.oldestMillis(records),
        )
        assertNull(SyncPaging.oldestMillis(emptyList()))
        assertNull(SyncPaging.oldestMillis(listOf("not-a-date", "")))
    }

    @Test
    fun `unparseable timestamps are ignored`() {
        assertEquals(
            java.time.Instant.parse("2026-11-16T00:00:00Z").toEpochMilli(),
            SyncPaging.oldestMillis(listOf("not-a-date", "2026-11-16T00:00:00Z")),
        )
    }

    // ------------------------------------------------------------------
    // effectiveMode: 自动全量校准 (§1 E)
    // ------------------------------------------------------------------

    @Test
    fun `due account upgrades incremental round to full`() {
        assertEquals("full", SyncPaging.effectiveMode("incremental", fullSyncDue = true))
        assertEquals("incremental", SyncPaging.effectiveMode("incremental", fullSyncDue = false))
        // 用户显式点「全量同步」时 mode 恒为 full, due 与否都不改变语义
        assertEquals("full", SyncPaging.effectiveMode("full", fullSyncDue = true))
        assertEquals("full", SyncPaging.effectiveMode("full", fullSyncDue = false))
    }

    @Test
    fun `truncation message matches unified spec wording`() {
        assertEquals(
            "达到单轮翻页上限 (数据不完整, 下次同步继续补拉; 如持续出现可手动全量同步)",
            SyncPaging.TRUNCATED_MESSAGE,
        )
    }

    @Test
    fun `failed pages message matches desktop wording`() {
        // 桌面 _finish_sync 两种 provider 共用该措辞; partial 收尾不推进游标, 下轮自动续拉
        assertEquals(
            "完成, 但翻页中断 (数据不完整, 下次同步自动继续补拉; 如持续出现可手动全量同步)",
            SyncPaging.FAILED_PAGES_MESSAGE,
        )
    }
}
