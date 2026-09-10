/**
 * GitHub Releases 更新检查 —— updater.py / UpdateApi.kt 的 ArkTS 移植。
 * 轻量提示即可; 下载走系统浏览器。API 受限时降级到 Releases Atom 流 (正则解析)。
 */
import { HttpFetch } from './HttpFetch'
import { UpdateInfo } from '../../common/model/Models'

export class UpdateApi {
  // fork 发布仓库: HAP 由本 fork 的 release 分发 (与 Android UpdateApi 一致)
  static readonly REPO = 'w-PiaoPiao/opencode-go-gauge'
  // 列表接口而非 /releases/latest: 仓库 Latest 是全平台共享的一个标记,
  // 其他平台 (-macos/-windows/-android) 发布后占据 Latest 会把鸿蒙的更新
  // 判断带偏 (tag 后缀被剥掉后版本比较失真). 这里只认 -harmony 条目
  // — desktop updater.py / Android UpdateApi.kt 同做法。
  static readonly RELEASES_URL = `https://api.github.com/repos/${UpdateApi.REPO}/releases?per_page=30`
  static readonly ATOM_URL = `https://github.com/${UpdateApi.REPO}/releases.atom`
  static readonly RELEASE_PAGE_URL = `https://github.com/${UpdateApi.REPO}/releases/latest`

  private static readonly MAX_ATTEMPTS = 3
  private static readonly RETRY_SLEEP_MS = 800
  /** 平台 tag 后缀: 更新检查只认带此后缀且版本前缀合法的 release 条目。 */
  private static readonly PLATFORM_SUFFIX = '-harmony'

  // 版本号支持三段数字 + 可选字母预发布后缀 (2.1.0b > 2.1.0) 及 -/+ 尾缀
  // (2.1.0b-harmony, 尾缀不参与比较) — desktop updater.py parity
  private static readonly TAG_RE = /^v?(\d+)\.(\d+)\.(\d+)([a-z])?(?:[-+].*)?$/

  /**
   * 版本号解析 (公开供单测): 无后缀=第 4 位 0, 字母后缀 a=1..z=26。
   */
  static parseVersion(text: string): [number, number, number, number] | null {
    const m = UpdateApi.TAG_RE.exec(text.trim())
    if (m === null) {
      return null
    }
    // 第 4 位为字母预发布后缀 (a=1..z=26, 无后缀=0), 与 desktop/Android 的
    // "2.1.0b > 2.1.0" 规则一致
    const suffix = m[4] !== undefined && m[4].length > 0 ? m[4].charCodeAt(0) - 96 : 0
    return [Number(m[1]), Number(m[2]), Number(m[3]), suffix]
  }

  /** 该 tag 是否为本平台 release (带 -harmony 后缀且版本合法)。公开供单测。 */
  static isPlatformTag(tag: string): boolean {
    const t = tag.trim().toLowerCase()
    return t.endsWith(UpdateApi.PLATFORM_SUFFIX) && UpdateApi.parseVersion(t) !== null
  }

  /** 版本比较 (公开供单测)。 */
  static isNewer(
    latest: [number, number, number, number],
    current: [number, number, number, number],
  ): boolean {
    for (let i = 0; i < latest.length; i++) {
      if (latest[i] !== current[i]) {
        return latest[i] > current[i]
      }
    }
    return false
  }

  private static unescapeBody(v: string): string {
    return v.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\')
  }

  /**
   * 从 API JSON 列表中提取首个本平台 release 的 tag/html_url/body
   * (正则解析, 规避 JSON 库类型限制)。
   *
   * 接口为列表 (releases?per_page=30), 按创建时间倒序 —— 首个 -harmony 条目
   * 即最新本平台版本; 非本平台条目直接跳过。
   */
  private static parseReleaseJson(text: string): [string, string, string] {
    // 逐个 release 对象切分: 以 "tag_name" 为锚点向前后取字段
    const tagRe = /"tag_name"\s*:\s*"([^"]+)"/g
    let m: RegExpExecArray | null
    while ((m = tagRe.exec(text)) !== null) {
      const tag = m[1]
      if (!UpdateApi.isPlatformTag(tag)) {
        continue
      }
      // 在本 release 对象范围内取 html_url 与 body (对象以 "}," 或末尾 "}" 收束;
      // 取到下一个 tag_name 之前即可, 避免跨 release 误匹配)
      const rest = text.slice(m.index)
      const nextIdx = rest.indexOf('"tag_name"', 1)
      const scope = nextIdx > 0 ? rest.slice(0, nextIdx) : rest
      let url = UpdateApi.RELEASE_PAGE_URL
      let body = ''
      const um = /"html_url"\s*:\s*"([^"]+)"/.exec(scope)
      if (um !== null) {
        url = um[1]
      }
      const bm = /"body"\s*:\s*"((?:[^"\\]|\\.)*)"/.exec(scope)
      if (bm !== null) {
        body = UpdateApi.unescapeBody(bm[1]).slice(0, 600)
      }
      return [tag, url, body]
    }
    return ['', UpdateApi.RELEASE_PAGE_URL, '']
  }

  private static stripHtml(text: string): string {
    let t = text.replace(/<[^>]*>/g, ' ')
    return t.replace(/\s+/g, ' ').trim()
  }

  /**
   * 从 Releases Atom 流解析最新的本平台 release。
   *
   * 流内混排各平台条目, 必须逐条过滤 —— 原先只取首条 entry, 会把
   * macOS/Android 的 release 当成鸿蒙的更新 (desktop _fetch_latest_atom /
   * Android UpdateApi.parseAtom parity)。
   */
  private static parseAtom(text: string): [string, string, string] {
    const entryRe = /<entry>([\s\S]*?)<\/entry>/g
    let em: RegExpExecArray | null
    let sawEntry = false
    while ((em = entryRe.exec(text)) !== null) {
      sawEntry = true
      const block = em[1]
      let tag = ''
      const idm = /<id>([^<]*)<\/id>/.exec(block)
      if (idm !== null) {
        const id = idm[1].trim()
        const slash = id.lastIndexOf('/')
        tag = slash >= 0 ? id.slice(slash + 1) : id
      }
      if (!UpdateApi.isPlatformTag(tag)) {
        continue
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
    if (!sawEntry) {
      throw new Error('GitHub Releases 订阅流为空，未获取到版本信息')
    }
    throw new Error(`Releases 订阅流中暂无 ${UpdateApi.PLATFORM_SUFFIX} 版本`)
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