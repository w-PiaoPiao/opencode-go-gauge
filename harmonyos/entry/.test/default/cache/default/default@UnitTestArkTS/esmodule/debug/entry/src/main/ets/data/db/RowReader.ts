import type relationalStore from "@ohos:data.relationalStore";
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
let bjccovmt7djy52 = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/db/RowReader.ets", hash: "7e7336733bc613e800f9116f062bfbb9ac271c0190e473ae18a4a2a16578d346", lineCnt: 80, count: 0, projectPath: "", functions: { 0: { name: "RowReader.constructor", count: 0, regions: { 0: { startLoc: { line: 8, col: 3 }, endLoc: { line: 10, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 9, col: 5 }, endLoc: { line: 10, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "RowReader.rowCount", count: 0, regions: { 0: { startLoc: { line: 12, col: 3 }, endLoc: { line: 14, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 13, col: 5 }, endLoc: { line: 14, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "RowReader.next", count: 0, regions: { 0: { startLoc: { line: 16, col: 3 }, endLoc: { line: 18, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 17, col: 5 }, endLoc: { line: 18, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 2 }, 3: { name: "RowReader.idx", count: 0, regions: { 0: { startLoc: { line: 20, col: 3 }, endLoc: { line: 27, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 22, col: 26 }, endLoc: { line: 25, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 26, col: 5 }, endLoc: { line: 27, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 22, col: 9 }, endLoc: { line: 22, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 3 }, 4: { name: "RowReader.getStrAt", count: 0, regions: { 0: { startLoc: { line: 29, col: 3 }, endLoc: { line: 35, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 30, col: 9 }, endLoc: { line: 32, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 32, col: 7 }, endLoc: { line: 34, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 4 }, 5: { name: "RowReader.getLongAt", count: 0, regions: { 0: { startLoc: { line: 37, col: 3 }, endLoc: { line: 43, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 38, col: 9 }, endLoc: { line: 40, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 40, col: 7 }, endLoc: { line: 42, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 5 }, 6: { name: "RowReader.getStr", count: 0, regions: { 0: { startLoc: { line: 45, col: 3 }, endLoc: { line: 51, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 46, col: 9 }, endLoc: { line: 48, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 48, col: 7 }, endLoc: { line: 50, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 6 }, 7: { name: "RowReader.getLong", count: 0, regions: { 0: { startLoc: { line: 53, col: 3 }, endLoc: { line: 59, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 54, col: 9 }, endLoc: { line: 56, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 56, col: 7 }, endLoc: { line: 58, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 7 }, 8: { name: "RowReader.getDouble", count: 0, regions: { 0: { startLoc: { line: 61, col: 3 }, endLoc: { line: 67, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 62, col: 9 }, endLoc: { line: 64, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 64, col: 7 }, endLoc: { line: 66, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 8 }, 9: { name: "RowReader.isNull", count: 0, regions: { 0: { startLoc: { line: 69, col: 3 }, endLoc: { line: 75, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 70, col: 9 }, endLoc: { line: 72, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 72, col: 7 }, endLoc: { line: 74, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 9 }, 10: { name: "RowReader.close", count: 0, regions: { 0: { startLoc: { line: 77, col: 3 }, endLoc: { line: 79, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 78, col: 5 }, endLoc: { line: 79, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 10 } }, exeLine: { 0: 2, 1: 4, 2: 5, 3: 6, 4: 8, 5: 9, 6: 12, 7: 13, 8: 16, 9: 17, 10: 20, 11: 21, 12: 22, 13: 23, 14: 24, 15: 26, 16: 29, 17: 30, 18: 31, 19: 32, 20: 33, 21: 37, 22: 38, 23: 39, 24: 40, 25: 41, 26: 45, 27: 46, 28: 47, 29: 48, 30: 49, 31: 53, 32: 54, 33: 55, 34: 56, 35: 57, 36: 61, 37: 62, 38: 63, 39: 64, 40: 65, 41: 69, 42: 70, 43: 71, 44: 72, 45: 73, 46: 77, 47: 78 } });
export class RowReader {
    private rs: relationalStore.ResultSet;
    private colCache: Map<string, number> = new Map();
    constructor(rs: relationalStore.ResultSet) {
        bjccovmt7djy52.instrumentFunction(0);
        bjccovmt7djy52.instrumentRegion(0, 1);
        this.rs = rs;
    }
    get rowCount(): number {
        bjccovmt7djy52.instrumentFunction(1);
        bjccovmt7djy52.instrumentRegion(1, 1);
        return this.rs.rowCount;
    }
    next(): boolean {
        bjccovmt7djy52.instrumentFunction(2);
        bjccovmt7djy52.instrumentRegion(2, 1);
        return this.rs.goToNextRow();
    }
    private idx(name: string): number {
        bjccovmt7djy52.instrumentFunction(3);
        let i = this.colCache.get(name);
        if (i === undefined) {
            bjccovmt7djy52.instrumentBranch(3, 0, true);
            bjccovmt7djy52.instrumentRegion(3, 1);
            i = this.rs.getColumnIndex(name);
            this.colCache.set(name, i);
        }
        else {
            bjccovmt7djy52.instrumentBranch(3, 0, false);
        }
        bjccovmt7djy52.instrumentRegion(3, 2);
        return i;
    }
    getStrAt(idx: number): string {
        bjccovmt7djy52.instrumentFunction(4);
        try {
            bjccovmt7djy52.instrumentRegion(4, 1);
            return this.rs.getString(idx);
        }
        catch (e) {
            bjccovmt7djy52.instrumentRegion(4, 2);
            return '';
        }
    }
    getLongAt(idx: number): number {
        bjccovmt7djy52.instrumentFunction(5);
        try {
            bjccovmt7djy52.instrumentRegion(5, 1);
            return this.rs.getLong(idx);
        }
        catch (e) {
            bjccovmt7djy52.instrumentRegion(5, 2);
            return 0;
        }
    }
    getStr(name: string): string {
        bjccovmt7djy52.instrumentFunction(6);
        try {
            bjccovmt7djy52.instrumentRegion(6, 1);
            return this.rs.getString(this.idx(name));
        }
        catch (e) {
            bjccovmt7djy52.instrumentRegion(6, 2);
            return '';
        }
    }
    getLong(name: string): number {
        bjccovmt7djy52.instrumentFunction(7);
        try {
            bjccovmt7djy52.instrumentRegion(7, 1);
            return this.rs.getLong(this.idx(name));
        }
        catch (e) {
            bjccovmt7djy52.instrumentRegion(7, 2);
            return 0;
        }
    }
    getDouble(name: string): number {
        bjccovmt7djy52.instrumentFunction(8);
        try {
            bjccovmt7djy52.instrumentRegion(8, 1);
            return this.rs.getDouble(this.idx(name));
        }
        catch (e) {
            bjccovmt7djy52.instrumentRegion(8, 2);
            return 0;
        }
    }
    isNull(name: string): boolean {
        bjccovmt7djy52.instrumentFunction(9);
        try {
            bjccovmt7djy52.instrumentRegion(9, 1);
            return this.rs.isColumnNull(this.idx(name));
        }
        catch (e) {
            bjccovmt7djy52.instrumentRegion(9, 2);
            return true;
        }
    }
    close(): void {
        bjccovmt7djy52.instrumentFunction(10);
        bjccovmt7djy52.instrumentRegion(10, 1);
        this.rs.close();
    }
}
