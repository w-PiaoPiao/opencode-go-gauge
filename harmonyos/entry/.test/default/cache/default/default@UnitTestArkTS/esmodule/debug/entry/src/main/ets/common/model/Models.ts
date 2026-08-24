class BjcCov {
    coverage: {
        [key: string]: string | number;
    };
    constructor(covData: object) {
        const gcv = "__coverage__";
        let coverage = globalThis[gcv] || (globalThis[gcv] = {});
        if (!coverage[covData.path] && true) {
            coverage[covData.path] = covData;
        }
        this.coverage = coverage[covData.path];
    }
    instrumentFunction(func: number) {
        this.coverage.functions[func].count++;
        this.coverage.functions[func].regions[0].count++;
    }
    instrumentRegion(func: number, region: number) {
        this.coverage.functions[func].regions[region].count++;
    }
    instrumentReturn(func: number, retIdx: number) {
        this.coverage.functions[func].returnes[retIdx].count++;
    }
    instrumentBranch(func: number, branch: number, trueOrFalse: boolean) {
        if (trueOrFalse) {
            this.coverage.functions[func].branches[branch].trueCount++;
            for (let r of Object.values(this.coverage.functions[func].branches[branch].group)) {
                if (r !== branch) {
                    this.coverage.functions[func].branches[r as number].falseCount++;
                }
            }
        }
        else {
            this.coverage.functions[func].branches[branch].falseCount++;
        }
    }
}
let bjccovmt7djy3c = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/common/model/Models.ets", hash: "c31a969f250e136415a67297b21fe9bbfb36d4061004388cff605105f5e1e15b", lineCnt: 229, count: 0, projectPath: "", functions: { 0: { name: "emptySyncState", count: 0, regions: { 0: { startLoc: { line: 210, col: 1 }, endLoc: { line: 221, col: 2 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 211, col: 3 }, endLoc: { line: 221, col: 2 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "emptySyncProgress", count: 0, regions: { 0: { startLoc: { line: 223, col: 1 }, endLoc: { line: 225, col: 2 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 224, col: 3 }, endLoc: { line: 225, col: 2 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "defaultSettings", count: 0, regions: { 0: { startLoc: { line: 227, col: 1 }, endLoc: { line: 229, col: 2 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 228, col: 3 }, endLoc: { line: 229, col: 2 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 2 } }, exeLine: { 0: 6, 1: 7, 2: 8, 3: 9, 4: 10, 5: 11, 6: 12, 7: 13, 8: 17, 9: 18, 10: 19, 11: 20, 12: 21, 13: 22, 14: 23, 15: 27, 16: 28, 17: 29, 18: 30, 19: 31, 20: 32, 21: 33, 22: 34, 23: 35, 24: 36, 25: 37, 26: 38, 27: 39, 28: 40, 29: 41, 30: 45, 31: 46, 32: 47, 33: 48, 34: 49, 35: 50, 36: 51, 37: 52, 38: 53, 39: 54, 40: 55, 41: 56, 42: 57, 43: 58, 44: 59, 45: 63, 46: 64, 47: 65, 48: 66, 49: 67, 50: 68, 51: 69, 52: 70, 53: 71, 54: 72, 55: 73, 56: 77, 57: 78, 58: 79, 59: 83, 60: 84, 61: 85, 62: 86, 63: 87, 64: 88, 65: 89, 66: 90, 67: 91, 68: 92, 69: 93, 70: 94, 71: 98, 72: 99, 73: 100, 74: 101, 75: 102, 76: 103, 77: 104, 78: 105, 79: 106, 80: 107, 81: 108, 82: 112, 83: 113, 84: 114, 85: 115, 86: 116, 87: 120, 88: 121, 89: 122, 90: 123, 91: 124, 92: 125, 93: 126, 94: 127, 95: 128, 96: 129, 97: 130, 98: 131, 99: 135, 100: 136, 101: 137, 102: 138, 103: 139, 104: 140, 105: 141, 106: 142, 107: 143, 108: 147, 109: 148, 110: 149, 111: 150, 112: 151, 113: 152, 114: 153, 115: 154, 116: 158, 117: 159, 118: 160, 119: 161, 120: 165, 121: 166, 122: 167, 123: 168, 124: 169, 125: 170, 126: 171, 127: 172, 128: 173, 129: 174, 130: 175, 131: 176, 132: 177, 133: 178, 134: 182, 135: 183, 136: 184, 137: 185, 138: 186, 139: 187, 140: 191, 141: 192, 142: 193, 143: 194, 144: 195, 145: 196, 146: 197, 147: 201, 148: 202, 149: 203, 150: 204, 151: 205, 152: 206, 153: 210, 154: 211, 155: 212, 156: 213, 157: 214, 158: 215, 159: 216, 160: 217, 161: 218, 162: 219, 163: 223, 164: 224, 165: 227, 166: 228 } });
/**
 * 数据模型 —— android data/model/*.kt 的 ArkTS 移植 (int/long/double 统一用 number)。
 */
/** 配额窗口 —— 对齐 opencode_api.QuotaWindow (desktop)。 */
export interface QuotaWindow {
    label: string;
    used: number; // percent 0-100
    remaining: number; // percent
    total: number;
    unit: string;
    resetAt: string; // ISO
    resetInSec: number;
}
/** 配额抓取结果 —— 对齐 opencode_api.QuotaResult (desktop)。 */
export interface QuotaResult {
    name: string;
    workspaceId: string;
    success: boolean;
    updatedAt: string;
    windows: QuotaWindow[];
    error: string | null;
}
/** 一条用量记录 —— 对齐 opencode_api.UsageRecord (desktop)。 */
export interface UsageRecord {
    usgId: string;
    createdAt: string;
    model: string;
    provider: string;
    inputTokens: number;
    outputTokens: number;
    reasoningTokens: number;
    cacheReadTokens: number;
    cacheWrite5mTokens: number;
    cacheWrite1hTokens: number;
    costRaw: number; // 单位 1e-8 USD
    keyId: string;
    sessionId: string;
    plan: string | null;
}
/** 用量记录列表行 —— 对齐 db.usage_records_page 输出。 */
export interface UsageRecordRow {
    usgId: string;
    createdAt: string;
    model: string;
    provider: string | null;
    inputTokens: number;
    outputTokens: number;
    reasoningTokens: number;
    cacheReadTokens: number;
    cacheWriteTokens: number;
    costUsd: number;
    sessionId: string | null;
    plan: string | null;
    keyId: string | null;
    keyName: string | null;
}
/** 会话聚合行 —— 对齐 db.session_stats_page 输出。 */
export interface SessionStat {
    sessionId: string;
    requestCount: number;
    totalInputTokens: number;
    uncachedInputTokens: number;
    totalOutputTokens: number;
    totalReasoningTokens: number;
    totalCostUsd: number;
    lastAt: string;
    keyId: string | null;
    keyName: string | null;
}
/** 分页结果。 */
export interface PageResult<T> {
    records: T[];
    total: number;
}
/** 聚合总计 —— 对齐 db.totals() 输出。 */
export interface Totals {
    requestCount: number;
    sessionCount: number;
    totalInputTokens: number; // input + cache read + cache write
    uncachedInputTokens: number;
    totalReasoningTokens: number;
    cacheHitTokens: number;
    cacheWriteTokens: number;
    totalOutputTokens: number;
    totalCostUsd: number;
    hitRate: number; // percent
    totalTokens: number; // totalInputTokens + totalOutputTokens + totalReasoningTokens
}
/** 单日聚合 —— 对齐 db.daily_stats 输出。 */
export interface DailyStat {
    date: string;
    totalInputTokens: number;
    uncachedInputTokens: number;
    totalReasoningTokens: number;
    cacheHitTokens: number;
    cacheWriteTokens: number;
    totalOutputTokens: number;
    totalCostUsd: number;
    requestCount: number;
    hitRate: number;
}
/** 今日某小时 —— 对齐 db.today_trend 输出。 */
export interface HourStat {
    hour: string;
    input: number;
    output: number;
    reasoning: number;
}
/** 单模型聚合 —— 对齐 db.model_stats 输出。 */
export interface ModelStat {
    model: string;
    requestCount: number;
    sessionCount: number;
    totalInputTokens: number;
    uncachedInputTokens: number;
    totalReasoningTokens: number;
    cacheHitTokens: number;
    cacheWriteTokens: number;
    totalOutputTokens: number;
    totalCostUsd: number;
    hitRate: number;
}
/** 同步元数据 —— 对齐 db.get_sync_state 输出。 */
export interface SyncState {
    lastSyncAt: string | null;
    lastSyncStatus: string | null;
    lastSyncError: string | null;
    lastInsertedCount: number;
    deepestPageFetched: number;
    totalRecords: number;
    oldestRecordAt: string | null;
    newestRecordAt: string | null;
}
/** 进行中的同步进度 —— 对齐 server._sync_state。 */
export interface SyncProgress {
    running: boolean;
    mode: string;
    page: number;
    inserted: number;
    phase: string; // idle | quota | usage | done | error
    message: string;
    account: string;
}
/** 应用设置 —— 对齐 db._DEFAULT_SETTINGS。 */
export interface AppSettings {
    syncIntervalSec: number; // 1/5/15/30 min
    windowDays: number | null; // 30/60/90/180, null = all
    autoSync: boolean;
}
/** Dashboard 数据包 —— 对齐 GET /api/dashboard。 */
export interface DashboardData {
    loggedIn: boolean;
    quota: QuotaResult | null;
    totals: Totals;
    today: Totals;
    daily: DailyStat[];
    trend: DailyStat[];
    todayTrend: HourStat[];
    models: ModelStat[];
    sync: SyncState;
    progress: SyncProgress;
    range: string;
    usdCny: number;
    serverTime: string;
}
/** 账号摘要 —— 对齐 db._account_dict (desktop v2.0.0)。 */
export interface AccountInfo {
    id: number;
    name: string;
    workspaceId: string;
    resolvedWorkspaceId: string | null;
    hasToken: boolean;
}
/** 同步结果 —— 对齐 server.py sync_usage 返回。 */
export interface SyncResult {
    ok: boolean;
    error: string | null;
    inserted: number;
    pages: number;
    partial: boolean;
    failedPages: number;
}
/** GitHub 更新检查结果。 */
export interface UpdateInfo {
    hasUpdate: boolean;
    current: string;
    latest: string;
    releaseUrl: string;
    notes: string;
}
/** 模型工厂: 缺省对象。 */
export function emptySyncState(): SyncState {
    bjccovmt7djy3c.instrumentFunction(0);
    bjccovmt7djy3c.instrumentRegion(0, 1);
    return {
        lastSyncAt: null,
        lastSyncStatus: null,
        lastSyncError: null,
        lastInsertedCount: 0,
        deepestPageFetched: -1,
        totalRecords: 0,
        oldestRecordAt: null,
        newestRecordAt: null,
    };
}
export function emptySyncProgress(): SyncProgress {
    bjccovmt7djy3c.instrumentFunction(1);
    bjccovmt7djy3c.instrumentRegion(1, 1);
    return { running: false, mode: '', page: 0, inserted: 0, phase: 'idle', message: '', account: '' };
}
export function defaultSettings(): AppSettings {
    bjccovmt7djy3c.instrumentFunction(2);
    bjccovmt7djy3c.instrumentRegion(2, 1);
    return { syncIntervalSec: 300, windowDays: 60, autoSync: true };
}
