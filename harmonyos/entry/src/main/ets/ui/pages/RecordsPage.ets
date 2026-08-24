/**
 * 记录页 —— 会话聚合 + 使用记录, 分页 + 模型筛选 (android RecordsScreen 移植)。
 */
import { Repo } from '../../data/repository/DashboardRepository'
import { PageResult, SessionStat, UsageRecordRow } from '../../common/model/Models'
import { Fmt } from '../../common/util/Fmt'
import { ModelIcon, SectionCard } from '../components/Cards'

const PAGE_SIZE = 20

@Component
export struct RecordsPage {
  @State private sessions: PageResult<SessionStat> = { records: [], total: 0 }
  @State private records: PageResult<UsageRecordRow> = { records: [], total: 0 }
  @State private models: string[] = []
  @State private sessionPage: number = 1
  @State private recordPage: number = 1
  @State private selModel: string = ''
  @State private currency: string = 'USD'
  @State private usdCny: number = 7.2
  @State private tab: string = 'sessions'
  @Prop @Watch('onRefresh') refreshToken: number = 0

  aboutToAppear(): void {
    this.loadAll()
  }

  onRefresh(): void {
    this.loadAll()
  }

  private async loadAll(): Promise<void> {
    try {
      const repo = Repo.get()
      this.usdCny = (await repo.loadDashboard('all')).usdCny
      await Promise.all([
        this.loadSessions(1),
        this.loadRecords(1, ''),
        repo.listModels().then((m) => { this.models = m }),
      ])
    } catch (e) {
      // ignore
    }
  }

  private async loadSessions(page: number): Promise<void> {
    this.sessions = await Repo.get().sessionsPage(page, PAGE_SIZE, null)
    this.sessionPage = page
  }

  private async loadRecords(page: number, model: string): Promise<void> {
    this.records = await Repo.get().recordsPage(page, PAGE_SIZE, model.length > 0 ? model : null, null)
    this.recordPage = page
  }

  build() {
    Column() {
      Row({ space: 10 }) {
        this.tabPill('sessions', '会话')
        this.tabPill('records', '使用记录')
        Blank()
        if (this.tab === 'records') {
          Select(this.modelOptions())
            .selected(this.selectedIndex())
            .value(this.selModel.length === 0 ? '全部模型' : this.selModel)
            .onSelect((idx: number) => {
              const m = idx < 1 ? '' : this.models[idx - 1]
              this.selModel = m
              this.loadRecords(1, m)
            })
            .width(120)
        }
      }
      .width('100%')
      .padding({ left: 12, right: 12, top: 10, bottom: 6 })

      if (this.tab === 'sessions') {
        this.sessionList()
      } else {
        this.recordList()
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F2F3F7')
  }

  private selectedIndex(): number {
    if (this.selModel.length === 0) {
      return 0
    }
    const i = this.models.indexOf(this.selModel)
    return i >= 0 ? i + 1 : 0
  }

  private modelOptions(): Array<SelectOption> {
    const out: Array<SelectOption> = [{ value: '全部模型' }]
    for (const m of this.models) {
      out.push({ value: m })
    }
    return out
  }

  @Builder
  tabPill(key: string, label: string) {
    Text(label)
      .fontSize(14)
      .fontColor(this.tab === key ? '#FFFFFF' : '#666666')
      .padding({ left: 16, right: 16, top: 6, bottom: 6 })
      .backgroundColor(this.tab === key ? '#3B82F6' : '#E9EAEE')
      .borderRadius(16)
      .onClick(() => {
        this.tab = key
      })
  }

  @Builder
  sessionList() {
    List({ space: 10 }) {
      ForEach(this.sessions.records, (s: SessionStat) => {
        ListItem() {
          Row({ space: 10 }) {
            ModelIcon({ model: this.sessionLabel(s) })
            Column({ space: 3 }) {
              Text(this.sessionTitle(s))
                .fontSize(13)
                .fontWeight(FontWeight.Medium)
                .fontColor('#222222')
                .maxLines(1)
              Text(`${Fmt.int(s.requestCount)} 请求 · ${Fmt.dateTimeShort(s.lastAt)}`)
                .fontSize(11)
                .fontColor('#999999')
            }
            .alignItems(HorizontalAlign.Start)
            .layoutWeight(1)
            Column({ space: 3 }) {
              Text(Fmt.tokens(s.totalInputTokens + s.totalOutputTokens + s.totalReasoningTokens))
                .fontSize(13)
                .fontWeight(FontWeight.Medium)
                .fontColor('#333333')
              Text(Fmt.money(s.totalCostUsd, this.currency, this.usdCny))
                .fontSize(11)
                .fontColor('#888888')
            }
            .alignItems(HorizontalAlign.End)
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#FFFFFF')
          .borderRadius(12)
        }
      }, (s: SessionStat) => s.sessionId + s.keyId)
    }
    .width('100%')
    .layoutWeight(1)
    .padding({ left: 12, right: 12 })
    this.pager(this.sessions.total, this.sessionPage, (p: number) => { this.loadSessions(p) })
  }

  @Builder
  recordList() {
    List({ space: 10 }) {
      ForEach(this.records.records, (r: UsageRecordRow) => {
        ListItem() {
          Column({ space: 6 }) {
            Row({ space: 10 }) {
              ModelIcon({ model: r.model })
              Column({ space: 2 }) {
                Text(r.model)
                  .fontSize(13)
                  .fontWeight(FontWeight.Medium)
                  .fontColor('#222222')
                  .maxLines(1)
                Text(`${r.keyName !== null && r.keyName.length > 0 ? r.keyName : '—'} · ${Fmt.dateTimeShort(r.createdAt)}`)
                  .fontSize(11)
                  .fontColor('#999999')
              }
              .alignItems(HorizontalAlign.Start)
              .layoutWeight(1)
              Text(Fmt.money(r.costUsd, this.currency, this.usdCny))
                .fontSize(13)
                .fontColor('#D97706')
            }
            .width('100%')
            Row({ space: 14 }) {
              Text(`入 ${Fmt.tokens(r.inputTokens)}`)
                .fontSize(11)
                .fontColor('#888888')
              Text(`出 ${Fmt.tokens(r.outputTokens)}`)
                .fontSize(11)
                .fontColor('#888888')
              if (r.cacheReadTokens > 0) {
                Text(`缓存 ${Fmt.tokens(r.cacheReadTokens)}`)
                  .fontSize(11)
                  .fontColor('#888888')
              }
            }
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#FFFFFF')
          .borderRadius(12)
        }
      }, (r: UsageRecordRow) => r.usgId)
    }
    .width('100%')
    .layoutWeight(1)
    .padding({ left: 12, right: 12 })
    this.pager(this.records.total, this.recordPage, (p: number) => { this.loadRecords(p, this.selModel) })
  }

  private totalPages(total: number): number {
    return Math.max(1, Math.ceil(total / PAGE_SIZE))
  }

  @Builder
  pager(total: number, page: number, onPage: (p: number) => void) {
    Row({ space: 10 }) {
      Button('‹')
        .fontSize(16)
        .width(40)
        .height(32)
        .backgroundColor(page > 1 ? '#3B82F6' : '#D3D3D3')
        .enabled(page > 1)
        .onClick(() => { onPage(Math.max(1, page - 1)) })
      Text(`${page} / ${this.totalPages(total)}`)
        .fontSize(12)
        .fontColor('#666666')
      Button('›')
        .fontSize(16)
        .width(40)
        .height(32)
        .backgroundColor(page < this.totalPages(total) ? '#3B82F6' : '#D3D3D3')
        .enabled(page < this.totalPages(total))
        .onClick(() => { onPage(Math.min(this.totalPages(total), page + 1)) })
      Blank()
      Text(`共 ${Fmt.int(total)} 条`)
        .fontSize(12)
        .fontColor('#999999')
    }
    .width('100%')
    .padding({ left: 12, right: 12, top: 8, bottom: 8 })
  }

  private sessionTitle(s: SessionStat): string {
    if (s.sessionId.length > 0) {
      const p = s.sessionId.split('_')
      return p.length > 1 ? `会话 ${p[1].slice(0, 8)}` : s.sessionId
    }
    if (s.keyId !== null && s.keyId.length > 0) {
      return s.keyName !== null && s.keyName.length > 0 ? `Key: ${s.keyName}` : '未归属 (Key)'
    }
    return '未归属'
  }

  private sessionLabel(s: SessionStat): string {
    return s.keyId !== null && s.keyId.length > 0 ? s.keyId : (s.sessionId.length > 0 ? s.sessionId : '?')
  }
}