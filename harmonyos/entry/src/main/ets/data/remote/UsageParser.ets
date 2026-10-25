/**
 * /console/api/request-logs 解析器 —— opencode_api.parse_request_logs / UsageParser.kt 移植。
 *
 * items[] 仅 category=="inference" 计入用量 (api 类是控制台自身接口调用);
 * ``cost`` 为 USD 浮点, 还原为 1e-8 单位存 costRaw; 新接口不再区分 5m/1h 缓存写入,
 * 统一记入缓存写入列 (合计口径不变); nextCursor 供续翻, retentionDays 为服务端保留窗口。
 *
 * 2026-09 opencode.ai 改版: 旧 /_server server-fn 响应的正则解析随改版下线。
 */
import { UsageRecord } from '../../common/model/Models'
import { Json } from './QuotaParser'

/** request-logs 的一页结果 (游标分页)。 */
export interface UsagePage {
  records: UsageRecord[]
  nextCursor: string | null
  retentionDays: number | null
}

export class UsageParser {
  private static readonly CATEGORY_INFERENCE = 'inference'

  /** 毫秒时间戳 -> ISO ...Z; 非法值返回空串。 */
  private static isoFromMs(ms: number): string {
    if (ms <= 0) {
      return ''
    }
    try {
      return new Date(ms).toISOString()
    } catch (e) {
      return ''
    }
  }

  private static recordFromItem(item: Record<string, Object>): UsageRecord | null {
    const usgId = Json.str(item['id']).trim()
    const createdAt = UsageParser.isoFromMs(Json.num(item['startedAt']))
    if (usgId.length === 0 || createdAt.length === 0) {
      return null
    }
    // 新接口不再区分 5m/1h 缓存写入, 统一记入 5m 列 (合计口径不变)
    const cacheWrite = Math.round(Json.num(item['cacheWriteTokens']))
    const product = Json.str(item['product']).trim()
    const rec: UsageRecord = {
      usgId: usgId,
      createdAt: createdAt,
      model: Json.str(item['model']).trim(),
      provider: Json.str(item['provider']).trim(),
      inputTokens: Math.round(Json.num(item['inputTokens'])),
      outputTokens: Math.round(Json.num(item['outputTokens'])),
      reasoningTokens: Math.round(Json.num(item['reasoningTokens'])),
      cacheReadTokens: Math.round(Json.num(item['cacheReadTokens'])),
      cacheWrite5mTokens: cacheWrite,
      cacheWrite1hTokens: 0,
      costRaw: Math.round(Json.num(item['cost']) * 100_000_000),
      keyId: Json.str(item['serviceAPIKeyID']).trim(),
      sessionId: Json.str(item['sessionID']).trim(),
      plan: product.length > 0 ? product : null,
    }
    return rec
  }

  /** 解析 /console/api/request-logs 响应 (只保留 inference 类请求)。 */
  static parseRequestLogsPayload(payload: Object | null): UsagePage {
    const root = Json.asObj(payload)
    if (root === null) {
      return { records: [], nextCursor: null, retentionDays: null }
    }
    const records: UsageRecord[] = []
    const items = Json.asArr(root['items'])
    if (items !== null) {
      for (const el of items) {
        const item = Json.asObj(el)
        if (item === null) {
          continue
        }
        if (Json.str(item['category']).trim().toLowerCase() !== UsageParser.CATEGORY_INFERENCE) {
          continue  // 控制台自身接口调用, 不计入用量
        }
        const rec = UsageParser.recordFromItem(item)
        if (rec !== null) {
          records.push(rec)
        }
      }
    }
    const cursor = Json.str(root['nextCursor']).trim()
    const retention = root['retentionDays']
    return {
      records: records,
      nextCursor: cursor.length > 0 ? cursor : null,
      retentionDays: retention === undefined || retention === null
        ? null
        : Math.round(Json.num(retention)),
    }
  }

  /** 文本便捷入口 (单测/调用方持有原始响应体时使用)。 */
  static parseRequestLogsText(text: string): UsagePage {
    let payload: Object | null = null
    try {
      payload = JSON.parse(text) as Object
    } catch (e) {
      return { records: [], nextCursor: null, retentionDays: null }
    }
    return UsageParser.parseRequestLogsPayload(payload)
  }
}
