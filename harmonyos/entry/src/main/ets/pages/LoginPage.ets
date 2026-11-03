/**
 * 内置 WebView 登录页 —— auth.py / android LoginScreen 的 ArkTS 移植。
 * 加载官方授权页, 登录完成后页面落到 opencode.ai 域, 用 WebCookieManager
 * 读取 HttpOnly 的 auth cookie, 解析工作区 hint, 落库账号后返回。
 */
import webview from '@ohos.web.webview'
import router from '@ohos.router'
import { Login } from '../common/auth/Login'
import { Repo, DashboardRepository } from '../data/repository/DashboardRepository'
import { I18n } from '../common/i18n/I18n'
import { Theme, Dimens } from '../ui/theme/Theme'

const POLL_INTERVAL_MS = 1000

@Entry
@Component
struct LoginPage {
  controller: webview.WebviewController = new webview.WebviewController()
  private pollTimer: number = -1
  private currentUrl: string = ''
  private loginMode: string = 'add'
  @State private src: string = Login.buildLoginUrl()
  @State private statusText: string = I18n.t('loginLoading')
  @State private captured: boolean = false

  aboutToAppear(): void {
    // getParams() 在无参数时返回 undefined（不是 null）：此前的 null 判断会让
    // 取属性直接抛 TypeError → 点「立即登录」闪退（emu-verify 抓到的 jscrash）
    const params = router.getParams() as Record<string, string> | undefined
    if (params !== undefined && params !== null && params['mode'] === 'relogin') {
      this.loginMode = 'relogin'
    } else {
      this.loginMode = 'add'
    }
  }

  aboutToDisappear(): void {
    this.stopPolling()
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
          this.stopPolling()
          router.back()
        })
        Text(I18n.t('loginPageTitle'))
          .fontSize(17)
          .fontFamily('GgSerif')
          .fontColor(Theme.text())
          .maxLines(1)
        Blank()
      }
      .width('100%')
      .height(52)
      .padding({ left: 8, right: 14 })
      .backgroundColor(Theme.surface())
      .border({ width: { bottom: 1 }, color: Theme.border() })

      Row({ space: 8 }) {
        if (!this.captured) {
          LoadingProgress()
            .width(16)
            .height(16)
            .color(Theme.accent())
        } else {
          Image($r('app.media.ic_check'))
            .width(14)
            .height(14)
            .fillColor(Theme.green())
        }
        Text(this.statusText)
          .fontSize(12)
          .fontColor(this.captured ? Theme.green() : Theme.sub())
          .layoutWeight(1)
      }
      .width('100%')
      .padding({ left: 16, right: 16, top: 10, bottom: 10 })
      .backgroundColor(Theme.surfaceSoft())

      Column() {
        Web({ src: this.src, controller: this.controller })
          .width('100%')
          .height('100%')
          .javaScriptAccess(true)
          .domStorageAccess(true)
          .onPageBegin((event) => {
            this.handleUrlChange(event.url)
          })
          .onPageEnd((event) => {
            this.handleUrlChange(event.url)
          })
      }
      .width('100%')
      .layoutWeight(1)
      .margin({ top: 1 })
    }
    .width('100%')
    .height('100%')
    .backgroundColor(Theme.bg())
  }

  private handleUrlChange(url: string): void {
    this.currentUrl = url
    if (Login.isOnOpencodeDomain(url)) {
      this.startPolling()
    } else {
      this.stopPolling()
    }
  }

  private startPolling(): void {
    if (this.pollTimer >= 0) {
      return
    }
    this.pollTimer = setInterval(() => {
      this.tryCapture()
    }, POLL_INTERVAL_MS)
    this.tryCapture()
  }

  private stopPolling(): void {
    if (this.pollTimer >= 0) {
      clearInterval(this.pollTimer)
      this.pollTimer = -1
    }
  }

  private async tryCapture(): Promise<void> {
    if (this.captured) {
      return
    }
    let raw = ''
    try {
      raw = webview.WebCookieManager.fetchCookieSync(Login.OPENCODE_DOMAIN)
    } catch (e) {
      return // cookie 未就绪, 继续轮询
    }
    const segment: string = Login.extractAuthCookie(raw)
    if (segment.length === 0) {
      return
    }
    this.captured = true
    this.stopPolling()
    const hint: string = Login.extractWorkspaceHint(this.currentUrl)
    // 捕获后清掉 WebView 中的会话 cookie (Android LoginScreen 同做法):
    // cookie 已落入账号表, 无需继续留在应用持久化 Web 数据里
    await DashboardRepository.clearWebCookies()
    try {
      await Repo.get().loginSuccess(segment, hint, this.loginMode)
      this.statusText = I18n.t('login_success')
      setTimeout(() => {
        router.back()
      }, 600)
    } catch (e) {
      this.statusText = `${I18n.t('login_failed')}: ${(e as Error).message}`
      this.captured = false
    }
  }
}