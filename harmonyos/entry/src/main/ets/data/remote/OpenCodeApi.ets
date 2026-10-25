/**
 * OpenCode Console API 客户端 —— opencode_api.py / OpenCodeApi.kt 的 ArkTS 移植
 * (2026-09 opencode.ai 前端改版后)。
 *
 * - 会话 Cookie: ``auth`` -> ``__Host-console_session`` (登录页 /console/login)
 * - 配额: 旧 dashboard HTML 解析 -> GET /console/api/go/status
 * - 明细: 旧 /_server server-fn -> GET /console/api/request-logs (游标分页)
 * - 工作区: GET /console/api/orgs ; Key 名称: GET /console/api/service-accounts
 *
 * 所有 /console/api 请求除 Cookie 外还需 ``x-org-id: <wrk_xxx>`` 头 (org 即工作区)。
 * 服务端对请求明细只保留 30 天 (响应中的 retentionDays)。
 */
import { HttpFetch } from './HttpFetch'
import { Json, QuotaParser } from './QuotaParser'
import { UsageParser, UsagePage } from './UsageParser'
import { Cookie } from '../../common/util/Cookie'
import { QuotaResult, QuotaWindow } from '../../common/model/Models'

export class OpenCodeApi {
  static readonly CONSOLE_ORIGIN = 'https://opencode.ai'
  static readonly CONSOLE_LOGIN_URL = 'https://opencode.ai/console/login'
  static readonly API_BASE = 'https://opencode.ai/console/api'
  // 会话 Cookie: 新版 __Host-console_session, 旧版 auth (兼容历史 token)
  static readonly SESSION_COOKIE = '__Host-console_session'
  static readonly LEGACY_SESSION_COOKIE = 'auth'
  static readonly USER_AGENT =
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:148.0) Gecko/20100101 Firefox/148.0'

  /** request-logs 单页条数 (接口上限 100)。 */
  static readonly USAGE_PAGE_SIZE = 100

  private static readonly WORKSPACE_ID_RE = /wrk_[A-Za-z0-9]+/

  /**
   * 归一化 token 为 Cookie 头 (opencode_api.build_cookie_header parity)。
   * 支持完整 Cookie 串 / "cookie:" 前缀串 / 纯值三种输入。
   */
  static buildCookieHeader(token: string): string {
    const raw = Cookie.stripPrefix(token)
    if (raw.length === 0) {
      return ''
    }
    for (const part of raw.split(';')) {
      const p = part.trim()
      if (p.length === 0) {
        continue
      }
      const name = p.split('=')[0].trim().toLowerCase()
      if (name === OpenCodeApi.SESSION_COOKIE || name === OpenCodeApi.LEGACY_SESSION_COOKIE) {
        return p
      }
    }
    // 形如 name=value 的其它 Cookie 原样透传, 纯值则按新版会话 Cookie 处理
    if (/^[A-Za-z0-9_.\-]+\s*=\s*\S+$/.test(raw)) {
      return raw
    }
    return `${OpenCodeApi.SESSION_COOKIE}=${raw}`
  }

  /** GET /console/api 下接口, 返回解析后的 JSON (解析失败抛错)。 */
  private static async apiGet(
    path: string, token: string, orgId: string,
    params: Map<string, string | null> = new Map(),
  ): Promise<Object | null> {
    const cookie = OpenCodeApi.buildCookieHeader(token)
    if (cookie.length === 0) {
      throw new Error('token 为空')
    }
    let url = `${OpenCodeApi.API_BASE}${path}`
    const parts: string[] = []
    params.forEach((v, k) => {
      if (v !== null && v.length > 0) {
        parts.push(`${k}=${encodeURIComponent(v)}`)
      }
    })
    if (parts.length > 0) {
      url += `?${parts.join('&')}`
    }
    const headers: Record<string, string> = {
      'Cookie': cookie,
      'Accept': 'application/json',
      'User-Agent': OpenCodeApi.USER_AGENT,
      'Origin': OpenCodeApi.CONSOLE_ORIGIN,
      'Referer': `${OpenCodeApi.CONSOLE_ORIGIN}/console/`,
    }
    if (orgId.length > 0) {
      headers['x-org-id'] = orgId
    }
    const text = await HttpFetch.fetch(url, headers, 2)
    return JSON.parse(text) as Object
  }

  // ------------------------------------------------------------------
  // 工作区 (org)
  // ------------------------------------------------------------------

  static extractWorkspaceId(raw: string): string {
    const value = raw.trim()
    if (value.length === 0) {
      return ''
    }
    if (value.startsWith('wrk_') && value.length > 4) {
      return value
    }
    const m = OpenCodeApi.WORKSPACE_ID_RE.exec(value)
    return m === null ? '' : m[0]
  }

  /** 拉取账号下全部工作区 (id, name) — GET /console/api/orgs。 */
  static async fetchWorkspaceRefs(token: string): Promise<Array<[string, string]>> {
    const data = await OpenCodeApi.apiGet('/orgs', token, '')
    const refs: Array<[string, string]> = []
    const seen: Set<string> = new Set()
    const arr = Json.asArr(data)
    if (arr !== null) {
      for (const el of arr) {
        const item = Json.asObj(el)
        if (item === null) {
          continue
        }
        const wid = Json.str(item['id']).trim()
        if (wid.length === 0 || seen.has(wid)) {
          continue
        }
        seen.add(wid)
        refs.push([wid, Json.str(item['name']).trim()])
      }
    }
    if (refs.length === 0) {
      throw new Error('无法获取工作区列表 (账号下没有工作区)')
    }
    return refs
  }

  /** 将工作区 hint (id / name / Default) 解析为 wrk_xxx ID。 */
  static async resolveWorkspaceId(hint: string, token: string): Promise<string> {
    const resolved = OpenCodeApi.extractWorkspaceId(hint)
    if (resolved.length > 0) {
      return resolved
    }
    const refs = await OpenCodeApi.fetchWorkspaceRefs(token)
    const hintL = hint.trim().toLowerCase()
    if (hintL.length > 0) {
      for (const ref of refs) {
        if (ref[0].toLowerCase() === hintL || ref[1].toLowerCase() === hintL) {
          return ref[0]
        }
      }
    }
    if (refs.length > 0) {
      return refs[0][0]
    }
    throw new Error(`无法从 "${hint}" 解析工作区 ID`)
  }

  // ------------------------------------------------------------------
  // 配额 (go/status)
  // ------------------------------------------------------------------

  /** 抓取工作区 Go 配额窗口 (5h/weekly/monthly)。绝不抛异常 —— 失败返回带 error 的 QuotaResult。 */
  static async fetchQuota(token: string, workspaceHint: string = 'Default'): Promise<QuotaResult> {
    const nowIso = new Date().toISOString()
    const hint = (workspaceHint.length === 0 ? 'Default' : workspaceHint).trim()
    if (token.trim().length === 0) {
      return {
        name: 'Default', workspaceId: hint, success: false,
        updatedAt: nowIso, windows: [], error: '未配置 token',
      }
    }
    try {
      const workspaceId = await OpenCodeApi.resolveWorkspaceId(hint, token)
      const payload = await OpenCodeApi.apiGet('/go/status', token, workspaceId)
      const windows = QuotaParser.parseGoStatusPayload(payload)
      if (windows.length === 0) {
        throw new Error('账号未订阅 OpenCode Go (接口无额度数据)')
      }
      return {
        name: 'Default', workspaceId: workspaceId, success: true,
        updatedAt: nowIso, windows: windows, error: null,
      }
    } catch (e) {
      const msg = (e as Error).message !== undefined ? (e as Error).message : '未知错误'
      return {
        name: 'Default', workspaceId: hint, success: false,
        updatedAt: nowIso, windows: [], error: msg,
      }
    }
  }

  // ------------------------------------------------------------------
  // 用量明细 (request-logs)
  // ------------------------------------------------------------------

  /**
   * 拉取一页用量明细 (游标分页, 按时间倒序)。
   *
   * cursor: 上一页返回的 next_cursor, 首页传 null; sinceMs: 只取该毫秒时间戳
   * 之后的记录 (增量同步用)。
   */
  static async fetchUsagePage(
    token: string, workspaceId: string,
    cursor: string | null = null, sinceMs: number | null = null,
  ): Promise<UsagePage> {
    const params: Map<string, string | null> = new Map()
    params.set('limit', String(OpenCodeApi.USAGE_PAGE_SIZE))
    if (cursor !== null && cursor.length > 0) {
      params.set('cursor', cursor)
    }
    if (sinceMs !== null && sinceMs > 0) {
      params.set('since', String(Math.floor(sinceMs)))
    }
    const payload = await OpenCodeApi.apiGet('/request-logs', token, workspaceId, params)
    return UsageParser.parseRequestLogsPayload(payload)
  }

  /** 拉取工作区下所有 API key 的名称映射 (key_id -> 名称)。失败返回空 map。 */
  static async fetchKeyNames(token: string, workspaceId: string): Promise<Map<string, string>> {
    const names: Map<string, string> = new Map()
    try {
      const payload = await OpenCodeApi.apiGet('/service-accounts', token, workspaceId)
      const root = Json.asObj(payload)
      const items = root === null ? null : Json.asArr(root['items'])
      if (items !== null) {
        for (const el of items) {
          const entry = Json.asObj(el)
          if (entry === null) {
            continue
          }
          const keys = Json.asArr(entry['keys'])
          if (keys === null) {
            continue
          }
          for (const kel of keys) {
            const key = Json.asObj(kel)
            if (key === null) {
              continue
            }
            const id = Json.str(key['id']).trim()
            const name = Json.str(key['name']).trim()
            if (id.length > 0 && name.length > 0 && !names.has(id)) {
              names.set(id, name)
            }
          }
        }
      }
    } catch (e) {
      // 失败返回空 map (不影响主流程)
    }
    return names
  }
}
