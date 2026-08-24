/**
 * 登录 URL 构造 + auth cookie 提取 —— auth.py / android Login.kt 的 ArkTS 移植。
 *
 * 流程: Web 组件加载 buildLoginUrl() → 登录完成后页面位于 opencode.ai 域,
 * 轮询 WebCookieManager 读取 HttpOnly 的 auth cookie, 并从 URL 提取工作区 hint。
 */

export interface LoginResult {
  /** 形如 "auth=<value>" 的 cookie 段, 供构造请求 Cookie 头 */
  cookie: string
  /** 工作区 hint: /workspace/wrk_xxx 或 "Default" */
  workspaceHint: string
}

export class Login {
  static readonly LOGIN_BASE: string = 'https://auth.opencode.ai/authorize'
  static readonly LOGIN_CLIENT_ID: string = 'app'
  static readonly LOGIN_REDIRECT_URI: string = 'https://opencode.ai/auth/callback'
  static readonly AUTH_COOKIE_NAME: string = 'auth'
  static readonly OPENCODE_DOMAIN: string = 'https://opencode.ai'

  private static readonly WORKSPACE_URL_RE = new RegExp('/workspace/(wrk_[A-Za-z0-9]+)')

  /** 构造 OAuth 授权 URL —— auth.build_login_url 移植。 */
  static buildLoginUrl(): string {
    const state: string = `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`
    const params: string = [
      `client_id=${Login.LOGIN_CLIENT_ID}`,
      `redirect_uri=${encodeURIComponent(Login.LOGIN_REDIRECT_URI)}`,
      'response_type=code',
      `state=${state}`,
    ].join('&')
    return `${Login.LOGIN_BASE}?${params}`
  }

  /** 从 cookie 头中提取 "auth=<value>" 段 —— build_cookie_header 的逆操作。 */
  static extractAuthCookie(cookieHeader: string): string {
    let cookie: string = cookieHeader.trim()
    if (cookie.toLowerCase().startsWith('cookie:')) {
      cookie = cookie.slice(7).trim()
    }
    for (const part of cookie.split(';')) {
      const p: string = part.trim()
      if (p.startsWith(`${Login.AUTH_COOKIE_NAME}=`)) {
        return p
      }
    }
    return ''
  }

  /** 从登录页 URL 提取工作区 hint —— _WORKSPACE_URL_RE 移植。 */
  static extractWorkspaceHint(url: string): string {
    if (url.length === 0) {
      return 'Default'
    }
    const m = Login.WORKSPACE_URL_RE.exec(url)
    return m !== null ? m[1] : 'Default'
  }

  /** 页面是否已位于 opencode.ai 域（该域下可读取 auth cookie）。 */
  static isOnOpencodeDomain(url: string): boolean {
    if (url.length === 0) {
      return false
    }
    // 仅做前缀/域名片段判断, 避免 URL 解析差异
    if (url.startsWith(Login.OPENCODE_DOMAIN)) {
      return true
    }
    const prefix = `${Login.OPENCODE_DOMAIN}/`
    if (url.startsWith(prefix)) {
      return true
    }
    const host: string = Login.hostOf(url)
    if (host === 'opencode.ai') {
      return true
    }
    return host.length > 0 && host.endsWith('.opencode.ai')
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