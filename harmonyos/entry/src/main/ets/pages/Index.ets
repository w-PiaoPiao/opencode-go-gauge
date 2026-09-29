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
  /** 数据刷新世代: 配额/同步完成后 +1, 经 AppRoot 透传给子页面触发重载。 */
  @State private refreshToken: number = 0
  private syncTimer: number = -1
  /**
   * 定时器世代号: startForegroundSync 内的 await 之后据此判断自己是否已被作废。
   * (仅靠 syncTimer 句柄不够: 两次进入交叠时, #2 的 stop 可能发生在 #1 赋值句柄之前,
   *  于是 #1 之后创建的定时器无人清理 —— 登出/退后台都清不掉的野定时器。)
   */
  private syncGen: number = 0
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
   * 复查 pageHidden 与世代号: 否则 await 期间发生的 onPageHide/重入会让刚创建的
   * 定时器无人清理, 之后长期在后台空转。
   */
  private async startForegroundSync(): Promise<void> {
    this.stopForegroundSync()
    this.syncGen++
    const gen = this.syncGen
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
    // await 期间可能又进入了新一轮 start (或 onPageHide/登出): 本轮的定时器已作废,
    // 绝不赋值句柄 —— 保证任意时刻最多一个定时器存活
    if (gen !== this.syncGen || this.pageHidden || !this.loggedIn) {
      return
    }
    if (!autoSync) {
      return
    }
    this.syncTimer = setInterval(() => {
      this.runScheduledSync()
    }, intervalSec * 1000)
  }

  /** 定时增量同步: 完成后通知页面重载 (否则同步结果只落库, 界面一直是旧数据)。 */
  private async runScheduledSync(): Promise<void> {
    try {
      await Repo.get().syncAll('incremental')
    } catch (e) {
      // 单次失败不中断: 下一周期继续
    }
    if (!this.pageHidden) {
      this.refreshToken++
    }
  }

  private stopForegroundSync(): void {
    // 世代 +1 使进行中的 startForegroundSync 作废 (其 await 后不再创建定时器)
    this.syncGen++
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
    // 首帧 onPageShow 时 AppDb.init 尚未完成 (initialized=false), 那次不会建定时器;
    // 初始化完成后补启, 否则 syncIntervalSec 设置形同失效
    if (!this.pageHidden) {
      this.startForegroundSync()
    }
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
      // 配额走网络, 必然晚于 loadDashboard 的本地聚合 —— 完成后必须通知页面重载,
      // 否则首页配额区一直空着直到切 tab (子页面靠 refreshToken 触发)。
      Repo.get().ensureQuota().then(() => {
        this.refreshToken++
      }).catch(() => {})
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
      AppRoot({
        // 配额/定时同步完成后 +1: AppRoot 会把它透传给当前页面的 refreshToken 触发重载
        externalRefresh: this.refreshToken,
        onLogout: () => {
          // 登出后立即回到欢迎页并停掉前台定时器 (否则会继续跑"未登录"同步)
          this.loggedIn = false
          this.accountName = ''
          this.stopForegroundSync()
        },
      })
    }
  }
}