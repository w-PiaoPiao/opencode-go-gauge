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
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:148.0) Gecko/20100101 Firefox/148.0'
  static readonly MAX_BODY_BYTES = 4 * 1024 * 1024
  static readonly CONNECT_TIMEOUT_MS = 10_000
  static readonly READ_TIMEOUT_MS = 15_000
  static readonly RETRY_BACKOFF_MS: number[] = [500, 1500, 3000]

  /**
   * GET 请求, 自动重试, 返回响应体文本。
   * 401/403 -> AuthHttpError; 404 -> HttpError("工作区不存在 (HTTP 404)");
   * 其他非 2xx -> HttpError("请求返回 HTTP <code>"); 网络错误重试耗尽后抛出;
   * 响应体超过 MAX_BODY_BYTES -> HttpError("响应过大"), 不静默截断。
   *
   * 说明: ArkTS 的 http 模块只提供 STRING 形式的整体响应, 无法像
   * OkHttp 那样流式读取, 因此无法阻止解码本身占内存; 但可以在解码后明确
   * 判定超限并报错 —— 原实现用 substring 静默截断, 会把半截响应当成
   * 成功结果解析 (桌面 Content-Length 预检 / Android readBounded 都是报错)。
   * 先用 Content-Length 预检, 可在解出内容前挡掉声明过大的响应。
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
        // 声明长度预检 (桌面 opencode_api.py 同做法)
        const declared: number = HttpFetch.declaredLength(resp)
        if (declared > HttpFetch.MAX_BODY_BYTES) {
          throw new HttpError(`响应过大 (声明 ${declared} 字节, 上限 ${HttpFetch.MAX_BODY_BYTES})`, status)
        }
        let body = ''
        if (typeof resp.result === 'string') {
          // ArkTS 字符串按 UTF-16 码元计, 与字节数不是同一量纲 —— 这里作为
          // 上界判定 (码元数 >= 字节数的 1/2), 超过即认为响应异常大
          if (resp.result.length > HttpFetch.MAX_BODY_BYTES) {
            throw new HttpError(
              `响应过大 (${resp.result.length} 码元, 上限 ${HttpFetch.MAX_BODY_BYTES})`, status,
            )
          }
          body = resp.result
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

  /** 从响应头取 Content-Length; 缺失/非数字返回 0 (视为未知)。 */
  private static declaredLength(resp: http.HttpResponse): number {
    try {
      const result: Object = resp.result as Object
      void result
      const header: Object | undefined = resp.header as Object | undefined
      if (header === undefined || header === null) {
        return 0
      }
      const rec: Record<string, string> = header as Record<string, string>
      for (const key of Object.keys(rec)) {
        if (key.toLowerCase() === 'content-length') {
          const v: number = Number(rec[key])
          return Number.isNaN(v) ? 0 : v
        }
      }
    } catch (e) {
      // 头部形态异常: 跳过预检, 由解码后的长度判定兜底
    }
    return 0
  }
}