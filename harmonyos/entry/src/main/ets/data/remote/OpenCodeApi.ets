/**
 * OpenCode Go API 客户端 —— opencode_api.py / OpenCodeApi.kt 的 1:1 移植。
 * 两个能力:
 *  1. quota: 抓取 opencode.ai dashboard HTML, 正则解析 5h/weekly/monthly 用量
 *  2. usage: 调用 opencode.ai/_server server-fn 接口, 解析每条请求的 token/cost 明细
 */
import { HttpFetch } from './HttpFetch'
import { QuotaParser } from './QuotaParser'
import { UsageParser } from './UsageParser'
import { QuotaResult, UsageRecord } from '../../common/model/Models'

export class OpenCodeApi {
  static readonly DASHBOARD_BASE = 'https://opencode.ai/workspace'
  static readonly WORKSPACE_SERVER_ID = 'def39973159c7f0483d8793a822b8dbb10d067e12c65455fcb4608459ba0234f'
  static readonly DEFAULT_USAGE_SERVER_ID = 'bfd684bfc2e4eed05cd0b518f5e4eafd3f3376e3938abb9e536e7c03df831e5c'
  static readonly USER_AGENT =
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/148.0'

  private static readonly WORKSPACE_ID_RE = /wrk_[A-Za-z0-9]+/
  private static readonly WORKSPACE_ENTRY_RE =
    /id\s*:\s*"(wrk_[^"]+)"[^{}]*?name\s*:\s*"([^"]*)"/gs
  private static readonly KEY_ENTRY_RE = /\{id:"(key_[A-Za-z0-9]+)",name:"([^"]*)"/g

  /** 归一化 token 为 auth cookie 段。 */
  static buildCookieHeader(token: string): string {
    let cookie = token.trim()
    if (cookie.toLowerCase().startsWith('cookie:')) {
      cookie = cookie.slice(7).trim()
    }
    if (cookie.length === 0) {
      return ''
    }
    for (const part of cookie.split(';')) {
      const p = part.trim()
      if (p.startsWith('auth=')) {
        return p
      }
    }
    return `auth=${cookie}`
  }

  private static argsToJson(args: Array<string | number | null>): string {
    const sb: string[] = ['[']
    for (let i = 0; i < args.length; i++) {
      if (i > 0) {
        sb.push(',')
      }
      const a = args[i]
      if (a === null) {
        sb.push('null')
      } else if (typeof a === 'string') {
        sb.push(`"${a.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`)
      } else {
        sb.push(a.toString())
      }
    }
    sb.push(']')
    return sb.join('')
  }

  private static async serverCall(
    serverId: string, args: Array<string | number | null>, refererPath: string, token: string,
  ): Promise<string> {
    const cookie = OpenCodeApi.buildCookieHeader(token)
    if (cookie.length === 0) {
      throw new Error('token 为空')
    }
    const url = 'https://opencode.ai/_server?id=' +
      encodeURIComponent(serverId) +
      '&args=' + encodeURIComponent(OpenCodeApi.argsToJson(args))
    const headers: Record<string, string> = {
      'Cookie': cookie,
      'X-Server-Id': serverId,
      'X-Server-Instance': `server-fn:${Date.now() * 1000}`,
      'User-Agent': OpenCodeApi.USER_AGENT,
      'Origin': 'https://opencode.ai',
      'Referer': `https://opencode.ai${refererPath}`,
      'Accept': 'text/javascript, application/json;q=0.9, */*;q=0.8',
    }
    return HttpFetch.fetch(url, headers)
  }

  // ------------------------------------------------------------------
  // 工作区解析
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

  /** 拉取账号下全部工作区 (id, name)。 */
  static async fetchWorkspaceRefs(token: string): Promise<Array<[string, string]>> {
    const cookie = OpenCodeApi.buildCookieHeader(token)
    if (cookie.length === 0) {
      throw new Error('token 为空')
    }
    const url = 'https://opencode.ai/_server?id=' + encodeURIComponent(OpenCodeApi.WORKSPACE_SERVER_ID)
    const headers: Record<string, string> = {
      'Cookie': cookie,
      'X-Server-Id': OpenCodeApi.WORKSPACE_SERVER_ID,
      'X-Server-Instance': `server-fn:${Date.now() * 1000}`,
      'User-Agent': OpenCodeApi.USER_AGENT,
      'Origin': 'https://opencode.ai',
      'Referer': 'https://opencode.ai',
      'Accept': 'text/javascript, application/json;q=0.9, */*;q=0.8',
    }
    const text = await HttpFetch.fetch(url, headers)
    const refs: Array<[string, string]> = []
    const seen: Set<string> = new Set()
    let m: RegExpExecArray | null
    while ((m = OpenCodeApi.WORKSPACE_ENTRY_RE.exec(text)) !== null) {
      const workspaceId = m[1]
      const name = m[2].trim()
      if (seen.has(workspaceId)) {
        continue
      }
      seen.add(workspaceId)
      refs.push([workspaceId, name])
    }
    if (refs.length === 0) {
      throw new Error('无法从账号数据解析工作区 ID')
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
  // Quota
  // ------------------------------------------------------------------

  /** 抓取工作区配额窗口。绝不抛异常 —— 失败返回带 error 的 QuotaResult。 */
  static async fetchQuota(token: string, workspaceHint: string = 'Default'): Promise<QuotaResult> {
    const nowIso = new Date().toISOString()
    const hint = (workspaceHint.length === 0 ? 'Default' : workspaceHint).trim()
    if (token.length === 0) {
      return { name: 'Default', workspaceId: hint, success: false, updatedAt: nowIso, windows: [], error: '未配置 token' }
    }
    try {
      const workspaceId = await OpenCodeApi.resolveWorkspaceId(hint, token)
      const cookie = OpenCodeApi.buildCookieHeader(token)
      if (cookie.length === 0) {
        throw new Error('token 为空')
      }
      const url = `${OpenCodeApi.DASHBOARD_BASE}/${encodeURIComponent(workspaceId)}/go`
      const headers: Record<string, string> = {
        'Cookie': cookie,
        'User-Agent': OpenCodeApi.USER_AGENT,
        'Accept': 'text/html, application/xhtml+xml',
      }
      // dashboard HTML 较慢: 2 次尝试 + 500ms 退避 (desktop parity)
      const html = await HttpFetch.fetch(url, headers, 2)
      const windows = QuotaParser.parseQuotaHtml(html)
      if (windows.length === 0) {
        throw new Error('无法从 Dashboard HTML 解析额度数据')
      }
      return { name: 'Default', workspaceId: workspaceId, success: true, updatedAt: nowIso, windows: windows, error: null }
    } catch (e) {
      return {
        name: 'Default', workspaceId: hint, success: false, updatedAt: nowIso, windows: [],
        error: (e as Error).message !== undefined ? (e as Error).message : '未知错误',
      }
    }
  }

  // ------------------------------------------------------------------
  // Usage records
  // ------------------------------------------------------------------

  /** 拉取一页用量记录 (每页 50 条, page 从 0 开始)。 */
  static async fetchUsagePage(
    token: string, workspaceId: string, page: number = 0, keyId: string | null = null,
  ): Promise<UsageRecord[]> {
    const args: Array<string | number | null> = [workspaceId]
    if (keyId !== null) {
      if (page > 0) {
        args.push(page)
        args.push(keyId)
      } else {
        args.push(keyId)
      }
    } else if (page > 0) {
      args.push(page)
    }
    const text = await OpenCodeApi.serverCall(
      OpenCodeApi.DEFAULT_USAGE_SERVER_ID, args, `/workspace/${workspaceId}/usage`, token,
    )
    return UsageParser.parseUsageResponse(text)
  }

  /** 拉取工作区下所有 API key 的名称映射 (key_id -> 名称)。失败返回空 map。 */
  static async fetchKeyNames(token: string, workspaceId: string): Promise<Map<string, string>> {
    const cookie = OpenCodeApi.buildCookieHeader(token)
    if (cookie.length === 0) {
      return new Map()
    }
    const url = `${OpenCodeApi.DASHBOARD_BASE}/${workspaceId}/keys`
    const headers: Record<string, string> = {
      'Cookie': cookie,
      'User-Agent': OpenCodeApi.USER_AGENT,
      'Origin': 'https://opencode.ai',
      'Referer': `${OpenCodeApi.DASHBOARD_BASE}/${workspaceId}/keys`,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try {
      const html = await HttpFetch.fetch(url, headers)
      const names: Map<string, string> = new Map()
      let m: RegExpExecArray | null
      OpenCodeApi.KEY_ENTRY_RE.lastIndex = 0
      while ((m = OpenCodeApi.KEY_ENTRY_RE.exec(html)) !== null) {
        const id = m[1]
        const name = m[2].trim()
        if (id.length > 0 && name.length > 0 && !names.has(id)) {
          names.set(id, name)
        }
      }
      return names
    } catch (e) {
      return new Map()
    }
  }
}