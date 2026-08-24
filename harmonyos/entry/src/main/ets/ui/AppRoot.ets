/**
 * 主壳 —— 一多自适应: 窄屏底部 TabBar, 宽屏(PC/2in1/平板横屏)左侧导航。
 * 子页面通过 refreshToken(带 @Watch) 统一触发刷新。
 */
import { Repo } from '../data/repository/DashboardRepository'
import { HomePage } from './pages/HomePage'
import { StatsPage } from './pages/StatsPage'
import { RecordsPage } from './pages/RecordsPage'

@Component
export struct AppRoot {
  @State private wide: boolean = false
  @State private tab: string = 'home'
  @State private refreshToken: number = 0
  @State private accountName: string = ''
  @State private syncing: boolean = false
  @State private syncMsg: string = ''

  aboutToAppear(): void {
    this.refreshAccount()
  }

  private async refreshAccount(): Promise<void> {
    const acct = await Repo.get().account()
    this.accountName = acct !== null ? acct.name : ''
  }

  private async doSync(): Promise<void> {
    if (this.syncing) {
      return
    }
    this.syncing = true
    this.syncMsg = '同步中…'
    try {
      await Repo.get().syncAll('incremental')
      this.syncMsg = Repo.get().progress.message
      this.refreshToken++
    } catch (e) {
      this.syncMsg = `同步失败: ${(e as Error).message}`
    }
    this.syncing = false
    this.refreshAccount()
  }

  build() {
    Row() {
      if (this.wide) {
        this.sideNav()
      }
      Column() {
        this.topBar()
        Row() {
          if (this.tab === 'home') {
            HomePage({ refreshToken: this.refreshToken })
          } else if (this.tab === 'stats') {
            StatsPage({ refreshToken: this.refreshToken })
          } else if (this.tab === 'records') {
            RecordsPage({ refreshToken: this.refreshToken })
          } else {
            this.settingsPlaceholder()
          }
        }
        .layoutWeight(1)
        if (!this.wide) {
          this.bottomNav()
        }
      }
      .layoutWeight(1)
      .height('100%')
    }
    .width('100%')
    .height('100%')
    .onAreaChange((_oldValue: Area, newValue: Area) => {
      this.wide = (newValue.width as number) > 760
    })
  }

  @Builder
  topBar() {
    Row({ space: 8 }) {
      Text('GoGauge')
        .fontSize(16)
        .fontWeight(FontWeight.Bold)
      Blank()
      Text(this.accountName)
        .fontSize(12)
        .fontColor('#666666')
      if (this.syncMsg.length > 0) {
        Text(this.syncMsg)
          .fontSize(11)
          .fontColor('#999999')
          .maxLines(1)
      }
      Button(this.syncing ? '同步中…' : '同步')
        .fontSize(12)
        .height(30)
        .backgroundColor('#3B82F6')
        .enabled(!this.syncing)
        .onClick(() => {
          this.doSync()
        })
      Button('退出')
        .fontSize(12)
        .height(30)
        .backgroundColor('#E74C3C')
        .onClick(async () => {
          await Repo.get().logout()
          this.accountName = ''
        })
    }
    .width('100%')
    .height(48)
    .padding({ left: 12, right: 12 })
    .backgroundColor('#FFFFFF')
  }

  @Builder
  bottomNav() {
    Row() {
      this.navItem('home', '首页')
      this.navItem('stats', '统计')
      this.navItem('records', '记录')
      this.navItem('settings', '设置')
    }
    .width('100%')
    .height(52)
    .backgroundColor('#FFFFFF')
  }

  @Builder
  navItem(key: string, label: string) {
    Column({ space: 2 }) {
      Text(this.tabIcon(key))
        .fontSize(18)
        .fontColor(this.tab === key ? '#3B82F6' : '#999999')
      Text(label)
        .fontSize(11)
        .fontColor(this.tab === key ? '#3B82F6' : '#999999')
    }
    .layoutWeight(1)
    .height(52)
    .justifyContent(FlexAlign.Center)
    .onClick(() => {
      this.tab = key
    })
  }

  @Builder
  sideNav() {
    Column({ space: 4 }) {
      Text('GoGauge')
        .fontSize(18)
        .fontWeight(FontWeight.Bold)
        .padding({ top: 16, bottom: 20 })
      this.sideItem('home', '⌂ 首页')
      this.sideItem('stats', '◔ 统计')
      this.sideItem('records', '≡ 记录')
      this.sideItem('settings', '⚙ 设置')
      Blank()
    }
    .width(150)
    .height('100%')
    .padding({ left: 8, right: 8 })
    .backgroundColor('#FFFFFF')
  }

  @Builder
  sideItem(key: string, label: string) {
    Text(label)
      .fontSize(14)
      .fontColor(this.tab === key ? '#3B82F6' : '#555555')
      .fontWeight(this.tab === key ? FontWeight.Medium : FontWeight.Normal)
      .width('100%')
      .padding({ left: 12, top: 10, bottom: 10 })
      .borderRadius(8)
      .backgroundColor(this.tab === key ? '#EFF4FF' : '#00000000')
      .onClick(() => {
        this.tab = key
      })
  }

  @Builder
  settingsPlaceholder() {
    Column({ space: 12 }) {
      Text('设置页 (M4 开发中)')
        .fontSize(16)
        .fontWeight(FontWeight.Bold)
      Text(`账号: ${this.accountName}`)
        .fontSize(13)
        .fontColor('#666666')
      Button('退出登录')
        .height(40)
        .backgroundColor('#E74C3C')
        .onClick(async () => {
          await Repo.get().logout()
          this.accountName = ''
        })
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center)
  }

  private tabIcon(key: string): string {
    if (key === 'home') {
      return '⌂'
    }
    if (key === 'stats') {
      return '◔'
    }
    if (key === 'records') {
      return '≡'
    }
    return '⚙'
  }
}