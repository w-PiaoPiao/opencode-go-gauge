/**
 * 图表组件（ArkUI 原生，零三方依赖）—— 24h 双柱 / 环形占比 / 多序列折线 / 模型堆叠面积 / 日历热力图。
 *
 * - 布局型图表（柱状/热力图）用 ArkUI 布局元素实现，天然响应式 + 可做弹性动画；
 * - 曲线类图表用 Canvas 绘制，进入时整体淡入（Canvas 不逐帧重绘，避免动画掉帧）。
 * - 颜色一律来自 Theme 令牌；数据由页面传入，组件不读 Repo/DB。
 */
import { HourStat } from '../../common/model/Models'
import { I18n } from '../../common/i18n/I18n'
import { Theme, Dimens } from '../theme/Theme'

/** 环形图 / 占比图的一段。 */
export interface ChartSegment {
  name: string
  value: number
  color: string
}

/** 折线/面积图的一条序列。 */
export interface TrendSeries {
  name: string
  color: string
  values: number[]
}

/** 热力图的一天。 */
export interface HeatDay {
  date: string
  value: number
  requests: number
  cost: number
}

/** 24 小时输入/输出双柱图（手机/宽屏共用，宽度自适应）。 */
@Component
export struct BarChart24h {
  @Prop @Watch('onData') hours: HourStat[] = []
  /** true = 输入含缓存读/写（与桌面「含缓存」口径一致）。 */
  @Prop totalMode: boolean = false
  @Prop chartHeight: number = 132
  @Prop inputLabel: string = ''
  @Prop outputLabel: string = ''
  @State private grow: number = 0

  aboutToAppear(): void {
    this.play()
  }

  onData(): void {
    this.play()
  }

  private play(): void {
    this.grow = 0
    animateTo({ duration: 450, curve: Curve.EaseOut }, () => {
      this.grow = 1
    })
  }

  private inputValue(h: HourStat): number {
    return this.totalMode ? h.input + h.cacheRead + h.cacheWrite : h.input
  }

  private maxVal(): number {
    let m = 1
    for (const h of this.hours) {
      const iv = this.inputValue(h)
      if (iv > m) {
        m = iv
      }
      if (h.output > m) {
        m = h.output
      }
    }
    return m
  }

  private barH(v: number): number {
    const m = this.maxVal()
    const ratio = m > 0 ? v / m : 0
    return Math.max(2, ratio * this.chartHeight * this.grow)
  }

  build() {
    Column({ space: 6 }) {
      Row({ space: 12 }) {
        Row({ space: 4 }) {
          Circle({ width: 7, height: 7 }).fill(Theme.chartInput())
          Text(this.inputLabel)
            .fontSize(11)
            .fontColor(Theme.faint())
            .maxLines(1)
        }
        Row({ space: 4 }) {
          Circle({ width: 7, height: 7 }).fill(Theme.chartOutput())
          Text(this.outputLabel)
            .fontSize(11)
            .fontColor(Theme.faint())
            .maxLines(1)
        }
        Blank()
      }
      .width('100%')

      Stack({ alignContent: Alignment.TopStart }) {
        // 网格线（4 条，顶部到底部均匀分布）
        Column() {
          ForEach([0, 1, 2, 3], (i: number) => {
            Divider()
              .strokeWidth(0.5)
              .color(Theme.border())
              .opacity(i === 3 ? 0.9 : 0.45)
          }, (i: number) => `g_${i}`)
        }
        .width('100%')
        .height(this.chartHeight)
        .justifyContent(FlexAlign.SpaceBetween)

        Row() {
          ForEach(this.hours, (h: HourStat, idx: number) => {
            Column() {
              Row({ space: 1 }) {
                Column()
                  .width('46%')
                  .height(this.barH(this.inputValue(h)))
                  .backgroundColor(Theme.chartInput())
                  .borderRadius(1)
                Column()
                  .width('46%')
                  .height(this.barH(h.output))
                  .backgroundColor(Theme.chartOutput())
                  .borderRadius(1)
              }
              .width('100%')
              .height(this.chartHeight)
              .alignItems(VerticalAlign.Bottom)
            }
            .layoutWeight(1)
          }, (h: HourStat) => h.hour)
        }
        .width('100%')
        .height(this.chartHeight)
      }
      .width('100%')
      .height(this.chartHeight)

      Row() {
        ForEach(this.hours, (h: HourStat, idx: number) => {
          Text(idx % 4 === 0 ? h.hour.slice(0, 2) : '')
            .fontSize(9)
            .fontColor(Theme.faint())
            .layoutWeight(1)
            .textAlign(TextAlign.Center)
        }, (h: HourStat) => `l_${h.hour}`)
      }
      .width('100%')
    }
    .width('100%')
  }
}

/** 环形占比图：Canvas 绘制圆环 + 居中总量（尺寸自适应由调用方指定）。 */
@Component
export struct DonutChart {
  @Prop @Watch('onData') segments: ChartSegment[] = []
  @Prop centerValue: string = ''
  @Prop centerLabel: string = ''
  @Prop chartSize: number = 156
  @Prop thickness: number = 16
  @State private appear: number = 0
  private settings: RenderingContextSettings = new RenderingContextSettings(true)
  private ctx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings)

  aboutToAppear(): void {
    animateTo({ duration: 380, curve: Curve.EaseOut }, () => {
      this.appear = 1
    })
  }

  onData(): void {
    this.paint()
  }

  private total(): number {
    let t = 0
    for (const s of this.segments) {
      if (s.value > 0) {
        t += s.value
      }
    }
    return t
  }

  private paint(): void {
    const c = this.ctx
    const w = this.chartSize
    const h = this.chartSize
    const r = w / 2 - this.thickness / 2 - 2
    c.clearRect(0, 0, w, h)
    // 轨道
    c.lineWidth = this.thickness
    c.lineCap = 'butt'
    c.strokeStyle = Theme.surfaceStrong()
    c.beginPath()
    c.arc(w / 2, h / 2, r, 0, Math.PI * 2)
    c.stroke()
    const total = this.total()
    if (total <= 0) {
      return
    }
    let start = -Math.PI / 2
    for (const seg of this.segments) {
      if (seg.value <= 0) {
        continue
      }
      const angle = seg.value / total * Math.PI * 2
      c.strokeStyle = seg.color
      c.beginPath()
      c.arc(w / 2, h / 2, r, start, start + angle)
      c.stroke()
      start += angle
    }
  }

  build() {
    Stack({ alignContent: Alignment.Center }) {
      Canvas(this.ctx)
        .width(this.chartSize)
        .height(this.chartSize)
        .onReady(() => {
          this.paint()
        })
        .opacity(this.appear)
      Column({ space: 2 }) {
        Text(this.centerValue)
          .fontSize(17)
          .fontWeight(FontWeight.Bold)
          .fontColor(Theme.text())
          .maxLines(1)
        if (this.centerLabel.length > 0) {
          Text(this.centerLabel)
            .fontSize(11)
            .fontColor(Theme.faint())
            .maxLines(1)
        }
      }
    }
    .width(this.chartSize)
    .height(this.chartSize)
  }
}

/** 多序列折线图：Canvas 绘制网格 + 折线，坐标轴文字用布局承载。 */
@Component
export struct TrendLineChart {
  @Prop @Watch('onData') series: TrendSeries[] = []
  @Prop labels: string[] = []
  @Prop chartHeight: number = 190
  @Prop yMaxLabel: string = ''
  @Prop yMidLabel: string = ''
  @State private appear: number = 0
  @State private cw: number = 0
  private settings: RenderingContextSettings = new RenderingContextSettings(true)
  private ctx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings)

  aboutToAppear(): void {
    animateTo({ duration: 380, curve: Curve.EaseOut }, () => {
      this.appear = 1
    })
  }

  onData(): void {
    this.paint()
  }

  private maxVal(): number {
    let m = 1
    for (const s of this.series) {
      for (const v of s.values) {
        if (v > m) {
          m = v
        }
      }
    }
    return m
  }

  private labelAt(index: number): string {
    if (index < 0 || index >= this.labels.length) {
      return ''
    }
    return this.labels[index]
  }

  private paint(): void {
    const c = this.ctx
    const w = this.cw
    const h = this.chartHeight
    if (w <= 0 || h <= 0) {
      return
    }
    const left = 6
    const right = 6
    const top = 8
    const bottom = 14
    const plotW = w - left - right
    const plotH = h - top - bottom
    c.clearRect(0, 0, w, h)
    // 网格
    c.lineWidth = 0.5
    c.strokeStyle = Theme.border()
    for (let i = 0; i <= 3; i++) {
      const y = top + plotH * i / 3
      c.beginPath()
      c.moveTo(left, y)
      c.lineTo(left + plotW, y)
      c.stroke()
    }
    const n = this.labels.length
    if (n < 2) {
      return
    }
    const maxV = this.maxVal()
    for (const s of this.series) {
      if (s.values.length === 0) {
        continue
      }
      c.lineWidth = 2
      c.strokeStyle = s.color
      c.beginPath()
      for (let i = 0; i < n; i++) {
        const v = i < s.values.length ? s.values[i] : 0
        const x = left + plotW * i / (n - 1)
        const y = top + plotH * (1 - v / maxV)
        if (i === 0) {
          c.moveTo(x, y)
        } else {
          c.lineTo(x, y)
        }
      }
      c.stroke()
    }
  }

  build() {
    Column({ space: 6 }) {
      Row({ space: 12 }) {
        ForEach(this.series, (s: TrendSeries) => {
          Row({ space: 4 }) {
            Circle({ width: 7, height: 7 }).fill(s.color)
            Text(s.name)
              .fontSize(11)
              .fontColor(Theme.faint())
              .maxLines(1)
          }
        }, (s: TrendSeries) => s.name)
        Blank()
      }
      .width('100%')

      Row({ space: 6 }) {
        Column() {
          if (this.yMaxLabel.length > 0) {
            Text(this.yMaxLabel).fontSize(9).fontColor(Theme.faint())
          }
          Blank()
          if (this.yMidLabel.length > 0) {
            Text(this.yMidLabel).fontSize(9).fontColor(Theme.faint())
          }
          Blank()
          Text('0').fontSize(9).fontColor(Theme.faint())
        }
        .height(this.chartHeight)
        .alignItems(HorizontalAlign.End)
        .justifyContent(FlexAlign.SpaceBetween)

        Column() {
          Canvas(this.ctx)
            .width('100%')
            .height(this.chartHeight)
            .onReady(() => {
              this.paint()
            })
            .onAreaChange((_old: Area, nw: Area) => {
              this.cw = Number(nw.width)
              this.paint()
            })
            .opacity(this.appear)
          Row() {
            Text(this.labelAt(0)).fontSize(9).fontColor(Theme.faint())
            Blank()
            Text(this.labelAt(Math.floor(this.labels.length / 2)))
              .fontSize(9)
              .fontColor(Theme.faint())
            Blank()
            Text(this.labelAt(this.labels.length - 1)).fontSize(9).fontColor(Theme.faint())
          }
          .width('100%')
          .padding({ left: 2, right: 2 })
        }
        .layoutWeight(1)
      }
      .width('100%')
    }
    .width('100%')
  }
}

/** 模型用量趋势：按天堆叠面积图（每个模型一层），进入淡入。 */
@Component
export struct ModelTrendChart {
  @Prop @Watch('onData') series: TrendSeries[] = []
  @Prop labels: string[] = []
  @Prop chartHeight: number = 150
  @State private appear: number = 0
  @State private cw: number = 0
  private settings: RenderingContextSettings = new RenderingContextSettings(true)
  private ctx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings)

  aboutToAppear(): void {
    animateTo({ duration: 380, curve: Curve.EaseOut }, () => {
      this.appear = 1
    })
  }

  onData(): void {
    this.paint()
  }

  private labelAt(index: number): string {
    if (index < 0 || index >= this.labels.length) {
      return ''
    }
    return this.labels[index]
  }

  private stacked(): number[][] {
    const out: number[][] = []
    const n = this.labels.length
    let base: number[] = []
    for (let i = 0; i < n; i++) {
      base.push(0)
    }
    for (const s of this.series) {
      const next: number[] = []
      for (let i = 0; i < n; i++) {
        const v = i < s.values.length ? s.values[i] : 0
        next.push(base[i] + v)
      }
      out.push(next)
      base = next
    }
    return out
  }

  private paint(): void {
    const c = this.ctx
    const w = this.cw
    const h = this.chartHeight
    const n = this.labels.length
    if (w <= 0 || h <= 0 || n < 2) {
      return
    }
    c.clearRect(0, 0, w, h)
    const stack = this.stacked()
    let maxV = 1
    if (stack.length > 0) {
      const top = stack[stack.length - 1]
      for (const v of top) {
        if (v > maxV) {
          maxV = v
        }
      }
    }
    const topPad = 6
    const plotH = h - topPad
    const xAt = (i: number): number => w * i / (n - 1)
    const yAt = (v: number): number => topPad + plotH * (1 - v / maxV)
    let lower: number[] = []
    for (let i = 0; i < n; i++) {
      lower.push(0)
    }
    for (let k = 0; k < stack.length; k++) {
      const upper = stack[k]
      c.fillStyle = this.series[k].color
      c.globalAlpha = 0.85
      c.beginPath()
      c.moveTo(xAt(0), yAt(upper[0]))
      for (let i = 1; i < n; i++) {
        c.lineTo(xAt(i), yAt(upper[i]))
      }
      for (let i = n - 1; i >= 0; i--) {
        c.lineTo(xAt(i), yAt(lower[i]))
      }
      c.closePath()
      c.fill()
      c.globalAlpha = 1
      lower = upper
    }
  }

  build() {
    Column({ space: 6 }) {
      Flex({ wrap: FlexWrap.Wrap }) {
        ForEach(this.series.slice(0, 8), (s: TrendSeries) => {
          Row({ space: 4 }) {
            Circle({ width: 7, height: 7 }).fill(s.color)
            Text(s.name)
              .fontSize(11)
              .fontColor(Theme.faint())
              .maxLines(1)
              .textOverflow({ overflow: TextOverflow.Ellipsis })
          }
        }, (s: TrendSeries) => s.name)
      }
      .width('100%')

      Column() {
        Canvas(this.ctx)
          .width('100%')
          .height(this.chartHeight)
          .onReady(() => {
            this.paint()
          })
          .onAreaChange((_old: Area, nw: Area) => {
            this.cw = Number(nw.width)
            this.paint()
          })
          .opacity(this.appear)
        Row() {
          Text(this.labelAt(0)).fontSize(9).fontColor(Theme.faint())
          Blank()
          Text(this.labelAt(Math.floor(this.labels.length / 2)))
            .fontSize(9)
            .fontColor(Theme.faint())
          Blank()
          Text(this.labelAt(this.labels.length - 1)).fontSize(9).fontColor(Theme.faint())
        }
        .width('100%')
        .padding({ left: 2, right: 2 })
      }
      .width('100%')
    }
    .width('100%')
  }
}

/** 日历热力图：7 行 × N 周，档位色来自 Theme.heatRamp；底部带"少→多"图例。 */
@Component
export struct CalendarHeatmap {
  @Prop days: HeatDay[] = []
  @Prop ramp: string[] = []
  @Prop cellHeight: number = 11
  @Prop maxValue: number = 0

  private paddedDays(): HeatDay[] {
    const out: HeatDay[] = []
    if (this.days.length === 0) {
      return out
    }
    const first = this.days[0].date
    const d = new Date(`${first}T00:00:00`)
    let lead = d.getDay() - 1
    if (lead < 0) {
      lead = 6
    }
    for (let i = 0; i < lead; i++) {
      out.push({ date: '', value: 0, requests: 0, cost: 0 })
    }
    for (const day of this.days) {
      out.push(day)
    }
    return out
  }

  private weeks(): HeatDay[][] {
    const padded = this.paddedDays()
    const out: HeatDay[][] = []
    let week: HeatDay[] = []
    for (const day of padded) {
      week.push(day)
      if (week.length === 7) {
        out.push(week)
        week = []
      }
    }
    if (week.length > 0) {
      while (week.length < 7) {
        week.push({ date: '', value: 0, requests: 0, cost: 0 })
      }
      out.push(week)
    }
    return out
  }

  private maxOf(): number {
    if (this.maxValue > 0) {
      return this.maxValue
    }
    let m = 1
    for (const d of this.days) {
      if (d.value > m) {
        m = d.value
      }
    }
    return m
  }

  private level(v: number): number {
    if (v <= 0) {
      return 0
    }
    const ratio = v / this.maxOf()
    if (ratio >= 0.75) {
      return 4
    }
    if (ratio >= 0.5) {
      return 3
    }
    if (ratio >= 0.25) {
      return 2
    }
    return 1
  }

  private cellColor(v: number): string {
    const ramp = this.ramp.length > 0 ? this.ramp : Theme.heatRamp()
    const lv = this.level(v)
    return lv === 0 ? Theme.surfaceSoft() : ramp[lv - 1]
  }

  build() {
    Column({ space: 6 }) {
      Row({ space: 2 }) {
        ForEach(this.weeks(), (week: HeatDay[], wi: number) => {
          Column({ space: 2 }) {
            ForEach(week, (day: HeatDay, di: number) => {
              Column()
                .width('100%')
                .height(this.cellHeight)
                .backgroundColor(this.cellColor(day.value))
                .borderRadius(2)
            }, (day: HeatDay, di: number) => `h_${wi}_${di}_${day.date}`)
          }
          .layoutWeight(1)
        }, (week: HeatDay[], wi: number) => `w_${wi}`)
      }
      .width('100%')

      Row({ space: 4 }) {
        Text(I18n.t('fewer')).fontSize(9).fontColor(Theme.faint())
        ForEach([0, 1, 2, 3, 4], (lv: number) => {
          Column()
            .width(9)
            .height(9)
            .backgroundColor(lv === 0 ? Theme.surfaceSoft() : (this.ramp.length > 0 ? this.ramp : Theme.heatRamp())[lv - 1])
            .borderRadius(2)
        }, (lv: number) => `lg_${lv}`)
        Text(I18n.t('more')).fontSize(9).fontColor(Theme.faint())
        Blank()
      }
      .width('100%')
    }
    .width('100%')
  }
}
