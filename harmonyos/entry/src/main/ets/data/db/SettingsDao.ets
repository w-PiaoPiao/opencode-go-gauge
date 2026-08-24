/**
 * settings 表 (JSON payload 行) 的访问层 —— SettingsDao.kt 的 ArkTS 移植。
 * payload 为 JSON 文本; 为规避 ArkTS 对 JSON 库的严格类型限制, 读写用
 * 自带的轻量编解码 (写: 固定键序 JSON 文本; 读: 正则逐键提取), 语义与桌面一致。
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
  private static escapeJson(v: string): string {
    return v.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
  }

  private static unescapeJson(v: string): string {
    return v.replace(/\\"/g, '"').replace(/\\\\/g, '\\')
  }

  /** 将已知键序列化为 JSON 文本 (固定键序便于 diff/调试)。 */
  static encode(
    patch: AppSettings | null,
    keyNames: Map<string, string> | null,
    activeAccountId: number | null,
  ): string {
    const s: number = patch !== null && patch.syncIntervalSec !== undefined ? patch.syncIntervalSec : 300
    let w: string = 'null'
    if (patch !== null && patch.windowDays !== undefined) {
      w = patch.windowDays === null ? 'null' : patch.windowDays.toString()
    }
    const a: boolean = patch !== null && patch.autoSync !== undefined ? patch.autoSync : true
    let acc: string = 'null'
    if (activeAccountId !== null) {
      acc = activeAccountId.toString()
    }
    let kn = '{}'
    if (keyNames !== null && keyNames.size > 0) {
      const parts: string[] = []
      keyNames.forEach((v, k) => {
        parts.push(`"${SettingsDao.escapeJson(k)}":"${SettingsDao.escapeJson(v)}"`)
      })
      kn = `{${parts.join(',')}}`
    }
    return `{"sync_interval_sec":${s},"window_days":${w},"auto_sync":${a},"active_account_id":${acc},"key_names":${kn}}`
  }

  /** 从 payload JSON 文本解析已知键 (容错: 缺键/坏文本回退默认)。 */
  static decode(raw: string): PayloadData {
    let text = raw
    if (text.length === 0) {
      text = '{}'
    }
    const parseNum = (key: string): number | null => {
      const m = new RegExp(`"${key}"\\s*:\\s*(-?\\d+)`).exec(text)
      return m === null ? null : Number(m[1])
    }
    const parseBool = (key: string): boolean | null => {
      const m = new RegExp(`"${key}"\\s*:\\s*(true|false)`).exec(text)
      return m === null ? null : m[1] === 'true'
    }
    const interval = parseNum('sync_interval_sec')
    const days = parseNum('window_days')
    const auto = parseBool('auto_sync')
    const acc = parseNum('active_account_id')

    const keyNames: Map<string, string> = new Map()
    const knBlock = /"key_names"\s*:\s*\{([^}]*)\}/.exec(text)
    if (knBlock !== null) {
      const pairRe = /"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"/g
      let pm: RegExpExecArray | null
      while ((pm = pairRe.exec(knBlock[1])) !== null) {
        keyNames.set(SettingsDao.unescapeJson(pm[1]), SettingsDao.unescapeJson(pm[2]))
      }
    }
    const def = defaultSettings()
    return {
      syncIntervalSec: interval !== null ? Math.min(3600, Math.max(30, interval)) : def.syncIntervalSec,
      windowDays: days !== null ? Math.min(3650, Math.max(1, days)) : null,
      autoSync: auto !== null ? auto : def.autoSync,
      activeAccountId: acc,
      keyNames: keyNames,
    }
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
    const current = SettingsDao.decode(await this.rawPayload())
    const keyNames = current.keyNames
    await this.writePayload(SettingsDao.encode(merged, keyNames, current.activeAccountId))
    return merged
  }

  async getKeyNames(): Promise<Map<string, string>> {
    const d = SettingsDao.decode(await this.rawPayload())
    return d.keyNames
  }

  async saveKeyNames(names: Map<string, string>): Promise<void> {
    const filtered: Map<string, string> = new Map()
    names.forEach((v, k) => {
      if (k.length > 0 && v.length > 0) {
        filtered.set(k, v)
      }
    })
    const current = SettingsDao.decode(await this.rawPayload())
    await this.writePayload(SettingsDao.encode(null, filtered, current.activeAccountId))
  }

  /** 活跃账号 id (settings payload), 无则 null。 */
  async readActiveAccountId(): Promise<number | null> {
    const d = SettingsDao.decode(await this.rawPayload())
    return d.activeAccountId
  }

  async writeActiveAccountId(accountId: number): Promise<void> {
    const current = SettingsDao.decode(await this.rawPayload())
    await this.writePayload(SettingsDao.encode(null, current.keyNames, accountId))
  }

  async removeActiveAccountId(): Promise<void> {
    const current = SettingsDao.decode(await this.rawPayload())
    await this.writePayload(SettingsDao.encode(null, current.keyNames, null))
  }
}