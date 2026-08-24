/**
 * 本地偏好存储（preferences）—— 登录凭据/账号/设置的最小封装。
 * 对应: desktop 的登录凭据保存在本机; Android 的 SharedPreferences 角色。
 * 仅存 cookie 与工作区 hint, 绝不写日志、绝不上传。
 */
import { preferences } from '@kit.ArkData'

export class AppPrefs {
  static readonly PREFS_NAME: string = 'gogauge'

  static readonly KEY_AUTH_COOKIE: string = 'auth_cookie'       // "auth=<value>"
  static readonly KEY_WORKSPACE_HINT: string = 'workspace_hint' // "wrk_xxx" | "Default"
  static readonly KEY_LANGUAGE: string = 'language'             // 'zh' | 'en'
  static readonly KEY_DARK_MODE: string = 'dark_mode'           // '0' | '1'

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

  static getAuthCookie(): string {
    if (AppPrefs.store === null) {
      return ''
    }
    return AppPrefs.store.getSync(AppPrefs.KEY_AUTH_COOKIE, '') as string
  }

  static setAuthCookie(value: string): void {
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
    if (AppPrefs.store === null) {
      return
    }
    try {
      AppPrefs.store.putSync(AppPrefs.KEY_WORKSPACE_HINT, value)
      AppPrefs.store.flush()
    } catch (e) {
      // ignore
    }
  }

  static clearAuth(): void {
    if (AppPrefs.store === null) {
      return
    }
    try {
      AppPrefs.store.putSync(AppPrefs.KEY_AUTH_COOKIE, '')
      AppPrefs.store.flush()
    } catch (e) {
      // ignore
    }
  }
}