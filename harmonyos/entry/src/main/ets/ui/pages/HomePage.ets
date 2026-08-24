/**
 * 首页 —— 配额窗口 + 6 KPI + 今日 24h 趋势 (android HomeScreen / desktop home 移植)。
 */
import { Repo } from '../../data/repository/DashboardRepository'
import { I18n } from '../../common/i18n/I18n'
import { DashboardData, QuotaWindow } from '../../common/model/Models'
import { Fmt } from '../../common/util/Fmt'
import { KpiCard, SectionCard } from '../components/Cards'
import { BarChart24h, QuotaRing } from '../components/Charts'

@Component
export struct HomePage {
  @State private data: DashboardData | null = null
  @State private currency: string = 'USD'
  @Prop @Watch('onRefresh') refreshToken: number = 0

  aboutToAppear(): void {
    this.load()
  }

  onRefresh(): void {
    this.load()
  }

  aboutToReuse(params: Record<string, Object>): void {
    this.load()
  }

  private async load(): Promise<void> {
    try {
      this.data = await Repo.get().loadDashboard('all')
    } catch (e) {
      this.data = null
    }
  }

  build() {
    Scroll() {
      Column({ space: 12 }) {
        if (this.data === null) {
          Text(I18n.t('loading'))
            .fontSize(14)
            .fontColor('#999999')
            .padding(24)
        } else {
          this.quotaSection(this.data!.quota !== null ? this.data!.quota.windows : [])
          this.kpiSection()
          SectionCard({ title: I18n.t('today_trend'), subtitle: I18n.t('hours24') }) {
            BarChart24h({ hours: this.data!.todayTrend })
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

  @Builder
  quotaSection(windows: QuotaWindow[]) {
    SectionCard({ title: I18n.t('quota_windows'), subtitle: 'OpenCode Go' }) {
      if (windows.length === 0) {
        Text(I18n.t('quota_empty'))
          .fontSize(12)
          .fontColor('#999999')
      } else {
        GridRow({ columns: { sm: 2, md: 3, lg: 4 }, gutter: 8 }) {
          ForEach(windows, (w: QuotaWindow) => {
            GridCol() {
              QuotaRing({
                percent: w.used,
                label: this.windowLabel(w.label),
                caption: this.resetCaption(w.resetInSec),
                accent: this.windowAccent(w.label),
              })
            }
          }, (w: QuotaWindow) => w.label)
        }
      }
    }
  }

  private windowLabel(label: string): string {
    if (label.indexOf('Weekly') >= 0) {
      return I18n.t('weekly')
    }
    if (label.indexOf('Monthly') >= 0) {
      return I18n.t('monthly')
    }
    return I18n.t('rolling5h')
  }

  private windowAccent(label: string): string {
    if (label.indexOf('Weekly') >= 0) {
      return '#F59E0B'
    }
    if (label.indexOf('Monthly') >= 0) {
      return '#10B981'
    }
    return '#3B82F6'
  }

  private resetCaption(sec: number): string {
    return Fmt.dur(sec, I18n.t('d_unit'), I18n.t('h_unit'), I18n.t('m_unit'), I18n.t('soon'))
  }

  @Builder
  kpiSection() {
    SectionCard({ title: I18n.t('overview') }) {
      GridRow({ columns: { sm: 2, md: 3, lg: 6 }, gutter: 8 }) {
        GridCol() {
          KpiCard({ label: I18n.t('requests'), value: Fmt.int(this.data!.totals.requestCount) })
        }
        GridCol() {
          KpiCard({ label: I18n.t('total_tokens'), value: Fmt.tokens(this.data!.totals.totalTokens) })
        }
        GridCol() {
          KpiCard({ label: I18n.t('output'), value: Fmt.tokens(this.data!.totals.totalOutputTokens) })
        }
        GridCol() {
          KpiCard({ label: I18n.t('hit_rate'), value: `${this.data!.totals.hitRate.toFixed(1)}%` })
        }
        GridCol() {
          KpiCard({ label: I18n.t('cost'), value: Fmt.money(this.data!.totals.totalCostUsd, this.currency, this.data!.usdCny) })
        }
        GridCol() {
          KpiCard({ label: I18n.t('sessions'), value: Fmt.int(this.data!.totals.sessionCount) })
        }
      }
    }
  }
}