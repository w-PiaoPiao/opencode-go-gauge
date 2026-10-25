/**
 * hypium 测试套件 —— Android JUnit 用例的 ArkTS 移植:
 * QuotaParser / UsageParser / Fmt / 活跃账号策略 (纯逻辑, 无 UI/设备依赖)。
 */
import { describe, it, expect } from '@ohos/hypium'
import { QuotaParser } from '../main/ets/data/remote/QuotaParser'
import { UsageParser } from '../main/ets/data/remote/UsageParser'
import { Fmt } from '../main/ets/common/util/Fmt'
import { SyncDao } from '../main/ets/data/db/SyncDao'
import { Login } from '../main/ets/common/auth/Login'
import { UpdateApi } from '../main/ets/data/remote/UpdateApi'
import { OpenCodeApi } from '../main/ets/data/remote/OpenCodeApi'

const NOW_MS = 1752000000000

// ArkTS 禁止无类型对象字面量, fixture 一律拼 JSON 文本 (与线上响应体同构)
const GO_STATUS_JSON = '{"access":{"startsAt":"2025-07-08T00:00:00Z","endsAt":"2025-09-01T00:00:00Z",' +
  '"meters":{' +
  '"fiveHour":{"limitMicroCents":100000000000,"usedMicroCents":34500000000,"resetsAt":"2025-07-09T00:00:00Z"},' +
  '"week":{"limitMicroCents":100000000000,"usedMicroCents":12300000000,"resetsAt":"2025-07-14T00:00:00Z"},' +
  '"month":{"limitMicroCents":100000000000,"usedMicroCents":105700000000}}}}'

// 5h/周窗口空闲 (接口不给 resetsAt): 重置时间必须留空, 不能借月周期兜底
const GO_STATUS_IDLE_JSON = '{"access":{"endsAt":"2025-09-01T00:00:00Z","meters":{' +
  '"fiveHour":{"limitMicroCents":100000000000,"usedMicroCents":0},' +
  '"week":{"limitMicroCents":100000000000,"usedMicroCents":0},' +
  '"month":{"limitMicroCents":100000000000,"usedMicroCents":0}}}}'

const REQUEST_LOGS_JSON = '{"items":[' +
  '{"id":"usg_abc123","startedAt":1753773600000,"category":"inference",' +
  '"model":"deepseek-chat","provider":"deepseek","inputTokens":1234,"outputTokens":567,' +
  '"reasoningTokens":89,"cacheReadTokens":100,"cacheWriteTokens":75,"cost":0.12345678,' +
  '"serviceAPIKeyID":"key_1","sessionID":"ses_1","product":"lite"},' +
  '{"id":"usg_api999","startedAt":1753773601000,"category":"api","model":"console",' +
  '"provider":"opencode","inputTokens":0,"outputTokens":0,"reasoningTokens":0,' +
  '"cacheReadTokens":0,"cacheWriteTokens":0,"cost":0},' +
  '{"id":"usg_def456","startedAt":1753771300000,"category":"inference","model":"gpt-4o",' +
  '"provider":"openai","inputTokens":100,"outputTokens":200,"reasoningTokens":0,' +
  '"cacheReadTokens":0,"cacheWriteTokens":0,"cost":0.05,"serviceAPIKeyID":"","sessionID":"","product":""},' +
  '{"id":"usg_no_time","category":"inference","model":"x"}],' +
  '"nextCursor":"cur_2","retentionDays":30}'

/**
 * 活跃账号解析策略 —— 直接调用生产实现 SyncDao.resolveActive。
 * (此前这里复制了一份同名函数, 生产逻辑漂移时测试仍会通过。)
 */
function resolveActive(stored: number | null, pairs: Array<[number, boolean]>): number {
  return SyncDao.resolveActive(stored, pairs)
}

export default function ggTest() {
  describe('QuotaParserTest', () => {
    it('parses_all_three_windows_from_go_status_json', 0, () => {
      const windows = QuotaParser.parseGoStatusText(GO_STATUS_JSON, NOW_MS)
      expect(windows.length).assertEqual(3)
      const rolling = windows[0]
      expect(rolling.label).assertEqual('5h Rolling')
      expect(rolling.used).assertEqual(34.5)
      expect(rolling.remaining).assertEqual(65.5)
      const expectedSec = Math.max(0, Math.floor((Date.parse('2025-07-09T00:00:00Z') - NOW_MS) / 1000))
      expect(rolling.resetInSec).assertEqual(expectedSec)
      const weekly = windows[1]
      expect(weekly.label).assertEqual('Weekly')
      expect(weekly.used).assertEqual(12.3)
      expect(windows[2].label).assertEqual('Monthly')
    })

    it('clamps_usage_percent_to_0_100', 0, () => {
      const windows = QuotaParser.parseGoStatusText(GO_STATUS_JSON, NOW_MS)
      expect(windows[2].used).assertEqual(100.0)
      expect(windows[2].remaining).assertEqual(0.0)
    })

    it('monthly_window_falls_back_to_access_endsAt', 0, () => {
      const windows = QuotaParser.parseGoStatusText(GO_STATUS_JSON, NOW_MS)
      expect(windows[2].resetAt).assertEqual(new Date(Date.parse('2025-09-01T00:00:00Z')).toISOString())
    })

    it('idle_5h_window_keeps_reset_at_empty', 0, () => {
      // 5h/周窗口无 resetsAt = 窗口未开始: 留空, 不借月周期兜底
      const windows = QuotaParser.parseGoStatusText(GO_STATUS_IDLE_JSON, NOW_MS)
      expect(windows.length).assertEqual(3)
      expect(windows[0].resetAt).assertEqual('')
      expect(windows[0].resetInSec).assertEqual(0)
      expect(windows[2].resetAt).assertEqual(new Date(Date.parse('2025-09-01T00:00:00Z')).toISOString())
    })

    it('returns_empty_for_non_dict_or_missing_meters', 0, () => {
      expect(QuotaParser.parseGoStatusText('no json here', NOW_MS).length).assertEqual(0)
      expect(QuotaParser.parseGoStatusText('{}', NOW_MS).length).assertEqual(0)
      expect(QuotaParser.parseGoStatusText('{"access":{}}', NOW_MS).length).assertEqual(0)
    })
  })

  describe('UsageParserTest', () => {
    it('parses_request_logs_json_inference_only', 0, () => {
      const page = UsageParser.parseRequestLogsText(REQUEST_LOGS_JSON)
      expect(page.records.length).assertEqual(2)
      expect(page.nextCursor).assertEqual('cur_2')
      expect(page.retentionDays).assertEqual(30)
      const first = page.records[0]
      expect(first.usgId).assertEqual('usg_abc123')
      expect(first.createdAt).assertEqual(new Date(1753773600000).toISOString())
      expect(first.model).assertEqual('deepseek-chat')
      expect(first.provider).assertEqual('deepseek')
      expect(first.inputTokens).assertEqual(1234)
      expect(first.outputTokens).assertEqual(567)
      expect(first.reasoningTokens).assertEqual(89)
      expect(first.cacheReadTokens).assertEqual(100)
      expect(first.cacheWrite5mTokens).assertEqual(75)
      expect(first.cacheWrite1hTokens).assertEqual(0)
      expect(first.costRaw).assertEqual(12345678)
      expect(parseFloat((first.costRaw / 100000000.0).toFixed(9))).assertEqual(0.12345678)
      expect(first.keyId).assertEqual('key_1')
      expect(first.sessionId).assertEqual('ses_1')
      expect(first.plan).assertEqual('lite')
      const second = page.records[1]
      expect(second.usgId).assertEqual('usg_def456')
      expect(second.model).assertEqual('gpt-4o')
      expect(second.plan).assertEqual(null)
    })

    it('returns_empty_for_garbage_or_missing_items', 0, () => {
      expect(UsageParser.parseRequestLogsText('no records here').records.length).assertEqual(0)
      expect(UsageParser.parseRequestLogsText('{}').records.length).assertEqual(0)
    })

    it('skips_records_without_id_or_startedAt', 0, () => {
      // ArkTS 禁止无类型对象字面量, 这里直接拼 JSON 文本
      const text = '{"items":[' +
        '{"id":"usg_no_time","category":"inference","model":"x","startedAt":0},' +
        '{"category":"inference","model":"y","startedAt":1753773600000}]}'
      expect(UsageParser.parseRequestLogsText(text).records.length).assertEqual(0)
    })
  })

  describe('CookieHeaderTest', () => {
    it('pure_value_becomes_new_session_cookie', 0, () => {
      expect(OpenCodeApi.buildCookieHeader('st_abc')).assertEqual('__Host-console_session=st_abc')
    })

    it('new_and_legacy_cookie_segments_pass_through', 0, () => {
      expect(OpenCodeApi.buildCookieHeader('__Host-console_session=st_abc'))
        .assertEqual('__Host-console_session=st_abc')
      expect(OpenCodeApi.buildCookieHeader('a=1; auth=Fe26; b=2')).assertEqual('auth=Fe26')
    })

    it('cookie_prefix_is_stripped', 0, () => {
      expect(OpenCodeApi.buildCookieHeader('Cookie: __Host-console_session=st_abc'))
        .assertEqual('__Host-console_session=st_abc')
    })
  })

  describe('FmtTest', () => {
    it('tokens_abbreviation', 0, () => {
      expect(Fmt.tokens(1.2e9)).assertEqual('1.20B')
      expect(Fmt.tokens(3450000)).assertEqual('3.45M')
      expect(Fmt.tokens(5600)).assertEqual('5.6k')
      expect(Fmt.tokens(999)).assertEqual('999')
      expect(Fmt.tokens(0)).assertEqual('0')
      expect(Fmt.tokens(-5)).assertEqual('-5')
    })

    it('int_grouping', 0, () => {
      expect(Fmt.int(1234567)).assertEqual('1,234,567')
      expect(Fmt.int(0)).assertEqual('0')
    })

    it('money_cny', 0, () => {
      expect(Fmt.money(1.0, 'CNY', 7.2)).assertEqual('¥7.20')
      expect(Fmt.money(0.001, 'CNY', 7.2)).assertEqual('¥0.0072')
      expect(Fmt.money(0.0000001, 'CNY', 7.2)).assertEqual('¥0.0000')
    })

    it('money_usd', 0, () => {
      expect(Fmt.money(1.0, 'USD', 7.2)).assertEqual('$1.00')
      expect(Fmt.money(0.12345, 'USD', 7.2)).assertEqual('$0.1235')
      expect(Fmt.money(0.0, 'USD', 7.2)).assertEqual('$0')
    })

    it('duration', 0, () => {
      expect(Fmt.dur(2 * 86400 + 3 * 3600, '天', '小时', '分钟', '即将重置')).assertEqual('2 天 3 小时')
      expect(Fmt.dur(5400, '天', '小时', '分钟', '即将重置')).assertEqual('1 小时 30 分钟')
      expect(Fmt.dur(300, '天', '小时', '分钟', '即将重置')).assertEqual('5 分钟')
      expect(Fmt.dur(0, '天', '小时', '分钟', '即将重置')).assertEqual('即将重置')
      expect(Fmt.dur(-10, '天', '小时', '分钟', '即将重置')).assertEqual('即将重置')
    })

    it('relative_time', 0, () => {
      const now = Date.now()
      expect(Fmt.relative(new Date(now - 10000).toISOString(), '刚刚', '分钟前', '小时前', '天前', '从未同步'))
        .assertEqual('刚刚')
      expect(Fmt.relative(new Date(now - 180000).toISOString(), '刚刚', '分钟前', '小时前', '天前', '从未同步'))
        .assertEqual('3 分钟前')
      expect(Fmt.relative(new Date(now - 7200000).toISOString(), '刚刚', '分钟前', '小时前', '天前', '从未同步'))
        .assertEqual('2 小时前')
      expect(Fmt.relative(new Date(now - 90000000).toISOString(), '刚刚', '分钟前', '小时前', '天前', '从未同步'))
        .assertEqual('1 天前')
      expect(Fmt.relative(null, '刚刚', '分钟前', '小时前', '天前', '从未同步')).assertEqual('从未同步')
    })

    it('mask_workspace', 0, () => {
      expect(Fmt.maskWs('wrk_abcdefghijklmnop')).assertEqual('wrk_abcd…')
      expect(Fmt.maskWs('wrk_123')).assertEqual('wrk_123')
    })
  })

  describe('ActiveAccountPolicyTest', () => {
    it('stored_logged_in_kept', 0, () => {
      expect(resolveActive(2, [[1, true], [2, true]])).assertEqual(2)
    })

    it('stored_logged_out_yields_to_min_logged_in', 0, () => {
      expect(resolveActive(1, [[1, false], [3, true], [5, true]])).assertEqual(3)
    })

    it('all_logged_out_keeps_stored', 0, () => {
      expect(resolveActive(2, [[1, false], [2, false]])).assertEqual(2)
    })

    it('no_stored_prefers_min_logged_in', 0, () => {
      expect(resolveActive(null, [[4, false], [7, true], [9, true]])).assertEqual(7)
    })

    it('missing_stored_row_falls_back', 0, () => {
      expect(resolveActive(99, [[1, true]])).assertEqual(1)
    })

    it('nothing_at_all_returns_zero', 0, () => {
      expect(resolveActive(null, [])).assertEqual(0)
    })

    it('no_stored_no_logged_in_uses_min_any_id', 0, () => {
      expect(resolveActive(null, [[3, false], [8, false]])).assertEqual(3)
    })
  })

  describe('LoginEntryTest', () => {
    it('builds_console_login_url', 0, () => {
      // 2026-09 改版: 旧授权页 auth.opencode.ai/authorize 已下线, 入口即控制台登录页
      expect(Login.buildLoginUrl()).assertEqual('https://opencode.ai/console/login?next=%2Fconsole%2F')
    })

    it('new_session_cookie_takes_priority_over_legacy', 0, () => {
      expect(Login.extractAuthCookie('__Host-console_session=st_new; auth=Fe26_old'))
        .assertEqual('__Host-console_session=st_new')
      expect(Login.extractAuthCookie('auth=Fe26_old')).assertEqual('auth=Fe26_old')
      expect(Login.extractAuthCookie('other=1')).assertEqual('')
    })

    it('workspace_hint_matches_console_and_workspace_paths', 0, () => {
      expect(Login.extractWorkspaceHint('https://opencode.ai/console/wrk_abc')).assertEqual('wrk_abc')
      expect(Login.extractWorkspaceHint('https://opencode.ai/workspace/wrk_xyz')).assertEqual('wrk_xyz')
      expect(Login.extractWorkspaceHint('https://opencode.ai/console/')).assertEqual('Default')
    })
  })

  describe('LoginDomainTest', () => {
    it('accepts_opencode_root_and_subdomains', 0, () => {
      expect(Login.isOnOpencodeDomain('https://opencode.ai/workspace/x')).assertTrue()
      expect(Login.isOnOpencodeDomain('https://app.opencode.ai/x')).assertTrue()
    })

    it('rejects_lookalike_host_prefix', 0, () => {
      // 回归: 旧实现用 url.startsWith('https://opencode.ai') 判前缀,
      // 会把该钓鱼域名当成同域并启动 cookie 轮询
      expect(Login.isOnOpencodeDomain('https://opencode.ai.evil.com/x')).assertFalse()
      expect(Login.isOnOpencodeDomain('https://notopencode.ai/x')).assertFalse()
    })

    it('rejects_empty_and_other_hosts', 0, () => {
      expect(Login.isOnOpencodeDomain('')).assertFalse()
      expect(Login.isOnOpencodeDomain('https://example.com/')).assertFalse()
    })
  })

  describe('UpdatePlatformTagTest', () => {
    it('accepts_harmony_tags_only', 0, () => {
      // 仓库 Latest 是全平台共享标记: 其他平台的 release 必须被过滤掉,
      // 否则会弹出错误更新提示且 releaseUrl 指向别的平台
      expect(UpdateApi.isPlatformTag('v2.1.0-harmony')).assertTrue()
      expect(UpdateApi.isPlatformTag('v2.1.0b-harmony')).assertTrue()
      expect(UpdateApi.isPlatformTag('v2.1.0-android')).assertFalse()
      expect(UpdateApi.isPlatformTag('v2.1.0-macos')).assertFalse()
      expect(UpdateApi.isPlatformTag('v2.1.0')).assertFalse()
    })

    it('letter_suffix_orders_after_plain_release', 0, () => {
      // 2.1.0b > 2.1.0 (desktop updater.py 同规则)
      const plain = UpdateApi.parseVersion('2.1.0')!
      const suffixed = UpdateApi.parseVersion('2.1.0b')!
      expect(UpdateApi.isNewer(suffixed, plain)).assertTrue()
      expect(UpdateApi.isNewer(plain, suffixed)).assertFalse()
    })

    it('platform_suffix_ignored_in_comparison', 0, () => {
      const a = UpdateApi.parseVersion('v2.1.0b-harmony')!
      const b = UpdateApi.parseVersion('2.1.0b')!
      expect(UpdateApi.isNewer(a, b)).assertFalse()
      expect(UpdateApi.isNewer(b, a)).assertFalse()
    })

    it('rejects_malformed_versions', 0, () => {
      expect(UpdateApi.parseVersion('not-a-version') === null).assertTrue()
      expect(UpdateApi.parseVersion('v2.1-harmony') === null).assertTrue()
    })
  })
}