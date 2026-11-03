/**
 * 统计页 —— 4 KPI + Token 构成 + 模型用量 + 用量趋势 + 日历热力图 + 模型用量趋势。
 *
 * 手机（<840vp）对标 Android StatsScreen：页头 + 周期胶囊 + 单列卡片流 + 下拉刷新；
 * 宽屏（>=840vp）对标桌面 #page-stats：页头标题左/周期胶囊右，KPI 4 列，
 * [模型用量 | 用量趋势]、[日历热力图 | 模型用量趋势] 两栏（列宽 1:1.6）。
 * 颜色/圆角/间距一律走 Theme/Dimens，文案一律走 I18n。
 */
import { Repo } from '../../data/repository/DashboardRepository'
import {
  AccountInfo, DailyStat, DashboardData, ModelStat, ModelTrendData, ModelTrendSeries, Totals,
} from '../../common/model/Models'
import { Fmt } from '../../common/util/Fmt'
import { AppPrefs } from '../../common/store/AppPrefs'
import { I18n } from '../../common/i18n/I18n'
import { Theme, Dimens, FONT_SERIF } from '../theme/Theme'
import {
  GgCard, KpiCard, EditorialCell, EditorialGrid, PillRow, SegButtons, AccountChip, ModelIcon,
  Loader, EmptyState, ErrorCard, Option,
} from '../components/Cards'
import {
  DonutChart, TrendLineChart, ModelTrendChart, CalendarHeatmap,
  ChartSegment, TrendSeries, HeatDay,
} from '../components/Charts'

/** 热力图窗口：近 180 天（design-spec 5 heatmapRange「近 6 个月」）。 */
const HEATMAP_DAYS: number = 180
/** 模型趋势窗口：30 天（与桌面 chartModelTrend 一致，独立于页签 range）。 */
const MODEL_TREND_DAYS: number = 30

@Component
export struct StatsPage {
  @State private data: DashboardData | null = null
  @State private heatDays: DailyStat[] = []
  @State private modelTrend: ModelTrendData | null = null
  @State private loading: boolean = true
  @State private loadError: string = ''
  @State private range: string = '7d'
  @State private modelDim: string = 'input'
  @State private heatDim: string = 'tokens'
  @State private accountName: string = ''
  @State private accountCount: number = 0
  @State private currency: string = 'USD'
  @State private wide: boolean = false
  @State private syncing: boolean = false
  @State private refreshing: boolean = false
  @State private appear: number = 0
  /** 并发加载序号：range 快速切换时只采纳最后一次请求的结果。 */
  private loadSeq: number = 0
  @Prop @Watch('onRefresh') refreshToken: number = 0
  /** 壳层注入：点击页头账号胶囊时打开账号切换（未注入时无操作）。 */
  onOpenAccountSwitcher: () => void = () => {
  }

  aboutToAppear(): void {
    this.load(true)
  }

  onRefresh(): void {
    this.load(false)
  }

  // ------------------------------------------------------------------
  // 数据加载
  // ------------------------------------------------------------------

  private async load(initial: boolean): Promise<void> {
    this.loadSeq += 1
    const seq: number = this.loadSeq
    if (initial) {
      this.loading = true
    }
    this.loadError = ''
    this.currency = AppPrefs.getCurrency()
    try {
      const repo = Repo.get()
      const acct: AccountInfo | null = await repo.account()
      const list: AccountInfo[] = await repo.accounts()
      const dash: DashboardData = await repo.loadDashboard(this.range)
      const heat: DailyStat[] = await repo.loadHeatmapDays(HEATMAP_DAYS)
      const modelTrend: ModelTrendData = await repo.loadModelTrend(MODEL_TREND_DAYS)
      if (seq !== this.loadSeq) {
        return
      }
      this.accountName = acct !== null ? acct.name : ''
      let logged: number = 0
      for (const a of list) {
        if (a.hasToken) {
          logged += 1
        }
      }
      this.accountCount = logged
      this.data = dash
      this.heatDays = heat
      this.modelTrend = modelTrend
    } catch (e) {
      if (seq !== this.loadSeq) {
        return
      }
      const msg: string = (e as Error).message !== undefined ? (e as Error).message : ''
      this.loadError = msg.length > 0 ? msg : I18n.t('sync_fail')
      if (this.data === null) {
        this.heatDays = []
        this.modelTrend = null
      }
    }
    if (seq !== this.loadSeq) {
      return
    }
    this.loading = false
    this.playEnter()
  }

  /** 页头刷新按钮 / 下拉刷新：增量同步完成后重载数据。 */
  private async doSync(): Promise<void> {
    if (this.syncing) {
      return
    }
    this.syncing = true
    this.refreshing = true
    try {
      await Repo.get().syncAll('incremental')
    } catch (e) {
      // 同步失败保留现有数据；错误由 load() 的查询结果兜底
    }
    await this.load(false)
    this.syncing = false
    this.refreshing = false
  }

  private playEnter(): void {
    if (this.appear >= 1) {
      return
    }
    animateTo({ duration: 220, curve: Curve.EaseOut }, () => {
      this.appear = 1
    })
  }

  private changeRange(value: string): void {
    if (this.range === value) {
      return
    }
    this.range = value
    this.load(false)
  }

  // ------------------------------------------------------------------
  // 通用取值
  // ------------------------------------------------------------------

  private usdCny(): number {
    return this.data !== null ? this.data.usdCny : 7.2
  }

  private totals(): Totals | null {
    return this.data !== null ? this.data.totals : null
  }

  private money(usd: number): string {
    return Fmt.money(usd, this.currency, this.usdCny())
  }

  private shortDate(iso: string): string {
    const parts: string[] = iso.split('-')
    if (parts.length === 3) {
      return `${Number(parts[1])}/${Number(parts[2])}`
    }
    return iso.length >= 5 ? iso.slice(iso.length - 5) : iso
  }

  /** 维度文案（输入/输出/成本）。 */
  private dimLabel(): string {
    if (this.modelDim === 'output') {
      return I18n.t('output')
    }
    if (this.modelDim === 'cost') {
      return I18n.t('cost')
    }
    return I18n.t('input')
  }

  private rangeOptions(): Option[] {
    const out: Option[] = []
    out.push({ value: 'today', label: I18n.t('today') })
    out.push({ value: '7d', label: I18n.t('d7') })
    out.push({ value: '30d', label: I18n.t('d30') })
    out.push({ value: 'month', label: I18n.t('month') })
    out.push({ value: 'all', label: I18n.t('all') })
    return out
  }

  // ------------------------------------------------------------------
  // Token 构成
  // ------------------------------------------------------------------

  /** 环图 4 段合计（未命中输入 + 输出 + 推理 + 缓存读），中心值与之同口径。 */
  private compositionTotal(): number {
    let sum: number = 0
    for (const seg of this.compositionSegments()) {
      sum += seg.value
    }
    return sum
  }

  private compositionSegments(): ChartSegment[] {
    const t = this.totals()
    const out: ChartSegment[] = []
    if (t === null) {
      return out
    }
    out.push({ name: I18n.t('input'), value: t.uncachedInputTokens, color: Theme.chartInput() })
    out.push({ name: I18n.t('output'), value: t.totalOutputTokens, color: Theme.chartOutput() })
    out.push({ name: I18n.t('reasoning'), value: t.totalReasoningTokens, color: Theme.chartReasoning() })
    out.push({ name: I18n.t('colCacheRead'), value: t.cacheHitTokens, color: Theme.chartCache() })
    // 缓存写也计入总 TOKEN（与 KPI「总 TOKEN」口径一致），否则圆心合计比 KPI 少一块
    if (t.cacheWriteTokens > 0) {
      out.push({ name: I18n.t('cacheWrite'), value: t.cacheWriteTokens, color: Theme.chartExtra() })
    }
    return out
  }

  private compositionCells(): EditorialCell[] {
    const t = this.totals()
    const out: EditorialCell[] = []
    if (t === null) {
      return out
    }
    // 推理占比与桌面 renderDetail6 同口径：未缓存输入 + 输出 + 推理
    const base: number = t.uncachedInputTokens + t.totalOutputTokens + t.totalReasoningTokens
    const reasonPct: string = base > 0 ? `${(t.totalReasoningTokens / base * 100).toFixed(1)}%` : '0%'
    out.push({
      label: I18n.t('input'), value: Fmt.tokens(t.uncachedInputTokens),
      sub: `${I18n.t('inclCache')} ${Fmt.tokens(t.totalInputTokens)}`, accent: Theme.chartInput(),
    })
    out.push({
      label: I18n.t('output'), value: Fmt.tokens(t.totalOutputTokens),
      sub: I18n.t('output'), accent: Theme.chartOutput(),
    })
    out.push({
      label: I18n.t('colReasoning'), value: Fmt.tokens(t.totalReasoningTokens),
      sub: reasonPct, accent: Theme.chartReasoning(),
    })
    out.push({
      label: I18n.t('colCacheRead'), value: Fmt.tokens(t.cacheHitTokens),
      sub: `${I18n.t('hit_rate')} ${t.hitRate.toFixed(1)}%`, accent: Theme.chartCache(),
    })
    out.push({
      label: I18n.t('cacheWrite'), value: Fmt.tokens(t.cacheWriteTokens),
      sub: I18n.t('newCacheWrites'), accent: Theme.chartCache(),
    })
    out.push({
      label: I18n.t('sessions'), value: Fmt.int(t.sessionCount),
      sub: I18n.t('dedup'), accent: Theme.slate(),
    })
    return out
  }

  // ------------------------------------------------------------------
  // 模型用量
  // ------------------------------------------------------------------

  private modelValue(m: ModelStat): number {
    if (this.modelDim === 'output') {
      return m.totalOutputTokens
    }
    if (this.modelDim === 'cost') {
      return m.totalCostUsd
    }
    return m.totalInputTokens
  }

  private sortedModels(): ModelStat[] {
    const out: ModelStat[] = []
    if (this.data === null) {
      return out
    }
    const list: ModelStat[] = this.data.models.slice()
    list.sort((a: ModelStat, b: ModelStat): number => this.modelValue(b) - this.modelValue(a))
    return list
  }

  /** 环形图调色板：与安卓 MODEL_COLORS / 桌面 MODEL_PALETTE 同序（6 槽）。 */
  private modelPalette(): string[] {
    return [
      Theme.chartInput(), Theme.chartOutput(), Theme.chartReasoning(),
      Theme.chartCache(), Theme.chartCost(), Theme.chartExtra(),
    ]
  }

  private modelSegments(): ChartSegment[] {
    const out: ChartSegment[] = []
    const list: ModelStat[] = this.sortedModels()
    const palette: string[] = this.modelPalette()
    const n: number = Math.min(6, list.length)
    for (let i = 0; i < n; i++) {
      const m: ModelStat = list[i]
      const v: number = this.modelValue(m)
      if (v > 0) {
        out.push({ name: m.model, value: v, color: palette[i % palette.length] })
      }
    }
    return out
  }

  private modelTotal(): number {
    let sum: number = 0
    for (const seg of this.modelSegments()) {
      sum += seg.value
    }
    return sum
  }

  private modelCenterValue(): string {
    const v: number = this.modelTotal()
    return this.modelDim === 'cost' ? this.money(v) : Fmt.tokens(v)
  }

  /** 排行主数值：跟随当前维度（成本显示金额，其余显示 Token 简写）。 */
  private rankText(m: ModelStat): string {
    if (this.modelDim === 'cost') {
      return this.money(m.totalCostUsd)
    }
    return Fmt.tokens(this.modelDim === 'output' ? m.totalOutputTokens : m.totalInputTokens)
  }

  // ------------------------------------------------------------------
  // 用量趋势
  // ------------------------------------------------------------------

  /** 首个有量日（桌面 chartTrend firstOn）：前置全零段裁掉。 */
  private trendLead(): number {
    if (this.data === null) {
      return -1
    }
    const trend: DailyStat[] = this.data.trend
    for (let i = 0; i < trend.length; i++) {
      const d: DailyStat = trend[i]
      const tokens: number = d.totalInputTokens + d.totalOutputTokens + d.totalReasoningTokens
      if (d.requestCount > 0 || d.totalCostUsd > 0 || tokens > 0) {
        return i
      }
    }
    return -1
  }

  private trimmedTrend(): DailyStat[] {
    if (this.data === null) {
      return []
    }
    const lead: number = this.trendLead()
    return lead > 0 ? this.data.trend.slice(lead) : this.data.trend
  }

  /** 序列按自身峰值对齐（三条线量纲差异过大，与安卓双轴归一化同思路）。 */
  private norm(values: number[]): number[] {
    let max: number = 0
    for (const v of values) {
      if (v > max) {
        max = v
      }
    }
    const out: number[] = []
    for (const v of values) {
      out.push(max > 0 ? v / max : 0)
    }
    return out
  }

  private trendSeries(): TrendSeries[] {
    const trend: DailyStat[] = this.trimmedTrend()
    const costs: number[] = []
    const reqs: number[] = []
    const toks: number[] = []
    for (const d of trend) {
      costs.push(d.totalCostUsd)
      reqs.push(d.requestCount)
      toks.push(d.totalInputTokens + d.totalOutputTokens + d.totalReasoningTokens)
    }
    const out: TrendSeries[] = []
    out.push({ name: I18n.t('totalCost'), color: Theme.chartInput(), values: this.norm(costs) })
    out.push({ name: I18n.t('totalRequests'), color: Theme.chartOutput(), values: this.norm(reqs) })
    out.push({ name: I18n.t('total_tokens'), color: Theme.chartReasoning(), values: this.norm(toks) })
    return out
  }

  private trendLabels(): string[] {
    const out: string[] = []
    for (const d of this.trimmedTrend()) {
      out.push(this.shortDate(d.date))
    }
    return out
  }

  private trendHint(): string {
    const lead: number = this.trendLead()
    return lead > 0 ? I18n.t('trendHintGap').replace('%1', String(lead)) : I18n.t('trendHint')
  }

  // ------------------------------------------------------------------
  // 日历热力图
  // ------------------------------------------------------------------

  private heatMetricValue(d: DailyStat): number {
    if (this.heatDim === 'cost') {
      return d.totalCostUsd
    }
    if (this.heatDim === 'requests') {
      return d.requestCount
    }
    return d.totalInputTokens + d.totalOutputTokens + d.totalReasoningTokens
  }

  private heatDaysData(): HeatDay[] {
    const out: HeatDay[] = []
    for (const d of this.heatDays) {
      out.push({
        date: d.date,
        value: this.heatMetricValue(d),
        requests: d.requestCount,
        cost: d.totalCostUsd,
      })
    }
    return out
  }

  private hasHeatData(): boolean {
    for (const d of this.heatDays) {
      if (d.requestCount > 0) {
        return true
      }
    }
    return false
  }

  private formatHeatValue(v: number): string {
    if (this.heatDim === 'cost') {
      return this.money(v)
    }
    if (this.heatDim === 'requests') {
      return Fmt.int(v)
    }
    return Fmt.tokens(v)
  }

  private heatPeakLabel(): string {
    let bestV: number = -1
    let bestDate: string = ''
    for (const d of this.heatDays) {
      const v: number = this.heatMetricValue(d)
      if (v > bestV) {
        bestV = v
        bestDate = d.date
      }
    }
    const peakLabel: string = I18n.t('hmPeak')
    return bestDate.length > 5 ? `${peakLabel} · ${bestDate.slice(bestDate.length - 5)}` : peakLabel
  }

  private heatPeakValue(): string {
    let bestV: number = 0
    for (const d of this.heatDays) {
      const v: number = this.heatMetricValue(d)
      if (v > bestV) {
        bestV = v
      }
    }
    return this.formatHeatValue(bestV)
  }

  /** 当前连续：从最新一天回溯，最新一天无请求即中断（与桌面同口径）。 */
  private heatCurrentStreak(): number {
    let cur: number = 0
    let i: number = this.heatDays.length - 1
    while (i >= 0 && this.heatDays[i].requestCount > 0) {
      cur += 1
      i -= 1
    }
    return cur
  }

  private heatLongestStreak(): number {
    let longest: number = 0
    let run: number = 0
    for (const d of this.heatDays) {
      if (d.requestCount > 0) {
        run += 1
        if (run > longest) {
          longest = run
        }
      } else {
        run = 0
      }
    }
    return longest
  }

  private streakText(n: number): string {
    return `${n}${I18n.t('d_unit')}`
  }

  // ------------------------------------------------------------------
  // 模型用量趋势
  // ------------------------------------------------------------------

  private hasModelTrend(): boolean {
    return this.modelTrend !== null && this.modelTrend.days.length > 0 && this.modelTrend.series.length > 0
  }

  private modelTrendLead(): number {
    const mt: ModelTrendData | null = this.modelTrend
    if (mt === null) {
      return -1
    }
    for (let i = 0; i < mt.days.length; i++) {
      for (const s of mt.series) {
        const input: number = i < s.input.length ? s.input[i] : 0
        const output: number = i < s.output.length ? s.output[i] : 0
        const cost: number = i < s.cost.length ? s.cost[i] : 0
        if (input + output > 0 || cost > 0) {
          return i
        }
      }
    }
    return -1
  }

  private modelTrendLabels(): string[] {
    const mt: ModelTrendData | null = this.modelTrend
    const out: string[] = []
    if (mt === null) {
      return out
    }
    const lead: number = this.modelTrendLead()
    const days: string[] = lead > 0 ? mt.days.slice(lead) : mt.days
    for (const d of days) {
      out.push(this.shortDate(d))
    }
    return out
  }

  private modelTrendSeries(): TrendSeries[] {
    const out: TrendSeries[] = []
    const mt: ModelTrendData | null = this.modelTrend
    if (mt === null) {
      return out
    }
    const lead: number = this.modelTrendLead()
    const palette: string[] = this.modelPalette()
    const n: number = Math.min(6, mt.series.length)
    for (let i = 0; i < n; i++) {
      const s: ModelTrendSeries = mt.series[i]
      const raw: number[] = this.modelDim === 'output' ? s.output : (this.modelDim === 'cost' ? s.cost : s.input)
      const values: number[] = lead > 0 ? raw.slice(lead) : raw
      out.push({ name: s.model, color: palette[i % palette.length], values })
    }
    return out
  }

  private modelTrendHint(): string {
    const lead: number = this.modelTrendLead()
    return lead > 0 ? I18n.t('trendHintGap').replace('%1', String(lead)) : I18n.t('trendHint')
  }

  // ------------------------------------------------------------------
  // 页头 / 卡片
  // ------------------------------------------------------------------

  @Builder
  pageHeader() {
    if (this.wide) {
      Row({ space: 12 }) {
        Text(I18n.t('statsTitle'))
          .fontSize(Dimens.TITLE_WIDE)
          .fontFamily(FONT_SERIF)
          .fontWeight(FontWeight.Bold)
          .fontColor(Theme.text())
          .maxLines(1)
        Blank()
        Row() {
          this.rangePills()
        }
        .width(360)
      }
      .width('100%')
      .height(Dimens.TOUCH_MIN)
    } else {
      Row({ space: 8 }) {
        Text(I18n.t('statsTitle'))
          .fontSize(Dimens.TITLE_PHONE)
          .fontFamily(FONT_SERIF)
          .fontWeight(FontWeight.Bold)
          .fontColor(Theme.text())
          .maxLines(1)
        Blank()
        AccountChip({
          name: this.accountName,
          count: this.accountCount,
          onTap: () => {
            this.onOpenAccountSwitcher()
          },
        })
        this.refreshButton()
      }
      .width('100%')
      .height(Dimens.TOUCH_MIN)
    }
  }

  @Builder
  rangePills() {
    PillRow({
      options: this.rangeOptions(),
      selected: this.range,
      onSelect: (value: string) => {
        this.changeRange(value)
      },
    })
  }

  @Builder
  refreshButton() {
    Stack() {
      Circle({ width: 34, height: 34 }).fill(Theme.surfaceSoft())
      if (this.syncing) {
        LoadingProgress().width(17).height(17).color(Theme.accent())
      } else {
        Text('↻')
          .fontSize(17)
          .fontColor(Theme.sub())
      }
    }
    .width(Dimens.TOUCH_MIN)
    .height(Dimens.TOUCH_MIN)
    .hoverEffect(HoverEffect.Highlight)
    .onClick(() => {
      this.doSync()
    })
  }

  @Builder
  kpiSection() {
    if (this.data !== null) {
      if (this.wide) {
        Row({ space: Dimens.GAP_WIDE }) {
          Column() {
            this.kpiCost()
          }.layoutWeight(1)
          Column() {
            this.kpiRequests()
          }.layoutWeight(1)
          Column() {
            this.kpiTokens()
          }.layoutWeight(1)
          Column() {
            this.kpiHit()
          }.layoutWeight(1)
        }
        .width('100%')
        .alignItems(VerticalAlign.Top)
      } else {
        Column({ space: Dimens.GAP }) {
          Row({ space: Dimens.GAP }) {
            Column() {
              this.kpiCost()
            }.layoutWeight(1)
            Column() {
              this.kpiRequests()
            }.layoutWeight(1)
          }
          .width('100%')
          .alignItems(VerticalAlign.Top)
          Row({ space: Dimens.GAP }) {
            Column() {
              this.kpiTokens()
            }.layoutWeight(1)
            Column() {
              this.kpiHit()
            }.layoutWeight(1)
          }
          .width('100%')
          .alignItems(VerticalAlign.Top)
        }
        .width('100%')
      }
    }
  }

  private avgPerReq(): string {
    const t: Totals | null = this.totals()
    if (t === null || t.requestCount <= 0) {
      return this.money(0)
    }
    return this.money(t.totalCostUsd / t.requestCount)
  }

  @Builder
  kpiCost() {
    KpiCard({
      label: I18n.t('totalCost'),
      value: this.data !== null ? this.money(this.data.totals.totalCostUsd) : '—',
      sub: `${I18n.t('avgPer')} ${this.avgPerReq()}${I18n.t('perReq')}`,
      accent: Theme.amber(),
    })
  }

  @Builder
  kpiRequests() {
    KpiCard({
      label: I18n.t('totalRequests'),
      value: this.data !== null ? Fmt.int(this.data.totals.requestCount) : '—',
      sub: I18n.t('currentRange'),
      accent: Theme.blue(),
    })
  }

  @Builder
  kpiTokens() {
    KpiCard({
      label: I18n.t('total_tokens'),
      value: this.data !== null ? Fmt.tokens(this.data.totals.totalTokens) : '—',
      sub: this.data !== null
        ? `${I18n.t('input')} ${Fmt.tokens(this.data.totals.totalInputTokens)} · ${I18n.t('output')} ${Fmt.tokens(this.data.totals.totalOutputTokens)}`
        : '',
      accent: Theme.violet(),
    })
  }

  @Builder
  kpiHit() {
    KpiCard({
      label: I18n.t('hit_rate'),
      value: this.data !== null ? `${this.data.totals.hitRate.toFixed(1)}%` : '—',
      sub: this.data !== null
        ? `${I18n.t('hit')} ${Fmt.tokens(this.data.totals.cacheHitTokens)} / ${I18n.t('miss')} ${Fmt.tokens(this.data.totals.uncachedInputTokens)}`
        : '',
      accent: Theme.green(),
    })
  }

  @Builder
  tokenCompositionCard() {
    GgCard({ title: I18n.t('token_composition') }) {
      this.tokenCompositionBody()
    }
  }

  @Builder
  tokenCompositionBody() {
    if (this.data !== null) {
      if (this.wide) {
        Row({ space: 16 }) {
          DonutChart({
            segments: this.compositionSegments(),
            centerValue: Fmt.tokens(this.compositionTotal()),
            centerLabel: I18n.t('total_tokens'),
          })
          Column() {
            EditorialGrid({ cells: this.compositionCells(), columns: 3 })
          }
          .layoutWeight(1)
        }
        .width('100%')
        .alignItems(VerticalAlign.Center)
      } else {
        Column({ space: 10 }) {
          Row() {
            Blank()
            DonutChart({
              segments: this.compositionSegments(),
              centerValue: Fmt.tokens(this.compositionTotal()),
              centerLabel: I18n.t('total_tokens'),
            })
            Blank()
          }
          .width('100%')
          EditorialGrid({ cells: this.compositionCells(), columns: 2 })
        }
        .width('100%')
      }
    }
  }

  @Builder
  modelDimSeg() {
    SegButtons({
      options: this.modelDimOptions(),
      selected: this.modelDim,
      onSelect: (value: string) => {
        this.modelDim = value
      },
    })
  }

  private modelDimOptions(): Option[] {
    const out: Option[] = []
    out.push({ value: 'input', label: I18n.t('input') })
    out.push({ value: 'output', label: I18n.t('output') })
    out.push({ value: 'cost', label: I18n.t('cost') })
    return out
  }

  @Builder
  modelUsageCard() {
    GgCard({}) {
      Column({ space: 8 }) {
        Row({ space: 8 }) {
          Text(I18n.t('modelUsage'))
            .fontSize(15)
            .fontFamily('GgSerif')
            .fontColor(Theme.text())
            .maxLines(1)
          Blank()
          this.modelDimSeg()
        }
        .width('100%')
        this.modelUsageBody()
      }
      .width('100%')
    }
  }

  @Builder
  modelUsageBody() {
    Column({ space: 8 }) {
      Row() {
        Blank()
        DonutChart({
          segments: this.modelSegments(),
          centerValue: this.modelCenterValue(),
          centerLabel: this.dimLabel(),
        })
        Blank()
      }
      .width('100%')
      this.modelRank()
    }
    .width('100%')
  }

  @Builder
  modelRank() {
    if (this.sortedModels().length === 0) {
      EmptyState({ text: I18n.t('noData') })
    } else {
      Column({ space: 6 }) {
        ForEach(this.sortedModels().slice(0, 3), (m: ModelStat, i: number) => {
          Row({ space: 6 }) {
            Text(`#${i + 1}`)
              .fontSize(11)
              .fontWeight(FontWeight.Bold)
              .fontColor(Theme.faint())
              .width(18)
            ModelIcon({ model: m.model })
            Column({ space: 2 }) {
              Text(m.model)
                .fontSize(13)
                .fontWeight(FontWeight.Medium)
                .fontColor(Theme.text())
                .maxLines(1)
                .textOverflow({ overflow: TextOverflow.Ellipsis })
              Text(`${Fmt.int(m.requestCount)} ${I18n.t('req_unit')} · ${I18n.t('hit_rate')} ${m.hitRate.toFixed(1)}%`)
                .fontSize(11)
                .fontColor(Theme.sub())
                .maxLines(1)
                .textOverflow({ overflow: TextOverflow.Ellipsis })
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
            Text(this.rankText(m))
              .fontSize(12)
              .fontWeight(FontWeight.Medium)
              .fontColor(Theme.text())
              .maxLines(1)
              .textAlign(TextAlign.End)
              .constraintSize({ minWidth: 56 })
          }
          .width('100%')
          .padding({ left: 8, right: 8, top: 6, bottom: 6 })
          .backgroundColor(Theme.surfaceSoft())
          .borderRadius(Dimens.TILE_RADIUS)
        }, (m: ModelStat) => `rank_${m.model}`)
      }
      .width('100%')
    }
  }

  @Builder
  trendCard() {
    GgCard({ title: I18n.t('usageTrend'), hint: this.trendHint() }) {
      this.trendBody()
    }
  }

  @Builder
  trendBody() {
    TrendLineChart({ series: this.trendSeries(), labels: this.trendLabels() })
  }

  @Builder
  heatDimSeg() {
    SegButtons({
      options: this.heatDimOptions(),
      selected: this.heatDim,
      onSelect: (value: string) => {
        this.heatDim = value
      },
    })
  }

  private heatDimOptions(): Option[] {
    const out: Option[] = []
    out.push({ value: 'tokens', label: I18n.t('total_tokens') })
    out.push({ value: 'requests', label: I18n.t('totalRequests') })
    out.push({ value: 'cost', label: I18n.t('cost') })
    return out
  }

  @Builder
  heatmapCard() {
    GgCard({}) {
      Column({ space: 8 }) {
        Row({ space: 8 }) {
          Text(I18n.t('heatmapTitle'))
            .fontSize(15)
            .fontFamily('GgSerif')
            .fontColor(Theme.text())
            .maxLines(1)
          Blank()
          this.heatDimSeg()
        }
        .width('100%')
        this.heatmapBody()
      }
      .width('100%')
    }
  }

  @Builder
  heatmapBody() {
    if (!this.hasHeatData()) {
      EmptyState({ text: I18n.t('heatmapNoData') })
    } else {
      Column({ space: 10 }) {
        CalendarHeatmap({ days: this.heatDaysData(), ramp: Theme.heatRamp() })
        Row({ space: 8 }) {
          this.heatStat(this.heatPeakLabel(), this.heatPeakValue())
          this.heatStat(I18n.t('hmCurStreak'), this.streakText(this.heatCurrentStreak()))
          this.heatStat(I18n.t('hmMaxStreak'), this.streakText(this.heatLongestStreak()))
        }
        .width('100%')
      }
      .width('100%')
    }
  }

  @Builder
  heatStat(label: string, value: string) {
    Column({ space: 2 }) {
      Text(label)
        .fontSize(11)
        .fontColor(Theme.faint())
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
      Text(value)
        .fontSize(15)
        .fontWeight(FontWeight.Bold)
        .fontColor(Theme.text())
        .maxLines(1)
    }
    .layoutWeight(1)
    .alignItems(HorizontalAlign.Start)
    .padding({ left: 10, right: 8, top: 8, bottom: 8 })
    .backgroundColor(Theme.surfaceSoft())
    .borderRadius(Dimens.TILE_RADIUS)
  }

  @Builder
  modelTrendCard() {
    GgCard({ title: I18n.t('mtTitle'), hint: this.modelTrendHint() }) {
      this.modelTrendBody()
    }
  }

  @Builder
  modelTrendBody() {
    ModelTrendChart({ series: this.modelTrendSeries(), labels: this.modelTrendLabels() })
  }

  // ------------------------------------------------------------------
  // 页面骨架
  // ------------------------------------------------------------------

  build() {
    Column() {
      Refresh({ refreshing: $$this.refreshing }) {
        Scroll() {
          Column({ space: this.wide ? 12 : 10 }) {
            this.pageHeader()
            if (this.loadError.length > 0 && this.data === null) {
              ErrorCard({
                title: I18n.t('sync_fail'),
                detail: this.loadError,
                retryText: I18n.t('retry'),
                onRetry: () => {
                  this.load(true)
                },
              })
            } else if (this.loading && this.data === null) {
              Loader({ text: I18n.t('loading') })
            } else if (this.data === null) {
              EmptyState({ text: I18n.t('noData') })
            } else {
              if (!this.wide) {
                this.rangePills()
              }
              Column({ space: this.wide ? 12 : 10 }) {
                this.kpiSection()
                this.tokenCompositionCard()
                if (this.wide) {
                  Row({ space: Dimens.GAP_WIDE }) {
                    Column() {
                      this.modelUsageCard()
                    }.layoutWeight(5)
                    Column() {
                      this.trendCard()
                    }.layoutWeight(8)
                  }
                  .width('100%')
                  .alignItems(VerticalAlign.Top)
                  Row({ space: Dimens.GAP_WIDE }) {
                    Column() {
                      this.heatmapCard()
                    }.layoutWeight(this.hasModelTrend() ? 5 : 10)
                    if (this.hasModelTrend()) {
                      Column() {
                        this.modelTrendCard()
                      }.layoutWeight(8)
                    }
                  }
                  .width('100%')
                  .alignItems(VerticalAlign.Top)
                } else {
                  this.modelUsageCard()
                  this.trendCard()
                  this.heatmapCard()
                  if (this.hasModelTrend()) {
                    this.modelTrendCard()
                  }
                }
              }
              .width('100%')
              .opacity(this.appear)
              .translate({ y: (1 - this.appear) * 8 })
            }
          }
          .width('100%')
          .padding({
            left: this.wide ? Dimens.PAGE_H_WIDE : Dimens.PAGE_H,
            right: this.wide ? Dimens.PAGE_H_WIDE : Dimens.PAGE_H,
            top: this.wide ? Dimens.PAGE_V_WIDE : Dimens.PAGE_V,
            bottom: this.wide ? Dimens.PAGE_V_WIDE : Dimens.PAGE_V,
          })
        }
        .width('100%')
        .height('100%')
        .scrollBar(BarState.Off)
        .edgeEffect(EdgeEffect.Spring)
        .align(Alignment.Top)
      }
      .width('100%')
      .layoutWeight(1)
      .onRefreshing(() => {
        this.doSync()
      })
    }
    .width('100%')
    .height('100%')
    .backgroundColor(Theme.bg())
    .onAreaChange((_old: Area, area: Area) => {
      const w: number = area.width as number
      this.wide = w >= Dimens.WIDE_BREAKPOINT
    })
  }
}
