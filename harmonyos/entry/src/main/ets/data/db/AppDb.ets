/**
 * RDB 单例 + schema —— db.py _init_schema (v2.0.0) 的 ArkTS 移植。
 * 四表: usage_records / accounts / usage_sync_state / settings, 字段与索引逐句对应。
 *
 * schema 版本: 用 PRAGMA user_version 记录 (与 Android Room 的 version 同义),
 * 新版本只追加迁移分支, 不再依赖 "CREATE TABLE IF NOT EXISTS 恰好够用".
 */
import { relationalStore } from '@kit.ArkData'
import { UsageDao } from './UsageDao'
import { SyncDao } from './SyncDao'
import { SettingsDao } from './SettingsDao'

/** 当前 schema 版本; 每次结构变更 +1 并在 migrate() 里补对应分支。 */
const SCHEMA_VERSION: number = 1

export class AppDb {
  private static _store: relationalStore.RdbStore | null = null
  /** init 并发守卫: UIAbility 与页面可能同时调用 init (此前 check-then-await 有竞态). */
  private static _initing: Promise<void> | null = null

  /** 需在 UIAbility/页面上下文可用后调用一次 (可重入, 并发调用共享同一 Promise)。 */
  static init(context: Context): Promise<void> {
    if (AppDb._store !== null) {
      return Promise.resolve()
    }
    if (AppDb._initing !== null) {
      return AppDb._initing
    }
    AppDb._initing = AppDb.doInit(context).then(() => {
      AppDb._initing = null
    }).catch((e: Error) => {
      AppDb._initing = null
      throw e
    })
    return AppDb._initing
  }

  private static async doInit(context: Context): Promise<void> {
    const config: relationalStore.StoreConfig = {
      name: 'gousage.db',
      // S2: 库内含登录凭证相关数据, 按敏感度要求取中档 (S1 面向公开数据)
      securityLevel: relationalStore.SecurityLevel.S2,
    }
    const store = await relationalStore.getRdbStore(context, config)
    await AppDb.createSchema(store)
    await AppDb.migrate(store)
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

  private static async readUserVersion(store: relationalStore.RdbStore): Promise<number> {
    const rs = await store.querySql('PRAGMA user_version')
    let v = 0
    if (rs.goToFirstRow()) {
      v = rs.getLong(0)
    }
    rs.close()
    return v
  }

  /**
   * 版本检查 + 迁移入口。
   *
   * 此前没有任何版本管理: 加列/改表只能靠 CREATE TABLE IF NOT EXISTS 的巧合,
   * 已存在的库不会补新列. 现在新结构必须在此登记迁移步骤.
   */
  private static async migrate(store: relationalStore.RdbStore): Promise<void> {
    const current = await AppDb.readUserVersion(store)
    if (current === SCHEMA_VERSION) {
      return
    }
    if (current > SCHEMA_VERSION) {
      // 降级安装 (装了更新的版本又回退): 继续跑旧代码可能读到不兼容结构, 明确报错
      throw new Error(`数据库版本 ${current} 高于当前应用支持的 ${SCHEMA_VERSION}, 请升级应用`)
    }
    // 逐版本升级: 目前只有 v0 -> v1 (首次引入版本号, 结构由 createSchema 保证)
    if (current < 1) {
      // v0 为无版本号的初始形态; 结构与 v1 一致 (createSchema 已建齐), 只需登记版本
    }
    await store.executeSql(`PRAGMA user_version = ${SCHEMA_VERSION}`)
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

    // 账号种子用 INSERT OR IGNORE: 两个并发的 init 同时读到 count=0 时,
    // 后到者会撞 accounts 主键 (此前为裸 INSERT)
    await store.executeSql(
      `INSERT OR IGNORE INTO accounts (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)
       VALUES (1, 'Default', 'Default', NULL, '', ?, ?)`,
      [now, now],
    )
  }
}