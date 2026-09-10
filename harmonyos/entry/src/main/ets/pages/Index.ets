/**
 * 应用根页面 —— 欢迎/登录门 + 主壳 (AppRoot)。
 */
import router from '@ohos.router'
import { AppDb } from '../data/db/AppDb'
import { Repo } from '../data/repository/DashboardRepository'
import { AccountInfo } from '../common/model/Models'
import { AppPrefs } from '../common/store/AppPrefs'
import { I18n } from '../common/i18n/I18n'
import { AppRoot } from '../ui/AppRoot'

@Entry
@Component
struct Index {
  @State private initialized: boolean = false
  @State private loggedIn: boolean = false
  @State private accountName: string = ''
  @State private initError: string = ''
  private syncTimer: number = -1
  /** 页面已隐藏标记: 定时器创建是 async 的, 期间可能已 onPageHide。 */
  private pageHidden: boolean = false

  aboutToAppear(): void {
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

  /**
   * 前台定时同步 (M5): 按设置间隔 (1/5/15/30 分钟) 增量同步; 退后台即停。
   *
   * autoSync 开关此前只写不读 —— 现在关闭时不再创建定时器 (与 Android
   * MainViewModel 的 autoSync 判定一致)。另外 intervalSec 的 await 之后必须
   * 复查 pageHidden: 否则 await 期间发生的 onPageHide 会让刚创建的定时器
   * 无人清理, 之后长期在后台空转。
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
    if (!autoSync) {
      return
    }
    if (this.pageHidden) {
      return
    }
    this.syncTimer = setInterval(() => {
      Repo.get().syncAll('incremental')
    }, intervalSec * 1000)
  }

  private stopForegroundSync(): void {
    if (this.syncTimer >= 0) {
      clearInterval(this.syncTimer)
      this.syncTimer = -1
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
      // DB 打开/迁移失败此前无处理: 页面会永远停在转圈且抛未捕获异常
      this.initError = (e as Error).message
      return
    }
    this.initialized = true
    await this.refresh()
  }

  private async refresh(): Promise<void> {
    if (!AppDb.isReady()) {
      return
    }
    const acct: AccountInfo | null = await Repo.get().account()
    this.loggedIn = acct !== null && acct.hasToken
    this.accountName = acct !== null ? acct.name : ''
    if (this.loggedIn) {
      // 冷启动拉配额: 此前唯一入口是 syncAll (需用户手动点同步), 只跑后台
      // 增量同步的应用打开首页一直是"暂无配额数据". ensureQuota 自带 30s 缓存
      // 与防重入, 重复调用无害。
      Repo.get().ensureQuota().catch(() => {})
    }
  }

  build() {
    if (this.initError.length > 0) {
      Column({ space: 12 }) {
        Text(I18n.t('db_init_failed')).fontSize(15).fontColor('#E74C3C')
        Text(this.initError).fontSize(12).fontColor('#888888').textAlign(TextAlign.Center)
      }
      .width('100%')
      .height('100%')
      .padding(24)
      .justifyContent(FlexAlign.Center)
      .backgroundColor(AppPrefs.isDarkMode() ? '#12141A' : '#FAFAFC')
    } else if (!this.initialized) {
      Column() {
        LoadingProgress()
          .width(40)
          .height(40)
      }
      .width('100%')
      .height('100%')
      .justifyContent(FlexAlign.Center)
      .backgroundColor(AppPrefs.isDarkMode() ? '#12141A' : '#FAFAFC')
    } else if (!this.loggedIn) {
      Column({ space: 14 }) {
        Image($r('app.media.icon'))
          .width(96)
          .height(96)
        Text('GoGauge')
          .fontSize(34)
          .fontWeight(FontWeight.Bold)
          .fontColor(AppPrefs.isDarkMode() ? '#E8EAED' : '#222222')
        Text(I18n.t('welcome_sub')).fontSize(15).fontColor('#888888')
        Blank()
        Text(I18n.t('welcome_hint')).fontSize(13).fontColor('#666666')
        Button(I18n.t('goLogin'))
          .width(220)
          .height(44)
          .onClick(() => {
            router.pushUrl({ url: 'pages/LoginPage' })
          })
        Blank()
      }
      .width('100%')
      .height('100%')
      .padding(24)
      .justifyContent(FlexAlign.Center)
      .backgroundColor(AppPrefs.isDarkMode() ? '#12141A' : '#FAFAFC')
    } else {
      AppRoot({ onLogout: () => {
        // 登出后立即回到欢迎页并停掉前台定时器 (否则会继续跑"未登录"同步)
        this.loggedIn = false
        this.accountName = ''
        this.stopForegroundSync()
      } })
    }
  }
}