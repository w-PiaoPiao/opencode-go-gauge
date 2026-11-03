/**
 * 应用根页面 —— 首次启动隐私合规弹窗 + 欢迎门 + 主壳（AppRoot）。
 *
 * 合规（AppGallery 7.1/7.5）：
 *  - 首次启动展示隐私政策弹窗，必须「同意并继续」后才能登录；拒绝则无法使用；
 *  - 欢迎页与设置页均提供应用内可点击的隐私政策入口（pages/PrivacyPage）。
 *
 * 调试/截图（仅 debug 构建，见 common/dev/DemoSeed.ets）：
 *  - 启动参数 `--ps demo 1`（仅 debug 构建）时自动视为已同意隐私政策并注入演示数据；
 *  - 启动参数 `--ps page home|stats|records|settings` 指定进入的页签。
 */
import router from '@ohos.router'
import { font, promptAction } from '@kit.ArkUI'
import BuildProfile from 'BuildProfile'
import { AppDb } from '../data/db/AppDb'
import { Repo } from '../data/repository/DashboardRepository'
import { AccountInfo } from '../common/model/Models'
import { AppPrefs } from '../common/store/AppPrefs'
import { I18n } from '../common/i18n/I18n'
import { LaunchParams } from '../common/dev/LaunchParams'
import { DemoSeed } from '../common/dev/DemoSeed'
import { AppRoot } from '../ui/AppRoot'
import { PrivacyDialog } from '../ui/components/PrivacyDialog'
import { AppVersion } from '../common/AppVersion'
import { Theme, Dimens } from '../ui/theme/Theme'

@Entry
@Component
struct Index {
  @State private initialized: boolean = false
  @State private loggedIn: boolean = false
  @State private initError: string = ''
  @State private privacyAgreed: boolean = false
  @State private rootWidth: number = 0
  @State private entered: number = 0
  @State private demoRunning: boolean = false
  private syncTimer: number = -1
  /** 页面已隐藏标记：定时器创建是 async 的，期间可能已 onPageHide。 */
  private pageHidden: boolean = false
  /** 首启隐私弹窗（内含可点开的《隐私政策》链接，满足审核 7.1/7.5）。 */
  private privacyDialogCtrl: CustomDialogController = new CustomDialogController({
    builder: PrivacyDialog({
      lang: AppPrefs.getLanguage(),
      onAgree: () => {
        AppPrefs.setPrivacyAccepted(true)
        this.privacyAgreed = true
      },
      onDecline: () => {
        promptAction.showToast({ message: I18n.t('privacyDeclinedTip') })
      },
    }),
    autoCancel: false,
    customStyle: true,
    alignment: DialogAlignment.Center,
  })

  aboutToAppear(): void {
    this.registerSerifFont()
    this.init()
  }

  onPageShow(): void {
    this.pageHidden = false
    if (this.initialized) {
      this.refresh()
      this.startForegroundSync()
    }
  }

  onPageHide(): void {
    this.pageHidden = true
    this.stopForegroundSync()
  }

  aboutToDisappear(): void {
    this.stopForegroundSync()
  }

  /** 注册标题衬线字体（失败回退系统字体，不阻塞启动）。 */
  private registerSerifFont(): void {
    try {
      font.registerFont({
        familyName: 'GgSerif',
        familySrc: $rawfile('fonts/gg_serif_sc_regular.otf'),
      })
    } catch (e) {
      // 字体注册失败只影响标题观感，不影响功能
    }
  }

  private async init(): Promise<void> {
    if (this.initialized) {
      return
    }
    const host = this.getUIContext().getHostContext()
    if (host === undefined) {
      return
    }
    try {
      await AppDb.init(host)
    } catch (e) {
      this.initError = (e as Error).message
      return
    }
    // 启动参数：语言/主题/演示数据（仅 debug 构建；release 必须走正常隐私同意流程）
    if (BuildProfile.DEBUG) {
      DemoSeed.applyAppearance(LaunchParams.lang, LaunchParams.theme)
      if (LaunchParams.demo) {
        // 演示模式使用合成数据，不涉及真实个人信息；直接视为已同意，避免截图被弹窗遮挡
        AppPrefs.setPrivacyAccepted(true)
        await DemoSeed.run()
      }
    }
    this.privacyAgreed = AppPrefs.isPrivacyAccepted()
    this.initialized = true
    await this.refresh()
    animateTo({ duration: 260, curve: Curve.EaseOut }, () => {
      this.entered = 1
    })
    if (!this.privacyAgreed) {
      this.showPrivacyDialog()
    }
  }

  private async refresh(): Promise<void> {
    if (!AppDb.isReady()) {
      return
    }
    this.privacyAgreed = AppPrefs.isPrivacyAccepted()
    try {
      const acct: AccountInfo | null = await Repo.get().account()
      this.loggedIn = acct !== null && acct.hasToken
      if (this.loggedIn) {
        Repo.get().ensureQuota().catch(() => {
        })
      }
    } catch (e) {
      this.loggedIn = false
    }
  }

  /**
   * 前台定时同步：按设置间隔（1/5/15/30 分钟）增量同步；退后台即停。
   * await 之后必须复查 pageHidden，否则期间的 onPageHide 会让刚创建的定时器无人清理。
   */
  private async startForegroundSync(): Promise<void> {
    this.stopForegroundSync()
    if (!this.loggedIn) {
      return
    }
    let intervalSec = 300
    let autoSync = true
    try {
      const s = await Repo.get().settings()
      intervalSec = s.syncIntervalSec
      autoSync = s.autoSync
    } catch (e) {
      // 默认 5 分钟 / 开启
    }
    if (!autoSync || this.pageHidden) {
      return
    }
    this.syncTimer = setInterval(() => {
      // 每次触发都重读设置：设置页关闭自动同步/改间隔后无需重启应用
      this.tickSync()
    }, intervalSec * 1000)
  }

  private async tickSync(): Promise<void> {
    try {
      const s = await Repo.get().settings()
      if (!s.autoSync) {
        return
      }
      await Repo.get().syncAll('incremental')
    } catch (e) {
      // 后台同步失败静默忽略
    }
  }

  private stopForegroundSync(): void {
    if (this.syncTimer >= 0) {
      clearInterval(this.syncTimer)
      this.syncTimer = -1
    }
  }

  private showPrivacyDialog(): void {
    this.privacyDialogCtrl.open()
  }

  private openLogin(): void {
    if (!this.privacyAgreed) {
      this.showPrivacyDialog()
      return
    }
    router.pushUrl({ url: 'pages/LoginPage', params: { mode: 'add' } })
  }

  private openPrivacy(): void {
    router.pushUrl({ url: 'pages/PrivacyPage' })
  }

  private async startDemo(): Promise<void> {
    if (this.demoRunning) {
      return
    }
    this.demoRunning = true
    AppPrefs.setPrivacyAccepted(true)
    this.privacyAgreed = true
    const ok = await DemoSeed.run()
    this.demoRunning = false
    if (ok) {
      await this.refresh()
    }
  }

  @Builder
  featureRow(text: string) {
    Row({ space: 8 }) {
      Image($r('app.media.ic_check'))
        .width(14)
        .height(14)
        .fillColor(Theme.green())
      Text(text)
        .fontSize(13)
        .fontColor(Theme.sub())
        .layoutWeight(1)
    }
    .width('100%')
  }

  @Builder
  welcomeView() {
    Column() {
      Blank()
      Column({ space: 16 }) {
        Column({ space: 8 }) {
          Image($r('app.media.icon'))
            .width(84)
            .height(84)
            .borderRadius(20)
          Text('GoGauge')
            .fontSize(30)
            .fontWeight(FontWeight.Bold)
            .fontFamily('GgSerif')
            .fontColor(Theme.text())
          Text(I18n.t('welcome_sub'))
            .fontSize(12)
            .fontColor(Theme.faint())
            .textAlign(TextAlign.Center)
        }
        .width('100%')

        Column({ space: 10 }) {
          this.featureRow(I18n.t('welcomeFeat1'))
          this.featureRow(I18n.t('welcomeFeat2'))
          this.featureRow(I18n.t('welcomeFeat3'))
        }
        .width('100%')
        .padding(14)
        .backgroundColor(Theme.surface())
        .borderRadius(Dimens.CARD_RADIUS)
        .border({ width: 1, color: Theme.border() })

        Button(I18n.t('goLogin'))
          .width('100%')
          .height(46)
          .fontSize(15)
          .fontColor('#FFFFFF')
          .backgroundColor(Theme.accent())
          .borderRadius(10)
          .onClick(() => {
            this.openLogin()
          })

        if (BuildProfile.DEBUG) {
          Button(I18n.t('demoMode'))
            .width('100%')
            .height(40)
            .fontSize(13)
            .fontColor(Theme.sub())
            .backgroundColor(Theme.surfaceSoft())
            .borderRadius(10)
            .onClick(() => {
              this.startDemo()
            })
          Text(I18n.t('demoModeHint'))
            .fontSize(10)
            .fontColor(Theme.faint())
        }

        Row({ space: 4 }) {
          Image($r('app.media.ic_check'))
            .width(11)
            .height(11)
            .fillColor(Theme.faint())
          Text(I18n.t('privacyShort'))
            .fontSize(11)
            .fontColor(Theme.faint())
            .layoutWeight(1)
        }
        .width('100%')

        Text(I18n.t('privacyEntry'))
          .fontSize(12)
          .fontColor(Theme.accent())
          .onClick(() => {
            this.openPrivacy()
          })
      }
      .width('100%')
      .constraintSize({ maxWidth: 440 })
      .padding({ left: 4, right: 4 })
      Blank()
      Text(I18n.t('pageFoot').replace('{version}', AppVersion.display()))
        .fontSize(10)
        .fontColor(Theme.faint())
        .textAlign(TextAlign.Center)
    }
    .width('100%')
    .height('100%')
    .padding({ left: 22, right: 22, top: 20, bottom: 18 })
    .backgroundColor(Theme.bg())
    .opacity(this.entered)
    .translate({ y: (1 - this.entered) * 6 })
    .onAreaChange((_old: Area, nv: Area) => {
      this.rootWidth = Number(nv.width)
    })
  }

  build() {
    if (this.initError.length > 0) {
      Column({ space: 12 }) {
        Text(I18n.t('db_init_failed')).fontSize(15).fontColor(Theme.danger())
        Text(this.initError)
          .fontSize(12)
          .fontColor(Theme.sub())
          .textAlign(TextAlign.Center)
      }
      .width('100%')
      .height('100%')
      .padding(24)
      .justifyContent(FlexAlign.Center)
      .backgroundColor(Theme.bg())
    } else if (!this.initialized) {
      Column({ space: 14 }) {
        LoadingProgress()
          .width(40)
          .height(40)
          .color(Theme.accent())
        Text('GoGauge')
          .fontSize(14)
          .fontColor(Theme.faint())
      }
      .width('100%')
      .height('100%')
      .justifyContent(FlexAlign.Center)
      .backgroundColor(Theme.bg())
    } else if (!this.loggedIn) {
      this.welcomeView()
    } else {
      AppRoot({
        initialTab: LaunchParams.page.length > 0 ? LaunchParams.page : 'home',
        onLogout: () => {
          this.loggedIn = false
          this.stopForegroundSync()
        },
      })
    }
  }
}
