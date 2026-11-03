/**
 * 应用内隐私政策页 —— AppGallery 合规要求：应用内可点击查看隐私政策。
 * 正文与 docs/release/privacy-policy-zh.md / -en.md 保持一致（PrivacyText.ets）。
 */
import router from '@ohos.router'
import { AppPrefs } from '../common/store/AppPrefs'
import { I18n } from '../common/i18n/I18n'
import { PrivacySection, PrivacyText } from '../common/legal/PrivacyText'
import { Theme, Dimens } from '../ui/theme/Theme'
import { AppVersion } from '../common/AppVersion'

@Entry
@Component
struct PrivacyPage {
  @State private lang: string = 'zh'

  aboutToAppear(): void {
    this.lang = AppPrefs.getLanguage()
  }

  build() {
    Column() {
      Row({ space: 6 }) {
        Row() {
          Image($r('app.media.ic_arrow_back'))
            .width(22)
            .height(22)
            .fillColor(Theme.text())
        }
        .width(Dimens.TOUCH_MIN)
        .height(Dimens.TOUCH_MIN)
        .justifyContent(FlexAlign.Center)
        .hoverEffect(HoverEffect.Highlight)
        .onClick(() => {
          router.back()
        })
        Text(I18n.t('privacyTitle'))
          .fontSize(18)
          .fontFamily('GgSerif')
          .fontColor(Theme.text())
        Blank()
      }
      .width('100%')
      .height(52)
      .padding({ left: 8, right: 14 })
      .backgroundColor(Theme.surface())
      .border({ width: { bottom: 1 }, color: Theme.border() })

      Scroll() {
        Column({ space: 18 }) {
          Text(`GoGauge · HarmonyOS NEXT ${AppVersion.versionName()}`)
            .fontSize(11)
            .fontColor(Theme.faint())
            .width('100%')
          ForEach(PrivacyText.sections(this.lang), (sec: PrivacySection) => {
            Column({ space: 6 }) {
              Text(sec.title)
                .fontSize(15)
                .fontFamily('GgSerif')
                .fontColor(Theme.text())
                .width('100%')
              Text(sec.body)
                .fontSize(13)
                .lineHeight(21)
                .fontColor(Theme.sub())
                .width('100%')
            }
            .width('100%')
            .alignItems(HorizontalAlign.Start)
          }, (sec: PrivacySection) => sec.title)
        }
        .width('100%')
        .padding({
          left: Dimens.PAGE_H_WIDE,
          right: Dimens.PAGE_H_WIDE,
          top: 16,
          bottom: 32,
        })
      }
      .layoutWeight(1)
      .width('100%')
      .scrollBar(BarState.Off)
      .edgeEffect(EdgeEffect.Spring)
    }
    .width('100%')
    .height('100%')
    .backgroundColor(Theme.bg())
  }
}
