/**
 * usage_records DAO —— UsageDao.kt (android) 的 ArkTS 移植。
 * SQL 与 desktop db.py v2.0.0 逐句对应, 一律按 account_id 维度过滤。
 */
import { relationalStore } from '@kit.ArkData'
import { AppDb } from './AppDb'
import { RowReader } from './RowReader'
import { MonthlyCycle } from '../../common/util/MonthlyCycle'
import { DailyStat, HourStat, ModelStat, SessionStat, Totals, UsageRecordRow } from '../../common/model/Models'

export interface UsageRecordEntity {
  usgId: string
  createdAt: string
  model: string
  provider: string
  inputTokens: number
  outputTokens: number
  reasoningTokens: number
  cacheReadTokens: number
  cacheWrite5mTokens: number
  cacheWrite1hTokens: number
  costRaw: number
  costUsd: number
  keyId: string
  sessionId: string
  plan: string | null
  syncedAt: string
  accountId: number
}

interface BoundsRow {
  count: number
  oldest: string | null
  newest: string | null
}

export class UsageDao {
  private store(): relationalStore.RdbStore {
    return AppDb.store()
  }

  // ------------------------------------------------------------------
  // Write
  // ------------------------------------------------------------------

  private static placeholders(n: number): string {
    const parts: string[] = []
    for (let i = 0; i < n; i++) {
      parts.push('?')
    }
    return parts.join(',')
  }

  /** 单条多值 upsert 的列清单 (local_date 由 SQLite 末位从 created_at 派生)。 */
  private static readonly UPSERT_COLUMNS =
    'usg_id, created_at, model, provider, input_tokens, output_tokens, reasoning_tokens,' +
    ' cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens, cost_raw, cost_usd,' +
    ' key_id, session_id, plan, synced_at, account_id, local_date'

  /** 单行占位模板: 17 个绑定值 + 末位 created_at 绑定给 date(?, 'localtime')。 */
  private static readonly UPSERT_ROW_VALUES = `(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,date(?,'localtime'))`

  /**
   * 多值 VALUES 的分片行数: 18 个绑定值/行, 老版本 SQLite 的
   * SQLITE_MAX_VARIABLE_NUMBER 为 999 (40 行 = 720 个参数, 留足余量)。
   */
  private static readonly UPSERT_CHUNK_ROWS = 40

  /** 冲突时的更新列 —— 刻意不含 account_id (见 insertUsageRecords 注释)。 */
  private static readonly UPSERT_UPDATE_SET =
    `created_at=excluded.created_at, model=excluded.model, provider=excluded.provider,
     input_tokens=excluded.input_tokens, output_tokens=excluded.output_tokens,
     reasoning_tokens=excluded.reasoning_tokens, cache_read_tokens=excluded.cache_read_tokens,
     cache_write_5m_tokens=excluded.cache_write_5m_tokens,
     cache_write_1h_tokens=excluded.cache_write_1h_tokens,
     cost_raw=excluded.cost_raw, cost_usd=excluded.cost_usd, key_id=excluded.key_id,
     session_id=excluded.session_id, plan=excluded.plan, synced_at=excluded.synced_at,
     local_date=excluded.local_date`

  /**
   * 批量写入去重 (单条多值 upsert, 桌面 db.insert_usage_records parity);
   * 返回新增行数。
   *
   * 归属语义 = **保留首次归属**: DO UPDATE 列表中不得出现
   * `account_id = excluded.account_id` —— 桌面用转移语义, Android / HarmonyOS
   * 本次统一为保留首次归属 (增量同步有 1 小时重叠窗口, 转移语义会让同一批记录
   * 在两个账号之间来回抖动).
   *
   * 原先整批逐条 executeSql: 50 条记录 = 50 次 RDB 往返 + 1 次预检 SELECT;
   * 现在按分片拼多值 VALUES 一次执行, 计数语义不变 (批内重复 usg_id 只计首次)。
   */
  async insertUsageRecords(records: UsageRecordEntity[], accountId: number): Promise<number> {
    if (records.length === 0) {
      return 0
    }
    const store = this.store()
    // 批内去重: 只统计/写入唯一的 usg_id (与旧逐条实现的计数语义一致)
    const uniqueIds: string[] = []
    const seen: Map<string, boolean> = new Map()
    for (const r of records) {
      if (!seen.has(r.usgId)) {
        seen.set(r.usgId, true)
        uniqueIds.push(r.usgId)
      }
    }
    // 预检已存在行: 仅用于计数 (归属账号由冲突分支保留, 不参与写入)
    const existing: Map<string, boolean> = new Map()
    for (let i = 0; i < uniqueIds.length; i += 400) {
      const idChunk: string[] = uniqueIds.slice(i, i + 400)
      const rs = await store.querySql(
        `SELECT usg_id FROM usage_records WHERE usg_id IN (${UsageDao.placeholders(idChunk.length)})`,
        idChunk,
      )
      const reader = new RowReader(rs)
      while (reader.next()) {
        existing.set(reader.getStr('usg_id'), true)
      }
      reader.close()
    }
    let inserted = 0
    for (const id of uniqueIds) {
      if (!existing.has(id)) {
        inserted++
      }
    }

    store.beginTransaction()
    try {
      for (let start = 0; start < records.length; start += UsageDao.UPSERT_CHUNK_ROWS) {
        const chunk: UsageRecordEntity[] = records.slice(start, start + UsageDao.UPSERT_CHUNK_ROWS)
        const values: string[] = []
        const args: Array<relationalStore.ValueType> = []
        for (const r of chunk) {
          values.push(UsageDao.UPSERT_ROW_VALUES)
          args.push(r.usgId, r.createdAt, r.model, r.provider, r.inputTokens, r.outputTokens,
            r.reasoningTokens, r.cacheReadTokens, r.cacheWrite5mTokens, r.cacheWrite1hTokens,
            r.costRaw, r.costUsd, r.keyId, r.sessionId, r.plan, r.syncedAt, accountId,
            r.createdAt)
        }
        await store.executeSql(
          `INSERT INTO usage_records (${UsageDao.UPSERT_COLUMNS})
           VALUES ${values.join(',')}
           ON CONFLICT(usg_id) DO UPDATE SET ${UsageDao.UPSERT_UPDATE_SET}`,
          args,
        )
      }
      store.commit()
    } catch (e) {
      store.rollBack()
      throw (e instanceof Error ? e : new Error('批量插入失败'))
    }
    return inserted
  }

  /** 裁剪窗口外的记录 —— 日历日口径走 idx_usage_account_localdate (desktop parity)。 */
  async pruneOldRecords(intervalArg: string, accountId: number): Promise<void> {
    // 日历日口径最多多保留窗口边界当天一天的记录, 只多不少, 不会丢数据;
    // 原先 datetime(created_at) 包裹索引列, 每次同步都退化为按账号全表扫.
    await this.store().executeSql(
      `DELETE FROM usage_records WHERE account_id = ? AND local_date < date('now', 'localtime', ?)`,
      [accountId, intervalArg],
    )
  }

  async deleteAll(): Promise<void> {
    await this.store().executeSql('DELETE FROM usage_records')
  }

  // ------------------------------------------------------------------
  // Aggregations
  // ------------------------------------------------------------------

  /**
   * 周期过滤条件 —— db._PERIOD_CLAUSES / _period_where 的 ArkTS 移植。
   *
   * local_date 为写入时物化的本地日 "YYYY-MM-DD" (AppDb 迁移 v2), 可直接走
   * idx_usage_account_localdate; 原先用 datetime(created_at)/substr(datetime(...))
   * 包裹索引列, 每次周期查询都退化为按账号全表扫描 (dashboard 一次刷新 6 条).
   */
  private static periodClause(period: string, cycleStart: string | null = null): [string | null, Array<string>] {
    switch (period) {
      case '5h':
        // 滚动 5 小时窗口: datetime() 包裹索引列无法走索引, 先用 local_date 把行集
        // 收敛到昨/今两天 (索引范围扫), 再叠加 datetime() 保留精确的滚动口径
        return [`(local_date >= date('now', 'localtime', '-1 day')
                  AND datetime(created_at) >= datetime('now', '-5 hours'))`, []]
      case 'today':
        return [`local_date = date('now', 'localtime')`, []]
      case 'month':
        // 「本月」= 当前月度重置周期起点 (desktop db._period_where parity);
        // 无周期记录 (配额从未拉到) 时回退滚动 30 天, 与 "30d" 口径一致
        if (cycleStart !== null && cycleStart.length > 0) {
          // 先以起点的本地日做索引收敛, 再用 datetime() 保留秒级精确口径
          return [`(local_date >= date(?, 'localtime') AND datetime(created_at) >= datetime(?))`,
            [cycleStart, cycleStart]]
        }
        return [`local_date >= date('now', 'localtime', ?)`, [`-${MonthlyCycle.PERIOD_DAYS} days`]]
      case 'all':
        return [null, []]
      default: {
        // "7d"/"30d" 等: 日历日口径 (与 dailyStats/todayTrend 一致), 走索引
        const m = /^(\d+)d$/.exec(period)
        let days = 30
        if (m !== null) {
          const n = Number(m[1])
          if (!Number.isNaN(n)) {
            days = Math.min(365, Math.max(1, n))
          }
        }
        return [`local_date >= date('now', 'localtime', ?)`, [`-${days} days`]]
      }
    }
  }

  private static buildWhere(period: string, accountId: number, cycleStart: string | null = null): [string, Array<string>] {
    const pc = UsageDao.periodClause(period, cycleStart)
    const clause = pc[0]
    const args = pc[1]
    const allArgs: Array<string> = [accountId.toString()]
    for (const a of args) {
      allArgs.push(a)
    }
    if (clause === null) {
      return ['WHERE account_id = ?', allArgs]
    }
    return [`WHERE account_id = ? AND ${clause}`, allArgs]
  }

  private static totalsSql(where: string): string {
    return `SELECT COALESCE(COUNT(*), 0) AS request_count,
                   COALESCE(COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id END), 0) AS session_count,
                   COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
                   COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
                   COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
                   COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
                   COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                   COALESCE(SUM(cost_usd), 0) AS total_cost_usd
            FROM usage_records
            ${where}`
  }

  async totals(period: string, accountId: number, cycleStart: string | null = null): Promise<Totals> {
    const bw = UsageDao.buildWhere(period, accountId, cycleStart)
    const where = bw[0]
    const args = bw[1]
    const rs = await this.store().querySql(UsageDao.totalsSql(where), args)
    const reader = new RowReader(rs)
    let t: Totals = {
      requestCount: 0, sessionCount: 0, totalInputTokens: 0, uncachedInputTokens: 0,
      totalReasoningTokens: 0, cacheHitTokens: 0, cacheWriteTokens: 0, totalOutputTokens: 0,
      totalCostUsd: 0, hitRate: 0, totalTokens: 0,
    }
    if (reader.next()) {
      const hit = reader.getLong('cache_hit_tokens')
      const miss = reader.getLong('uncached_input_tokens')
      const hitRate = hit + miss > 0 ? hit / (hit + miss) * 100 : 0
      const ti = reader.getLong('total_input_tokens')
      const to = reader.getLong('total_output_tokens')
      const tr = reader.getLong('total_reasoning_tokens')
      t = {
        requestCount: reader.getLong('request_count'),
        sessionCount: reader.getLong('session_count'),
        totalInputTokens: ti,
        uncachedInputTokens: miss,
        totalReasoningTokens: tr,
        cacheHitTokens: hit,
        cacheWriteTokens: reader.getLong('cache_write_tokens'),
        totalOutputTokens: to,
        totalCostUsd: reader.getDouble('total_cost_usd'),
        hitRate: Math.round(hitRate * 100) / 100,
        totalTokens: ti + to + tr,
      }
    }
    reader.close()
    return t
  }

  /** 每日聚合 —— db.daily_stats (按账号)。 */
  async dailyStats(days: number, accountId: number): Promise<DailyStat[]> {
    const clamped = Math.min(365, Math.max(1, days))
    const rs = await this.store().querySql(
      `SELECT local_date AS date,
              COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
              COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
              COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
              COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
              COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
              COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
              COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
              COALESCE(COUNT(*), 0) AS request_count
       FROM usage_records
       WHERE account_id = ? AND local_date >= date('now', 'localtime', ?)
       GROUP BY local_date
       ORDER BY date ASC`,
      [accountId.toString(), `-${clamped} days`],
    )
    const reader = new RowReader(rs)
    const byDate: Map<string, DailyStat> = new Map()
    while (reader.next()) {
      const hit = reader.getLong('cache_hit_tokens')
      const miss = reader.getLong('uncached_input_tokens')
      const hitRate = hit + miss > 0 ? hit / (hit + miss) * 100 : 0
      const stat: DailyStat = {
        date: reader.getStr('date'),
        totalInputTokens: reader.getLong('total_input_tokens'),
        uncachedInputTokens: miss,
        totalReasoningTokens: reader.getLong('total_reasoning_tokens'),
        cacheHitTokens: hit,
        cacheWriteTokens: reader.getLong('cache_write_tokens'),
        totalOutputTokens: reader.getLong('total_output_tokens'),
        totalCostUsd: reader.getDouble('total_cost_usd'),
        requestCount: reader.getLong('request_count'),
        hitRate: Math.round(hitRate * 100) / 100,
      }
      byDate.set(stat.date, stat)
    }
    reader.close()

    // 连续日期补 0 (desktop db.daily_stats / Android UsageDao.dailyStats 同口径):
    // 只返回有记录的天会让趋势图 x 轴压缩、缺天跳线
    const out: DailyStat[] = []
    const now = new Date()
    for (let i = clamped; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i)
      const key = `${d.getFullYear()}-${UsageDao.pad2(d.getMonth() + 1)}-${UsageDao.pad2(d.getDate())}`
      const existing = byDate.get(key)
      if (existing !== undefined) {
        out.push(existing)
      } else {
        out.push({
          date: key,
          totalInputTokens: 0,
          uncachedInputTokens: 0,
          totalReasoningTokens: 0,
          cacheHitTokens: 0,
          cacheWriteTokens: 0,
          totalOutputTokens: 0,
          totalCostUsd: 0,
          requestCount: 0,
          hitRate: 0,
        })
      }
    }
    return out
  }

  private static pad2(n: number): string {
    return n < 10 ? `0${n}` : `${n}`
  }

  /** 今日 24 小时趋势 (零填充) —— db.today_trend (按账号)。 */
  async todayTrend(accountId: number): Promise<HourStat[]> {
    const rs = await this.store().querySql(
      `SELECT CAST(strftime('%H', datetime(created_at, 'localtime')) AS INTEGER) AS hour,
              COALESCE(SUM(input_tokens), 0) AS input,
              COALESCE(SUM(output_tokens), 0) AS output,
              COALESCE(SUM(reasoning_tokens), 0) AS reasoning
       FROM usage_records
       WHERE account_id = ? AND local_date = date('now', 'localtime')
       GROUP BY hour`,
      [accountId.toString()],
    )
    const reader = new RowReader(rs)
    const byHour: Map<number, HourStat> = new Map()
    while (reader.next()) {
      const h = reader.getLong('hour')
      byHour.set(h, {
        hour: '',
        input: reader.getLong('input'),
        output: reader.getLong('output'),
        reasoning: reader.getLong('reasoning'),
      })
    }
    reader.close()
    const out: HourStat[] = []
    for (let h = 0; h < 24; h++) {
      const r = byHour.get(h)
      out.push({
        hour: `${String(h).padStart(2, '0')}:00`,
        input: r !== undefined ? r.input : 0,
        output: r !== undefined ? r.output : 0,
        reasoning: r !== undefined ? r.reasoning : 0,
      })
    }
    return out
  }

  /** 单模型聚合 —— db.model_stats (按账号)。 */
  async modelStats(period: string, accountId: number, cycleStart: string | null = null): Promise<ModelStat[]> {
    const bw = UsageDao.buildWhere(period, accountId, cycleStart)
    const where = bw[0]
    const args = bw[1]
    const rs = await this.store().querySql(
      `SELECT model,
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
       ${where}
       GROUP BY model
       ORDER BY (COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) + COALESCE(SUM(output_tokens), 0)) DESC`,
      args,
    )
    const reader = new RowReader(rs)
    const out: ModelStat[] = []
    while (reader.next()) {
      const hit = reader.getLong('cache_hit_tokens')
      const miss = reader.getLong('uncached_input_tokens')
      const hitRate = hit + miss > 0 ? hit / (hit + miss) * 100 : 0
      out.push({
        model: reader.getStr('model'),
        requestCount: reader.getLong('request_count'),
        sessionCount: reader.getLong('session_count'),
        totalInputTokens: reader.getLong('total_input_tokens'),
        uncachedInputTokens: miss,
        totalReasoningTokens: reader.getLong('total_reasoning_tokens'),
        cacheHitTokens: hit,
        cacheWriteTokens: reader.getLong('cache_write_tokens'),
        totalOutputTokens: reader.getLong('total_output_tokens'),
        totalCostUsd: reader.getDouble('total_cost_usd'),
        hitRate: Math.round(hitRate * 100) / 100,
      })
    }
    reader.close()
    return out
  }

  private static readonly SESSION_KEY =
    `CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id
          WHEN key_id IS NOT NULL AND key_id != '' THEN key_id ELSE '' END`

  /** 会话聚合 + 分页 —— db.session_stats_page (按账号)。 */
  async sessionStatsPage(
    page: number, pageSize: number, days: number | null, accountId: number,
  ): Promise<[SessionStat[], number]> {
    const whereParts: string[] = ['account_id = ?']
    const params: Array<string> = [accountId.toString()]
    if (days !== null) {
      // 日历日口径 + local_date 索引 (desktop _period_where / prune parity)
      whereParts.push(`local_date >= date('now', 'localtime', ?)`)
      params.push(`-${Math.min(365, Math.max(1, days))} days`)
    }
    const where = `WHERE ${whereParts.join(' AND ')}`
    const store = this.store()

    const totalRs = await store.querySql(
      `SELECT COUNT(DISTINCT ${UsageDao.SESSION_KEY}) AS count FROM usage_records ${where}`, params,
    )
    const totalReader = new RowReader(totalRs)
    let total = 0
    if (totalReader.next()) {
      total = totalReader.getLong('count')
    }
    totalReader.close()

    const pageArgs: Array<string> = []
    for (const pv of params) {
      pageArgs.push(pv)
    }
    pageArgs.push(pageSize.toString(), ((page - 1) * pageSize).toString())
    const rs = await store.querySql(
      `SELECT ${UsageDao.SESSION_KEY} AS session_id,
              MAX(key_id) AS key_id,
              COALESCE(COUNT(*), 0) AS request_count,
              COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
              COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
              COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
              COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
              COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
              MAX(created_at) AS last_at
       FROM usage_records ${where}
       GROUP BY ${UsageDao.SESSION_KEY}
       ORDER BY last_at DESC
       LIMIT ? OFFSET ?`,
      pageArgs,
    )
    const reader = new RowReader(rs)
    const records: SessionStat[] = []
    while (reader.next()) {
      records.push({
        sessionId: reader.getStr('session_id'),
        requestCount: reader.getLong('request_count'),
        totalInputTokens: reader.getLong('total_input_tokens'),
        uncachedInputTokens: reader.getLong('uncached_input_tokens'),
        totalOutputTokens: reader.getLong('total_output_tokens'),
        totalReasoningTokens: reader.getLong('total_reasoning_tokens'),
        totalCostUsd: reader.getDouble('total_cost_usd'),
        lastAt: reader.getStr('last_at'),
        keyId: reader.isNull('key_id') ? null : reader.getStr('key_id'),
        keyName: null,
      })
    }
    reader.close()
    return [records, total]
  }

  /** 分页用量记录 —— db.usage_records_page (按账号)。 */
  async usageRecordsPage(
    page: number, pageSize: number, model: string | null, days: number | null, accountId: number,
  ): Promise<[UsageRecordRow[], number]> {
    const whereParts: string[] = ['account_id = ?']
    const params: Array<string> = [accountId.toString()]
    if (model !== null && model.length > 0) {
      whereParts.push(`model = ?`)
      params.push(model)
    }
    if (days !== null) {
      // 日历日口径 + local_date 索引 (desktop _period_where / prune parity)
      whereParts.push(`local_date >= date('now', 'localtime', ?)`)
      params.push(`-${Math.min(365, Math.max(1, days))} days`)
    }
    const where = `WHERE ${whereParts.join(' AND ')}`
    const store = this.store()

    const totalRs = await store.querySql(`SELECT COUNT(*) AS count FROM usage_records ${where}`, params)
    const totalReader = new RowReader(totalRs)
    let total = 0
    if (totalReader.next()) {
      total = totalReader.getLong('count')
    }
    totalReader.close()

    const pageArgs: Array<string> = []
    for (const pv of params) {
      pageArgs.push(pv)
    }
    pageArgs.push(pageSize.toString(), ((page - 1) * pageSize).toString())
    const rs = await store.querySql(
      `SELECT * FROM usage_records ${where} ORDER BY created_at DESC LIMIT ? OFFSET ?`, pageArgs,
    )
    const reader = new RowReader(rs)
    const records: UsageRecordRow[] = []
    while (reader.next()) {
      records.push({
        usgId: reader.getStr('usg_id'),
        createdAt: reader.getStr('created_at'),
        model: reader.getStr('model'),
        provider: reader.isNull('provider') ? null : reader.getStr('provider'),
        inputTokens: reader.getLong('input_tokens'),
        outputTokens: reader.getLong('output_tokens'),
        reasoningTokens: reader.getLong('reasoning_tokens'),
        cacheReadTokens: reader.getLong('cache_read_tokens'),
        cacheWriteTokens: reader.getLong('cache_write_5m_tokens') + reader.getLong('cache_write_1h_tokens'),
        costUsd: reader.getDouble('cost_usd'),
        sessionId: reader.isNull('session_id') ? null : reader.getStr('session_id'),
        plan: reader.isNull('plan') ? null : reader.getStr('plan'),
        keyId: reader.isNull('key_id') ? null : reader.getStr('key_id'),
        keyName: null,
      })
    }
    reader.close()
    return [records, total]
  }

  async listModels(accountId: number): Promise<string[]> {
    const rs = await this.store().querySql(
      'SELECT DISTINCT model FROM usage_records WHERE account_id = ? ORDER BY model', [accountId.toString()],
    )
    const reader = new RowReader(rs)
    const out: string[] = []
    while (reader.next()) {
      out.push(reader.getStr('model'))
    }
    reader.close()
    return out
  }

  async recordBounds(accountId: number): Promise<BoundsRow> {
    const rs = await this.store().querySql(
      `SELECT COUNT(*) AS count, MIN(created_at) AS oldest, MAX(created_at) AS newest
       FROM usage_records WHERE account_id = ?`, [accountId.toString()],
    )
    const reader = new RowReader(rs)
    let out: BoundsRow = { count: 0, oldest: null, newest: null }
    if (reader.next()) {
      out = {
        count: reader.getLong('count'),
        oldest: reader.isNull('oldest') ? null : reader.getStr('oldest'),
        newest: reader.isNull('newest') ? null : reader.getStr('newest'),
      }
    }
    reader.close()
    return out
  }

  /** 清除 injectSampleData 注入的调试记录 (debug 构建的设置页入口), 返回删除条数。 */
  async clearSampleData(): Promise<number> {
    const store = this.store()
    const rs = await store.querySql(
      "SELECT COUNT(*) AS count FROM usage_records WHERE usg_id LIKE 'usg_sample_%'",
    )
    const reader = new RowReader(rs)
    let count = 0
    if (reader.next()) {
      count = reader.getLong('count')
    }
    reader.close()
    if (count === 0) {
      return 0
    }
    await store.executeSql("DELETE FROM usage_records WHERE usg_id LIKE 'usg_sample_%'")
    return count
  }
}