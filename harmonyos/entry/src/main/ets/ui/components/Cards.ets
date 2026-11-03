/**
 * 通用卡片 / 数据格 / 胶囊 / 空态组件 —— 安卓版 Components.kt 的 ArkUI 移植 + 鸿蒙动效。
 *
 * 只允许使用 Theme 令牌；组件不读 Repo/DB，数据全部由页面传入。
 * 布局兼容手机（宽 <600vp）与宽屏（平板/PC），由调用方传入 columns 或由 GridRow 断点决定。
 */
import { Theme, Dimens, FONT_SERIF } from '../theme/Theme'

/** 胶囊 / 分段控件的选项。 */
export interface Option {
  value: string
  label: string
}

/** 编辑式数据格。 */
export interface EditorialCell {
  label: string
  value: string
  sub: string
  accent: string
}

/**
 * 卡容器：surface + 发丝线 + 圆角；可选卡头条（标题/说明）。
 *
 * ⚠️ ArkUI 运行时约束（v1.0 实测踩坑）：@BuilderParam 传来的 @Builder 会在子组件内
 * 被 `bind(子组件this)` 调用，因此**不要用 `content: this.xxxBuilder` 传值**——builder
 * 体内的 `this.xxx` 会取不到父组件成员（表现为 "xxx is not callable" jscrash）。
 * 正确写法：用**尾随闭包**（编译期捕获父组件 this），或在闭包内调用父组件 @Builder：
 *
 *   GgCard({ title: 'x' }) { this.someContentBuilder() }
 *
 * 需要卡头右侧控件的卡片：GgCard 只传 hint，内容里用 CardHeader 的尾随闭包：
 *
 *   GgCard({}) {
 *     Column() {
 *       CardHeader({ title: 'x' }) { this.trailingBuilder() }
 *       this.someContentBuilder()
 *     }
 *   }
 */
@Component
export struct GgCard {
  @Prop title: string = ''
  @Prop hint: string = ''
  @Prop dense: boolean = false
  @BuilderParam content: () => void = this.emptyContent

  @Builder
  emptyContent() {
  }

  build() {
    Column() {
      if (this.title.length > 0 || this.hint.length > 0) {
        Row({ space: 8 }) {
          Text(this.title)
            .fontSize(15)
            .fontFamily(FONT_SERIF)
            .fontColor(Theme.text())
            .maxLines(1)
          Blank()
          if (this.hint.length > 0) {
            Text(this.hint)
              .fontSize(11)
              .fontColor(Theme.faint())
              .maxLines(1)
          }
        }
        .width('100%')
        .padding({ bottom: this.dense ? 6 : 8 })
      }
      Column() {
        this.content()
      }
      .width('100%')
    }
    .width('100%')
    .padding(this.dense ? 12 : Dimens.CARD_PAD)
    .backgroundColor(Theme.surface())
    .borderRadius(Dimens.CARD_RADIUS)
    .border({ width: 1, color: Theme.border() })
    .shadow(Theme.cardShadow())
  }
}

/** 卡头（独立使用：放进已有容器/自定义布局）。 */
@Component
export struct CardHeader {
  @Prop title: string = ''
  @Prop hint: string = ''
  @BuilderParam trailing: () => void = this.emptyTrailing

  @Builder
  emptyTrailing() {
  }

  build() {
    Row({ space: 8 }) {
      Text(this.title)
        .fontSize(15)
        .fontFamily(FONT_SERIF)
        .fontColor(Theme.text())
        .maxLines(1)
      if (this.hint.length > 0) {
        Text(this.hint)
          .fontSize(11)
          .fontColor(Theme.faint())
          .maxLines(1)
      }
      Blank()
      this.trailing()
    }
    .width('100%')
  }
}

/** 次级说明文字。 */
@Component
export struct Hint {
  @Prop text: string = ''

  build() {
    Text(this.text)
      .fontSize(11)
      .fontColor(Theme.faint())
      .maxLines(1)
  }
}

/** KPI 卡：顶部语义色条 + caption 标签 + 大数值 + 辅助说明（桌面版 kpi 卡语言）。 */
@Component
export struct KpiCard {
  @Prop label: string = ''
  @Prop value: string = ''
  @Prop sub: string = ''
  @Prop accent: string = Theme.accent()

  build() {
    Column() {
      Column()
        .width('100%')
        .height(3)
        .backgroundColor(this.accent)
      Column({ space: 2 }) {
        Text(this.label)
          .fontSize(11)
          .fontColor(Theme.faint())
          .maxLines(1)
        Text(this.value)
          .fontSize(22)
          .fontWeight(FontWeight.Bold)
          .fontColor(this.accent)
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
        if (this.sub.length > 0) {
          Text(this.sub)
            .fontSize(11)
            .fontColor(Theme.sub())
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
      .padding({ left: 12, right: 10, top: 9, bottom: 9 })
    }
    .width('100%')
    .backgroundColor(Theme.surface())
    .borderRadius(Dimens.CARD_RADIUS)
    .border({ width: 1, color: Theme.border() })
    .clip(true)
    .shadow(Theme.cardShadow())
  }
}

/**
 * 编辑式数据网格：瓷砖 + 语义色点 + 墨色数值。
 * columns: 手机 2；宽屏 3（首页概览）或 6（统计构成）。
 */
@Component
export struct EditorialGrid {
  @Prop cells: EditorialCell[] = []
  @Prop columns: number = 2

  private rows(): Array<EditorialCell[]> {
    const out: Array<EditorialCell[]> = []
    const cols = this.columns > 0 ? this.columns : 2
    let row: EditorialCell[] = []
    for (let i = 0; i < this.cells.length; i++) {
      row.push(this.cells[i])
      if (row.length === cols) {
        out.push(row)
        row = []
      }
    }
    if (row.length > 0) {
      out.push(row)
    }
    return out
  }

  build() {
    Column({ space: 8 }) {
      ForEach(this.rows(), (row: EditorialCell[], ri: number) => {
        Row({ space: 8 }) {
          ForEach(row, (cell: EditorialCell, ci: number) => {
            Column({ space: 3 }) {
              Row({ space: 5 }) {
                Circle({ width: 5, height: 5 }).fill(cell.accent)
                Text(cell.label)
                  .fontSize(11)
                  .fontColor(Theme.faint())
                  .maxLines(1)
              }
              Text(cell.value)
                .fontSize(17)
                .fontWeight(FontWeight.Bold)
                .fontColor(Theme.text())
                .maxLines(1)
                .textOverflow({ overflow: TextOverflow.Ellipsis })
              if (cell.sub.length > 0) {
                Text(cell.sub)
                  .fontSize(11)
                  .lineHeight(15)
                  .fontColor(Theme.sub())
                  .maxLines(2)
                  .textOverflow({ overflow: TextOverflow.Ellipsis })
              }
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Start)
            .padding({ left: 12, right: 8, top: 9, bottom: 9 })
            .backgroundColor(Theme.surfaceSoft())
            .borderRadius(Dimens.TILE_RADIUS)
          }, (cell: EditorialCell, ci: number) => `c${this.columns}_${ri}_${ci}_${cell.label}`)
        }
        .width('100%')
        // ⚠️ key 必须包含列数：仅用 row_${ri} 时，窗口缩放导致列数变化（3→6）会残留
        // 已删除的旧行（实测「用量概览」出现 9 格，切 tab 重建才消失）
      }, (row: EditorialCell[], ri: number) => `row_${this.columns}_${ri}`)
    }
    .width('100%')
  }
}

/** 配额窗口卡：顶部渐变条 + 细进度条 + 剩余/重置/预测（安卓 QuotaCard 语言）。 */
@Component
export struct QuotaCard {
  @Prop label: string = ''
  @Prop @Watch('onUsedPercent') usedPercent: number = 0
  @Prop remainingText: string = ''
  @Prop resetText: string = ''
  @Prop accent: string = Theme.accent()
  @Prop accentEnd: string = Theme.accent()
  @Prop forecastText: string = ''
  @Prop usedLabel: string = ''
  @State private fill: number = 0

  aboutToAppear(): void {
    this.animateFill()
  }

  onUsedPercent(): void {
    this.animateFill()
  }

  private animateFill(): void {
    animateTo({ duration: 450, curve: Curve.EaseOut }, () => {
      this.fill = Math.max(0, Math.min(100, this.usedPercent))
    })
  }

  build() {
    Column() {
      Column()
        .width('100%')
        .height(3)
        .linearGradient({ angle: 90, colors: [[this.accent, 0.0], [this.accentEnd, 1.0]] })
      Column({ space: 8 }) {
        Row() {
          Text(this.label)
            .fontSize(13)
            .fontColor(Theme.sub())
            .maxLines(1)
          Blank()
          Text(this.remainingText)
            .fontSize(15)
            .fontWeight(FontWeight.Bold)
            .fontColor(Theme.text())
            .maxLines(1)
        }
        .width('100%')

        Row() {
          Column()
            .width(`${this.fill}%`)
            .height('100%')
            .linearGradient({ angle: 90, colors: [[this.accent, 0.0], [this.accentEnd, 1.0]] })
        }
        .width('100%')
        .height(8)
        .backgroundColor(Theme.surfaceStrong())
        .borderRadius(4)
        .alignItems(VerticalAlign.Center)

        Row() {
          Row({ space: 4 }) {
            Text(this.usedLabel)
              .fontSize(11)
              .fontColor(Theme.faint())
              .maxLines(1)
            if (this.forecastText.length > 0) {
              Text(this.forecastText)
                .fontSize(11)
                .fontColor(this.accent)
                .maxLines(1)
                .textOverflow({ overflow: TextOverflow.Ellipsis })
                .layoutWeight(1)
            }
          }
          .layoutWeight(1)

          Text(this.resetText)
            .fontSize(11)
            .fontColor(Theme.faint())
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
        }
        .width('100%')
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
      .padding(Dimens.CARD_PAD)
    }
    .width('100%')
    .backgroundColor(Theme.surface())
    .borderRadius(Dimens.CARD_RADIUS)
    .border({ width: 1, color: Theme.border() })
    .clip(true)
    .shadow(Theme.cardShadow())
  }
}

/** 周期胶囊行：容器强瓷砖 + 选中项暖白卡（安卓 PillRow 语言）。 */
@Component
export struct PillRow {
  @Prop options: Option[] = []
  @Prop selected: string = ''
  onSelect: (value: string) => void = () => {
  }

  build() {
    Scroll() {
      Row({ space: 4 }) {
        ForEach(this.options, (opt: Option) => {
          Text(opt.label)
            .fontSize(12)
            .fontWeight(this.selected === opt.value ? FontWeight.Medium : FontWeight.Normal)
            .fontColor(this.selected === opt.value ? Theme.accent() : Theme.sub())
            .padding({ left: 12, right: 12, top: 8, bottom: 8 })
            .backgroundColor(this.selected === opt.value ? Theme.surface() : '#00000000')
            .borderRadius(7)
            .shadow(this.selected === opt.value
              ? { radius: 3, color: '#14000000', offsetX: 0, offsetY: 1 }
              : { radius: 0, color: '#00000000', offsetX: 0, offsetY: 0 })
            .hoverEffect(HoverEffect.Highlight)
            .onClick(() => {
              this.onSelect(opt.value)
            })
        }, (opt: Option) => opt.value)
      }
      .padding(3)
      .backgroundColor(Theme.surfaceStrong())
      .borderRadius(9)
    }
    .scrollable(ScrollDirection.Horizontal)
    .scrollBar(BarState.Off)
  }
}

/** 卡内紧凑分段控件（输入/输出/成本、口径切换等）。 */
@Component
export struct SegButtons {
  @Prop options: Option[] = []
  @Prop selected: string = ''
  onSelect: (value: string) => void = () => {
  }

  build() {
    Row({ space: 2 }) {
      ForEach(this.options, (opt: Option) => {
        Text(opt.label)
          .fontSize(12)
          .fontWeight(this.selected === opt.value ? FontWeight.Medium : FontWeight.Normal)
          .fontColor(this.selected === opt.value ? Theme.accent() : Theme.sub())
          .padding({ left: 10, right: 10, top: 6, bottom: 6 })
          .backgroundColor(this.selected === opt.value ? Theme.surface() : '#00000000')
          .borderRadius(6)
          .hoverEffect(HoverEffect.Highlight)
          .onClick(() => {
            this.onSelect(opt.value)
          })
      }, (opt: Option) => opt.value)
    }
    .padding(2)
    .backgroundColor(Theme.surfaceStrong())
    .borderRadius(8)
  }
}

/** 账号胶囊（手机页头）：当前账号名 + 已登录数徽标。 */
@Component
export struct AccountChip {
  @Prop name: string = ''
  @Prop count: number = 0
  onTap: () => void = () => {
  }
  @State private hovered: boolean = false

  build() {
    Row({ space: 4 }) {
      Text(this.name.length > 0 ? this.name : '—')
        .fontSize(12)
        .fontWeight(FontWeight.Medium)
        .fontColor(Theme.text())
        .maxLines(1)
        .textOverflow({ overflow: TextOverflow.Ellipsis })
        .constraintSize({ maxWidth: 120 })
      if (this.count > 1) {
        Text(String(this.count))
          .fontSize(10)
          .fontColor(Theme.sub())
          .padding({ left: 4, right: 4 })
          .backgroundColor(Theme.surfaceSoft())
          .borderRadius(6)
      }
    }
    .padding({ left: 10, right: 10, top: 5, bottom: 5 })
    .backgroundColor(this.hovered ? Theme.surfaceSoft() : Theme.surfaceStrong())
    .borderRadius(99)
    .hoverEffect(HoverEffect.Highlight)
    .onHover((isHover: boolean) => {
      this.hovered = isHover
    })
    .onClick(() => {
      this.onTap()
    })
  }
}

/** 模型图标：首字母圆角块 + 品牌色映射（安卓 ModelIcons 移植）。 */
@Component
export struct ModelIcon {
  @Prop model: string = ''
  @Prop iconSize: number = 26
  private static hueMap: string[][] = [
    ['gpt', '#10A37F'], ['deepseek', '#4D6BFE'], ['qwen', '#615CED'], ['glm', '#0EA5E9'],
    ['kimi', '#000000'], ['grok', '#7C3AED'], ['claude', '#D97757'], ['gemini', '#4285F4'],
    ['meta', '#0866FF'], ['llama', '#0369A1'], ['mistral', '#F97316'], ['minimax', '#14B8A6'],
    ['step', '#8B5CF6'], ['longcat', '#F59E0B'], ['space', '#334155'],
  ]

  private initials(): string {
    const m = this.model.trim()
    if (m.length === 0) {
      return '?'
    }
    if (m.startsWith('gpt-')) {
      return 'GPT'
    }
    const parts = m.split(/[/-]/)
    const seg = parts[0]
    return seg.length > 0 ? seg.slice(0, 2).toUpperCase() : '?'
  }

  private color(): string {
    const m = this.model.toLowerCase()
    for (const pair of ModelIcon.hueMap) {
      if (m.indexOf(pair[0]) >= 0) {
        return pair[1]
      }
    }
    return '#64748B'
  }

  build() {
    Text(this.initials())
      .fontSize(Math.max(9, Math.floor(this.iconSize * 0.42)))
      .fontWeight(FontWeight.Medium)
      .fontColor('#FFFFFF')
      .width(this.iconSize)
      .height(this.iconSize)
      .textAlign(TextAlign.Center)
      .borderRadius(this.iconSize * 0.28)
      .backgroundColor(this.color())
  }
}

/** 居中加载态。 */
@Component
export struct Loader {
  @Prop text: string = ''

  build() {
    Column({ space: 10 }) {
      LoadingProgress()
        .width(36)
        .height(36)
        .color(Theme.accent())
      if (this.text.length > 0) {
        Text(this.text).fontSize(13).fontColor(Theme.sub())
      }
    }
    .width('100%')
    .padding({ top: 60, bottom: 60 })
    .justifyContent(FlexAlign.Center)
  }
}

/** 空态。 */
@Component
export struct EmptyState {
  @Prop text: string = ''

  build() {
    Text(this.text)
      .fontSize(12)
      .fontColor(Theme.faint())
      .width('100%')
      .textAlign(TextAlign.Center)
      .padding({ top: 22, bottom: 22 })
  }
}

/** 配额骨架屏（数据未到）。 */
@Component
export struct QuotaSkeleton {
  build() {
    Column({ space: 10 }) {
      ForEach([0, 1, 2], (i: number) => {
        Column({ space: 10 }) {
          Row() {
            Column().width(88).height(13).backgroundColor(Theme.surfaceSoft()).borderRadius(4)
            Blank()
            Column().width(52).height(13).backgroundColor(Theme.surfaceSoft()).borderRadius(4)
          }
          .width('100%')
          Column().width('100%').height(8).backgroundColor(Theme.surfaceSoft()).borderRadius(4)
        }
        .width('100%')
        .padding(14)
        .backgroundColor(Theme.surface())
        .borderRadius(Dimens.CARD_RADIUS)
        .border({ width: 1, color: Theme.border() })
      }, (i: number) => `sk_${i}`)
    }
    .width('100%')
  }
}

/** 错误卡：原因 + 重试。 */
@Component
export struct ErrorCard {
  @Prop title: string = ''
  @Prop detail: string = ''
  @Prop retryText: string = ''
  onRetry: () => void = () => {
  }

  build() {
    Column({ space: 6 }) {
      Text(`${this.title}：${this.detail}`)
        .fontSize(13)
        .fontColor(Theme.danger())
        .width('100%')
      Row() {
        Text(this.retryText)
          .fontSize(13)
          .fontColor(Theme.accent())
          .onClick(() => {
            this.onRetry()
          })
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
    .padding(14)
    .backgroundColor(Theme.dangerSoft())
    .borderRadius(Dimens.CARD_RADIUS)
    .border({ width: 1, color: Theme.border() })
  }
}

/** 分页器（记录页两表共用）。 */
@Component
export struct Pager {
  @Prop pageInfo: string = ''
  @Prop prevText: string = ''
  @Prop nextText: string = ''
  @Prop hasPrev: boolean = false
  @Prop hasNext: boolean = false
  onPrev: () => void = () => {
  }
  onNext: () => void = () => {
  }

  build() {
    Row({ space: 14 }) {
      Text(this.prevText)
        .fontSize(12)
        .fontColor(this.hasPrev ? Theme.accent() : Theme.faint())
        .padding({ left: 10, right: 10, top: 6, bottom: 6 })
        .borderRadius(6)
        .backgroundColor(this.hasPrev ? Theme.accentSoft() : '#00000000')
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          if (this.hasPrev) {
            this.onPrev()
          }
        })
      Text(this.pageInfo)
        .fontSize(12)
        .fontColor(Theme.faint())
        .maxLines(1)
      Text(this.nextText)
        .fontSize(12)
        .fontColor(this.hasNext ? Theme.accent() : Theme.faint())
        .padding({ left: 10, right: 10, top: 6, bottom: 6 })
        .borderRadius(6)
        .backgroundColor(this.hasNext ? Theme.accentSoft() : '#00000000')
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          if (this.hasNext) {
            this.onNext()
          }
        })
    }
    .width('100%')
    .justifyContent(FlexAlign.Center)
    .padding({ top: 8, bottom: 4 })
  }
}
