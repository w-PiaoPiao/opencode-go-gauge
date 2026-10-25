/**
 * 登录 URL 构造 + 会话 cookie 提取 —— auth.py / android Login.kt 的 ArkTS 移植。
 *
 * 2026-09 opencode.ai 前端改版: 旧授权页 auth.opencode.ai/authorize 已下线, 现由
 * /console 控制台接管登录 (入口 https://opencode.ai/console/login), 会话 cookie 为
 * ``__Host-console_session`` (旧 ``auth`` 保留在候选尾部兼容历史账号)。
 *
 * 流程: Web 组件加载 buildLoginUrl() → 登录完成后页面位于 opencode.ai 域,
 * 轮询 WebCookieManager 读取 HttpOnly 会话 cookie, 并从 URL 提取工作区 hint。
 */
import { Cookie } from '../util/Cookie'

export class Login {
  static readonly CONSOLE_LOGIN_URL: string = 'https://opencode.ai/console/login'
  static readonly LOGIN_NEXT_PATH: string = '/console/'
  // 会话 cookie: 新版 __Host-console_session 优先, 旧版 auth 兼容历史账号
  static readonly AUTH_COOKIE_NAME: string = '__Host-console_session'
  static readonly LEGACY_AUTH_COOKIE_NAME: string = 'auth'
  static readonly OPENCODE_DOMAIN: string = 'https://opencode.ai'

  private static readonly WORKSPACE_URL_RE = new RegExp('/(?:console|workspace)/(wrk_[A-Za-z0-9]+)')

  /** 构造登录入口 URL (opencode: 控制台登录页, next 指向控制台首页)。 */
  static buildLoginUrl(): string {
    return `${Login.CONSOLE_LOGIN_URL}?next=${encodeURIComponent(Login.LOGIN_NEXT_PATH)}`
  }

  /**
   * 按优先级提取会话 cookie 段 (build_cookie_header 的逆操作):
   * 新名 __Host-console_session 必须压过旧名 auth, 否则残留的历史 cookie
   * 会盖掉当前会话。
   */
  static extractAuthCookie(cookieHeader: string): string {
    const next = Cookie.findSegment(cookieHeader, Login.AUTH_COOKIE_NAME)
    if (next.length > 0) {
      return next
    }
    return Cookie.findSegment(cookieHeader, Login.LEGACY_AUTH_COOKIE_NAME)
  }

  /** 从登录页 URL 提取工作区 hint —— _WORKSPACE_URL_RE 移植。 */
  static extractWorkspaceHint(url: string): string {
    if (url.length === 0) {
      return 'Default'
    }
    const m = Login.WORKSPACE_URL_RE.exec(url)
    return m !== null ? m[1] : 'Default'
  }

  /** 页面是否已位于 opencode.ai 域（该域下可读取会话 cookie）。 */
  static isOnOpencodeDomain(url: string): boolean {
    if (url.length === 0) {
      return false
    }
    // 必须先解析 host 再判断: 原先的 url.startsWith('https://opencode.ai')
    // 会把 https://opencode.ai.evil.com/... 当成同域 (前缀匹配), 从而在
    // 非 opencode 页面上启动 cookie 轮询. Android Login.kt 是先取 host 的.
    const host: string = Login.hostOf(url).toLowerCase()
    if (host === 'opencode.ai') {
      return true
    }
    return host.endsWith('.opencode.ai')
  }

  private static hostOf(url: string): string {
    const idx = url.indexOf('://')
    const rest = idx >= 0 ? url.slice(idx + 3) : url
    const slash = rest.indexOf('/')
    const hostPort = slash >= 0 ? rest.slice(0, slash) : rest
    const colon = hostPort.indexOf(':')
    return colon >= 0 ? hostPort.slice(0, colon) : hostPort
  }
}
