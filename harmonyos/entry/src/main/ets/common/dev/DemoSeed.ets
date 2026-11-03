/**
 * 演示数据 seed（仅 debug 构建）—— 上架截图流水线 & 无账号时的本地预览。
 *
 * 做三件事：
 * 1) 若无账号：创建一个本地 demo 账号（假 token，不会真的同步成功）；
 * 2) 若本地几乎无用量记录：注入 180 天模拟用量（见 Repo.injectSampleData，覆盖热力图窗口）；
 * 3) 注入 3 个配额窗口（Repo.setDemoQuota），让首页配额卡在离线时也有数据。
 *
 * 幂等：重复启动不会重复注入/重复建账号。release 构建下直接返回，不产生副作用。
 */
import BuildProfile from 'BuildProfile'
import { Repo } from '../../data/repository/DashboardRepository'
import { AppPrefs } from '../store/AppPrefs'
import { DashboardData, QuotaResult, QuotaWindow } from '../model/Models'

export class DemoSeed {
  /** 应用演示模式：语言/主题 + 账号 + 数据 + 配额。返回是否成功进入演示态。 */
  static async run(): Promise<boolean> {
    if (!BuildProfile.DEBUG) {
      return false
    }
    try {
      const repo = Repo.get()
      const accounts = await repo.accounts()
      let hasLogged: boolean = false
      for (const a of accounts) {
        if (a.hasToken) {
          hasLogged = true
        }
      }
      if (accounts.length === 0) {
        await repo.loginSuccess('demo-preview-token', 'OpenCode Go', 'add')
      } else if (!hasLogged) {
        // 首次建库会种一个 token 为空的占位账号（id=1）：直接给活跃占位账号写入
        // demo 凭证，否则 loggedIn 恒为 false、demo 模式会停在欢迎页。
        await repo.switchAccount(accounts[0].id)
        await repo.loginSuccess('demo-preview-token', 'OpenCode Go', 'relogin')
        await repo.renameAccount(accounts[0].id, 'OpenCode Go')
      } else {
        // 已有可用账号：直接复用（seed 过就切到第一个）
        await repo.switchAccount(accounts[0].id)
      }
      const dash: DashboardData = await repo.loadDashboard('all')
      if (dash.totals.requestCount < 20) {
        await repo.injectSampleData(180)
      }
      repo.setDemoQuota(DemoSeed.demoQuota())
      // 演示账号没有有效凭证：自动同步保持「开」但把间隔拉到 30 分钟（截图期间不会触发），
      // 避免设置页出现一个「关」的开关看起来像缺陷；即便触发，同步失败只静默忽略。
      const s = await repo.settings()
      s.autoSync = true
      s.syncIntervalSec = 1800
      await repo.saveSettings(s)
      return true
    } catch (e) {
      return false
    }
  }

  /** 语言 / 主题（来自 --ps 参数）—— 仅 debug 构建生效。 */
  static applyAppearance(lang: string, theme: string): void {
    if (!BuildProfile.DEBUG) {
      return
    }
    if (lang === 'zh' || lang === 'en') {
      AppPrefs.setLanguage(lang)
    }
    if (theme === 'light') {
      AppPrefs.setDarkMode(false)
    } else if (theme === 'dark') {
      AppPrefs.setDarkMode(true)
    }
  }

  /** 与首页三张配额卡一致的真实形态数据（不写库，仅内存）。 */
  static demoQuota(): QuotaResult {
    const now = Date.now()
    const windows: QuotaWindow[] = [
      DemoSeed.window('5h Rolling', 43, now + 2 * 3600 * 1000 + 13 * 60 * 1000, 'hours'),
      DemoSeed.window('Weekly', 21, now + 4 * 86400 * 1000 + 7 * 3600 * 1000, 'hours'),
      DemoSeed.window('Monthly', 68, now + 12 * 86400 * 1000 + 5 * 3600 * 1000, 'hours'),
    ]
    return {
      name: 'OpenCode Go',
      workspaceId: 'Default',
      success: true,
      updatedAt: new Date(now).toISOString(),
      windows: windows,
      error: null,
    }
  }

  private static window(label: string, used: number, resetMs: number, unit: string): QuotaWindow {
    const resetInSec = Math.max(0, Math.floor((resetMs - Date.now()) / 1000))
    return {
      label: label,
      used: used,
      remaining: 100 - used,
      total: 100,
      unit: unit,
      resetAt: new Date(resetMs).toISOString(),
      resetInSec: resetInSec,
    }
  }
}
