/**
 * 主壳 —— 一套代码两种形态（鸿蒙一多自适应）：
 *  - compact（宽 <840vp，手机形态）：底部 TabBar + 页面自带页头，布局对标安卓版；
 *  - expanded（>=840vp，平板横屏 / 2in1 / PC）：桌面式顶栏 + 左侧图标导航 + 内容区，
 *    布局对标桌面版（app/web）。
 *
 * 鸿蒙独有适配：Tabs 手势切换、页面转场过渡、图标侧栏弹性指示、2in1 悬停反馈、
 * 键盘快捷键（Ctrl+1..4 切页 / Ctrl+R、F5 刷新）、账号切换底部 Sheet（bindSheet）。
 */
import { promptAction } from '@kit.ArkUI'
import { Repo } from '../data/repository/DashboardRepository'
import { I18n } from '../common/i18n/I18n'
import { AppVersion } from '../common/AppVersion'
import { AppPrefs } from '../common/store/AppPrefs'
import { AccountInfo, SyncState } from '../common/model/Models'
import { Theme, Dimens } from './theme/Theme'
import { AccountChip } from './components/Cards'
import { HomePage } from './pages/HomePage'
import { StatsPage } from './pages/StatsPage'
import { RecordsPage } from './pages/RecordsPage'
import { SettingsPage } from './pages/SettingsPage'
import BuildProfile from 'BuildProfile'
import { LaunchParams } from '../common/dev/LaunchParams'

/** 导航项。 */
interface NavItem {
  key: string
  icon: Resource
  label: string
}

/** 快捷键 keyCode（@ohos.multimodalInput.keyCode）。 */
const KB_1: number = 2001
const KB_4: number = 2004
const KB_R: number = 2034
const KB_F5: number = 2094

@Component
export struct AppRoot {
  @Prop initialTab: string = ''
  @State private tab: string = 'home'
  @State private wide: boolean = false
  @State private rootWidth: number = 0
  @State private refreshToken: number = 0
  @State private accountName: string = ''
  @State private accountCount: number = 0
  @State private activeId: number = 0
  @State private accounts: AccountInfo[] = []
  @State private syncing: boolean = false
  @State private syncLine: string = ''
  @State private showSwitcher: boolean = false
  /** 主题/语言切换后壳层重建计数（设置页通过 AppStorage 递增，壳层 @StorageLink 监听）。 */
  @State private chromeToken: number = 0
  /** 登录态失效/主动退出时回调 Index。 */
  onLogout: () => void = () => {
  }

  aboutToAppear(): void {
    // 启动页参数仅 debug 构建生效（release 始终从首页进入）
    const p = this.initialTab.length > 0 ? this.initialTab : (BuildProfile.DEBUG ? LaunchParams.page : '')
    if (p === 'stats' || p === 'records' || p === 'settings') {
      this.tab = p
    }
    this.refreshHeader()
  }

  private async refreshHeader(): Promise<void> {
    try {
      const repo = Repo.get()
      const acct = await repo.account()
      this.accountName = acct !== null ? acct.name : ''
      this.activeId = await repo.activeAccountId()
      const list = await repo.accounts()
      this.accounts = list
      let logged = 0
      for (const a of list) {
        if (a.hasToken) {
          logged++
        }
      }
      this.accountCount = logged
      if ((BuildProfile.DEBUG && LaunchParams.demo) || repo.isDemoQuota()) {
        // 演示/截图模式：数据为本地合成数据，不显示「上次同步」占位（商店图观感 + 不说谎）
        this.syncLine = I18n.t('localData')
      } else {
        const st = await repo.syncState()
        this.syncLine = this.buildSyncLine(st)
      }
    } catch (e) {
      // 壳层信息失败不阻塞页面
    }
  }

  private buildSyncLine(st: SyncState): string {
    if (st.lastSyncAt === null || st.lastSyncAt.length === 0) {
      return `${I18n.t('notSyncedYet')} · ${st.totalRecords} ${I18n.t('items')}`
    }
    const rel = this.relativeTime(st.lastSyncAt)
    return `${I18n.t('lastSync')} ${rel} · ${st.totalRecords} ${I18n.t('items')}`
  }

  private relativeTime(iso: string | null): string {
    if (iso === null || iso.length === 0) {
      return I18n.t('never')
    }
    const ms = Date.parse(iso)
    if (Number.isNaN(ms)) {
      return I18n.t('never')
    }
    const diff = Math.max(0, Math.floor((Date.now() - ms) / 1000))
    if (diff < 60) {
      return I18n.t('justNow')
    }
    if (diff < 3600) {
      return `${Math.floor(diff / 60)} ${I18n.t('minAgo')}`
    }
    if (diff < 86400) {
      return `${Math.floor(diff / 3600)} ${I18n.t('hrAgo')}`
    }
    return `${Math.floor(diff / 86400)} ${I18n.t('dayAgo')}`
  }

  private selectTab(key: string): void {
    if (key === this.tab) {
      return
    }
    this.tab = key
    this.refreshToken++
    this.refreshHeader()
  }

  private async doSync(): Promise<void> {
    if (this.syncing) {
      return
    }
    this.syncing = true
    try {
      await Repo.get().syncAll('incremental')
      this.refreshToken++
      await this.refreshHeader()
    } catch (e) {
      promptAction.showToast({ message: I18n.t('sync_fail') })
    }
    this.syncing = false
  }

  private toggleTheme(): void {
    AppPrefs.setDarkMode(!Theme.isDark())
    this.chromeToken++
    this.refreshToken++
  }

  private async doLogout(): Promise<void> {
    this.showSwitcher = false
    try {
      await Repo.get().logout()
    } catch (e) {
      // 登出清理失败也要回欢迎页（token 已清）
    }
    this.onLogout()
  }

  private async switchAccount(id: number): Promise<void> {
    if (id === this.activeId) {
      this.showSwitcher = false
      return
    }
    const ok = await Repo.get().switchAccount(id)
    this.showSwitcher = false
    if (ok) {
      this.refreshToken++
      await this.refreshHeader()
      promptAction.showToast({ message: I18n.t('switchedAccount') })
    }
  }

  /**
   * 读取 chromeToken 后再取主题色：ArkUI 只追踪 build 中真正读取过的状态，
   * 外壳容器的颜色属性必须依赖 chromeToken，否则主题/语言切换后容器仍是旧配色。
   */
  private chromeBg(): ResourceColor {
    const tick: number = this.chromeToken
    return Theme.bg()
  }

  private chromeSurface(): ResourceColor {
    const tick: number = this.chromeToken
    return Theme.surface()
  }

  private chromeBorder(): ResourceColor {
    const tick: number = this.chromeToken
    return Theme.border()
  }

  private navItems(): NavItem[] {
    const items: NavItem[] = [
      { key: 'home', icon: $r('app.media.ic_home'), label: I18n.t('tab_home') },
      { key: 'stats', icon: $r('app.media.ic_stats'), label: I18n.t('tab_stats') },
      { key: 'records', icon: $r('app.media.ic_records'), label: I18n.t('tab_records') },
      { key: 'settings', icon: $r('app.media.ic_settings'), label: I18n.t('tab_settings') },
    ]
    return items
  }

  @Builder
  pageBody() {
    if (this.tab === 'home') {
      Column() {
        HomePage({
          refreshToken: this.refreshToken,
          onOpenAccountSwitcher: () => {
            this.showSwitcher = true
          },
        })
      }
      .width('100%')
      .height('100%')
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 8 })).animation({ duration: 220, curve: Curve.EaseOut }))
    } else if (this.tab === 'stats') {
      Column() {
        StatsPage({
          refreshToken: this.refreshToken,
          onOpenAccountSwitcher: () => {
            this.showSwitcher = true
          },
        })
      }
      .width('100%')
      .height('100%')
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 8 })).animation({ duration: 220, curve: Curve.EaseOut }))
    } else if (this.tab === 'records') {
      Column() {
        RecordsPage({
          refreshToken: this.refreshToken,
          onOpenAccountSwitcher: () => {
            this.showSwitcher = true
          },
        })
      }
      .width('100%')
      .height('100%')
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 8 })).animation({ duration: 220, curve: Curve.EaseOut }))
    } else {
      Column() {
        SettingsPage({
          refreshToken: this.refreshToken,
          onLogout: () => {
            this.doLogout()
          },
          onOpenAccountSwitcher: () => {
            this.showSwitcher = true
          },
          onAppearanceChanged: () => {
            // 主题/语言切换后立即重建壳层 + 当前页
            this.chromeToken++
            this.refreshToken++
          },
        })
      }
      .width('100%')
      .height('100%')
      .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 8 })).animation({ duration: 220, curve: Curve.EaseOut }))
    }
  }

  /**
   * 页面重建槽：主题/语言切换时 chromeToken 增减 1，if 分支翻转 -> 当前页整棵子树销毁重建。
   * ArkUI 部分更新只重跑"读取该状态的节点"，@Prop/@StorageLink 都不足以让当前页全量重渲染；
   * 这里用 if 分支切换强制 remount（外观切换会重置当前页滚动位置，可接受）。
   */
  @Builder
  pageSlot() {
    // key 随 chromeToken 变化 -> ArkUI 销毁旧子树并重建（if/else 同构分支会被 diff 复用，无法 remount）
    ForEach([this.chromeToken], (_tick: number) => {
      this.pageBody()
    }, (tick: number) => `page_${tick}`)
  }

  @Builder
  iconChip(icon: Resource, color: string, size: number) {
    Image(icon)
      .width(size)
      .height(size)
      .fillColor(color)
      .objectFit(ImageFit.Contain)
  }

  @Builder
  topBar() {
    Row({ space: 10 }) {
      Image($r('app.media.icon'))
        .width(24)
        .height(24)
        .borderRadius(7)
      Text('GoGauge')
        .fontSize(14)
        .fontWeight(FontWeight.Bold)
        .fontColor(Theme.text())
      Text(this.syncLine)
        .fontSize(11)
        .fontColor(Theme.faint())
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
        .layoutWeight(1)
      Row({ space: 5 }) {
        this.iconChip(Theme.isDark() ? $r('app.media.ic_sun') : $r('app.media.ic_moon'), Theme.sub(), 14)
        Text(Theme.isDark() ? I18n.t('themeLight') : I18n.t('themeDark'))
          .fontSize(12)
          .fontColor(Theme.sub())
      }
      .padding({ left: 10, right: 10, top: 5, bottom: 5 })
      .borderRadius(99)
      .border({ width: 1, color: Theme.border() })
      .hoverEffect(HoverEffect.Highlight)
      .onClick(() => {
        this.toggleTheme()
      })
      Row({ space: 5 }) {
        this.iconChip($r('app.media.ic_refresh'), Theme.amber(), 14)
        Text(this.syncing ? I18n.t('syncing') : I18n.t('refresh'))
          .fontSize(12)
          .fontColor(Theme.amber())
      }
      .padding({ left: 10, right: 10, top: 5, bottom: 5 })
      .borderRadius(99)
      .border({ width: 1, color: Theme.amber() })
      .hoverEffect(HoverEffect.Highlight)
      .onClick(() => {
        this.doSync()
      })
      AccountChip({
        name: this.accountName,
        count: this.accountCount,
        onTap: () => {
          this.showSwitcher = true
        },
      })
    }
    .width('100%')
    .height(Dimens.TOPBAR_H)
    .padding({ left: 14, right: 12 })
    .backgroundColor(this.chromeSurface())
    .border({ width: { bottom: 1 }, color: Theme.border() })
  }

  @Builder
  sideRail() {
    Column({ space: 4 }) {
      ForEach(this.navItems(), (item: NavItem) => {
        Column({ space: 4 }) {
          this.iconChip(item.icon, this.tab === item.key ? Theme.accent() : Theme.sub(), 22)
          Text(item.label)
            .fontSize(10)
            .fontColor(this.tab === item.key ? Theme.accent() : Theme.sub())
            .maxLines(1)
        }
        .width(56)
        .padding({ top: 9, bottom: 9 })
        .borderRadius(10)
        .backgroundColor(this.tab === item.key ? Theme.accentSoft() : '#00000000')
        .animation({ duration: 180, curve: Curve.EaseOut })
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          this.selectTab(item.key)
        })
      }, (item: NavItem) => `${item.key}_${this.chromeToken}`)
      Blank()
      Text(AppVersion.display())
        .fontSize(10)
        .fontColor(Theme.faint())
        .padding({ bottom: 10 })
    }
    .width(Dimens.SIDEBAR_W)
    .height('100%')
    .padding({ top: 10 })
    .backgroundColor(this.chromeSurface())
    .border({ width: { right: 1 }, color: Theme.border() })
  }

  @Builder
  bottomBar() {
    Column() {
      Divider()
        .strokeWidth(0.5)
        .color(this.chromeBorder())
      Row() {
        ForEach(this.navItems(), (item: NavItem) => {
          Column({ space: 3 }) {
            this.iconChip(item.icon, this.tab === item.key ? Theme.accent() : Theme.faint(), 22)
            Text(item.label)
              .fontSize(10)
              .fontColor(this.tab === item.key ? Theme.accent() : Theme.faint())
              .maxLines(1)
          }
          .layoutWeight(1)
          .height(Dimens.TABBAR_H)
          .justifyContent(FlexAlign.Center)
          .animation({ duration: 180, curve: Curve.EaseOut })
          .onClick(() => {
            this.selectTab(item.key)
          })
        }, (item: NavItem) => `${item.key}_${this.chromeToken}`)
      }
      .width('100%')
      .backgroundColor(this.chromeSurface())
    }
    .width('100%')
  }

  @Builder
  accountSheet() {
    Column({ space: 2 }) {
      Row() {
        Text(I18n.t('userSwitchTip'))
          .fontSize(12)
          .fontColor(Theme.faint())
          .layoutWeight(1)
        Text(`${this.accountCount}`)
          .fontSize(11)
          .fontColor(Theme.sub())
          .padding({ left: 6, right: 6, top: 2, bottom: 2 })
          .backgroundColor(Theme.surfaceSoft())
          .borderRadius(6)
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 6, bottom: 8 })

      Scroll() {
        Column({ space: 2 }) {
          ForEach(this.accounts, (acc: AccountInfo) => {
            Row({ space: 10 }) {
              Image(acc.id === this.activeId ? $r('app.media.ic_check') : $r('app.media.ic_chevron_down'))
            .width(18)
            .height(18)
            .fillColor(acc.id === this.activeId ? Theme.accent() : '#00000000')
          Column({ space: 2 }) {
            Text(acc.name)
              .fontSize(14)
              .fontWeight(FontWeight.Medium)
              .fontColor(Theme.text())
              .maxLines(1)
            Text(`${I18n.t('workspace')} ${acc.workspaceId}`)
              .fontSize(11)
              .fontColor(Theme.faint())
              .maxLines(1)
          }
          .alignItems(HorizontalAlign.Start)
          .layoutWeight(1)
        }
        .width('100%')
        .padding({ left: 20, right: 20, top: 11, bottom: 11 })
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          this.switchAccount(acc.id)
        })
            }, (acc: AccountInfo) => String(acc.id))
        }
        .width('100%')
      }
      .width('100%')
      .constraintSize({ maxHeight: 320 })
      .scrollBar(BarState.Off)

      if (this.accounts.length === 0) {
        Text(I18n.t('noUsers'))
          .fontSize(13)
          .fontColor(Theme.faint())
          .width('100%')
          .padding({ left: 20, right: 20, top: 16, bottom: 16 })
      }

      Divider().color(Theme.border()).margin({ top: 6, bottom: 6 })

      Row({ space: 10 }) {
        this.iconChip($r('app.media.ic_settings'), Theme.sub(), 18)
        Text(I18n.t('manageUsers'))
          .fontSize(14)
          .fontColor(Theme.text())
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 11, bottom: 11 })
      .hoverEffect(HoverEffect.Highlight)
      .onClick(() => {
        this.showSwitcher = false
        this.selectTab('settings')
      })

      Row({ space: 10 }) {
        this.iconChip($r('app.media.ic_logout'), Theme.danger(), 18)
        Text(I18n.t('logout'))
          .fontSize(14)
          .fontColor(Theme.danger())
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 11, bottom: 11 })
      .hoverEffect(HoverEffect.Highlight)
      .onClick(() => {
        this.doLogout()
      })
    }
    .width('100%')
    .padding({ bottom: 20 })
    .backgroundColor(this.chromeSurface())
  }

  build() {
    Column() {
      if (this.wide) {
        this.topBar()
        Row() {
          this.sideRail()
          Column() {
            this.pageSlot()
          }
          .layoutWeight(1)
          .height('100%')
          .backgroundColor(this.chromeBg())
        }
        .layoutWeight(1)
        .width('100%')
      } else {
        Column() {
          this.pageSlot()
        }
        .layoutWeight(1)
        .width('100%')
        .backgroundColor(this.chromeBg())
        this.bottomBar()
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor(this.chromeBg())
    .onAreaChange((_old: Area, nv: Area) => {
      this.rootWidth = Number(nv.width)
      this.wide = this.rootWidth >= Dimens.SHELL_WIDE_BREAKPOINT
    })
    .focusable(true)
    .onKeyEvent((event: KeyEvent) => {
      if (event.type !== KeyType.Down) {
        return
      }
      const code = event.keyCode
      const withCtrl: boolean = event.getModifierKeyState !== undefined &&
        event.getModifierKeyState(['Ctrl'])
      if (withCtrl && code >= KB_1 && code <= KB_4) {
        const keys: string[] = ['home', 'stats', 'records', 'settings']
        this.selectTab(keys[code - KB_1])
        return
      }
      if ((withCtrl && code === KB_R) || code === KB_F5) {
        this.doSync()
      }
    })
    .bindSheet($$this.showSwitcher, this.accountSheet(), {
      height: SheetSize.MEDIUM,
      dragBar: true,
      showClose: false,
      backgroundColor: Theme.surface(),
    })
  }
}
