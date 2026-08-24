import type { QuotaWindow } from '../../common/model/Models';
class BjcCov {
    coverage: {
        [key: string]: string | number;
    };
    constructor(covData: object) {
        const gcv = "__coverage__";
        let coverage = globalThis[gcv] || (globalThis[gcv] = {});
        if (!coverage[covData.path] && true) {
            coverage[covData.path] = covData;
        }
        this.coverage = coverage[covData.path];
    }
    instrumentFunction(func: number) {
        this.coverage.functions[func].count++;
        this.coverage.functions[func].regions[0].count++;
    }
    instrumentRegion(func: number, region: number) {
        this.coverage.functions[func].regions[region].count++;
    }
    instrumentReturn(func: number, retIdx: number) {
        this.coverage.functions[func].returnes[retIdx].count++;
    }
    instrumentBranch(func: number, branch: number, trueOrFalse: boolean) {
        if (trueOrFalse) {
            this.coverage.functions[func].branches[branch].trueCount++;
            for (let r of Object.values(this.coverage.functions[func].branches[branch].group)) {
                if (r !== branch) {
                    this.coverage.functions[func].branches[r as number].falseCount++;
                }
            }
        }
        else {
            this.coverage.functions[func].branches[branch].falseCount++;
        }
    }
}
let bjccovmt7djy4k = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/remote/QuotaParser.ets", hash: "9eeef14f44bad85affeb4b05407e89fa8567c0c94d56361f1d10936215371658", lineCnt: 79, count: 0, projectPath: "", functions: { 0: { name: "QuotaParser.clampPercent", count: 0, regions: { 0: { startLoc: { line: 32, col: 3 }, endLoc: { line: 34, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 33, col: 5 }, endLoc: { line: 34, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "QuotaParser.toNum", count: 0, regions: { 0: { startLoc: { line: 36, col: 3 }, endLoc: { line: 42, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 37, col: 58 }, endLoc: { line: 39, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 40, col: 5 }, endLoc: { line: 42, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 37, col: 9 }, endLoc: { line: 37, col: 56 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 41, col: 12 }, endLoc: { line: 41, col: 42 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 1 }, 2: { name: "QuotaParser.parseWindow", count: 0, regions: { 0: { startLoc: { line: 44, col: 3 }, endLoc: { line: 54, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 46, col: 21 }, endLoc: { line: 48, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 50, col: 22 }, endLoc: { line: 52, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 53, col: 5 }, endLoc: { line: 54, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 46, col: 9 }, endLoc: { line: 46, col: 19 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 50, col: 9 }, endLoc: { line: 50, col: 20 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 }, 3: { name: "QuotaParser.parseQuotaHtml", count: 0, regions: { 0: { startLoc: { line: 57, col: 3 }, endLoc: { line: 78, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 59, col: 5 }, endLoc: { line: 76, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 61, col: 28 }, endLoc: { line: 63, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 77, col: 5 }, endLoc: { line: 78, col: 4 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 64, col: 7 }, endLoc: { line: 76, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 61, col: 11 }, endLoc: { line: 61, col: 26 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 3 } }, exeLine: { 0: 6, 1: 8, 2: 9, 3: 10, 4: 11, 5: 13, 6: 14, 7: 15, 8: 16, 9: 17, 10: 18, 11: 19, 12: 20, 13: 21, 14: 22, 15: 23, 16: 24, 17: 26, 18: 27, 19: 28, 20: 29, 21: 32, 22: 33, 23: 36, 24: 37, 25: 38, 26: 40, 27: 41, 28: 44, 29: 45, 30: 46, 31: 47, 32: 49, 33: 50, 34: 51, 35: 53, 36: 57, 37: 58, 38: 59, 39: 60, 40: 61, 41: 62, 42: 64, 43: 65, 44: 66, 45: 67, 46: 68, 47: 69, 48: 70, 49: 71, 50: 72, 51: 73, 52: 74, 53: 77 } });
export class QuotaParser {
    private static readonly LABEL_ROLLING = '5h Rolling';
    private static readonly LABEL_WEEKLY = 'Weekly';
    private static readonly LABEL_MONTHLY = 'Monthly';
    private static readonly ROLLING_PCT_FIRST = /rollingUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/;
    private static readonly ROLLING_RESET_FIRST = /rollingUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/;
    private static readonly WEEKLY_PCT_FIRST = /weeklyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/;
    private static readonly WEEKLY_RESET_FIRST = /weeklyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/;
    private static readonly MONTHLY_PCT_FIRST = /monthlyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/;
    private static readonly MONTHLY_RESET_FIRST = /monthlyUsage:\s*\$R\[\d+\]\s*=\s*\{[^}]*resetInSec\s*:\s*(-?\d+(?:\.\d+)?)[^}]*usagePercent\s*:\s*(-?\d+(?:\.\d+)?)[^}]*\}/;
    private static readonly PAIRS: Array<[
        string,
        RegExp,
        RegExp
    ]> = [
        [QuotaParser.LABEL_ROLLING, QuotaParser.ROLLING_PCT_FIRST, QuotaParser.ROLLING_RESET_FIRST],
        [QuotaParser.LABEL_WEEKLY, QuotaParser.WEEKLY_PCT_FIRST, QuotaParser.WEEKLY_RESET_FIRST],
        [QuotaParser.LABEL_MONTHLY, QuotaParser.MONTHLY_PCT_FIRST, QuotaParser.MONTHLY_RESET_FIRST],
    ];
    private static clampPercent(v: number): number {
        bjccovmt7djy4k.instrumentFunction(0);
        bjccovmt7djy4k.instrumentRegion(0, 1);
        return Math.min(100.0, Math.max(0.0, v));
    }
    private static toNum(g: string | undefined, fallback: number): number {
        bjccovmt7djy4k.instrumentFunction(1);
        if (g === undefined || g === null || g.length === 0) {
            bjccovmt7djy4k.instrumentBranch(1, 0, true);
            bjccovmt7djy4k.instrumentRegion(1, 1);
            return fallback;
        }
        else {
            bjccovmt7djy4k.instrumentBranch(1, 0, false);
        }
        bjccovmt7djy4k.instrumentRegion(1, 2);
        const n = Number(g);
        return Number.isNaN(n) ? (bjccovmt7djy4k.instrumentBranch(1, 1, true), fallback) : (bjccovmt7djy4k.instrumentBranch(1, 1, false), n);
    }
    private static parseWindow(pctRe: RegExp, resetRe: RegExp, html: string): [
        number,
        number
    ] | null {
        bjccovmt7djy4k.instrumentFunction(2);
        const m = pctRe.exec(html);
        if (m !== null) {
            bjccovmt7djy4k.instrumentBranch(2, 0, true);
            bjccovmt7djy4k.instrumentRegion(2, 1);
            return [QuotaParser.toNum(m[1], 0), QuotaParser.toNum(m[2], 0)];
        }
        else {
            bjccovmt7djy4k.instrumentBranch(2, 0, false);
        }
        const m2 = resetRe.exec(html);
        if (m2 !== null) {
            bjccovmt7djy4k.instrumentBranch(2, 1, true);
            bjccovmt7djy4k.instrumentRegion(2, 2);
            return [QuotaParser.toNum(m2[2], 0), QuotaParser.toNum(m2[1], 0)];
        }
        else {
            bjccovmt7djy4k.instrumentBranch(2, 1, false);
        }
        bjccovmt7djy4k.instrumentRegion(2, 3);
        return null;
    }
    /** 从 Dashboard HTML 解析配额窗口。nowMs = 当前 UTC epoch 毫秒。 */
    static parseQuotaHtml(html: string, nowMs: number = Date.now()): QuotaWindow[] {
        bjccovmt7djy4k.instrumentFunction(3);
        const windows: QuotaWindow[] = [];
        for (const pair of QuotaParser.PAIRS) {
            bjccovmt7djy4k.instrumentRegion(3, 1);
            const parsed = QuotaParser.parseWindow(pair[1], pair[2], html);
            if (parsed === null) {
                bjccovmt7djy4k.instrumentBranch(3, 0, true);
                bjccovmt7djy4k.instrumentRegion(3, 2);
                continue;
            }
            else {
                bjccovmt7djy4k.instrumentBranch(3, 0, false);
            }
            bjccovmt7djy4k.instrumentRegion(3, 4);
            const used: number = QuotaParser.clampPercent(parsed[0]);
            const resetIn: number = Math.max(0, parsed[1]);
            const resetAt: string = new Date(nowMs + resetIn * 1000).toISOString();
            windows.push({
                label: pair[0],
                used: used,
                remaining: Math.round((100.0 - used) * 10) / 10.0,
                total: 100.0,
                unit: '%',
                resetAt: resetAt,
                resetInSec: resetIn,
            });
        }
        bjccovmt7djy4k.instrumentRegion(3, 3);
        return windows;
    }
}
