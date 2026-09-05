/**
 * 月度重置周期策略 —— desktop db.monthly_cycle_start / android MonthlyCycle 的 ArkTS 移植。
 *
 * OpenCode Go $10 月度套餐按 30 天滚动周期重置, 官方接口只暴露下次重置时间, 周期起点
 * 以 "下次重置 - 30 天" 推算; 若记录的重置时刻已过去 (重置已发生而配额未刷新),
 * 该时刻即本周期开始的精确边界。无记录或格式异常时返回 null (调用方回退滚动 30 天)。
 * 时间统一为 UTC "yyyy-MM-dd HH:mm:ss" 字符串, 与持久化格式一致。
 */
export class MonthlyCycle {
  static readonly PERIOD_DAYS: number = 30
  private static readonly DAY_MS: number = 24 * 3600 * 1000

  private static parseUtc(s: string): number | null {
    const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(s)
    if (m === null) {
      return null
    }
    const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]),
      Number(m[4]), Number(m[5]), Number(m[6]))
    return Number.isNaN(t) ? null : t
  }

  static fmtUtc(ms: number): string {
    const d = new Date(ms)
    const p = (n: number): string => String(n).padStart(2, '0')
    return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}` +
      ` ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`
  }

  /** 推导当前周期起点; resetUtc 为持久化的下次重置时间, nowMs 为当前毫秒时刻。 */
  static start(resetUtc: string | null, nowMs: number): string | null {
    if (resetUtc === null || resetUtc.length === 0) {
      return null
    }
    const reset = MonthlyCycle.parseUtc(resetUtc)
    if (reset === null) {
      return null
    }
    const started = reset > nowMs
      ? reset - MonthlyCycle.PERIOD_DAYS * MonthlyCycle.DAY_MS
      : reset
    return MonthlyCycle.fmtUtc(started)
  }
}
