/** 主题色板 —— 亮/暗 (M4)。页面通过 AppPrefs.isDarkMode() 取当前模式。 */
import { AppPrefs } from '../../common/store/AppPrefs'

export class Theme {
  static isDark(): boolean {
    return AppPrefs.isDarkMode()
  }

  static bg(): string {
    return Theme.isDark() ? '#12141A' : '#F2F3F7'
  }

  static surface(): string {
    return Theme.isDark() ? '#1C1F27' : '#FFFFFF'
  }

  static surfaceSoft(): string {
    return Theme.isDark() ? '#262A33' : '#F8F9FC'
  }

  static text(): string {
    return Theme.isDark() ? '#E8EAED' : '#222222'
  }

  static sub(): string {
    return Theme.isDark() ? '#9AA0A8' : '#888888'
  }

  static faint(): string {
    return Theme.isDark() ? '#6B7280' : '#AAAAAA'
  }

  static accent(): string {
    return '#3B82F6'
  }

  static danger(): string {
    return '#E74C3C'
  }

  static divider(): string {
    return Theme.isDark() ? '#2E323B' : '#EFEFF2'
  }
}