package io.github.yphyphyph.gogauge.data.db

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 峰谷分档规则 — 与桌面 app/db.py `_peak_tier_sql` / `_PRICING_GATES` 逐条 parity。
 *
 * 关键口径 (全部来自桌面实测账单反证, 不是推测):
 * - 北京峰窗 09:00-12:00 / 14:00-18:00, 区间**左闭右开** (11:59:59 仍高峰);
 * - 只有周一至周五 + 非法定节假日才算高峰 (调休补班的周六仍按空闲计费);
 * - 起始门按模型区分: v4.1-flash 北京 2026-09-10、v4-flash 北京 2026-08-17。
 */
class PeakSplitTest {

    // ── 峰窗 ────────────────────────────────────────────────────────────

    @Test
    fun workdayPeakWindowsInBeijingTime() {
        // 2026-10-27 是周二。北京 09:00 = UTC 01:00
        assertEquals("peak", PeakSplit.tierOf("2026-10-27T01:00:00Z", "deepseek-v4.1-flash"))
        // 北京 10:00 = UTC 02:00
        assertEquals("peak", PeakSplit.tierOf("2026-10-27T02:00:00Z", "deepseek-v4.1-flash"))
        // 北京 11:59 = UTC 03:59 (左闭右开: 仍高峰)
        assertEquals("peak", PeakSplit.tierOf("2026-10-27T03:59:00Z", "deepseek-v4.1-flash"))
        // 北京 12:00 = UTC 04:00 (右开: 已切空闲 —— 实测 12:00:07 为空闲价)
        assertEquals("off", PeakSplit.tierOf("2026-10-27T04:00:00Z", "deepseek-v4.1-flash"))
        // 北京 13:00 = UTC 05:00 午休空闲
        assertEquals("off", PeakSplit.tierOf("2026-10-27T05:00:00Z", "deepseek-v4.1-flash"))
        // 北京 14:00 = UTC 06:00 下午峰段起点
        assertEquals("peak", PeakSplit.tierOf("2026-10-27T06:00:00Z", "deepseek-v4.1-flash"))
        // 北京 17:59 = UTC 09:59
        assertEquals("peak", PeakSplit.tierOf("2026-10-27T09:59:00Z", "deepseek-v4.1-flash"))
        // 北京 18:00 = UTC 10:00 收工
        assertEquals("off", PeakSplit.tierOf("2026-10-27T10:00:00Z", "deepseek-v4.1-flash"))
    }

    @Test
    fun weekendIsAlwaysOffPeak() {
        // 2026-10-31 周六 / 2026-11-01 周日, 峰窗时刻也按空闲计
        assertEquals("off", PeakSplit.tierOf("2026-10-31T02:00:00Z", "deepseek-v4.1-flash"))
        assertEquals("off", PeakSplit.tierOf("2026-11-01T07:00:00Z", "deepseek-v4.1-flash"))
    }

    @Test
    fun statutoryHolidaysAreOffPeak() {
        // 国庆 2026-10-01..07 (周四), 中秋 2026-09-25 —— 都在起始门之后
        assertEquals("off", PeakSplit.tierOf("2026-10-01T02:00:00Z", "deepseek-v4.1-flash"))
        assertEquals("off", PeakSplit.tierOf("2026-10-06T07:00:00Z", "deepseek-v4.1-flash"))
        assertEquals("off", PeakSplit.tierOf("2026-09-25T02:00:00Z", "deepseek-v4.1-flash"))
        // 春节 (2026-02-15..23) 在计价起始门之前: 当时还是单一价, 不分档
        assertNull(PeakSplit.tierOf("2026-02-16T02:00:00Z", "deepseek-v4.1-flash"))
        // 节假日结束后的首个工作日恢复高峰
        assertEquals("peak", PeakSplit.tierOf("2026-10-08T02:00:00Z", "deepseek-v4.1-flash"))
    }

    @Test
    fun makeupWorkSaturdayStaysOffPeak() {
        // 2026-10-10 为调休补班的周六: 实测仍按空闲价, 判定只看周末 + 法定节假日
        assertEquals("off", PeakSplit.tierOf("2026-10-10T02:00:00Z", "deepseek-v4.1-flash"))
        // 2026-09-20 同为补班周日
        assertEquals("off", PeakSplit.tierOf("2026-09-20T02:00:00Z", "deepseek-v4.1-flash"))
    }

    // ── 起始门 (按模型区分) ──────────────────────────────────────────────

    @Test
    fun gateIsPerModel() {
        // v4.1-flash: 北京 2026-09-10 00:00 = UTC 2026-09-09 16:00
        assertNull(PeakSplit.tierOf("2026-09-09T15:59:00Z", "deepseek-v4.1-flash"))
        assertEquals("off", PeakSplit.tierOf("2026-09-09T16:00:00Z", "deepseek-v4.1-flash"))
        // v4-flash: 北京 2026-08-17 00:00 = UTC 2026-08-16 16:00 (真实账单反证)
        assertNull(PeakSplit.tierOf("2026-08-16T15:59:00Z", "deepseek-v4-flash"))
        assertEquals("off", PeakSplit.tierOf("2026-08-16T16:00:00Z", "deepseek-v4-flash"))
        // 同一条 8 月记录: v4-flash 已分档, v4.1-flash 仍在门外 (不能共用统一门)。
        // 2026-08-17 是周一, UTC 02:00 = 北京 10:00 → 高峰
        assertEquals("peak", PeakSplit.tierOf("2026-08-17T02:00:00Z", "deepseek-v4-flash"))
        assertNull(PeakSplit.tierOf("2026-08-17T02:00:00Z", "deepseek-v4.1-flash"))
    }

    // ── 模型匹配 ────────────────────────────────────────────────────────

    @Test
    fun providerPrefixedAndCaseInsensitiveModels() {
        assertEquals("peak", PeakSplit.tierOf("2026-10-27T02:00:00Z", "inf-go/deepseek-v4.1-flash"))
        assertEquals("peak", PeakSplit.tierOf("2026-10-27T02:00:00Z", "DeepSeek-V4.1-Flash"))
        assertTrue(PeakSplit.isSplitModel("DeepSeek-V4-Flash"))
        assertTrue(PeakSplit.isSplitModel("opencode/deepseek-v4.1-flash"))
    }

    @Test
    fun nonWhitelistedModelsAreNotSplit() {
        // 未经验证的实验变体/其它模型一律不分档 (宽匹配会把它们也拆开)
        assertNull(PeakSplit.tierOf("2026-10-27T02:00:00Z", "deepseek-chat"))
        assertNull(PeakSplit.tierOf("2026-10-27T02:00:00Z", "deepseek-v4-flash-vision-exp"))
        assertNull(PeakSplit.tierOf("2026-10-27T02:00:00Z", "glm-4.5"))
        assertFalse(PeakSplit.isSplitModel("deepseek-v4-flash-vision-exp"))
    }

    // ── 标签 ────────────────────────────────────────────────────────────

    @Test
    fun labelsUseDesktopSuffixes() {
        assertEquals("deepseek-v4.1-flash 峰", PeakSplit.labelFor("deepseek-v4.1-flash", "peak"))
        assertEquals("deepseek-v4.1-flash 谷", PeakSplit.labelFor("deepseek-v4.1-flash", "off"))
        assertEquals("glm-4.5", PeakSplit.labelFor("glm-4.5", ""))
        assertEquals("glm-4.5", PeakSplit.labelFor("glm-4.5", null))
    }

    @Test
    fun stripSuffixRestoresModelForExclusion() {
        assertEquals("deepseek-v4.1-flash", PeakSplit.stripSuffix("deepseek-v4.1-flash 峰"))
        assertEquals("deepseek-v4.1-flash", PeakSplit.stripSuffix("deepseek-v4.1-flash 谷"))
        assertEquals("deepseek-v4.1-flash", PeakSplit.stripSuffix("  deepseek-v4.1-flash  "))
        assertEquals("deepseek-v4.1-flash", PeakSplit.stripSuffix("deepseek-v4.1-flash"))
        // 只剥后缀, 不误伤模型名本身的空格/单词
        assertEquals("model 峰", PeakSplit.stripSuffix("model 峰 峰"))
    }

    // ── SQL 片段 ────────────────────────────────────────────────────────

    @Test
    fun sqlFragmentsStayComplementary() {
        assertTrue(PeakSplit.flashSql.contains("COLLATE NOCASE"))
        assertTrue(PeakSplit.flashSql.contains("LIKE '%/"))
        assertTrue(PeakSplit.baseSql.startsWith("NOT "))
        // 两个分支必须互补: 并集覆盖全表, 交集为空 (两段式查询的前提)
        assertEquals("NOT ${PeakSplit.flashSql}", PeakSplit.baseSql)
    }

    @Test
    fun tierSqlBindsOneHolidayParamPerDay() {
        val (expr, holidays) = PeakSplit.tierSql("created_at")
        assertEquals(PeakSplit.CN_HOLIDAYS.size, holidays.size)
        assertEquals(PeakSplit.CN_HOLIDAYS.sorted(), holidays)
        // 节假日占位符只出现一次 (CASE 归约写法), 否则参数个数会对不上
        assertEquals(holidays.size, expr.split("?").size - 1)
        assertTrue(expr.contains("strftime('%w', created_at) BETWEEN '1' AND '5'"))
        assertTrue(expr.contains("'01', '02', '03', '06', '07', '08', '09'"))
        // 每个模型一个起始门
        PeakSplit.PRICING_GATES.forEach { (model, gate) ->
            assertTrue(expr.contains(PeakSplit.modelMatchSql("model", model)))
            assertTrue(expr.contains(gate.first) && expr.contains(gate.second))
        }
    }

    @Test
    fun tierSqlGroupsByOutputAlias() {
        // tier 表达式只能出现一次 (SELECT 列表), 分组用输出别名 —— 写两遍会让
        // 节假日占位符翻倍, 绑定参数个数对不上 (实测 SQLite 报 68 vs 35)
        val (expr, holidays) = PeakSplit.tierSql("created_at")
        assertEquals(holidays.size, expr.split("?").size - 1)
        // 展示名在 Kotlin 侧拼 (labelFor), SQL 只输出原始 model + tier 列
        assertEquals("deepseek-v4.1-flash 峰", PeakSplit.labelFor("deepseek-v4.1-flash", "peak"))
        assertEquals("deepseek-v4.1-flash 谷", PeakSplit.labelFor("deepseek-v4.1-flash", "off"))
    }

    @Test
    fun parsesBothUtcAndSqliteTimestampForms() {
        // created_at 为 ISO (...Z), time_bucket 为 "yyyy-MM-dd HH:mm:ss" —— SQL 两者都吃
        assertEquals(
            PeakSplit.tierOf("2026-10-27T02:00:00Z", "deepseek-v4.1-flash"),
            PeakSplit.tierOf("2026-10-27 02:00:00", "deepseek-v4.1-flash"),
        )
        assertEquals("peak", PeakSplit.tierOf("2026-10-27T02:00:00Z", "deepseek-v4.1-flash"))
        assertNull(PeakSplit.tierOf("", "deepseek-v4.1-flash"))
        assertNull(PeakSplit.tierOf("not-a-date", "deepseek-v4.1-flash"))
    }
}
