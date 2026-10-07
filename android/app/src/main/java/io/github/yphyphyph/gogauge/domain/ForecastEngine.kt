package io.github.yphyphyph.gogauge.domain

import kotlin.math.ceil

/**
 * Burn-rate 用量预测引擎 — 纯函数, 无 Android 依赖 (JVM 单测直跑)。
 *
 * 两种月度口径的统一:
 * - GOAT (commandcode): 月剩余金额直读 (月池 × 剩余%), 5h/weekly 窗口带真实 cap ($);
 * - opencode: 窗口只有百分比 → 用「本周期已耗 $ ÷ 已用 %」换算每 1% 单价,
 *   再推出各窗口剩余金额。已用 <1% 时除数过小噪声放大, 该路径放弃 (结果置 null)。
 *
 * 输出各字段独立可空: 缺输入只影响对应项, 不拖垮整份预测。
 */
object ForecastEngine {

    /** 单日消耗 (date "yyyy-MM-dd", 本地日口径)。 */
    data class DayCost(val date: String, val costUsd: Double)

    /** 预测输入 — repository 从 Room 聚合与配额结果组装。 */
    data class Input(
        /** 近 N 天逐日消耗 (升序, 无记录的天补 0)。 */
        val dailyCosts: List<DayCost>,
        /** 当前计费周期起止 (epoch ms); opencode 无周期接口, start 为 null (回退 30 天)。 */
        val periodStartMs: Long?,
        val periodEndMs: Long?,
        /** 月度窗口已用/剩余 %。 */
        val monthUsedPercent: Double?,
        val monthRemainingPercent: Double?,
        /** GOAT 月剩余金额 ($); opencode 为 null (走 % 换算)。 */
        val monthRemainingAmount: Double?,
        /** GOAT 5h / weekly 窗口 cap ($); opencode 为 null。 */
        val fiveHourCapAmount: Double?,
        val weekCapAmount: Double?,
        /** 5h / weekly 窗口已用 %。 */
        val fiveHourUsedPercent: Double?,
        val weekUsedPercent: Double?,
        /** 本计费周期已耗 $ (本地明细聚合)。 */
        val periodCostUsd: Double,
        /** 近 2 小时已耗 $ (5h 窗口速率的样本)。 */
        val recent2hCost: Double,
    )

    /** 预测输出。 */
    data class Forecast(
        /** 月度剩余额度 ($) — GOAT 直读; opencode 为换算值。 */
        val monthRemainingUsd: Double?,
        /** 今日可用预算 ($) = 月剩余 ÷ 周期剩余天数 (周期终末半天内不输出)。 */
        val dailyBudgetUsd: Double?,
        /** 月度额度按日均耗还能用几天 (可小数, 日期换算由 UI 做)。 */
        val monthDaysLeft: Double?,
        /** 预计整个周期总耗 $ (日均耗 × 周期天数)。 */
        val projectedPeriodCostUsd: Double?,
        /** 5h 窗口按近 2h 速率预计多少分钟后打满 (>300 即到重置也打不满, UI 判断)。 */
        val fiveHourExhaustInMin: Long?,
        /** 周窗口剩余额度按日均耗还能用几天。 */
        val weekDaysLeft: Double?,
        /** true = 近期有效消耗日 <2, 天数类预测为粗略外推 (UI 提示"数据积累中")。 */
        val degraded: Boolean,
    )

    /** 参与日均耗统计的天数窗口。 */
    private const val AVG_WINDOW_DAYS = 14
    /** % 换算的最小已用比例: 低于此值除数噪声放大, 放弃换算。 */
    private const val MIN_USED_PERCENT_FOR_RATE = 1.0

    fun forecast(input: Input, nowMs: Long = System.currentTimeMillis()): Forecast {
        val days = input.dailyCosts.takeLast(AVG_WINDOW_DAYS)
        val nonZeroDays = days.count { it.costUsd > 0.0 }
        val avgDaily = if (days.isNotEmpty()) days.sumOf { it.costUsd } / days.size else 0.0
        val degraded = nonZeroDays < 2

        // ---- 每 1% 窗口单价 (opencode 换算路径) ----
        val usdPerPercent = input.monthUsedPercent
            ?.takeIf { it >= MIN_USED_PERCENT_FOR_RATE && input.periodCostUsd > 0.0 }
            ?.let { input.periodCostUsd / it }

        // ---- 月度剩余 $: GOAT 直读, opencode 换算 ----
        val monthRemainingUsd = input.monthRemainingAmount
            ?: usdPerPercent?.let { upp ->
                input.monthRemainingPercent?.let { rem -> upp * rem }
            }

        // ---- 月度还能用几天 ----
        val monthDaysLeft = monthRemainingUsd
            ?.takeIf { avgDaily > 0.0 }
            ?.let { it / avgDaily }

        // ---- 今日预算: 月剩余 ÷ 周期剩余天数 ----
        val dailyBudgetUsd = monthRemainingUsd?.let { rem ->
            input.periodEndMs?.let { end ->
                val daysLeft = (end - nowMs) / 86_400_000.0
                // 终末半天内重置临近, 除数过小会让预算虚高, 不输出
                if (daysLeft >= 0.5) rem / daysLeft else null
            }
        }

        // ---- 预计整周期总耗 ----
        val projectedPeriodCost = avgDaily.takeIf { it > 0.0 }?.let { avg ->
            val spanDays = if (input.periodStartMs != null && input.periodEndMs != null && input.periodEndMs > input.periodStartMs) {
                (input.periodEndMs - input.periodStartMs) / 86_400_000.0
            } else {
                30.0 // opencode 30 天滚动周期 (MonthlyCycle.PERIOD_DAYS parity)
            }
            avg * spanDays
        }

        // ---- 5h 窗口打满预测: 剩余金额 ÷ 近 2h 速率 ----
        val fiveHourRemainingUsd = input.fiveHourCapAmount
            ?.let { cap -> cap * (100.0 - (input.fiveHourUsedPercent ?: 0.0)) / 100.0 }
            ?: usdPerPercent?.let { upp ->
                input.fiveHourUsedPercent?.let { used -> upp * (100.0 - used) }
            }
        val fiveHourExhaustInMin = fiveHourRemainingUsd
            ?.takeIf { it > 0.0 && input.recent2hCost > 0.0 }
            ?.let { rem -> ceil(rem / (input.recent2hCost / 2.0) * 60.0).toLong() }

        // ---- 周窗口还能用几天 ----
        val weekRemainingUsd = input.weekCapAmount
            ?.let { cap -> cap * (100.0 - (input.weekUsedPercent ?: 0.0)) / 100.0 }
            ?: usdPerPercent?.let { upp ->
                input.weekUsedPercent?.let { used -> upp * (100.0 - used) }
            }
        val weekDaysLeft = weekRemainingUsd
            ?.takeIf { avgDaily > 0.0 }
            ?.let { it / avgDaily }

        return Forecast(
            monthRemainingUsd = monthRemainingUsd,
            dailyBudgetUsd = dailyBudgetUsd,
            monthDaysLeft = monthDaysLeft,
            projectedPeriodCostUsd = projectedPeriodCost,
            fiveHourExhaustInMin = fiveHourExhaustInMin,
            weekDaysLeft = weekDaysLeft,
            degraded = degraded,
        )
    }
}
