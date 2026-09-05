/**
 * 本地偏好存储（preferences + asset store）—— 登录凭据/工作区/外观设置的封装。
 * 对应: desktop 的登录凭据保存在本机; Android 的 SharedPreferences 角色。
 *
 * 登录凭据 (auth cookie) 的正式存放处是系统 asset store (@ohos.security.asset):
 * 由硬件密钥加密落盘, preferences 中不再保留明文。旧版本把 cookie 存在
 * preferences 里, 首次读取时自动迁移到 asset store 并删除明文。
 * 仅存本地偏好, 绝不写日志、绝不上传。
 */
import { preferences } from '@kit.ArkData'
import { asset } from '@kit.AssetStoreKit'
import { util } from '@kit.ArkTS'

export class AppPrefs {
  static readonly PREFS_NAME: string = 'gogauge'

  static readonly KEY_AUTH_COOKIE: string = 'auth_cookie'       // "auth=<value>" (仅旧版迁移态)
  static readonly KEY_WORKSPACE_HINT: string = 'workspace_hint' // "wrk_xxx" | "Default"
  static readonly KEY_LANGUAGE: string = 'language'             // 'zh' | 'en'
  static readonly KEY_DARK_MODE: string = 'dark_mode'           // '0' | '1'
  static readonly KEY_CURRENCY: string = 'currency'             // 'USD' | 'CNY'

  private static readonly ASSET_ALIAS: string = 'GoGauge.auth_cookie'

  private static store: preferences.Preferences | null = null

  private static toU8(s: string): Uint8Array {
    return util.TextEncoder.create().encodeInto(s)
  }

  private static u8ToStr(data: Uint8Array): string {
    return util.TextDecoder.create('utf-8').decodeToString(data)
  }

  /** 读取 asset store 中的凭证; 不存在/不可用返回 ''。 */
  private static assetGet(): string {
    try {
      const query: asset.AssetMap = new Map()
      query.set(asset.Tag.ALIAS, AppPrefs.toU8(AppPrefs.ASSET_ALIAS))
      query.set(asset.Tag.RETURN_TYPE, asset.ReturnType.ALL)
      const result: Array<asset.AssetMap> = asset.querySync(query)
      if (result.length === 0) {
        return ''
      }
      const secret = result[0].get(asset.Tag.SECRET)
      if (secret === undefined || !(secret instanceof Uint8Array)) {
        return ''
      }
      return AppPrefs.u8ToStr(secret)
    } catch (e) {
      return '' // NOT_FOUND 等错误: 按无凭据处理
    }
  }

  /** 写入 asset store; 先试更新再新增 (asset 无 upsert)。失败返回 false。 */
  private static assetSet(value: string): boolean {
    if (value.length === 0) {
      return false
    }
    try {
      const query: asset.AssetMap = new Map()
      query.set(asset.Tag.ALIAS, AppPrefs.toU8(AppPrefs.ASSET_ALIAS))
      // DEVICE_POWERED_ON: 设备开机即可读 (含锁屏), 保证后台 WorkScheduler 同步可用;
      // 密文由系统硬件密钥保护, 静止不落明文。
      const upd: asset.AssetMap = new Map()
      upd.set(asset.Tag.SECRET, AppPrefs.toU8(value))
      upd.set(asset.Tag.ACCESSIBILITY, asset.Accessibility.DEVICE_POWERED_ON)
      try {
        asset.updateSync(query, upd)
      } catch (e) {
        // 别名不存在: 新增 (addSync 需要 ALIAS + SECRET 完整属性)
        const add: asset.AssetMap = new Map()
        add.set(asset.Tag.ALIAS, AppPrefs.toU8(AppPrefs.ASSET_ALIAS))
        add.set(asset.Tag.SECRET, AppPrefs.toU8(value))
        add.set(asset.Tag.ACCESSIBILITY, asset.Accessibility.DEVICE_POWERED_ON)
        asset.addSync(add)
      }
      return true
    } catch (e) {
      return false
    }
  }

  private static assetRemove(): void {
    try {
      const query: asset.AssetMap = new Map()
      query.set(asset.Tag.ALIAS, AppPrefs.toU8(AppPrefs.ASSET_ALIAS))
      asset.removeSync(query)
    } catch (e) {
      // 不存在即视为已清除
    }
  }

  private static dropPrefsCookie(): void {
    if (AppPrefs.store === null) {
      return
    }
    try {
      AppPrefs.store.deleteSync(AppPrefs.KEY_AUTH_COOKIE)
      AppPrefs.store.flush()
    } catch (e) {
      // ignore
    }
  }

  /** 需在 UIAbility/页面上下文可用后调用一次。 */
  static init(context: Context): void {
    if (AppPrefs.store !== null) {
      return
    }
    try {
      AppPrefs.store = preferences.getPreferencesSync(context, { name: AppPrefs.PREFS_NAME })
    } catch (e) {
      AppPrefs.store = null
    }
  }

  static getAuthCookie(): string {
    const fromAsset = AppPrefs.assetGet()
    if (fromAsset.length > 0) {
      return fromAsset
    }
    if (AppPrefs.store === null) {
      return ''
    }
    const legacy = AppPrefs.store.getSync(AppPrefs.KEY_AUTH_COOKIE, '') as string
    if (legacy.length > 0 && AppPrefs.assetSet(legacy)) {
      // 旧版本明文迁移到 asset store, 迁移成功即删除 preferences 明文
      AppPrefs.dropPrefsCookie()
    }
    return legacy
  }

  static setAuthCookie(value: string): void {
    if (AppPrefs.assetSet(value)) {
      // 正式凭证已在 asset store, 不在 preferences 保留明文
      AppPrefs.dropPrefsCookie()
      return
    }
    // asset 不可用: 回退 preferences (应用沙盒内, 弱于 asset 但保登录可用)
    if (AppPrefs.store === null) {
      return
    }
    try {
      AppPrefs.store.putSync(AppPrefs.KEY_AUTH_COOKIE, value)
      AppPrefs.store.flush()
    } catch (e) {
      // 本地写入失败不影响登录流程; 下次启动用旧值
    }
  }

  static getWorkspaceHint(): string {
    if (AppPrefs.store === null) {
      return 'Default'
    }
    const v = AppPrefs.store.getSync(AppPrefs.KEY_WORKSPACE_HINT, 'Default') as string
    return v.length > 0 ? v : 'Default'
  }

  static setWorkspaceHint(value: string): void {
    AppPrefs.put(AppPrefs.KEY_WORKSPACE_HINT, value)
  }

  static clearAuth(): void {
    AppPrefs.assetRemove()
    if (AppPrefs.store === null) {
      return
    }
    try {
      AppPrefs.store.deleteSync(AppPrefs.KEY_AUTH_COOKIE)
      AppPrefs.store.flush()
    } catch (e) {
      // ignore
    }
  }

  // ------------------------------------------------------------------
  // 外观 / 语言 / 货币 (M4)
  // ------------------------------------------------------------------

  static getLanguage(): string {
    if (AppPrefs.store === null) {
      return 'zh'
    }
    const v = AppPrefs.store.getSync(AppPrefs.KEY_LANGUAGE, 'zh') as string
    return v === 'en' ? 'en' : 'zh'
  }

  static setLanguage(value: string): void {
    AppPrefs.put(AppPrefs.KEY_LANGUAGE, value === 'zh' ? 'zh' : 'en')
  }

  static isDarkMode(): boolean {
    if (AppPrefs.store === null) {
      return false
    }
    return (AppPrefs.store.getSync(AppPrefs.KEY_DARK_MODE, '0') as string) === '1'
  }

  static setDarkMode(dark: boolean): void {
    AppPrefs.put(AppPrefs.KEY_DARK_MODE, dark ? '1' : '0')
  }

  static getCurrency(): string {
    if (AppPrefs.store === null) {
      return 'USD'
    }
    const v = AppPrefs.store.getSync(AppPrefs.KEY_CURRENCY, 'USD') as string
    return v === 'CNY' ? 'CNY' : 'USD'
  }

  static setCurrency(value: string): void {
    AppPrefs.put(AppPrefs.KEY_CURRENCY, value === 'CNY' ? 'CNY' : 'USD')
  }

  private static put(key: string, value: string): void {
    if (AppPrefs.store === null) {
      return
    }
    try {
      AppPrefs.store.putSync(key, value)
      AppPrefs.store.flush()
    } catch (e) {
      // ignore
    }
  }
}
