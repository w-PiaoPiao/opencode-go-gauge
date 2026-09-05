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

    @Query("SELECT MAX(synced_at) AS at FROM usage_charts WHERE account_id = :accountId")
    abstract suspend fun chartsLastSynced(accountId: Int): String?

    // ------------------------------------------------------------------
    // 周期条件 (与 UsageDao.periodClause 口径一致: UTC 存储 + localtime 日界)
    // ------------------------------------------------------------------

    private fun periodClause(period: String, cycleStart: String?): Pair<String?, Array<Any>> {
        val clause: String?
        val args: Array<Any>
        when (period) {
            "5h" -> {
                clause = "datetime(time_bucket) >= datetime('now', '-5 hours')"
                args = emptyArray()
            }
            "today" -> {
                clause = "substr(datetime(time_bucket, 'localtime'), 1, 10) = date('now', 'localtime')"
                args = emptyArray()
            }
            "month" -> if (cycleStart != null) {
                clause = "datetime(time_bucket) >= datetime(?)"
                args = arrayOf(cycleStart)
            } else {
                clause = "datetime(time_bucket) >= datetime('now', ?)"
                args = arrayOf("-${MonthlyCycle.PERIOD_DAYS} days")
            }
            "all" -> return null to emptyArray()
            else -> {
                val days = Regex("^(\\d+)d$").find(period)?.groupValues?.get(1)?.toIntOrNull()?.coerceIn(1, 365) ?: 30
                clause = "datetime(time_bucket) >= datetime('now', ?)"
                args = arrayOf("-${days} days")
            }
        }
        return clause to args
    }

    private fun buildWhere(period: String, accountId: Int, cycleStart: String?): Pair<String, Array<Any>> {
        val (clause, args) = periodClause(period, cycleStart)
        val allArgs = listOf<Any>(accountId) + args.toList()
        return if (clause == null) {
            "WHERE account_id = ?" to arrayOf<Any>(accountId)
        } else {
            "WHERE account_id = ? AND $clause" to allArgs.toTypedArray()
        }
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

    suspend fun totals(period: String, accountId: Int, cycleStart: String? = null): Totals {
        val (where, args) = buildWhere(period, accountId, cycleStart)
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

    suspend fun modelStats(period: String, accountId: Int, cycleStart: String? = null): List<ModelStat> {
        val (where, args) = buildWhere(period, accountId, cycleStart)
        val rows = modelStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT model,
                       SUM(requests) AS request_count,
                       0 AS session_count,
                       SUM(tokens_in) AS total_input_tokens,
                       SUM(tokens_in - cache_read_tokens) AS uncached_input_tokens,
                       0 AS total_reasoning_tokens,
                       SUM(cache_read_tokens) AS cache_hit_tokens,
                       SUM(cache_creation_tokens) AS cache_write_tokens,
                       SUM(tokens_out) AS total_output_tokens,
                       SUM(total_cost) AS total_cost_usd
                FROM usage_charts
                $where
                GROUP BY model
                ORDER BY SUM(tokens_in + tokens_out) DESC
                """.trimIndent(),
                args,
            )
        )
        return rows.map { r ->
            val hit = r.cacheHitTokens
            val miss = r.uncachedInputTokens
            val hitRate = if (hit + miss > 0) hit.toDouble() / (hit + miss) * 100 else 0.0
            ModelStat(
                model = r.model,
                requestCount = r.requestCount,
                sessionCount = 0,
                totalInputTokens = r.totalInputTokens,
                uncachedInputTokens = miss,
                totalReasoningTokens = 0,
                cacheHitTokens = hit,
                cacheWriteTokens = r.cacheWriteTokens,
                totalOutputTokens = r.totalOutputTokens,
                totalCostUsd = r.totalCostUsd,
                hitRate = Math.round(hitRate * 100) / 100.0,
            )
        }
    }

    @RawQuery(observedEntities = [UsageChartEntity::class])
    abstract suspend fun dailyStatsRaw(query: SupportSQLiteQuery): List<DailyStatRow>

    /** Daily aggregation from chart buckets — mirrors db.daily_stats charts 分支 (按账号). */
    suspend fun dailyStats(days: Int, accountId: Int): List<io.github.yphyphyph.gogauge.data.model.DailyStat> {
        val clamped = days.coerceIn(1, 365)
        val rows = dailyStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT substr(datetime(time_bucket, 'localtime'), 1, 10) AS date,
                       SUM(tokens_in) AS total_input_tokens,
                       SUM(tokens_in - cache_read_tokens) AS uncached_input_tokens,
                       0 AS total_reasoning_tokens,
                       SUM(cache_read_tokens) AS cache_hit_tokens,
                       SUM(cache_creation_tokens) AS cache_write_tokens,
                       SUM(tokens_out) AS total_output_tokens,
                       SUM(total_cost) AS total_cost_usd,
                       SUM(requests) AS request_count
                FROM usage_charts
                WHERE account_id = ? AND substr(datetime(time_bucket, 'localtime'), 1, 10) >= date('now', 'localtime', ?)
                GROUP BY substr(datetime(time_bucket, 'localtime'), 1, 10)
                ORDER BY date ASC
                """.trimIndent(),
                arrayOf(accountId, "-${clamped} days"),
            )
        )
        // 连续日期补 0 (与 UsageDao.dailyStats 同口径)
        val byDate = rows.associateBy { it.date }
        val today = java.time.LocalDate.now()
        val out = ArrayList<io.github.yphyphyph.gogauge.data.model.DailyStat>(clamped + 1)
        for (i in clamped downTo 0) {
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
               SUM(tokens_in) AS input,
               SUM(tokens_out) AS output,
               0 AS reasoning
        FROM usage_charts
        WHERE account_id = :accountId
          AND substr(datetime(time_bucket, 'localtime'), 1, 10) = date('now', 'localtime')
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
            )
        }
    }

    @Query("SELECT DISTINCT model FROM usage_charts WHERE account_id = :accountId " +
        "UNION SELECT DISTINCT model FROM usage_records WHERE account_id = :accountId ORDER BY model")
    abstract suspend fun listModelsUnionRecords(accountId: Int): List<String>
}
