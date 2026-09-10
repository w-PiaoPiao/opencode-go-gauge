/** ResultSet 行读取器 —— 按列名取值, 屏蔽下标/空值细节。 */
import { relationalStore } from '@kit.ArkData'
import hilog from '@ohos.hilog'

const DOMAIN: number = 0x0001
const TAG: string = 'GoGaugeDb'

export class RowReader {
  private rs: relationalStore.ResultSet
  private colCache: Map<string, number> = new Map()

  constructor(rs: relationalStore.ResultSet) {
    this.rs = rs
  }

  get rowCount(): number {
    return this.rs.rowCount
  }

  next(): boolean {
    return this.rs.goToNextRow()
  }

  /**
   * 列名 -> 下标; 找不到时返回 -1 并记一次告警。
   *
   * 取值方法一律吞异常 (调用方不应因单列异常中断整表读取), 但列名拼错此前是
   * 完全无声的: 聚合结果会整体变 0, 看起来像"没有数据"而不是 bug. 这里至少
   * 在 hilog 留痕 (getColumnIndex 对未知列返回 -1, 随后 getXxx 抛错被吞).
   */
  private idx(name: string): number {
    let i = this.colCache.get(name)
    if (i === undefined) {
      i = this.rs.getColumnIndex(name)
      if (i < 0) {
        hilog.warn(DOMAIN, TAG, 'RowReader: 列 "%{public}s" 不存在, 返回值将为空/0', name)
      }
      this.colCache.set(name, i)
    }
    return i
  }

  getStrAt(idx: number): string {
    try {
      return this.rs.getString(idx)
    } catch (e) {
      return ''
    }
  }

  getLongAt(idx: number): number {
    try {
      return this.rs.getLong(idx)
    } catch (e) {
      return 0
    }
  }

  getStr(name: string): string {
    try {
      return this.rs.getString(this.idx(name))
    } catch (e) {
      return ''
    }
  }

  getLong(name: string): number {
    try {
      return this.rs.getLong(this.idx(name))
    } catch (e) {
      return 0
    }
  }

  getDouble(name: string): number {
    try {
      return this.rs.getDouble(this.idx(name))
    } catch (e) {
      return 0
    }
  }

  isNull(name: string): boolean {
    try {
      return this.rs.isColumnNull(this.idx(name))
    } catch (e) {
      return true
    }
  }

  close(): void {
    this.rs.close()
  }
}