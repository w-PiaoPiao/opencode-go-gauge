/**
 * usage_records DAO —— UsageDao.kt (android) 的 ArkTS 移植。
 * SQL 与 desktop db.py v2.0.0 逐句对应, 一律按 account_id 维度过滤。
 */
import { relationalStore } from '@kit.ArkData'
import { AppDb } from './AppDb'
import { RowReader } from './RowReader'
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

  /** 批量插入去重; 返回新增行数。已存在的记录保留原归属账号 (desktop ON CONFLICT 语义)。 */
  async insertUsageRecords(records: UsageRecordEntity[], accountId: number): Promise<number> {
    if (records.length === 0) {
      return 0
    }
    const store = this.store()
    const ids: string[] = records.map((r) => r.usgId)
    const existingAccount: Map<string, number> = new Map()
    const rs = await store.querySql(
      `SELECT usg_id, account_id FROM usage_records WHERE usg_id IN (${UsageDao.placeholders(ids.length)})`,
      ids,
    )
    const reader = new RowReader(rs)
    while (reader.next()) {
      existingAccount.set(reader.getStr('usg_id'), reader.getLong('account_id'))
    }
    reader.close()

    let inserted = 0
    store.beginTransaction()
    try {
      for (const r of records) {
        if (existingAccount.has(r.usgId)) {
          await store.executeSql(
            `UPDATE usage_records SET created_at=?, model=?, provider=?, input_tokens=?, output_tokens=?,
               reasoning_tokens=?, cache_read_tokens=?, cache_write_5m_tokens=?, cache_write_1h_tokens=?,
               cost_raw=?, cost_usd=?, key_id=?, session_id=?, plan=?, synced_at=?
             WHERE usg_id=?`,
            [r.createdAt, r.model, r.provider, r.inputTokens, r.outputTokens, r.reasoningTokens,
              r.cacheReadTokens, r.cacheWrite5mTokens, r.cacheWrite1hTokens, r.costRaw, r.costUsd,
              r.keyId, r.sessionId, r.plan, r.syncedAt, r.usgId],
          )
        } else {
          await store.executeSql(
            `INSERT INTO usage_records (usg_id, created_at, model, provider, input_tokens, output_tokens,
               reasoning_tokens, cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens,
               cost_raw, cost_usd, key_id, session_id, plan, synced_at, account_id)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
            [r.usgId, r.createdAt, r.model, r.provider, r.inputTokens, r.outputTokens, r.reasoningTokens,
              r.cacheReadTokens, r.cacheWrite5mTokens, r.cacheWrite1hTokens, r.costRaw, r.costUsd,
              r.keyId, r.sessionId, r.plan, r.syncedAt, existingAccount.get(r.usgId) !== undefined
                ? existingAccount.get(r.usgId) : accountId],
          )
          inserted++
        }
      }
      store.commit()
    } catch (e) {
      store.rollBack()
      throw (e instanceof Error ? e : new Error('批量插入失败'))
    }
    return inserted
  }

  async pruneOldRecords(intervalArg: string, accountId: number): Promise<void> {
    await this.store().executeSql(
      `DELETE FROM usage_records WHERE account_id = ? AND datetime(created_at) < datetime('now', ?)`,
      [accountId, intervalArg],
    )
  }

  async deleteAll(): Promise<void> {
    await this.store().executeSql('DELETE FROM usage_records')
  }

  // ------------------------------------------------------------------
  // Aggregations
  // ------------------------------------------------------------------

  private static periodClause(period: string): [string | null, Array<string>] {
    switch (period) {
      case '5h':
        return [`datetime(created_at) >= datetime('now', '-5 hours')`, []]
      case 'today':
        return [`substr(datetime(created_at, 'localtime'), 1, 10) = date('now', 'localtime')`, []]
      case 'all':
        return [null, []]
      default: {
        const m = /^(\d+)d$/.exec(period)
        let days = 30
        if (m !== null) {
          const n = Number(m[1])
          if (!Number.isNaN(n)) {
            days = Math.min(365, Math.max(1, n))
          }
        }
        return [`datetime(created_at) >= datetime('now', ?)`, [`-${days} days`]]
      }
    }
  }

  private static buildWhere(period: string, accountId: number): [string, Array<string>] {
    const pc = UsageDao.periodClause(period)
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

  async totals(period: string, accountId: number): Promise<Totals> {
    const bw = UsageDao.buildWhere(period, accountId)
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
      `SELECT substr(datetime(created_at, 'localtime'), 1, 10) AS date,
              COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
              COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
              COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
              COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
              COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
              COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
              COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
              COALESCE(COUNT(*), 0) AS request_count
       FROM usage_records
       WHERE account_id = ? AND substr(datetime(created_at, 'localtime'), 1, 10) >= date('now', 'localtime', ?)
       GROUP BY substr(datetime(created_at, 'localtime'), 1, 10)
       ORDER BY date ASC`,
      [accountId.toString(), `-${clamped} days`],
    )
    const reader = new RowReader(rs)
    const out: DailyStat[] = []
    while (reader.next()) {
      const hit = reader.getLong('cache_hit_tokens')
      const miss = reader.getLong('uncached_input_tokens')
      const hitRate = hit + miss > 0 ? hit / (hit + miss) * 100 : 0
      out.push({
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
      })
    }
    reader.close()
    return out
  }

  /** 今日 24 小时趋势 (零填充) —— db.today_trend (按账号)。 */
  async todayTrend(accountId: number): Promise<HourStat[]> {
    const rs = await this.store().querySql(
      `SELECT CAST(strftime('%H', datetime(created_at, 'localtime')) AS INTEGER) AS hour,
              COALESCE(SUM(input_tokens), 0) AS input,
              COALESCE(SUM(output_tokens), 0) AS output,
              COALESCE(SUM(reasoning_tokens), 0) AS reasoning
       FROM usage_records
       WHERE account_id = ? AND substr(datetime(created_at, 'localtime'), 1, 10) = date('now', 'localtime')
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
  async modelStats(period: string, accountId: number): Promise<ModelStat[]> {
    const bw = UsageDao.buildWhere(period, accountId)
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
      whereParts.push(`datetime(created_at) >= datetime('now', ?)`)
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
      whereParts.push(`datetime(created_at) >= datetime('now', ?)`)
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
}