/**
 * 应用根页面 —— 初始化数据库/仓库, 展示登录态与同步验证入口 (M2 占位)。
 * M3 起替换为底部导航 (手机) / 侧边导航 (PC) 主壳。
 */
import router from '@ohos.router'
import { AppDb } from '../data/db/AppDb'
import { Repo } from '../data/repository/DashboardRepository'
import { AccountInfo } from '../common/model/Models'

@Entry
@Component
struct Index {
  @State private initialized: boolean = false
  @State private accountName: string = ''
  @State private loggedIn: boolean = false
  @State private syncing: boolean = false
  @State private syncMsg: string = ''

  aboutToAppear(): void {
    this.init()
  }

  onPageShow(): void {
    this.refresh()
  }

  private async init(): Promise<void> {
    const ctx = getContext(this)
    await AppDb.init(ctx)
    this.initialized = true
    this.refresh()
  }

  private async refresh(): Promise<void> {
    if (!AppDb.isReady()) {
      return
    }
    const acct: AccountInfo | null = await Repo.get().account()
    this.loggedIn = acct !== null && acct.hasToken
    this.accountName = acct !== null ? acct.name : ''
  }

  private async doSync(): Promise<void> {
    if (this.syncing) {
      return
    }
    this.syncing = true
    this.syncMsg = '同步中…'
    try {
      await Repo.get().syncAll('full')
      const s = Repo.get().progress
      this.syncMsg = s.message.length > 0 ? s.message : '同步完成'
    } catch (e) {
      this.syncMsg = `同步失败: ${(e as Error).message}`
    }
    this.syncing = false
    this.refresh()
  }

  build() {
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

      if (!this.loggedIn) {
        Text('未登录，登录后开始同步用量数据')
          .fontSize(13)
          .fontColor('#666666')
        Button('立即登录')
          .width(220)
          .height(44)
          .onClick(() => {
            router.pushUrl({ url: 'pages/LoginPage' })
          })
      } else {
        Text(`已登录: ${this.accountName}`)
          .fontSize(15)
          .fontColor('#2E7D32')
        Text(this.syncMsg.length > 0 ? this.syncMsg : '')
          .fontSize(13)
          .fontColor('#888888')
        Button(this.syncing ? '同步中…' : '全量同步')
          .width(220)
          .height(44)
          .enabled(!this.syncing)
          .onClick(() => {
            this.doSync()
          })
        Button('退出登录')
          .width(220)
          .height(40)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .onClick(async () => {
            await Repo.get().logout()
            this.refresh()
          })
      }

      Blank()
    }
    .width('100%')
    .height('100%')
    .padding(24)
    .justifyContent(FlexAlign.Center)
    .backgroundColor('#FAFAFC')
  }
}