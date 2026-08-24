/**
 * 首页 —— 配额窗口 + 6 KPI + 今日 24h 趋势 (android HomeScreen / desktop home 移植)。
 */
import { Repo } from '../../data/repository/DashboardRepository'
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
          Text('数据加载中…')
            .fontSize(14)
            .fontColor('#999999')
            .padding(24)
        } else {
          this.quotaSection(this.data!.quota !== null ? this.data!.quota.windows : [])
          this.kpiSection()
          SectionCard({ title: '今日趋势', subtitle: '24 小时' }) {
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
    SectionCard({ title: '配额窗口', subtitle: 'OpenCode Go' }) {
      if (windows.length === 0) {
        Text('暂无配额数据，登录后将自动同步')
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
      return '每周'
    }
    if (label.indexOf('Monthly') >= 0) {
      return '每月'
    }
    return '滚动 5 小时'
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
    return Fmt.dur(sec, '天', '时', '分', '即将重置')
  }

  @Builder
  kpiSection() {
    SectionCard({ title: '用量概览' }) {
      GridRow({ columns: { sm: 2, md: 3, lg: 6 }, gutter: 8 }) {
        GridCol() {
          KpiCard({ label: '请求数', value: Fmt.int(this.data!.totals.requestCount) })
        }
        GridCol() {
          KpiCard({ label: '总 TOKEN', value: Fmt.tokens(this.data!.totals.totalTokens) })
        }
        GridCol() {
          KpiCard({ label: '输出', value: Fmt.tokens(this.data!.totals.totalOutputTokens) })
        }
        GridCol() {
          KpiCard({ label: '缓存命中率', value: `${this.data!.totals.hitRate.toFixed(1)}%` })
        }
        GridCol() {
          KpiCard({ label: '费用', value: Fmt.money(this.data!.totals.totalCostUsd, this.currency, this.data!.usdCny) })
        }
        GridCol() {
          KpiCard({ label: '会话数', value: Fmt.int(this.data!.totals.sessionCount) })
        }
      }
    }
  }
}