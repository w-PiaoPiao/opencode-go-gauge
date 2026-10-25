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
import { UsagePage } from '../remote/UsageParser'
import { ExchangeApi } from '../remote/ExchangeApi'
import { MonthlyCycle } from '../../common/util/MonthlyCycle'
import { Fmt } from '../../common/util/Fmt'
import {
  AccountInfo, AppSettings, DashboardData, DailyStat, HourStat, ModelStat, PageResult, QuotaResult,
  QuotaWindow, SessionStat, SyncProgress, SyncResult, SyncState, Totals, UsageRecord, UsageRecordRow,
  emptySyncProgress,
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
  private exchangeFetching: boolean = false

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
    // 同步占位后再 await: 检查与置位之间不留异步点, 否则并发双进会绕过防重入
    // (desktop _quota_gate / android quotaMutex parity)
    this.quotaRefreshing.add(accountId)
    try {
      const token = await this.syncDao.getTokenFor(accountId)
      if (token.length === 0) {
        return
      }
      const target: QuotaCacheSlot = this.quotaCache.get(accountId) ?? { at: 0, data: null }
      const hint = await this.syncDao.getWorkspaceHintFor(accountId)
      target.at = Date.now() / 1000
      try {
        target.data = await OpenCodeApi.fetchQuota(token, hint)
      } catch (e) {
        target.data = null
      }
      this.quotaCache.set(accountId, target)
      // 配额拉取成功后持久化月度窗口的重置时间 (供「本月」筛选推算周期起点,
      // desktop server._record_monthly_reset parity); 失败不影响配额返回
      const quota = target.data
      if (quota !== null && quota.success) {
        const monthly = quota.windows.find((w: QuotaWindow): boolean => w.label === 'Monthly')
        if (monthly !== undefined && monthly.resetAt.length > 0) {
          const resetUtc = DashboardRepository.formatResetUtc(monthly.resetAt)
          if (resetUtc !== null) {
            try {
              await AppDb.settingsDao().saveMonthlyReset(accountId, resetUtc)
            } catch (e) {
              // 持久化失败不影响配额返回
            }
          }
        }
      }
    } finally {
      this.quotaRefreshing.delete(accountId)
    }
  }

  /**
   * Quota resetAt (Instant ISO) -> UTC "yyyy-MM-dd HH:mm:ss" —
   * desktop record_monthly_reset 存储格式 parity; 解析失败返回 null (不落库)。
   */
  private static formatResetUtc(resetAt: string): string | null {
    const ms = Date.parse(resetAt)
    return Number.isNaN(ms) ? null : MonthlyCycle.fmtUtc(ms)
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
    if (this.exchangeFetching) {
      return this.exchangeCache.usdCny
    }
    // 同步占位后再 await, 防并发重复请求 (desktop _exchange_refreshing parity)
    this.exchangeFetching = true
    try {
      const rate = await ExchangeApi.fetchUsdCny()
      if (rate > 0) {
        this.exchangeCache.usdCny = rate
      }
    } catch (e) {
      // 失败保留旧值 (server.py parity)
    } finally {
      // 无论成败都推进时间戳: 失败时避免后续每次请求都立刻重打汇率接口
      this.exchangeCache.at = Date.now() / 1000
      this.exchangeFetching = false
    }
    return this.exchangeCache.usdCny
  }

  /**
   * 汇率访问器 (供只关心金额换算的页面使用).
   *
   * RecordsPage 此前为拿一个汇率值调用 loadDashboard('all'), 连带跑完
   * totals ×2 / dailyStats ×2 / todayTrend / modelStats / getSyncState 共 9 条查询
   * 与一次汇率请求 —— 每次刷新、每次切 tab 都重跑一遍.
   */
  async usdCnyRate(): Promise<number> {
    return this.usdCny()
  }

  // ------------------------------------------------------------------
  // Dashboard 数据包 (活跃账号视角)
  // ------------------------------------------------------------------

  static fmtServerTime(): string {
    const d = new Date()
    return `${d.getFullYear()}-${Fmt.pad2(d.getMonth() + 1)}-${Fmt.pad2(d.getDate())} ${Fmt.pad2(d.getHours())}:${Fmt.pad2(d.getMinutes())}:${Fmt.pad2(d.getSeconds())}`
  }

  async loadDashboard(range: string): Promise<DashboardData> {
    const aid = await this.syncDao.getActiveAccountId()
    const token = await this.syncDao.getTokenFor(aid)
    // 「本月」= 当前月度重置周期起点 (desktop parity); 无配额记录时为 null,
    // UsageDao 回退滚动 30 天
    let cycleStart: string | null = null
    if (range === 'month') {
      try {
        cycleStart = MonthlyCycle.start(await AppDb.settingsDao().getMonthlyReset(aid), Date.now())
      } catch (e) {
        cycleStart = null
      }
    }
    // 并发跑相互独立的 DB/汇率查询
    const parts = await Promise.all([
      this.usageDao.totals(range, aid, cycleStart),
      this.usageDao.totals('today', aid),
      this.usageDao.dailyStats(7, aid),
      this.usageDao.dailyStats(30, aid),
      this.usageDao.todayTrend(aid),
      this.usageDao.modelStats(range, aid, cycleStart),
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
    // 同步占位必须在任何 await 之前: 否则前台定时器与后台 WorkScheduler 并发触发时
    // 会双双通过 running 检查, 互踩进度状态 (desktop _sync_lock / android syncMutex parity)
    this._progress = { running: true, mode: mode, page: 0, inserted: 0, phase: 'usage', message: '', account: '' }

    const settings = await AppDb.settingsDao().getSettings()
    const windowDays: number | null = settings.windowDays

    try {
      let totalInserted = 0
      let pages = 0
      const errors: string[] = []
      let partial = false

      // 单账号失败不中断整轮 (与桌面 sync_usage / Android syncUsage 一致):
      // 否则首个 token 失效的账号会永久阻塞其后所有账号的自动同步
      for (const target of targets) {
        const aid = target[0]
        const name = target[1]
        this.updateProgress((p) => { p.account = name })
        const result = await this.syncOneAccount(aid, name, mode, windowDays)
        totalInserted += result.inserted
        pages += result.pages
        if (!result.ok) {
          errors.push(`[${name}] ${result.error !== null ? result.error : '同步失败'}`)
        }
        if (result.partial) {
          partial = true
        }
      }

      const anyError = errors.join('; ')
      if (errors.length === targets.length) {
        this.updateProgress((p) => { p.phase = 'error'; p.message = anyError })
        return { ok: false, error: anyError, inserted: totalInserted, pages: pages, partial: false, failedPages: 0 }
      }
      if (partial || errors.length > 0) {
        const msg = errors.length > 0 ? '部分账号同步异常' : '完成, 但部分页面拉取失败'
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

  /**
   * 同步单个账号的用量记录 (desktop server._sync_one_account parity)。
   *
   * /console/api/request-logs 为游标分页 (按时间倒序, 无法并发跳页): 顺序翻页,
   * 直到游标耗尽 / 触达同步范围边界 / 增量追平 (连续两批 0 新增)。
   * 旧实现的页码并发跳页 (fetchBatch) 是 /_server 时代的形态, 随 2026-09 改版下线。
   */
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
      // 页数上限对齐桌面 (_max_pages_for: full 1000 / incremental 10; 此前 2000/5 漂移)
      const maxPages = mode === 'full' ? 1000 : 10
      let page = 0
      let cursor: string | null = null
      let emptyPages = 0
      let failedPages = 0
      let windowBoundaryReached = false

      // 增量同步: 只取最新记录之后的一段时间 (重叠 1 小时防边界漏记),
      // 命中不到旧数据就不会去翻历史页, 既快又少请求
      let sinceMs: number | null = null
      if (mode !== 'full') {
        const newest = (await this.syncDao.getSyncStateFor(accountId)).newestRecordAt
        if (newest !== null && newest.length > 0) {
          const stamp = Date.parse(newest)
          if (!Number.isNaN(stamp)) {
            const overlap = stamp - 3600 * 1000
            if (overlap > 0) {
              sinceMs = overlap
            }
          }
        }
      }

      while (page < maxPages) {
        this.updateProgress((p) => { p.page = page })
        let usagePage: UsagePage
        try {
          usagePage = await OpenCodeApi.fetchUsagePage(token, workspaceId, cursor, sinceMs)
        } catch (e) {
          // 首页即失败 -> 整体报错; 翻页中途失败 -> 保留已入库数据标记 partial
          // (深页偶尔慢/连接被重置; 桌面同语义, 无游标重试路径)
          if (page === 0) {
            const msg = `[${name}] ${(e as Error).message}`
            await this.syncDao.updateSyncStateAndTotals(accountId, 'error', msg, 0)
            this.updateProgress((p) => { p.phase = 'error'; p.message = msg })
            return { ok: false, error: (e as Error).message, inserted: 0, pages: 0, partial: false, failedPages: 0 }
          }
          failedPages += 1
          break
        }
        page += 1
        const records = usagePage.records
        let inserted = 0
        if (records.length > 0) {
          // 同步范围: 全量拉取时, 若本页最早记录早于窗口边界 -> 该页保留后停止
          if (mode === 'full' && windowDays !== null) {
            let earliest = ''
            for (const r of records) {
              if (earliest.length === 0 || r.createdAt < earliest) {
                earliest = r.createdAt
              }
            }
            if (earliest.length > 0) {
              const et = Date.parse(earliest)
              const boundary = Date.now() - windowDays * 24 * 3600 * 1000
              if (!Number.isNaN(et) && et < boundary) {
                windowBoundaryReached = true
              }
            }
          }
          const syncedAt = new Date().toISOString()
          const entities: UsageRecordEntity[] = records.map((r) => toEntity(r, syncedAt, accountId))
          inserted = await this.usageDao.insertUsageRecords(entities, accountId)
          totalInserted += inserted
          this.updateProgress((p) => { p.inserted = totalInserted })
        }
        // 增量停止判定: 连续两批 0 新增 (空页同计) 即追平 (desktop _incremental_done parity)
        if (mode === 'incremental' && inserted === 0) {
          emptyPages += 1
          if (emptyPages >= 2) {
            break
          }
        } else {
          emptyPages = 0
        }
        cursor = usagePage.nextCursor
        if (cursor === null) {
          break // 已到最早一条
        }
        if (windowBoundaryReached) {
          break
        }
      }

      // 同步只按范围取数, 不裁剪本地存量: window_days 是取数范围, 不是保留期
      // (desktop 6995669 同语义: 过期数据由设置页「按同步范围清理」显式删除)

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
        const msg = '完成, 但翻页中断 (数据不完整, 可再次全量同步补全)'
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

  /** 配额刷新 + 用量同步; 返回同步结果文本供调用方展示 (full 模式必须可被触发, 见设置页说明). */
  async syncAll(mode: string): Promise<string> {
    await this.ensureQuota()
    const result = await this.syncUsage(mode)
    if (!result.ok) {
      return `同步失败: ${result.error !== null ? result.error : ''}`
    }
    if (result.partial) {
      return `同步完成（部分数据）: 新增 ${result.inserted} 条 / ${result.pages} 页`
    }
    return `同步完成: 新增 ${result.inserted} 条 / ${result.pages} 页`
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

  async settings(): Promise<AppSettings> {
    return AppDb.settingsDao().getSettings()
  }

  async saveSettings(patch: AppSettings): Promise<AppSettings> {
    return AppDb.settingsDao().saveSettings(patch)
  }

  /**
   * 「按同步范围清理」预演 (desktop db.prune_preview parity): [窗口天数, 边界, 待删数],
   * 跨账号不写库; 同步范围为「所有」(windowDays=null) 时返回 null (无需清理)。
   */
  async prunePreview(): Promise<[number, string, number] | null> {
    const wd = (await AppDb.settingsDao().getSettings()).windowDays
    if (wd === null) {
      return null
    }
    const cutoff = await this.usageDao.pruneCutoff(wd)
    return [wd, cutoff, await this.usageDao.prunePreviewCount(cutoff)]
  }

  /**
   * 按同步范围清理**所有账号**的过期记录 (desktop db.prune_expired parity)。
   * 删除不可恢复, 调用方负责二次确认; 删除后回填同步状态的总数/最老最新。
   */
  async pruneExpired(): Promise<number> {
    const wd = (await AppDb.settingsDao().getSettings()).windowDays
    if (wd === null) {
      return 0
    }
    const cutoff = await this.usageDao.pruneCutoff(wd)
    const deleted = await this.usageDao.pruneExpiredAll(cutoff)
    if (deleted > 0) {
      for (const acc of await this.syncDao.listAccounts()) {
        await this.syncDao.refreshSyncTotals(acc.id)
      }
    }
    return deleted
  }

  /** 退出登录当前活跃账号 (清其数据, 保留账号行)。 */
  async logout(): Promise<void> {
    await this.syncDao.clearAccount()
    // 清空配额缓存槽: 否则重新登录前 UI 可能取到上一个账号的残留配额
    // (Android DashboardRepository.logout 同做法)
    this.quotaCache.clear()
    // 清 WebView cookie 库: 登录时从 opencode.ai 读走的会话 cookie 会留在
    // 应用持久化 Web 数据里, 登出后仍可用 (Android LoginScreen 在捕获时就
    // removeAllCookies; 这里在登出侧兜底清理).
    await DashboardRepository.clearWebCookies()
  }

  /**
   * 清理 WebView 侧的会话 cookie (含 opencode.ai 登录态)。
   * 导入失败/无 webview 能力时静默跳过 (非致命, 不影响本地登出).
   */
  static async clearWebCookies(): Promise<void> {
    try {
      const webviewMod = await import('@ohos.web.webview')
      // clearAllCookiesSync: 同步清空 cookie 库 (API 8+);
      // 没有 removeAllCookies 这个成员, 名称写错会直接编译失败
      webviewMod.default.WebCookieManager.clearAllCookiesSync()
    } catch (e) {
      // WebView 不可用时无需清理
    }
  }

  /** 清除 injectSampleData 注入的调试记录 (debug 构建设置页入口), 返回删除条数。 */
  async clearSampleData(): Promise<number> {
    const deleted = await this.usageDao.clearSampleData()
    if (deleted > 0) {
      // 刷新同步统计口径, 使明细总数与新记录集一致
      const aid = await this.syncDao.getActiveAccountId()
      if (aid !== 0) {
        await this.syncDao.updateSyncStateAndTotals(aid, 'ok', null, 0)
      }
    }
    return deleted
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