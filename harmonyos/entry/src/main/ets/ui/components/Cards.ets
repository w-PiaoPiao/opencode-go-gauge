/** 通用卡片组件 —— Compose Cards 的 ArkUI 移植。 */
import { Fmt } from '../../common/util/Fmt'

/** 区块容器: 标题 + 内容区 (由 @BuilderParam content 注入)。 */
@Component
export struct SectionCard {
  @Prop title: string = ''
  @Prop subtitle: string = ''
  @BuilderParam content: () => void

  build() {
    Column({ space: 10 }) {
      Row() {
        Text(this.title)
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor('#222222')
        Blank()
        if (this.subtitle.length > 0) {
          Text(this.subtitle)
            .fontSize(11)
            .fontColor('#999999')
        }
      }
      .width('100%')

      Column() {
        this.content()
      }
      .width('100%')
    }
    .width('100%')
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(14)
    .shadow({ radius: 8, color: '#11000000', offsetY: 2 })
  }
}

/** KPI 卡片: 数值 + 标签 (+ 可选辅助说明)。 */
@Component
export struct KpiCard {
  @Prop label: string = ''
  @Prop value: string = ''
  @Prop hint: string = ''
  @Prop accent: string = '#333333'

  build() {
    Column({ space: 4 }) {
      Text(this.value)
        .fontSize(18)
        .fontWeight(FontWeight.Bold)
        .fontColor(this.accent)
        .maxLines(1)
      Text(this.label)
        .fontSize(12)
        .fontColor('#666666')
      if (this.hint.length > 0) {
        Text(this.hint)
          .fontSize(10)
          .fontColor('#AAAAAA')
          .maxLines(1)
      }
    }
    .width('100%')
    .padding(10)
    .backgroundColor('#F8F9FC')
    .borderRadius(10)
    .alignItems(HorizontalAlign.Start)
  }
}

/** 模型图标 (首字母圆块, 品牌色映射)。 */
@Component
export struct ModelIcon {
  @Prop model: string = ''
  private static hueMap: Array<[string, string]> = [
    ['gpt', '#10A37F'], ['deepseek', '#4D6BFE'], ['qwen', '#615CED'], ['glm', '#0EA5E9'],
    ['kimi', '#000000'], ['grok', '#7C3AED'], ['claude', '#D97757'], ['gemini', '#4285F4'],
    ['meta', '#0866FF'], ['llama', '#0369A1'], ['mistral', '#F97316'], ['minimax', '#14B8A6'],
  ]

  build() {
    Text(this.initials())
      .fontSize(12)
      .fontColor('#FFFFFF')
      .width(26)
      .height(26)
      .textAlign(TextAlign.Center)
      .borderRadius(7)
      .backgroundColor(this.color())
  }

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
}

/** 价格格式化快捷入口 (页面内复用)。 */
export function fmtMoneyUsd(usd: number, currency: string, usdCny: number): string {
  return Fmt.money(usd, currency, usdCny)
}