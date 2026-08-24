/**
 * 数据模型 —— android data/model/*.kt 的 ArkTS 移植 (int/long/double 统一用 number)。
 */

/** 配额窗口 —— 对齐 opencode_api.QuotaWindow (desktop)。 */
export interface QuotaWindow {
  label: string
  used: number          // percent 0-100
  remaining: number     // percent
  total: number
  unit: string
  resetAt: string       // ISO
  resetInSec: number
}

/** 配额抓取结果 —— 对齐 opencode_api.QuotaResult (desktop)。 */
export interface QuotaResult {
  name: string
  workspaceId: string
  success: boolean
  updatedAt: string
  windows: QuotaWindow[]
  error: string | null
}

/** 一条用量记录 —— 对齐 opencode_api.UsageRecord (desktop)。 */
export interface UsageRecord {
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
  costRaw: number       // 单位 1e-8 USD
  keyId: string
  sessionId: string
  plan: string | null
}

/** 用量记录列表行 —— 对齐 db.usage_records_page 输出。 */
export interface UsageRecordRow {
  usgId: string
  createdAt: string
  model: string
  provider: string | null
  inputTokens: number
  outputTokens: number
  reasoningTokens: number
  cacheReadTokens: number
  cacheWriteTokens: number
  costUsd: number
  sessionId: string | null
  plan: string | null
  keyId: string | null
  keyName: string | null
}

/** 会话聚合行 —— 对齐 db.session_stats_page 输出。 */
export interface SessionStat {
  sessionId: string
  requestCount: number
  totalInputTokens: number
  uncachedInputTokens: number
  totalOutputTokens: number
  totalReasoningTokens: number
  totalCostUsd: number
  lastAt: string
  keyId: string | null
  keyName: string | null
}

/** 分页结果。 */
export interface PageResult<T> {
  records: T[]
  total: number
}

/** 聚合总计 —— 对齐 db.totals() 输出。 */
export interface Totals {
  requestCount: number
  sessionCount: number
  totalInputTokens: number   // input + cache read + cache write
  uncachedInputTokens: number
  totalReasoningTokens: number
  cacheHitTokens: number
  cacheWriteTokens: number
  totalOutputTokens: number
  totalCostUsd: number
  hitRate: number            // percent
  totalTokens: number        // totalInputTokens + totalOutputTokens + totalReasoningTokens
}

/** 单日聚合 —— 对齐 db.daily_stats 输出。 */
export interface DailyStat {
  date: string
  totalInputTokens: number
  uncachedInputTokens: number
  totalReasoningTokens: number
  cacheHitTokens: number
  cacheWriteTokens: number
  totalOutputTokens: number
  totalCostUsd: number
  requestCount: number
  hitRate: number
}

/** 今日某小时 —— 对齐 db.today_trend 输出。 */
export interface HourStat {
  hour: string
  input: number
  output: number
  reasoning: number
}

/** 单模型聚合 —— 对齐 db.model_stats 输出。 */
export interface ModelStat {
  model: string
  requestCount: number
  sessionCount: number
  totalInputTokens: number
  uncachedInputTokens: number
  totalReasoningTokens: number
  cacheHitTokens: number
  cacheWriteTokens: number
  totalOutputTokens: number
  totalCostUsd: number
  hitRate: number
}

/** 同步元数据 —— 对齐 db.get_sync_state 输出。 */
export interface SyncState {
  lastSyncAt: string | null
  lastSyncStatus: string | null
  lastSyncError: string | null
  lastInsertedCount: number
  deepestPageFetched: number
  totalRecords: number
  oldestRecordAt: string | null
  newestRecordAt: string | null
}

/** 进行中的同步进度 —— 对齐 server._sync_state。 */
export interface SyncProgress {
  running: boolean
  mode: string
  page: number
  inserted: number
  phase: string   // idle | quota | usage | done | error
  message: string
  account: string
}

/** 应用设置 —— 对齐 db._DEFAULT_SETTINGS。 */
export interface AppSettings {
  syncIntervalSec: number   // 1/5/15/30 min
  windowDays: number | null // 30/60/90/180, null = all
  autoSync: boolean
}

/** Dashboard 数据包 —— 对齐 GET /api/dashboard。 */
export interface DashboardData {
  loggedIn: boolean
  quota: QuotaResult | null
  totals: Totals
  today: Totals
  daily: DailyStat[]
  trend: DailyStat[]
  todayTrend: HourStat[]
  models: ModelStat[]
  sync: SyncState
  progress: SyncProgress
  range: string
  usdCny: number
  serverTime: string
}

/** 账号摘要 —— 对齐 db._account_dict (desktop v2.0.0)。 */
export interface AccountInfo {
  id: number
  name: string
  workspaceId: string
  resolvedWorkspaceId: string | null
  hasToken: boolean
}

/** 同步结果 —— 对齐 server.py sync_usage 返回。 */
export interface SyncResult {
  ok: boolean
  error: string | null
  inserted: number
  pages: number
  partial: boolean
  failedPages: number
}

/** GitHub 更新检查结果。 */
export interface UpdateInfo {
  hasUpdate: boolean
  current: string
  latest: string
  releaseUrl: string
  notes: string
}

/** 模型工厂: 缺省对象。 */
export function emptySyncState(): SyncState {
  return {
    lastSyncAt: null,
    lastSyncStatus: null,
    lastSyncError: null,
    lastInsertedCount: 0,
    deepestPageFetched: -1,
    totalRecords: 0,
    oldestRecordAt: null,
    newestRecordAt: null,
  }
}

export function emptySyncProgress(): SyncProgress {
  return { running: false, mode: '', page: 0, inserted: 0, phase: 'idle', message: '', account: '' }
}

export function defaultSettings(): AppSettings {
  return { syncIntervalSec: 300, windowDays: 60, autoSync: true }
}