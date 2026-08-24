import { AppDb } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/AppDb";
import { RowReader } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/RowReader";
import type { SettingsDao } from './SettingsDao';
import { emptySyncState } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/common/model/Models";
import type { AccountInfo, SyncState } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/common/model/Models";
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
let bjccovmt7djxzh = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/db/SyncDao.ets", hash: "89a9013483693df93ac5f4ab029902da9bcc7971f6ae88e8940d078f39bcd2ba", lineCnt: 451, count: 0, projectPath: "", functions: { 0: { name: "accountRowFromReader", count: 0, regions: { 0: { startLoc: { line: 32, col: 1 }, endLoc: { line: 42, col: 2 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 33, col: 3 }, endLoc: { line: 42, col: 2 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 37, col: 26 }, endLoc: { line: 37, col: 102 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 0 }, 1: { name: "toInfo", count: 0, regions: { 0: { startLoc: { line: 44, col: 1 }, endLoc: { line: 52, col: 2 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 45, col: 3 }, endLoc: { line: 52, col: 2 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "SyncDao.settings", count: 0, regions: { 0: { startLoc: { line: 55, col: 3 }, endLoc: { line: 57, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 56, col: 5 }, endLoc: { line: 57, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 2 }, 3: { name: "SyncDao.listAccountRows", count: 0, regions: { 0: { startLoc: { line: 63, col: 3 }, endLoc: { line: 72, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 67, col: 5 }, endLoc: { line: 69, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 70, col: 5 }, endLoc: { line: 72, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 3 }, 4: { name: "SyncDao.accountRowById", count: 0, regions: { 0: { startLoc: { line: 74, col: 3 }, endLoc: { line: 83, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 78, col: 19 }, endLoc: { line: 80, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 81, col: 5 }, endLoc: { line: 83, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 78, col: 9 }, endLoc: { line: 78, col: 17 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 4 }, 5: { name: "SyncDao.scalarInt", count: 0, regions: { 0: { startLoc: { line: 85, col: 3 }, endLoc: { line: 94, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 89, col: 19 }, endLoc: { line: 91, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 92, col: 5 }, endLoc: { line: 94, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 89, col: 9 }, endLoc: { line: 89, col: 17 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 5 }, 6: { name: "SyncDao.minLoggedInId", count: 0, regions: { 0: { startLoc: { line: 96, col: 3 }, endLoc: { line: 98, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 97, col: 5 }, endLoc: { line: 98, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 6 }, 7: { name: "SyncDao.minAnyId", count: 0, regions: { 0: { startLoc: { line: 100, col: 3 }, endLoc: { line: 102, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 101, col: 5 }, endLoc: { line: 102, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 7 }, 8: { name: "SyncDao.countAccounts", count: 0, regions: { 0: { startLoc: { line: 104, col: 3 }, endLoc: { line: 106, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 105, col: 5 }, endLoc: { line: 106, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 8 }, 9: { name: "SyncDao.countLoggedInAccounts", count: 0, regions: { 0: { startLoc: { line: 108, col: 3 }, endLoc: { line: 110, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 109, col: 5 }, endLoc: { line: 110, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 9 }, 10: { name: "SyncDao.nextAccountId", count: 0, regions: { 0: { startLoc: { line: 113, col: 3 }, endLoc: { line: 115, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 114, col: 5 }, endLoc: { line: 115, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 10 }, 11: { name: "SyncDao.insertAccountRow", count: 0, regions: { 0: { startLoc: { line: 117, col: 3 }, endLoc: { line: 123, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 118, col: 5 }, endLoc: { line: 123, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 11 }, 12: { name: "SyncDao.updateCredential", count: 0, regions: { 0: { startLoc: { line: 125, col: 3 }, endLoc: { line: 130, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 126, col: 5 }, endLoc: { line: 130, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 12 }, 13: { name: "SyncDao.updateWorkspaceHint", count: 0, regions: { 0: { startLoc: { line: 132, col: 3 }, endLoc: { line: 137, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 133, col: 5 }, endLoc: { line: 137, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 13 }, 14: { name: "SyncDao.saveResolvedWorkspace", count: 0, regions: { 0: { startLoc: { line: 139, col: 3 }, endLoc: { line: 144, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 140, col: 5 }, endLoc: { line: 144, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 14 }, 15: { name: "SyncDao.renameAccountRow", count: 0, regions: { 0: { startLoc: { line: 146, col: 3 }, endLoc: { line: 151, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 147, col: 5 }, endLoc: { line: 151, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 15 }, 16: { name: "SyncDao.clearToken", count: 0, regions: { 0: { startLoc: { line: 153, col: 3 }, endLoc: { line: 158, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 154, col: 5 }, endLoc: { line: 158, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 16 }, 17: { name: "SyncDao.deleteAccountRow", count: 0, regions: { 0: { startLoc: { line: 160, col: 3 }, endLoc: { line: 162, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 161, col: 5 }, endLoc: { line: 162, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 17 }, 18: { name: "SyncDao.resolveActive", count: 0, regions: { 0: { startLoc: { line: 168, col: 3 }, endLoc: { line: 205, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 172, col: 5 }, endLoc: { line: 176, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 173, col: 58 }, endLoc: { line: 175, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 177, col: 56 }, endLoc: { line: 194, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 179, col: 7 }, endLoc: { line: 184, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 180, col: 38 }, endLoc: { line: 183, col: 10 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 185, col: 25 }, endLoc: { line: 193, col: 8 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 186, col: 21 }, endLoc: { line: 188, col: 10 }, count: 0, ignored: 0 }, 8: { startLoc: { line: 189, col: 30 }, endLoc: { line: 191, col: 10 }, count: 0, ignored: 0 }, 9: { startLoc: { line: 195, col: 26 }, endLoc: { line: 197, col: 6 }, count: 0, ignored: 0 }, 10: { startLoc: { line: 199, col: 5 }, endLoc: { line: 203, col: 6 }, count: 0, ignored: 0 }, 11: { startLoc: { line: 200, col: 46 }, endLoc: { line: 202, col: 8 }, count: 0, ignored: 0 }, 12: { startLoc: { line: 204, col: 5 }, endLoc: { line: 205, col: 4 }, count: 0, ignored: 0 }, 13: { startLoc: { line: 192, col: 9 }, endLoc: { line: 193, col: 8 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 173, col: 11 }, endLoc: { line: 173, col: 56 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 177, col: 9 }, endLoc: { line: 177, col: 54 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 180, col: 13 }, endLoc: { line: 180, col: 36 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 185, col: 11 }, endLoc: { line: 185, col: 23 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 186, col: 13 }, endLoc: { line: 186, col: 19 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 189, col: 13 }, endLoc: { line: 189, col: 28 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 6: { startLoc: { line: 195, col: 9 }, endLoc: { line: 195, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 7: { startLoc: { line: 200, col: 11 }, endLoc: { line: 200, col: 44 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 18 }, 19: { name: "SyncDao.getActiveAccountId", count: 0, regions: { 0: { startLoc: { line: 207, col: 3 }, endLoc: { line: 222, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 214, col: 73 }, endLoc: { line: 220, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 215, col: 25 }, endLoc: { line: 217, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 217, col: 14 }, endLoc: { line: 219, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 221, col: 5 }, endLoc: { line: 222, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 214, col: 9 }, endLoc: { line: 214, col: 71 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 214, col: 42 }, endLoc: { line: 214, col: 70 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 215, col: 11 }, endLoc: { line: 215, col: 23 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 19 }, 20: { name: "anonymous_0", count: 0, regions: { 0: { startLoc: { line: 212, col: 16 }, endLoc: { line: 212, col: 83 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 20 }, 21: { name: "SyncDao.setActiveAccount", count: 0, regions: { 0: { startLoc: { line: 224, col: 3 }, endLoc: { line: 231, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 226, col: 23 }, endLoc: { line: 228, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 229, col: 5 }, endLoc: { line: 231, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 226, col: 9 }, endLoc: { line: 226, col: 21 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 21 }, 22: { name: "SyncDao.getAccount", count: 0, regions: { 0: { startLoc: { line: 237, col: 3 }, endLoc: { line: 244, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 239, col: 20 }, endLoc: { line: 241, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 242, col: 5 }, endLoc: { line: 244, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 239, col: 9 }, endLoc: { line: 239, col: 18 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 243, col: 12 }, endLoc: { line: 243, col: 45 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 22 }, 23: { name: "SyncDao.listAccounts", count: 0, regions: { 0: { startLoc: { line: 246, col: 3 }, endLoc: { line: 249, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 247, col: 5 }, endLoc: { line: 249, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 23 }, 24: { name: "anonymous_1", count: 0, regions: { 0: { startLoc: { line: 248, col: 21 }, endLoc: { line: 248, col: 41 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 24 }, 25: { name: "SyncDao.addAccount", count: 0, regions: { 0: { startLoc: { line: 252, col: 3 }, endLoc: { line: 285, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 256, col: 29 }, endLoc: { line: 269, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 258, col: 7 }, endLoc: { line: 268, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 259, col: 48 }, endLoc: { line: 267, col: 10 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 260, col: 32 }, endLoc: { line: 262, col: 12 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 263, col: 26 }, endLoc: { line: 265, col: 12 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 281, col: 20 }, endLoc: { line: 283, col: 6 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 284, col: 5 }, endLoc: { line: 285, col: 4 }, count: 0, ignored: 0 }, 8: { startLoc: { line: 266, col: 11 }, endLoc: { line: 267, col: 10 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 256, col: 9 }, endLoc: { line: 256, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 259, col: 13 }, endLoc: { line: 259, col: 46 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 260, col: 15 }, endLoc: { line: 260, col: 30 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 263, col: 15 }, endLoc: { line: 263, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 273, col: 13 }, endLoc: { line: 273, col: 79 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 274, col: 20 }, endLoc: { line: 274, col: 54 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 6: { startLoc: { line: 281, col: 9 }, endLoc: { line: 281, col: 18 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 25 }, 26: { name: "SyncDao.renameAccount", count: 0, regions: { 0: { startLoc: { line: 287, col: 3 }, endLoc: { line: 294, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 289, col: 31 }, endLoc: { line: 291, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 292, col: 5 }, endLoc: { line: 294, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 289, col: 9 }, endLoc: { line: 289, col: 29 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 26 }, 27: { name: "SyncDao.deleteAccount", count: 0, regions: { 0: { startLoc: { line: 297, col: 3 }, endLoc: { line: 312, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 303, col: 31 }, endLoc: { line: 310, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 305, col: 22 }, endLoc: { line: 307, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 307, col: 14 }, endLoc: { line: 309, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 311, col: 5 }, endLoc: { line: 312, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 303, col: 9 }, endLoc: { line: 303, col: 29 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 305, col: 11 }, endLoc: { line: 305, col: 20 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 27 }, 28: { name: "SyncDao.clearAccount", count: 0, regions: { 0: { startLoc: { line: 315, col: 3 }, endLoc: { line: 324, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 317, col: 20 }, endLoc: { line: 319, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 320, col: 5 }, endLoc: { line: 324, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 317, col: 9 }, endLoc: { line: 317, col: 18 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 28 }, 29: { name: "SyncDao.saveToken", count: 0, regions: { 0: { startLoc: { line: 327, col: 3 }, endLoc: { line: 336, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 329, col: 20 }, endLoc: { line: 331, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 332, col: 5 }, endLoc: { line: 336, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 329, col: 9 }, endLoc: { line: 329, col: 18 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 332, col: 52 }, endLoc: { line: 332, col: 114 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 29 }, 30: { name: "SyncDao.ensureStateRow", count: 0, regions: { 0: { startLoc: { line: 342, col: 3 }, endLoc: { line: 354, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 349, col: 18 }, endLoc: { line: 353, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 349, col: 9 }, endLoc: { line: 349, col: 16 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 30 }, 31: { name: "SyncDao.bumpSyncState", count: 0, regions: { 0: { startLoc: { line: 356, col: 3 }, endLoc: { line: 363, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 357, col: 5 }, endLoc: { line: 363, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 31 }, 32: { name: "SyncDao.resetSyncStateForAccount", count: 0, regions: { 0: { startLoc: { line: 365, col: 3 }, endLoc: { line: 373, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 366, col: 5 }, endLoc: { line: 373, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 32 }, 33: { name: "SyncDao.resetCursorForAccount", count: 0, regions: { 0: { startLoc: { line: 375, col: 3 }, endLoc: { line: 379, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 376, col: 5 }, endLoc: { line: 379, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 33 }, 34: { name: "SyncDao.recordBounds", count: 0, regions: { 0: { startLoc: { line: 381, col: 3 }, endLoc: { line: 397, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 388, col: 19 }, endLoc: { line: 394, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 395, col: 5 }, endLoc: { line: 397, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 388, col: 9 }, endLoc: { line: 388, col: 17 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 391, col: 9 }, endLoc: { line: 391, col: 55 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 392, col: 9 }, endLoc: { line: 392, col: 55 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 34 }, 35: { name: "SyncDao.updateSyncStateAndTotals", count: 0, regions: { 0: { startLoc: { line: 400, col: 3 }, endLoc: { line: 408, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 401, col: 5 }, endLoc: { line: 408, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 35 }, 36: { name: "SyncDao.getSyncStateFor", count: 0, regions: { 0: { startLoc: { line: 410, col: 3 }, endLoc: { line: 430, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 416, col: 19 }, endLoc: { line: 427, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 428, col: 5 }, endLoc: { line: 430, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 416, col: 9 }, endLoc: { line: 416, col: 17 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 418, col: 21 }, endLoc: { line: 418, col: 79 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 419, col: 25 }, endLoc: { line: 419, col: 91 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 420, col: 24 }, endLoc: { line: 420, col: 88 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 424, col: 25 }, endLoc: { line: 424, col: 91 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 425, col: 25 }, endLoc: { line: 425, col: 91 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 36 }, 37: { name: "SyncDao.getSyncState", count: 0, regions: { 0: { startLoc: { line: 432, col: 3 }, endLoc: { line: 434, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 433, col: 5 }, endLoc: { line: 434, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 37 }, 38: { name: "SyncDao.getTokenFor", count: 0, regions: { 0: { startLoc: { line: 436, col: 3 }, endLoc: { line: 439, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 437, col: 5 }, endLoc: { line: 439, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 438, col: 12 }, endLoc: { line: 438, col: 48 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 38 }, 39: { name: "SyncDao.getWorkspaceHintFor", count: 0, regions: { 0: { startLoc: { line: 441, col: 3 }, endLoc: { line: 450, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 443, col: 23 }, endLoc: { line: 445, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 446, col: 81 }, endLoc: { line: 448, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 449, col: 5 }, endLoc: { line: 450, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 443, col: 9 }, endLoc: { line: 443, col: 21 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 446, col: 9 }, endLoc: { line: 446, col: 79 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 449, col: 12 }, endLoc: { line: 449, col: 68 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 39 } }, exeLine: { 0: 5, 1: 6, 2: 7, 3: 8, 4: 10, 5: 11, 6: 12, 7: 13, 8: 14, 9: 15, 10: 16, 11: 17, 12: 20, 13: 21, 14: 22, 15: 23, 16: 24, 17: 25, 18: 26, 19: 27, 20: 28, 21: 29, 22: 32, 23: 33, 24: 34, 25: 35, 26: 36, 27: 37, 28: 38, 29: 39, 30: 40, 31: 44, 32: 45, 33: 46, 34: 47, 35: 48, 36: 49, 37: 50, 38: 54, 39: 55, 40: 56, 41: 63, 42: 64, 43: 65, 44: 66, 45: 67, 46: 68, 47: 70, 48: 71, 49: 74, 50: 75, 51: 76, 52: 77, 53: 78, 54: 79, 55: 81, 56: 82, 57: 85, 58: 86, 59: 87, 60: 88, 61: 89, 62: 90, 63: 92, 64: 93, 65: 96, 66: 97, 67: 100, 68: 101, 69: 104, 70: 105, 71: 108, 72: 109, 73: 113, 74: 114, 75: 117, 76: 118, 77: 119, 78: 121, 79: 125, 80: 126, 81: 127, 82: 128, 83: 132, 84: 133, 85: 134, 86: 135, 87: 139, 88: 140, 89: 141, 90: 142, 91: 146, 92: 147, 93: 148, 94: 149, 95: 153, 96: 154, 97: 155, 98: 156, 99: 160, 100: 161, 101: 168, 102: 169, 103: 170, 104: 171, 105: 172, 106: 173, 107: 174, 108: 177, 109: 178, 110: 179, 111: 180, 112: 181, 113: 182, 114: 185, 115: 186, 116: 187, 117: 189, 118: 190, 119: 192, 120: 195, 121: 196, 122: 198, 123: 199, 124: 200, 125: 201, 126: 204, 127: 207, 128: 208, 129: 209, 130: 210, 131: 211, 132: 212, 133: 214, 134: 215, 135: 216, 136: 217, 137: 218, 138: 221, 139: 224, 140: 225, 141: 226, 142: 227, 143: 229, 144: 230, 145: 237, 146: 238, 147: 239, 148: 240, 149: 242, 150: 243, 151: 246, 152: 247, 153: 248, 154: 252, 155: 253, 156: 254, 157: 255, 158: 256, 159: 257, 160: 258, 161: 259, 162: 260, 163: 261, 164: 263, 165: 264, 166: 266, 167: 270, 168: 271, 169: 272, 170: 273, 171: 274, 172: 275, 173: 276, 174: 277, 175: 278, 176: 280, 177: 281, 178: 282, 179: 284, 180: 287, 181: 288, 182: 289, 183: 290, 184: 292, 185: 293, 186: 297, 187: 298, 188: 299, 189: 300, 190: 301, 191: 302, 192: 303, 193: 304, 194: 305, 195: 306, 196: 307, 197: 308, 198: 311, 199: 315, 200: 316, 201: 317, 202: 318, 203: 320, 204: 321, 205: 322, 206: 323, 207: 327, 208: 328, 209: 329, 210: 330, 211: 332, 212: 333, 213: 334, 214: 335, 215: 342, 216: 343, 217: 344, 218: 346, 219: 347, 220: 348, 221: 349, 222: 350, 223: 351, 224: 356, 225: 357, 226: 358, 227: 361, 228: 365, 229: 366, 230: 367, 231: 371, 232: 375, 233: 376, 234: 377, 235: 381, 236: 382, 237: 383, 238: 384, 239: 386, 240: 387, 241: 388, 242: 389, 243: 390, 244: 391, 245: 392, 246: 395, 247: 396, 248: 400, 249: 401, 250: 402, 251: 403, 252: 404, 253: 405, 254: 406, 255: 410, 256: 411, 257: 412, 258: 414, 259: 415, 260: 416, 261: 417, 262: 418, 263: 419, 264: 420, 265: 421, 266: 422, 267: 423, 268: 424, 269: 425, 270: 428, 271: 429, 272: 432, 273: 433, 274: 436, 275: 437, 276: 438, 277: 441, 278: 442, 279: 443, 280: 444, 281: 446, 282: 447, 283: 449 } });
export interface AccountRow {
    id: number;
    name: string;
    workspaceId: string;
    resolvedWorkspaceId: string | null;
    token: string;
    createdAt: string;
    updatedAt: string;
}
export interface SyncStateRow {
    accountId: number;
    lastSyncAt: string | null;
    lastSyncStatus: string | null;
    lastSyncError: string | null;
    lastInsertedCount: number;
    deepestPageFetched: number;
    totalRecords: number;
    oldestRecordAt: string | null;
    newestRecordAt: string | null;
}
function accountRowFromReader(r: RowReader): AccountRow {
    bjccovmt7djxzh.instrumentFunction(0);
    bjccovmt7djxzh.instrumentRegion(0, 1);
    return {
        id: r.getLong('id'),
        name: r.getStr('name'),
        workspaceId: r.getStr('workspace_id'),
        resolvedWorkspaceId: r.isNull('resolved_workspace_id') ? (bjccovmt7djxzh.instrumentBranch(0, 0, true), null) : (bjccovmt7djxzh.instrumentBranch(0, 0, false), r.getStr('resolved_workspace_id')),
        token: r.getStr('token'),
        createdAt: r.getStr('created_at'),
        updatedAt: r.getStr('updated_at'),
    };
}
function toInfo(row: AccountRow): AccountInfo {
    bjccovmt7djxzh.instrumentFunction(1);
    bjccovmt7djxzh.instrumentRegion(1, 1);
    return {
        id: row.id,
        name: row.name,
        workspaceId: row.workspaceId,
        resolvedWorkspaceId: row.resolvedWorkspaceId,
        hasToken: row.token.trim().length > 0,
    };
}
export class SyncDao {
    private settings(): SettingsDao {
        bjccovmt7djxzh.instrumentFunction(2);
        bjccovmt7djxzh.instrumentRegion(2, 1);
        return AppDb.settingsDao();
    }
    // ------------------------------------------------------------------
    // 账号行
    // ------------------------------------------------------------------
    async listAccountRows(): Promise<AccountRow[]> {
        bjccovmt7djxzh.instrumentFunction(3);
        const rs = await AppDb.store().querySql('SELECT * FROM accounts ORDER BY id ASC');
        const r = new RowReader(rs);
        const out: AccountRow[] = [];
        while (r.next()) {
            bjccovmt7djxzh.instrumentRegion(3, 1);
            out.push(accountRowFromReader(r));
        }
        bjccovmt7djxzh.instrumentRegion(3, 2);
        r.close();
        return out;
    }
    async accountRowById(id: number): Promise<AccountRow | null> {
        bjccovmt7djxzh.instrumentFunction(4);
        const rs = await AppDb.store().querySql('SELECT * FROM accounts WHERE id = ?', [id.toString()]);
        const r = new RowReader(rs);
        let out: AccountRow | null = null;
        if (r.next()) {
            bjccovmt7djxzh.instrumentBranch(4, 0, true);
            bjccovmt7djxzh.instrumentRegion(4, 1);
            out = accountRowFromReader(r);
        }
        else {
            bjccovmt7djxzh.instrumentBranch(4, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(4, 2);
        r.close();
        return out;
    }
    private async scalarInt(sql: string, args: Array<string> = []): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(5);
        const rs = await AppDb.store().querySql(sql, args);
        const r = new RowReader(rs);
        let v = 0;
        if (r.next()) {
            bjccovmt7djxzh.instrumentBranch(5, 0, true);
            bjccovmt7djxzh.instrumentRegion(5, 1);
            v = r.getLongAt(0);
        }
        else {
            bjccovmt7djxzh.instrumentBranch(5, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(5, 2);
        r.close();
        return v;
    }
    async minLoggedInId(): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(6);
        bjccovmt7djxzh.instrumentRegion(6, 1);
        return (await this.scalarInt('SELECT MIN(id) FROM accounts WHERE TRIM(token) != \'\''));
    }
    async minAnyId(): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(7);
        bjccovmt7djxzh.instrumentRegion(7, 1);
        return (await this.scalarInt('SELECT MIN(id) FROM accounts'));
    }
    async countAccounts(): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(8);
        bjccovmt7djxzh.instrumentRegion(8, 1);
        return this.scalarInt('SELECT COUNT(*) FROM accounts');
    }
    async countLoggedInAccounts(): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(9);
        bjccovmt7djxzh.instrumentRegion(9, 1);
        return this.scalarInt('SELECT COUNT(*) FROM accounts WHERE TRIM(token) != \'\'');
    }
    /** desktop add_account 显式取 MAX(id)+1 作主键 (保持 id 连续)。 */
    async nextAccountId(): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(10);
        bjccovmt7djxzh.instrumentRegion(10, 1);
        return (await this.scalarInt('SELECT COALESCE(MAX(id), 0) + 1 FROM accounts'));
    }
    async insertAccountRow(row: AccountRow): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(11);
        bjccovmt7djxzh.instrumentRegion(11, 1);
        await AppDb.store().executeSql(`INSERT INTO accounts (id, name, workspace_id, resolved_workspace_id, token, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`, [row.id.toString(), row.name, row.workspaceId, row.resolvedWorkspaceId, row.token, row.createdAt, row.updatedAt]);
    }
    async updateCredential(id: number, token: string, workspaceId: string, updatedAt: string): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(12);
        bjccovmt7djxzh.instrumentRegion(12, 1);
        await AppDb.store().executeSql('UPDATE accounts SET token = ?, workspace_id = ?, resolved_workspace_id = NULL, updated_at = ? WHERE id = ?', [token, workspaceId, updatedAt, id.toString()]);
    }
    async updateWorkspaceHint(id: number, workspaceId: string, updatedAt: string): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(13);
        bjccovmt7djxzh.instrumentRegion(13, 1);
        await AppDb.store().executeSql('UPDATE accounts SET workspace_id = ?, updated_at = ? WHERE id = ?', [workspaceId, updatedAt, id.toString()]);
    }
    async saveResolvedWorkspace(id: number, workspaceId: string, updatedAt: string): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(14);
        bjccovmt7djxzh.instrumentRegion(14, 1);
        await AppDb.store().executeSql('UPDATE accounts SET resolved_workspace_id = ?, updated_at = ? WHERE id = ?', [workspaceId, updatedAt, id.toString()]);
    }
    async renameAccountRow(id: number, name: string, updatedAt: string): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(15);
        bjccovmt7djxzh.instrumentRegion(15, 1);
        await AppDb.store().executeSql('UPDATE accounts SET name = ?, updated_at = ? WHERE id = ?', [name, updatedAt, id.toString()]);
    }
    async clearToken(id: number, updatedAt: string): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(16);
        bjccovmt7djxzh.instrumentRegion(16, 1);
        await AppDb.store().executeSql('UPDATE accounts SET token = \'\', resolved_workspace_id = NULL, updated_at = ? WHERE id = ?', [updatedAt, id.toString()]);
    }
    async deleteAccountRow(id: number): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(17);
        bjccovmt7djxzh.instrumentRegion(17, 1);
        await AppDb.store().executeSql('DELETE FROM accounts WHERE id = ?', [id.toString()]);
    }
    // ------------------------------------------------------------------
    // 活跃账号 (ActiveAccountPolicy 移植)
    // ------------------------------------------------------------------
    private static resolveActive(storedActiveId: number | null, accounts: Array<[
        number,
        boolean
    ]>): number {
        bjccovmt7djxzh.instrumentFunction(18);
        let loggedMin = 0;
        for (const a of accounts) {
            bjccovmt7djxzh.instrumentRegion(18, 1);
            if (a[1] && (loggedMin === 0 || a[0] < loggedMin)) {
                bjccovmt7djxzh.instrumentBranch(18, 0, true);
                bjccovmt7djxzh.instrumentRegion(18, 2);
                loggedMin = a[0];
            }
            else {
                bjccovmt7djxzh.instrumentBranch(18, 0, false);
            }
        }
        if (storedActiveId !== null && storedActiveId > 0) {
            bjccovmt7djxzh.instrumentBranch(18, 1, true);
            bjccovmt7djxzh.instrumentRegion(18, 3);
            let row: [
                number,
                boolean
            ] | null = null;
            for (const a of accounts) {
                bjccovmt7djxzh.instrumentRegion(18, 4);
                if (a[0] === storedActiveId) {
                    bjccovmt7djxzh.instrumentBranch(18, 2, true);
                    bjccovmt7djxzh.instrumentRegion(18, 5);
                    row = a;
                    break;
                }
                else {
                    bjccovmt7djxzh.instrumentBranch(18, 2, false);
                }
            }
            if (row !== null) {
                bjccovmt7djxzh.instrumentBranch(18, 3, true);
                bjccovmt7djxzh.instrumentRegion(18, 6);
                if (row[1]) {
                    bjccovmt7djxzh.instrumentBranch(18, 4, true);
                    bjccovmt7djxzh.instrumentRegion(18, 7);
                    return storedActiveId;
                }
                else {
                    bjccovmt7djxzh.instrumentBranch(18, 4, false);
                }
                if (loggedMin !== 0) {
                    bjccovmt7djxzh.instrumentBranch(18, 5, true);
                    bjccovmt7djxzh.instrumentRegion(18, 8);
                    return loggedMin; // 活跃行未登录但有其他已登录账号 -> 让位
                }
                else {
                    bjccovmt7djxzh.instrumentBranch(18, 5, false);
                }
                bjccovmt7djxzh.instrumentRegion(18, 13);
                return storedActiveId; // 全部未登录: 维持原选择
            }
            else {
                bjccovmt7djxzh.instrumentBranch(18, 3, false);
            }
        }
        else {
            bjccovmt7djxzh.instrumentBranch(18, 1, false);
        }
        if (loggedMin !== 0) {
            bjccovmt7djxzh.instrumentBranch(18, 6, true);
            bjccovmt7djxzh.instrumentRegion(18, 9);
            return loggedMin;
        }
        else {
            bjccovmt7djxzh.instrumentBranch(18, 6, false);
        }
        let fallback = 0;
        for (const a of accounts) {
            bjccovmt7djxzh.instrumentRegion(18, 10);
            if (fallback === 0 || a[0] < fallback) {
                bjccovmt7djxzh.instrumentBranch(18, 7, true);
                bjccovmt7djxzh.instrumentRegion(18, 11);
                fallback = a[0];
            }
            else {
                bjccovmt7djxzh.instrumentBranch(18, 7, false);
            }
        }
        bjccovmt7djxzh.instrumentRegion(18, 12);
        return fallback;
    }
    async getActiveAccountId(): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(19);
        const rows = await this.listAccountRows();
        const stored = await this.settings().readActiveAccountId();
        const resolved = SyncDao.resolveActive(stored, rows.map((row) => { bjccovmt7djxzh.instrumentFunction(20); return [row.id, row.token.trim().length > 0] as [
            number,
            boolean
        ]; }));
        if (rows.length > 0 && resolved !== (stored !== null ? (bjccovmt7djxzh.instrumentBranch(19, 1, true), stored) : (bjccovmt7djxzh.instrumentBranch(19, 1, false), 0))) {
            bjccovmt7djxzh.instrumentBranch(19, 0, true);
            bjccovmt7djxzh.instrumentRegion(19, 1);
            if (resolved > 0) {
                bjccovmt7djxzh.instrumentBranch(19, 2, true);
                bjccovmt7djxzh.instrumentRegion(19, 2);
                await this.settings().writeActiveAccountId(resolved);
            }
            else {
                bjccovmt7djxzh.instrumentBranch(19, 2, false);
                bjccovmt7djxzh.instrumentRegion(19, 3);
                await this.settings().removeActiveAccountId();
            }
        }
        else {
            bjccovmt7djxzh.instrumentBranch(19, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(19, 4);
        return resolved;
    }
    async setActiveAccount(accountId: number): Promise<boolean> {
        bjccovmt7djxzh.instrumentFunction(21);
        const row = await this.accountRowById(accountId);
        if (row === null) {
            bjccovmt7djxzh.instrumentBranch(21, 0, true);
            bjccovmt7djxzh.instrumentRegion(21, 1);
            return false;
        }
        else {
            bjccovmt7djxzh.instrumentBranch(21, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(21, 2);
        await this.settings().writeActiveAccountId(accountId);
        return true;
    }
    // ------------------------------------------------------------------
    // 账号摘要 / CRUD
    // ------------------------------------------------------------------
    async getAccount(): Promise<AccountInfo | null> {
        bjccovmt7djxzh.instrumentFunction(22);
        const aid = await this.getActiveAccountId();
        if (aid === 0) {
            bjccovmt7djxzh.instrumentBranch(22, 0, true);
            bjccovmt7djxzh.instrumentRegion(22, 1);
            return null;
        }
        else {
            bjccovmt7djxzh.instrumentBranch(22, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(22, 2);
        const row = await this.accountRowById(aid);
        return row === null ? (bjccovmt7djxzh.instrumentBranch(22, 1, true), null) : (bjccovmt7djxzh.instrumentBranch(22, 1, false), toInfo(row));
    }
    async listAccounts(): Promise<AccountInfo[]> {
        bjccovmt7djxzh.instrumentFunction(23);
        bjccovmt7djxzh.instrumentRegion(23, 1);
        const rows = await this.listAccountRows();
        return rows.map((row) => { bjccovmt7djxzh.instrumentFunction(24); return toInfo(row); });
    }
    /** 添加新账号; 相同 token 视为同一用户, 更新工作区提示后返回其 id。 */
    async addAccount(token: string, workspaceHint: string, switchNow: boolean = true): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(25);
        const trimmed = token.trim();
        const hint = workspaceHint.trim();
        const now = new Date().toISOString();
        if (trimmed.length > 0) {
            bjccovmt7djxzh.instrumentBranch(25, 0, true);
            bjccovmt7djxzh.instrumentRegion(25, 1);
            const rows = await this.listAccountRows();
            for (const existing of rows) {
                bjccovmt7djxzh.instrumentRegion(25, 2);
                if (existing.token.trim() === trimmed) {
                    bjccovmt7djxzh.instrumentBranch(25, 1, true);
                    bjccovmt7djxzh.instrumentRegion(25, 3);
                    if (hint.length > 0) {
                        bjccovmt7djxzh.instrumentBranch(25, 2, true);
                        bjccovmt7djxzh.instrumentRegion(25, 4);
                        await this.updateWorkspaceHint(existing.id, hint, now);
                    }
                    else {
                        bjccovmt7djxzh.instrumentBranch(25, 2, false);
                    }
                    if (switchNow) {
                        bjccovmt7djxzh.instrumentBranch(25, 3, true);
                        bjccovmt7djxzh.instrumentRegion(25, 5);
                        await this.settings().writeActiveAccountId(existing.id);
                    }
                    else {
                        bjccovmt7djxzh.instrumentBranch(25, 3, false);
                    }
                    bjccovmt7djxzh.instrumentRegion(25, 8);
                    return existing.id;
                }
                else {
                    bjccovmt7djxzh.instrumentBranch(25, 1, false);
                }
            }
        }
        else {
            bjccovmt7djxzh.instrumentBranch(25, 0, false);
        }
        const newId = await this.nextAccountId();
        await this.insertAccountRow({
            id: newId,
            name: hint.slice(0, 50).length > 0 ? (bjccovmt7djxzh.instrumentBranch(25, 4, true), hint.slice(0, 50)) : (bjccovmt7djxzh.instrumentBranch(25, 4, false), `User ${newId}`),
            workspaceId: hint.length > 0 ? (bjccovmt7djxzh.instrumentBranch(25, 5, true), hint) : (bjccovmt7djxzh.instrumentBranch(25, 5, false), 'Default'),
            resolvedWorkspaceId: null,
            token: trimmed,
            createdAt: now,
            updatedAt: now,
        });
        await this.ensureStateRow(newId);
        if (switchNow) {
            bjccovmt7djxzh.instrumentBranch(25, 6, true);
            bjccovmt7djxzh.instrumentRegion(25, 6);
            await this.settings().writeActiveAccountId(newId);
        }
        else {
            bjccovmt7djxzh.instrumentBranch(25, 6, false);
        }
        bjccovmt7djxzh.instrumentRegion(25, 7);
        return newId;
    }
    async renameAccount(accountId: number, name: string): Promise<boolean> {
        bjccovmt7djxzh.instrumentFunction(26);
        const cleaned = name.trim().slice(0, 50);
        if (cleaned.length === 0) {
            bjccovmt7djxzh.instrumentBranch(26, 0, true);
            bjccovmt7djxzh.instrumentRegion(26, 1);
            return false;
        }
        else {
            bjccovmt7djxzh.instrumentBranch(26, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(26, 2);
        await this.renameAccountRow(accountId, cleaned, new Date().toISOString());
        return true;
    }
    /** 删除账号及其本地全部数据 (级联), 返回剩余账号数。 */
    async deleteAccount(accountId: number): Promise<number> {
        bjccovmt7djxzh.instrumentFunction(27);
        await AppDb.store().executeSql('DELETE FROM usage_records WHERE account_id = ?', [accountId.toString()]);
        await AppDb.store().executeSql('DELETE FROM usage_sync_state WHERE account_id = ?', [accountId.toString()]);
        await this.deleteAccountRow(accountId);
        const remaining = await this.countAccounts();
        const stored = await this.settings().readActiveAccountId();
        if (stored === accountId) {
            bjccovmt7djxzh.instrumentBranch(27, 0, true);
            bjccovmt7djxzh.instrumentRegion(27, 1);
            const nxt = await this.minAnyId();
            if (nxt !== 0) {
                bjccovmt7djxzh.instrumentBranch(27, 1, true);
                bjccovmt7djxzh.instrumentRegion(27, 2);
                await this.settings().writeActiveAccountId(nxt);
            }
            else {
                bjccovmt7djxzh.instrumentBranch(27, 1, false);
                bjccovmt7djxzh.instrumentRegion(27, 3);
                await this.settings().removeActiveAccountId();
            }
        }
        else {
            bjccovmt7djxzh.instrumentBranch(27, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(27, 4);
        return remaining;
    }
    /** 退出登录当前活跃账号: 清凭证与本地缓存数据 (保留账号行)。 */
    async clearAccount(): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(28);
        const aid = await this.getActiveAccountId();
        if (aid === 0) {
            bjccovmt7djxzh.instrumentBranch(28, 0, true);
            bjccovmt7djxzh.instrumentRegion(28, 1);
            return;
        }
        else {
            bjccovmt7djxzh.instrumentBranch(28, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(28, 2);
        await AppDb.store().executeSql('DELETE FROM usage_records WHERE account_id = ?', [aid.toString()]);
        await this.clearToken(aid, new Date().toISOString());
        await this.ensureStateRow(aid);
        await this.resetSyncStateForAccount(aid);
    }
    /** 重新登录语义: 更新活跃账号凭证并重置其增量游标。 */
    async saveToken(token: string, workspaceId: string): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(29);
        const aid = await this.getActiveAccountId();
        if (aid === 0) {
            bjccovmt7djxzh.instrumentBranch(29, 0, true);
            bjccovmt7djxzh.instrumentRegion(29, 1);
            return;
        }
        else {
            bjccovmt7djxzh.instrumentBranch(29, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(29, 2);
        await this.updateCredential(aid, token.trim(), workspaceId.trim().length > 0 ? (bjccovmt7djxzh.instrumentBranch(29, 1, true), workspaceId.trim()) : (bjccovmt7djxzh.instrumentBranch(29, 1, false), 'Default'), new Date().toISOString());
        await this.ensureStateRow(aid);
        await this.resetCursorForAccount(aid);
    }
    // ------------------------------------------------------------------
    // 同步状态
    // ------------------------------------------------------------------
    async ensureStateRow(accountId: number): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(30);
        const rs = await AppDb.store().querySql('SELECT account_id FROM usage_sync_state WHERE account_id = ?', [accountId.toString()]);
        const r = new RowReader(rs);
        const exists = r.next();
        r.close();
        if (!exists) {
            bjccovmt7djxzh.instrumentBranch(30, 0, true);
            bjccovmt7djxzh.instrumentRegion(30, 1);
            await AppDb.store().executeSql('INSERT INTO usage_sync_state (account_id, deepest_page_fetched) VALUES (?, -1)', [accountId.toString()]);
        }
        else {
            bjccovmt7djxzh.instrumentBranch(30, 0, false);
        }
    }
    async bumpSyncState(accountId: number, status: string, error: string | null, inserted: number, at: string): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(31);
        bjccovmt7djxzh.instrumentRegion(31, 1);
        await AppDb.store().executeSql(`UPDATE usage_sync_state
       SET last_sync_at = ?, last_sync_status = ?, last_sync_error = ?, last_inserted_count = last_inserted_count + ?
       WHERE account_id = ?`, [at, status, error, inserted.toString(), accountId.toString()]);
    }
    async resetSyncStateForAccount(accountId: number): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(32);
        bjccovmt7djxzh.instrumentRegion(32, 1);
        await AppDb.store().executeSql(`UPDATE usage_sync_state
       SET last_sync_status = NULL, last_sync_error = NULL, last_inserted_count = 0,
           deepest_page_fetched = -1, total_records = 0, oldest_record_at = NULL, newest_record_at = NULL
       WHERE account_id = ?`, [accountId.toString()]);
    }
    async resetCursorForAccount(accountId: number): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(33);
        bjccovmt7djxzh.instrumentRegion(33, 1);
        await AppDb.store().executeSql('UPDATE usage_sync_state SET deepest_page_fetched = -1 WHERE account_id = ?', [accountId.toString()]);
    }
    private async recordBounds(accountId: number): Promise<[
        number,
        string | null,
        string | null
    ]> {
        bjccovmt7djxzh.instrumentFunction(34);
        const rs = await AppDb.store().querySql(`SELECT COUNT(*) AS count, MIN(created_at) AS oldest, MAX(created_at) AS newest
       FROM usage_records WHERE account_id = ?`, [accountId.toString()]);
        const r = new RowReader(rs);
        let out: [
            number,
            string | null,
            string | null
        ] = [0, null, null];
        if (r.next()) {
            bjccovmt7djxzh.instrumentBranch(34, 0, true);
            bjccovmt7djxzh.instrumentRegion(34, 1);
            out = [
                r.getLong('count'),
                r.isNull('oldest') ? (bjccovmt7djxzh.instrumentBranch(34, 1, true), null) : (bjccovmt7djxzh.instrumentBranch(34, 1, false), r.getStr('oldest')),
                r.isNull('newest') ? (bjccovmt7djxzh.instrumentBranch(34, 2, true), null) : (bjccovmt7djxzh.instrumentBranch(34, 2, false), r.getStr('newest')),
            ];
        }
        else {
            bjccovmt7djxzh.instrumentBranch(34, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(34, 2);
        r.close();
        return out;
    }
    /** 持久化同步结果并刷新 totals —— db.update_sync_state + _refresh_sync_totals。 */
    async updateSyncStateAndTotals(accountId: number, status: string, error: string | null, inserted: number): Promise<void> {
        bjccovmt7djxzh.instrumentFunction(35);
        bjccovmt7djxzh.instrumentRegion(35, 1);
        await this.ensureStateRow(accountId);
        await this.bumpSyncState(accountId, status, error, inserted, new Date().toISOString());
        const b = await this.recordBounds(accountId);
        await AppDb.store().executeSql('UPDATE usage_sync_state SET total_records = ?, oldest_record_at = ?, newest_record_at = ? WHERE account_id = ?', [b[0].toString(), b[1], b[2], accountId.toString()]);
    }
    async getSyncStateFor(accountId: number): Promise<SyncState> {
        bjccovmt7djxzh.instrumentFunction(36);
        const rs = await AppDb.store().querySql('SELECT * FROM usage_sync_state WHERE account_id = ?', [accountId.toString()]);
        const r = new RowReader(rs);
        let out: SyncState = emptySyncState();
        if (r.next()) {
            bjccovmt7djxzh.instrumentBranch(36, 0, true);
            bjccovmt7djxzh.instrumentRegion(36, 1);
            out = {
                lastSyncAt: r.isNull('last_sync_at') ? (bjccovmt7djxzh.instrumentBranch(36, 1, true), null) : (bjccovmt7djxzh.instrumentBranch(36, 1, false), r.getStr('last_sync_at')),
                lastSyncStatus: r.isNull('last_sync_status') ? (bjccovmt7djxzh.instrumentBranch(36, 2, true), null) : (bjccovmt7djxzh.instrumentBranch(36, 2, false), r.getStr('last_sync_status')),
                lastSyncError: r.isNull('last_sync_error') ? (bjccovmt7djxzh.instrumentBranch(36, 3, true), null) : (bjccovmt7djxzh.instrumentBranch(36, 3, false), r.getStr('last_sync_error')),
                lastInsertedCount: r.getLong('last_inserted_count'),
                deepestPageFetched: r.getLong('deepest_page_fetched'),
                totalRecords: r.getLong('total_records'),
                oldestRecordAt: r.isNull('oldest_record_at') ? (bjccovmt7djxzh.instrumentBranch(36, 4, true), null) : (bjccovmt7djxzh.instrumentBranch(36, 4, false), r.getStr('oldest_record_at')),
                newestRecordAt: r.isNull('newest_record_at') ? (bjccovmt7djxzh.instrumentBranch(36, 5, true), null) : (bjccovmt7djxzh.instrumentBranch(36, 5, false), r.getStr('newest_record_at')),
            };
        }
        else {
            bjccovmt7djxzh.instrumentBranch(36, 0, false);
        }
        bjccovmt7djxzh.instrumentRegion(36, 2);
        r.close();
        return out;
    }
    async getSyncState(): Promise<SyncState> {
        bjccovmt7djxzh.instrumentFunction(37);
        bjccovmt7djxzh.instrumentRegion(37, 1);
        return this.getSyncStateFor(await this.getActiveAccountId());
    }
    async getTokenFor(accountId: number): Promise<string> {
        bjccovmt7djxzh.instrumentFunction(38);
        bjccovmt7djxzh.instrumentRegion(38, 1);
        const row = await this.accountRowById(accountId);
        return row === null ? (bjccovmt7djxzh.instrumentBranch(38, 0, true), '') : (bjccovmt7djxzh.instrumentBranch(38, 0, false), row.token.trim());
    }
    async getWorkspaceHintFor(accountId: number): Promise<string> {
        bjccovmt7djxzh.instrumentFunction(39);
        const row = await this.accountRowById(accountId);
        if (row === null) {
            bjccovmt7djxzh.instrumentBranch(39, 0, true);
            bjccovmt7djxzh.instrumentRegion(39, 1);
            return 'Default';
        }
        else {
            bjccovmt7djxzh.instrumentBranch(39, 0, false);
        }
        if (row.resolvedWorkspaceId !== null && row.resolvedWorkspaceId.length > 0) {
            bjccovmt7djxzh.instrumentBranch(39, 1, true);
            bjccovmt7djxzh.instrumentRegion(39, 2);
            return row.resolvedWorkspaceId;
        }
        else {
            bjccovmt7djxzh.instrumentBranch(39, 1, false);
        }
        bjccovmt7djxzh.instrumentRegion(39, 3);
        return row.workspaceId.length > 0 ? (bjccovmt7djxzh.instrumentBranch(39, 2, true), row.workspaceId) : (bjccovmt7djxzh.instrumentBranch(39, 2, false), 'Default');
    }
}
