/**
 * GitHub Releases 更新检查 —— updater.py / UpdateApi.kt 的 ArkTS 移植。
 * 轻量提示即可; 下载走系统浏览器。API 受限时降级到 Releases Atom 流 (正则解析)。
 */
import { HttpFetch } from './HttpFetch'
import { UpdateInfo } from '../../common/model/Models'

export class UpdateApi {
  static readonly REPO = 'yphyphyph/opencode-go-gauge'
  static readonly RELEASES_URL = `https://api.github.com/repos/${UpdateApi.REPO}/releases/latest`
  static readonly ATOM_URL = `https://github.com/${UpdateApi.REPO}/releases.atom`
  static readonly RELEASE_PAGE_URL = `https://github.com/${UpdateApi.REPO}/releases/latest`

  private static readonly MAX_ATTEMPTS = 3
  private static readonly RETRY_SLEEP_MS = 800

  private static readonly TAG_RE = /^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$/

  private static parseVersion(text: string): [number, number, number] | null {
    const m = UpdateApi.TAG_RE.exec(text.trim())
    if (m === null) {
      return null
    }
    return [Number(m[1]), Number(m[2]), Number(m[3])]
  }

  private static isNewer(latest: [number, number, number], current: [number, number, number]): boolean {
    return latest[0] > current[0] ||
      (latest[0] === current[0] && (latest[1] > current[1] ||
        (latest[1] === current[1] && latest[2] > current[2])))
  }

  private static unescapeBody(v: string): string {
    return v.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\')
  }

  /** 从 API JSON 文本中提取 tag/html_url/body (正则, 规避 JSON 库类型限制)。 */
  private static parseReleaseJson(text: string): [string, string, string] {
    let tag = ''
    let url = UpdateApi.RELEASE_PAGE_URL
    let body = ''
    const tm = /"tag_name"\s*:\s*"([^"]+)"/.exec(text)
    if (tm !== null) {
      tag = tm[1]
    }
    const um = /"html_url"\s*:\s*"([^"]+)"/.exec(text)
    if (um !== null) {
      url = um[1]
    }
    const bm = /"body"\s*:\s*"((?:[^"\\]|\\.)*)"/.exec(text)
    if (bm !== null) {
      body = UpdateApi.unescapeBody(bm[1]).slice(0, 600)
    }
    return [tag, url, body]
  }

  private static stripHtml(text: string): string {
    let t = text.replace(/<[^>]*>/g, ' ')
    return t.replace(/\s+/g, ' ').trim()
  }

  /** 从 Releases Atom 流解析最新 release (正则解析首条 entry)。 */
  private static parseAtom(text: string): [string, string, string] {
    const entry = /<entry>([\s\S]*?)<\/entry>/.exec(text)
    if (entry === null) {
      throw new Error('GitHub Releases 订阅流为空，未获取到版本信息')
    }
    const block = entry[1]
    let tag = ''
    const idm = /<id>([^<]*)<\/id>/.exec(block)
    if (idm !== null) {
      const id = idm[1].trim()
      const slash = id.lastIndexOf('/')
      tag = slash >= 0 ? id.slice(slash + 1) : id
    }
    let releaseUrl = UpdateApi.RELEASE_PAGE_URL
    const linkRe = /<link[^>]*href="([^"]*)"[^>]*>/g
    let lm: RegExpExecArray | null
    while ((lm = linkRe.exec(block)) !== null) {
      const href = lm[1]
      if (href.indexOf('/releases/tag/') >= 0) {
        releaseUrl = href
        break
      }
    }
    let notes = ''
    const cm = /<content[^>]*>([\s\S]*?)<\/content>/.exec(block)
    if (cm !== null) {
      notes = UpdateApi.stripHtml(cm[1]).slice(0, 600)
    }
    return [tag, releaseUrl, notes]
  }

  /** 检查最新版本 vs 本地版本; 网络/解析失败抛异常。 */
  static async checkUpdate(currentVersion: string): Promise<UpdateInfo> {
    const ua = `GoGauge/${currentVersion}`
    const errors: string[] = []
    let tag = ''
    let releaseUrl = UpdateApi.RELEASE_PAGE_URL
    let notes = ''

    try {
      const text = await UpdateApi.fetchText(UpdateApi.RELEASES_URL, 'application/vnd.github+json', ua)
      const parsed = UpdateApi.parseReleaseJson(text)
      tag = parsed[0]
      releaseUrl = parsed[1]
      notes = parsed[2]
    } catch (e) {
      errors.push((e as Error).message)
    }

    if (tag.length === 0) {
      try {
        const atom = UpdateApi.parseAtom(
          await UpdateApi.fetchText(UpdateApi.ATOM_URL, 'application/atom+xml,application/xml', ua),
        )
        tag = atom[0]
        releaseUrl = atom[1]
        notes = atom[2]
      } catch (e) {
        errors.push((e as Error).message)
      }
    }

    if (tag.length === 0) {
      throw new Error(
        `无法连接 GitHub，无法检查更新（${errors.join('；')}）。\n` +
        '通常是境内直连 GitHub 暂时不可用：请稍后重试，或开启系统代理 / VPN 后再次「检查更新」。',
      )
    }

    const latest = UpdateApi.parseVersion(tag)
    const current = UpdateApi.parseVersion(currentVersion)
    const hasUpdate = latest !== null && current !== null && UpdateApi.isNewer(latest, current)
    return { hasUpdate: hasUpdate, current: currentVersion, latest: tag, releaseUrl: releaseUrl, notes: notes }
  }

  private static async fetchText(url: string, accept: string, ua: string): Promise<string> {
    let lastErr: Error | null = null
    for (let attempt = 0; attempt < UpdateApi.MAX_ATTEMPTS; attempt++) {
      try {
        return await HttpFetch.fetch(url, { 'User-Agent': ua, 'Accept': accept }, 1)
      } catch (e) {
        lastErr = (e as Error)
        if (attempt < UpdateApi.MAX_ATTEMPTS - 1) {
          await HttpFetch.sleep(UpdateApi.RETRY_SLEEP_MS)
        }
      }
    }
    throw lastErr !== null ? lastErr : new Error('未知网络错误')
  }
}