/**
 * RDB 单例 + schema —— db.py _init_schema (v2.0.0) 的 ArkTS 移植。
 * 四表: usage_records / accounts / usage_sync_state / settings, 字段与索引逐句对应。
 */
import { relationalStore } from '@kit.ArkData'
import { UsageDao } from './UsageDao'
import { SyncDao } from './SyncDao'
import { SettingsDao } from './SettingsDao'

export class AppDb {
  private static _store: relationalStore.RdbStore | null = null

  /** 需在 UIAbility/页面上下文可用后调用一次。 */
  static async init(context: Context): Promise<void> {
    if (AppDb._store !== null) {
      return
    }
    const config: relationalStore.StoreConfig = {
      name: 'gousage.db',
      securityLevel: relationalStore.SecurityLevel.S1,
    }
    const store = await relationalStore.getRdbStore(context, config)
    await AppDb.createSchema(store)
    AppDb._store = store
    await AppDb.seed(store)
  }

  static isReady(): boolean {
    return AppDb._store !== null
  }

  static store(): relationalStore.RdbStore {
    if (AppDb._store === null) {
      throw new Error('AppDb not initialized')
    }
    return AppDb._store
  }

  static usageDao(): UsageDao {
    return new UsageDao()
  }

  static syncDao(): SyncDao {
    return new SyncDao()
  }

  static settingsDao(): SettingsDao {
    return new SettingsDao()
  }

  private static async createSchema(store: relationalStore.RdbStore): Promise<void> {
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
    ]
    for (const sql of ddl) {
      await store.executeSql(sql)
    }
  }

  /** 种子行: settings 单行 + 默认空账号 (未登录态, 与历史行为一致)。 */
  private static async seed(store: relationalStore.RdbStore): Promise<void> {
    const now = new Date().toISOString()
    const settingsRow = await store.querySql('SELECT id FROM settings WHERE id = 1')
    if (settingsRow.rowCount === 0) {
      await store.executeSql('INSERT INTO settings (id, payload, updated_at) VALUES (1, ?, ?)', ['{}', now])
    }
    settingsRow.close()

    const accountCount = await store.querySql('SELECT COUNT(*) AS c FROM accounts')
    let count = 0
    if (accountCount.goToFirstRow()) {
      count = accountCount.getLong(0)
    }
    accountCount.close()
    if (count === 0) {
      await store.executeSql(
        `INSERT INTO accounts (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)
         VALUES (1, 'Default', 'Default', NULL, '', ?, ?)`,
        [now, now],
      )
    }
  }
}