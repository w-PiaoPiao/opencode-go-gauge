/**
 * 账号 / 同步状态 / 活跃账号 DAO —— SyncDao.kt / ActiveAccountPolicy.kt 的 ArkTS 移植
 * (accounts 多行表 + usage_sync_state 按账号主键 + settings.payload.active_account_id)。
 */
import { AppDb } from './AppDb'
import { RowReader } from './RowReader'
import { SettingsDao } from './SettingsDao'
import { AccountInfo, SyncState, emptySyncState } from '../../common/model/Models'

export interface AccountRow {
  id: number
  name: string
  workspaceId: string
  resolvedWorkspaceId: string | null
  token: string
  createdAt: string
  updatedAt: string
}

export interface SyncStateRow {
  accountId: number
  lastSyncAt: string | null
  lastSyncStatus: string | null
  lastSyncError: string | null
  lastInsertedCount: number
  deepestPageFetched: number
  totalRecords: number
  oldestRecordAt: string | null
  newestRecordAt: string | null
}

function accountRowFromReader(r: RowReader): AccountRow {
  return {
    id: r.getLong('id'),
    name: r.getStr('name'),
    workspaceId: r.getStr('workspace_id'),
    resolvedWorkspaceId: r.isNull('resolved_workspace_id') ? null : r.getStr('resolved_workspace_id'),
    token: r.getStr('token'),
    createdAt: r.getStr('created_at'),
    updatedAt: r.getStr('updated_at'),
  }
}

function toInfo(row: AccountRow): AccountInfo {
  return {
    id: row.id,
    name: row.name,
    workspaceId: row.workspaceId,
    resolvedWorkspaceId: row.resolvedWorkspaceId,
    hasToken: row.token.trim().length > 0,
  }
}

export class SyncDao {
  private settings(): SettingsDao {
    return AppDb.settingsDao()
  }

  // ------------------------------------------------------------------
  // 账号行
  // ------------------------------------------------------------------

  async listAccountRows(): Promise<AccountRow[]> {
    const rs = await AppDb.store().querySql('SELECT * FROM accounts ORDER BY id ASC')
    const r = new RowReader(rs)
    const out: AccountRow[] = []
    while (r.next()) {
      out.push(accountRowFromReader(r))
    }
    r.close()
    return out
  }

  async accountRowById(id: number): Promise<AccountRow | null> {
    const rs = await AppDb.store().querySql('SELECT * FROM accounts WHERE id = ?', [id.toString()])
    const r = new RowReader(rs)
    let out: AccountRow | null = null
    if (r.next()) {
      out = accountRowFromReader(r)
    }
    r.close()
    return out
  }

  private async scalarInt(sql: string, args: Array<string> = []): Promise<number> {
    const rs = await AppDb.store().querySql(sql, args)
    const r = new RowReader(rs)
    let v = 0
    if (r.next()) {
      v = r.getLongAt(0)
    }
    r.close()
    return v
  }

  async minLoggedInId(): Promise<number> {
    return (await this.scalarInt('SELECT MIN(id) FROM accounts WHERE TRIM(token) != \'\''))
  }

  async minAnyId(): Promise<number> {
    return (await this.scalarInt('SELECT MIN(id) FROM accounts'))
  }

  async countAccounts(): Promise<number> {
    return this.scalarInt('SELECT COUNT(*) FROM accounts')
  }

  async countLoggedInAccounts(): Promise<number> {
    return this.scalarInt('SELECT COUNT(*) FROM accounts WHERE TRIM(token) != \'\'')
  }

  /** desktop add_account 显式取 MAX(id)+1 作主键 (保持 id 连续)。 */
  async nextAccountId(): Promise<number> {
    return (await this.scalarInt('SELECT COALESCE(MAX(id), 0) + 1 FROM accounts'))
  }

  async insertAccountRow(row: AccountRow): Promise<void> {
    await AppDb.store().executeSql(
      `INSERT INTO accounts (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [row.id.toString(), row.name, row.workspaceId, row.resolvedWorkspaceId, row.token, row.createdAt, row.updatedAt],
    )
  }

  async updateCredential(id: number, token: string, workspaceId: string, updatedAt: string): Promise<void> {
    await AppDb.store().executeSql(
      'UPDATE accounts SET token = ?, workspace_id = ?, resolved_workspace_id = NULL, updated_at = ? WHERE id = ?',
      [token, workspaceId, updatedAt, id.toString()],
    )
  }

  async updateWorkspaceHint(id: number, workspaceId: string, updatedAt: string): Promise<void> {
    await AppDb.store().executeSql(
      'UPDATE accounts SET workspace_id = ?, updated_at = ? WHERE id = ?',
      [workspaceId, updatedAt, id.toString()],
    )
  }

  async saveResolvedWorkspace(id: number, workspaceId: string, updatedAt: string): Promise<void> {
    await AppDb.store().executeSql(
      'UPDATE accounts SET resolved_workspace_id = ?, updated_at = ? WHERE id = ?',
      [workspaceId, updatedAt, id.toString()],
    )
  }

  async renameAccountRow(id: number, name: string, updatedAt: string): Promise<void> {
    await AppDb.store().executeSql(
      'UPDATE accounts SET name = ?, updated_at = ? WHERE id = ?',
      [name, updatedAt, id.toString()],
    )
  }

  async clearToken(id: number, updatedAt: string): Promise<void> {
    await AppDb.store().executeSql(
      'UPDATE accounts SET token = \'\', resolved_workspace_id = NULL, updated_at = ? WHERE id = ?',
      [updatedAt, id.toString()],
    )
  }

  async deleteAccountRow(id: number): Promise<void> {
    await AppDb.store().executeSql('DELETE FROM accounts WHERE id = ?', [id.toString()])
  }

  // ------------------------------------------------------------------
  // 活跃账号 (ActiveAccountPolicy 移植)
  // ------------------------------------------------------------------

  private static resolveActive(
    storedActiveId: number | null, accounts: Array<[number, boolean]>,
  ): number {
    let loggedMin = 0
    for (const a of accounts) {
      if (a[1] && (loggedMin === 0 || a[0] < loggedMin)) {
        loggedMin = a[0]
      }
    }
    if (storedActiveId !== null && storedActiveId > 0) {
      let row: [number, boolean] | null = null
      for (const a of accounts) {
        if (a[0] === storedActiveId) {
          row = a
          break
        }
      }
      if (row !== null) {
        if (row[1]) {
          return storedActiveId
        }
        if (loggedMin !== 0) {
          return loggedMin // 活跃行未登录但有其他已登录账号 -> 让位
        }
        return storedActiveId // 全部未登录: 维持原选择
      }
    }
    if (loggedMin !== 0) {
      return loggedMin
    }
    let fallback = 0
    for (const a of accounts) {
      if (fallback === 0 || a[0] < fallback) {
        fallback = a[0]
      }
    }
    return fallback
  }

  async getActiveAccountId(): Promise<number> {
    const rows = await this.listAccountRows()
    const stored = await this.settings().readActiveAccountId()
    const resolved = SyncDao.resolveActive(
      stored,
      rows.map((row) => [row.id, row.token.trim().length > 0] as [number, boolean]),
    )
    if (rows.length > 0 && resolved !== (stored !== null ? stored : 0)) {
      if (resolved > 0) {
        await this.settings().writeActiveAccountId(resolved)
      } else {
        await this.settings().removeActiveAccountId()
      }
    }
    return resolved
  }

  async setActiveAccount(accountId: number): Promise<boolean> {
    const row = await this.accountRowById(accountId)
    if (row === null) {
      return false
    }
    await this.settings().writeActiveAccountId(accountId)
    return true
  }

  // ------------------------------------------------------------------
  // 账号摘要 / CRUD
  // ------------------------------------------------------------------

  async getAccount(): Promise<AccountInfo | null> {
    const aid = await this.getActiveAccountId()
    if (aid === 0) {
      return null
    }
    const row = await this.accountRowById(aid)
    return row === null ? null : toInfo(row)
  }

  async listAccounts(): Promise<AccountInfo[]> {
    const rows = await this.listAccountRows()
    return rows.map((row) => toInfo(row))
  }

  /** 添加新账号; 相同 token 视为同一用户, 更新工作区提示后返回其 id。 */
  async addAccount(token: string, workspaceHint: string, switchNow: boolean = true): Promise<number> {
    const trimmed = token.trim()
    const hint = workspaceHint.trim()
    const now = new Date().toISOString()
    if (trimmed.length > 0) {
      const rows = await this.listAccountRows()
      for (const existing of rows) {
        if (existing.token.trim() === trimmed) {
          if (hint.length > 0) {
            await this.updateWorkspaceHint(existing.id, hint, now)
          }
          if (switchNow) {
            await this.settings().writeActiveAccountId(existing.id)
          }
          return existing.id
        }
      }
    }
    const newId = await this.nextAccountId()
    await this.insertAccountRow({
      id: newId,
      name: hint.slice(0, 50).length > 0 ? hint.slice(0, 50) : `User ${newId}`,
      workspaceId: hint.length > 0 ? hint : 'Default',
      resolvedWorkspaceId: null,
      token: trimmed,
      createdAt: now,
      updatedAt: now,
    })
    await this.ensureStateRow(newId)
    if (switchNow) {
      await this.settings().writeActiveAccountId(newId)
    }
    return newId
  }

  async renameAccount(accountId: number, name: string): Promise<boolean> {
    const cleaned = name.trim().slice(0, 50)
    if (cleaned.length === 0) {
      return false
    }
    await this.renameAccountRow(accountId, cleaned, new Date().toISOString())
    return true
  }

  /** 删除账号及其本地全部数据 (级联), 返回剩余账号数。 */
  async deleteAccount(accountId: number): Promise<number> {
    await AppDb.store().executeSql('DELETE FROM usage_records WHERE account_id = ?', [accountId.toString()])
    await AppDb.store().executeSql('DELETE FROM usage_sync_state WHERE account_id = ?', [accountId.toString()])
    await this.deleteAccountRow(accountId)
    const remaining = await this.countAccounts()
    const stored = await this.settings().readActiveAccountId()
    if (stored === accountId) {
      const nxt = await this.minAnyId()
      if (nxt !== 0) {
        await this.settings().writeActiveAccountId(nxt)
      } else {
        await this.settings().removeActiveAccountId()
      }
    }
    return remaining
  }

  /** 退出登录当前活跃账号: 清凭证与本地缓存数据 (保留账号行)。 */
  async clearAccount(): Promise<void> {
    const aid = await this.getActiveAccountId()
    if (aid === 0) {
      return
    }
    await AppDb.store().executeSql('DELETE FROM usage_records WHERE account_id = ?', [aid.toString()])
    await this.clearToken(aid, new Date().toISOString())
    await this.ensureStateRow(aid)
    await this.resetSyncStateForAccount(aid)
  }

  /** 重新登录语义: 更新活跃账号凭证并重置其增量游标。 */
  async saveToken(token: string, workspaceId: string): Promise<void> {
    const aid = await this.getActiveAccountId()
    if (aid === 0) {
      return
    }
    await this.updateCredential(aid, token.trim(), workspaceId.trim().length > 0 ? workspaceId.trim() : 'Default',
      new Date().toISOString())
    await this.ensureStateRow(aid)
    await this.resetCursorForAccount(aid)
  }

  // ------------------------------------------------------------------
  // 同步状态
  // ------------------------------------------------------------------

  async ensureStateRow(accountId: number): Promise<void> {
    const rs = await AppDb.store().querySql(
      'SELECT account_id FROM usage_sync_state WHERE account_id = ?', [accountId.toString()],
    )
    const r = new RowReader(rs)
    const exists = r.next()
    r.close()
    if (!exists) {
      await AppDb.store().executeSql(
        'INSERT INTO usage_sync_state (account_id, deepest_page_fetched) VALUES (?, -1)', [accountId.toString()],
      )
    }
  }

  async bumpSyncState(accountId: number, status: string, error: string | null, inserted: number, at: string): Promise<void> {
    await AppDb.store().executeSql(
      `UPDATE usage_sync_state
       SET last_sync_at = ?, last_sync_status = ?, last_sync_error = ?, last_inserted_count = last_inserted_count + ?
       WHERE account_id = ?`,
      [at, status, error, inserted.toString(), accountId.toString()],
    )
  }

  async resetSyncStateForAccount(accountId: number): Promise<void> {
    await AppDb.store().executeSql(
      `UPDATE usage_sync_state
       SET last_sync_status = NULL, last_sync_error = NULL, last_inserted_count = 0,
           deepest_page_fetched = -1, total_records = 0, oldest_record_at = NULL, newest_record_at = NULL
       WHERE account_id = ?`,
      [accountId.toString()],
    )
  }

  async resetCursorForAccount(accountId: number): Promise<void> {
    await AppDb.store().executeSql(
      'UPDATE usage_sync_state SET deepest_page_fetched = -1 WHERE account_id = ?', [accountId.toString()],
    )
  }

  private async recordBounds(accountId: number): Promise<[number, string | null, string | null]> {
    const rs = await AppDb.store().querySql(
      `SELECT COUNT(*) AS count, MIN(created_at) AS oldest, MAX(created_at) AS newest
       FROM usage_records WHERE account_id = ?`, [accountId.toString()],
    )
    const r = new RowReader(rs)
    let out: [number, string | null, string | null] = [0, null, null]
    if (r.next()) {
      out = [
        r.getLong('count'),
        r.isNull('oldest') ? null : r.getStr('oldest'),
        r.isNull('newest') ? null : r.getStr('newest'),
      ]
    }
    r.close()
    return out
  }

  /** 持久化同步结果并刷新 totals —— db.update_sync_state + _refresh_sync_totals。 */
  async updateSyncStateAndTotals(accountId: number, status: string, error: string | null, inserted: number): Promise<void> {
    await this.ensureStateRow(accountId)
    await this.bumpSyncState(accountId, status, error, inserted, new Date().toISOString())
    const b = await this.recordBounds(accountId)
    await AppDb.store().executeSql(
      'UPDATE usage_sync_state SET total_records = ?, oldest_record_at = ?, newest_record_at = ? WHERE account_id = ?',
      [b[0].toString(), b[1], b[2], accountId.toString()],
    )
  }

  async getSyncStateFor(accountId: number): Promise<SyncState> {
    const rs = await AppDb.store().querySql(
      'SELECT * FROM usage_sync_state WHERE account_id = ?', [accountId.toString()],
    )
    const r = new RowReader(rs)
    let out: SyncState = emptySyncState()
    if (r.next()) {
      out = {
        lastSyncAt: r.isNull('last_sync_at') ? null : r.getStr('last_sync_at'),
        lastSyncStatus: r.isNull('last_sync_status') ? null : r.getStr('last_sync_status'),
        lastSyncError: r.isNull('last_sync_error') ? null : r.getStr('last_sync_error'),
        lastInsertedCount: r.getLong('last_inserted_count'),
        deepestPageFetched: r.getLong('deepest_page_fetched'),
        totalRecords: r.getLong('total_records'),
        oldestRecordAt: r.isNull('oldest_record_at') ? null : r.getStr('oldest_record_at'),
        newestRecordAt: r.isNull('newest_record_at') ? null : r.getStr('newest_record_at'),
      }
    }
    r.close()
    return out
  }

  async getSyncState(): Promise<SyncState> {
    return this.getSyncStateFor(await this.getActiveAccountId())
  }

  async getTokenFor(accountId: number): Promise<string> {
    const row = await this.accountRowById(accountId)
    return row === null ? '' : row.token.trim()
  }

  async getWorkspaceHintFor(accountId: number): Promise<string> {
    const row = await this.accountRowById(accountId)
    if (row === null) {
      return 'Default'
    }
    if (row.resolvedWorkspaceId !== null && row.resolvedWorkspaceId.length > 0) {
      return row.resolvedWorkspaceId
    }
    return row.workspaceId.length > 0 ? row.workspaceId : 'Default'
  }
}