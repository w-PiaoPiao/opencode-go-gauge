/**
 * 内置 WebView 登录页 —— auth.py / android LoginScreen 的 ArkTS 移植。
 * 加载官方授权页, 登录完成后页面落到 opencode.ai 域, 用 WebCookieManager
 * 读取 HttpOnly 的 auth cookie, 解析工作区 hint, 落库账号后返回。
 */
import webview from '@ohos.web.webview'
import router from '@ohos.router'
import { Login } from '../common/auth/Login'
import { Repo } from '../data/repository/DashboardRepository'

const POLL_INTERVAL_MS = 1000

@Entry
@Component
struct LoginPage {
  controller: webview.WebviewController = new webview.WebviewController()
  private pollTimer: number = -1
  private currentUrl: string = ''
  @State private src: string = Login.buildLoginUrl()
  @State private statusText: string = '正在加载授权页…'
  @State private captured: boolean = false

  aboutToDisappear(): void {
    this.stopPolling()
  }

  build() {
    Column() {
      Row() {
        Button('‹ 返回')
          .fontSize(14)
          .backgroundColor('#00000000')
          .fontColor('#1E88E5')
          .onClick(() => {
            router.back()
          })
        Blank()
        Text('OpenCode Go 登录')
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
        Blank()
        Text('　')
          .fontSize(16)
      }
      .width('100%')
      .padding({ left: 8, right: 8, top: 8, bottom: 8 })

      Text(this.statusText)
        .fontSize(13)
        .fontColor(this.captured ? '#2E7D32' : '#888888')
        .padding(8)

      Web({ src: this.src, controller: this.controller })
        .width('100%')
        .layoutWeight(1)
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
    .height('100%')
    .backgroundColor('#FFFFFF')
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
    try {
      await Repo.get().loginSuccess(segment, hint, 'add')
      this.statusText = '登录成功，正在进入仪表盘…'
      setTimeout(() => {
        router.back()
      }, 600)
    } catch (e) {
      this.statusText = `登录失败: ${(e as Error).message}`
      this.captured = false
    }
  }
}