/** ResultSet 行读取器 —— 按列名取值, 屏蔽下标/空值细节。 */
import { relationalStore } from '@kit.ArkData'

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

  private idx(name: string): number {
    let i = this.colCache.get(name)
    if (i === undefined) {
      i = this.rs.getColumnIndex(name)
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