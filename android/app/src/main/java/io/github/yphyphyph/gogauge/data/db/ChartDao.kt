package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.RawQuery
import androidx.sqlite.db.SimpleSQLiteQuery
import androidx.sqlite.db.SupportSQLiteQuery
import io.github.yphyphyph.gogauge.data.db.UsageDao.DailyStatRow
import io.github.yphyphyph.gogauge.data.model.HourStat
import io.github.yphyphyph.gogauge.data.model.ModelStat
import io.github.yphyphyph.gogauge.data.model.Totals

/**
 * usage_charts DAO — commandcode 全计费周期聚合 (desktop db.py `_charts_*` 系列 parity)。
 *
 * 口径要点: charts 的 tokens_in 已包含缓存读 (tokensTotal = tokensIn + tokensOut),
 * 因此 total_input = SUM(tokens_in) 而非叠加 cache_read; 会话数/推理 token
 * 服务端聚合无此维度, 恒为 0 (与桌面输出同形)。
 */
@Dao
abstract class ChartDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun upsertAll(rows: List<UsageChartEntity>)

    @Query("SELECT 1 FROM usage_charts WHERE account_id = :accountId LIMIT 1")
    abstract suspend fun chartsReady(accountId: Int): Int?

    @Query("SELECT COALESCE(SUM(requests), 0) AS reqs FROM usage_charts WHERE account_id = :accountId")
    abstract suspend fun chartsRequests(accountId: Int): Int

    // ------------------------------------------------------------------
    // 周期条件 (与 UsageDao.periodClause 口径一致: UTC 存储 + localtime 日界)
    //
    // "5h" 与「有真实周期起点的 month」用两段式: local_date 先把行集收敛到窗口附近
    // (走 idx_charts_account_localdate), 再叠加 datetime() 保留精确口径.
    // "Nd" 与「month 回退」只用 local_date (日历日口径) —— 与 UsageDao.periodClause /
    // dailyStats / modelDailyStats 完全同源. 这几张图按本地日分桶, 窗口必须整天对齐;
    // 原先此处只按 datetime(time_bucket) 精确 N×24h, 同一张 usage_charts 表上并存两套
    // 窗口, 总卡比趋势图少掉最早半天的数据 (desktop db._charts_period_where 同款遗留).
    // ------------------------------------------------------------------

    private fun periodClause(period: String, cycleStart: String?): Pair<String?, Array<Any>> {
        val clause: String?
        val args: Array<Any>
        when (period) {
            "5h" -> {
                clause = "local_date >= date('now', 'localtime', '-1 day')" +
                    " AND datetime(time_bucket) >= datetime('now', '-5 hours')"
                args = emptyArray()
            }
            "today" -> {
                // local_date 为写入时物化的本地日 (见 MIGRATION_3_4)
                clause = "local_date = date('now', 'localtime')"
                args = emptyArray()
            }
            "month" -> if (cycleStart != null) {
                clause = "local_date >= date(?, 'localtime')" +
                    " AND datetime(time_bucket) >= datetime(?)"
                args = arrayOf(cycleStart, cycleStart)
            } else {
                clause = "local_date >= date('now', 'localtime', ?)"
                args = arrayOf("-${MonthlyCycle.PERIOD_DAYS} days")
            }
            "all" -> return null to emptyArray()
            else -> {
                val days = Regex("^(\\d+)d$").find(period)?.groupValues?.get(1)?.toIntOrNull()?.coerceIn(1, 365) ?: 30
                // 恰好 days 个日历日 (今天-days+1 … 今天), 与 daily_stats/totals 同源 (I10)
                clause = "local_date >= date('now', 'localtime', ?)"
                args = arrayOf("-${days - 1} days")
            }
        }
        return clause to args
    }

    /**
     * 「排除模型」SQL 片段 — mirrors db._exclude_clause (参数化 NOT IN, 模型名不拼进 SQL 文本).
     * 去空白去重后为空返回 null.
     *
     * 峰谷分档打开时图例给的是带「 峰 / 谷」后缀的名称; 排除是模型级动作, 先剥后缀
     * 还原真实模型名, 否则 `model NOT IN ('xxx 峰')` 一条也匹配不上 (desktop 同口径).
     */
    private fun excludeClause(excludeModels: Collection<String>): Pair<String?, List<String>> {
        val cleaned = excludeModels
            .map { PeakSplit.stripSuffix(it) }
            .filter { it.isNotEmpty() }
            .distinct()
        if (cleaned.isEmpty()) return null to emptyList()
        return "model NOT IN (${cleaned.joinToString(", ") { "?" }})" to cleaned
    }

    private fun buildWhere(
        period: String,
        accountId: Int,
        cycleStart: String?,
        excludeModels: Collection<String> = emptyList(),
    ): Pair<String, Array<Any>> {
        val (clause, args) = periodClause(period, cycleStart)
        val parts = mutableListOf("account_id = ?")
        val params = mutableListOf<Any>(accountId)
        if (clause != null) {
            parts.add(clause)
            params.addAll(args)
        }
        val (exClause, exArgs) = excludeClause(excludeModels)
        if (exClause != null) {
            parts.add(exClause)
            params.addAll(exArgs)
        }
        return "WHERE ${parts.joinToString(" AND ")}" to params.toTypedArray()
    }

    // ------------------------------------------------------------------
    // 聚合查询 (输出列与 UsageDao 同形)
    // ------------------------------------------------------------------

    private fun totalsSql(where: String): String = """
        SELECT COALESCE(SUM(requests), 0) AS request_count,
               0 AS session_count,
               COALESCE(SUM(tokens_in), 0) AS total_input_tokens,
               COALESCE(SUM(tokens_in - cache_read_tokens), 0) AS uncached_input_tokens,
               0 AS total_reasoning_tokens,
               COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
               COALESCE(SUM(cache_creation_tokens), 0) AS cache_write_tokens,
               COALESCE(SUM(tokens_out), 0) AS total_output_tokens,
               COALESCE(SUM(total_cost), 0) AS total_cost_usd
        FROM usage_charts
        $where
    """.trimIndent()

    @RawQuery(observedEntities = [UsageChartEntity::class])
    abstract suspend fun totalsRaw(query: SupportSQLiteQuery): UsageDao.TotalsRow

    suspend fun totals(
        period: String,
        accountId: Int,
        cycleStart: String? = null,
        excludeModels: Collection<String> = emptyList(),
    ): Totals {
        val (where, args) = buildWhere(period, accountId, cycleStart, excludeModels)
        val row = totalsRaw(SimpleSQLiteQuery(totalsSql(where), args))
        val hit = row.cacheHitTokens
        val miss = row.uncachedInputTokens
        val hitRate = if (hit + miss > 0) hit.toDouble() / (hit + miss) * 100 else 0.0
        return Totals(
            requestCount = row.requestCount,
            sessionCount = 0,
            totalInputTokens = row.totalInputTokens,
            uncachedInputTokens = miss,
            totalReasoningTokens = 0,
            cacheHitTokens = hit,
            cacheWriteTokens = row.cacheWriteTokens,
            totalOutputTokens = row.totalOutputTokens,
            totalCostUsd = row.totalCostUsd,
            hitRate = Math.round(hitRate * 100) / 100.0,
        )
    }

    @RawQuery(observedEntities = [UsageChartEntity::class])
    abstract suspend fun modelStatsRaw(query: SupportSQLiteQuery): List<UsageDao.ModelStatRow>

    /** charts 源 model_stats 的聚合列。 */
    private val modelAggCols = """
        SUM(requests) AS request_count,
                       0 AS session_count,
                       SUM(tokens_in) AS total_input_tokens,
                       SUM(tokens_in - cache_read_tokens) AS uncached_input_tokens,
                       0 AS total_reasoning_tokens,
                       SUM(cache_read_tokens) AS cache_hit_tokens,
                       SUM(cache_creation_tokens) AS cache_write_tokens,
                       SUM(tokens_out) AS total_output_tokens,
                       SUM(total_cost) AS total_cost_usd
    """.trimIndent()

    suspend fun modelStats(
        period: String,
        accountId: Int,
        cycleStart: String? = null,
        peakSplit: Boolean = false,
    ): List<ModelStat> {
        val (where, args) = buildWhere(period, accountId, cycleStart)
        if (!peakSplit) {
            val rows = modelStatsRaw(
                SimpleSQLiteQuery(
                    """
                    SELECT model, '' AS tier, $modelAggCols
                    FROM usage_charts
                    $where
                    GROUP BY model
                    ORDER BY SUM(tokens_in + tokens_out) DESC
                    """.trimIndent(),
                    args,
                )
            )
            return rows.map { it.toModelStat() }
        }
        // 两段式 (P2-1) — 与 UsageDao.modelStats 同口径, 时间列换成 charts 的 time_bucket
        val (tierExpr, holidays) = PeakSplit.tierSql("time_bucket")
        val baseRows = modelStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT model, '' AS tier, $modelAggCols
                FROM usage_charts
                $where AND ${PeakSplit.baseSql}
                GROUP BY model
                """.trimIndent(),
                args,
            )
        )
        // GROUP BY 用输出别名 tier: tier 表达式与节假日占位符只出现一次
        val tierRows = modelStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT model, $tierExpr AS tier, $modelAggCols
                FROM usage_charts
                $where AND ${PeakSplit.flashSql}
                GROUP BY model, tier
                """.trimIndent(),
                (holidays + args.toList()).toTypedArray(),
            )
        )
        return (baseRows + tierRows)
            .map { it.toModelStat() }
            .sortedByDescending { it.totalInputTokens + it.totalOutputTokens }
    }

    /** charts 行的 ModelStat 映射 (会话数/推理 token 服务端聚合无此维度, 恒为 0)。 */
    private fun UsageDao.ModelStatRow.toModelStat(): ModelStat {
        val hit = cacheHitTokens
        val miss = uncachedInputTokens
        val hitRate = if (hit + miss > 0) hit.toDouble() / (hit + miss) * 100 else 0.0
        return ModelStat(
            model = PeakSplit.labelFor(model, tier),
            requestCount = requestCount,
            sessionCount = 0,
            totalInputTokens = totalInputTokens,
            uncachedInputTokens = miss,
            totalReasoningTokens = 0,
            cacheHitTokens = hit,
            cacheWriteTokens = cacheWriteTokens,
            totalOutputTokens = totalOutputTokens,
            totalCostUsd = totalCostUsd,
            hitRate = Math.round(hitRate * 100) / 100.0,
        )
    }

    @RawQuery(observedEntities = [UsageChartEntity::class])
    abstract suspend fun dailyStatsRaw(query: SupportSQLiteQuery): List<DailyStatRow>

    /** Daily aggregation from chart buckets — mirrors db.daily_stats charts 分支 (按账号, 支持排除). */
    suspend fun dailyStats(days: Int, accountId: Int, excludeModels: Collection<String> = emptyList()): List<io.github.yphyphyph.gogauge.data.model.DailyStat> {
        val clamped = days.coerceIn(1, 365)
        val (exClause, exArgs) = excludeClause(excludeModels)
        val exAnd = if (exClause != null) " AND $exClause" else ""
        val rows = dailyStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT local_date AS date,
                       SUM(tokens_in) AS total_input_tokens,
                       SUM(tokens_in - cache_read_tokens) AS uncached_input_tokens,
                       0 AS total_reasoning_tokens,
                       SUM(cache_read_tokens) AS cache_hit_tokens,
                       SUM(cache_creation_tokens) AS cache_write_tokens,
                       SUM(tokens_out) AS total_output_tokens,
                       SUM(total_cost) AS total_cost_usd,
                       SUM(requests) AS request_count
                FROM usage_charts
                WHERE account_id = ? AND local_date >= date('now', 'localtime', ?)$exAnd
                GROUP BY local_date
                ORDER BY date ASC
                """.trimIndent(),
                (listOf<Any>(accountId, "-${clamped - 1} days") + exArgs).toTypedArray(),
            )
        )
        // 连续日期补 0 (与 UsageDao.dailyStats 同口径), 恰好 clamped 个日历日 (I10)
        val byDate = rows.associateBy { it.date }
        val today = java.time.LocalDate.now()
        val out = ArrayList<io.github.yphyphyph.gogauge.data.model.DailyStat>(clamped)
        for (i in (clamped - 1) downTo 0) {
            val key = today.minusDays(i.toLong()).toString()
            val r = byDate[key]
            if (r == null) {
                out.add(
                    io.github.yphyphyph.gogauge.data.model.DailyStat(
                        date = key, totalInputTokens = 0, uncachedInputTokens = 0,
                        totalReasoningTokens = 0, cacheHitTokens = 0, cacheWriteTokens = 0,
                        totalOutputTokens = 0, totalCostUsd = 0.0, requestCount = 0, hitRate = 0.0,
                    )
                )
                continue
            }
            val hit = r.cacheHitTokens
            val miss = r.uncachedInputTokens
            val hitRate = if (hit + miss > 0) hit.toDouble() / (hit + miss) * 100 else 0.0
            out.add(
                io.github.yphyphyph.gogauge.data.model.DailyStat(
                    date = r.date,
                    totalInputTokens = r.totalInputTokens,
                    uncachedInputTokens = miss,
                    totalReasoningTokens = 0,
                    cacheHitTokens = hit,
                    cacheWriteTokens = r.cacheWriteTokens,
                    totalOutputTokens = r.totalOutputTokens,
                    totalCostUsd = r.totalCostUsd,
                    requestCount = r.requestCount,
                    hitRate = Math.round(hitRate * 100) / 100.0,
                )
            )
        }
        return out
    }

    @Query(
        """
        SELECT CAST(strftime('%H', datetime(time_bucket, 'localtime')) AS INTEGER) AS hour,
               COALESCE(SUM(tokens_in - cache_read_tokens), 0) AS input,
               COALESCE(SUM(cache_read_tokens), 0) AS cache_read,
               COALESCE(SUM(cache_creation_tokens), 0) AS cache_write,
               COALESCE(SUM(tokens_out), 0) AS output,
               0 AS reasoning
        FROM usage_charts
        WHERE account_id = :accountId
          AND local_date = date('now', 'localtime')
        GROUP BY hour
        """
    )
    abstract suspend fun todayTrendRaw(accountId: Int): List<UsageDao.HourTrendRow>

    /** Today 24-hour trend from chart buckets, zero-filled (desktop parity). */
    suspend fun todayTrend(accountId: Int): List<HourStat> {
        val byHour = todayTrendRaw(accountId).associate { it.hour to it }
        return (0 until 24).map { h ->
            val r = byHour[h]
            HourStat(
                hour = "%02d:00".format(h),
                input = r?.input ?: 0L,
                output = r?.output ?: 0L,
                reasoning = r?.reasoning ?: 0L,
                cacheRead = r?.cacheRead ?: 0L,
                cacheWrite = r?.cacheWrite ?: 0L,
            )
        }
    }

    @Query(
        """
        SELECT local_date AS date, model, '' AS tier,
               COALESCE(SUM(tokens_in), 0) AS input,
               COALESCE(SUM(tokens_out), 0) AS output,
               COALESCE(SUM(total_cost), 0) AS cost_usd
        FROM usage_charts
        WHERE account_id = :accountId AND local_date >= date('now', 'localtime', :intervalArg)
        GROUP BY local_date, model
        """
    )
    abstract suspend fun modelDailyStatsRaw(accountId: Int, intervalArg: String): List<UsageDao.ModelDailyRow>

    /** 近 N 天「日 × 模型」原始聚合 (charts 源; tokens_in 含缓存) — desktop model_daily_stats charts 分支 parity.
     *
     * @param peakSplit 峰谷分档: 命中 DeepSeek flash 白名单的桶按档位拆成两条序列。
     */
    suspend fun modelDailyStatsRows(
        days: Int,
        accountId: Int,
        peakSplit: Boolean = false,
    ): List<UsageDao.ModelDailyRow> {
        val clamped = days.coerceIn(1, 365)
        val intervalArg = "-${clamped - 1} days"
        if (!peakSplit) return modelDailyStatsRaw(accountId, intervalArg)
        val consts = """
            COALESCE(SUM(tokens_in), 0) AS input,
            COALESCE(SUM(tokens_out), 0) AS output,
            COALESCE(SUM(total_cost), 0) AS cost_usd
        """.trimIndent()
        val (tierExpr, holidays) = PeakSplit.tierSql("time_bucket")
        val base = modelDailyQuery(
            SimpleSQLiteQuery(
                """
                SELECT local_date AS date, model, '' AS tier, $consts
                FROM usage_charts
                WHERE account_id = ? AND local_date >= date('now', 'localtime', ?) AND ${PeakSplit.baseSql}
                GROUP BY local_date, model
                """.trimIndent(),
                arrayOf<Any>(accountId, intervalArg),
            )
        )
        val split = modelDailyQuery(
            SimpleSQLiteQuery(
                """
                SELECT local_date AS date, model, $tierExpr AS tier, $consts
                FROM usage_charts
                WHERE account_id = ? AND local_date >= date('now', 'localtime', ?) AND ${PeakSplit.flashSql}
                GROUP BY local_date, model, tier
                """.trimIndent(),
                (holidays + listOf<Any>(accountId, intervalArg)).toTypedArray(),
            )
        )
        return (base + split).map { it.copy(model = PeakSplit.labelFor(it.model, it.tier)) }
    }

    @RawQuery(observedEntities = [UsageChartEntity::class])
    abstract suspend fun modelDailyQuery(query: SupportSQLiteQuery): List<UsageDao.ModelDailyRow>

    @Query("SELECT DISTINCT model FROM usage_charts WHERE account_id = :accountId " +
        "UNION SELECT DISTINCT model FROM usage_records WHERE account_id = :accountId ORDER BY model")
    abstract suspend fun listModelsUnionRecords(accountId: Int): List<String>

    // ------------------------------------------------------------------
    // 「按同步范围清理」的聚合表侧 (desktop P2-7 parity)
    //
    // GOAT 账号统计主口径来自 usage_charts: 只删明细会让「已清理 N 条」之后
    // totals("all") 仍含历史, charts 也会跨计费周期无限累积.
    // ------------------------------------------------------------------

    /** 待删的过期聚合桶数 (与明细侧同一 local_date 边界, 不写库)。 */
    @Query(
        "SELECT COUNT(*) FROM usage_charts" +
            " WHERE local_date IS NOT NULL AND local_date < :cutoff"
    )
    abstract suspend fun prunePreviewCount(cutoff: String): Int

    /** 按边界删除**所有账号**的过期聚合桶, 返回删除条数 (删除不可恢复)。 */
    @Query(
        "DELETE FROM usage_charts" +
            " WHERE local_date IS NOT NULL AND local_date < :cutoff"
    )
    abstract suspend fun pruneExpiredAll(cutoff: String): Int
}
