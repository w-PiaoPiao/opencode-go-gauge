/**
 * 本地偏好存储（preferences）—— 工作区提示/外观设置的封装。
 * 对应: Android 的 SharedPreferences 角色。
 *
 * 注意凭证的实际存放位置: 登录 token 由 SyncDao 写入 RDB 的 accounts.token
 * 列 (AppDb 以 securityLevel S2 创建), 本文件不参与凭证明文/密文存取。
 * 此处曾有一套 @ohos.security.asset 的加密凭证读写 (getAuthCookie/setAuthCookie/
 * clearAuth), 但从未被任何调用点接入, 文件头注释因此错误地宣称"preferences 中
 * 不再保留明文"。该死代码已移除, 以免遮蔽真实的凭证存放位置。
 *
 * 仅存本地偏好, 绝不写日志、绝不上传。
 */
import { preferences } from '@kit.ArkData'

export class AppPrefs {
  static readonly PREFS_NAME: string = 'gogauge'

  static readonly KEY_WORKSPACE_HINT: string = 'workspace_hint' // "wrk_xxx" | "Default"
  static readonly KEY_LANGUAGE: string = 'language'             // 'zh' | 'en'
  static readonly KEY_DARK_MODE: string = 'dark_mode'           // '0' | '1'
  static readonly KEY_CURRENCY: string = 'currency'             // 'USD' | 'CNY'

  private static store: preferences.Preferences | null = null

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
