package io.github.yphyphyph.gogauge.data.model

import io.github.yphyphyph.gogauge.util.parseIsoInstant
import kotlin.math.ceil

/** 窗口打满预测结果 — mirrors app/forecast.py window_forecast 返回值. */
data class WindowForecast(
    val state: String,   // "fill" | "no_fill"
    val sec: Int = 0,    // state="fill": 预计 N 秒后耗尽
)

/**
 * 配额窗口打满预测 (纯函数) — port of app/forecast.py (desktop 2026-10-14 精简版).
 *
 * 口径: 按窗口内自身的平均消耗速率外推 (已用 % ÷ 已过时间). used 与 resetInSec
 * 取自同一份配额快照, 因此预测与界面上「重置于 X」始终同源可比; 不依赖历史账单
 * 或金额换算 —— 各窗口独立自洽, 缺周期边界时宁可不显示.
 */
object Forecast {
    private const val LABEL_ROLLING = "5h Rolling"
    private const val LABEL_WEEKLY = "Weekly"
    private const val LABEL_MONTHLY = "Monthly"

    private const val FIVE_HOUR_SEC = 5 * 3600.0
    private const val WEEK_SEC = 7 * 86400.0

    /** 已过时间不足窗口长度的 1% 时不预测: 窗口刚重置的突发用量会放大噪声 */
    private const val MIN_SAMPLE_RATIO = 0.01

    /** 窗口总时长 (秒). 5h/周为固定长度; 月窗口取订阅周期起止, 缺边界则 null. */
    fun windowLenSec(label: String, periodStart: String?, periodEnd: String?): Double? = when (label) {
        LABEL_ROLLING -> FIVE_HOUR_SEC
        LABEL_WEEKLY -> WEEK_SEC
        LABEL_MONTHLY -> {
            val start = parseIsoInstant(periodStart.orEmpty())?.toEpochMilli()
            val end = parseIsoInstant(periodEnd.orEmpty())?.toEpochMilli()
            if (start != null && end != null && end > start) (end - start) / 1000.0 else null
        }
        else -> null
    }

    /**
     * 按窗口内平均速率判断能否在重置前打满.
     *
     * fill — 预计 [WindowForecast.sec] 秒后耗尽, 早于重置;
     * no_fill — 按当前速率重置前用不完;
     * null — 无法预测 (样本不足 / 已打满 / 缺窗口长度).
     */
    fun windowForecast(used: Double, resetInSec: Int, windowLen: Double?): WindowForecast? {
        if (windowLen == null || windowLen <= 0) return null
        if (used >= 100.0) return null  // 已打满, 无预测可言
        val reset = maxOf(0.0, resetInSec.toDouble())
        val elapsed = windowLen - reset
        if (elapsed < windowLen * MIN_SAMPLE_RATIO) return null  // 样本不足 (含 reset 越过窗口长度的脏数据)
        if (used <= 0.0) return WindowForecast("no_fill")  // 零消耗: 重置前用不完
        val exhaust = (100.0 - used) * elapsed / used
        return if (exhaust < reset) WindowForecast("fill", ceil(exhaust).toInt())
        else WindowForecast("no_fill")
    }

    /**
     * 一个窗口 + 所属配额的周期边界 → 预测.
     *
     * 无重置时间 = 窗口未开始 (见 QuotaParser.parseGoStatus): 没有已过时间, 速率
     * 外推无从谈起 —— resetInSec 此时为 0, 硬算会把整窗当已过样本得出「不会打满」
     * (desktop server._attach_forecast 的 reset_at 空则不出预测 parity).
     */
    fun forWindow(w: QuotaWindow, periodStart: String?, periodEnd: String?): WindowForecast? {
        if (w.resetAt.isBlank()) return null
        return windowForecast(w.used, w.resetInSec, windowLenSec(w.label, periodStart, periodEnd))
    }
}
