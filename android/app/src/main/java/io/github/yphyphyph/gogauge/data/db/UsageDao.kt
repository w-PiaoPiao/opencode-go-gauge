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
 * Usage records DAO — every query is a direct port of desktop db.py SQL,
 * v2.0.0 起全部按 account_id 维度过滤 (desktop parity).
 */
@Dao
abstract class UsageDao {

    // ------------------------------------------------------------------
    // Write
    // ------------------------------------------------------------------

    data class OwnershipRow(
        @androidx.room.ColumnInfo(name = "usg_id") val usgId: String,
        @androidx.room.ColumnInfo(name = "account_id") val accountId: Int,
    )

    /**
     * 查重按 (account_id, usg_id) 组合: usg_id 只是 provider 侧 id, 不同账号空间
     * 可能重叠 —— 复合主键下同号 id 在不同账号是两行独立记录 (桌面迁移 8 parity).
     */
    @Query("SELECT usg_id, account_id FROM usage_records WHERE usg_id IN (:ids)")
    abstract suspend fun existingOwnership(ids: List<String>): List<OwnershipRow>

    @Upsert
    abstract suspend fun upsertAll(records: List<UsageRecordEntity>)

    /**
     * Batch insert with dedup; returns count of newly inserted rows.
     * 逐行按记录自身 accountId 归属 (desktop insert_usage_records parity: 记录带
     * account_id 字段时逐行归属, 备份导入按行 remap); 账号内同号已存在则 upsert 更新,
     * 跨账号同号 id 互不影响. 已存在的 (账号内同号) 记录保留原归属账号
     * (desktop ON CONFLICT DO UPDATE 不更新 account_id).
     */
    @Transaction
    open suspend fun insertUsageRecords(records: List<UsageRecordEntity>, accountId: Int): Int {
        if (records.isEmpty()) return 0
        // Map<usg_id, 拥有该 id 的账号集合>: 同号 id 可被多个账号各自持有;
        // 新增数 = 不在自己的目标账号中已存在的行数 (以每行自己的归属为准)
        val ownership = HashMap<String, MutableSet<Int>>()
        for (chunk in records.map { it.usgId }.distinct().chunked(500)) {
            existingOwnership(chunk).forEach { row ->
                ownership.getOrPut(row.usgId) { mutableSetOf() }.add(row.accountId)
            }
        }
        upsertAll(records)
        return records.count { r -> r.accountId !in (ownership[r.usgId] ?: emptySet()) }
    }

    @Query(
        "DELETE FROM usage_records WHERE account_id = :accountId" +
            " AND local_date < date('now', 'localtime', :intervalArg)"
    )
    abstract suspend fun pruneOldRecords(intervalArg: String, accountId: Int): Int

    // ------------------------------------------------------------------
    // 「按同步范围清理」显式入口 (desktop db.prune_preview / prune_expired parity):
    // 同步不再自动删数据, 这里是唯一的删除入口, 由设置页按钮触发 (二次确认).
    // ------------------------------------------------------------------

    /** 过期判定的日历日边界 (local_date 早于它即过期)。 */
    @Query("SELECT date('now', 'localtime', :intervalArg) AS cutoff")
    abstract suspend fun pruneCutoff(intervalArg: String): String

    /** 待删条数预演 (跨账号, 不写库)。 */
    @Query(
        "SELECT COUNT(*) FROM usage_records" +
            " WHERE local_date IS NOT NULL AND local_date < :cutoff"
    )
    abstract suspend fun prunePreviewCount(cutoff: String): Int

    /** 按边界删除**所有账号**的过期记录, 返回删除条数 (删除不可恢复). */
    @Query(
        "DELETE FROM usage_records" +
            " WHERE local_date IS NOT NULL AND local_date < :cutoff"
    )
    abstract suspend fun pruneExpiredAll(cutoff: String): Int

    /**
     * 回填 local_date 为 NULL 的历史行 —— 旧版 Android (API ≤33) 上 Instant.parse
     * 拒绝 "+00:00" 导致 localDateOf 恒失败, 这些行在日期范围聚合里永远不命中。
     *
     * created_at 为 ISO8601 UTC ("...Z"), substr 取 "YYYY-MM-DDTHH:MM:SS" 这一 SQLite
     * 原生支持的格式 (不依赖 3.38+ 才有的 Z 后缀解析), 'localtime' 转本地日 ——
     * 与 Kotlin 侧 localDateOf 口径一致。幂等: 无 NULL 行时是无害空更新。
     */
    @Query(
        "UPDATE usage_records SET local_date = date(substr(created_at, 1, 19), 'localtime')" +
            " WHERE local_date IS NULL AND LENGTH(created_at) >= 19"
    )
    abstract suspend fun backfillNullLocalDates(): Int

    // ------------------------------------------------------------------
    // Aggregations (desktop db.py ports)
    // ------------------------------------------------------------------

    /**
     * Period where builder — mirrors db._PERIOD_CLAUSES + _period_where;
     * 返回不含 WHERE 前缀的条件与参数, 由调用方与 account_id 过滤组合.
     *
     * 周期过滤统一走 local_date 索引 (desktop 95d177c parity): datetime(created_at)
     * 包裹索引列会让每个周期查询退化为按账号全表扫; 秒级口径用两段式保留
     * (local_date 索引预收敛 + datetime 精筛).
     *
     * "month" = 「本月」, 按当前月度重置周期 (最近激活的 $10 付费期间) 筛选:
     * [cycleStart] 为周期起点 (UTC "yyyy-MM-dd HH:mm:ss", 由调用方从持久化的
     * 下次月度重置时间推算); 起点缺失 (配额从未拉到) 时回退滚动 30 天, 与 "30d" 口径一致.
     */
    private fun periodClause(period: String, cycleStart: String?): Pair<String?, Array<Any>> {
        val clause: String?
        val args: Array<Any>
        when (period) {
            "5h" -> {
                // 滚动 5 小时: local_date 先把行集收敛到昨/今两天 (索引范围扫, 行数少),
                // 再叠加 datetime() 保留精确的滚动窗口 (两段式)
                clause = "(local_date >= date('now', 'localtime', '-1 day')" +
                    " AND datetime(created_at) >= datetime('now', '-5 hours'))"
                args = emptyArray()
            }
            "today" -> {
                // local_date 为写入时物化的本地日 (见 MIGRATION_3_4): 原先
                // substr(datetime(...,'localtime')) 让索引失效, 退化为账号全表扫
                clause = "local_date = date('now', 'localtime')"
                args = emptyArray()
            }
            "month" -> if (cycleStart != null) {
                // 先以起点的本地日做索引收敛, 再用 datetime() 保留秒级精确口径
                clause = "local_date >= date(?, 'localtime') AND datetime(created_at) >= datetime(?)"
                args = arrayOf(cycleStart, cycleStart)
            } else {
                // 该账号尚未成功拉取过配额: 回退为滚动 30 天 (与 "30d" 日历口径一致)。
                // 恰好 30 个日历日 (今天-29 … 今天), 与 daily_stats 的 30 个点同源 (I10)
                clause = "local_date >= date('now', 'localtime', ?)"
                args = arrayOf("-${MonthlyCycle.PERIOD_DAYS - 1} days")
            }
            "all" -> return null to emptyArray()
            else -> {
                val days = Regex("^(\\d+)d$").find(period)?.groupValues?.get(1)?.toIntOrNull()?.coerceIn(1, 365) ?: 30
                // "7d"/"30d" 等: 日历日口径 (与 daily_stats/today_trend 一致), 走索引。
                // 恰好 days 个日历日 (今天-days+1 … 今天): 原先 "-N days" 含首尾共 N+1 天,
                // 与前端「N 日」文案/totals 的 N 个日历日不一致 (desktop I10 parity)
                clause = "local_date >= date('now', 'localtime', ?)"
                args = arrayOf("-${days - 1} days")
            }
        }
        return clause to args
    }

    /** 组合 WHERE: account 过滤恒在首位, 周期与排除条件以 AND 追加. */
    private fun buildWhere(
        period: String,
        accountId: Int,
        cycleStart: String? = null,
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

    /**
     * 「排除模型」SQL 片段 — mirrors db._exclude_clause (参数化 NOT IN, 模型名不拼进 SQL 文本).
     * 去空白去重后为空返回 null.
     *
     * 峰谷分档打开时统计页图例给出的是带「 峰 / 谷」后缀的名称; 排除是**模型级**动作
     * (总量/趋势无法按档拆), 这里先剥后缀还原真实模型名 —— 否则
     * `model NOT IN ('xxx 峰')` 一条也匹配不上, 点图例等于没反应 (desktop 同口径).
     */
    private fun excludeClause(excludeModels: Collection<String>): Pair<String?, List<String>> {
        val cleaned = excludeModels
            .map { PeakSplit.stripSuffix(it) }
            .filter { it.isNotEmpty() }
            .distinct()
        if (cleaned.isEmpty()) return null to emptyList()
        return "model NOT IN (${cleaned.joinToString(", ") { "?" }})" to cleaned
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

    /** TotalsRow -> Totals 的公共映射。 */
    private fun toTotals(row: TotalsRow): Totals {
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

    suspend fun totals(
        period: String,
        accountId: Int,
        cycleStart: String? = null,
        excludeModels: Collection<String> = emptyList(),
    ): Totals {
        val (where, args) = buildWhere(period, accountId, cycleStart, excludeModels)
        val row = totalsRaw(SimpleSQLiteQuery(totalsSql(where), args))
        return toTotals(row)
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun dailyStatsRaw(query: SupportSQLiteQuery): List<DailyStatRow>

    /** Daily aggregation — mirrors db.daily_stats (按账号, 支持排除模型). */
    suspend fun dailyStats(days: Int, accountId: Int, excludeModels: Collection<String> = emptyList()): List<DailyStat> {
        val clamped = days.coerceIn(1, 365)
        val (exClause, exArgs) = excludeClause(excludeModels)
        val exAnd = if (exClause != null) " AND $exClause" else ""
        val rows = dailyStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT local_date AS date,
                       COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
                       COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
                       COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
                       COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
                       COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
                       COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                       COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                       COALESCE(COUNT(*), 0) AS request_count
                FROM usage_records
                WHERE account_id = ? AND local_date >= date('now', 'localtime', ?)$exAnd
                GROUP BY local_date
                ORDER BY date ASC
                """.trimIndent(),
                (listOf<Any>(accountId, "-${clamped - 1} days") + exArgs).toTypedArray(),
            )
        )
        // 连续日期补 0 (desktop db.daily_stats parity): 无记录的天也占位,
        // 避免折线/柱状图 x 轴错位跳线。恰好 clamped 个日历日 (今天-clamped+1 … 今天),
        // 与「N 日」文案同源 (I10: 原先 clamped+1 个点, 多出最早一天)
        val byDate = rows.associateBy { it.date }
        val today = java.time.LocalDate.now()
        val out = ArrayList<DailyStat>(clamped)
        for (i in (clamped - 1) downTo 0) {
            val key = today.minusDays(i.toLong()).toString()
            val r = byDate[key]
            if (r == null) {
                out.add(
                    DailyStat(
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
            )
        }
        return out
    }

    @Query(
        """
        SELECT CAST(strftime('%H', datetime(created_at, 'localtime')) AS INTEGER) AS hour,
               COALESCE(SUM(input_tokens), 0) AS input,
               COALESCE(SUM(cache_read_tokens), 0) AS cache_read,
               COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write,
               COALESCE(SUM(output_tokens), 0) AS output,
               COALESCE(SUM(reasoning_tokens), 0) AS reasoning
        FROM usage_records
        WHERE account_id = :accountId
          AND local_date = date('now', 'localtime')
        GROUP BY hour
        """
    )
    abstract suspend fun todayTrendRaw(accountId: Int): List<HourTrendRow>

    /** Today 24-hour trend, zero-filled — mirrors db.today_trend (按账号). */
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
               COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS input,
               COALESCE(SUM(output_tokens), 0) AS output,
               COALESCE(SUM(cost_usd), 0) AS cost_usd
        FROM usage_records
        WHERE account_id = :accountId AND local_date >= date('now', 'localtime', :intervalArg)
        GROUP BY local_date, model
        """
    )
    abstract suspend fun modelDailyStatsRaw(accountId: Int, intervalArg: String): List<ModelDailyRow>

    /**
     * 近 N 天「日 × 模型」原始聚合 — mirrors db.model_daily_stats 聚合行 (desktop
     * /api/model_trend): input 含缓存读/写 (与环形图 input 口径一致); 连续日期补齐与
     * series 组装在 repository 层 (与 charts 源共用同一份组装逻辑).
     *
     * @param peakSplit 峰谷分档: 命中 DeepSeek flash 白名单的行按档位拆成
     *   「模型 峰」「模型 谷」两条序列 (desktop model_daily_stats peak_split parity)。
     */
    suspend fun modelDailyStatsRows(
        days: Int,
        accountId: Int,
        peakSplit: Boolean = false,
    ): List<ModelDailyRow> {
        val clamped = days.coerceIn(1, 365)
        // 恰好 N 个日历日 (今天-N+1 … 今天), 与「N 日」文案同源 (I10)
        val intervalArg = "-${clamped - 1} days"
        if (!peakSplit) return modelDailyStatsRaw(accountId, intervalArg)
        val consts = """
            COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS input,
            COALESCE(SUM(output_tokens), 0) AS output,
            COALESCE(SUM(cost_usd), 0) AS cost_usd
        """.trimIndent()
        val (tierExpr, holidays) = PeakSplit.tierSql("created_at")
        // 两段式 (P2-1): 基准分支不碰 tier 表达式; 仅分档模型求值后按 (model, tier) 分组。
        // GROUP BY 用输出别名 tier, 使表达式与节假日占位符只出现一次
        val base = modelDailyQuery(
            SimpleSQLiteQuery(
                """
                SELECT local_date AS date, model, '' AS tier, $consts
                FROM usage_records
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
                FROM usage_records
                WHERE account_id = ? AND local_date >= date('now', 'localtime', ?) AND ${PeakSplit.flashSql}
                GROUP BY local_date, model, tier
                """.trimIndent(),
                // tier 表达式占位符 (法定节假日) 在 SELECT 列表, 先于 WHERE 参数绑定
                (holidays + listOf<Any>(accountId, intervalArg)).toTypedArray(),
            )
        )
        return (base + split).map { it.copy(model = PeakSplit.labelFor(it.model, it.tier)) }
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun modelDailyQuery(query: SupportSQLiteQuery): List<ModelDailyRow>

    /** model_stats 的聚合列 (明细源; charts 源见 ChartDao.modelStats)。 */
    private val modelAggCols = """
        COALESCE(COUNT(*), 0) AS request_count,
                       COALESCE(COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id END), 0) AS session_count,
                       COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
                       COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
                       COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
                       COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
                       COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
                       COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                       COALESCE(SUM(cost_usd), 0) AS total_cost_usd
    """.trimIndent()

    /**
     * Per-model aggregation — mirrors db.model_stats (按账号).
     *
     * @param peakSplit 峰谷分档 (desktop v2.2.2): 命中 DeepSeek flash 白名单的行按档位
     *   拆成「模型 峰」「模型 谷」两条; 起始门之前的行与非分档模型保持整条。
     *   两段式查询 (P2-1): 非分档模型走基准聚合 (完全不求值 tier 表达式), 分档模型
     *   单独一段求值 —— 全量行上求 tier 会让聚合慢 2.6–12×。
     */
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
                    FROM usage_records
                    $where
                    GROUP BY model
                    ORDER BY (COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) + COALESCE(SUM(output_tokens), 0)) DESC
                    """.trimIndent(),
                    args,
                )
            )
            return rows.map { it.toModelStat() }
        }
        val (tierExpr, holidays) = PeakSplit.tierSql("created_at")
        // 1) 非分档模型: 基准聚合 (不求值 tier 表达式)
        val baseRows = modelStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT model, '' AS tier, $modelAggCols
                FROM usage_records
                $where AND ${PeakSplit.baseSql}
                GROUP BY model
                """.trimIndent(),
                args,
            )
        )
        // 2) 仅分档模型: 求值 tier 后按 (model, tier) 分组。GROUP BY 用**输出别名**
        //    tier —— 表达式只出现一次, 节假日占位符也只绑定一次 (写两遍会让参数个数翻倍)
        val tierRows = modelStatsRaw(
            SimpleSQLiteQuery(
                """
                SELECT model, $tierExpr AS tier, $modelAggCols
                FROM usage_records
                $where AND ${PeakSplit.flashSql}
                GROUP BY model, tier
                """.trimIndent(),
                // tier 表达式在 SELECT 列表, 其占位符 (法定节假日) 要先于 WHERE 参数绑定
                (holidays + args.toList()).toTypedArray(),
            )
        )
        // 与旧 SQL 的 ORDER BY (含缓存输入 + 输出) DESC 同口径; 并列时保持稳定次序
        return (baseRows + tierRows)
            .map { it.toModelStat() }
            .sortedByDescending { it.totalInputTokens + it.totalOutputTokens }
    }

    /** ModelStatRow -> ModelStat 的公共映射 (峰谷档位在后缀里体现)。 */
    private fun ModelStatRow.toModelStat(): ModelStat {
        val hit = cacheHitTokens
        val miss = uncachedInputTokens
        val hitRate = if (hit + miss > 0) hit.toDouble() / (hit + miss) * 100 else 0.0
        return ModelStat(
            model = PeakSplit.labelFor(model, tier),
            requestCount = requestCount,
            sessionCount = sessionCount,
            totalInputTokens = totalInputTokens,
            uncachedInputTokens = miss,
            totalReasoningTokens = totalReasoningTokens,
            cacheHitTokens = hit,
            cacheWriteTokens = cacheWriteTokens,
            totalOutputTokens = totalOutputTokens,
            totalCostUsd = totalCostUsd,
            hitRate = Math.round(hitRate * 100) / 100.0,
        )
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun modelStatsRaw(query: SupportSQLiteQuery): List<ModelStatRow>

    // 有 session 的行按 session 聚合; 无 session 的行按 key_id 拆分 (直接调 key /
    // 其他 agent 工具调用等来源一目了然); 兜底聚合为 "" 的"未归属"行 (desktop parity) —
    // mirrors db.py session_stats_page.
    private val sessionKey =
        "CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id " +
            "WHEN key_id IS NOT NULL AND key_id != '' THEN key_id ELSE '' END"

    /** Session aggregation with paging — mirrors db.session_stats_page (按账号). */
    suspend fun sessionStatsPage(page: Int, pageSize: Int, days: Int?, accountId: Int): Pair<List<SessionStat>, Int> {
        val whereParts = mutableListOf("account_id = ?")
        val params = mutableListOf<Any>(accountId)
        if (days != null) {
            // 日历日口径 + local_date 索引 (原先 datetime(created_at) 全表扫)
            whereParts.add("local_date >= date('now', 'localtime', ?)")
            params.add("-${days.coerceIn(1, 365)} days")
        }
        val where = "WHERE ${whereParts.joinToString(" AND ")}"

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
                       MAX(key_id) AS key_id,
                       COALESCE(COUNT(*), 0) AS request_count,
                       COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
                       COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                       COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
                       COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                       MAX(created_at) AS last_at
                FROM usage_records $where
                GROUP BY $sessionKey
                -- session_id 是分组键 (结果集内唯一), 并列 last_at 时由它构成全序:
                -- 只按 last_at 排序时分页在页边界可能重复/跳过 (desktop session_stats_page parity)
                ORDER BY last_at DESC, session_id ASC
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
                keyId = r.keyId,
            )
        }
        return records to total
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun sessionStatsRaw(query: SupportSQLiteQuery): List<SessionRow>

    /** Paginated usage records — mirrors db.usage_records_page (按账号). */
    suspend fun usageRecordsPage(page: Int, pageSize: Int, model: String?, days: Int?, accountId: Int): Pair<List<UsageRecordRow>, Int> {
        val whereParts = mutableListOf("account_id = ?")
        val params = mutableListOf<Any>(accountId)
        if (model != null) {
            whereParts.add("model = ?")
            params.add(model)
        }
        if (days != null) {
            // 日历日口径 + local_date 索引 (原先 datetime(created_at) 全表扫)
            whereParts.add("local_date >= date('now', 'localtime', ?)")
            params.add("-${days.coerceIn(1, 365)} days")
        }
        val where = "WHERE ${whereParts.joinToString(" AND ")}"

        val totalRow = totalRaw(
            SimpleSQLiteQuery("SELECT COUNT(*) AS count FROM usage_records $where", params.toTypedArray())
        )
        val total = totalRow.count

        val rows = recordsRaw(
            SimpleSQLiteQuery(
                """
                SELECT * FROM usage_records $where
                -- usg_id 次序键: created_at 不唯一 (毫秒精度 + 批量同步一次插多条),
                -- 页边界可能重复/跳过 (desktop usage_records_page parity)
                ORDER BY created_at DESC, usg_id DESC LIMIT ? OFFSET ?
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
                keyId = r.keyId,
            )
        }
        return records to total
    }

    @RawQuery(observedEntities = [UsageRecordEntity::class])
    abstract suspend fun recordsRaw(query: SupportSQLiteQuery): List<UsageRecordEntity>

    @RawQuery
    abstract suspend fun totalRaw(query: SupportSQLiteQuery): CountRow

    @Query("SELECT DISTINCT model FROM usage_records WHERE account_id = :accountId ORDER BY model")
    abstract suspend fun listModels(accountId: Int): List<String>

    // ------------------------------------------------------------------
    // Export (v2.2.0b — CSV/JSON 备份的分页遍历)
    // ------------------------------------------------------------------

    /**
     * 按时间升序分页导出 (BackupManager 流式写文件, 避免一次性载入全表)。
     *
     * [afterCreated]/[afterUsgId] 为 keyset 游标 (上一页末行的两个值): created_at
     * 不唯一 (毫秒精度 + 批量同步一次插多条), 只按它排序时 OFFSET 分页会漏行/重行,
     * 表现为备份静默丢记录 (desktop db.export_page parity); (created_at, usg_id)
     * 在单账号内是全序。传 null 保留首屏语义。
     */
    @Query(
        "SELECT * FROM usage_records WHERE account_id = :accountId" +
            " AND (:afterCreated IS NULL OR (created_at > :afterCreated" +
            " OR (created_at = :afterCreated AND usg_id > :afterUsgId)))" +
            " ORDER BY created_at ASC, usg_id ASC LIMIT :limit"
    )
    abstract suspend fun exportPage(
        accountId: Int,
        limit: Int,
        afterCreated: String?,
        afterUsgId: String?,
    ): List<UsageRecordEntity>

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

    /** 今日趋势聚合行 (v2.2.1a 起含 cache 两列, 供首页「含缓存」口径求和); charts 源共用. */
    data class HourTrendRow(
        val hour: Int,
        val input: Long,
        val output: Long,
        val reasoning: Long,
        @androidx.room.ColumnInfo(name = "cache_read") val cacheRead: Long = 0L,
        @androidx.room.ColumnInfo(name = "cache_write") val cacheWrite: Long = 0L,
    )

    /** 模型用量趋势聚合行 (日 × 模型, input 含缓存); charts 源共用. */
    data class ModelDailyRow(
        val date: String,
        val model: String,
        val input: Long,
        val output: Long,
        @androidx.room.ColumnInfo(name = "cost_usd") val costUsd: Double,
        /** 峰谷档位 ('peak'/'off'/''), 仅分档查询填充; 展示名由调用方拼后缀. */
        val tier: String = "",
    )

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
        /** 峰谷档位 ('peak'/'off'/''), 仅分档查询填充; 展示名由 [PeakSplit.labelFor] 拼后缀. */
        val tier: String = "",
    )

    data class SessionRow(
        @androidx.room.ColumnInfo(name = "session_id") val sessionId: String,
        @androidx.room.ColumnInfo(name = "key_id") val keyId: String? = null,
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
