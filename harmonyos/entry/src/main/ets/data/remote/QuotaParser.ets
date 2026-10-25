/**
 * /console/api/go/status JSON 解析器 —— opencode_api.parse_go_status / QuotaParser.kt 移植。
 *
 * 结构: access.meters.{fiveHour,week,month} 各含 limitMicroCents / usedMicroCents
 * (单位 1e-8 USD, 值可能是数字或字符串), 以及可选 resetsAt; 月额度无 resetsAt 时
 * 用 access.endsAt 兜底。5h 窗口自窗口内第一条请求起算, 空闲时 (最近 5 小时无请求)
 * 接口不给 resetsAt —— 此时重置时间留空, 界面按「窗口未开始」呈现, 不能借月周期兜底
 * (会让滚动窗口显示成「重置于 24 天」, 与「已用 0%」自相矛盾)。
 *
 * 2026-09 opencode.ai 改版: 旧 dashboard HTML 的 rollingUsage/$R[...] 正则解析随
 * 改版下线 (配额改由 /console/api/go/status 提供)。
 */
import { QuotaWindow } from '../../common/model/Models'

/** JSON 宽容取值工具 (go/status 与 request-logs 解析共用; 数值可能是数字或字符串)。 */
export class Json {
  static asObj(v: Object | null | undefined): Record<string, Object> | null {
    if (v === null || v === undefined || typeof v !== 'object' || Array.isArray(v)) {
      return null
    }
    return v as Record<string, Object>
  }

  static asArr(v: Object | null | undefined): Array<Object> | null {
    if (v === null || v === undefined || !Array.isArray(v)) {
      return null
    }
    return v as Array<Object>
  }

  static str(v: Object | null | undefined): string {
    if (typeof v === 'string') {
      return v
    }
    if (typeof v === 'number') {
      return String(v)
    }
    return ''
  }

  static num(v: Object | null | undefined, fallback: number = 0): number {
    if (typeof v === 'number') {
      return v
    }
    if (typeof v === 'string' && v.length > 0 && v !== 'null') {
      const n = Number(v)
      if (!Number.isNaN(n)) {
        return n
      }
    }
    return fallback
  }
}

export class QuotaParser {
  private static readonly LABEL_ROLLING = '5h Rolling'
  private static readonly LABEL_WEEKLY = 'Weekly'
  private static readonly LABEL_MONTHLY = 'Monthly'

  private static readonly METER_KEYS: Array<[string, string]> = [
    [QuotaParser.LABEL_ROLLING, 'fiveHour'],
    [QuotaParser.LABEL_WEEKLY, 'week'],
    [QuotaParser.LABEL_MONTHLY, 'month'],
  ]

  private static clampPercent(v: number): number {
    return Math.min(100.0, Math.max(0.0, v))
  }

  private static round2(v: number): number {
    return Math.round(v * 100) / 100.0
  }

  /** ISO 时间串规范为 ...Z; 解析失败原样返回 (调用方 isoOrNull 挡脏值)。 */
  static isoFromText(raw: string): string {
    if (raw.length === 0) {
      return ''
    }
    const ms = Date.parse(raw)
    if (Number.isNaN(ms)) {
      return raw
    }
    return new Date(ms).toISOString()
  }

  /** 规范 ISO-Z 值; [isoFromText] 解析失败时原样透传, 周期字段要挡掉这类脏值。 */
  static isoOrNull(raw: string): string | null {
    const text = QuotaParser.isoFromText(raw)
    return text.endsWith('Z') && text.includes('T') ? text : null
  }

  private static secondsUntil(isoText: string, nowMs: number): number {
    if (isoText.length === 0) {
      return 0
    }
    const target = Date.parse(isoText)
    if (Number.isNaN(target)) {
      return 0
    }
    return Math.max(0, Math.floor((target - nowMs) / 1000))
  }

  /** 解析 /console/api/go/status 响应为三个额度窗口 (5h/weekly/monthly)。 */
  static parseGoStatusPayload(payload: Object | null, nowMs: number = Date.now()): QuotaWindow[] {
    const root = Json.asObj(payload)
    if (root === null) {
      return []
    }
    const access = Json.asObj(root['access'])
    if (access === null) {
      return []
    }
    const meters = Json.asObj(access['meters'])
    if (meters === null) {
      return []
    }
    const periodEnd = QuotaParser.isoFromText(Json.str(access['endsAt']))
    const windows: QuotaWindow[] = []
    for (const pair of QuotaParser.METER_KEYS) {
      const label = pair[0]
      const meter = Json.asObj(meters[pair[1]])
      if (meter === null) {
        continue
      }
      const limit = Json.num(meter['limitMicroCents'])
      const usedRaw = Json.num(meter['usedMicroCents'])
      if (limit <= 0) {
        continue
      }
      const used = QuotaParser.clampPercent(usedRaw / limit * 100.0)
      // 月额度无 resetsAt 是常态, 用订阅周期结束兜底; 5h/周窗口没有 resetsAt 则是
      // 「窗口未开始」—— 留空交给界面 (desktop 08dfca1 parity)
      let resetAt = QuotaParser.isoFromText(Json.str(meter['resetsAt']))
      if (resetAt.length === 0 && label === QuotaParser.LABEL_MONTHLY) {
        resetAt = periodEnd
      }
      const w: QuotaWindow = {
        label: label,
        used: QuotaParser.round2(used),
        remaining: QuotaParser.round2(100.0 - used),
        total: 100.0,
        unit: '%',
        resetAt: resetAt,
        resetInSec: QuotaParser.secondsUntil(resetAt, nowMs),
      }
      windows.push(w)
    }
    return windows
  }

  /** 文本便捷入口 (单测/调用方持有原始响应体时使用)。 */
  static parseGoStatusText(text: string, nowMs: number = Date.now()): QuotaWindow[] {
    let payload: Object | null = null
    try {
      payload = JSON.parse(text) as Object
    } catch (e) {
      return []
    }
    return QuotaParser.parseGoStatusPayload(payload, nowMs)
  }
}
