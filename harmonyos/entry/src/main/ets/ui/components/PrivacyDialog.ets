/**
 * 首次启动隐私政策弹窗（合规：AppGallery 7.1 / 7.5）。
 *
 * 与 AlertDialog 的区别：弹窗内必须能点开完整《隐私政策》（否则审核会认为
 * 用户只能"拒绝"后才能查看政策）；同意/拒绝都是显式按钮，不默认勾选。
 */
import router from '@ohos.router'
import { I18n } from '../../common/i18n/I18n'
import { PrivacyText } from '../../common/legal/PrivacyText'
import { Theme, Dimens } from '../theme/Theme'

@CustomDialog
export struct PrivacyDialog {
  controller: CustomDialogController
  @Prop lang: string = 'zh'
  onAgree: () => void = () => {
  }
  onDecline: () => void = () => {
  }

  private openPolicy(): void {
    this.controller.close()
    router.pushUrl({ url: 'pages/PrivacyPage' })
  }

  build() {
    Column({ space: 14 }) {
      Text(I18n.t('privacyTitle'))
        .fontSize(19)
        .fontFamily('GgSerif')
        .fontColor(Theme.text())
        .width('100%')
        .textAlign(TextAlign.Center)

      Scroll() {
        Text(PrivacyText.summary(this.lang))
          .fontSize(13)
          .lineHeight(21)
          .fontColor(Theme.sub())
          .width('100%')
      }
      .width('100%')
      .constraintSize({ maxHeight: 240 })
      .scrollBar(BarState.Off)
      .edgeEffect(EdgeEffect.Spring)

      Text(I18n.t('privacyEntry'))
        .fontSize(13)
        .fontColor(Theme.accent())
        .decoration({ type: TextDecorationType.Underline, color: Theme.accent() })
        .onClick(() => {
          this.openPolicy()
        })

      Row({ space: 10 }) {
        Text(I18n.t('privacyDecline'))
          .fontSize(14)
          .fontColor(Theme.sub())
          .height(44)
          .layoutWeight(1)
          .textAlign(TextAlign.Center)
          .borderRadius(Dimens.TILE_RADIUS)
          .backgroundColor(Theme.surfaceSoft())
          .onClick(() => {
            this.controller.close()
            this.onDecline()
          })
        Text(I18n.t('privacyAgree'))
          .fontSize(14)
          .fontColor(Theme.onAccent())
          .height(44)
          .layoutWeight(1)
          .textAlign(TextAlign.Center)
          .borderRadius(Dimens.TILE_RADIUS)
          .backgroundColor(Theme.accent())
          .onClick(() => {
            this.controller.close()
            this.onAgree()
          })
      }
      .width('100%')
    }
    .width('100%')
    .padding(20)
    .backgroundColor(Theme.surface())
    .borderRadius(Dimens.CARD_RADIUS)
  }
}
