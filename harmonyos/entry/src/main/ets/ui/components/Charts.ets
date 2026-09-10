/**
 * 图表组件 (ArkUI 原生, 零三方依赖) —— 配额环 / 24h 柱状图 / 环形图 / 折线趋势。
 * 组件内封闭实现, 后续如需可平滑替换为 mpchart 等三方库。
 */
import { HourStat } from '../../common/model/Models'
import { Theme } from '../theme/Theme'

/** 配额环: Ring Progress + 中央百分比。 */
@Component
export struct QuotaRing {
  @Prop percent: number = 0
  @Prop label: string = ''
  @Prop caption: string = ''
  @Prop accent: string = '#3B82F6'

  build() {
    Column({ space: 6 }) {
      Stack({ alignContent: Alignment.Center }) {
        Progress({ value: this.percent, total: 100, type: ProgressType.Ring })
          .width(86)
          .height(86)
          .style({ strokeWidth: 9 })
          .color(this.accent)
          .rotate({ angle: -90 })
        Text(`${Math.round(this.percent)}%`)
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
      }
      Text(this.label)
        .fontSize(13)
        .fontColor(Theme.text())
      Text(this.caption)
        .fontSize(11)
        .fontColor(Theme.sub())
        .maxLines(1)
    }
    .width(120)
    .padding(8)
    .backgroundColor(Theme.surfaceSoft())
    .borderRadius(12)
  }
}

/** 24h 输入/输出双柱状图。 */
@Component
export struct BarChart24h {
  @Prop hours: HourStat[] = []

  build() {
    Column({ space: 4 }) {
      Row() {
        Text(`${this.hours.length} 小时输入/输出`)
          .fontSize(12)
          .fontColor(Theme.sub())
        Blank()
        Row({ space: 8 }) {
          Row({ space: 3 }) {
            Circle({ width: 8, height: 8 }).fill('#4C8DFF')
            Text('输入').fontSize(11).fontColor(Theme.sub())
          }
          Row({ space: 3 }) {
            Circle({ width: 8, height: 8 }).fill('#FFB74D')
            Text('输出').fontSize(11).fontColor(Theme.sub())
          }
        }
      }
      .width('100%')

      Row({ space: 2 }) {
        ForEach(this.hours, (h: HourStat, idx: number) => {
          Column({ space: 2 }) {
            Column({ space: 1 }) {
              Column()
                .width(4)
                .height(this.barHeight(h.input, true))
                .backgroundColor('#4C8DFF')
                .borderRadius(2)
              Column()
                .width(4)
                .height(this.barHeight(h.output, false))
                .backgroundColor('#FFB74D')
                .borderRadius(2)
            }
            .height(96)
            .justifyContent(FlexAlign.End)
            if (idx % 4 === 0) {
              Text(h.hour.slice(0, 2))
                .fontSize(9)
                .fontColor(Theme.faint())
            } else {
              Text('')
                .fontSize(9)
            }
          }
        }, (h: HourStat) => h.hour)
      }
      .width('100%')
      .alignItems(VerticalAlign.Bottom)
    }
    .width('100%')
    .padding(12)
    .backgroundColor(Theme.surfaceSoft())
    .borderRadius(12)
  }

  private maxVal(): number {
    let m = 1
    for (const h of this.hours) {
      if (h.input > m) {
        m = h.input
      }
      if (h.output > m) {
        m = h.output
      }
    }
    return m
  }

  private barHeight(v: number, isInput: boolean): number {
    const m = this.maxVal()
    const ratio = m > 0 ? v / m : 0
    const h = Math.round(ratio * 88)
    if (h < 2 && v > 0) {
      return 2
    }
    return h
  }
}

/** 环形占比图 + 图例 (由调用方渲染 legend 行)。 */
@Component
export struct DonutChart {
  @Prop percent: number = 0
  @Prop centerLabel: string = ''
  @Prop accent: string = '#3B82F6'

  build() {
    Stack({ alignContent: Alignment.Center }) {
      Progress({ value: this.percent, total: 100, type: ProgressType.Ring })
        .width(110)
        .height(110)
        .style({ strokeWidth: 12 })
        .color(this.accent)
        .rotate({ angle: -90 })
      Column({ space: 0 }) {
        Text(this.centerLabel)
          .fontSize(16)
          .fontWeight(FontWeight.Bold)
      }
    }
    .padding(8)
  }
}

/** 折线趋势图 (多序列归一化, Canvas 绘制)。 */
@Component
export struct TrendLine {
  // @Watch 必需: ArkUI 的 Canvas 不会因状态变化自动重绘, 只在 onReady 回调里
  // 画一次. 没有它时, 统计页 load() 换掉数据后曲线仍是上一份 (要等组件重建,
  // 例如切 tab, 才会更新).
  @Prop @Watch('onSeriesChanged') series: TrendPointSeries[] = []
  @Prop chartHeight: number = 150
  private settings: RenderingContextSettings = new RenderingContextSettings(true)
  private ctx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings)
  /** onReady 是否已触发: 数据先到时不能画 (画布尺寸为 0), 需在 ready 后补画。 */
  private ready: boolean = false

  onSeriesChanged(): void {
    if (this.ready) {
      this.draw()
    }
  }

  build() {
    Canvas(this.ctx)
      .width('100%')
      .height(this.chartHeight)
      .backgroundColor(Theme.surfaceSoft())
      .borderRadius(12)
      .onReady(() => {
        this.ready = true
        this.draw()
      })
  }

  private draw(): void {
    const w = this.ctx.width
    const h = this.ctx.height
    if (w <= 0 || h <= 0) {
      return
    }
    this.ctx.clearRect(0, 0, w, h)
    const pad = 8
    let maxV = 0
    let n = 0
    for (const s of this.series) {
      if (s.values.length > n) {
        n = s.values.length
      }
      for (const v of s.values) {
        if (v > maxV) {
          maxV = v
        }
      }
    }
    if (n === 0 || maxV <= 0) {
      return
    }
    const step = n > 1 ? (w - pad * 2) / (n - 1) : 0
    const top = pad + 4
    const bottom = h - pad - 4
    for (const s of this.series) {
      if (s.values.length < 2) {
        continue
      }
      this.ctx.beginPath()
      for (let i = 0; i < s.values.length; i++) {
        const x = pad + i * step
        const y = bottom - (s.values[i] / maxV) * (bottom - top)
        if (i === 0) {
          this.ctx.moveTo(x, y)
        } else {
          this.ctx.lineTo(x, y)
        }
      }
      this.ctx.strokeStyle = s.color
      this.ctx.lineWidth = 2
      this.ctx.lineJoin = 'round'
      this.ctx.stroke()
    }
  }
}

export interface TrendPointSeries {
  name: string
  color: string
  values: number[]
}