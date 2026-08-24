/**
 * USD→CNY 汇率 —— server.py _fetch_usd_cny / ExchangeApi.kt 移植。
 * 失败抛 HttpError (调用方保留缓存/默认值)。
 */
import { HttpFetch, HttpError } from './HttpFetch'

export class ExchangeApi {
  static readonly EXCHANGE_URL = 'https://open.er-api.com/v6/latest/USD'

  /** 抓取 USD→CNY; 失败抛异常。 */
  static async fetchUsdCny(): Promise<number> {
    const body = await HttpFetch.fetch(ExchangeApi.EXCHANGE_URL, {
      'User-Agent': 'GoGauge/1.0',
      'Accept': 'application/json',
    })
    const m = /"CNY"\s*:\s*([\d.]+)/.exec(body)
    if (m === null) {
      throw new HttpError('汇率接口缺少 CNY')
    }
    const rate = Number(m[1])
    if (!(rate > 0)) {
      throw new HttpError('汇率接口缺少 CNY')
    }
    return rate
  }
}