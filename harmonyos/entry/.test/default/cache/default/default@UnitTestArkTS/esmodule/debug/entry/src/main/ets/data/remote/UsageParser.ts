import type { UsageRecord } from '../../common/model/Models';
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
let bjccovmt7djy49 = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/remote/UsageParser.ets", hash: "8abd9b5da56ee6480b84f519ca9155a0694abd51ec55dd1ce0feffe6e0279246", lineCnt: 78, count: 0, projectPath: "", functions: { 0: { name: "UsageParser.parseNumField", count: 0, regions: { 0: { startLoc: { line: 12, col: 3 }, endLoc: { line: 23, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 15, col: 21 }, endLoc: { line: 17, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 18, col: 26 }, endLoc: { line: 20, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 21, col: 5 }, endLoc: { line: 23, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 15, col: 9 }, endLoc: { line: 15, col: 19 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 18, col: 9 }, endLoc: { line: 18, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 22, col: 12 }, endLoc: { line: 22, col: 35 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 0 }, 1: { name: "UsageParser.parseStrField", count: 0, regions: { 0: { startLoc: { line: 25, col: 3 }, endLoc: { line: 29, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 26, col: 5 }, endLoc: { line: 29, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 28, col: 12 }, endLoc: { line: 28, col: 56 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 1 }, 2: { name: "UsageParser.parseUsageResponse", count: 0, regions: { 0: { startLoc: { line: 32, col: 3 }, endLoc: { line: 77, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 36, col: 5 }, endLoc: { line: 38, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 44, col: 5 }, endLoc: { line: 46, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 49, col: 5 }, endLoc: { line: 75, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 54, col: 29 }, endLoc: { line: 56, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 76, col: 5 }, endLoc: { line: 77, col: 4 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 57, col: 7 }, endLoc: { line: 75, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 51, col: 27 }, endLoc: { line: 51, col: 86 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 54, col: 11 }, endLoc: { line: 54, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 73, col: 15 }, endLoc: { line: 73, col: 53 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 } }, exeLine: { 0: 5, 1: 7, 2: 8, 3: 9, 4: 10, 5: 12, 6: 13, 7: 14, 8: 15, 9: 16, 10: 18, 11: 19, 12: 21, 13: 22, 14: 25, 15: 26, 16: 27, 17: 28, 18: 32, 19: 33, 20: 34, 21: 35, 22: 36, 23: 37, 24: 40, 25: 41, 26: 42, 27: 43, 28: 44, 29: 45, 30: 48, 31: 49, 32: 50, 33: 51, 34: 52, 35: 53, 36: 54, 37: 55, 38: 57, 39: 58, 40: 59, 41: 60, 42: 61, 43: 62, 44: 63, 45: 64, 46: 65, 47: 66, 48: 67, 49: 68, 50: 69, 51: 70, 52: 71, 53: 72, 54: 73, 55: 76 } });
export class UsageParser {
    private static readonly RECORD_ANCHOR = /id:\s*"(usg_[^"]+)"/g;
    private static readonly PLAN_RE = /id:\s*"(usg_[^"]+)"[^}]*?enrichment:\$R\[\d+\]=\{plan:"([^"]+)"\}/gs;
    private static readonly CREATED_RE = /timeCreated:\s*\$R\[\d+\]\s*=\s*new Date\("([^"]+)"\)/;
    private static parseNumField(body: string, name: string): number {
        bjccovmt7djy49.instrumentFunction(0);
        const re = new RegExp(`${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:\\s*(\\d+|null)`);
        const m = re.exec(body);
        if (m === null) {
            bjccovmt7djy49.instrumentBranch(0, 0, true);
            bjccovmt7djy49.instrumentRegion(0, 1);
            return 0;
        }
        else {
            bjccovmt7djy49.instrumentBranch(0, 0, false);
        }
        if (m[1] === 'null') {
            bjccovmt7djy49.instrumentBranch(0, 1, true);
            bjccovmt7djy49.instrumentRegion(0, 2);
            return 0;
        }
        else {
            bjccovmt7djy49.instrumentBranch(0, 1, false);
        }
        bjccovmt7djy49.instrumentRegion(0, 3);
        const n = Number(m[1]);
        return Number.isNaN(n) ? (bjccovmt7djy49.instrumentBranch(0, 2, true), 0) : (bjccovmt7djy49.instrumentBranch(0, 2, false), n);
    }
    private static parseStrField(body: string, name: string): string {
        bjccovmt7djy49.instrumentFunction(1);
        bjccovmt7djy49.instrumentRegion(1, 1);
        const re = new RegExp(`${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}:\\s*"([^"]*)"`);
        const m = re.exec(body);
        return m === null || m[1] === undefined ? (bjccovmt7djy49.instrumentBranch(1, 0, true), '') : (bjccovmt7djy49.instrumentBranch(1, 0, false), m[1]);
    }
    /** 解析一个 server-fn 响应体为 UsageRecord 列表。 */
    static parseUsageResponse(text: string): UsageRecord[] {
        bjccovmt7djy49.instrumentFunction(2);
        const plans: Map<string, string> = new Map();
        let pm: RegExpExecArray | null;
        const planRe = UsageParser.PLAN_RE;
        while ((pm = planRe.exec(text)) !== null) {
            bjccovmt7djy49.instrumentRegion(2, 1);
            plans.set(pm[1], pm[2]);
        }
        const anchors: RegExpExecArray[] = [];
        let am: RegExpExecArray | null;
        const anchorRe = UsageParser.RECORD_ANCHOR;
        anchorRe.lastIndex = 0;
        while ((am = anchorRe.exec(text)) !== null) {
            bjccovmt7djy49.instrumentRegion(2, 2);
            anchors.push(am);
        }
        const records: UsageRecord[] = [];
        for (let i = 0; i < anchors.length; i++) {
            bjccovmt7djy49.instrumentRegion(2, 3);
            const m = anchors[i];
            const end: number = i + 1 < anchors.length ? (bjccovmt7djy49.instrumentBranch(2, 0, true), anchors[i + 1].index) : (bjccovmt7djy49.instrumentBranch(2, 0, false), text.length);
            const body: string = text.substring(m.index + m[0].length, end);
            const created = UsageParser.CREATED_RE.exec(body);
            if (created === null) {
                bjccovmt7djy49.instrumentBranch(2, 1, true);
                bjccovmt7djy49.instrumentRegion(2, 4);
                continue;
            }
            else {
                bjccovmt7djy49.instrumentBranch(2, 1, false);
            }
            bjccovmt7djy49.instrumentRegion(2, 6);
            const usgId: string = m[1];
            const planVal = plans.get(usgId);
            records.push({
                usgId: usgId,
                createdAt: created[1],
                model: UsageParser.parseStrField(body, 'model'),
                provider: UsageParser.parseStrField(body, 'provider'),
                inputTokens: UsageParser.parseNumField(body, 'inputTokens'),
                outputTokens: UsageParser.parseNumField(body, 'outputTokens'),
                reasoningTokens: UsageParser.parseNumField(body, 'reasoningTokens'),
                cacheReadTokens: UsageParser.parseNumField(body, 'cacheReadTokens'),
                cacheWrite5mTokens: UsageParser.parseNumField(body, 'cacheWrite5mTokens'),
                cacheWrite1hTokens: UsageParser.parseNumField(body, 'cacheWrite1hTokens'),
                costRaw: UsageParser.parseNumField(body, 'cost'),
                keyId: UsageParser.parseStrField(body, 'keyID'),
                sessionId: UsageParser.parseStrField(body, 'sessionID'),
                plan: planVal === undefined ? (bjccovmt7djy49.instrumentBranch(2, 2, true), null) : (bjccovmt7djy49.instrumentBranch(2, 2, false), planVal),
            });
        }
        bjccovmt7djy49.instrumentRegion(2, 5);
        return records;
    }
}
