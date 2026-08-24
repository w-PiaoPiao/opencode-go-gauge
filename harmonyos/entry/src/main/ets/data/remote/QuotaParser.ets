/**
 * Quota Dashboard HTML 解析器 —— opencode_api.py / QuotaParser.kt 的 1:1 移植。
 * 解析 rollingUsage / weeklyUsage / monthlyUsage JS 字面量中的 usagePercent + resetInSec。
 * 字段顺序兼容 (usagePercent 在前或 resetInSec 在前)。
 */
import { QuotaWindow } from '../../common/model/Models'

export class QuotaParser {
  private static readonly LABEL_ROLLING = '5h Rolling'
  private static readonly LABEL_WEEKLY = 'Weekly'
  private static readonly LABEL_MONTHLY = 'Monthly'

  private static readonly ROLLING_PCT_FIRST =
    /rollingUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/
  private static readonly ROLLING_RESET_FIRST =
    /rollingUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/
  private static readonly WEEKLY_PCT_FIRST =
    /weeklyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/
  private static readonly WEEKLY_RESET_FIRST =
    /weeklyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/
  private static readonly MONTHLY_PCT_FIRST =
    /monthlyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/
  private static readonly MONTHLY_RESET_FIRST =
    /monthlyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/

  private static readonly PAIRS: Array<[string, RegExp, RegExp]> = [
    [QuotaParser.LABEL_ROLLING, QuotaParser.ROLLING_PCT_FIRST, QuotaParser.ROLLING_RESET_FIRST],
    [QuotaParser.LABEL_WEEKLY, QuotaParser.WEEKLY_PCT_FIRST, QuotaParser.WEEKLY_RESET_FIRST],
    [QuotaParser.LABEL_MONTHLY, QuotaParser.MONTHLY_PCT_FIRST, QuotaParser.MONTHLY_RESET_FIRST],
  ]

  private static clampPercent(v: number): number {
    return Math.min(100.0, Math.max(0.0, v))
  }

  private static toNum(g: string | undefined, fallback: number): number {
    if (g === undefined || g === null || g.length === 0) {
      return fallback
    }
    const n = Number(g)
    return Number.isNaN(n) ? fallback : n
  }

  private static parseWindow(pctRe: RegExp, resetRe: RegExp, html: string): [number, number] | null {
    const m = pctRe.exec(html)
    if (m !== null) {
      return [QuotaParser.toNum(m[1], 0), QuotaParser.toNum(m[2], 0)]
    }
    const m2 = resetRe.exec(html)
    if (m2 !== null) {
      return [QuotaParser.toNum(m2[2], 0), QuotaParser.toNum(m2[1], 0)]
    }
    return null
  }

  /** 从 Dashboard HTML 解析配额窗口。nowMs = 当前 UTC epoch 毫秒。 */
  static parseQuotaHtml(html: string, nowMs: number = Date.now()): QuotaWindow[] {
    const windows: QuotaWindow[] = []
    for (const pair of QuotaParser.PAIRS) {
      const parsed = QuotaParser.parseWindow(pair[1], pair[2], html)
      if (parsed === null) {
        continue
      }
      const used: number = QuotaParser.clampPercent(parsed[0])
      const resetIn: number = Math.max(0, parsed[1])
      const resetAt: string = new Date(nowMs + resetIn * 1000).toISOString()
      windows.push({
        label: pair[0],
        used: used,
        remaining: Math.round((100.0 - used) * 10) / 10.0,
        total: 100.0,
        unit: '%',
        resetAt: resetAt,
        resetInSec: resetIn,
      })
    }
    return windows
  }
}