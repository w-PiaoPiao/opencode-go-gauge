/**
 * 应用根页面 —— 欢迎/登录门 + 主壳 (AppRoot)。
 */
import router from '@ohos.router'
import { AppDb } from '../data/db/AppDb'
import { Repo } from '../data/repository/DashboardRepository'
import { AccountInfo } from '../common/model/Models'
import { AppRoot } from '../ui/AppRoot'

@Entry
@Component
struct Index {
  @State private initialized: boolean = false
  @State private loggedIn: boolean = false
  @State private accountName: string = ''
  private syncTimer: number = -1

  aboutToAppear(): void {
    this.init()
  }

  onPageShow(): void {
    if (this.initialized) {
      this.refresh()
      this.startForegroundSync()
    }
  }

  onPageHide(): void {
    this.stopForegroundSync()
  }

  /** 前台定时同步 (M5): 按设置间隔 (1/5/15/30 分钟) 增量同步; 退后台即停。 */
  private async startForegroundSync(): Promise<void> {
    this.stopForegroundSync()
    if (!this.loggedIn) {
      return
    }
    let intervalSec = 300
    try {
      intervalSec = (await Repo.get().settings()).syncIntervalSec
    } catch (e) {
      // 默认 5 分钟
    }
    this.syncTimer = setInterval(() => {
      Repo.get().syncUsage('incremental')
    }, intervalSec * 1000)
  }

  private stopForegroundSync(): void {
    if (this.syncTimer >= 0) {
      clearInterval(this.syncTimer)
      this.syncTimer = -1
    }
  }

  private async init(): Promise<void> {
    if (!this.initialized) {
      await AppDb.init(getContext(this))
      this.initialized = true
      await this.refresh()
    }
  }

  private async refresh(): Promise<void> {
    if (!AppDb.isReady()) {
      return
    }
    const acct: AccountInfo | null = await Repo.get().account()
    this.loggedIn = acct !== null && acct.hasToken
    this.accountName = acct !== null ? acct.name : ''
  }

  build() {
    if (!this.initialized) {
      Column() {
        LoadingProgress()
          .width(40)
          .height(40)
      }
      .width('100%')
      .height('100%')
      .justifyContent(FlexAlign.Center)
      .backgroundColor('#FAFAFC')
    } else if (!this.loggedIn) {
      Column({ space: 14 }) {
        Image($r('app.media.icon'))
          .width(96)
          .height(96)
        Text('GoGauge')
          .fontSize(34)
          .fontWeight(FontWeight.Bold)
        Text('OpenCode Go 用量仪表盘 · HarmonyOS NEXT')
          .fontSize(15)
          .fontColor('#888888')
        Blank()
        Text('登录后自动同步用量数据，数据仅保存在本机')
          .fontSize(13)
          .fontColor('#666666')
        Button('立即登录')
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
      .backgroundColor('#FAFAFC')
    } else {
      AppRoot()
    }
  }
}