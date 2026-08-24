/**
 * HTTP 封装 —— OkHttpClient 的角色 (android OpenCodeApi.defaultClient 移植)。
 * 超时/UA/重试策略与 Android 对齐; 返回响应体文本。
 */
import { http } from '@kit.NetworkKit'

export class HttpError extends Error {
  code: number
  constructor(message: string, code: number = 0) {
    super(message)
    this.code = code
  }
}

/** 认证失败 (401/403) —— token 失效或过期。 */
export class AuthHttpError extends HttpError {
}

export class HttpFetch {
  static readonly USER_AGENT =
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/148.0'
  static readonly MAX_BODY_BYTES = 4 * 1024 * 1024
  static readonly CONNECT_TIMEOUT_MS = 10_000
  static readonly READ_TIMEOUT_MS = 15_000
  static readonly RETRY_BACKOFF_MS: number[] = [500, 1500, 3000]

  /**
   * GET 请求, 自动重试, 返回响应体文本 (截断到 MAX_BODY_BYTES)。
   * 401/403 -> AuthHttpError; 404 -> HttpError("工作区不存在 (HTTP 404)");
   * 其他非 2xx -> HttpError("请求返回 HTTP <code>"); 网络错误重试耗尽后抛出。
   */
  static async fetch(url: string, headers: Record<string, string>, retries: number = 2): Promise<string> {
    let lastErr: Error | null = null
    for (let attempt = 0; attempt < retries; attempt++) {
      const req = http.createHttp()
      try {
        const resp = await req.request(url, {
          method: http.RequestMethod.GET,
          header: headers,
          expectDataType: http.HttpDataType.STRING,
          connectTimeout: HttpFetch.CONNECT_TIMEOUT_MS,
          readTimeout: HttpFetch.READ_TIMEOUT_MS,
          usingCache: false,
        })
        const status: number = resp.responseCode as number
        let body = ''
        if (typeof resp.result === 'string') {
          body = resp.result.substring(0, HttpFetch.MAX_BODY_BYTES)
        }
        if (status === 401 || status === 403) {
          throw new AuthHttpError(`认证失败 (HTTP ${status})，请重新登录`, status)
        }
        if (status === 404) {
          throw new HttpError('工作区不存在 (HTTP 404)', 404)
        }
        if (status < 200 || status > 299) {
          throw new HttpError(`请求返回 HTTP ${status}`, status)
        }
        return body
      } catch (e) {
        if (e instanceof HttpError) {
          throw e // 业务错误不重试
        }
        lastErr = (e as Error)
        if (attempt < retries - 1) {
          await HttpFetch.sleep(HttpFetch.RETRY_BACKOFF_MS[Math.min(attempt, HttpFetch.RETRY_BACKOFF_MS.length - 1)])
        }
      } finally {
        req.destroy()
      }
    }
    throw new HttpError(`网络错误: ${lastErr?.message ?? '未知'}`, 0)
  }

  static async sleep(ms: number): Promise<void> {
    await new Promise<void>((resolve) => {
      setTimeout(() => { resolve() }, ms)
    })
  }
}