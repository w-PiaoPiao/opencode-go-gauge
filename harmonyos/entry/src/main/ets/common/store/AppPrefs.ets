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

  static readonly KEY_LANGUAGE: string = 'language'             // 'zh' | 'en'
  static readonly KEY_DARK_MODE: string = 'dark_mode'           // '0' | '1'
  static readonly KEY_CURRENCY: string = 'currency'             // 'USD' | 'CNY'
  /**
   * 图标风格 'blue' | 'terracotta'（与桌面/Android 同名同值契约）。
   * ⚠️ HarmonyOS NEXT 没有运行时切换启动器应用图标的公开 API：AppScope/module 的
   * 启动器图标固定为蓝色 H，本键只切换应用内品牌 Logo（顶栏 + 欢迎页）。
   */
  static readonly KEY_ICON_STYLE: string = 'icon_style'
  static readonly KEY_PRIVACY_ACCEPTED: string = 'privacy_accepted' // '0' | '1'（首次启动合规弹窗）

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

  /**
   * 应用内品牌 Logo 风格（读容错：非 'terracotta' 一律回落 blue）。
   * 注意：不影响启动器图标（HarmonyOS 无运行时切换 API，固定蓝色 H）。
   */
  static getIconStyle(): string {
    if (AppPrefs.store === null) {
      return 'blue'
    }
    const v = AppPrefs.store.getSync(AppPrefs.KEY_ICON_STYLE, 'blue') as string
    return v === 'terracotta' ? 'terracotta' : 'blue'
  }

  static setIconStyle(value: string): void {
    AppPrefs.put(AppPrefs.KEY_ICON_STYLE, value === 'terracotta' ? 'terracotta' : 'blue')
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

  /** 隐私政策是否已被用户明确同意（首次启动弹窗；应用内可再次查看）。 */
  static isPrivacyAccepted(): boolean {
    if (AppPrefs.store === null) {
      return false
    }
    return (AppPrefs.store.getSync(AppPrefs.KEY_PRIVACY_ACCEPTED, '0') as string) === '1'
  }

  static setPrivacyAccepted(accepted: boolean): void {
    AppPrefs.put(AppPrefs.KEY_PRIVACY_ACCEPTED, accepted ? '1' : '0')
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
