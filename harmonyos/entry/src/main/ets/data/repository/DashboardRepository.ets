/**
 * Dashboard repository —— DashboardRepository.kt / server.py v2.0.0 移植
 * (多账号同步引擎, 配额按账号分槽缓存) + db.py 聚合, 作为 UI 层的唯一服务。
 *
 * 未显式传 accountId 的接口一律作用于活跃账号 (desktop db 兼容约定)。
 */
import { AppDb } from '../db/AppDb'
import { UsageDao, UsageRecordEntity } from '../db/UsageDao'
import { SyncDao } from '../db/SyncDao'
import { OpenCodeApi } from '../remote/OpenCodeApi'
import { ExchangeApi } from '../remote/ExchangeApi'
import {
  AccountInfo, AppSettings, DashboardData, DailyStat, HourStat, ModelStat, PageResult, QuotaResult,
  SessionStat, SyncProgress, SyncResult, SyncState, Totals, UsageRecord, UsageRecordRow, emptySyncProgress,
} from '../../common/model/Models'

interface QuotaCacheSlot {
  at: number
  data: QuotaResult | null
}

interface ExchangeCache {
  at: number
  usdCny: number
}

export class DashboardRepository {
  private static readonly QUOTA_CACHE_TTL = 30.0
  private static readonly EXCHANGE_TTL = 6 * 3600.0
  private static readonly DEFAULT_USD_CNY = 7.2

  private quotaCache: Map<number, QuotaCacheSlot> = new Map()
  private quotaRefreshing: Set<number> = new Set()
  private exchangeCache: ExchangeCache = { at: 0, usdCny: DashboardRepository.DEFAULT_USD_CNY }

  private usageDao: UsageDao = AppDb.usageDao()
  private syncDao: SyncDao = AppDb.syncDao()

  private _progress: SyncProgress = emptySyncProgress()

  get progress(): SyncProgress {
    return this._progress
  }

  private updateProgress(fn: (p: SyncProgress) => void): void {
    const cur = this._progress
    const next: SyncProgress = {
      running: cur.running,
      mode: cur.mode,
      page: cur.page,
      inserted: cur.inserted,
      phase: cur.phase,
      message: cur.message,
      account: cur.account,
    }
    fn(next)
    this._progress = next
  }

  // ------------------------------------------------------------------
  // 活跃账号
  // ------------------------------------------------------------------

  async activeAccountId(): Promise<number> {
    return this.syncDao.getActiveAccountId()
  }

  async accounts(): Promise<AccountInfo[]> {
    return this.syncDao.listAccounts()
  }

  async countLoggedInAccounts(): Promise<number> {
    return this.syncDao.countLoggedInAccounts()
  }

  async account(): Promise<AccountInfo | null> {
    return this.syncDao.getAccount()
  }

  async switchAccount(accountId: number): Promise<boolean> {
    const ok = await this.syncDao.setActiveAccount(accountId)
    if (ok) {
      this._progress = emptySyncProgress()
    }
    return ok
  }

  async renameAccount(accountId: number, name: string): Promise<boolean> {
    return this.syncDao.renameAccount(accountId, name)
  }

  /** 返回剩余账号数。 */
  async deleteAccount(accountId: number): Promise<number> {
    const remaining = await this.syncDao.deleteAccount(accountId)
    this._progress = emptySyncProgress()
    return remaining
  }

  /** 登录成功按模式落库: add=新建账号 (同 token 去重) 并切换; relogin=更新活跃账号凭证。 */
  async loginSuccess(token: string, workspaceHint: string, mode: string): Promise<void> {
    if (mode === 'add') {
      await this.syncDao.addAccount(token, workspaceHint, true)
    } else {
      await this.syncDao.saveToken(token, workspaceHint.trim().length > 0 ? workspaceHint.trim() : 'Default')
    }
    this._progress = emptySyncProgress()
  }

  // ------------------------------------------------------------------
  // Quota 刷新 (按账号分槽缓存 + 防重入)
  // ------------------------------------------------------------------

  async ensureQuota(): Promise<void> {
    const accountId = await this.syncDao.getActiveAccountId()
    if (accountId === 0) {
      return
    }
    const now = Date.now() / 1000
    const slot = this.quotaCache.get(accountId)
    if (slot !== undefined && slot.data !== null && now - slot.at < DashboardRepository.QUOTA_CACHE_TTL) {
      return
    }
    if (this.quotaRefreshing.has(accountId)) {
      return
    }
    const token = await this.syncDao.getTokenFor(accountId)
    if (token.length === 0) {
      return
    }
    this.quotaRefreshing.add(accountId)
    try {
      const target: QuotaCacheSlot = this.quotaCache.get(accountId) ?? { at: 0, data: null }
      const hint = await this.syncDao.getWorkspaceHintFor(accountId)
      target.at = Date.now() / 1000
      try {
        target.data = await OpenCodeApi.fetchQuota(token, hint)
      } catch (e) {
        target.data = null
      }
      this.quotaCache.set(accountId, target)
    } finally {
      this.quotaRefreshing.delete(accountId)
    }
  }

  async currentQuota(): Promise<QuotaResult | null> {
    const accountId = await this.syncDao.getActiveAccountId()
    const slot = this.quotaCache.get(accountId)
    return slot !== undefined ? slot.data : null
  }

  private async usdCny(): Promise<number> {
    const now = Date.now() / 1000
    if (now - this.exchangeCache.at < DashboardRepository.EXCHANGE_TTL) {
      return this.exchangeCache.usdCny
    }
    try {
      const rate = await ExchangeApi.fetchUsdCny()
      if (rate > 0) {
        this.exchangeCache.usdCny = rate
      }
    } catch (e) {
      // 失败保留旧值 (server.py parity)
    }
    this.exchangeCache.at = Date.now() / 1000
    return this.exchangeCache.usdCny
  }

  // ------------------------------------------------------------------
  // Dashboard 数据包 (活跃账号视角)
  // ------------------------------------------------------------------

  static fmtServerTime(): string {
    const d = new Date()
    const p = (n: number): string => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  }

  async loadDashboard(range: string): Promise<DashboardData> {
    const aid = await this.syncDao.getActiveAccountId()
    const token = await this.syncDao.getTokenFor(aid)
    // 并发跑相互独立的 DB/汇率查询
    const parts = await Promise.all([
      this.usageDao.totals(range, aid),
      this.usageDao.totals('today', aid),
      this.usageDao.dailyStats(60, aid),
      this.usageDao.dailyStats(30, aid),
      this.usageDao.todayTrend(aid),
      this.usageDao.modelStats(range, aid),
      this.syncDao.getSyncStateFor(aid),
      this.usdCny(),
      this.currentQuota(),
    ])
    return {
      loggedIn: token.length > 0,
      quota: token.length > 0 ? (parts[8] as QuotaResult | null) : null,
      totals: parts[0] as Totals,
      today: parts[1] as Totals,
      daily: parts[2] as DailyStat[],
      trend: parts[3] as DailyStat[],
      todayTrend: parts[4] as HourStat[],
      models: parts[5] as ModelStat[],
      sync: parts[6] as SyncState,
      progress: this._progress,
      range: range,
      usdCny: parts[7] as number,
      serverTime: DashboardRepository.fmtServerTime(),
    }
  }

  // ------------------------------------------------------------------
  // 同步引擎 (多账号轮询)
  // ------------------------------------------------------------------

  async syncUsage(mode: string): Promise<SyncResult> {
    // incremental 轮询所有已登录账号; full 仅作用于活跃账号 (desktop parity)
    const targets: Array<[number, string]> = []
    let windowDays: number | null = null
    if (mode === 'full') {
      const aid = await this.syncDao.getActiveAccountId()
      const acct = aid !== 0 ? await this.syncDao.getTokenFor(aid) : ''
      if (aid !== 0 && acct.length > 0) {
        const info = await this.syncDao.getAccount()
        targets.push([aid, info !== null ? info.name : `#${aid}`])
      }
    } else {
      const accounts = await this.syncDao.listAccounts()
      for (const a of accounts) {
        if (a.hasToken) {
          targets.push([a.id, a.name])
        }
      }
    }
    if (targets.length === 0) {
      return { ok: false, error: '未登录', inserted: 0, pages: 0, partial: false, failedPages: 0 }
    }
    if (this._progress.running) {
      return { ok: false, error: '已有同步任务进行中', inserted: 0, pages: 0, partial: false, failedPages: 0 }
    }

    const settings = await AppDb.settingsDao().getSettings()
    windowDays = settings.windowDays

    this._progress = { running: true, mode: mode, page: 0, inserted: 0, phase: 'usage', message: '', account: '' }

    try {
      let totalInserted = 0
      let pages = 0
      let anyError = ''
      let partial = false

      for (const target of targets) {
        const aid = target[0]
        const name = target[1]
        this.updateProgress((p) => { p.account = name })
        const result = await this.syncOneAccount(aid, name, mode, windowDays)
        totalInserted += result.inserted
        pages += result.pages
        if (!result.ok) {
          anyError = result.error !== null ? result.error : '同步失败'
          if (mode === 'incremental') {
            const msg = `[${name}] ${anyError}`
            this.updateProgress((p) => { p.phase = 'error'; p.message = msg })
            return { ok: false, error: anyError, inserted: totalInserted, pages: pages, partial: false, failedPages: 0 }
          }
        }
        if (result.partial) {
          partial = true
        }
      }

      if (partial || (mode !== 'incremental' && anyError.length > 0)) {
        const msg = anyError.length > 0 ? '部分账号同步异常' : '完成, 但部分页面拉取失败'
        this.updateProgress((p) => { p.phase = 'done'; p.message = msg })
        return { ok: true, error: null, inserted: totalInserted, pages: pages, partial: true, failedPages: 0 }
      }
      const msg = `同步完成, 新增 ${totalInserted} 条`
      this.updateProgress((p) => { p.phase = 'done'; p.message = msg })
      return { ok: true, error: null, inserted: totalInserted, pages: pages, partial: false, failedPages: 0 }
    } catch (e) {
      const errMsg = (e as Error).message !== undefined ? (e as Error).message : '同步失败'
      this.updateProgress((p) => { p.phase = 'error'; p.message = errMsg })
      return { ok: false, error: errMsg, inserted: 0, pages: 0, partial: false, failedPages: 0 }
    } finally {
      this.updateProgress((p) => { p.running = false; p.account = '' })
    }
  }

  /** 同步单个账号的用量记录。 */
  private async syncOneAccount(
    accountId: number, name: string, mode: string, windowDays: number | null,
  ): Promise<SyncResult> {
    const token = await this.syncDao.getTokenFor(accountId)
    if (token.length === 0) {
      return { ok: false, error: '未登录', inserted: 0, pages: 0, partial: false, failedPages: 0 }
    }
    let workspaceId = await this.syncDao.getWorkspaceHintFor(accountId)

    try {
      // 确保工作区 ID 已解析
      try {
        const resolved = await OpenCodeApi.resolveWorkspaceId(workspaceId, token)
        if (!workspaceId.startsWith('wrk_')) {
          workspaceId = resolved
          await this.syncDao.saveResolvedWorkspace(accountId, resolved, new Date().toISOString())
        }
      } catch (e) {
        const msg = `工作区解析失败: ${(e as Error).message}`
        await this.syncDao.updateSyncStateAndTotals(accountId, 'error', msg, 0)
        this.updateProgress((p) => { p.phase = 'error'; p.message = msg })
        return { ok: false, error: (e as Error).message, inserted: 0, pages: 0, partial: false, failedPages: 0 }
      }

      let totalInserted = 0
      const maxPages = mode === 'full' ? 2000 : 5
      let page = 0
      let emptyBatches = 0
      let failedPages = 0
      let windowBoundaryReached = false

      while (page < maxPages) {
        const batchEnd = Math.min(page + 5, maxPages)
        const batchPages: number[] = []
        for (let p = page; p < batchEnd; p++) {
          batchPages.push(p)
        }
        this.updateProgress((p) => { p.page = page })

        const results = await this.fetchBatch(token, workspaceId, batchPages)

        let batchInserted = 0
        let batchFullPages = 0
        let batchFailed = 0
        for (const p of batchPages) {
          const result = results.get(p)
          if (result === undefined || result === null) {
            batchFailed++
            continue
          }
          if (result.length === 0) {
            continue // 空页: 数据结束
          }
          if (mode === 'full' && windowDays !== null) {
            let earliest = ''
            for (const r of result) {
              if (earliest.length === 0 || r.createdAt < earliest) {
                earliest = r.createdAt
              }
            }
            if (earliest.length > 0) {
              try {
                const et = Date.parse(earliest)
                const boundary = Date.now() - windowDays * 24 * 3600 * 1000
                if (!Number.isNaN(et) && et < boundary) {
                  windowBoundaryReached = true
                }
              } catch (e) {
                // 忽略不可解析的日期 (desktop parity)
              }
            }
          }
          const syncedAt = new Date().toISOString()
          const entities: UsageRecordEntity[] = result.map((r) => toEntity(r, syncedAt, accountId))
          const inserted = await this.usageDao.insertUsageRecords(entities, accountId)
          totalInserted += inserted
          batchInserted += inserted
          if (result.length >= 50) {
            batchFullPages++
          }
          this.updateProgress((p) => { p.inserted = totalInserted })
        }

        page += 5

        if (windowBoundaryReached) {
          break
        }
        if (batchFailed > 0) {
          failedPages += batchFailed
          if (mode === 'incremental') {
            const msg = '网络请求失败 (IncompleteRead/超时)'
            await this.syncDao.updateSyncStateAndTotals(accountId, 'error', `[${name}] 第 ${page - 4} 页拉取失败: ${msg}`, totalInserted)
            this.updateProgress((p) => {
              p.phase = 'error'
              p.message = `[${name}] 第 ${page - 4} 页拉取失败: ${msg}`
            })
            return { ok: false, error: msg, inserted: totalInserted, pages: page, partial: false, failedPages: batchFailed }
          }
        }
        if (batchFullPages === 0) {
          break // 本批没有满页 -> 到底
        }
        if (mode === 'incremental' && batchInserted === 0) {
          emptyBatches++
          if (emptyBatches >= 2) {
            break
          }
        } else {
          emptyBatches = 0
        }
      }

      if (windowDays !== null) {
        await this.usageDao.pruneOldRecords(`-${windowDays} days`, accountId)
      }

      // 刷新该账号的 key 显示名称缓存 (失败不影响已有缓存)
      try {
        const names = await OpenCodeApi.fetchKeyNames(token, workspaceId)
        if (names.size > 0) {
          const merged: Map<string, string> = await AppDb.settingsDao().getKeyNames()
          names.forEach((v, k) => {
            merged.set(k, v)
          })
          await AppDb.settingsDao().saveKeyNames(merged)
        }
      } catch (e) {
        // ignore
      }

      if (failedPages > 0) {
        const msg = `完成, 但 ${failedPages} 页拉取失败 (数据不完整, 可再次全量同步补全)`
        await this.syncDao.updateSyncStateAndTotals(accountId, 'partial', msg, totalInserted)
        return { ok: true, error: null, inserted: totalInserted, pages: page, partial: true, failedPages: failedPages }
      }
      await this.syncDao.updateSyncStateAndTotals(accountId, 'ok', null, totalInserted)
      return { ok: true, error: null, inserted: totalInserted, pages: page, partial: false, failedPages: 0 }
    } catch (e) {
      const errMsg = (e as Error).message !== undefined ? (e as Error).message : '同步失败'
      await this.syncDao.updateSyncStateAndTotals(accountId, 'error', errMsg, 0)
      return { ok: false, error: errMsg, inserted: 0, pages: 0, partial: false, failedPages: 0 }
    }
  }

  /** 并发抓取最多 5 页; undefined = 失败页。 */
  private async fetchBatch(
    token: string, workspaceId: string, pages: number[],
  ): Promise<Map<number, UsageRecord[] | null>> {
    const out: Map<number, UsageRecord[] | null> = new Map()
    const tasks: Array<Promise<void>> = []
    for (const p of pages) {
      tasks.push((async () => {
        try {
          out.set(p, await OpenCodeApi.fetchUsagePage(token, workspaceId, p))
        } catch (e) {
          out.set(p, null)
        }
      })())
    }
    await Promise.all(tasks)
    return out
  }

  async syncAll(mode: string): Promise<void> {
    await this.ensureQuota()
    await this.syncUsage(mode)
  }

  // ------------------------------------------------------------------
  // 页面 / 设置 / 账号 (server.py API parity — 活跃账号)
  // ------------------------------------------------------------------

  async recordsPage(page: number, pageSize: number, model: string | null, days: number | null): Promise<PageResult<UsageRecordRow>> {
    const aid = await this.syncDao.getActiveAccountId()
    const paged = await this.usageDao.usageRecordsPage(page, pageSize, model, days, aid)
    const records = paged[0]
    const total = paged[1]
    const names = await AppDb.settingsDao().getKeyNames()
    if (names.size > 0) {
      for (const r of records) {
        if (r.keyId !== null) {
          const n = names.get(r.keyId)
          if (n !== undefined) {
            r.keyName = n
          }
        }
      }
    }
    return { records: records, total: total }
  }

  async sessionsPage(page: number, pageSize: number, days: number | null): Promise<PageResult<SessionStat>> {
    const aid = await this.syncDao.getActiveAccountId()
    const paged = await this.usageDao.sessionStatsPage(page, pageSize, days, aid)
    const records = paged[0]
    const total = paged[1]
    const names = await AppDb.settingsDao().getKeyNames()
    for (const st of records) {
      const keyGroup = st.keyId !== null && st.keyId.length > 0 && st.sessionId.startsWith('key_')
      if (keyGroup) {
        st.sessionId = ''
      }
      if (st.keyId !== null) {
        const n = names.get(st.keyId)
        if (n !== undefined && n.length > 0) {
          st.keyName = n
        }
      }
    }
    return { records: records, total: total }
  }

  async listModels(): Promise<string[]> {
    return this.usageDao.listModels(await this.syncDao.getActiveAccountId())
  }

  async syncState(): Promise<SyncState> {
    return this.syncDao.getSyncState()
  }

  async settings(): Promise<AppSettings> {
    return AppDb.settingsDao().getSettings()
  }

  async saveSettings(patch: AppSettings): Promise<AppSettings> {
    return AppDb.settingsDao().saveSettings(patch)
  }

  /** 退出登录当前活跃账号 (清其数据, 保留账号行)。 */
  async logout(): Promise<void> {
    return this.syncDao.clearAccount()
  }

  /**
   * 开发调试: 注入一组模拟用量记录 (360 条, 覆盖今天全部 24 小时/多模型/多会话/多 key),
   * 用于无网络环境下验证图表/列表渲染 (上架截图前准备数据)。返回新增条数。
   */
  async injectSampleData(): Promise<number> {
    const aid = await this.syncDao.getActiveAccountId()
    const models: string[] = ['deepseek-chat', 'gpt-4o', 'qwen-max', 'glm-4', 'claude-sonnet']
    const now = Date.now()
    const records: UsageRecord[] = []
    for (let i = 0; i < 360; i++) {
      const t = now - i * 15 * 60 * 1000
      const model = models[i % models.length]
      records.push({
        usgId: `usg_sample_${i}`,
        createdAt: new Date(t).toISOString(),
        model: model,
        provider: model.split('-')[0],
        inputTokens: 100 + (i * 37) % 5000,
        outputTokens: 50 + (i * 23) % 2000,
        reasoningTokens: (i * 11) % 300,
        cacheReadTokens: (i * 7) % 900,
        cacheWrite5mTokens: (i * 5) % 200,
        cacheWrite1hTokens: (i * 3) % 100,
        costRaw: 1000000 + (i * 12345) % 90000000,
        keyId: i % 2 === 0 ? 'key_demo1' : 'key_demo2',
        sessionId: `ses_${Math.floor(i / 6) % 25}`,
        plan: i % 3 === 0 ? 'lite' : null,
      })
    }
    const syncedAt = new Date().toISOString()
    const entities = records.map((r) => toEntity(r, syncedAt, aid))
    const inserted = await this.usageDao.insertUsageRecords(entities, aid)
    const names: Map<string, string> = new Map()
    names.set('key_demo1', '产品密钥')
    names.set('key_demo2', '测试密钥')
    await AppDb.settingsDao().saveKeyNames(names)
    return inserted
  }
}

export function toEntity(r: UsageRecord, syncedAt: string, accountId: number): UsageRecordEntity {
  return {
    usgId: r.usgId,
    createdAt: r.createdAt,
    model: r.model,
    provider: r.provider,
    inputTokens: r.inputTokens,
    outputTokens: r.outputTokens,
    reasoningTokens: r.reasoningTokens,
    cacheReadTokens: r.cacheReadTokens,
    cacheWrite5mTokens: r.cacheWrite5mTokens,
    cacheWrite1hTokens: r.cacheWrite1hTokens,
    costRaw: r.costRaw,
    costUsd: r.costRaw / 100_000_000.0,
    keyId: r.keyId,
    sessionId: r.sessionId,
    plan: r.plan,
    syncedAt: syncedAt,
    accountId: accountId,
  }
}

/** 仓库单例 —— UI/入口层统一入口。 */
export class Repo {
  private static instance: DashboardRepository | null = null

  static get(): DashboardRepository {
    if (Repo.instance === null) {
      Repo.instance = new DashboardRepository()
    }
    return Repo.instance
  }
}