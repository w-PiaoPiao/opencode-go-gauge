import { describe, it, expect } from "@package:pkg_modules/.ohpm/@ohos+hypium@1.0.18/pkg_modules/@ohos/hypium/index";
import { QuotaParser } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/remote/QuotaParser";
import { UsageParser } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/remote/UsageParser";
import { Fmt } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/common/util/Fmt";
const QUOTA_HTML = `
<html><body>
<script>
window.__APP_DATA__ = {};
var $R = [];
// usagePercent first
rollingUsage: $R[12] = {usagePercent: 34.5, resetInSec: 43199, isActive: true, something: "x"};
// resetInSec first
weeklyUsage: $R[13] = {resetInSec: 518400, usagePercent: 12.3, isActive: true};
// usagePercent first, negative guard value
monthlyUsage: $R[14] = {usagePercent: 105.7, resetInSec: 15552000, isActive: true};
</script>
</body></html>`;
const USAGE_RESPONSE = `
window.__SERVER_DATA__ = {ok: true};
const $R = [];
$R[0] = {version: 1};
$R[1] = {id: "usg_abc123", timeCreated: $R[2] = new Date("2025-08-01T10:00:00.000Z"), model: "deepseek-chat", provider: "deepseek", inputTokens: 1234, outputTokens: 567, reasoningTokens: 89, cacheReadTokens: 100, cacheWrite5mTokens: 50, cacheWrite1hTokens: 25, cost: 12345678, keyID: "key_1", sessionID: "ses_1", enrichment:$R[3]={plan:"lite"}};
$R[4] = {id:"usg_def456",timeCreated:$R[5]=new Date("2025-08-01T09:30:00.000Z"),model:"gpt-4o",provider:"openai",inputTokens:100,outputTokens:200,reasoningTokens:0,cacheReadTokens:0,cacheWrite5mTokens:0,cacheWrite1hTokens:0,cost:5000000,keyID:"key_2",sessionID:""};
$R[6] = {id: "usg_ghi789", timeCreated: $R[7] = new Date("2025-08-01T08:00:00.000Z"), model: "glm-4", provider: "zhipu", inputTokens: null, outputTokens: 0, reasoningTokens: null, cacheReadTokens: 0, cacheWrite5mTokens: 0, cacheWrite1hTokens: 0, cost: 0, keyID: "", sessionID: ""};`;
/** 活跃账号解析策略 —— desktop db.get_active_account_id 决策逻辑 parity。 */
function resolveActive(stored: number | null, pairs: Array<[
    number,
    boolean
]>): number {
    let loggedMin = 0;
    for (const a of pairs) {
        if (a[1] && (loggedMin === 0 || a[0] < loggedMin)) {
            loggedMin = a[0];
        }
    }
    if (stored !== null && stored > 0) {
        let row: [
            number,
            boolean
        ] | null = null;
        for (const a of pairs) {
            if (a[0] === stored) {
                row = a;
                break;
            }
        }
        if (row !== null) {
            if (row[1]) {
                return stored;
            }
            if (loggedMin !== 0) {
                return loggedMin;
            }
            return stored;
        }
    }
    if (loggedMin !== 0) {
        return loggedMin;
    }
    let fallback = 0;
    for (const a of pairs) {
        if (fallback === 0 || a[0] < fallback) {
            fallback = a[0];
        }
    }
    return fallback;
}
export default function ggTest() {
    describe('QuotaParserTest', () => {
        it('parses_all_three_windows_both_field_orders', 0, () => {
            const windows = QuotaParser.parseQuotaHtml(QUOTA_HTML, 1752000000000);
            expect(windows.length).assertEqual(3);
            const rolling = windows[0];
            expect(rolling.label).assertEqual('5h Rolling');
            expect(rolling.used).assertEqual(34.5);
            expect(rolling.remaining).assertEqual(65.5);
            expect(rolling.resetInSec).assertEqual(43199);
            const weekly = windows[1];
            expect(weekly.label).assertEqual('Weekly');
            expect(weekly.used).assertEqual(12.3);
            expect(weekly.resetInSec).assertEqual(518400);
            expect(windows[2].label).assertEqual('Monthly');
        });
        it('clamps_usage_percent_to_0_100', 0, () => {
            const windows = QuotaParser.parseQuotaHtml(QUOTA_HTML);
            const monthly = windows[2];
            expect(monthly.used).assertEqual(100.0);
            expect(monthly.remaining).assertEqual(0.0);
        });
        it('returns_empty_when_no_markers', 0, () => {
            expect(QuotaParser.parseQuotaHtml('<html><body>nothing here</body></html>').length).assertEqual(0);
        });
        it('resetAt_is_now_plus_resetInSec', 0, () => {
            const windows = QuotaParser.parseQuotaHtml(QUOTA_HTML, 1752000000000);
            const expected = new Date(1752000000000 + 43199 * 1000).toISOString();
            expect(windows[0].resetAt).assertEqual(expected);
        });
    });
    describe('UsageParserTest', () => {
        it('parses_records_in_both_get_and_post_formats', 0, () => {
            const records = UsageParser.parseUsageResponse(USAGE_RESPONSE);
            expect(records.length).assertEqual(3);
            const first = records[0];
            expect(first.usgId).assertEqual('usg_abc123');
            expect(first.createdAt).assertEqual('2025-08-01T10:00:00.000Z');
            expect(first.model).assertEqual('deepseek-chat');
            expect(first.provider).assertEqual('deepseek');
            expect(first.inputTokens).assertEqual(1234);
            expect(first.outputTokens).assertEqual(567);
            expect(first.reasoningTokens).assertEqual(89);
            expect(first.cacheReadTokens).assertEqual(100);
            expect(first.cacheWrite5mTokens).assertEqual(50);
            expect(first.cacheWrite1hTokens).assertEqual(25);
            expect(first.costRaw).assertEqual(12345678);
            expect(parseFloat((first.costRaw / 100000000.0).toFixed(9))).assertEqual(0.12345678);
            expect(first.keyId).assertEqual('key_1');
            expect(first.sessionId).assertEqual('ses_1');
            expect(first.plan).assertEqual('lite');
            const second = records[1];
            expect(second.usgId).assertEqual('usg_def456');
            expect(second.model).assertEqual('gpt-4o');
            expect(second.inputTokens).assertEqual(100);
            expect(second.plan).assertEqual(null);
            const third = records[2];
            expect(third.usgId).assertEqual('usg_ghi789');
            expect(third.inputTokens).assertEqual(0);
            expect(third.reasoningTokens).assertEqual(0);
        });
        it('returns_empty_for_garbage', 0, () => {
            expect(UsageParser.parseUsageResponse('no records here').length).assertEqual(0);
        });
        it('skips_records_without_timeCreated', 0, () => {
            const text = `const $R = [];
$R[1] = {id: "usg_no_time", model: "x", inputTokens: 1, outputTokens: 1};`;
            expect(UsageParser.parseUsageResponse(text).length).assertEqual(0);
        });
    });
    describe('FmtTest', () => {
        it('tokens_abbreviation', 0, () => {
            expect(Fmt.tokens(1.2e9)).assertEqual('1.20B');
            expect(Fmt.tokens(3450000)).assertEqual('3.45M');
            expect(Fmt.tokens(5600)).assertEqual('5.6k');
            expect(Fmt.tokens(999)).assertEqual('999');
            expect(Fmt.tokens(0)).assertEqual('0');
            expect(Fmt.tokens(-5)).assertEqual('-5');
        });
        it('int_grouping', 0, () => {
            expect(Fmt.int(1234567)).assertEqual('1,234,567');
            expect(Fmt.int(0)).assertEqual('0');
        });
        it('money_cny', 0, () => {
            expect(Fmt.money(1.0, 'CNY', 7.2)).assertEqual('¥7.20');
            expect(Fmt.money(0.001, 'CNY', 7.2)).assertEqual('¥0.0072');
            expect(Fmt.money(0.0000001, 'CNY', 7.2)).assertEqual('¥0.0000');
        });
        it('money_usd', 0, () => {
            expect(Fmt.money(1.0, 'USD', 7.2)).assertEqual('$1.00');
            expect(Fmt.money(0.12345, 'USD', 7.2)).assertEqual('$0.1235');
            expect(Fmt.money(0.0, 'USD', 7.2)).assertEqual('$0');
        });
        it('duration', 0, () => {
            expect(Fmt.dur(2 * 86400 + 3 * 3600, '天', '小时', '分钟', '即将重置')).assertEqual('2 天 3 小时');
            expect(Fmt.dur(5400, '天', '小时', '分钟', '即将重置')).assertEqual('1 小时 30 分钟');
            expect(Fmt.dur(300, '天', '小时', '分钟', '即将重置')).assertEqual('5 分钟');
            expect(Fmt.dur(0, '天', '小时', '分钟', '即将重置')).assertEqual('即将重置');
            expect(Fmt.dur(-10, '天', '小时', '分钟', '即将重置')).assertEqual('即将重置');
        });
        it('relative_time', 0, () => {
            const now = Date.now();
            expect(Fmt.relative(new Date(now - 10000).toISOString(), '刚刚', '分钟前', '小时前', '天前', '从未同步'))
                .assertEqual('刚刚');
            expect(Fmt.relative(new Date(now - 180000).toISOString(), '刚刚', '分钟前', '小时前', '天前', '从未同步'))
                .assertEqual('3 分钟前');
            expect(Fmt.relative(new Date(now - 7200000).toISOString(), '刚刚', '分钟前', '小时前', '天前', '从未同步'))
                .assertEqual('2 小时前');
            expect(Fmt.relative(new Date(now - 90000000).toISOString(), '刚刚', '分钟前', '小时前', '天前', '从未同步'))
                .assertEqual('1 天前');
            expect(Fmt.relative(null, '刚刚', '分钟前', '小时前', '天前', '从未同步')).assertEqual('从未同步');
        });
        it('mask_workspace', 0, () => {
            expect(Fmt.maskWs('wrk_abcdefghijklmnop')).assertEqual('wrk_abcd…');
            expect(Fmt.maskWs('wrk_123')).assertEqual('wrk_123');
        });
    });
    describe('ActiveAccountPolicyTest', () => {
        it('stored_logged_in_kept', 0, () => {
            expect(resolveActive(2, [[1, true], [2, true]])).assertEqual(2);
        });
        it('stored_logged_out_yields_to_min_logged_in', 0, () => {
            expect(resolveActive(1, [[1, false], [3, true], [5, true]])).assertEqual(3);
        });
        it('all_logged_out_keeps_stored', 0, () => {
            expect(resolveActive(2, [[1, false], [2, false]])).assertEqual(2);
        });
        it('no_stored_prefers_min_logged_in', 0, () => {
            expect(resolveActive(null, [[4, false], [7, true], [9, true]])).assertEqual(7);
        });
        it('missing_stored_row_falls_back', 0, () => {
            expect(resolveActive(99, [[1, true]])).assertEqual(1);
        });
        it('nothing_at_all_returns_zero', 0, () => {
            expect(resolveActive(null, [])).assertEqual(0);
        });
        it('no_stored_no_logged_in_uses_min_any_id', 0, () => {
            expect(resolveActive(null, [[3, false], [8, false]])).assertEqual(3);
        });
    });
}
