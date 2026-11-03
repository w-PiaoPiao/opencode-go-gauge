/**
 * 设置页 —— 账户管理 / 自动同步 / 外观 / 软件更新 / 关于 / 调试（仅 debug）。
 *
 * 视觉契约见 docs/design-spec.md §4.4：分组 GgCard + 行式布局（label + 说明 + 控件），
 * 宽屏（>=840vp）两列分组：左「账户 + 自动同步」，右「外观 + 更新 + 关于 + 调试」。
 * 所有颜色取自 Theme，所有文案取自 I18n；手机触控目标 >=44vp，宽屏 hoverEffect(Highlight)。
 *
 * 功能与旧版完全一致（loadAll/saveSettings/rename/delete/switch/runFullSync/prune/checkUpdate/
 * debug inject），仅替换表现层。账户/同步数据来自 Repo，外观偏好来自 AppPrefs。
 */
import router from '@ohos.router'
import { promptAction, window } from '@kit.ArkUI'
import { common } from '@kit.AbilityKit'
import { Repo } from '../../data/repository/DashboardRepository'
import { UpdateApi } from '../../data/remote/UpdateApi'
import { AppPrefs } from '../../common/store/AppPrefs'
import { I18n } from '../../common/i18n/I18n'
import { Theme, Dimens, FONT_SERIF } from '../theme/Theme'
import { AccountInfo, AppSettings } from '../../common/model/Models'
import { AppVersion } from '../../common/AppVersion'
import { BackgroundSync } from '../../common/BackgroundSync'
import { LaunchParams } from '../../common/dev/LaunchParams'
import { GgCard, PillRow, SegButtons, AccountChip, EmptyState, Option } from '../components/Cards'
import BuildProfile from 'BuildProfile'

/** 开源仓库地址（「关于」组点击行打开）。 */
const REPO_URL = 'https://github.com/w-PiaoPiao/opencode-go-gauge'
/**
 * 调试工具（注入/清除模拟数据）仅 debug 构建且非演示/截图模式显示：
 * release 混入演示数据会污染真实统计；`--ps demo=1` 截图时露出调试入口会触审核红线。
 */
const SHOW_DEBUG_TOOLS: boolean = BuildProfile.DEBUG && !LaunchParams.demo

/** 同步间隔秒数与胶囊文案下标一一对应，避免选项/索引/标签三处漂移。 */
const SYNC_INTERVALS: number[] = [60, 300, 900, 1800]
/** 同步范围（窗口天数），null = 所有。 */
const WINDOW_DAY_OPTIONS: Array<number | null> = [30, 60, 90, 180, null]

/** 设置页单行的垂直内边距（vp）—— 与 44vp 触控目标配合，保证手机可点。 */
const ROW_PAD_V = 10

@Component
export struct SettingsPage {
  @State private accounts: AccountInfo[] = []
  @State private activeId: number = 0
  @State private settings: AppSettings = { syncIntervalSec: 300, windowDays: 60, autoSync: true }
  @State private lang: string = 'zh'
  @State private dark: boolean = false
  @State private currency: string = 'USD'
  @State private renamingId: number = -1
  @State private renameText: string = ''
  @State private updateMsg: string = ''
  @State private syncMsg: string = ''
  @State private syncing: boolean = false
  @State private checkingUpdate: boolean = false
  /** 宽屏判定（>=840vp 走两列分组），由本页 onAreaChange 自行决定，不等壳层传参。 */
  @State private wide: boolean = false
  @Prop @Watch('onRefresh') refreshToken: number = 0
  /** 登出/删除最后一个账号后通知壳层切回欢迎页（plain 属性，父组件传入）。 */
  onLogout: () => void = () => {
  }
  /** 账号胶囊点击：打开壳层的账号切换 Sheet（宽屏/手机一致）。 */
  onOpenAccountSwitcher: () => void = () => {
  }
  /** 主题/语言切换后通知壳层立即重建（顶栏/底部 Tab 即时刷新，无需重启）。 */
  onAppearanceChanged: () => void = () => {
  }

  aboutToAppear(): void {
    this.loadAll()
  }

  onRefresh(): void {
    this.loadAll()
  }

  // ------------------------------------------------------------------
  // 数据加载 / 保存
  // ------------------------------------------------------------------

  private async loadAll(): Promise<void> {
    this.lang = AppPrefs.getLanguage()
    this.dark = AppPrefs.isDarkMode()
    this.currency = AppPrefs.getCurrency()
    try {
      const repo = Repo.get()
      this.accounts = await repo.accounts()
      this.activeId = await repo.activeAccountId()
      this.settings = await repo.settings()
    } catch (e) {
      // 冷启动时 DB 可能尚未就绪：保持默认值，下次刷新重试
    }
  }

  private async saveSettings(): Promise<void> {
    try {
      await Repo.get().saveSettings(this.settings)
    } catch (e) {
      // 持久化失败不阻塞 UI（设置值仍在内存态生效）
    }
  }

  private applySettings(next: AppSettings): void {
    this.settings = next
    this.saveSettings()
  }

  private saveAppearance(): void {
    AppPrefs.setLanguage(this.lang)
    AppPrefs.setDarkMode(this.dark)
    AppPrefs.setCurrency(this.currency)
    this.refreshWindowChrome()
    // 通知 AppRoot 重建壳层与当前页（顶栏/底部 Tab 文案、配色、页面内容即时刷新）
    this.onAppearanceChanged()
  }

  /**
   * 亮暗主题切换后同步刷新窗口背景与系统栏配色（设置页不 import EntryAbility，
   * 直接用窗口 API 取主窗口；预览器/无窗口环境下静默忽略）。
   */
  private async refreshWindowChrome(): Promise<void> {
    try {
      const host = this.getUIContext().getHostContext()
      if (host === undefined) {
        return
      }
      const win = await window.getLastWindow(host)
      const bg = Theme.bg()
      win.setWindowBackgroundColor(bg)
      win.setWindowSystemBarProperties({
        statusBarColor: bg,
        isStatusBarLightIcon: this.dark,
        statusBarContentColor: Theme.text(),
        navigationBarColor: bg,
        isNavigationBarLightIcon: this.dark,
        navigationBarContentColor: Theme.text(),
      }).catch(() => {
        // 部分设备/形态不支持系统栏着色时忽略
      })
    } catch (e) {
      // 预览器/窗口未就绪时忽略
    }
  }

  // ------------------------------------------------------------------
  // 同步 / 清理 / 更新检查
  // ------------------------------------------------------------------

  /**
   * 手动全量同步。
   *
   * 增量同步被 maxPages=5 硬性截断（5 页 × 50 条 = 250 条），超过 250 条的历史
   * 只能靠 full 模式补全 —— 设置页是应用内唯一入口。
   */
  private async runFullSync(): Promise<void> {
    if (this.syncing) {
      return
    }
    this.syncing = true
    try {
      this.syncMsg = await Repo.get().syncAll('full')
    } catch (e) {
      this.syncMsg = I18n.t('sync_fail')
    } finally {
      this.syncing = false
    }
  }

  /**
   * 「按同步范围清理」：先预演（数量/边界），再二次确认后真删。
   * 同步只按范围取数、不自动裁剪本地存量，这是唯一的删除入口（不可恢复）。
   */
  private async runPrune(): Promise<void> {
    try {
      const preview = await Repo.get().prunePreview()
      if (preview === null) {
        promptAction.showToast({ message: I18n.t('prune_none') })
        return
      }
      if (preview[2] === 0) {
        promptAction.showToast({ message: I18n.t('prune_empty') })
        return
      }
      const res = await promptAction.showDialog({
        title: I18n.t('pruneTitle'),
        message: I18n.t('prune_confirm')
          .replace('%1', String(preview[0]))
          .replace('%2', preview[1])
          .replace('%3', String(preview[2])),
        buttons: [
          { text: I18n.t('cancel'), color: Theme.sub() },
          { text: I18n.t('prune_now'), color: Theme.danger() },
        ],
      })
      if (res.index === 1) {
        const deleted = await Repo.get().pruneExpired()
        promptAction.showToast({ message: I18n.t('prune_done').replace('%1', String(deleted)) })
        await this.loadAll()
      }
    } catch (e) {
      this.syncMsg = I18n.t('sync_fail')
    }
  }

  private async checkUpdate(): Promise<void> {
    if (this.checkingUpdate) {
      return
    }
    this.checkingUpdate = true
    this.updateMsg = I18n.t('checkingUpdate')
    try {
      const info = await UpdateApi.checkUpdate(AppVersion.versionName())
      this.updateMsg = info.hasUpdate ? I18n.t('update_has') : I18n.t('update_none')
    } catch (e) {
      this.updateMsg = I18n.t('update_fail')
    } finally {
      this.checkingUpdate = false
    }
  }

  // ------------------------------------------------------------------
  // 账户操作
  // ------------------------------------------------------------------

  private addAccount(): void {
    router.pushUrl({ url: 'pages/LoginPage', params: { mode: 'add' } })
  }

  private relogin(): void {
    router.pushUrl({ url: 'pages/LoginPage', params: { mode: 'relogin' } })
  }

  private async switchAccount(accountId: number): Promise<void> {
    await Repo.get().switchAccount(accountId)
    promptAction.showToast({ message: I18n.t('switchedAccount') })
    await this.loadAll()
  }

  private startRename(a: AccountInfo): void {
    this.renamingId = a.id
    this.renameText = a.name
  }

  private async submitRename(a: AccountInfo): Promise<void> {
    const name = this.renameText.trim()
    if (name.length === 0) {
      this.renamingId = -1
      return
    }
    await Repo.get().renameAccount(a.id, name)
    this.renamingId = -1
    promptAction.showToast({ message: I18n.t('userRenamed') })
    await this.loadAll()
  }

  private async confirmDelete(a: AccountInfo): Promise<void> {
    const res = await promptAction.showDialog({
      title: I18n.t('deleteTitle'),
      message: I18n.t('deleteUserConfirm').replace('%1', a.name),
      buttons: [
        { text: I18n.t('cancel'), color: Theme.sub() },
        { text: I18n.t('confirm'), color: Theme.danger() },
      ],
    })
    if (res.index !== 1) {
      return
    }
    const remaining = await Repo.get().deleteAccount(a.id)
    promptAction.showToast({ message: I18n.t('userDeleted') })
    await this.loadAll()
    // 删光账号后已无可用数据：通知壳层回到欢迎页（等价退出登录）
    if (remaining <= 0) {
      this.onLogout()
    }
  }

  private async confirmLogout(): Promise<void> {
    const name = this.activeName()
    const res = await promptAction.showDialog({
      title: I18n.t('logout'),
      message: I18n.t('logoutUserConfirm').replace('%1', name.length > 0 ? name : I18n.t('account')),
      buttons: [
        { text: I18n.t('cancel'), color: Theme.sub() },
        { text: I18n.t('ok'), color: Theme.danger() },
      ],
    })
    if (res.index !== 1) {
      return
    }
    await Repo.get().logout()
    this.onLogout()
  }

  // ------------------------------------------------------------------
  // 关于 / 外部链接
  // ------------------------------------------------------------------

  private async openRepo(): Promise<void> {
    try {
      const host = this.getUIContext().getHostContext()
      if (host === undefined) {
        throw new Error('no host context')
      }
      const ctx = host as common.UIAbilityContext
      await ctx.openLink(REPO_URL)
    } catch (e) {
      promptAction.showToast({ message: I18n.t('openLinkFailed') })
    }
  }

  // ------------------------------------------------------------------
  // 调试数据（仅 debug 构建）
  // ------------------------------------------------------------------

  private async injectSample(): Promise<void> {
    try {
      const n = await Repo.get().injectSampleData()
      promptAction.showToast({ message: I18n.t('sampleInjected').replace('%1', String(n)) })
    } catch (e) {
      promptAction.showToast({ message: I18n.t('sync_fail') })
    }
  }

  private async clearSample(): Promise<void> {
    try {
      const n = await Repo.get().clearSampleData()
      Repo.get().setDemoQuota(null)
      promptAction.showToast({ message: I18n.t('sampleCleared').replace('%1', String(n)) })
    } catch (e) {
      promptAction.showToast({ message: I18n.t('sync_fail') })
    }
  }

  // ------------------------------------------------------------------
  // 小工具
  // ------------------------------------------------------------------

  private activeName(): string {
    for (const a of this.accounts) {
      if (a.id === this.activeId) {
        return a.name
      }
    }
    return ''
  }

  /** 手机 44vp / 宽屏 32vp 触控目标。 */
  private touchH(): number {
    return this.wide ? Dimens.PC_TOUCH_MIN : Dimens.TOUCH_MIN
  }

  private intervalOptions(): Option[] {
    return [
      { value: '60', label: I18n.t('min1') },
      { value: '300', label: I18n.t('min5') },
      { value: '900', label: I18n.t('min15') },
      { value: '1800', label: I18n.t('min30') },
    ]
  }

  private intervalValue(): string {
    const i = SYNC_INTERVALS.indexOf(this.settings.syncIntervalSec)
    return String(SYNC_INTERVALS[i >= 0 ? i : 1])
  }

  private rangeOptions(): Option[] {
    return [
      { value: '30', label: I18n.t('d30short') },
      { value: '60', label: I18n.t('d60') },
      { value: '90', label: I18n.t('d90') },
      { value: '180', label: I18n.t('d180') },
      { value: 'all', label: I18n.t('daysAll') },
    ]
  }

  private rangeValue(): string {
    return this.settings.windowDays === null ? 'all' : String(this.settings.windowDays)
  }

  private themeOptions(): Option[] {
    return [
      { value: 'light', label: I18n.t('light') },
      { value: 'dark', label: I18n.t('dark') },
    ]
  }

  private languageOptions(): Option[] {
    return [
      { value: 'zh', label: '中文' },
      { value: 'en', label: 'English' },
    ]
  }

  private currencyOptions(): Option[] {
    return [
      { value: 'USD', label: 'USD' },
      { value: 'CNY', label: 'CNY' },
    ]
  }

  private featureList(): string[] {
    return [
      I18n.t('feat1'), I18n.t('feat2'), I18n.t('feat3'), I18n.t('feat4'), I18n.t('feat5'),
    ]
  }

  // ------------------------------------------------------------------
  // 视图
  // ------------------------------------------------------------------

  build() {
    Scroll() {
      Column({ space: this.wide ? Dimens.GAP_WIDE : Dimens.GAP }) {
        this.pageHeader()
        if (this.wide) {
          Row({ space: Dimens.GAP_WIDE }) {
            Column({ space: Dimens.GAP_WIDE }) {
              this.accountCard()
              this.syncCard()
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Start)

            Column({ space: Dimens.GAP_WIDE }) {
              this.appearanceCard()
              this.updateCard()
              this.aboutCard()
              if (SHOW_DEBUG_TOOLS) {
                this.debugCard()
              }
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Start)
          }
          .width('100%')
          .alignItems(VerticalAlign.Top)
        } else {
          this.accountCard()
          this.syncCard()
          this.appearanceCard()
          this.updateCard()
          this.aboutCard()
          if (SHOW_DEBUG_TOOLS) {
            this.debugCard()
          }
        }
        this.pageFooter()
      }
      .width('100%')
      .padding({
        left: this.wide ? Dimens.PAGE_H_WIDE : Dimens.PAGE_H,
        right: this.wide ? Dimens.PAGE_H_WIDE : Dimens.PAGE_H,
        top: this.wide ? Dimens.PAGE_V_WIDE : Dimens.PAGE_V,
        bottom: this.wide ? Dimens.PAGE_V_WIDE : Dimens.PAGE_V,
      })
      .alignItems(HorizontalAlign.Start)
    }
    .width('100%')
    .height('100%')
    .backgroundColor(Theme.bg())
    .scrollBar(BarState.Off)
    .edgeEffect(EdgeEffect.Spring)
    .onAreaChange((_oldValue: Area, newValue: Area) => {
      const w = newValue.width as number
      this.wide = w >= Dimens.WIDE_BREAKPOINT
    })
  }

  /** 页头：标题（衬线）+ 账号胶囊 + 刷新（design-spec §3.2 每页自带页头）。 */
  @Builder
  pageHeader() {
    Row({ space: 10 }) {
      Text(I18n.t('settingsTitle'))
        .fontSize(this.wide ? Dimens.TITLE_WIDE : Dimens.TITLE_PHONE)
        .fontFamily(FONT_SERIF)
        .fontWeight(FontWeight.Bold)
        .fontColor(Theme.text())
        .maxLines(1)
      Blank()
      if (!this.wide) {
        AccountChip({
          name: this.activeName(),
          count: this.accounts.length,
          onTap: () => {
            this.onOpenAccountSwitcher()
          },
        })
        Row() {
          Image($r('app.media.ic_refresh'))
            .width(18)
            .height(18)
            .fillColor(Theme.sub())
            .objectFit(ImageFit.Contain)
        }
        .width(Dimens.TOUCH_MIN)
        .height(Dimens.TOUCH_MIN)
        .justifyContent(FlexAlign.Center)
        .borderRadius(Dimens.TILE_RADIUS)
        .backgroundColor(Theme.surfaceSoft())
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          this.loadAll()
        })
      }
    }
    .width('100%')
    .alignItems(VerticalAlign.Center)
  }

  @Builder
  pageFooter() {
    Text(I18n.t('pageFoot').replace('{version}', AppVersion.versionName()))
      .fontSize(11)
      .fontColor(Theme.faint())
      .width('100%')
      .textAlign(TextAlign.Center)
      .padding({ top: 4, bottom: 8 })
  }

  // ---------------- 1) 账户管理 ----------------

  @Builder
  accountCard() {
    GgCard({
      title: I18n.t('settings_account'),
      hint: `${I18n.t('manageUsers')} · ${this.accounts.length}`,
    }) {
      this.accountContent()
    }
  }

  @Builder
  accountContent() {
      Column() {
        if (this.accounts.length === 0) {
          EmptyState({ text: I18n.t('noUsers') })
        }
        ForEach(this.accounts, (a: AccountInfo, index: number) => {
          this.accountRow(a, index === this.accounts.length - 1)
        }, (a: AccountInfo) => `acc_${a.id}`)

        Text(I18n.t('addUser'))
          .fontSize(13)
          .fontWeight(FontWeight.Medium)
          .fontColor(Theme.accent())
          .width('100%')
          .height(this.touchH())
          .textAlign(TextAlign.Center)
          .backgroundColor(Theme.accentSoft())
          .borderRadius(Dimens.TILE_RADIUS)
          .hoverEffect(HoverEffect.Highlight)
          .margin({ top: 10 })
          .onClick(() => {
            this.addAccount()
          })

        Divider()
          .color(Theme.divider())
          .margin({ top: 12, bottom: 12 })

        Row({ space: 8 }) {
          Image($r('app.media.ic_logout'))
            .width(16)
            .height(16)
            .fillColor(Theme.danger())
            .objectFit(ImageFit.Contain)
          Text(I18n.t('logout'))
            .fontSize(13)
            .fontWeight(FontWeight.Medium)
            .fontColor(Theme.danger())
        }
        .width('100%')
        .height(this.touchH())
        .justifyContent(FlexAlign.Center)
        .backgroundColor(Theme.dangerSoft())
        .borderRadius(Dimens.TILE_RADIUS)
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          this.confirmLogout()
        })
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

  @Builder
  accountRow(a: AccountInfo, last: boolean) {
    Column() {
      if (this.renamingId === a.id) {
        Row({ space: 8 }) {
          TextInput({ text: this.renameText, placeholder: a.name })
            .layoutWeight(1)
            .height(this.touchH())
            .fontSize(13)
            .fontColor(Theme.text())
            .placeholderColor(Theme.faint())
            .backgroundColor(Theme.surfaceSoft())
            .borderRadius(Dimens.TILE_RADIUS)
            .onChange((v: string) => {
              this.renameText = v
            })
          Text(I18n.t('ok'))
            .fontSize(12)
            .fontColor(Theme.onAccent())
            .height(this.touchH())
            .padding({ left: 12, right: 12 })
            .textAlign(TextAlign.Center)
            .backgroundColor(Theme.accent())
            .borderRadius(Dimens.TILE_RADIUS)
            .hoverEffect(HoverEffect.Highlight)
            .onClick(() => {
              this.submitRename(a)
            })
          Text(I18n.t('cancel'))
            .fontSize(12)
            .fontColor(Theme.sub())
            .height(this.touchH())
            .padding({ left: 12, right: 12 })
            .textAlign(TextAlign.Center)
            .backgroundColor(Theme.surfaceSoft())
            .borderRadius(Dimens.TILE_RADIUS)
            .hoverEffect(HoverEffect.Highlight)
            .onClick(() => {
              this.renamingId = -1
            })
        }
        .width('100%')
        .padding({ top: 10, bottom: 10 })
      } else {
        Row({ space: 8 }) {
          Column({ space: 3 }) {
            Row({ space: 6 }) {
              Text(a.name)
                .fontSize(13)
                .fontWeight(FontWeight.Medium)
                .fontColor(Theme.text())
                .maxLines(1)
                .textOverflow({ overflow: TextOverflow.Ellipsis })
              if (a.id === this.activeId) {
                Text(I18n.t('currentUserBadge'))
                  .fontSize(10)
                  .fontColor(Theme.onAccent())
                  .padding({ left: 6, right: 6, top: 2, bottom: 2 })
                  .backgroundColor(Theme.accent())
                  .borderRadius(8)
              }
            }
            .width('100%')

            Text(a.hasToken ? `${I18n.t('workspace')} ${a.workspaceId}` : I18n.t('notLoggedIn'))
              .fontSize(11)
              .fontColor(a.hasToken ? Theme.faint() : Theme.danger())
              .maxLines(1)
              .textOverflow({ overflow: TextOverflow.Ellipsis })
          }
          .alignItems(HorizontalAlign.Start)
          .layoutWeight(1)
        }
        .width('100%')
        .padding({ top: 10, bottom: 4 })

        Row({ space: 6 }) {
          if (a.id !== this.activeId) {
            this.accountAction(a, 'switch')
          }
          if (!a.hasToken || a.id === this.activeId) {
            this.accountAction(a, 'relogin')
          }
          this.accountAction(a, 'rename')
          this.accountAction(a, 'delete')
        }
        .width('100%')
        .padding({ bottom: 10 })
      }

      if (!last) {
        Divider()
          .color(Theme.divider())
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  /** 账号操作按钮：kind = switch | relogin | rename | delete（函数型参数会破坏 @Builder 解析，故用字符串分发）。 */
  @Builder
  accountAction(a: AccountInfo, kind: string) {
    Text(this.actionLabel(kind))
      .fontSize(12)
      .fontColor(kind === 'delete' ? Theme.danger() : Theme.accent())
      .height(this.touchH())
      .padding({ left: 12, right: 12 })
      .textAlign(TextAlign.Center)
      .backgroundColor(kind === 'delete' ? Theme.dangerSoft() : Theme.surfaceSoft())
      .borderRadius(Dimens.TILE_RADIUS)
      .hoverEffect(HoverEffect.Highlight)
      .onClick(() => {
        this.onAccountAction(a, kind)
      })
  }

  private actionLabel(kind: string): string {
    if (kind === 'switch') {
      return I18n.t('settings_switch')
    }
    if (kind === 'relogin') {
      return I18n.t('relogin')
    }
    if (kind === 'rename') {
      return I18n.t('settings_rename')
    }
    return I18n.t('settings_delete')
  }

  private onAccountAction(a: AccountInfo, kind: string): void {
    if (kind === 'switch') {
      this.switchAccount(a.id)
    } else if (kind === 'relogin') {
      this.relogin()
    } else if (kind === 'rename') {
      this.startRename(a)
    } else {
      this.confirmDelete(a)
    }
  }

  // ---------------- 2) 自动同步 ----------------

  @Builder
  syncCard() {
    GgCard({ title: I18n.t('setAutoSync') }) {
      this.syncContent()
    }
  }

  @Builder
  syncContent() {
      Column() {
        Row({ space: 10 }) {
          this.flexLabel(I18n.t('autoSync'), I18n.t('autoSyncDesc'))
          Toggle({ type: ToggleType.Switch, isOn: this.settings.autoSync })
            .selectedColor(Theme.accent())
            .onChange((isOn: boolean) => {
              const next: AppSettings = {
                syncIntervalSec: this.settings.syncIntervalSec,
                windowDays: this.settings.windowDays,
                autoSync: isOn,
              }
              this.applySettings(next)
              // 立即生效：启动/取消后台周期任务（Index 前台定时器每次触发也会重读设置）
              BackgroundSync.apply(isOn)
            })
        }
        .width('100%')
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })

        this.rowDivider()

        Column({ space: 8 }) {
          this.stackLabel(I18n.t('sync_interval'), I18n.t('syncIntervalDesc'))
          PillRow({
            options: this.intervalOptions(),
            selected: this.intervalValue(),
            onSelect: (v: string) => {
              const next: AppSettings = {
                syncIntervalSec: Number(v),
                windowDays: this.settings.windowDays,
                autoSync: this.settings.autoSync,
              }
              this.applySettings(next)
            },
          })
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })

        this.rowDivider()

        Column({ space: 8 }) {
          this.stackLabel(I18n.t('sync_range'), I18n.t('syncRangeDesc'))
          PillRow({
            options: this.rangeOptions(),
            selected: this.rangeValue(),
            onSelect: (v: string) => {
              const idx = this.rangeOptions().findIndex((o: Option) => o.value === v)
              const wd = idx >= 0 ? WINDOW_DAY_OPTIONS[idx] : null
              const next: AppSettings = {
                syncIntervalSec: this.settings.syncIntervalSec,
                windowDays: wd,
                autoSync: this.settings.autoSync,
              }
              this.applySettings(next)
            },
          })
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })

        this.rowDivider()

        Row({ space: 10 }) {
          this.flexLabel(I18n.t('sync_full'), I18n.t('sync_full_desc'))
          Text(this.syncing ? I18n.t('syncing') : I18n.t('sync'))
            .fontSize(12)
            .fontColor(Theme.onAccent())
            .height(this.touchH())
            .padding({ left: 14, right: 14 })
            .textAlign(TextAlign.Center)
            .backgroundColor(this.syncing ? Theme.surfaceStrong() : Theme.accent())
            .borderRadius(Dimens.TILE_RADIUS)
            .enabled(!this.syncing)
            .hoverEffect(HoverEffect.Highlight)
            .onClick(() => {
              this.runFullSync()
            })
        }
        .width('100%')
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })

        if (this.syncMsg.length > 0) {
          Text(this.syncMsg)
            .fontSize(11)
            .fontColor(Theme.sub())
            .width('100%')
            .padding({ bottom: 8 })
        }

        this.rowDivider()

        Row({ space: 10 }) {
          this.flexLabel(I18n.t('prune_now'), I18n.t('prune_now_desc'))
          Text(I18n.t('prune_now'))
            .fontSize(12)
            .fontColor(Theme.danger())
            .height(this.touchH())
            .padding({ left: 14, right: 14 })
            .textAlign(TextAlign.Center)
            .backgroundColor(Theme.dangerSoft())
            .borderRadius(Dimens.TILE_RADIUS)
            .hoverEffect(HoverEffect.Highlight)
            .onClick(() => {
              this.runPrune()
            })
        }
        .width('100%')
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

  // ---------------- 3) 外观 ----------------

  @Builder
  appearanceCard() {
    GgCard({ title: I18n.t('setAppearance') }) {
      this.appearanceContent()
    }
  }

  @Builder
  appearanceContent() {
      Column() {
        Row({ space: 10 }) {
          this.flexLabel(I18n.t('theme'), I18n.t('themeDesc'))
          SegButtons({
            options: this.themeOptions(),
            selected: this.dark ? 'dark' : 'light',
            onSelect: (v: string) => {
              this.dark = v === 'dark'
              this.saveAppearance()
            },
          })
        }
        .width('100%')
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })

        this.rowDivider()

        Row({ space: 10 }) {
          this.flexLabel(I18n.t('language'), I18n.t('languageDesc'))
          SegButtons({
            options: this.languageOptions(),
            selected: this.lang,
            onSelect: (v: string) => {
              this.lang = v === 'en' ? 'en' : 'zh'
              this.saveAppearance()
            },
          })
        }
        .width('100%')
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })

        this.rowDivider()

        Row({ space: 10 }) {
          this.flexLabel(I18n.t('currency'), I18n.t('currencyDesc'))
          SegButtons({
            options: this.currencyOptions(),
            selected: this.currency,
            onSelect: (v: string) => {
              this.currency = v === 'CNY' ? 'CNY' : 'USD'
              this.saveAppearance()
            },
          })
        }
        .width('100%')
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

  // ---------------- 4) 软件更新 ----------------

  @Builder
  updateCard() {
    GgCard({ title: I18n.t('setUpdate') }) {
      this.updateContent()
    }
  }

  @Builder
  updateContent() {
      Column() {
        Row({ space: 10 }) {
          this.flexLabel(I18n.t('currentVersion'), 'HarmonyOS NEXT · ArkTS/ArkUI')
          Text(AppVersion.versionName())
            .fontSize(13)
            .fontWeight(FontWeight.Medium)
            .fontColor(Theme.text())
            .maxLines(1)
        }
        .width('100%')
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })

        this.rowDivider()

        Row({ space: 10 }) {
          this.flexLabel(I18n.t('checkUpdate'), I18n.t('checkUpdateDesc'))
          Text(this.checkingUpdate ? I18n.t('checkingUpdate') : I18n.t('checkUpdate'))
            .fontSize(12)
            .fontColor(Theme.accent())
            .height(this.touchH())
            .padding({ left: 14, right: 14 })
            .textAlign(TextAlign.Center)
            .backgroundColor(Theme.surfaceSoft())
            .borderRadius(Dimens.TILE_RADIUS)
            .enabled(!this.checkingUpdate)
            .hoverEffect(HoverEffect.Highlight)
            .onClick(() => {
              this.checkUpdate()
            })
        }
        .width('100%')
        .padding({ top: ROW_PAD_V, bottom: ROW_PAD_V })

        if (this.updateMsg.length > 0) {
          Text(this.updateMsg)
            .fontSize(11)
            .fontColor(Theme.sub())
            .width('100%')
            .padding({ bottom: 8 })
        }
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

  // ---------------- 5) 关于 ----------------

  @Builder
  aboutCard() {
    GgCard({ title: I18n.t('aboutTitle') }) {
      this.aboutContent()
    }
  }

  @Builder
  aboutContent() {
      Column({ space: 8 }) {
        Row({ space: 8 }) {
          Text('GoGauge')
            .fontSize(17)
            .fontFamily(FONT_SERIF)
            .fontWeight(FontWeight.Bold)
            .fontColor(Theme.text())
          Text(`${I18n.t('version')} ${AppVersion.versionName()}`)
            .fontSize(11)
            .fontColor(Theme.faint())
          Blank()
        }
        .width('100%')

        Text(`GoGauge ${I18n.t('introText')}`)
          .fontSize(12)
          .fontColor(Theme.sub())
          .lineHeight(19)
          .width('100%')

        Divider()
          .color(Theme.divider())

        Text(I18n.t('aboutFeatures'))
          .fontSize(12)
          .fontWeight(FontWeight.Medium)
          .fontColor(Theme.text())

        Column({ space: 5 }) {
          ForEach(this.featureList(), (feature: string) => {
            Row({ space: 6 }) {
              Text('·')
                .fontSize(12)
                .fontColor(Theme.accent())
              Text(feature)
                .fontSize(11)
                .fontColor(Theme.sub())
                .layoutWeight(1)
            }
            .width('100%')
            .alignItems(VerticalAlign.Top)
          }, (feature: string) => feature)
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)

        Divider()
          .color(Theme.divider())

        Row({ space: 8 }) {
          Image($r('app.media.ic_github'))
            .width(15)
            .height(15)
            .fillColor(Theme.sub())
            .objectFit(ImageFit.Contain)
          Text(I18n.t('openSource'))
            .fontSize(13)
            .fontColor(Theme.text())
          Blank()
          Text(REPO_URL)
            .fontSize(11)
            .fontColor(Theme.accent())
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
        .width('100%')
        .height(this.touchH())
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          this.openRepo()
        })

        Row({ space: 8 }) {
          Text(I18n.t('privacyEntry'))
            .fontSize(13)
            .fontColor(Theme.text())
          Blank()
          Text('›')
            .fontSize(16)
            .fontColor(Theme.faint())
        }
        .width('100%')
        .height(this.touchH())
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          router.pushUrl({ url: 'pages/PrivacyPage' })
        })

        Row({ space: 8 }) {
          Text(I18n.t('thanksText'))
            .fontSize(13)
            .fontColor(Theme.text())
          Blank()
          Text('OpenCode')
            .fontSize(12)
            .fontColor(Theme.sub())
        }
        .width('100%')
        .height(this.touchH())

        Divider()
          .color(Theme.divider())

        Text(I18n.t('privacy'))
          .fontSize(11)
          .fontColor(Theme.faint())
          .width('100%')
          .lineHeight(17)
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

  // ---------------- 6) 调试（仅 debug 构建） ----------------

  @Builder
  debugCard() {
    GgCard({ title: I18n.t('debugTools') }) {
      this.debugContent()
    }
  }

  @Builder
  debugContent() {
      Column({ space: 8 }) {
        Text(I18n.t('demoModeHint'))
          .fontSize(11)
          .fontColor(Theme.faint())
          .width('100%')

        Text(I18n.t('injectSample'))
          .fontSize(13)
          .fontColor(Theme.accent())
          .width('100%')
          .height(this.touchH())
          .textAlign(TextAlign.Center)
          .backgroundColor(Theme.accentSoft())
          .borderRadius(Dimens.TILE_RADIUS)
          .hoverEffect(HoverEffect.Highlight)
          .onClick(() => {
            this.injectSample()
          })

        Text(I18n.t('clearSample'))
          .fontSize(13)
          .fontColor(Theme.danger())
          .width('100%')
          .height(this.touchH())
          .textAlign(TextAlign.Center)
          .backgroundColor(Theme.dangerSoft())
          .borderRadius(Dimens.TILE_RADIUS)
          .hoverEffect(HoverEffect.Highlight)
          .onClick(() => {
            this.clearSample()
          })
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

  // ---------------- 行内基础块 ----------------

  /** Row 内使用：label + 说明左对齐并占满剩余宽度。 */
  @Builder
  flexLabel(label: string, desc: string) {
    Column({ space: 2 }) {
      Text(label)
        .fontSize(13)
        .fontColor(Theme.text())
        .maxLines(1)
      if (desc.length > 0) {
        Text(desc)
          .fontSize(11)
          .fontColor(Theme.faint())
          .maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
      }
    }
    .alignItems(HorizontalAlign.Start)
    .layoutWeight(1)
  }

  /** Column 内使用（控件换行到下方时）：label + 说明，不占权重。 */
  @Builder
  stackLabel(label: string, desc: string) {
    Column({ space: 2 }) {
      Text(label)
        .fontSize(13)
        .fontColor(Theme.text())
        .maxLines(1)
      if (desc.length > 0) {
        Text(desc)
          .fontSize(11)
          .fontColor(Theme.faint())
          .maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
      }
    }
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  rowDivider() {
    Divider()
      .color(Theme.divider())
      .strokeWidth(1)
  }
}
