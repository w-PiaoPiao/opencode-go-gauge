/**
 * 应用版本号 —— 单一来源：运行时从包信息读取（AppScope/app.json5 的 versionName），
 * 避免页面里硬编码 4 处、升版本时不一致。
 */
import { bundleManager } from '@kit.AbilityKit'

export class AppVersion {
  private static cached: string = ''

  /** 版本名（如 1.0.0）；读取失败回退 '1.0.0'。 */
  static versionName(): string {
    if (AppVersion.cached.length > 0) {
      return AppVersion.cached
    }
    try {
      const info = bundleManager.getBundleInfoForSelfSync(bundleManager.BundleFlag.GET_BUNDLE_INFO_DEFAULT)
      if (info.versionName !== undefined && info.versionName.length > 0) {
        AppVersion.cached = info.versionName
      }
    } catch (e) {
      // 预览器等环境无包信息
    }
    if (AppVersion.cached.length === 0) {
      AppVersion.cached = '1.0.0'
    }
    return AppVersion.cached
  }

  static display(): string {
    return `v${AppVersion.versionName()}`
  }
}
