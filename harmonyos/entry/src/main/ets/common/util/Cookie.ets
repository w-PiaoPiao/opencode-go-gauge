/**
 * Cookie 头处理工具 —— 登录侧提取 auth cookie 与 API 侧构造 Cookie 头的公共逻辑。
 *
 * 两处 (Login.extractAuthCookie / OpenCodeApi.buildCookieHeader) 都做同一件事:
 * 剥离可选的 "cookie:" 前缀, 再按 ';' 找出 `name=` 段。统一到此, 避免实现漂移。
 */
export class Cookie {
  /** 剥离可选的 "cookie:" 前缀并 trim (大小写不敏感)。 */
  static stripPrefix(raw: string): string {
    let cookie = raw.trim()
    if (cookie.toLowerCase().startsWith('cookie:')) {
      cookie = cookie.slice(7).trim()
    }
    return cookie
  }

  /** 从 cookie 串中找出 `<name>=<value>` 段; 找不到返回 ''。 */
  static findSegment(raw: string, name: string): string {
    const cookie = Cookie.stripPrefix(raw)
    for (const part of cookie.split(';')) {
      const p = part.trim()
      if (p.startsWith(`${name}=`)) {
        return p
      }
    }
    return ''
  }
}
