/**
 * 格式化工具 —— app.js fmt* / Android Fmt.kt 的 1:1 移植 (locale 无关)。
 */

export class Fmt {
  /** 1.2B / 3.4M / 5.6k / 123 —— fmtTokens 移植。 */
  static tokens(n: number): string {
    const v = n
    if (v >= 1e9) {
      return `${(v / 1e9).toFixed(2)}B`
    }
    if (v >= 1e6) {
      return `${(v / 1e6).toFixed(2)}M`
    }
    if (v >= 1e3) {
      return `${(v / 1e3).toFixed(1)}k`
    }
    return Math.round(v).toString()
  }

  /** 千分位整数 —— fmtInt 移植。 */
  static int(n: number): string {
    const s = Math.round(n).toString()
    let out = ''
    let count = 0
    for (let i = s.length - 1; i >= 0; i--) {
      out = s[i] + out
      count++
      if (count % 3 === 0 && i > 0) {
        out = ',' + out
      }
    }
    return out
  }

  /** 金额 —— fmtMoney 移植。 */
  static money(usd: number, currency: string, usdCny: number): string {
    const v = usd
    if (currency === 'CNY') {
      const c = v * usdCny
      return '¥' + (c >= 1 ? c.toFixed(2) : c.toFixed(4))
    }
    if (v >= 1) {
      return '$' + v.toFixed(2)
    }
    if (v > 0) {
      return '$' + v.toFixed(4)
    }
    return '$0'
  }

  /** 时长 d/h/m —— fmtDur 移植。 */
  static dur(sec: number, dUnit: string, hUnit: string, mUnit: string, soon: string): string {
    const s = Math.max(0, sec)
    const d = Math.floor(s / 86400)
    const h = Math.floor((s % 86400) / 3600)
    const m = Math.floor((s % 3600) / 60)
    if (d > 0) {
      return `${d} ${dUnit} ${h} ${hUnit}`
    }
    if (h > 0) {
      return `${h} ${hUnit} ${m} ${mUnit}`
    }
    if (m > 0) {
      return `${m} ${mUnit}`
    }
    return soon
  }

  /** 完整时间 yyyy-MM-dd HH:mm:ss (ISO → 本地时区)。 */
  static dateTime(iso: string | null): string {
    if (iso === null || iso.length === 0) {
      return '—'
    }
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) {
      return '—'
    }
    return Fmt.pad2(d.getFullYear()) + '-' + Fmt.pad2(d.getMonth() + 1) + '-' + Fmt.pad2(d.getDate()) +
      ' ' + Fmt.pad2(d.getHours()) + ':' + Fmt.pad2(d.getMinutes()) + ':' + Fmt.pad2(d.getSeconds())
  }

  /** 短时间 MM-dd HH:mm。 */
  static dateTimeShort(iso: string | null): string {
    if (iso === null || iso.length === 0) {
      return '—'
    }
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) {
      return '—'
    }
    return Fmt.pad2(d.getMonth() + 1) + '-' + Fmt.pad2(d.getDate()) +
      ' ' + Fmt.pad2(d.getHours()) + ':' + Fmt.pad2(d.getMinutes())
  }

  private static pad2(n: number): string {
    return n < 10 ? `0${n}` : `${n}`
  }

  /** 相对时间 —— fmtRelative 移植。 */
  static relative(iso: string | null, justNow: string, minAgo: string, hrAgo: string, dayAgo: string, never: string): string {
    if (iso === null || iso.length === 0) {
      return never
    }
    const t = new Date(iso).getTime()
    if (Number.isNaN(t)) {
      return never
    }
    const diff = (Date.now() - t) / 1000
    if (diff < 60) {
      return justNow
    }
    if (diff < 3600) {
      return `${Math.floor(diff / 60)} ${minAgo}`
    }
    if (diff < 86400) {
      return `${Math.floor(diff / 3600)} ${hrAgo}`
    }
    return `${Math.floor(diff / 86400)} ${dayAgo}`
  }

  /** 遮蔽长工作区 id —— maskWs 移植。 */
  static maskWs(ws: string): string {
    return ws.length > 12 ? ws.slice(0, 8) + '…' : ws
  }
}