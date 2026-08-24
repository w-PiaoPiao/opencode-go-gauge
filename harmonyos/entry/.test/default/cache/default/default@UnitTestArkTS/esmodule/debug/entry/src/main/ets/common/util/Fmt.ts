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
let bjccovmt7djy4s = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/common/util/Fmt.ets", hash: "c160cd2d4e4427867196ae486a3d31ba3d92655cdc716ca23f7bc44f44a97746", lineCnt: 126, count: 0, projectPath: "", functions: { 0: { name: "Fmt.tokens", count: 0, regions: { 0: { startLoc: { line: 7, col: 3 }, endLoc: { line: 19, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 9, col: 19 }, endLoc: { line: 11, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 12, col: 19 }, endLoc: { line: 14, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 15, col: 19 }, endLoc: { line: 17, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 18, col: 5 }, endLoc: { line: 19, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 9, col: 9 }, endLoc: { line: 9, col: 17 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 12, col: 9 }, endLoc: { line: 12, col: 17 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 15, col: 9 }, endLoc: { line: 15, col: 17 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 0 }, 1: { name: "Fmt.int", count: 0, regions: { 0: { startLoc: { line: 22, col: 3 }, endLoc: { line: 34, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 26, col: 5 }, endLoc: { line: 32, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 29, col: 37 }, endLoc: { line: 31, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 33, col: 5 }, endLoc: { line: 34, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 29, col: 11 }, endLoc: { line: 29, col: 35 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 1 }, 2: { name: "Fmt.money", count: 0, regions: { 0: { startLoc: { line: 37, col: 3 }, endLoc: { line: 50, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 39, col: 29 }, endLoc: { line: 42, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 43, col: 17 }, endLoc: { line: 45, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 46, col: 16 }, endLoc: { line: 48, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 49, col: 5 }, endLoc: { line: 50, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 39, col: 9 }, endLoc: { line: 39, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 41, col: 21 }, endLoc: { line: 41, col: 57 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 43, col: 9 }, endLoc: { line: 43, col: 15 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 46, col: 9 }, endLoc: { line: 46, col: 14 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 }, 3: { name: "Fmt.dur", count: 0, regions: { 0: { startLoc: { line: 53, col: 3 }, endLoc: { line: 68, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 58, col: 16 }, endLoc: { line: 60, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 61, col: 16 }, endLoc: { line: 63, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 64, col: 16 }, endLoc: { line: 66, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 67, col: 5 }, endLoc: { line: 68, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 58, col: 9 }, endLoc: { line: 58, col: 14 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 61, col: 9 }, endLoc: { line: 61, col: 14 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 64, col: 9 }, endLoc: { line: 64, col: 14 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 3 }, 4: { name: "Fmt.dateTime", count: 0, regions: { 0: { startLoc: { line: 71, col: 3 }, endLoc: { line: 81, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 72, col: 43 }, endLoc: { line: 74, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 76, col: 36 }, endLoc: { line: 78, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 79, col: 5 }, endLoc: { line: 81, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 72, col: 9 }, endLoc: { line: 72, col: 41 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 76, col: 9 }, endLoc: { line: 76, col: 34 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 4 }, 5: { name: "Fmt.dateTimeShort", count: 0, regions: { 0: { startLoc: { line: 84, col: 3 }, endLoc: { line: 94, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 85, col: 43 }, endLoc: { line: 87, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 89, col: 36 }, endLoc: { line: 91, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 92, col: 5 }, endLoc: { line: 94, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 85, col: 9 }, endLoc: { line: 85, col: 41 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 89, col: 9 }, endLoc: { line: 89, col: 34 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 5 }, 6: { name: "Fmt.pad2", count: 0, regions: { 0: { startLoc: { line: 96, col: 3 }, endLoc: { line: 98, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 97, col: 5 }, endLoc: { line: 98, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 97, col: 12 }, endLoc: { line: 97, col: 37 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 6 }, 7: { name: "Fmt.relative", count: 0, regions: { 0: { startLoc: { line: 101, col: 3 }, endLoc: { line: 120, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 102, col: 43 }, endLoc: { line: 104, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 106, col: 26 }, endLoc: { line: 108, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 110, col: 20 }, endLoc: { line: 112, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 113, col: 22 }, endLoc: { line: 115, col: 6 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 116, col: 23 }, endLoc: { line: 118, col: 6 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 119, col: 5 }, endLoc: { line: 120, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 102, col: 9 }, endLoc: { line: 102, col: 41 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 106, col: 9 }, endLoc: { line: 106, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 110, col: 9 }, endLoc: { line: 110, col: 18 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 113, col: 9 }, endLoc: { line: 113, col: 20 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 116, col: 9 }, endLoc: { line: 116, col: 21 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 7 }, 8: { name: "Fmt.maskWs", count: 0, regions: { 0: { startLoc: { line: 123, col: 3 }, endLoc: { line: 125, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 124, col: 5 }, endLoc: { line: 125, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 124, col: 12 }, endLoc: { line: 124, col: 54 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 8 } }, exeLine: { 0: 5, 1: 7, 2: 8, 3: 9, 4: 10, 5: 12, 6: 13, 7: 15, 8: 16, 9: 18, 10: 22, 11: 23, 12: 24, 13: 25, 14: 26, 15: 27, 16: 28, 17: 29, 18: 30, 19: 33, 20: 37, 21: 38, 22: 39, 23: 40, 24: 41, 25: 43, 26: 44, 27: 46, 28: 47, 29: 49, 30: 53, 31: 54, 32: 55, 33: 56, 34: 57, 35: 58, 36: 59, 37: 61, 38: 62, 39: 64, 40: 65, 41: 67, 42: 71, 43: 72, 44: 73, 45: 75, 46: 76, 47: 77, 48: 79, 49: 80, 50: 84, 51: 85, 52: 86, 53: 88, 54: 89, 55: 90, 56: 92, 57: 93, 58: 96, 59: 97, 60: 101, 61: 102, 62: 103, 63: 105, 64: 106, 65: 107, 66: 109, 67: 110, 68: 111, 69: 113, 70: 114, 71: 116, 72: 117, 73: 119, 74: 123, 75: 124 } });
/**
 * 格式化工具 —— app.js fmt* / Android Fmt.kt 的 1:1 移植 (locale 无关)。
 */
export class Fmt {
    /** 1.2B / 3.4M / 5.6k / 123 —— fmtTokens 移植。 */
    static tokens(n: number): string {
        bjccovmt7djy4s.instrumentFunction(0);
        const v = n;
        if (v >= 1e9) {
            bjccovmt7djy4s.instrumentBranch(0, 0, true);
            bjccovmt7djy4s.instrumentRegion(0, 1);
            return `${(v / 1e9).toFixed(2)}B`;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(0, 0, false);
        }
        if (v >= 1e6) {
            bjccovmt7djy4s.instrumentBranch(0, 1, true);
            bjccovmt7djy4s.instrumentRegion(0, 2);
            return `${(v / 1e6).toFixed(2)}M`;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(0, 1, false);
        }
        if (v >= 1e3) {
            bjccovmt7djy4s.instrumentBranch(0, 2, true);
            bjccovmt7djy4s.instrumentRegion(0, 3);
            return `${(v / 1e3).toFixed(1)}k`;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(0, 2, false);
        }
        bjccovmt7djy4s.instrumentRegion(0, 4);
        return Math.round(v).toString();
    }
    /** 千分位整数 —— fmtInt 移植。 */
    static int(n: number): string {
        bjccovmt7djy4s.instrumentFunction(1);
        const s = Math.round(n).toString();
        let out = '';
        let count = 0;
        for (let i = s.length - 1; i >= 0; i--) {
            bjccovmt7djy4s.instrumentRegion(1, 1);
            out = s[i] + out;
            count++;
            if (count % 3 === 0 && i > 0) {
                bjccovmt7djy4s.instrumentBranch(1, 0, true);
                bjccovmt7djy4s.instrumentRegion(1, 2);
                out = ',' + out;
            }
            else {
                bjccovmt7djy4s.instrumentBranch(1, 0, false);
            }
        }
        bjccovmt7djy4s.instrumentRegion(1, 3);
        return out;
    }
    /** 金额 —— fmtMoney 移植。 */
    static money(usd: number, currency: string, usdCny: number): string {
        bjccovmt7djy4s.instrumentFunction(2);
        const v = usd;
        if (currency === 'CNY') {
            bjccovmt7djy4s.instrumentBranch(2, 0, true);
            bjccovmt7djy4s.instrumentRegion(2, 1);
            const c = v * usdCny;
            return '¥' + (c >= 1 ? (bjccovmt7djy4s.instrumentBranch(2, 1, true), c.toFixed(2)) : (bjccovmt7djy4s.instrumentBranch(2, 1, false), c.toFixed(4)));
        }
        else {
            bjccovmt7djy4s.instrumentBranch(2, 0, false);
        }
        if (v >= 1) {
            bjccovmt7djy4s.instrumentBranch(2, 2, true);
            bjccovmt7djy4s.instrumentRegion(2, 2);
            return '$' + v.toFixed(2);
        }
        else {
            bjccovmt7djy4s.instrumentBranch(2, 2, false);
        }
        if (v > 0) {
            bjccovmt7djy4s.instrumentBranch(2, 3, true);
            bjccovmt7djy4s.instrumentRegion(2, 3);
            return '$' + v.toFixed(4);
        }
        else {
            bjccovmt7djy4s.instrumentBranch(2, 3, false);
        }
        bjccovmt7djy4s.instrumentRegion(2, 4);
        return '$0';
    }
    /** 时长 d/h/m —— fmtDur 移植。 */
    static dur(sec: number, dUnit: string, hUnit: string, mUnit: string, soon: string): string {
        bjccovmt7djy4s.instrumentFunction(3);
        const s = Math.max(0, sec);
        const d = Math.floor(s / 86400);
        const h = Math.floor((s % 86400) / 3600);
        const m = Math.floor((s % 3600) / 60);
        if (d > 0) {
            bjccovmt7djy4s.instrumentBranch(3, 0, true);
            bjccovmt7djy4s.instrumentRegion(3, 1);
            return `${d} ${dUnit} ${h} ${hUnit}`;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(3, 0, false);
        }
        if (h > 0) {
            bjccovmt7djy4s.instrumentBranch(3, 1, true);
            bjccovmt7djy4s.instrumentRegion(3, 2);
            return `${h} ${hUnit} ${m} ${mUnit}`;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(3, 1, false);
        }
        if (m > 0) {
            bjccovmt7djy4s.instrumentBranch(3, 2, true);
            bjccovmt7djy4s.instrumentRegion(3, 3);
            return `${m} ${mUnit}`;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(3, 2, false);
        }
        bjccovmt7djy4s.instrumentRegion(3, 4);
        return soon;
    }
    /** 完整时间 yyyy-MM-dd HH:mm:ss (ISO → 本地时区)。 */
    static dateTime(iso: string | null): string {
        bjccovmt7djy4s.instrumentFunction(4);
        if (iso === null || iso.length === 0) {
            bjccovmt7djy4s.instrumentBranch(4, 0, true);
            bjccovmt7djy4s.instrumentRegion(4, 1);
            return '—';
        }
        else {
            bjccovmt7djy4s.instrumentBranch(4, 0, false);
        }
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) {
            bjccovmt7djy4s.instrumentBranch(4, 1, true);
            bjccovmt7djy4s.instrumentRegion(4, 2);
            return '—';
        }
        else {
            bjccovmt7djy4s.instrumentBranch(4, 1, false);
        }
        bjccovmt7djy4s.instrumentRegion(4, 3);
        return Fmt.pad2(d.getFullYear()) + '-' + Fmt.pad2(d.getMonth() + 1) + '-' + Fmt.pad2(d.getDate()) +
            ' ' + Fmt.pad2(d.getHours()) + ':' + Fmt.pad2(d.getMinutes()) + ':' + Fmt.pad2(d.getSeconds());
    }
    /** 短时间 MM-dd HH:mm。 */
    static dateTimeShort(iso: string | null): string {
        bjccovmt7djy4s.instrumentFunction(5);
        if (iso === null || iso.length === 0) {
            bjccovmt7djy4s.instrumentBranch(5, 0, true);
            bjccovmt7djy4s.instrumentRegion(5, 1);
            return '—';
        }
        else {
            bjccovmt7djy4s.instrumentBranch(5, 0, false);
        }
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) {
            bjccovmt7djy4s.instrumentBranch(5, 1, true);
            bjccovmt7djy4s.instrumentRegion(5, 2);
            return '—';
        }
        else {
            bjccovmt7djy4s.instrumentBranch(5, 1, false);
        }
        bjccovmt7djy4s.instrumentRegion(5, 3);
        return Fmt.pad2(d.getMonth() + 1) + '-' + Fmt.pad2(d.getDate()) +
            ' ' + Fmt.pad2(d.getHours()) + ':' + Fmt.pad2(d.getMinutes());
    }
    private static pad2(n: number): string {
        bjccovmt7djy4s.instrumentFunction(6);
        bjccovmt7djy4s.instrumentRegion(6, 1);
        return n < 10 ? (bjccovmt7djy4s.instrumentBranch(6, 0, true), `0${n}`) : (bjccovmt7djy4s.instrumentBranch(6, 0, false), `${n}`);
    }
    /** 相对时间 —— fmtRelative 移植。 */
    static relative(iso: string | null, justNow: string, minAgo: string, hrAgo: string, dayAgo: string, never: string): string {
        bjccovmt7djy4s.instrumentFunction(7);
        if (iso === null || iso.length === 0) {
            bjccovmt7djy4s.instrumentBranch(7, 0, true);
            bjccovmt7djy4s.instrumentRegion(7, 1);
            return never;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(7, 0, false);
        }
        const t = new Date(iso).getTime();
        if (Number.isNaN(t)) {
            bjccovmt7djy4s.instrumentBranch(7, 1, true);
            bjccovmt7djy4s.instrumentRegion(7, 2);
            return never;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(7, 1, false);
        }
        const diff = (Date.now() - t) / 1000;
        if (diff < 60) {
            bjccovmt7djy4s.instrumentBranch(7, 2, true);
            bjccovmt7djy4s.instrumentRegion(7, 3);
            return justNow;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(7, 2, false);
        }
        if (diff < 3600) {
            bjccovmt7djy4s.instrumentBranch(7, 3, true);
            bjccovmt7djy4s.instrumentRegion(7, 4);
            return `${Math.floor(diff / 60)} ${minAgo}`;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(7, 3, false);
        }
        if (diff < 86400) {
            bjccovmt7djy4s.instrumentBranch(7, 4, true);
            bjccovmt7djy4s.instrumentRegion(7, 5);
            return `${Math.floor(diff / 3600)} ${hrAgo}`;
        }
        else {
            bjccovmt7djy4s.instrumentBranch(7, 4, false);
        }
        bjccovmt7djy4s.instrumentRegion(7, 6);
        return `${Math.floor(diff / 86400)} ${dayAgo}`;
    }
    /** 遮蔽长工作区 id —— maskWs 移植。 */
    static maskWs(ws: string): string {
        bjccovmt7djy4s.instrumentFunction(8);
        bjccovmt7djy4s.instrumentRegion(8, 1);
        return ws.length > 12 ? (bjccovmt7djy4s.instrumentBranch(8, 0, true), ws.slice(0, 8) + '…') : (bjccovmt7djy4s.instrumentBranch(8, 0, false), ws);
    }
}
