/**
 * 应用入口 Ability —— 启动参数透传 / 窗口策略 / 系统栏配色。
 *
 * 平台适配约定（design-spec §1.6 / §3.2 / §3.3）：
 * - 衬线字体 GgSerif 由 Index.ets 在首帧前注册（$rawfile 仅可用于 UI 文件，Ability 层不注册）；
 * - 2in1 / 平板最小窗口 720×560vp（按屏幕密度换算为 px），宽窗口默认 1280×840；
 * - 窗口背景取主题 bg（状态栏由窗口背景承载，不做全屏沉浸绘制），系统栏图标随亮暗反色；
 * - 后台周期同步（workScheduler）逻辑保持原样。
 */
import AbilityConstant from '@ohos.app.ability.AbilityConstant'
import hilog from '@ohos.hilog'
import UIAbility from '@ohos.app.ability.UIAbility'
import Want from '@ohos.app.ability.Want'
import window from '@ohos.window'
import { display } from '@kit.ArkUI'
import { deviceInfo } from '@kit.BasicServicesKit'
import { BusinessError } from '@kit.BasicServicesKit'
import { AppPrefs } from '../common/store/AppPrefs'
import { BackgroundSync } from '../common/BackgroundSync'
import { AppDb } from '../data/db/AppDb'
import { Repo } from '../data/repository/DashboardRepository'
import { Theme } from '../ui/theme/Theme'
import BuildProfile from 'BuildProfile'
import { LaunchParams } from '../common/dev/LaunchParams'

const HILOG_DOMAIN = 0x0000
const TAG = 'GoGauge'

/** 2in1 / 平板最小窗口尺寸（vp，窗口接口按 px 收口，运行时按屏幕密度换算）。 */
const MIN_WINDOW_W_VP = 720
const MIN_WINDOW_H_VP = 560
/** 宽窗口下的默认启动尺寸（vp）—— 换算成 px 后调用 resize。 */
const DEFAULT_WINDOW_W_VP = 1280
const DEFAULT_WINDOW_H_VP = 840
/** 窗口宽度超过该阈值（px）才视为桌面式宽窗口并套用默认尺寸。 */
const WIDE_WINDOW_PX = 720

export default class EntryAbility extends UIAbility {
  /** 主窗口引用：设置页切换亮暗主题时可立即刷新窗口背景/系统栏（静态，跨页面复用）。 */
  private static mainWindow: window.Window | null = null

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    // 调试/截图流水线的启动参数（--ps demo 1 --ps lang zh ...）：
    // 页面无法直接拿到 Want，先落到 LaunchParams 供 Index 首帧读取。
    // ⚠️ 仅 debug 构建生效：release 不能因为 Want 参数而进入演示/绕过隐私弹窗。
    if (BuildProfile.DEBUG) {
      LaunchParams.apply(want.parameters)
    }
    AppPrefs.init(this.context)
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onCreate')
  }

  /**
   * 应用已在前台时再次 `aa start`（截图流水线切演示页/主题）走这里。
   * 只更新 LaunchParams，Index 的 onPageShow 会读取并应用。
   */
  onNewWant(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    if (BuildProfile.DEBUG) {
      LaunchParams.apply(want.parameters)
    }
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onNewWant')
  }

  onDestroy(): void {
    EntryAbility.mainWindow = null
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onDestroy')
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onWindowStageCreate')
    this.applyWindowPolicy(windowStage)
    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(HILOG_DOMAIN, TAG, 'Failed to load the content. Cause: %{public}s', JSON.stringify(err))
        return
      }
      hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Succeeded in loading the content.')
    })
    this.applyBackgroundSync()
  }

  onWindowStageDestroy(): void {
    EntryAbility.mainWindow = null
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onWindowStageDestroy')
  }

  onForeground(): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onForeground')
  }

  onBackground(): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onBackground')
  }

  // ------------------------------------------------------------------
  // 窗口
  // ------------------------------------------------------------------

  /**
   * 窗口策略：背景色/系统栏配色 + (2in1/平板) 最小尺寸 + 宽窗口默认尺寸。
   * 手机全屏窗口下 resize 会被系统忽略，因此仅在 desktop-like 设备上套用尺寸限制。
   */
  private applyWindowPolicy(windowStage: window.WindowStage): void {
    windowStage.getMainWindow().then((win: window.Window) => {
      EntryAbility.mainWindow = win
      EntryAbility.applyWindowTheme(win)
      this.applyWindowSize(win)
    }).catch((e: Error) => {
      hilog.warn(HILOG_DOMAIN, TAG, 'getMainWindow failed %{public}s', e.message)
    })
  }

  private isDesktopLike(): boolean {
    const dev = deviceInfo.deviceType
    return dev === '2in1' || dev === 'tablet'
  }

  private applyWindowSize(win: window.Window): void {
    if (!this.isDesktopLike()) {
      return
    }
    try {
      let density = 1
      try {
        const d = display.getDefaultDisplaySync().densityPixels
        if (d > 0) {
          density = d
        }
      } catch (e) {
        density = 1
      }
      win.setWindowLimits({
        minWidth: Math.round(MIN_WINDOW_W_VP * density),
        minHeight: Math.round(MIN_WINDOW_H_VP * density),
      }).catch((e: BusinessError) => {
        hilog.warn(HILOG_DOMAIN, TAG, 'setWindowLimits failed %{public}s', e.message)
      })
      const w = win.getWindowProperties().windowRect.width
      if (w > WIDE_WINDOW_PX) {
        // resize 接口单位是 px：按 vp*density 换算，默认 1280×840vp（>=840 走桌面式布局）
        win.resize(Math.round(DEFAULT_WINDOW_W_VP * density), Math.round(DEFAULT_WINDOW_H_VP * density))
          .catch((e: BusinessError) => {
            hilog.warn(HILOG_DOMAIN, TAG, 'resize failed %{public}s', e.message)
          })
      }
    } catch (e) {
      hilog.warn(HILOG_DOMAIN, TAG, 'applyWindowSize failed %{public}s', (e as Error).message)
    }
  }

  /**
   * 窗口背景 + 状态栏/导航栏配色（取 Theme 令牌，随手动亮暗主题）。
   * 设置页切换主题后调用静态方法即可即时生效，无需重启 Ability。
   */
  private static applyWindowTheme(win: window.Window): void {
    const dark = Theme.isDark()
    const bg = Theme.bg()
    try {
      win.setWindowBackgroundColor(bg)
    } catch (e) {
      hilog.warn(HILOG_DOMAIN, TAG, 'setWindowBackgroundColor failed %{public}s', (e as Error).message)
    }
    try {
      win.setWindowSystemBarProperties({
        statusBarColor: bg,
        isStatusBarLightIcon: dark,
        statusBarContentColor: Theme.text(),
        navigationBarColor: bg,
        isNavigationBarLightIcon: dark,
        navigationBarContentColor: Theme.text(),
      }).catch((e: BusinessError) => {
        hilog.warn(HILOG_DOMAIN, TAG, 'setWindowSystemBarProperties failed %{public}s', e.message)
      })
    } catch (e) {
      hilog.warn(HILOG_DOMAIN, TAG, 'setWindowSystemBarProperties failed %{public}s', (e as Error).message)
    }
  }

  /** 供设置页在亮暗主题切换后调用：立即刷新窗口背景与系统栏配色（窗口未就绪时静默跳过）。 */
  static refreshWindowTheme(): void {
    const win = EntryAbility.mainWindow
    if (win === null) {
      return
    }
    EntryAbility.applyWindowTheme(win)
  }

  // ------------------------------------------------------------------
  // 后台同步
  // ------------------------------------------------------------------

  /**
   * 按用户「自动增量同步」设置注册/取消后台周期任务。
   * worker 内部还会再校验一次 autoSync（设置页关闭后已注册的任务也不会联网）。
   */
  private async applyBackgroundSync(): Promise<void> {
    try {
      await AppDb.init(this.context)
      const settings = await Repo.get().settings()
      BackgroundSync.apply(settings.autoSync)
      hilog.info(HILOG_DOMAIN, TAG, 'background sync applied: %{public}s', `${settings.autoSync}`)
    } catch (e) {
      // 读取设置失败时按开启处理（默认行为），不阻塞启动
      BackgroundSync.enable()
      hilog.warn(HILOG_DOMAIN, TAG, 'apply background sync failed %{public}s', (e as Error).message)
    }
  }

}
