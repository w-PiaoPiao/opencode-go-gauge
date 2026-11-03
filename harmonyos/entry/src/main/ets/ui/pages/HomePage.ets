/**
 * 首页 —— 配额窗口 + 6 KPI + 今日 24h 趋势。
 *
 * 布局对标：
 *  - 手机（compact，宽 <840vp）→ 安卓 HomeScreen：页头（标题+账号胶囊+刷新）→ 周期胶囊 →
 *    三张配额卡 → 「用量概览」编辑式 2 列数据格 → 「今日趋势」；
 *  - 平板/PC（expanded，宽 >=840vp）→ 桌面首页：页头右侧周期胶囊、配额三块一行三列、
 *    概览 6 格多列、趋势整行。
 *
 * 鸿蒙适配：下拉刷新（Refresh 原生回弹）、数据到达后配额进度条弹性生长、
 * 卡片分段落入、宽窄屏实时重排、悬停高亮。
 */
import { Repo } from '../../data/repository/DashboardRepository'
import { I18n } from '../../common/i18n/I18n'
import { AppPrefs } from '../../common/store/AppPrefs'
import { DashboardData, QuotaResult, QuotaWindow } from '../../common/model/Models'
import { Fmt } from '../../common/util/Fmt'
import {
  AccountChip, EditorialCell, EditorialGrid, EmptyState, ErrorCard, GgCard, Hint, KpiCard,
  Loader, Option, PillRow, QuotaCard, QuotaSkeleton, SegButtons,
} from '../components/Cards'
import { BarChart24h } from '../components/Charts'
import { Theme, Dimens } from '../theme/Theme'

@Component
export struct HomePage {
  @Prop @Watch('onRefresh') refreshToken: number = 0
  /** 壳层注入：点账号胶囊打开切换 Sheet。 */
  onOpenAccountSwitcher: () => void = () => {
  }
  @State private data: DashboardData | null = null
  @State private loading: boolean = true
  @State private error: string = ''
  @State private range: string = 'today'
  @State private currency: string = 'USD'
  @State private accountName: string = ''
  @State private accountCount: number = 0
  @State private isRefreshing: boolean = false
  @State private wide: boolean = false
  @State private rootWidth: number = 0
  @State private ttMode: string = 'plain'
  @State private entered: number = 0
  /** 并发加载序号：快速切换 range 时只采纳最后一次请求的结果。 */
  private loadSeq: number = 0

  aboutToAppear(): void {
    this.load()
    animateTo({ duration: 260, curve: Curve.EaseOut }, () => {
      this.entered = 1
    })
  }

  onRefresh(): void {
    this.load()
  }

  private async load(): Promise<void> {
    this.loadSeq += 1
    const seq: number = this.loadSeq
    this.currency = AppPrefs.getCurrency()
    try {
      const repo = Repo.get()
      const acct = await repo.account()
      this.accountName = acct !== null ? acct.name : ''
      const list = await repo.accounts()
      let logged = 0
      for (const a of list) {
        if (a.hasToken) {
          logged++
        }
      }
      this.accountCount = logged
      const dash = await repo.loadDashboard(this.range)
      if (seq !== this.loadSeq) {
        return
      }
      this.data = dash
      this.error = ''
    } catch (e) {
      if (seq !== this.loadSeq) {
        return
      }
      this.error = (e as Error).message
      this.data = null
    }
    if (seq !== this.loadSeq) {
      return
    }
    this.loading = false
  }

  private async doPullRefresh(): Promise<void> {
    this.isRefreshing = true
    try {
      await Repo.get().syncAll('incremental')
    } catch (e) {
      // 同步失败保留本地数据，仅结束刷新态
    }
    await this.load()
    this.isRefreshing = false
  }

  private rangeOptions(): Option[] {
    return [
      { value: 'today', label: I18n.t('today') },
      { value: '7d', label: I18n.t('d7') },
      { value: '30d', label: I18n.t('d30') },
      { value: 'month', label: I18n.t('month') },
      { value: 'all', label: I18n.t('all') },
    ]
  }

  private changeRange(v: string): void {
    if (v === this.range) {
      return
    }
    this.range = v
    this.loading = true
    this.load()
  }

  private quotaWindows(): QuotaWindow[] {
    if (this.data === null || this.data.quota === null) {
      return []
    }
    return this.data.quota.windows
  }

  private quotaLabel(label: string): string {
    if (label.indexOf('Weekly') >= 0) {
      return I18n.t('quotaWeekly')
    }
    if (label.indexOf('Monthly') >= 0) {
      return I18n.t('quotaMonthly')
    }
    return I18n.t('quotaRolling')
  }

  private quotaColor(label: string): string[] {
    if (label.indexOf('Weekly') >= 0) {
      return [Theme.cyan(), Theme.green()]
    }
    if (label.indexOf('Monthly') >= 0) {
      return [Theme.amber(), Theme.danger()]
    }
    return [Theme.accent(), Theme.amber()]
  }

  private resetText(w: QuotaWindow): string {
    if (w.resetAt.length > 0) {
      return `${I18n.t('resetsIn')} ${Fmt.dur(w.resetInSec, I18n.t('d_unit'), I18n.t('h_unit'), I18n.t('m_unit'), I18n.t('soon'))}`
    }
    return w.used <= 0 ? I18n.t('windowNotStarted') : I18n.t('resetUnknown')
  }

  private money(v: number): string {
    return Fmt.money(v, this.currency, this.data !== null ? this.data.usdCny : 7.2)
  }

  private overviewCells(): EditorialCell[] {
    const d = this.data
    if (d === null) {
      return []
    }
    const t = d.totals
    const avg = t.requestCount > 0 ? t.totalCostUsd / t.requestCount : 0
    const cells: EditorialCell[] = [
      {
        label: I18n.t('hit_rate'),
        value: `${Math.round(t.hitRate)}%`,
        sub: `${I18n.t('hit')} ${Fmt.tokens(t.cacheHitTokens)} · ${I18n.t('miss')} ${Fmt.tokens(t.uncachedInputTokens)}`,
        accent: Theme.green(),
      },
      {
        label: I18n.t('hitAmount'),
        value: Fmt.tokens(t.cacheHitTokens),
        sub: `${I18n.t('pctOfInput')} ${Math.round(t.hitRate)}%`,
        accent: Theme.cyan(),
      },
      {
        label: I18n.t('total_tokens'),
        value: Fmt.tokens(t.totalTokens),
        sub: I18n.t('inclCache'),
        accent: Theme.blue(),
      },
      {
        label: I18n.t('totalRequests'),
        value: Fmt.int(t.requestCount),
        sub: I18n.t('currentRange'),
        accent: Theme.slate(),
      },
      {
        label: I18n.t('totalCost'),
        value: this.money(t.totalCostUsd),
        sub: `${I18n.t('avgPer')} ${this.money(avg)}${I18n.t('perReq')}`,
        accent: Theme.amber(),
      },
      {
        label: I18n.t('sessions'),
        value: Fmt.int(t.sessionCount),
        sub: I18n.t('dedup'),
        accent: Theme.violet(),
      },
    ]
    return cells
  }

  private gridColumns(): number {
    if (this.rootWidth < 600) {
      return 2
    }
    if (this.rootWidth < 1000) {
      return 3
    }
    return 6
  }

  @Builder
  refreshButton() {
    // 注意 ArkUI 的 width 是 border-box：Image 再设置 padding 会把内容区压成 0 宽，
    // 图标不可见（商店截图里表现为一个空米色圆底）。用 Row 容器承担尺寸与背景。
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
    .borderRadius(99)
    .backgroundColor(Theme.surfaceSoft())
    .margin({ left: 8 })
    .hoverEffect(HoverEffect.Highlight)
    .onClick(() => {
      this.doPullRefresh()
    })
  }

  @Builder
  pageHeader() {
    Row() {
      Text(I18n.t('homeTitle'))
        .fontSize(this.wide ? Dimens.TITLE_WIDE : Dimens.TITLE_PHONE)
        .fontFamily('GgSerif')
        .fontColor(Theme.text())
        .maxLines(1)
      Blank()
      if (this.wide) {
        PillRow({ options: this.rangeOptions(), selected: this.range, onSelect: (v: string) => this.changeRange(v) })
      } else {
        AccountChip({
          name: this.accountName,
          count: this.accountCount,
          onTap: () => {
            this.onOpenAccountSwitcher()
          },
        })
        this.refreshButton()
      }
    }
    .width('100%')
  }

  @Builder
  quotaSection() {
    if (this.loading) {
      QuotaSkeleton()
    } else if (this.data === null && this.error.length > 0) {
      ErrorCard({
        title: I18n.t('quotaFail'),
        detail: this.error,
        retryText: I18n.t('retry'),
        onRetry: () => {
          this.load()
        },
      })
    } else if (this.data !== null && this.data.quota !== null && !this.data.quota.success) {
      ErrorCard({
        title: I18n.t('quotaFail'),
        detail: this.data.quota.error !== null ? this.data.quota.error : '?',
        retryText: I18n.t('retry'),
        onRetry: () => {
          this.doPullRefresh()
        },
      })
    } else if (this.quotaWindows().length === 0) {
      GgCard({ title: I18n.t('quota_windows') }) {
        this.quotaEmptyContent()
      }
    } else {
      if (this.wide) {
        Row({ space: Dimens.GAP_WIDE }) {
          ForEach(this.quotaWindows(), (w: QuotaWindow) => {
            Column() {
              QuotaCard({
                label: this.quotaLabel(w.label),
                usedPercent: w.used,
                remainingText: `${I18n.t('remaining')} ${Math.round(w.remaining)}%`,
                resetText: this.resetText(w),
                accent: this.quotaColor(w.label)[0],
                accentEnd: this.quotaColor(w.label)[1],
                usedLabel: `${I18n.t('used')} ${Math.round(w.used)}%`,
              })
            }
            .layoutWeight(1)
          }, (w: QuotaWindow) => w.label)
        }
        .width('100%')
        .alignItems(VerticalAlign.Top)
      } else {
        Column({ space: Dimens.GAP }) {
          ForEach(this.quotaWindows(), (w: QuotaWindow) => {
            QuotaCard({
              label: this.quotaLabel(w.label),
              usedPercent: w.used,
              remainingText: `${I18n.t('remaining')} ${Math.round(w.remaining)}%`,
              resetText: this.resetText(w),
              accent: this.quotaColor(w.label)[0],
              accentEnd: this.quotaColor(w.label)[1],
              usedLabel: `${I18n.t('used')} ${Math.round(w.used)}%`,
            })
          }, (w: QuotaWindow) => w.label)
        }
        .width('100%')
      }
    }
  }

  @Builder
  quotaEmptyContent() {
    EmptyState({ text: I18n.t('quota_empty') })
  }

  @Builder
  overviewContent() {
    EditorialGrid({ cells: this.overviewCells(), columns: this.gridColumns() })
  }

  @Builder
  overviewSection() {
    if (this.data !== null) {
      GgCard({
        title: I18n.t('overviewTitle'),
        hint: I18n.t('followRange'),
      }) {
        this.overviewContent()
      }
    }
  }

  @Builder
  trendContent() {
    BarChart24h({
      hours: this.data !== null ? this.data.todayTrend : [],
      totalMode: this.ttMode === 'total',
      inputLabel: I18n.t('input'),
      outputLabel: I18n.t('output'),
      chartHeight: this.wide ? 180 : 132,
    })
  }

  @Builder
  trendSection() {
    if (this.data !== null) {
      GgCard({}) {
        Column({ space: 8 }) {
          Row({ space: 8 }) {
            Text(I18n.t('todayTrend'))
              .fontSize(15)
              .fontFamily('GgSerif')
              .fontColor(Theme.text())
              .maxLines(1)
            Text(I18n.t('hours24'))
              .fontSize(11)
              .fontColor(Theme.faint())
              .maxLines(1)
            Blank()
            this.trendTrailing()
          }
          .width('100%')
          this.trendContent()
        }
        .width('100%')
      }
    }
  }

  @Builder
  trendTrailing() {
    SegButtons({
      options: [
        { value: 'plain', label: I18n.t('ttPlain') },
        { value: 'total', label: I18n.t('ttTotal') },
      ],
      selected: this.ttMode,
      onSelect: (v: string) => {
        this.ttMode = v
      },
    })
  }

  build() {
    Refresh({ refreshing: $$this.isRefreshing }) {
      Scroll() {
        Column({ space: this.wide ? Dimens.GAP_WIDE : Dimens.GAP }) {
          this.pageHeader()
          if (!this.wide) {
            Column() {
              PillRow({ options: this.rangeOptions(), selected: this.range, onSelect: (v: string) => this.changeRange(v) })
            }
            .width('100%')
          }
          this.quotaSection()
          this.overviewSection()
          this.trendSection()
        }
        .width('100%')
        .padding({
          left: this.wide ? Dimens.PAGE_H_WIDE : Dimens.PAGE_H,
          right: this.wide ? Dimens.PAGE_H_WIDE : Dimens.PAGE_H,
          top: this.wide ? Dimens.PAGE_V_WIDE : Dimens.PAGE_V,
          bottom: 20,
        })
        .opacity(this.entered)
        .translate({ y: (1 - this.entered) * 6 })
      }
      .width('100%')
      .height('100%')
      .scrollBar(BarState.Off)
      .edgeEffect(EdgeEffect.Spring)
    }
    .onRefreshing(() => {
      this.doPullRefresh()
    })
    .width('100%')
    .height('100%')
    .backgroundColor(Theme.bg())
    .onAreaChange((_old: Area, nv: Area) => {
      this.rootWidth = Number(nv.width)
      this.wide = this.rootWidth >= Dimens.WIDE_BREAKPOINT
    })
  }
}
