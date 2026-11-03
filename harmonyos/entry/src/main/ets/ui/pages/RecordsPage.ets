/**
 * 记录页 —— 会话用量 + 使用记录，分页（每页 10 条）+ 模型筛选。
 *
 * 手机（<840vp）对标 Android RecordsScreen：页头 + 两张卡片，行是卡片式；
 * 宽屏（>=840vp）对标桌面 #page-records：同两张卡，内部渲染为表格
 * （会话 8 列 / 记录 9 列，列宽百分比对齐 app/web/style.css），行 hover 高亮。
 * 颜色/圆角/间距一律走 Theme/Dimens，文案一律走 I18n。
 */
import { Repo } from '../../data/repository/DashboardRepository'
import { PageResult, SessionStat, UsageRecordRow } from '../../common/model/Models'
import { Fmt } from '../../common/util/Fmt'
import { AppPrefs } from '../../common/store/AppPrefs'
import { I18n } from '../../common/i18n/I18n'
import { Theme, Dimens, FONT_SERIF } from '../theme/Theme'
import { GgCard, ModelIcon, Loader, EmptyState, ErrorCard, Pager } from '../components/Cards'

const PAGE_SIZE: number = 10

/** 会话表列宽（百分比，对齐桌面 .card.sessions .tbl 8 列）。 */
const SESSION_COL_W: number[] = [12, 18, 18, 9, 9, 9, 13, 12]
/** 记录表列宽（百分比，对齐桌面 .card.records .tbl 9 列）。 */
const RECORD_COL_W: number[] = [10, 16, 16, 8, 8, 8, 9, 9, 16]

@Component
export struct RecordsPage {
  @State private sessions: PageResult<SessionStat> = { records: [], total: 0 }
  @State private records: PageResult<UsageRecordRow> = { records: [], total: 0 }
  @State private models: string[] = []
  @State private sessionPage: number = 1
  @State private recordPage: number = 1
  @State private selModel: string = ''
  @State private sessionsError: string = ''
  @State private recordsError: string = ''
  @State private currency: string = 'USD'
  @State private usdCny: number = 7.2
  @State private loading: boolean = true
  @State private wide: boolean = false
  @State private syncing: boolean = false
  @State private refreshing: boolean = false
  @State private appear: number = 0
  /** 并发加载序号：快速翻页/切筛选时只采纳最后一次请求的结果。 */
  private sessionsSeq: number = 0
  private recordsSeq: number = 0
  @Prop @Watch('onRefresh') refreshToken: number = 0
  /** 壳层统一注入（记录页页头不放账号胶囊，保留以兼容 AppRoot 的调用）。 */
  onOpenAccountSwitcher: () => void = () => {
  }

  aboutToAppear(): void {
    this.loadAll(true)
  }

  onRefresh(): void {
    this.loadAll(false)
  }

  // ------------------------------------------------------------------
  // 数据加载（保留原有 loadSessions / loadRecords 调用方式与错误处理）
  // ------------------------------------------------------------------

  private async loadAll(initial: boolean): Promise<void> {
    if (initial) {
      this.loading = true
    }
    this.currency = AppPrefs.getCurrency()
    try {
      this.usdCny = await Repo.get().usdCnyRate()
    } catch (e) {
      // 汇率失败沿用默认值，不阻塞列表
    }
    await this.loadSessions(this.sessionPage)
    await this.loadRecords(this.recordPage, this.selModel)
    await this.loadModels()
    this.loading = false
    this.playEnter()
  }

  private async loadSessions(page: number): Promise<void> {
    this.sessionsSeq += 1
    const seq: number = this.sessionsSeq
    try {
      const res: PageResult<SessionStat> = await Repo.get().sessionsPage(page, PAGE_SIZE, null)
      if (seq !== this.sessionsSeq) {
        return
      }
      this.sessions = res
      this.sessionPage = page
      this.sessionsError = ''
    } catch (e) {
      if (seq !== this.sessionsSeq) {
        return
      }
      const msg: string = (e as Error).message !== undefined ? (e as Error).message : ''
      this.sessionsError = msg.length > 0 ? msg : I18n.t('sync_fail')
    }
  }

  private async loadRecords(page: number, model: string): Promise<void> {
    this.recordsSeq += 1
    const seq: number = this.recordsSeq
    try {
      const res: PageResult<UsageRecordRow> = await Repo.get().recordsPage(
        page, PAGE_SIZE, model.length > 0 ? model : null, null)
      if (seq !== this.recordsSeq) {
        return
      }
      this.records = res
      this.recordPage = page
      this.recordsError = ''
    } catch (e) {
      if (seq !== this.recordsSeq) {
        return
      }
      const msg: string = (e as Error).message !== undefined ? (e as Error).message : ''
      this.recordsError = msg.length > 0 ? msg : I18n.t('sync_fail')
    }
  }

  private async loadModels(): Promise<void> {
    try {
      this.models = await Repo.get().listModels()
    } catch (e) {
      // 模型筛选列表失败不影响两张主卡
    }
  }

  /** 页头刷新按钮 / 下拉刷新：增量同步完成后重载当前页。 */
  private async doSync(): Promise<void> {
    if (this.syncing) {
      return
    }
    this.syncing = true
    this.refreshing = true
    try {
      await Repo.get().syncAll('incremental')
    } catch (e) {
      // 同步失败仍重载本地数据
    }
    await this.loadAll(false)
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

  private money(usd: number): string {
    return Fmt.money(usd, this.currency, this.usdCny)
  }

  private totalPages(total: number): number {
    return Math.max(1, Math.ceil(total / PAGE_SIZE))
  }

  private pageInfo(page: number, total: number): string {
    return `${page} / ${this.totalPages(total)}`
  }

  private changeFilter(model: string): void {
    if (this.selModel === model) {
      return
    }
    this.selModel = model
    this.loadRecords(1, model)
  }

  private selectedIndex(): number {
    if (this.selModel.length === 0) {
      return 0
    }
    const i: number = this.models.indexOf(this.selModel)
    return i >= 0 ? i + 1 : 0
  }

  private modelOptions(): Array<SelectOption> {
    const out: Array<SelectOption> = [{ value: I18n.t('all_models') }]
    for (const m of this.models) {
      out.push({ value: m })
    }
    return out
  }

  // ------------------------------------------------------------------
  // 会话行文案
  // ------------------------------------------------------------------

  private keyLabel(s: SessionStat): string {
    if (s.keyName !== null && s.keyName.length > 0) {
      return s.keyName
    }
    if (s.keyId !== null && s.keyId.length > 0) {
      return `…${s.keyId.slice(s.keyId.length > 6 ? s.keyId.length - 6 : 0)}`
    }
    return '—'
  }

  private sessionTitle(s: SessionStat): string {
    if (s.sessionId.length > 0) {
      const p: string[] = s.sessionId.split('_')
      return p.length > 1 ? `${I18n.t('session_prefix')} ${p[1].slice(0, 8)}` : s.sessionId
    }
    if (s.keyId !== null && s.keyId.length > 0) {
      return s.keyName !== null && s.keyName.length > 0
        ? `${I18n.t('key_prefix')} ${s.keyName}`
        : I18n.t('ungrouped_key')
    }
    return I18n.t('ungrouped')
  }

  private sessionCell(s: SessionStat): string {
    return s.sessionId.length > 0 ? this.sessionTitle(s) : I18n.t('ungrouped')
  }

  /** 会话缓存量：总输入（含缓存读/写）与未缓存输入之差。 */
  private sessionCache(s: SessionStat): number {
    return Math.max(0, s.totalInputTokens - s.uncachedInputTokens)
  }

  private sessionTokensLine(s: SessionStat): string {
    return `${I18n.t('colInput')} ${Fmt.tokens(s.totalInputTokens)} · ` +
      `${I18n.t('colOutput')} ${Fmt.tokens(s.totalOutputTokens)} · ` +
      `${I18n.t('colReasoning')} ${Fmt.tokens(s.totalReasoningTokens)} · ` +
      `${I18n.t('cache_label')} ${Fmt.tokens(this.sessionCache(s))}`
  }

  private sessionRequestsLine(s: SessionStat): string {
    return `${I18n.t('colLastUsed')} ${Fmt.dateTimeShort(s.lastAt)} · ` +
      `${Fmt.int(s.requestCount)} ${I18n.t('colRequests')}`
  }

  // ------------------------------------------------------------------
  // 使用记录行文案
  // ------------------------------------------------------------------

  private recordKey(r: UsageRecordRow): string {
    if (r.keyName !== null && r.keyName.length > 0) {
      return r.keyName
    }
    if (r.keyId !== null && r.keyId.length > 0) {
      return `…${r.keyId.slice(r.keyId.length > 6 ? r.keyId.length - 6 : 0)}`
    }
    return '—'
  }

  private recordMeta(r: UsageRecordRow): string {
    const time: string = Fmt.dateTimeShort(r.createdAt)
    const key: string = this.recordKey(r)
    return key === '—' ? time : `${time} · ${key}`
  }

  private recordTokensLine(r: UsageRecordRow): string {
    return `${I18n.t('colInput')} ${Fmt.tokens(r.inputTokens)} · ` +
      `${I18n.t('colOutput')} ${Fmt.tokens(r.outputTokens)} · ` +
      `${I18n.t('colReasoning')} ${Fmt.tokens(r.reasoningTokens)} · ` +
      `${I18n.t('colCacheRead')} ${Fmt.tokens(r.cacheReadTokens)} · ` +
      `${I18n.t('colCacheWrite')} ${Fmt.tokens(r.cacheWriteTokens)}`
  }

  // ------------------------------------------------------------------
  // 页头
  // ------------------------------------------------------------------

  @Builder
  pageHeader() {
    Row({ space: 8 }) {
      Text(I18n.t('recordsPage'))
        .fontSize(this.wide ? Dimens.TITLE_WIDE : Dimens.TITLE_PHONE)
        .fontFamily(FONT_SERIF)
        .fontWeight(FontWeight.Bold)
        .fontColor(Theme.text())
        .maxLines(1)
      Blank()
      if (!this.wide) {
        this.refreshButton()
      }
    }
    .width('100%')
    .height(Dimens.TOUCH_MIN)
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

  // ------------------------------------------------------------------
  // 会话用量卡
  // ------------------------------------------------------------------

  @Builder
  sessionsCard() {
    GgCard({
      title: I18n.t('sessionUsage'),
      hint: `${I18n.t('totalN')} ${Fmt.int(this.sessions.total)} ${I18n.t('items')}`,
    }) {
      this.sessionsBody()
    }
  }

  @Builder
  sessionsBody() {
    if (this.sessionsError.length > 0 && this.sessions.records.length === 0) {
      ErrorCard({
        title: I18n.t('sync_fail'),
        detail: this.sessionsError,
        retryText: I18n.t('retry'),
        onRetry: () => {
          this.loadSessions(this.sessionPage)
        },
      })
    } else if (this.sessions.records.length === 0) {
      EmptyState({ text: I18n.t('noData') })
    } else {
      Column({ space: 8 }) {
        if (this.wide) {
          this.sessionTable()
        } else {
          this.sessionCards()
        }
        Pager({
          pageInfo: this.pageInfo(this.sessionPage, this.sessions.total),
          prevText: I18n.t('prev'),
          nextText: I18n.t('next'),
          hasPrev: this.sessionPage > 1,
          hasNext: this.sessionPage < this.totalPages(this.sessions.total),
          onPrev: () => {
            this.loadSessions(Math.max(1, this.sessionPage - 1))
          },
          onNext: () => {
            this.loadSessions(Math.min(this.totalPages(this.sessions.total), this.sessionPage + 1))
          },
        })
      }
      .width('100%')
    }
  }

  @Builder
  sessionCards() {
    Column({ space: 8 }) {
      ForEach(this.sessions.records, (s: SessionStat) => {
        Column({ space: 4 }) {
          Row({ space: 8 }) {
            Text(this.sessionTitle(s))
              .fontSize(13)
              .fontWeight(FontWeight.Medium)
              .fontColor(s.sessionId.length > 0 ? Theme.text() : Theme.sub())
              .maxLines(1)
              .textOverflow({ overflow: TextOverflow.Ellipsis })
              .layoutWeight(1)
            Text(this.money(s.totalCostUsd))
              .fontSize(13)
              .fontWeight(FontWeight.Bold)
              .fontColor(Theme.text())
              .maxLines(1)
          }
          .width('100%')
          Text(this.sessionRequestsLine(s))
            .fontSize(11)
            .fontColor(Theme.sub())
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          if (s.keyName !== null && s.keyName.length > 0 && s.sessionId.length > 0) {
            Text(s.keyName)
              .fontSize(11)
              .fontColor(Theme.faint())
              .maxLines(1)
              .textOverflow({ overflow: TextOverflow.Ellipsis })
          }
          Text(this.sessionTokensLine(s))
            .fontSize(11)
            .fontColor(Theme.sub())
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding({ left: 10, right: 10, top: 8, bottom: 8 })
        .backgroundColor(Theme.surfaceSoft())
        .borderRadius(Dimens.TILE_RADIUS)
      }, (s: SessionStat) => `${s.sessionId}_${s.keyId !== null ? s.keyId : ''}_${s.lastAt}`)
    }
    .width('100%')
  }

  @Builder
  sessionTable() {
    Column() {
      Row() {
        this.thCell(I18n.t('colKey'), SESSION_COL_W[0], false)
        this.thCell(I18n.t('colSession'), SESSION_COL_W[1], false)
        this.thCell(I18n.t('colLastUsed'), SESSION_COL_W[2], false)
        this.thCell(I18n.t('colInput'), SESSION_COL_W[3], true)
        this.thCell(I18n.t('colOutput'), SESSION_COL_W[4], true)
        this.thCell(I18n.t('colReasoning'), SESSION_COL_W[5], true)
        this.thCell(I18n.t('colRequests'), SESSION_COL_W[6], true)
        this.thCell(I18n.t('colCost'), SESSION_COL_W[7], true)
      }
      .width('100%')
      .height(26)
      .border({ width: { bottom: 1 }, color: Theme.border() })
      ForEach(this.sessions.records, (s: SessionStat) => {
        Row() {
          this.tdCell(this.keyLabel(s), SESSION_COL_W[0], false)
          this.tdCell(this.sessionCell(s), SESSION_COL_W[1], false)
          this.tdCell(Fmt.dateTimeShort(s.lastAt), SESSION_COL_W[2], false)
          this.tdCell(Fmt.tokens(s.totalInputTokens), SESSION_COL_W[3], true)
          this.tdCell(Fmt.tokens(s.totalOutputTokens), SESSION_COL_W[4], true)
          this.tdCell(Fmt.tokens(s.totalReasoningTokens), SESSION_COL_W[5], true)
          this.tdCell(Fmt.int(s.requestCount), SESSION_COL_W[6], true)
          this.tdCell(this.money(s.totalCostUsd), SESSION_COL_W[7], true)
        }
        .width('100%')
        .height(30)
        .hoverEffect(HoverEffect.Highlight)
        .border({ width: { bottom: 0.5 }, color: Theme.border() })
      }, (s: SessionStat) => `st_${s.sessionId}_${s.keyId !== null ? s.keyId : ''}_${s.lastAt}`)
    }
    .width('100%')
  }

  // ------------------------------------------------------------------
  // 使用记录卡
  // ------------------------------------------------------------------

  @Builder
  recordsCard() {
    GgCard({}) {
      Column({ space: 8 }) {
        Row({ space: 8 }) {
          Text(I18n.t('usageRecords'))
            .fontSize(15)
            .fontFamily('GgSerif')
            .fontColor(Theme.text())
            .maxLines(1)
          Text(`${I18n.t('totalN')} ${Fmt.int(this.records.total)} ${I18n.t('items')}`)
            .fontSize(11)
            .fontColor(Theme.faint())
            .maxLines(1)
          Blank()
          this.recordFilter()
        }
        .width('100%')
        this.recordsBody()
      }
      .width('100%')
    }
  }

  @Builder
  recordFilter() {
    Select(this.modelOptions())
      .selected(this.selectedIndex())
      .value(this.selModel.length === 0 ? I18n.t('all_models') : this.selModel)
      .width(126)
      .height(Dimens.TOUCH_MIN)
      .onSelect((index: number) => {
        const model: string = index < 1 ? '' : this.models[index - 1]
        this.changeFilter(model)
      })
  }

  @Builder
  recordsBody() {
    if (this.recordsError.length > 0 && this.records.records.length === 0) {
      ErrorCard({
        title: I18n.t('sync_fail'),
        detail: this.recordsError,
        retryText: I18n.t('retry'),
        onRetry: () => {
          this.loadRecords(this.recordPage, this.selModel)
        },
      })
    } else if (this.records.records.length === 0) {
      EmptyState({ text: I18n.t('noData') })
    } else {
      Column({ space: 8 }) {
        if (this.wide) {
          this.recordTable()
        } else {
          this.recordCards()
        }
        Pager({
          pageInfo: this.pageInfo(this.recordPage, this.records.total),
          prevText: I18n.t('prev'),
          nextText: I18n.t('next'),
          hasPrev: this.recordPage > 1,
          hasNext: this.recordPage < this.totalPages(this.records.total),
          onPrev: () => {
            this.loadRecords(Math.max(1, this.recordPage - 1), this.selModel)
          },
          onNext: () => {
            this.loadRecords(
              Math.min(this.totalPages(this.records.total), this.recordPage + 1), this.selModel)
          },
        })
      }
      .width('100%')
    }
  }

  @Builder
  recordCards() {
    Column({ space: 8 }) {
      ForEach(this.records.records, (r: UsageRecordRow) => {
        Column({ space: 4 }) {
          Row({ space: 8 }) {
            ModelIcon({ model: r.model })
            Text(r.model)
              .fontSize(13)
              .fontWeight(FontWeight.Medium)
              .fontColor(Theme.text())
              .maxLines(1)
              .textOverflow({ overflow: TextOverflow.Ellipsis })
              .layoutWeight(1)
            Text(this.money(r.costUsd))
              .fontSize(13)
              .fontWeight(FontWeight.Bold)
              .fontColor(Theme.text())
              .maxLines(1)
          }
          .width('100%')
          Text(this.recordMeta(r))
            .fontSize(11)
            .fontColor(Theme.sub())
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Text(this.recordTokensLine(r))
            .fontSize(11)
            .fontColor(Theme.sub())
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding({ left: 10, right: 10, top: 8, bottom: 8 })
        .backgroundColor(Theme.surfaceSoft())
        .borderRadius(Dimens.TILE_RADIUS)
      }, (r: UsageRecordRow) => r.usgId)
    }
    .width('100%')
  }

  @Builder
  recordTable() {
    Column() {
      Row() {
        this.thCell(I18n.t('colKey'), RECORD_COL_W[0], false)
        this.thCell(I18n.t('colTime'), RECORD_COL_W[1], false)
        this.thCell(I18n.t('colModel'), RECORD_COL_W[2], false)
        this.thCell(I18n.t('colInput'), RECORD_COL_W[3], true)
        this.thCell(I18n.t('colOutput'), RECORD_COL_W[4], true)
        this.thCell(I18n.t('colReasoning'), RECORD_COL_W[5], true)
        this.thCell(I18n.t('colCacheRead'), RECORD_COL_W[6], true)
        this.thCell(I18n.t('colCacheWrite'), RECORD_COL_W[7], true)
        this.thCell(I18n.t('colCost'), RECORD_COL_W[8], true)
      }
      .width('100%')
      .height(26)
      .border({ width: { bottom: 1 }, color: Theme.border() })
      ForEach(this.records.records, (r: UsageRecordRow) => {
        Row() {
          this.tdCell(this.recordKey(r), RECORD_COL_W[0], false)
          this.tdCell(Fmt.dateTimeShort(r.createdAt), RECORD_COL_W[1], false)
          this.tdCell(r.model, RECORD_COL_W[2], false)
          this.tdCell(Fmt.tokens(r.inputTokens), RECORD_COL_W[3], true)
          this.tdCell(Fmt.tokens(r.outputTokens), RECORD_COL_W[4], true)
          this.tdCell(Fmt.tokens(r.reasoningTokens), RECORD_COL_W[5], true)
          this.tdCell(Fmt.tokens(r.cacheReadTokens), RECORD_COL_W[6], true)
          this.tdCell(Fmt.tokens(r.cacheWriteTokens), RECORD_COL_W[7], true)
          this.tdCell(this.money(r.costUsd), RECORD_COL_W[8], true)
        }
        .width('100%')
        .height(30)
        .hoverEffect(HoverEffect.Highlight)
        .border({ width: { bottom: 0.5 }, color: Theme.border() })
      }, (r: UsageRecordRow) => r.usgId)
    }
    .width('100%')
  }

  // ------------------------------------------------------------------
  // 表格单元
  // ------------------------------------------------------------------

  @Builder
  thCell(label: string, pct: number, numeric: boolean) {
    Text(label)
      .fontSize(11)
      .fontWeight(FontWeight.Medium)
      .fontColor(Theme.faint())
      .width(`${pct}%`)
      .textAlign(numeric ? TextAlign.End : TextAlign.Start)
      .maxLines(1)
      .textOverflow({ overflow: TextOverflow.Ellipsis })
      .padding({ left: 4, right: 4 })
  }

  @Builder
  tdCell(text: string, pct: number, numeric: boolean) {
    Text(text)
      .fontSize(12)
      .fontColor(numeric ? Theme.text() : Theme.sub())
      .width(`${pct}%`)
      .textAlign(numeric ? TextAlign.End : TextAlign.Start)
      .maxLines(1)
      .textOverflow({ overflow: TextOverflow.Ellipsis })
      .padding({ left: 4, right: 4 })
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
            if (this.loading && this.sessions.records.length === 0 && this.records.records.length === 0) {
              Loader({ text: I18n.t('loading') })
            } else {
              Column({ space: this.wide ? 12 : 10 }) {
                this.sessionsCard()
                this.recordsCard()
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
