/**
 * 同步引擎的纯判定规则 —— 翻页停止 / 截断判定 / 游标推进 / 自动全量校准周期。
 *
 * 为什么单独抽出来: 这些判定决定「本轮增量是否追平」「游标能不能前移」
 * 「何时自动升级成全量校准」, 一旦写错会让休眠后的缺口永远补不上
 * (趋势图某几天为 0, 只有手动全量同步才恢复)。完整同步依赖网络与数据库,
 * 本地单测跑不起来, 所以把判定部分做成无 IO 的静态函数直接单测
 * (desktop server.py 的 _oldest_record_ms / _reached_since_boundary /
 * _max_pages_for 同构)。
 */
export class SyncPaging {
  /** 全量同步单轮页数预算 (每页 100 条). */
  static readonly FULL_PAGES: number = 1000
  /** 增量同步单轮页数预算 —— 与全量同值: 自然停止点是 since 边界/游标耗尽, 页数上限只防病态。 */
  static readonly INCREMENTAL_PAGES: number = 1000
  /** 自动全量校准周期 (天): 长期积压/历史遗留缺口由按账号的定期 full 兜底。 */
  static readonly AUTO_FULL_SYNC_DAYS: number = 7
  /** 增量重叠窗口: since = newest_record_at - 1h, 防边界漏记。 */
  static readonly INCREMENTAL_OVERLAP_MS: number = 3600 * 1000

  /** 单轮页数预算: full 与 incremental 同值 (desktop _max_pages_for parity)。 */
  static maxPagesFor(mode: string): number {
    return mode === 'full' ? SyncPaging.FULL_PAGES : SyncPaging.INCREMENTAL_PAGES
  }

  /** 本页最早记录 (ISO 字符串) —— 空串忽略, 无有效值返回 null (desktop _oldest_record_ms)。 */
  static oldestIso(values: string[]): string | null {
    let oldest = ''
    for (const v of values) {
      if (v.length > 0 && (oldest.length === 0 || v < oldest)) {
        oldest = v
      }
    }
    return oldest.length === 0 ? null : oldest
  }

  /** ISO 时间串 -> 毫秒; 空值/解析失败/非正数返回 null。 */
  static isoToMs(text: string | null): number | null {
    if (text === null || text.length === 0) {
      return null
    }
    const ms = Date.parse(text)
    return Number.isNaN(ms) || ms <= 0 ? null : ms
  }

  /**
   * 增量 since 起点: newest_record_at 前推 1 小时重叠窗口。
   * 无游标/解析失败/起点非正时返回 null —— 调用方回退「类全量」两批空停规则。
   */
  static sinceMsFromNewest(newest: string | null): number | null {
    const stamp = SyncPaging.isoToMs(newest)
    if (stamp === null) {
      return null
    }
    const overlap = stamp - SyncPaging.INCREMENTAL_OVERLAP_MS
    return overlap > 0 ? overlap : null
  }

  /**
   * 增量窗口是否已连续翻到 since 边界 (本页最早记录不晚于 since)。
   *
   * 这是 since 已知时唯一正确的停止点: 中间哪怕命中已入库旧数据
   * (inserted == 0) 也必须继续翻 —— 否则会停在已知数据段、越不过缺口,
   * 正是本次「自动同步漏数据」的直接放大器。
   */
  static reachedSince(pageOldestMs: number | null, sinceMs: number | null): boolean {
    if (sinceMs === null || sinceMs <= 0 || pageOldestMs === null) {
      return false
    }
    return pageOldestMs <= sinceMs
  }

  /**
   * 全量模式是否已翻过同步范围边界 (本页最早记录早于 now - windowDays)。
   * 该页整页保留后再停止: 边界附近不丢数据, 又不继续向更早翻页。
   */
  static beforeWindowBoundary(pageOldestIso: string | null, nowMs: number, windowDays: number | null): boolean {
    if (windowDays === null) {
      return false
    }
    const pageMs = SyncPaging.isoToMs(pageOldestIso)
    if (pageMs === null) {
      return false
    }
    const boundary = nowMs - windowDays * 24 * 3600 * 1000
    return pageMs < boundary
  }

  /**
   * 页数预算截断: 循环因 maxPages 退出, 而游标未耗尽、未达 since 边界、
   * 也未撞窗口边界 —— 更早的记录没拉全。
   *
   * 截断绝不能写 ok: 那会把 newest_record_at 推过未拉全的缺口, 下一轮 since
   * 直接越过缺口, 从此只能靠手动全量同步补回 (已确认的用户故障形态)。
   */
  static isTruncated(
    page: number, maxPages: number, exhausted: boolean, windowBoundaryReached: boolean, reachedSince: boolean,
  ): boolean {
    return page >= maxPages && !exhausted && !windowBoundaryReached && !reachedSince
  }

  /**
   * 收尾状态是否允许推进 newest_record_at 游标: 只有 ok。
   * partial/error 时本轮数据不完整, 推进游标等于宣布「缺口已补」。
   */
  static advancesCursor(status: string): boolean {
    return status === 'ok'
  }

  /**
   * 全量校准是否到期: 键缺失 / 解析失败 / 早于 now - days 天 → true。
   * 时钟偏快 (记录时间在未来) 不算过期, 避免每次同步都误触发全量。
   */
  static fullSyncDueAt(lastFullSyncAt: string | null, nowMs: number, days: number): boolean {
    if (days <= 0) {
      return true
    }
    if (lastFullSyncAt === null || lastFullSyncAt.length === 0) {
      return true
    }
    const lastMs = Date.parse(lastFullSyncAt)
    if (Number.isNaN(lastMs)) {
      return true
    }
    return lastMs < nowMs - days * 24 * 3600 * 1000
  }
}
