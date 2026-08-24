import { HttpFetch, HttpError } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/remote/HttpFetch";
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
let bjccovmt7djy35 = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/remote/ExchangeApi.ets", hash: "8a0344a325705a22968b63749afad127b68a70f74a6040a08838b161b8247511", lineCnt: 26, count: 0, projectPath: "", functions: { 0: { name: "ExchangeApi.fetchUsdCny", count: 0, regions: { 0: { startLoc: { line: 11, col: 3 }, endLoc: { line: 25, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 17, col: 21 }, endLoc: { line: 19, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 21, col: 22 }, endLoc: { line: 23, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 24, col: 5 }, endLoc: { line: 25, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 17, col: 9 }, endLoc: { line: 17, col: 19 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 21, col: 9 }, endLoc: { line: 21, col: 20 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 0 } }, exeLine: { 0: 5, 1: 7, 2: 8, 3: 11, 4: 12, 5: 13, 6: 14, 7: 16, 8: 17, 9: 18, 10: 20, 11: 21, 12: 22, 13: 24 } });
export class ExchangeApi {
    static readonly EXCHANGE_URL = 'https://open.er-api.com/v6/latest/USD';
    /** 抓取 USD→CNY; 失败抛异常。 */
    static async fetchUsdCny(): Promise<number> {
        bjccovmt7djy35.instrumentFunction(0);
        const body = await HttpFetch.fetch(ExchangeApi.EXCHANGE_URL, {
            'User-Agent': 'GoGauge/1.0',
            'Accept': 'application/json',
        });
        const m = /"CNY"\s*:\s*([\d.]+)/.exec(body);
        if (m === null) {
            bjccovmt7djy35.instrumentBranch(0, 0, true);
            bjccovmt7djy35.instrumentRegion(0, 1);
            throw new HttpError('汇率接口缺少 CNY');
        }
        else {
            bjccovmt7djy35.instrumentBranch(0, 0, false);
        }
        const rate = Number(m[1]);
        if (!(rate > 0)) {
            bjccovmt7djy35.instrumentBranch(0, 1, true);
            bjccovmt7djy35.instrumentRegion(0, 2);
            throw new HttpError('汇率接口缺少 CNY');
        }
        else {
            bjccovmt7djy35.instrumentBranch(0, 1, false);
        }
        bjccovmt7djy35.instrumentRegion(0, 3);
        return rate;
    }
}
