/**
 * 统计页 —— Token 构成 + 模型排行 + 三线趋势 (android StatsScreen / desktop stats 移植)。
 */
import { Repo } from '../../data/repository/DashboardRepository'
import { DashboardData, ModelStat } from '../../common/model/Models'
import { Fmt } from '../../common/util/Fmt'
import { KpiCard, ModelIcon, SectionCard } from '../components/Cards'
import { I18n } from '../../common/i18n/I18n'
import { DonutChart, TrendLine, TrendPointSeries } from '../components/Charts'

interface TrendAgg {
  cost: number
  req: number
  tokens: number
}
@Component
export struct StatsPage {
  @State private data: DashboardData | null = null
  @State private sortBy: string = 'cost'
  @State private currency: string = 'USD'
  @Prop @Watch('onRefresh') refreshToken: number = 0

  aboutToAppear(): void {
    this.load()
  }

  onRefresh(): void {
    this.load()
  }

  private async load(): Promise<void> {
    try {
      this.data = await Repo.get().loadDashboard('30d')
    } catch (e) {
      this.data = null
    }
  }

  private rankValue(m: ModelStat): number {
    if (this.sortBy === 'output') {
      return m.totalOutputTokens
    }
    if (this.sortBy === 'input') {
      return m.totalInputTokens
    }
    return m.totalCostUsd
  }

  private sortedModels(): ModelStat[] {
    if (this.data === null) {
      return []
    }
    const list = this.data.models.slice()
    list.sort((a, b) => this.rankValue(b) - this.rankValue(a))
    return list
  }

  private trendSeries(): TrendPointSeries[] {
    const d = this.data
    if (d === null) {
      return []
    }
    const byDate: Map<string, TrendAgg> = new Map()
    for (const day of d.trend) {
      byDate.set(day.date, {
        cost: Math.round(day.totalCostUsd * 100),
        req: day.requestCount,
        tokens: day.totalInputTokens + day.totalOutputTokens + day.totalReasoningTokens,
      })
    }
    // 按日期升序生成序列
    const dates: string[] = []
    for (const day of d.trend) {
      dates.push(day.date)
    }
    dates.sort()
    const costV: number[] = []
    const reqV: number[] = []
    const tokV: number[] = []
    for (const dt of dates) {
      const v = byDate.get(dt)
      if (v !== undefined) {
        costV.push(v.cost)
        reqV.push(v.req)
        tokV.push(v.tokens)
      }
    }
    return [
      { name: '费用', color: '#3B82F6', values: costV },
      { name: '请求', color: '#10B981', values: reqV },
      { name: 'TOKEN', color: '#F59E0B', values: tokV },
    ]
  }

  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.data === null) {
          Text(I18n.t('loading')).fontSize(14).fontColor('#999999').padding(24)
        } else {
          SectionCard({ title: I18n.t('token_composition'), subtitle: I18n.t('days30') }) {
            Row({ space: 12 }) {
              DonutChart({ percent: this.donutPercent(), centerLabel: `${Fmt.tokens(this.data!.totals.totalTokens)}` })
              Column({ space: 6 }) {
                this.compositionRow(I18n.t('input'), this.data!.totals.totalInputTokens, '#3B82F6')
                this.compositionRow(I18n.t('output'), this.data!.totals.totalOutputTokens, '#FFB74D')
                this.compositionRow(I18n.t('reasoning'), this.data!.totals.totalReasoningTokens, '#A78BFA')
                this.compositionRow(I18n.t('cache_hit'), this.data!.totals.cacheHitTokens, '#10B981')
              }
            }
            .width('100%')
          }

          SectionCard({ title: I18n.t('model_rank'), subtitle: this.sortLabel() }) {
            Row({ space: 8 }) {
              this.sortPill('cost', I18n.t('by_cost'))
              this.sortPill('tokens', I18n.t('by_tokens'))
              this.sortPill('output', I18n.t('by_output'))
              Blank()
            }
            .width('100%')
            .margin({ bottom: 8 })
            Column({ space: 8 }) {
              ForEach(this.sortedModels(), (m: ModelStat) => {
                Row({ space: 8 }) {
                  ModelIcon({ model: m.model })
                  Column({ space: 2 }) {
                    Text(m.model)
                      .fontSize(13)
                      .fontColor('#222222')
                      .maxLines(1)
                    Text(`${Fmt.int(m.requestCount)} ${I18n.t('req_unit')} · ${I18n.t('sessions')} ${Fmt.int(m.sessionCount)}`)
                      .fontSize(11)
                      .fontColor('#999999')
                  }
                  .alignItems(HorizontalAlign.Start)
                  .layoutWeight(1)
                  Column({ space: 2 }) {
                    Text(Fmt.tokens(m.totalInputTokens + m.totalOutputTokens))
                      .fontSize(13)
                      .fontWeight(FontWeight.Medium)
                      .fontColor('#333333')
                    Text(Fmt.money(m.totalCostUsd, this.currency, this.data!.usdCny))
                      .fontSize(11)
                      .fontColor('#888888')
                  }
                  .alignItems(HorizontalAlign.End)
                }
                .width('100%')
                .padding(8)
                .backgroundColor('#F8F9FC')
                .borderRadius(10)
              }, (m: ModelStat) => m.model)
            }
          }

          SectionCard({ title: I18n.t('trend_title'), subtitle: I18n.t('days30') }) {
            TrendLine({ series: this.trendSeries(), chartHeight: 150 })
            Row({ space: 14 }) {
              this.legend('#3B82F6', I18n.t('cost'))
              this.legend('#10B981', I18n.t('req_unit'))
              this.legend('#F59E0B', I18n.t('by_tokens'))
            }
            .margin({ top: 6 })
          }
        }
      }
      .width('100%')
      .padding(12)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F2F3F7')
  }

  private sortLabel(): string {
    if (this.sortBy === 'output') {
      return I18n.t('by_output')
    }
    if (this.sortBy === 'input') {
      return I18n.t('by_input')
    }
    return I18n.t('by_cost')
  }

  @Builder
  sortPill(key: string, label: string) {
    Text(label)
      .fontSize(12)
      .fontColor(this.sortBy === key ? '#FFFFFF' : '#666666')
      .padding({ left: 10, right: 10, top: 4, bottom: 4 })
      .backgroundColor(this.sortBy === key ? '#3B82F6' : '#F0F0F0')
      .borderRadius(12)
      .onClick(() => {
        this.sortBy = key
      })
  }

  @Builder
  compositionRow(label: string, v: number, color: string) {
    Row({ space: 8 }) {
      Circle({ width: 8, height: 8 }).fill(color)
      Text(label)
        .fontSize(12)
        .fontColor('#666666')
      Blank()
      Text(Fmt.tokens(v))
        .fontSize(12)
        .fontColor('#333333')
    }
    .width(160)
  }

  @Builder
  legend(color: string, label: string) {
    Row({ space: 4 }) {
      Circle({ width: 8, height: 8 }).fill(color)
      Text(label)
        .fontSize(11)
        .fontColor('#888888')
    }
  }

  private donutPercent(): number {
    const d = this.data
    if (d === null) {
      return 0
    }
    const total = d.totals.totalTokens
    if (total <= 0) {
      return 0
    }
    const input = d.totals.totalInputTokens
    return Math.round(input / total * 100)
  }
}