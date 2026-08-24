/**
 * 应用根页面: 未登录 → 欢迎页(立即登录); 已登录 → 进入仪表盘 (M1 先显示登录态占位)。
 */
import router from '@ohos.router'
import { AppPrefs } from '../common/store/AppPrefs'

@Entry
@Component
struct Index {
  @State private loggedIn: boolean = false
  @State private cookiePreview: string = ''

  aboutToAppear(): void {
    AppPrefs.init(getContext(this))
    this.refresh()
  }

  onPageShow(): void {
    this.refresh()
  }

  private refresh(): void {
    const cookie = AppPrefs.getAuthCookie()
    this.loggedIn = cookie.length > 0
    this.cookiePreview = this.loggedIn ? `已登录 (${cookie.slice(0, 14)}… · ws=${AppPrefs.getWorkspaceHint()})` : ''
  }

  build() {
    Column({ space: 14 }) {
      Image($r('app.media.icon'))
        .width(96)
        .height(96)
      Text('GoGauge')
        .fontSize(34)
        .fontWeight(FontWeight.Bold)
      Text('OpenCode Go 用量仪表盘 · HarmonyOS NEXT')
        .fontSize(15)
        .fontColor('#888888')

      Blank()

      Text(this.loggedIn ? this.cookiePreview : '未登录，登录后开始同步用量数据')
        .fontSize(13)
        .fontColor('#666666')

      Button(this.loggedIn ? '重新登录' : '立即登录')
        .width(220)
        .height(44)
        .onClick(() => {
          router.pushUrl({ url: 'pages/LoginPage' })
        })

      if (this.loggedIn) {
        Button('退出登录')
          .width(220)
          .height(40)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .onClick(() => {
            AppPrefs.clearAuth()
            this.refresh()
          })
      }

      Blank()
    }
    .width('100%')
    .height('100%')
    .padding(24)
    .justifyContent(FlexAlign.Center)
    .backgroundColor('#FAFAFC')
  }
}