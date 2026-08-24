/**
 * server-fn usage 响应解析器 —— opencode_api.py / UsageParser.kt 的 1:1 移植。
 * 兼容 GET (无空格: id:"usg_...") 与 POST (有空格: id: "usg_...") 两种格式。
 */
import { UsageRecord } from '../../common/model/Models'

export class UsageParser {
  private static readonly RECORD_ANCHOR = /id:\s*"(usg_[^"]+)"/g
  private static readonly PLAN_RE = /id:\s*"(usg_[^"]+)"[^}]*?enrichment:\$R\[\d+\]=\{plan:"([^"]+)"\}/gs
  private static readonly CREATED_RE = /timeCreated:\s*\$R\[\d+\]\s*=\s*new Date\("([^"]+)"\)/

  private static parseNumField(body: string, name: string): number {
    const re = new RegExp(`${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:\\s*(\\d+|null)`)
    const m = re.exec(body)
    if (m === null) {
      return 0
    }
    if (m[1] === 'null') {
      return 0
    }
    const n = Number(m[1])
    return Number.isNaN(n) ? 0 : n
  }

  private static parseStrField(body: string, name: string): string {
    const re = new RegExp(`${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:\\s*"([^"]*)"`)
    const m = re.exec(body)
    return m === null || m[1] === undefined ? '' : m[1]
  }

  /** 解析一个 server-fn 响应体为 UsageRecord 列表。 */
  static parseUsageResponse(text: string): UsageRecord[] {
    const plans: Map<string, string> = new Map()
    let pm: RegExpExecArray | null
    const planRe = UsageParser.PLAN_RE
    while ((pm = planRe.exec(text)) !== null) {
      plans.set(pm[1], pm[2])
    }

    const anchors: RegExpExecArray[] = []
    let am: RegExpExecArray | null
    const anchorRe = UsageParser.RECORD_ANCHOR
    anchorRe.lastIndex = 0
    while ((am = anchorRe.exec(text)) !== null) {
      anchors.push(am)
    }

    const records: UsageRecord[] = []
    for (let i = 0; i < anchors.length; i++) {
      const m = anchors[i]
      const end: number = i + 1 < anchors.length ? anchors[i + 1].index : text.length
      const body: string = text.substring(m.index + m[0].length, end)
      const created = UsageParser.CREATED_RE.exec(body)
      if (created === null) {
        continue
      }
      const usgId: string = m[1]
      const planVal = plans.get(usgId)
      records.push({
        usgId: usgId,
        createdAt: created[1],
        model: UsageParser.parseStrField(body, 'model'),
        provider: UsageParser.parseStrField(body, 'provider'),
        inputTokens: UsageParser.parseNumField(body, 'inputTokens'),
        outputTokens: UsageParser.parseNumField(body, 'outputTokens'),
        reasoningTokens: UsageParser.parseNumField(body, 'reasoningTokens'),
        cacheReadTokens: UsageParser.parseNumField(body, 'cacheReadTokens'),
        cacheWrite5mTokens: UsageParser.parseNumField(body, 'cacheWrite5mTokens'),
        cacheWrite1hTokens: UsageParser.parseNumField(body, 'cacheWrite1hTokens'),
        costRaw: UsageParser.parseNumField(body, 'cost'),
        keyId: UsageParser.parseStrField(body, 'keyID'),
        sessionId: UsageParser.parseStrField(body, 'sessionID'),
        plan: planVal === undefined ? null : planVal,
      })
    }
    return records
  }
}