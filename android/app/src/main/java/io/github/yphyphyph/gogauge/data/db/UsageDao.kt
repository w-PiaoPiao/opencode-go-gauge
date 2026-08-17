package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Query
import androidx.room.RawQuery
import androidx.room.Transaction
import androidx.room.Upsert
import androidx.sqlite.db.SimpleSQLiteQuery
import androidx.sqlite.db.SupportSQLiteQuery
import io.github.yphyphyph.gogauge.data.model.DailyStat
import io.github.yphyphyph.gogauge.data.model.HourStat
import io.github.yphyphyph.gogauge.data.model.ModelStat
import io.github.yphyphyph.gogauge.data.model.SessionStat
import io.github.yphyphyph.gogauge.data.model.Totals
import io.github.yphyphyph.gogauge.data.model.UsageRecordRow

/**
 * Usage records DAO — every query is a direct port of desktop db.py SQL.
 */
@Dao
abstract class UsageDao {

    // ------------------------------------------------------------------
    // Write
    // ------------------------------------------------------------------

    @Query("SELECT usg_id FROM usage_records WHERE usg_id IN (:ids)")
    abstract suspend fun existingIds(ids: List<String>): List<String>

    @Upsert
    abstract suspend fun upsertAll(records: List<UsageRecordEntity>)

    /** Batch insert with dedup; returns count of newly inserted rows. */
    @Transaction
    open suspend fun insertUsageRecords(records: List<UsageRecordEntity>): Int {
        if (records.isEmpty()) return 0
        val existing = existingIds(records.map { it.usgId }).toHashSet()
        upsertAll(records)
        return records.count { it.usgId !in existing }
    }

    @Query("DELETE FROM usage_records WHERE datetime(created_at) < datetime('now', :intervalArg)")
    abstract suspend fun pruneOldRecords(intervalArg: String): Int

    @Query("DELETE FROM usage_records")
    abstract suspend fun deleteAll()

    // ------------------------------------------------------------------
    // Aggregations (desktop db.py ports)
    // ------------------------------------------------------------------

    /** Period where clause builder — mirrors db._PERIOD_CLAUSES + _period_where. */
    private fun periodWhere(period: String): Pair<String, Array<Any>> {
        val clause: String
        val args: Array<Any>
        when (period) {
            "5h" -> {
                clause = "datetime(created_at) >= datetime('now', '-5 hours')"
                args = emptyArray()
            }
            "today" -> {
                clause = "substr(datetime(created_at, 'localtime'), 1, 10) = date('now', 'localtime')"
                args = emptyArray()
            }
            "all" -> return "" to emptyArray()
            else -> {
                val days = Regex("^(\\d+)d$").find(period)?.groupValues?.get(1)?.toIntOrNull()?.coerceIn(1, 365) ?: 30
                clause = "datetime(created_at) >= datetime('now', ?)"
                args = arrayOf("-${days} days")
            }
        }
        return "WHERE $clause" to args
    }

    private fun totalsSql(where: String): String = """
        SELECT COALESCE(COUNT(*), 0) AS request_count,
               COALESCE(COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id END), 0) AS session_count,
               COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
               COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
               COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
               COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
               COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
               COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
               COALESCE(SUM(cost_usd), 0) AS total_cost_usd
        FROM usage_records
        $where
    """.trimIndent()

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun totalsRaw(query: SupportSQLiteQuery): TotalsRow

    suspend fun totals(period: String): Totals {
        val (where, args) = periodWhere(period)
        val row = totalsRaw(SimpleSQLiteQuery(totalsSql(where), args))
        val hit = row.cacheHitTokens
        val miss = row.uncachedInputTokens
        val hitRate = if (hit + miss > 0) hit.toDouble() / (hit + miss) * 100 else 0.0
        return Totals(
            requestCount = row.requestCount,
            sessionCount = row.sessionCount,
            totalInputTokens = row.totalInputTokens,
            uncachedInputTokens = miss,
            totalReasoningTokens = row.totalReasoningTokens,
            cacheHitTokens = hit,
            cacheWriteTokens = row.cacheWriteTokens,
            totalOutputTokens = row.totalOutputTokens,
            totalCostUsd = row.totalCostUsd,
            hitRate = Math.round(hitRate * 100) / 100.0,
        )
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun dailyStatsRaw(query: SupportSQLiteQuery): List<DailyStatRow>

    /** Daily aggregation — mirrors db.daily_stats. */
    suspend fun dailyStats(days: Int): List<DailyStat> {
        val clamped = days.coerceIn(1, 365)
        val rows = dailyStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT substr(datetime(created_at, 'localtime'), 1, 10) AS date,
                       COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
                       COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
                       COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
                       COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
                       COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
                       COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                       COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                       COALESCE(COUNT(*), 0) AS request_count
                FROM usage_records
                WHERE substr(datetime(created_at, 'localtime'), 1, 10) >= date('now', 'localtime', ?)
                GROUP BY substr(datetime(created_at, 'localtime'), 1, 10)
                ORDER BY date ASC
                """.trimIndent(),
                arrayOf("-${clamped} days"),
            )
        )
        return rows.map { r ->
            val hit = r.cacheHitTokens
            val miss = r.uncachedInputTokens
            val hitRate = if (hit + miss > 0) hit.toDouble() / (hit + miss) * 100 else 0.0
            DailyStat(
                date = r.date,
                totalInputTokens = r.totalInputTokens,
                uncachedInputTokens = miss,
                totalReasoningTokens = r.totalReasoningTokens,
                cacheHitTokens = hit,
                cacheWriteTokens = r.cacheWriteTokens,
                totalOutputTokens = r.totalOutputTokens,
                totalCostUsd = r.totalCostUsd,
                requestCount = r.requestCount,
                hitRate = Math.round(hitRate * 100) / 100.0,
            )
        }
    }

    @Query(
        """
        SELECT CAST(strftime('%H', datetime(created_at, 'localtime')) AS INTEGER) AS hour,
               COALESCE(SUM(input_tokens), 0) AS input,
               COALESCE(SUM(output_tokens), 0) AS output,
               COALESCE(SUM(reasoning_tokens), 0) AS reasoning
        FROM usage_records
        WHERE substr(datetime(created_at, 'localtime'), 1, 10) = date('now', 'localtime')
        GROUP BY hour
        """
    )
    abstract suspend fun todayTrendRaw(): List<HourTrendRow>

    /** Today 24-hour trend, zero-filled — mirrors db.today_trend. */
    suspend fun todayTrend(): List<HourStat> {
        val byHour = todayTrendRaw().associate { it.hour to it }
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

    /** Per-model aggregation — mirrors db.model_stats. */
    suspend fun modelStats(period: String): List<ModelStat> {
        val (where, args) = periodWhere(period)
        val rows = modelStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT model,
                       COALESCE(COUNT(*), 0) AS request_count,
                       COALESCE(COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id END), 0) AS session_count,
                       COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
                       COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
                       COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
                       COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
                       COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
                       COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                       COALESCE(SUM(cost_usd), 0) AS total_cost_usd
                FROM usage_records
                $where
                GROUP BY model
                ORDER BY (COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) + COALESCE(SUM(output_tokens), 0)) DESC
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
                sessionCount = r.sessionCount,
                totalInputTokens = r.totalInputTokens,
                uncachedInputTokens = miss,
                totalReasoningTokens = r.totalReasoningTokens,
                cacheHitTokens = hit,
                cacheWriteTokens = r.cacheWriteTokens,
                totalOutputTokens = r.totalOutputTokens,
                totalCostUsd = r.totalCostUsd,
                hitRate = Math.round(hitRate * 100) / 100.0,
            )
        }
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun modelStatsRaw(query: SupportSQLiteQuery): List<ModelStatRow>

    private val sessionKey =
        "CASE WHEN session_id IS NULL OR session_id = '' THEN '' ELSE session_id END"

    /** Session aggregation with paging — mirrors db.session_stats_page. */
    suspend fun sessionStatsPage(page: Int, pageSize: Int, days: Int?): Pair<List<SessionStat>, Int> {
        val whereParts = mutableListOf<String>()
        val params = mutableListOf<Any>()
        if (days != null) {
            whereParts.add("datetime(created_at) >= datetime('now', ?)")
            params.add("-${days.coerceIn(1, 365)} days")
        }
        val where = if (whereParts.isEmpty()) "" else "WHERE ${whereParts.joinToString(" AND ")}"

        val totalRow = totalRaw(
            SimpleSQLiteQuery(
                "SELECT COUNT(DISTINCT $sessionKey) AS count FROM usage_records $where",
                params.toTypedArray(),
            )
        )
        val total = totalRow.count

        val rows = sessionStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT $sessionKey AS session_id,
                       COALESCE(COUNT(*), 0) AS request_count,
                       COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
                       COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                       COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
                       COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                       MAX(created_at) AS last_at
                FROM usage_records $where
                GROUP BY $sessionKey
                ORDER BY last_at DESC
                LIMIT ? OFFSET ?
                """.trimIndent(),
                (params + listOf(pageSize, (page - 1) * pageSize)).toTypedArray(),
            )
        )
        val records = rows.map { r ->
            SessionStat(
                sessionId = r.sessionId,
                requestCount = r.requestCount,
                totalInputTokens = r.totalInputTokens,
                uncachedInputTokens = r.uncachedInputTokens,
                totalOutputTokens = r.totalOutputTokens,
                totalReasoningTokens = r.totalReasoningTokens,
                totalCostUsd = r.totalCostUsd,
                lastAt = r.lastAt,
            )
        }
        return records to total
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun sessionStatsRaw(query: SupportSQLiteQuery): List<SessionRow>

    /** Paginated usage records — mirrors db.usage_records_page. */
    suspend fun usageRecordsPage(page: Int, pageSize: Int, model: String?, days: Int?): Pair<List<UsageRecordRow>, Int> {
        val whereParts = mutableListOf<String>()
        val params = mutableListOf<Any>()
        if (model != null) {
            whereParts.add("model = ?")
            params.add(model)
        }
        if (days != null) {
            whereParts.add("datetime(created_at) >= datetime('now', ?)")
            params.add("-${days.coerceIn(1, 365)} days")
        }
        val where = if (whereParts.isEmpty()) "" else "WHERE ${whereParts.joinToString(" AND ")}"

        val totalRow = totalRaw(
            SimpleSQLiteQuery("SELECT COUNT(*) AS count FROM usage_records $where", params.toTypedArray())
        )
        val total = totalRow.count

        val rows = recordsRaw(
            SimpleSQLiteQuery(
                """
                SELECT * FROM usage_records $where ORDER BY created_at DESC LIMIT ? OFFSET ?
                """.trimIndent(),
                (params + listOf(pageSize, (page - 1) * pageSize)).toTypedArray(),
            )
        )
        val records = rows.map { r ->
            UsageRecordRow(
                usgId = r.usgId,
                createdAt = r.createdAt,
                model = r.model,
                provider = r.provider,
                inputTokens = r.inputTokens.toLong(),
                outputTokens = r.outputTokens.toLong(),
                reasoningTokens = r.reasoningTokens.toLong(),
                cacheReadTokens = r.cacheReadTokens.toLong(),
                cacheWriteTokens = (r.cacheWrite5mTokens ?: 0).toLong() + (r.cacheWrite1hTokens ?: 0).toLong(),
                costUsd = r.costUsd,
                sessionId = r.sessionId,
                plan = r.plan,
            )
        }
        return records to total
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun recordsRaw(query: SupportSQLiteQuery): List<UsageRecordEntity>

    @RawQuery
    abstract suspend fun totalRaw(query: SupportSQLiteQuery): CountRow

    @Query("SELECT DISTINCT model FROM usage_records ORDER BY model")
    abstract suspend fun listModels(): List<String>

    @Query("SELECT COUNT(*) AS count, MIN(created_at) AS oldest, MAX(created_at) AS newest FROM usage_records")
    abstract suspend fun recordBounds(): BoundsRow

    // ------------------------------------------------------------------
    // Row projections
    // ------------------------------------------------------------------

    data class TotalsRow(
        @androidx.room.ColumnInfo(name = "request_count") val requestCount: Int,
        @androidx.room.ColumnInfo(name = "session_count") val sessionCount: Int,
        @androidx.room.ColumnInfo(name = "total_input_tokens") val totalInputTokens: Long,
        @androidx.room.ColumnInfo(name = "uncached_input_tokens") val uncachedInputTokens: Long,
        @androidx.room.ColumnInfo(name = "total_reasoning_tokens") val totalReasoningTokens: Long,
        @androidx.room.ColumnInfo(name = "cache_hit_tokens") val cacheHitTokens: Long,
        @androidx.room.ColumnInfo(name = "cache_write_tokens") val cacheWriteTokens: Long,
        @androidx.room.ColumnInfo(name = "total_output_tokens") val totalOutputTokens: Long,
        @androidx.room.ColumnInfo(name = "total_cost_usd") val totalCostUsd: Double,
    )

    data class DailyStatRow(
        val date: String,
        @androidx.room.ColumnInfo(name = "total_input_tokens") val totalInputTokens: Long,
        @androidx.room.ColumnInfo(name = "uncached_input_tokens") val uncachedInputTokens: Long,
        @androidx.room.ColumnInfo(name = "total_reasoning_tokens") val totalReasoningTokens: Long,
        @androidx.room.ColumnInfo(name = "cache_hit_tokens") val cacheHitTokens: Long,
        @androidx.room.ColumnInfo(name = "cache_write_tokens") val cacheWriteTokens: Long,
        @androidx.room.ColumnInfo(name = "total_output_tokens") val totalOutputTokens: Long,
        @androidx.room.ColumnInfo(name = "total_cost_usd") val totalCostUsd: Double,
        @androidx.room.ColumnInfo(name = "request_count") val requestCount: Int,
    )

    data class HourTrendRow(val hour: Int, val input: Long, val output: Long, val reasoning: Long)

    data class ModelStatRow(
        val model: String,
        @androidx.room.ColumnInfo(name = "request_count") val requestCount: Int,
        @androidx.room.ColumnInfo(name = "session_count") val sessionCount: Int,
        @androidx.room.ColumnInfo(name = "total_input_tokens") val totalInputTokens: Long,
        @androidx.room.ColumnInfo(name = "uncached_input_tokens") val uncachedInputTokens: Long,
        @androidx.room.ColumnInfo(name = "total_reasoning_tokens") val totalReasoningTokens: Long,
        @androidx.room.ColumnInfo(name = "cache_hit_tokens") val cacheHitTokens: Long,
        @androidx.room.ColumnInfo(name = "cache_write_tokens") val cacheWriteTokens: Long,
        @androidx.room.ColumnInfo(name = "total_output_tokens") val totalOutputTokens: Long,
        @androidx.room.ColumnInfo(name = "total_cost_usd") val totalCostUsd: Double,
    )

    data class SessionRow(
        @androidx.room.ColumnInfo(name = "session_id") val sessionId: String,
        @androidx.room.ColumnInfo(name = "request_count") val requestCount: Int,
        @androidx.room.ColumnInfo(name = "total_input_tokens") val totalInputTokens: Long,
        @androidx.room.ColumnInfo(name = "uncached_input_tokens") val uncachedInputTokens: Long,
        @androidx.room.ColumnInfo(name = "total_output_tokens") val totalOutputTokens: Long,
        @androidx.room.ColumnInfo(name = "total_reasoning_tokens") val totalReasoningTokens: Long,
        @androidx.room.ColumnInfo(name = "total_cost_usd") val totalCostUsd: Double,
        @androidx.room.ColumnInfo(name = "last_at") val lastAt: String,
    )

    data class CountRow(val count: Int)

    data class BoundsRow(val count: Int, val oldest: String?, val newest: String?)
}
