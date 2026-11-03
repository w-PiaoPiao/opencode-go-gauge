/**
 * 设计令牌 —— 暖色「Claude 令牌」体系（安卓版 Color.kt 的 ArkTS 移植）。
 *
 * 三端统一品牌视觉：象牙画布 / 暖白卡 / 发丝线 / 珊瑚主色 / 语义色数据。
 * 页面与组件禁止硬编码颜色；所有颜色（含图表语义色、热力图档位）都从这里取。
 * 主题模式由 AppPrefs 持久化（手动浅色/深色），切换后页面重建即生效。
 */
import { AppPrefs } from '../../common/store/AppPrefs'

/** 标题衬线字体族（EntryAbility 启动时 registerFont 注册，缺省回退系统字体）。 */
export const FONT_SERIF: string = 'GgSerif'

/** 间距 / 圆角 / 尺寸常量（vp）。 */
export class Dimens {
  static readonly PAGE_H: number = 14
  static readonly PAGE_V: number = 12
  static readonly PAGE_H_WIDE: number = 18
  static readonly PAGE_V_WIDE: number = 14
  static readonly GAP: number = 10
  static readonly GAP_WIDE: number = 12
  static readonly CARD_RADIUS: number = 12
  static readonly TILE_RADIUS: number = 8
  static readonly CARD_PAD: number = 14
  static readonly CARD_PAD_WIDE: number = 16
  static readonly TOPBAR_H: number = 48
  static readonly SIDEBAR_W: number = 64
  static readonly TABBAR_H: number = 56
  static readonly TOUCH_MIN: number = 44
  static readonly PC_TOUCH_MIN: number = 32
  /**
   * 壳层断点（vp）：>=600 用桌面式外壳（顶栏 + 左侧图标导航）。
   * 依据 Material/HarmonyOS 一多规范：600-839 为 medium（平板竖屏/分屏），
   * >=840 为 expanded（平板横屏/PC）。内容栅格的多列断点仍用 WIDE_BREAKPOINT(840)。
   */
  static readonly SHELL_WIDE_BREAKPOINT: number = 600
  /** 内容页宽屏断点（vp）：>=840 时页内改用桌面版多列栅格。 */
  static readonly WIDE_BREAKPOINT: number = 840
  /** 手机/宽屏内容页头标题字号（fp）。 */
  static readonly TITLE_PHONE: number = 22
  static readonly TITLE_WIDE: number = 20
  /** 数据栅格断点（vp）。 */
  static readonly GRID_MD: number = 600
  static readonly GRID_LG: number = 1000
}

/** 亮/暗主题色板。 */
export class Theme {
  static isDark(): boolean {
    return AppPrefs.isDarkMode()
  }

  // ---------------- 表面与文字 ----------------
  static bg(): string {
    return Theme.isDark() ? '#1F1E1B' : '#F0EEE6'
  }

  /** 卡片 / 顶栏 / 侧栏表面。 */
  static surface(): string {
    return Theme.isDark() ? '#252320' : '#FAF9F5'
  }

  /** 卡内瓷砖（KPI / 子块 / 分段容器）。 */
  static surfaceSoft(): string {
    return Theme.isDark() ? '#2C2A26' : '#EFE9DE'
  }

  /** 强瓷砖（进度轨道 / 热力图 0 档 / 胶囊底）。 */
  static surfaceStrong(): string {
    return Theme.isDark() ? '#33302B' : '#E8E0D2'
  }

  static border(): string {
    return Theme.isDark() ? '#3B3833' : '#E6DFD8'
  }

  static divider(): string {
    return Theme.border()
  }

  static text(): string {
    return Theme.isDark() ? '#FAF9F5' : '#141413'
  }

  static sub(): string {
    return Theme.isDark() ? '#A09D96' : '#6C6A64'
  }

  static faint(): string {
    return Theme.isDark() ? '#8E8B82' : '#87867F'
  }

  // ---------------- 品牌与语义色 ----------------
  static accent(): string {
    return Theme.isDark() ? '#D97757' : '#C96442'
  }

  static accentSoft(): string {
    return Theme.isDark() ? '#3A2C26' : '#F4E8E1'
  }

  static danger(): string {
    return Theme.isDark() ? '#D96A6A' : '#C64545'
  }

  static dangerSoft(): string {
    return Theme.isDark() ? '#3D2624' : '#F7E9E4'
  }

  static blue(): string {
    return Theme.isDark() ? '#8FA9C7' : '#7B96B8'
  }

  static green(): string {
    return Theme.isDark() ? '#79C389' : '#5DB872'
  }

  static cyan(): string {
    return Theme.isDark() ? '#79C7B5' : '#5DB8A6'
  }

  static amber(): string {
    return Theme.isDark() ? '#EBB275' : '#E8A55A'
  }

  static violet(): string {
    return Theme.isDark() ? '#B79ABE' : '#9A7AA0'
  }

  static slate(): string {
    return Theme.isDark() ? '#8E8B82' : '#87867F'
  }

  /** 彩色图标块/徽标上的白字（与主题无关）。 */
  static onAccent(): string {
    return '#FFFFFF'
  }

  // ---------------- 图表语义色 ----------------
  static chartInput(): string {
    return Theme.blue()
  }

  static chartOutput(): string {
    return Theme.isDark() ? '#9AA583' : '#7D8B6A'
  }

  static chartReasoning(): string {
    return Theme.violet()
  }

  static chartCache(): string {
    return Theme.cyan()
  }

  static chartCost(): string {
    return Theme.isDark() ? '#D9AE8C' : '#D4A27F'
  }

  static chartExtra(): string {
    return Theme.accent()
  }

  static chartSeries(): string[] {
    return [
      Theme.accent(), Theme.blue(), Theme.green(), Theme.amber(),
      Theme.violet(), Theme.cyan(), Theme.danger(), Theme.slate(),
    ]
  }

  // ---------------- 热力图档位（0 档 = surfaceStrong） ----------------
  static heatRamp(): string[] {
    if (Theme.isDark()) {
      return ['#564136', '#815846', '#B07157', '#E08A68']
    }
    return ['#E2C0AE', '#D29880', '#BF7154', '#A8492B']
  }

  // ---------------- 其他 ----------------
  static scrim(): string {
    return Theme.isDark() ? '#99000000' : '#66000000'
  }

  static serifFont(): string {
    return FONT_SERIF
  }

  /** 极轻卡片阴影（暗色下由 border 承担层次，返回空阴影）。 */
  static cardShadow(): ShadowOptions {
    return Theme.isDark()
      ? { radius: 0, color: '#00000000', offsetX: 0, offsetY: 0 }
      : { radius: 6, color: '#0D000000', offsetX: 0, offsetY: 2 }
  }
}
