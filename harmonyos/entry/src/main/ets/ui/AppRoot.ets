/**
 * 主壳 —— 一多自适应: 窄屏底部 TabBar, 宽屏(PC/2in1/平板横屏)左侧导航。
 * 子页面通过 refreshToken(带 @Watch) 统一触发刷新。
 */
import { Repo } from '../data/repository/DashboardRepository'
import { I18n } from '../common/i18n/I18n'
import { Theme } from './theme/Theme'
import { HomePage } from './pages/HomePage'
import { StatsPage } from './pages/StatsPage'
import { RecordsPage } from './pages/RecordsPage'
import { SettingsPage } from './pages/SettingsPage'

@Component
export struct AppRoot {
  @State private wide: boolean = false
  @State private tab: string = 'home'
  @State private refreshToken: number = 0
  @State private accountName: string = ''
  @State private syncing: boolean = false
  @State private syncMsg: string = ''
  /** Index 的数据刷新世代 (配额拉取/定时同步完成后 +1): 转发给子页面触发重载。 */
  @Prop @Watch('onExternalRefresh') externalRefresh: number = 0
  /**
   * 外观版本号 (AppStorage 广播, 由 AppPrefs 在主题/语言/货币变更时 +1)。
   *
   * 主题色板与文案是 build 期由 Theme/I18n 现算的静态值, ArkUI 增量更新不会因
   * AppStorage 变化重建这些元素 —— 这里用奇偶分支强制重建整棵外壳子树, 让顶栏与
   * 已渲染页面立即采用新主题/新文案 (此前必须切一次 tab 才统一)。
   */
  @StorageLink('gg_appearance') appearance: number = 0
  /** 登出回调: 由 Index 传入, 用于把根页面切回欢迎/登录门。 */
  onLogout: () => void = () => {}

  aboutToAppear(): void {
    this.refreshAccount()
  }

  /** 外部刷新世代变化 (配额到位/定时同步完成): 重载当前页数据。 */
  onExternalRefresh(): void {
    this.refreshToken++
    this.refreshAccount()
  }

  private async refreshAccount(): Promise<void> {
    const acct = await Repo.get().account()
    this.accountName = acct !== null ? acct.name : ''
  }

  /** 切 tab 时刷新外壳外观/文案 (语言/主题变化即时生效)。 */
  private selectTab(key: string): void {
    this.tab = key
    this.refreshToken++
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
    // 两个分支内容相同: 外观版本号奇偶切换 = 整棵外壳子树重建 (见 appearance 注释)
    if (this.appearance % 2 === 0) {
      this.shell()
    } else {
      this.shell()
    }
  }

  @Builder
  shell() {
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
            SettingsPage({ refreshToken: this.refreshToken })
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
        .fontColor(Theme.text())
      Blank()
      Text(this.accountName)
        .fontSize(12)
        .fontColor(Theme.sub())
      if (this.syncMsg.length > 0) {
        Text(this.syncMsg)
          .fontSize(11)
          .fontColor(Theme.faint())
          .maxLines(1)
      }
      Button(this.syncing ? I18n.t('syncing') : I18n.t('sync'))
        .fontSize(12)
        .height(30)
        .backgroundColor(Theme.accent())
        .enabled(!this.syncing)
        .onClick(() => {
          this.doSync()
        })
      Button(I18n.t('logout'))
        .fontSize(12)
        .height(30)
        .backgroundColor(Theme.danger())
        .onClick(async () => {
          await Repo.get().logout()
          this.accountName = ''
          // 回到未登录态: Index 的 loggedIn 只在 onPageShow 刷新, 如不主动
          // 通知, 登出后会继续停留在仪表盘外壳 (且前台定时器还在跑 未登录 同步)
          this.onLogout()
        })
    }
    .width('100%')
    .height(48)
    .padding({ left: 12, right: 12 })
    .backgroundColor(Theme.surface())
  }

  @Builder
  bottomNav() {
    Row() {
      this.navItem('home', I18n.t('tab_home'))
      this.navItem('stats', I18n.t('tab_stats'))
      this.navItem('records', I18n.t('tab_records'))
      this.navItem('settings', I18n.t('tab_settings'))
    }
    .width('100%')
    .height(52)
    .backgroundColor(Theme.surface())
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
      this.selectTab(key)
    })
  }

  @Builder
  sideNav() {
    Column({ space: 4 }) {
      Text('GoGauge')
        .fontSize(18)
        .fontWeight(FontWeight.Bold)
        .fontColor(Theme.text())
        .padding({ top: 16, bottom: 20 })
      this.sideItem('home', `⌂ ${I18n.t('tab_home')}`)
      this.sideItem('stats', `◔ ${I18n.t('tab_stats')}`)
      this.sideItem('records', `≡ ${I18n.t('tab_records')}`)
      this.sideItem('settings', `⚙ ${I18n.t('tab_settings')}`)
      Blank()
    }
    .width(150)
    .height('100%')
    .padding({ left: 8, right: 8 })
    .backgroundColor(Theme.surface())
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
      .hoverEffect(HoverEffect.Highlight)
      .onClick(() => {
        this.selectTab(key)
      })
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