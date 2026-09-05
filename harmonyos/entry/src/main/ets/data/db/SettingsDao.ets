/**
 * settings 表 (JSON payload 行) 的访问层 —— SettingsDao.kt 的 ArkTS 移植。
 *
 * payload 为单行 JSON 文本: 读用 JSON.parse (坏文本容错回退默认),
 * 写在既有对象上覆盖已知键并保留未知键, JSON.stringify 负责转义
 * (旧手写拼接不转义控制字符且 patch=null 时会把已保存设置重置为默认值, 均已修复)。
 */
import { AppDb } from './AppDb'
import { RowReader } from './RowReader'
import { AppSettings, defaultSettings } from '../../common/model/Models'

export interface PayloadData {
  syncIntervalSec: number
  windowDays: number | null
  autoSync: boolean
  activeAccountId: number | null
  keyNames: Map<string, string>
}

export class SettingsDao {
  // 写侧串行队列: payload 是读-改-写的整包 JSON, 并发写会互相覆盖丢键
  // (desktop db._payload_lock / android PayloadLock parity)。
  // ArkTS 单线程事件循环内用 Promise 尾挂实现互斥, 单次写失败不阻断后续写。
  private static writeQueue: Promise<void> = Promise.resolve()

  private enqueueWrite(write: () => Promise<void>): Promise<void> {
    const task = SettingsDao.writeQueue.then(write)
    SettingsDao.writeQueue = task.then(
      () => undefined,
      () => undefined,
    )
    return task
  }

  private static parsePayload(raw: string): Record<string, Object | null> {
    let obj: Record<string, Object | null> = {}
    try {
      if (raw.length > 0) {
        obj = JSON.parse(raw) as Record<string, Object | null>
      }
    } catch (e) {
      // 坏文本回退空对象: 仅丢未知键, 已知键按默认值重建
    }
    return obj
  }

  /** 从 payload JSON 文本解析已知键 (容错: 缺键/坏文本回退默认)。 */
  static decode(raw: string): PayloadData {
    let obj: Record<string, Object | null> = {}
    try {
      obj = JSON.parse(raw.length > 0 ? raw : '{}') as Record<string, Object | null>
    } catch (e) {
      obj = {}
    }
    const intervalRaw = obj['sync_interval_sec']
    const daysRaw = obj['window_days']
    const autoRaw = obj['auto_sync']
    const accRaw = obj['active_account_id']
    const keyNames: Map<string, string> = new Map()
    const knRaw = obj['key_names']
    if (typeof knRaw === 'object' && knRaw !== null) {
      const kn = knRaw as Record<string, Object | null>
      const ks = Object.keys(kn)
      for (const k of ks) {
        const v = kn[k]
        if (typeof v === 'string') {
          keyNames.set(k, v)
        }
      }
    }
    const def = defaultSettings()
    return {
      syncIntervalSec: typeof intervalRaw === 'number'
        ? Math.min(3600, Math.max(30, Math.trunc(intervalRaw))) : def.syncIntervalSec,
      windowDays: typeof daysRaw === 'number'
        ? Math.min(3650, Math.max(1, Math.trunc(daysRaw))) : null,
      autoSync: typeof autoRaw === 'boolean' ? autoRaw : def.autoSync,
      activeAccountId: typeof accRaw === 'number' ? Math.trunc(accRaw) : null,
      keyNames: keyNames,
    }
  }

  /**
   * 写侧构建: base 未知键原样保留; patch=null 时不改动设置项键
   * (key_names / active_account_id 由调用方显式传入)。
   */
  private static buildPayload(
    base: Record<string, Object | null>,
    patch: AppSettings | null,
    keyNames: Map<string, string>,
    activeAccountId: number | null,
  ): string {
    const out: Record<string, Object | null> = {}
    const keys = Object.keys(base)
    for (const k of keys) {
      out[k] = base[k]
    }
    if (patch !== null) {
      out['sync_interval_sec'] = patch.syncIntervalSec
      out['window_days'] = patch.windowDays
      out['auto_sync'] = patch.autoSync
    }
    out['active_account_id'] = activeAccountId
    const kn: Record<string, Object | null> = {}
    keyNames.forEach((v: string, k: string) => {
      kn[k] = v
    })
    out['key_names'] = kn
    return JSON.stringify(out)
  }

  private async rawPayload(): Promise<string> {
    const rs = await AppDb.store().querySql('SELECT payload FROM settings WHERE id = 1')
    const r = new RowReader(rs)
    let out = ''
    if (r.next()) {
      out = r.getStr('payload')
    }
    r.close()
    return out
  }

  private async writePayload(payload: string): Promise<void> {
    await AppDb.store().executeSql('UPDATE settings SET payload = ?, updated_at = ? WHERE id = 1',
      [payload, new Date().toISOString()])
  }

  async getSettings(): Promise<AppSettings> {
    const d = SettingsDao.decode(await this.rawPayload())
    return { syncIntervalSec: d.syncIntervalSec, windowDays: d.windowDays, autoSync: d.autoSync }
  }

  async saveSettings(patch: AppSettings): Promise<AppSettings> {
    const merged: AppSettings = {
      syncIntervalSec: Math.min(3600, Math.max(30, patch.syncIntervalSec)),
      windowDays: patch.windowDays === null ? null : Math.min(3650, Math.max(1, patch.windowDays)),
      autoSync: patch.autoSync,
    }
    await this.enqueueWrite(async () => {
      const raw = await this.rawPayload()
      const current = SettingsDao.decode(raw)
      const payload = SettingsDao.buildPayload(
        SettingsDao.parsePayload(raw), merged, current.keyNames, current.activeAccountId)
      await this.writePayload(payload)
    })
    return merged
  }

  async getKeyNames(): Promise<Map<string, string>> {
    const d = SettingsDao.decode(await this.rawPayload())
    return d.keyNames
  }

  async saveKeyNames(names: Map<string, string>): Promise<void> {
    const filtered: Map<string, string> = new Map()
    names.forEach((v: string, k: string) => {
      if (k.length > 0 && v.length > 0) {
        filtered.set(k, v)
      }
    })
    await this.enqueueWrite(async () => {
      const raw = await this.rawPayload()
      const current = SettingsDao.decode(raw)
      const payload = SettingsDao.buildPayload(
        SettingsDao.parsePayload(raw), null, filtered, current.activeAccountId)
      await this.writePayload(payload)
    })
  }

  /** 活跃账号 id (settings payload), 无则 null。 */
  async readActiveAccountId(): Promise<number | null> {
    const d = SettingsDao.decode(await this.rawPayload())
    return d.activeAccountId
  }

  async writeActiveAccountId(accountId: number): Promise<void> {
    await this.enqueueWrite(async () => {
      const raw = await this.rawPayload()
      const current = SettingsDao.decode(raw)
      const payload = SettingsDao.buildPayload(
        SettingsDao.parsePayload(raw), null, current.keyNames, accountId)
      await this.writePayload(payload)
    })
  }

  async removeActiveAccountId(): Promise<void> {
    await this.enqueueWrite(async () => {
      const raw = await this.rawPayload()
      const current = SettingsDao.decode(raw)
      const payload = SettingsDao.buildPayload(
        SettingsDao.parsePayload(raw), null, current.keyNames, null)
      await this.writePayload(payload)
    })
  }
}
