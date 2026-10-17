/**
 * 月度重置周期策略 —— desktop db.monthly_cycle_start / android MonthlyCycle 的 ArkTS 移植。
 *
 * 官方接口只暴露下次重置时间, 周期起点以「下次重置往前一个自然月」推算; 若记录的重置
 * 时刻已过去 (重置已发生而配额未刷新), 该时刻即本周期开始的精确边界。回推后仍不在
 * 过去 (重置在 1 个自然月之外) 或格式异常时返回 null, 调用方回退滚动 30 天 ——
 * 绝不返回未来起点。时间统一为 UTC "yyyy-MM-dd HH:mm:ss", 与持久化一致。
 *
 * 口径说明: 本端配额来自 dashboard HTML 的 monthlyUsage.resetInSec, 只有「下次重置」
 * 一个数据源 (没有 desktop 的 access.startsAt/endsAt 真实周期边界), 故回推按自然月
 * 而非固定 30 天 —— Go 月度实测就是自然月 (10-08 → 11-08), 固定 30 天会偏 1 天、
 * 丢掉周期首日的用量。
 */
export class MonthlyCycle {
  static readonly PERIOD_DAYS: number = 30

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

  /**
   * 往前一个自然月; 日号随锚点保持, 月末溢出钳到当月最后一天 (03-31 → 02-28)。
   * 必须以锚点一次算出 —— 逐月累加会丢锚点 (01-31 → 02-28 → 03-28, 此后停在 28 号)。
   */
  private static minusOneCalendarMonth(ms: number): number {
    const d = new Date(ms)
    const year = d.getUTCFullYear()
    const month = d.getUTCMonth() // 0-based
    const targetYear = month === 0 ? year - 1 : year
    const targetMonth = month === 0 ? 11 : month - 1
    // 目标月的下个月第 0 天 = 目标月最后一天
    const lastDay = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate()
    return Date.UTC(targetYear, targetMonth, Math.min(d.getUTCDate(), lastDay),
      d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds())
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
    if (reset <= nowMs) {
      return MonthlyCycle.fmtUtc(reset)
    }
    const started = MonthlyCycle.minusOneCalendarMonth(reset)
    // 回推一个自然月仍在未来 (重置在 1 个自然月之外): 该假设推不出过去的起点,
    // 未来起点会让「本周期」窗口恒为空 (实测筛出 0 条) —— 回退 null 走滚动 30 天。
    if (started > nowMs) {
      return null
    }
    return MonthlyCycle.fmtUtc(started)
  }
}
