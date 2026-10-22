package io.github.yphyphyph.gogauge.data.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * 配额窗口打满预测 — 夹具与桌面 app/forecast.py 的语义逐条对齐
 * (v2.2.1a 精简版: 按窗口内平均速率外推, 缺周期边界宁可不显示)。
 */
class ForecastTest {

    private val fiveH = 5 * 3600.0

    @Test
    fun `fill when average rate exhausts before reset`() {
        // 5h 窗口已过 3h, 已用 80% → 按均值 0.75h 后耗尽 (< 剩余 2h)
        val fc = Forecast.windowForecast(used = 80.0, resetInSec = 2 * 3600, windowLen = fiveH)!!
        assertEquals("fill", fc.state)
        assertEquals(2700, fc.sec)
    }

    @Test
    fun `no fill when rate too slow`() {
        // 5h 窗口已过 3h 用 10%: 按均值到 5h 结束只用到 16.7% → 17%
        val fc = Forecast.windowForecast(used = 10.0, resetInSec = 2 * 3600, windowLen = fiveH)!!
        assertEquals("no_fill", fc.state)
        assertEquals(17, fc.pct)
    }

    @Test
    fun `zero usage never fills`() {
        val fc = Forecast.windowForecast(0.0, 2 * 3600, fiveH)!!
        assertEquals("no_fill", fc.state)
        assertEquals(0, fc.pct)
    }

    @Test
    fun `no fill projects usage at reset`() {
        // 月窗口 30 天, 已过 13 天用 42%: 42 × 30 ÷ 13 ≈ 96.9% → 97% (与桌面 forecast.py 同口径)
        val month = 30 * 86400.0
        val elapsed = 13 * 86400.0
        val fc = Forecast.windowForecast(
            used = 42.0, resetInSec = (month - elapsed).toInt(), windowLen = month,
        )!!
        assertEquals("no_fill", fc.state)
        assertEquals(97, fc.pct)
    }

    @Test
    fun `no fill pct rounds half up and caps at 99`() {
        // 32.5 × 18000 ÷ 6000 = 97.5% → 98 (四舍五入)
        val half = Forecast.windowForecast(used = 32.5, resetInSec = 12000, windowLen = fiveH)!!
        assertEquals("no_fill", half.state)
        assertEquals(98, half.pct)
        // 边界: 耗尽时刻恰等于重置 (预测 100%) —— 封顶 99, 避免「不会打满（100%）」
        val edge = Forecast.windowForecast(used = 50.0, resetInSec = 1000, windowLen = 2000.0)!!
        assertEquals("no_fill", edge.state)
        assertEquals(99, edge.pct)
    }

    @Test
    fun `no prediction when already full or sample too short`() {
        // 已打满: 无预测可言
        assertNull(Forecast.windowForecast(100.0, 2 * 3600, fiveH))
        // 已过 1 分钟 (< 5h 的 1% = 3 分钟): 窗口刚重置的突发用量会放大噪声
        assertNull(Forecast.windowForecast(5.0, (5 * 3600 - 60), fiveH))
        // 缺窗口长度 (月窗口无周期边界)
        assertNull(Forecast.windowForecast(50.0, 3600, null))
    }

    @Test
    fun `window length by label`() {
        assertEquals(5 * 3600.0, Forecast.windowLenSec("5h Rolling", null, null)!!, 0.001)
        assertEquals(7 * 86400.0, Forecast.windowLenSec("Weekly", null, null)!!, 0.001)
        // 月窗口取订阅周期起止 (2026-09-26 → 2026-10-26 = 30 天)
        assertEquals(
            30 * 86400.0,
            Forecast.windowLenSec("Monthly", "2026-09-26T12:06:25Z", "2026-10-26T12:06:25Z")!!,
            0.001,
        )
        assertNull(Forecast.windowLenSec("Monthly", null, null))
        assertNull(Forecast.windowLenSec("Monthly", "2026-09-26T12:06:25Z", "2026-09-26T12:06:25Z"))
    }

    @Test
    fun `for window skips idle and predicts active`() {
        // 无重置时间 = 窗口未开始 (5h 空闲, 接口不给 resetsAt): resetInSec 为 0,
        // 硬算会把整窗当已过样本得出「不会打满」—— 直接不出预测 (desktop parity)
        val idle = QuotaWindow("5h Rolling", used = 0.0, remaining = 100.0, total = 100.0, unit = "%", resetAt = "", resetInSec = 0)
        assertNull(Forecast.forWindow(idle, null, null))
        val active = QuotaWindow(
            "5h Rolling", used = 80.0, remaining = 20.0, total = 100.0, unit = "%",
            resetAt = "2026-09-26T17:27:01.804Z", resetInSec = 2 * 3600,
        )
        assertEquals("fill", Forecast.forWindow(active, null, null)!!.state)
    }
}
