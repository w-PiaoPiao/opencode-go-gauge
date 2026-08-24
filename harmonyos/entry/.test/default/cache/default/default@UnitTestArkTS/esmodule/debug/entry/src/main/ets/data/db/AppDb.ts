import relationalStore from "@ohos:data.relationalStore";
import { UsageDao } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/UsageDao";
import { SyncDao } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/SyncDao";
import { SettingsDao } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/SettingsDao";
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
let bjccovmt7djxwe = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/db/AppDb.ets", hash: "3c1f1079334a0a890347b46cc9fe7f4ae687ddeb16e114d967228f3e3ead8793", lineCnt: 129, count: 0, projectPath: "", functions: { 0: { name: "AppDb.init", count: 0, regions: { 0: { startLoc: { line: 14, col: 3 }, endLoc: { line: 26, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 15, col: 32 }, endLoc: { line: 17, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 18, col: 5 }, endLoc: { line: 26, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 15, col: 9 }, endLoc: { line: 15, col: 30 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 0 }, 1: { name: "AppDb.isReady", count: 0, regions: { 0: { startLoc: { line: 28, col: 3 }, endLoc: { line: 30, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 29, col: 5 }, endLoc: { line: 30, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "AppDb.store", count: 0, regions: { 0: { startLoc: { line: 32, col: 3 }, endLoc: { line: 37, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 33, col: 32 }, endLoc: { line: 35, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 36, col: 5 }, endLoc: { line: 37, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 33, col: 9 }, endLoc: { line: 33, col: 30 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 }, 3: { name: "AppDb.usageDao", count: 0, regions: { 0: { startLoc: { line: 39, col: 3 }, endLoc: { line: 41, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 40, col: 5 }, endLoc: { line: 41, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 3 }, 4: { name: "AppDb.syncDao", count: 0, regions: { 0: { startLoc: { line: 43, col: 3 }, endLoc: { line: 45, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 44, col: 5 }, endLoc: { line: 45, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 4 }, 5: { name: "AppDb.settingsDao", count: 0, regions: { 0: { startLoc: { line: 47, col: 3 }, endLoc: { line: 49, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 48, col: 5 }, endLoc: { line: 49, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 5 }, 6: { name: "AppDb.createSchema", count: 0, regions: { 0: { startLoc: { line: 51, col: 3 }, endLoc: { line: 104, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 101, col: 5 }, endLoc: { line: 103, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 6 }, 7: { name: "AppDb.seed", count: 0, regions: { 0: { startLoc: { line: 107, col: 3 }, endLoc: { line: 128, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 110, col: 37 }, endLoc: { line: 112, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 117, col: 38 }, endLoc: { line: 119, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 121, col: 22 }, endLoc: { line: 127, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 110, col: 9 }, endLoc: { line: 110, col: 35 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 117, col: 9 }, endLoc: { line: 117, col: 36 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 121, col: 9 }, endLoc: { line: 121, col: 20 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 7 } }, exeLine: { 0: 5, 1: 6, 2: 7, 3: 8, 4: 10, 5: 11, 6: 14, 7: 15, 8: 16, 9: 18, 10: 19, 11: 20, 12: 22, 13: 23, 14: 24, 15: 25, 16: 28, 17: 29, 18: 32, 19: 33, 20: 34, 21: 36, 22: 39, 23: 40, 24: 43, 25: 44, 26: 47, 27: 48, 28: 51, 29: 52, 30: 53, 31: 72, 32: 73, 33: 74, 34: 75, 35: 84, 36: 95, 37: 101, 38: 102, 39: 107, 40: 108, 41: 109, 42: 110, 43: 111, 44: 113, 45: 115, 46: 116, 47: 117, 48: 118, 49: 120, 50: 121, 51: 122, 52: 123, 53: 125 } });
export class AppDb {
    private static _store: relationalStore.RdbStore | null = null;
    /** 需在 UIAbility/页面上下文可用后调用一次。 */
    static async init(context: Context): Promise<void> {
        bjccovmt7djxwe.instrumentFunction(0);
        if (AppDb._store !== null) {
            bjccovmt7djxwe.instrumentBranch(0, 0, true);
            bjccovmt7djxwe.instrumentRegion(0, 1);
            return;
        }
        else {
            bjccovmt7djxwe.instrumentBranch(0, 0, false);
        }
        bjccovmt7djxwe.instrumentRegion(0, 2);
        const config: relationalStore.StoreConfig = {
            name: 'gousage.db',
            securityLevel: relationalStore.SecurityLevel.S1,
        };
        const store = await relationalStore.getRdbStore(context, config);
        await AppDb.createSchema(store);
        AppDb._store = store;
        await AppDb.seed(store);
    }
    static isReady(): boolean {
        bjccovmt7djxwe.instrumentFunction(1);
        bjccovmt7djxwe.instrumentRegion(1, 1);
        return AppDb._store !== null;
    }
    static store(): relationalStore.RdbStore {
        bjccovmt7djxwe.instrumentFunction(2);
        if (AppDb._store === null) {
            bjccovmt7djxwe.instrumentBranch(2, 0, true);
            bjccovmt7djxwe.instrumentRegion(2, 1);
            throw new Error('AppDb not initialized');
        }
        else {
            bjccovmt7djxwe.instrumentBranch(2, 0, false);
        }
        bjccovmt7djxwe.instrumentRegion(2, 2);
        return AppDb._store;
    }
    static usageDao(): UsageDao {
        bjccovmt7djxwe.instrumentFunction(3);
        bjccovmt7djxwe.instrumentRegion(3, 1);
        return new UsageDao();
    }
    static syncDao(): SyncDao {
        bjccovmt7djxwe.instrumentFunction(4);
        bjccovmt7djxwe.instrumentRegion(4, 1);
        return new SyncDao();
    }
    static settingsDao(): SettingsDao {
        bjccovmt7djxwe.instrumentFunction(5);
        bjccovmt7djxwe.instrumentRegion(5, 1);
        return new SettingsDao();
    }
    private static async createSchema(store: relationalStore.RdbStore): Promise<void> {
        bjccovmt7djxwe.instrumentFunction(6);
        const ddl: string[] = [
            `CREATE TABLE IF NOT EXISTS usage_records (
         usg_id TEXT PRIMARY KEY,
         created_at TEXT NOT NULL,
         model TEXT NOT NULL,
         provider TEXT,
         input_tokens INTEGER NOT NULL,
         output_tokens INTEGER NOT NULL,
         reasoning_tokens INTEGER NOT NULL DEFAULT 0,
         cache_read_tokens INTEGER NOT NULL DEFAULT 0,
         cache_write_5m_tokens INTEGER NOT NULL DEFAULT 0,
         cache_write_1h_tokens INTEGER NOT NULL DEFAULT 0,
         cost_raw INTEGER NOT NULL,
         cost_usd REAL NOT NULL,
         key_id TEXT,
         session_id TEXT,
         plan TEXT,
         synced_at TEXT NOT NULL,
         account_id INTEGER NOT NULL DEFAULT 1
       )`,
            `CREATE INDEX IF NOT EXISTS idx_usage_time ON usage_records(created_at DESC)`,
            `CREATE INDEX IF NOT EXISTS idx_usage_session ON usage_records(session_id)`,
            `CREATE INDEX IF NOT EXISTS idx_usage_account_time ON usage_records(account_id, created_at DESC)`,
            `CREATE TABLE IF NOT EXISTS accounts (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT NOT NULL DEFAULT 'Default',
         workspace_id TEXT NOT NULL DEFAULT 'Default',
         resolved_workspace_id TEXT,
         token TEXT NOT NULL DEFAULT '',
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL
       )`,
            `CREATE TABLE IF NOT EXISTS usage_sync_state (
         account_id INTEGER PRIMARY KEY,
         last_sync_at TEXT,
         last_sync_status TEXT,
         last_sync_error TEXT,
         last_inserted_count INTEGER NOT NULL DEFAULT 0,
         deepest_page_fetched INTEGER NOT NULL DEFAULT -1,
         total_records INTEGER NOT NULL DEFAULT 0,
         oldest_record_at TEXT,
         newest_record_at TEXT
       )`,
            `CREATE TABLE IF NOT EXISTS settings (
         id INTEGER PRIMARY KEY CHECK (id = 1),
         payload TEXT NOT NULL,
         updated_at TEXT NOT NULL
       )`,
        ];
        for (const sql of ddl) {
            bjccovmt7djxwe.instrumentRegion(6, 1);
            await store.executeSql(sql);
        }
    }
    /** 种子行: settings 单行 + 默认空账号 (未登录态, 与历史行为一致)。 */
    private static async seed(store: relationalStore.RdbStore): Promise<void> {
        bjccovmt7djxwe.instrumentFunction(7);
        const now = new Date().toISOString();
        const settingsRow = await store.querySql('SELECT id FROM settings WHERE id = 1');
        if (settingsRow.rowCount === 0) {
            bjccovmt7djxwe.instrumentBranch(7, 0, true);
            bjccovmt7djxwe.instrumentRegion(7, 1);
            await store.executeSql('INSERT INTO settings (id, payload, updated_at) VALUES (1, ?, ?)', ['{}', now]);
        }
        else {
            bjccovmt7djxwe.instrumentBranch(7, 0, false);
        }
        settingsRow.close();
        const accountCount = await store.querySql('SELECT COUNT(*) AS c FROM accounts');
        let count = 0;
        if (accountCount.goToFirstRow()) {
            bjccovmt7djxwe.instrumentBranch(7, 1, true);
            bjccovmt7djxwe.instrumentRegion(7, 2);
            count = accountCount.getLong(0);
        }
        else {
            bjccovmt7djxwe.instrumentBranch(7, 1, false);
        }
        accountCount.close();
        if (count === 0) {
            bjccovmt7djxwe.instrumentBranch(7, 2, true);
            bjccovmt7djxwe.instrumentRegion(7, 3);
            await store.executeSql(`INSERT INTO accounts (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)
         VALUES (1, 'Default', 'Default', NULL, '', ?, ?)`, [now, now]);
        }
        else {
            bjccovmt7djxwe.instrumentBranch(7, 2, false);
        }
    }
}
