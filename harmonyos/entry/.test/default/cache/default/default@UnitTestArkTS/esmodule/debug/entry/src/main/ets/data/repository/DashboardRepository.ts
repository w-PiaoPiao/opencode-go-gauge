import { AppDb } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/AppDb";
import type { UsageDao, UsageRecordEntity } from '../db/UsageDao';
import type { SyncDao } from '../db/SyncDao';
import { OpenCodeApi } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/remote/OpenCodeApi";
import { ExchangeApi } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/remote/ExchangeApi";
import { emptySyncProgress, } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/common/model/Models";
import type { AccountInfo, AppSettings, DashboardData, DailyStat, HourStat, ModelStat, PageResult, QuotaResult, SessionStat, SyncProgress, SyncResult, SyncState, Totals, UsageRecord, UsageRecordRow } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/common/model/Models";
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
let bjccovmt7djxwp = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/repository/DashboardRepository.ets", hash: "7f13bef6efc5a96c4c2b442c54e3f529353eec2921a7f6fa6e16fcd149474ca2", lineCnt: 557, count: 0, projectPath: "", functions: { 0: { name: "DashboardRepository.progress", count: 0, regions: { 0: { startLoc: { line: 41, col: 3 }, endLoc: { line: 43, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 42, col: 5 }, endLoc: { line: 43, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "DashboardRepository.updateProgress", count: 0, regions: { 0: { startLoc: { line: 45, col: 3 }, endLoc: { line: 58, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 46, col: 5 }, endLoc: { line: 58, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "anonymous_0", count: 0, regions: { 0: { startLoc: { line: 45, col: 30 }, endLoc: { line: 45, col: 55 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 2 }, 3: { name: "DashboardRepository.activeAccountId", count: 0, regions: { 0: { startLoc: { line: 64, col: 3 }, endLoc: { line: 66, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 65, col: 5 }, endLoc: { line: 66, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 3 }, 4: { name: "DashboardRepository.accounts", count: 0, regions: { 0: { startLoc: { line: 68, col: 3 }, endLoc: { line: 70, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 69, col: 5 }, endLoc: { line: 70, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 4 }, 5: { name: "DashboardRepository.countLoggedInAccounts", count: 0, regions: { 0: { startLoc: { line: 72, col: 3 }, endLoc: { line: 74, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 73, col: 5 }, endLoc: { line: 74, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 5 }, 6: { name: "DashboardRepository.account", count: 0, regions: { 0: { startLoc: { line: 76, col: 3 }, endLoc: { line: 78, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 77, col: 5 }, endLoc: { line: 78, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 6 }, 7: { name: "DashboardRepository.switchAccount", count: 0, regions: { 0: { startLoc: { line: 80, col: 3 }, endLoc: { line: 86, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 82, col: 13 }, endLoc: { line: 84, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 85, col: 5 }, endLoc: { line: 86, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 82, col: 9 }, endLoc: { line: 82, col: 11 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 7 }, 8: { name: "DashboardRepository.renameAccount", count: 0, regions: { 0: { startLoc: { line: 88, col: 3 }, endLoc: { line: 90, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 89, col: 5 }, endLoc: { line: 90, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 8 }, 9: { name: "DashboardRepository.deleteAccount", count: 0, regions: { 0: { startLoc: { line: 93, col: 3 }, endLoc: { line: 97, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 94, col: 5 }, endLoc: { line: 97, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 9 }, 10: { name: "DashboardRepository.loginSuccess", count: 0, regions: { 0: { startLoc: { line: 100, col: 3 }, endLoc: { line: 107, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 101, col: 25 }, endLoc: { line: 103, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 103, col: 12 }, endLoc: { line: 105, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 106, col: 5 }, endLoc: { line: 107, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 101, col: 9 }, endLoc: { line: 101, col: 23 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 104, col: 43 }, endLoc: { line: 104, col: 109 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 10 }, 11: { name: "DashboardRepository.ensureQuota", count: 0, regions: { 0: { startLoc: { line: 113, col: 3 }, endLoc: { line: 144, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 115, col: 26 }, endLoc: { line: 117, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 120, col: 106 }, endLoc: { line: 122, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 123, col: 46 }, endLoc: { line: 125, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 127, col: 29 }, endLoc: { line: 129, col: 6 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 131, col: 9 }, endLoc: { line: 141, col: 6 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 141, col: 15 }, endLoc: { line: 143, col: 6 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 135, col: 11 }, endLoc: { line: 137, col: 8 }, count: 0, ignored: 0 }, 8: { startLoc: { line: 137, col: 9 }, endLoc: { line: 139, col: 8 }, count: 0, ignored: 0 }, 9: { startLoc: { line: 140, col: 7 }, endLoc: { line: 141, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 115, col: 9 }, endLoc: { line: 115, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 120, col: 9 }, endLoc: { line: 120, col: 104 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 123, col: 9 }, endLoc: { line: 123, col: 44 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 127, col: 9 }, endLoc: { line: 127, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 11 }, 12: { name: "DashboardRepository.currentQuota", count: 0, regions: { 0: { startLoc: { line: 146, col: 3 }, endLoc: { line: 150, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 147, col: 5 }, endLoc: { line: 150, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 149, col: 12 }, endLoc: { line: 149, col: 49 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 12 }, 13: { name: "DashboardRepository.usdCny", count: 0, regions: { 0: { startLoc: { line: 152, col: 3 }, endLoc: { line: 167, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 154, col: 73 }, endLoc: { line: 156, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 157, col: 9 }, endLoc: { line: 162, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 162, col: 7 }, endLoc: { line: 164, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 159, col: 21 }, endLoc: { line: 161, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 165, col: 5 }, endLoc: { line: 167, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 154, col: 9 }, endLoc: { line: 154, col: 71 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 159, col: 11 }, endLoc: { line: 159, col: 19 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 13 }, 14: { name: "DashboardRepository.fmtServerTime", count: 0, regions: { 0: { startLoc: { line: 173, col: 3 }, endLoc: { line: 177, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 174, col: 5 }, endLoc: { line: 177, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 14 }, 15: { name: "anonymous_1", count: 0, regions: { 0: { startLoc: { line: 175, col: 15 }, endLoc: { line: 175, col: 64 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 15 }, 16: { name: "DashboardRepository.loadDashboard", count: 0, regions: { 0: { startLoc: { line: 179, col: 3 }, endLoc: { line: 209, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 180, col: 5 }, endLoc: { line: 209, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 196, col: 14 }, endLoc: { line: 196, col: 72 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 16 }, 17: { name: "DashboardRepository.syncUsage", count: 0, regions: { 0: { startLoc: { line: 215, col: 3 }, endLoc: { line: 287, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 219, col: 26 }, endLoc: { line: 226, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 226, col: 12 }, endLoc: { line: 233, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 222, col: 41 }, endLoc: { line: 225, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 228, col: 7 }, endLoc: { line: 232, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 229, col: 25 }, endLoc: { line: 231, col: 10 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 234, col: 31 }, endLoc: { line: 236, col: 6 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 237, col: 33 }, endLoc: { line: 239, col: 6 }, count: 0, ignored: 0 }, 8: { startLoc: { line: 246, col: 9 }, endLoc: { line: 280, col: 6 }, count: 0, ignored: 0 }, 9: { startLoc: { line: 280, col: 7 }, endLoc: { line: 284, col: 6 }, count: 0, ignored: 0 }, 10: { startLoc: { line: 284, col: 15 }, endLoc: { line: 286, col: 6 }, count: 0, ignored: 0 }, 11: { startLoc: { line: 252, col: 7 }, endLoc: { line: 270, col: 8 }, count: 0, ignored: 0 }, 12: { startLoc: { line: 259, col: 25 }, endLoc: { line: 266, col: 10 }, count: 0, ignored: 0 }, 13: { startLoc: { line: 261, col: 39 }, endLoc: { line: 265, col: 12 }, count: 0, ignored: 0 }, 14: { startLoc: { line: 267, col: 29 }, endLoc: { line: 269, col: 10 }, count: 0, ignored: 0 }, 15: { startLoc: { line: 272, col: 71 }, endLoc: { line: 276, col: 8 }, count: 0, ignored: 0 }, 16: { startLoc: { line: 277, col: 7 }, endLoc: { line: 280, col: 6 }, count: 0, ignored: 0 }, 17: { startLoc: { line: 263, col: 61 }, endLoc: { line: 263, col: 78 }, count: 0, ignored: 0 }, 18: { startLoc: { line: 274, col: 56 }, endLoc: { line: 274, col: 73 }, count: 0, ignored: 0 }, 19: { startLoc: { line: 278, col: 54 }, endLoc: { line: 278, col: 71 }, count: 0, ignored: 0 }, 20: { startLoc: { line: 282, col: 55 }, endLoc: { line: 282, col: 75 }, count: 0, ignored: 0 }, 21: { startLoc: { line: 285, col: 55 }, endLoc: { line: 285, col: 71 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 219, col: 9 }, endLoc: { line: 219, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 221, col: 20 }, endLoc: { line: 221, col: 72 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 222, col: 11 }, endLoc: { line: 222, col: 39 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 224, col: 28 }, endLoc: { line: 224, col: 65 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 229, col: 13 }, endLoc: { line: 229, col: 23 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 234, col: 9 }, endLoc: { line: 234, col: 29 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 6: { startLoc: { line: 237, col: 9 }, endLoc: { line: 237, col: 31 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 7: { startLoc: { line: 259, col: 13 }, endLoc: { line: 259, col: 23 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 8: { startLoc: { line: 260, col: 22 }, endLoc: { line: 260, col: 67 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 9: { startLoc: { line: 261, col: 15 }, endLoc: { line: 261, col: 37 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 10: { startLoc: { line: 267, col: 13 }, endLoc: { line: 267, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 11: { startLoc: { line: 272, col: 11 }, endLoc: { line: 272, col: 69 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 12: { startLoc: { line: 273, col: 21 }, endLoc: { line: 273, col: 71 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 13: { startLoc: { line: 281, col: 22 }, endLoc: { line: 281, col: 88 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 17 }, 18: { name: "anonymous_2", count: 0, regions: { 0: { startLoc: { line: 255, col: 29 }, endLoc: { line: 255, col: 56 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 255, col: 38 }, endLoc: { line: 255, col: 56 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 18 }, 19: { name: "anonymous_3", count: 0, regions: { 0: { startLoc: { line: 263, col: 33 }, endLoc: { line: 263, col: 78 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 19 }, 20: { name: "anonymous_4", count: 0, regions: { 0: { startLoc: { line: 274, col: 29 }, endLoc: { line: 274, col: 73 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 20 }, 21: { name: "anonymous_5", count: 0, regions: { 0: { startLoc: { line: 278, col: 27 }, endLoc: { line: 278, col: 71 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 21 }, 22: { name: "anonymous_6", count: 0, regions: { 0: { startLoc: { line: 282, col: 27 }, endLoc: { line: 282, col: 75 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 22 }, 23: { name: "anonymous_7", count: 0, regions: { 0: { startLoc: { line: 285, col: 27 }, endLoc: { line: 285, col: 71 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 23 }, 24: { name: "DashboardRepository.syncOneAccount", count: 0, regions: { 0: { startLoc: { line: 290, col: 3 }, endLoc: { line: 433, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 294, col: 29 }, endLoc: { line: 296, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 299, col: 9 }, endLoc: { line: 428, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 428, col: 7 }, endLoc: { line: 432, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 301, col: 11 }, endLoc: { line: 307, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 307, col: 9 }, endLoc: { line: 312, col: 8 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 303, col: 46 }, endLoc: { line: 306, col: 10 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 321, col: 7 }, endLoc: { line: 401, col: 8 }, count: 0, ignored: 0 }, 8: { startLoc: { line: 324, col: 9 }, endLoc: { line: 326, col: 10 }, count: 0, ignored: 0 }, 9: { startLoc: { line: 334, col: 9 }, endLoc: { line: 371, col: 10 }, count: 0, ignored: 0 }, 10: { startLoc: { line: 336, col: 56 }, endLoc: { line: 339, col: 12 }, count: 0, ignored: 0 }, 11: { startLoc: { line: 340, col: 36 }, endLoc: { line: 342, col: 12 }, count: 0, ignored: 0 }, 12: { startLoc: { line: 343, col: 55 }, endLoc: { line: 361, col: 12 }, count: 0, ignored: 0 }, 13: { startLoc: { line: 345, col: 13 }, endLoc: { line: 349, col: 14 }, count: 0, ignored: 0 }, 14: { startLoc: { line: 346, col: 68 }, endLoc: { line: 348, col: 16 }, count: 0, ignored: 0 }, 15: { startLoc: { line: 350, col: 38 }, endLoc: { line: 360, col: 14 }, count: 0, ignored: 0 }, 16: { startLoc: { line: 351, col: 19 }, endLoc: { line: 357, col: 16 }, count: 0, ignored: 0 }, 17: { startLoc: { line: 357, col: 17 }, endLoc: { line: 359, col: 16 }, count: 0, ignored: 0 }, 18: { startLoc: { line: 354, col: 57 }, endLoc: { line: 356, col: 18 }, count: 0, ignored: 0 }, 19: { startLoc: { line: 367, col: 36 }, endLoc: { line: 369, col: 12 }, count: 0, ignored: 0 }, 20: { startLoc: { line: 375, col: 36 }, endLoc: { line: 377, col: 10 }, count: 0, ignored: 0 }, 21: { startLoc: { line: 378, col: 30 }, endLoc: { line: 389, col: 10 }, count: 0, ignored: 0 }, 22: { startLoc: { line: 380, col: 39 }, endLoc: { line: 388, col: 12 }, count: 0, ignored: 0 }, 23: { startLoc: { line: 390, col: 35 }, endLoc: { line: 392, col: 10 }, count: 0, ignored: 0 }, 24: { startLoc: { line: 393, col: 60 }, endLoc: { line: 398, col: 10 }, count: 0, ignored: 0 }, 25: { startLoc: { line: 398, col: 16 }, endLoc: { line: 400, col: 10 }, count: 0, ignored: 0 }, 26: { startLoc: { line: 395, col: 34 }, endLoc: { line: 397, col: 12 }, count: 0, ignored: 0 }, 27: { startLoc: { line: 403, col: 32 }, endLoc: { line: 405, col: 8 }, count: 0, ignored: 0 }, 28: { startLoc: { line: 408, col: 11 }, endLoc: { line: 417, col: 8 }, count: 0, ignored: 0 }, 29: { startLoc: { line: 417, col: 9 }, endLoc: { line: 419, col: 8 }, count: 0, ignored: 0 }, 30: { startLoc: { line: 410, col: 29 }, endLoc: { line: 416, col: 10 }, count: 0, ignored: 0 }, 31: { startLoc: { line: 421, col: 28 }, endLoc: { line: 425, col: 8 }, count: 0, ignored: 0 }, 32: { startLoc: { line: 426, col: 7 }, endLoc: { line: 428, col: 6 }, count: 0, ignored: 0 }, 33: { startLoc: { line: 310, col: 57 }, endLoc: { line: 310, col: 74 }, count: 0, ignored: 0 }, 34: { startLoc: { line: 370, col: 11 }, endLoc: { line: 371, col: 10 }, count: 0, ignored: 0 }, 35: { startLoc: { line: 385, col: 15 }, endLoc: { line: 386, col: 14 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 294, col: 9 }, endLoc: { line: 294, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 303, col: 13 }, endLoc: { line: 303, col: 44 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 315, col: 24 }, endLoc: { line: 315, col: 50 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 336, col: 15 }, endLoc: { line: 336, col: 54 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 340, col: 15 }, endLoc: { line: 340, col: 34 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 343, col: 15 }, endLoc: { line: 343, col: 53 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 6: { startLoc: { line: 346, col: 19 }, endLoc: { line: 346, col: 66 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 7: { startLoc: { line: 350, col: 17 }, endLoc: { line: 350, col: 36 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 8: { startLoc: { line: 354, col: 21 }, endLoc: { line: 354, col: 55 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 9: { startLoc: { line: 367, col: 15 }, endLoc: { line: 367, col: 34 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 10: { startLoc: { line: 375, col: 13 }, endLoc: { line: 375, col: 34 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 11: { startLoc: { line: 378, col: 13 }, endLoc: { line: 378, col: 28 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 12: { startLoc: { line: 380, col: 15 }, endLoc: { line: 380, col: 37 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 13: { startLoc: { line: 390, col: 13 }, endLoc: { line: 390, col: 33 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 14: { startLoc: { line: 393, col: 13 }, endLoc: { line: 393, col: 58 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 15: { startLoc: { line: 395, col: 15 }, endLoc: { line: 395, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 16: { startLoc: { line: 403, col: 11 }, endLoc: { line: 403, col: 30 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 17: { startLoc: { line: 410, col: 13 }, endLoc: { line: 410, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 18: { startLoc: { line: 421, col: 11 }, endLoc: { line: 421, col: 26 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 19: { startLoc: { line: 429, col: 22 }, endLoc: { line: 429, col: 88 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 24 }, 25: { name: "anonymous_8", count: 0, regions: { 0: { startLoc: { line: 310, col: 29 }, endLoc: { line: 310, col: 74 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 25 }, 26: { name: "anonymous_9", count: 0, regions: { 0: { startLoc: { line: 327, col: 29 }, endLoc: { line: 327, col: 53 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 327, col: 38 }, endLoc: { line: 327, col: 53 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 26 }, 27: { name: "anonymous_10", count: 0, regions: { 0: { startLoc: { line: 363, col: 60 }, endLoc: { line: 363, col: 99 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 27 }, 28: { name: "anonymous_11", count: 0, regions: { 0: { startLoc: { line: 370, col: 31 }, endLoc: { line: 370, col: 68 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 370, col: 40 }, endLoc: { line: 370, col: 68 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 28 }, 29: { name: "anonymous_12", count: 0, regions: { 0: { startLoc: { line: 383, col: 33 }, endLoc: { line: 386, col: 14 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 29 }, 30: { name: "anonymous_13", count: 0, regions: { 0: { startLoc: { line: 412, col: 25 }, endLoc: { line: 414, col: 12 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 413, col: 13 }, endLoc: { line: 414, col: 12 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 30 }, 31: { name: "DashboardRepository.fetchBatch", count: 0, regions: { 0: { startLoc: { line: 436, col: 3 }, endLoc: { line: 452, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 441, col: 5 }, endLoc: { line: 449, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 450, col: 5 }, endLoc: { line: 452, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 31 }, 32: { name: "anonymous_14", count: 0, regions: { 0: { startLoc: { line: 442, col: 19 }, endLoc: { line: 448, col: 8 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 443, col: 13 }, endLoc: { line: 445, col: 10 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 445, col: 11 }, endLoc: { line: 447, col: 10 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 32 }, 33: { name: "DashboardRepository.syncAll", count: 0, regions: { 0: { startLoc: { line: 454, col: 3 }, endLoc: { line: 457, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 455, col: 5 }, endLoc: { line: 457, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 33 }, 34: { name: "DashboardRepository.recordsPage", count: 0, regions: { 0: { startLoc: { line: 463, col: 3 }, endLoc: { line: 480, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 469, col: 25 }, endLoc: { line: 478, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 470, col: 7 }, endLoc: { line: 477, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 471, col: 31 }, endLoc: { line: 476, col: 10 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 473, col: 32 }, endLoc: { line: 475, col: 12 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 479, col: 5 }, endLoc: { line: 480, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 469, col: 9 }, endLoc: { line: 469, col: 23 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 471, col: 13 }, endLoc: { line: 471, col: 29 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 473, col: 15 }, endLoc: { line: 473, col: 30 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 34 }, 35: { name: "DashboardRepository.sessionsPage", count: 0, regions: { 0: { startLoc: { line: 482, col: 3 }, endLoc: { line: 501, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 488, col: 5 }, endLoc: { line: 499, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 490, col: 21 }, endLoc: { line: 492, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 493, col: 30 }, endLoc: { line: 498, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 495, col: 46 }, endLoc: { line: 497, col: 10 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 500, col: 5 }, endLoc: { line: 501, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 490, col: 11 }, endLoc: { line: 490, col: 19 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 493, col: 11 }, endLoc: { line: 493, col: 28 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 495, col: 13 }, endLoc: { line: 495, col: 44 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 35 }, 36: { name: "DashboardRepository.listModels", count: 0, regions: { 0: { startLoc: { line: 503, col: 3 }, endLoc: { line: 505, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 504, col: 5 }, endLoc: { line: 505, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 36 }, 37: { name: "DashboardRepository.syncState", count: 0, regions: { 0: { startLoc: { line: 507, col: 3 }, endLoc: { line: 509, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 508, col: 5 }, endLoc: { line: 509, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 37 }, 38: { name: "DashboardRepository.settings", count: 0, regions: { 0: { startLoc: { line: 511, col: 3 }, endLoc: { line: 513, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 512, col: 5 }, endLoc: { line: 513, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 38 }, 39: { name: "DashboardRepository.saveSettings", count: 0, regions: { 0: { startLoc: { line: 515, col: 3 }, endLoc: { line: 517, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 516, col: 5 }, endLoc: { line: 517, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 39 }, 40: { name: "DashboardRepository.logout", count: 0, regions: { 0: { startLoc: { line: 520, col: 3 }, endLoc: { line: 522, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 521, col: 5 }, endLoc: { line: 522, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 40 }, 41: { name: "toEntity", count: 0, regions: { 0: { startLoc: { line: 525, col: 1 }, endLoc: { line: 545, col: 2 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 526, col: 3 }, endLoc: { line: 545, col: 2 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 41 }, 42: { name: "Repo.get", count: 0, regions: { 0: { startLoc: { line: 551, col: 3 }, endLoc: { line: 556, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 552, col: 33 }, endLoc: { line: 554, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 555, col: 5 }, endLoc: { line: 556, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 552, col: 9 }, endLoc: { line: 552, col: 31 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 42 } }, exeLine: { 0: 7, 1: 8, 2: 9, 3: 10, 4: 11, 5: 12, 6: 13, 7: 14, 8: 15, 9: 17, 10: 18, 11: 19, 12: 22, 13: 23, 14: 24, 15: 27, 16: 28, 17: 29, 18: 30, 19: 32, 20: 33, 21: 34, 22: 36, 23: 37, 24: 39, 25: 41, 26: 42, 27: 45, 28: 46, 29: 47, 30: 48, 31: 49, 32: 50, 33: 51, 34: 52, 35: 53, 36: 54, 37: 56, 38: 57, 39: 64, 40: 65, 41: 68, 42: 69, 43: 72, 44: 73, 45: 76, 46: 77, 47: 80, 48: 81, 49: 82, 50: 83, 51: 85, 52: 88, 53: 89, 54: 93, 55: 94, 56: 95, 57: 96, 58: 100, 59: 101, 60: 102, 61: 103, 62: 104, 63: 106, 64: 113, 65: 114, 66: 115, 67: 116, 68: 118, 69: 119, 70: 120, 71: 121, 72: 123, 73: 124, 74: 126, 75: 127, 76: 128, 77: 130, 78: 131, 79: 132, 80: 133, 81: 134, 82: 135, 83: 136, 84: 137, 85: 138, 86: 140, 87: 141, 88: 142, 89: 146, 90: 147, 91: 148, 92: 149, 93: 152, 94: 153, 95: 154, 96: 155, 97: 157, 98: 158, 99: 159, 100: 160, 101: 162, 102: 165, 103: 166, 104: 173, 105: 174, 106: 175, 107: 176, 108: 179, 109: 180, 110: 181, 111: 183, 112: 184, 113: 185, 114: 186, 115: 187, 116: 188, 117: 189, 118: 190, 119: 191, 120: 192, 121: 194, 122: 195, 123: 196, 124: 197, 125: 198, 126: 199, 127: 200, 128: 201, 129: 202, 130: 203, 131: 204, 132: 205, 133: 206, 134: 207, 135: 215, 136: 217, 137: 218, 138: 219, 139: 220, 140: 221, 141: 222, 142: 223, 143: 224, 144: 226, 145: 227, 146: 228, 147: 229, 148: 230, 149: 234, 150: 235, 151: 237, 152: 238, 153: 241, 154: 242, 155: 244, 156: 246, 157: 247, 158: 248, 159: 249, 160: 250, 161: 252, 162: 253, 163: 254, 164: 255, 165: 256, 166: 257, 167: 258, 168: 259, 169: 260, 170: 261, 171: 262, 172: 263, 173: 264, 174: 267, 175: 268, 176: 272, 177: 273, 178: 274, 179: 275, 180: 277, 181: 278, 182: 279, 183: 280, 184: 281, 185: 282, 186: 283, 187: 284, 188: 285, 189: 290, 190: 291, 191: 292, 192: 293, 193: 294, 194: 295, 195: 297, 196: 299, 197: 301, 198: 302, 199: 303, 200: 304, 201: 305, 202: 307, 203: 308, 204: 309, 205: 310, 206: 311, 207: 314, 208: 315, 209: 316, 210: 317, 211: 318, 212: 319, 213: 321, 214: 322, 215: 323, 216: 324, 217: 325, 218: 327, 219: 329, 220: 331, 221: 332, 222: 333, 223: 334, 224: 335, 225: 336, 226: 337, 227: 338, 228: 340, 229: 341, 230: 343, 231: 344, 232: 345, 233: 346, 234: 347, 235: 350, 236: 351, 237: 352, 238: 353, 239: 354, 240: 355, 241: 357, 242: 362, 243: 363, 244: 364, 245: 365, 246: 366, 247: 367, 248: 368, 249: 370, 250: 373, 251: 375, 252: 376, 253: 378, 254: 379, 255: 380, 256: 381, 257: 382, 258: 383, 259: 384, 260: 385, 261: 387, 262: 390, 263: 391, 264: 393, 265: 394, 266: 395, 267: 396, 268: 398, 269: 399, 270: 403, 271: 404, 272: 408, 273: 409, 274: 410, 275: 411, 276: 412, 277: 413, 278: 415, 279: 417, 280: 421, 281: 422, 282: 423, 283: 424, 284: 426, 285: 427, 286: 428, 287: 429, 288: 430, 289: 431, 290: 436, 291: 437, 292: 438, 293: 439, 294: 440, 295: 441, 296: 442, 297: 443, 298: 444, 299: 445, 300: 446, 301: 450, 302: 451, 303: 454, 304: 455, 305: 456, 306: 463, 307: 464, 308: 465, 309: 466, 310: 467, 311: 468, 312: 469, 313: 470, 314: 471, 315: 472, 316: 473, 317: 474, 318: 479, 319: 482, 320: 483, 321: 484, 322: 485, 323: 486, 324: 487, 325: 488, 326: 489, 327: 490, 328: 491, 329: 493, 330: 494, 331: 495, 332: 496, 333: 500, 334: 503, 335: 504, 336: 507, 337: 508, 338: 511, 339: 512, 340: 515, 341: 516, 342: 520, 343: 521, 344: 525, 345: 526, 346: 527, 347: 528, 348: 529, 349: 530, 350: 531, 351: 532, 352: 533, 353: 534, 354: 535, 355: 536, 356: 537, 357: 538, 358: 539, 359: 540, 360: 541, 361: 542, 362: 543, 363: 548, 364: 549, 365: 551, 366: 552, 367: 553, 368: 555 } });
interface QuotaCacheSlot {
    at: number;
    data: QuotaResult | null;
}
interface ExchangeCache {
    at: number;
    usdCny: number;
}
export class DashboardRepository {
    private static readonly QUOTA_CACHE_TTL = 30.0;
    private static readonly EXCHANGE_TTL = 6 * 3600.0;
    private static readonly DEFAULT_USD_CNY = 7.2;
    private quotaCache: Map<number, QuotaCacheSlot> = new Map();
    private quotaRefreshing: Set<number> = new Set();
    private exchangeCache: ExchangeCache = { at: 0, usdCny: DashboardRepository.DEFAULT_USD_CNY };
    private usageDao: UsageDao = AppDb.usageDao();
    private syncDao: SyncDao = AppDb.syncDao();
    private _progress: SyncProgress = emptySyncProgress();
    get progress(): SyncProgress {
        bjccovmt7djxwp.instrumentFunction(0);
        bjccovmt7djxwp.instrumentRegion(0, 1);
        return this._progress;
    }
    private updateProgress(fn: (p: SyncProgress) => void): void {
        bjccovmt7djxwp.instrumentFunction(1);
        bjccovmt7djxwp.instrumentRegion(1, 1);
        const cur = this._progress;
        const next: SyncProgress = {
            running: cur.running,
            mode: cur.mode,
            page: cur.page,
            inserted: cur.inserted,
            phase: cur.phase,
            message: cur.message,
            account: cur.account,
        };
        fn(next);
        this._progress = next;
    }
    // ------------------------------------------------------------------
    // 活跃账号
    // ------------------------------------------------------------------
    async activeAccountId(): Promise<number> {
        bjccovmt7djxwp.instrumentFunction(3);
        bjccovmt7djxwp.instrumentRegion(3, 1);
        return this.syncDao.getActiveAccountId();
    }
    async accounts(): Promise<AccountInfo[]> {
        bjccovmt7djxwp.instrumentFunction(4);
        bjccovmt7djxwp.instrumentRegion(4, 1);
        return this.syncDao.listAccounts();
    }
    async countLoggedInAccounts(): Promise<number> {
        bjccovmt7djxwp.instrumentFunction(5);
        bjccovmt7djxwp.instrumentRegion(5, 1);
        return this.syncDao.countLoggedInAccounts();
    }
    async account(): Promise<AccountInfo | null> {
        bjccovmt7djxwp.instrumentFunction(6);
        bjccovmt7djxwp.instrumentRegion(6, 1);
        return this.syncDao.getAccount();
    }
    async switchAccount(accountId: number): Promise<boolean> {
        bjccovmt7djxwp.instrumentFunction(7);
        const ok = await this.syncDao.setActiveAccount(accountId);
        if (ok) {
            bjccovmt7djxwp.instrumentBranch(7, 0, true);
            bjccovmt7djxwp.instrumentRegion(7, 1);
            this._progress = emptySyncProgress();
        }
        else {
            bjccovmt7djxwp.instrumentBranch(7, 0, false);
        }
        bjccovmt7djxwp.instrumentRegion(7, 2);
        return ok;
    }
    async renameAccount(accountId: number, name: string): Promise<boolean> {
        bjccovmt7djxwp.instrumentFunction(8);
        bjccovmt7djxwp.instrumentRegion(8, 1);
        return this.syncDao.renameAccount(accountId, name);
    }
    /** 返回剩余账号数。 */
    async deleteAccount(accountId: number): Promise<number> {
        bjccovmt7djxwp.instrumentFunction(9);
        bjccovmt7djxwp.instrumentRegion(9, 1);
        const remaining = await this.syncDao.deleteAccount(accountId);
        this._progress = emptySyncProgress();
        return remaining;
    }
    /** 登录成功按模式落库: add=新建账号 (同 token 去重) 并切换; relogin=更新活跃账号凭证。 */
    async loginSuccess(token: string, workspaceHint: string, mode: string): Promise<void> {
        bjccovmt7djxwp.instrumentFunction(10);
        if (mode === 'add') {
            bjccovmt7djxwp.instrumentBranch(10, 0, true);
            bjccovmt7djxwp.instrumentRegion(10, 1);
            await this.syncDao.addAccount(token, workspaceHint, true);
        }
        else {
            bjccovmt7djxwp.instrumentBranch(10, 0, false);
            bjccovmt7djxwp.instrumentRegion(10, 2);
            await this.syncDao.saveToken(token, workspaceHint.trim().length > 0 ? (bjccovmt7djxwp.instrumentBranch(10, 1, true), workspaceHint.trim()) : (bjccovmt7djxwp.instrumentBranch(10, 1, false), 'Default'));
        }
        bjccovmt7djxwp.instrumentRegion(10, 3);
        this._progress = emptySyncProgress();
    }
    // ------------------------------------------------------------------
    // Quota 刷新 (按账号分槽缓存 + 防重入)
    // ------------------------------------------------------------------
    async ensureQuota(): Promise<void> {
        bjccovmt7djxwp.instrumentFunction(11);
        const accountId = await this.syncDao.getActiveAccountId();
        if (accountId === 0) {
            bjccovmt7djxwp.instrumentBranch(11, 0, true);
            bjccovmt7djxwp.instrumentRegion(11, 1);
            return;
        }
        else {
            bjccovmt7djxwp.instrumentBranch(11, 0, false);
        }
        const now = Date.now() / 1000;
        const slot = this.quotaCache.get(accountId);
        if (slot !== undefined && slot.data !== null && now - slot.at < DashboardRepository.QUOTA_CACHE_TTL) {
            bjccovmt7djxwp.instrumentBranch(11, 1, true);
            bjccovmt7djxwp.instrumentRegion(11, 2);
            return;
        }
        else {
            bjccovmt7djxwp.instrumentBranch(11, 1, false);
        }
        if (this.quotaRefreshing.has(accountId)) {
            bjccovmt7djxwp.instrumentBranch(11, 2, true);
            bjccovmt7djxwp.instrumentRegion(11, 3);
            return;
        }
        else {
            bjccovmt7djxwp.instrumentBranch(11, 2, false);
        }
        const token = await this.syncDao.getTokenFor(accountId);
        if (token.length === 0) {
            bjccovmt7djxwp.instrumentBranch(11, 3, true);
            bjccovmt7djxwp.instrumentRegion(11, 4);
            return;
        }
        else {
            bjccovmt7djxwp.instrumentBranch(11, 3, false);
        }
        this.quotaRefreshing.add(accountId);
        try {
            bjccovmt7djxwp.instrumentRegion(11, 5);
            const target: QuotaCacheSlot = this.quotaCache.get(accountId) ?? { at: 0, data: null };
            const hint = await this.syncDao.getWorkspaceHintFor(accountId);
            target.at = Date.now() / 1000;
            try {
                bjccovmt7djxwp.instrumentRegion(11, 7);
                target.data = await OpenCodeApi.fetchQuota(token, hint);
            }
            catch (e) {
                bjccovmt7djxwp.instrumentRegion(11, 8);
                target.data = null;
            }
            bjccovmt7djxwp.instrumentRegion(11, 9);
            this.quotaCache.set(accountId, target);
        }
        finally {
            bjccovmt7djxwp.instrumentRegion(11, 6);
            this.quotaRefreshing.delete(accountId);
        }
    }
    async currentQuota(): Promise<QuotaResult | null> {
        bjccovmt7djxwp.instrumentFunction(12);
        bjccovmt7djxwp.instrumentRegion(12, 1);
        const accountId = await this.syncDao.getActiveAccountId();
        const slot = this.quotaCache.get(accountId);
        return slot !== undefined ? (bjccovmt7djxwp.instrumentBranch(12, 0, true), slot.data) : (bjccovmt7djxwp.instrumentBranch(12, 0, false), null);
    }
    private async usdCny(): Promise<number> {
        bjccovmt7djxwp.instrumentFunction(13);
        const now = Date.now() / 1000;
        if (now - this.exchangeCache.at < DashboardRepository.EXCHANGE_TTL) {
            bjccovmt7djxwp.instrumentBranch(13, 0, true);
            bjccovmt7djxwp.instrumentRegion(13, 1);
            return this.exchangeCache.usdCny;
        }
        else {
            bjccovmt7djxwp.instrumentBranch(13, 0, false);
        }
        try {
            bjccovmt7djxwp.instrumentRegion(13, 2);
            const rate = await ExchangeApi.fetchUsdCny();
            if (rate > 0) {
                bjccovmt7djxwp.instrumentBranch(13, 1, true);
                bjccovmt7djxwp.instrumentRegion(13, 4);
                this.exchangeCache.usdCny = rate;
            }
            else {
                bjccovmt7djxwp.instrumentBranch(13, 1, false);
            }
        }
        catch (e) {
            bjccovmt7djxwp.instrumentRegion(13, 3);
        }
        bjccovmt7djxwp.instrumentRegion(13, 5);
        this.exchangeCache.at = Date.now() / 1000;
        return this.exchangeCache.usdCny;
    }
    // ------------------------------------------------------------------
    // Dashboard 数据包 (活跃账号视角)
    // ------------------------------------------------------------------
    static fmtServerTime(): string {
        bjccovmt7djxwp.instrumentFunction(14);
        bjccovmt7djxwp.instrumentRegion(14, 1);
        const d = new Date();
        const p = (n: number): string => { bjccovmt7djxwp.instrumentFunction(15); return String(n).padStart(2, '0'); };
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    }
    async loadDashboard(range: string): Promise<DashboardData> {
        bjccovmt7djxwp.instrumentFunction(16);
        bjccovmt7djxwp.instrumentRegion(16, 1);
        const aid = await this.syncDao.getActiveAccountId();
        const token = await this.syncDao.getTokenFor(aid);
        // 并发跑相互独立的 DB/汇率查询
        const parts = await Promise.all([
            this.usageDao.totals(range, aid),
            this.usageDao.totals('today', aid),
            this.usageDao.dailyStats(60, aid),
            this.usageDao.dailyStats(30, aid),
            this.usageDao.todayTrend(aid),
            this.usageDao.modelStats(range, aid),
            this.syncDao.getSyncStateFor(aid),
            this.usdCny(),
            this.currentQuota(),
        ]);
        return {
            loggedIn: token.length > 0,
            quota: token.length > 0 ? (bjccovmt7djxwp.instrumentBranch(16, 0, true), (parts[8] as QuotaResult | null)) : (bjccovmt7djxwp.instrumentBranch(16, 0, false), null),
            totals: parts[0] as Totals,
            today: parts[1] as Totals,
            daily: parts[2] as DailyStat[],
            trend: parts[3] as DailyStat[],
            todayTrend: parts[4] as HourStat[],
            models: parts[5] as ModelStat[],
            sync: parts[6] as SyncState,
            progress: this._progress,
            range: range,
            usdCny: parts[7] as number,
            serverTime: DashboardRepository.fmtServerTime(),
        };
    }
    // ------------------------------------------------------------------
    // 同步引擎 (多账号轮询)
    // ------------------------------------------------------------------
    async syncUsage(mode: string): Promise<SyncResult> {
        bjccovmt7djxwp.instrumentFunction(17);
        // incremental 轮询所有已登录账号; full 仅作用于活跃账号 (desktop parity)
        const targets: Array<[
            number,
            string
        ]> = [];
        let windowDays: number | null = null;
        if (mode === 'full') {
            bjccovmt7djxwp.instrumentBranch(17, 0, true);
            bjccovmt7djxwp.instrumentRegion(17, 1);
            const aid = await this.syncDao.getActiveAccountId();
            const acct = aid !== 0 ? (bjccovmt7djxwp.instrumentBranch(17, 1, true), await this.syncDao.getTokenFor(aid)) : (bjccovmt7djxwp.instrumentBranch(17, 1, false), '');
            if (aid !== 0 && acct.length > 0) {
                bjccovmt7djxwp.instrumentBranch(17, 2, true);
                bjccovmt7djxwp.instrumentRegion(17, 3);
                const info = await this.syncDao.getAccount();
                targets.push([aid, info !== null ? (bjccovmt7djxwp.instrumentBranch(17, 3, true), info.name) : (bjccovmt7djxwp.instrumentBranch(17, 3, false), `#${aid}`)]);
            }
            else {
                bjccovmt7djxwp.instrumentBranch(17, 2, false);
            }
        }
        else {
            bjccovmt7djxwp.instrumentBranch(17, 0, false);
            bjccovmt7djxwp.instrumentRegion(17, 2);
            const accounts = await this.syncDao.listAccounts();
            for (const a of accounts) {
                bjccovmt7djxwp.instrumentRegion(17, 4);
                if (a.hasToken) {
                    bjccovmt7djxwp.instrumentBranch(17, 4, true);
                    bjccovmt7djxwp.instrumentRegion(17, 5);
                    targets.push([a.id, a.name]);
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(17, 4, false);
                }
            }
        }
        if (targets.length === 0) {
            bjccovmt7djxwp.instrumentBranch(17, 5, true);
            bjccovmt7djxwp.instrumentRegion(17, 6);
            return { ok: false, error: '未登录', inserted: 0, pages: 0, partial: false, failedPages: 0 };
        }
        else {
            bjccovmt7djxwp.instrumentBranch(17, 5, false);
        }
        if (this._progress.running) {
            bjccovmt7djxwp.instrumentBranch(17, 6, true);
            bjccovmt7djxwp.instrumentRegion(17, 7);
            return { ok: false, error: '已有同步任务进行中', inserted: 0, pages: 0, partial: false, failedPages: 0 };
        }
        else {
            bjccovmt7djxwp.instrumentBranch(17, 6, false);
        }
        const settings = await AppDb.settingsDao().getSettings();
        windowDays = settings.windowDays;
        this._progress = { running: true, mode: mode, page: 0, inserted: 0, phase: 'usage', message: '', account: '' };
        try {
            bjccovmt7djxwp.instrumentRegion(17, 8);
            let totalInserted = 0;
            let pages = 0;
            let anyError = '';
            let partial = false;
            for (const target of targets) {
                bjccovmt7djxwp.instrumentRegion(17, 11);
                const aid = target[0];
                const name = target[1];
                this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(18); bjccovmt7djxwp.instrumentRegion(18, 1); p.account = name; });
                const result = await this.syncOneAccount(aid, name, mode, windowDays);
                totalInserted += result.inserted;
                pages += result.pages;
                if (!result.ok) {
                    bjccovmt7djxwp.instrumentBranch(17, 7, true);
                    bjccovmt7djxwp.instrumentRegion(17, 12);
                    anyError = result.error !== null ? (bjccovmt7djxwp.instrumentBranch(17, 8, true), result.error) : (bjccovmt7djxwp.instrumentBranch(17, 8, false), '同步失败');
                    if (mode === 'incremental') {
                        bjccovmt7djxwp.instrumentBranch(17, 9, true);
                        bjccovmt7djxwp.instrumentRegion(17, 13);
                        const msg = `[${name}] ${anyError}`;
                        this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(19); p.phase = 'error'; bjccovmt7djxwp.instrumentRegion(17, 17); p.message = msg; });
                        return { ok: false, error: anyError, inserted: totalInserted, pages: pages, partial: false, failedPages: 0 };
                    }
                    else {
                        bjccovmt7djxwp.instrumentBranch(17, 9, false);
                    }
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(17, 7, false);
                }
                if (result.partial) {
                    bjccovmt7djxwp.instrumentBranch(17, 10, true);
                    bjccovmt7djxwp.instrumentRegion(17, 14);
                    partial = true;
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(17, 10, false);
                }
            }
            if (partial || (mode !== 'incremental' && anyError.length > 0)) {
                bjccovmt7djxwp.instrumentBranch(17, 11, true);
                bjccovmt7djxwp.instrumentRegion(17, 15);
                const msg = anyError.length > 0 ? (bjccovmt7djxwp.instrumentBranch(17, 12, true), '部分账号同步异常') : (bjccovmt7djxwp.instrumentBranch(17, 12, false), '完成, 但部分页面拉取失败');
                this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(20); p.phase = 'done'; bjccovmt7djxwp.instrumentRegion(17, 18); p.message = msg; });
                return { ok: true, error: null, inserted: totalInserted, pages: pages, partial: true, failedPages: 0 };
            }
            else {
                bjccovmt7djxwp.instrumentBranch(17, 11, false);
            }
            bjccovmt7djxwp.instrumentRegion(17, 16);
            const msg = `同步完成, 新增 ${totalInserted} 条`;
            this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(21); p.phase = 'done'; bjccovmt7djxwp.instrumentRegion(17, 19); p.message = msg; });
            return { ok: true, error: null, inserted: totalInserted, pages: pages, partial: false, failedPages: 0 };
        }
        catch (e) {
            bjccovmt7djxwp.instrumentRegion(17, 9);
            const errMsg = (e as Error).message !== undefined ? (bjccovmt7djxwp.instrumentBranch(17, 13, true), (e as Error).message) : (bjccovmt7djxwp.instrumentBranch(17, 13, false), '同步失败');
            this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(22); p.phase = 'error'; bjccovmt7djxwp.instrumentRegion(17, 20); p.message = errMsg; });
            return { ok: false, error: errMsg, inserted: 0, pages: 0, partial: false, failedPages: 0 };
        }
        finally {
            bjccovmt7djxwp.instrumentRegion(17, 10);
            this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(23); p.running = false; bjccovmt7djxwp.instrumentRegion(17, 21); p.account = ''; });
        }
    }
    /** 同步单个账号的用量记录。 */
    private async syncOneAccount(accountId: number, name: string, mode: string, windowDays: number | null): Promise<SyncResult> {
        bjccovmt7djxwp.instrumentFunction(24);
        const token = await this.syncDao.getTokenFor(accountId);
        if (token.length === 0) {
            bjccovmt7djxwp.instrumentBranch(24, 0, true);
            bjccovmt7djxwp.instrumentRegion(24, 1);
            return { ok: false, error: '未登录', inserted: 0, pages: 0, partial: false, failedPages: 0 };
        }
        else {
            bjccovmt7djxwp.instrumentBranch(24, 0, false);
        }
        let workspaceId = await this.syncDao.getWorkspaceHintFor(accountId);
        try {
            bjccovmt7djxwp.instrumentRegion(24, 2);
            // 确保工作区 ID 已解析
            try {
                bjccovmt7djxwp.instrumentRegion(24, 4);
                const resolved = await OpenCodeApi.resolveWorkspaceId(workspaceId, token);
                if (!workspaceId.startsWith('wrk_')) {
                    bjccovmt7djxwp.instrumentBranch(24, 1, true);
                    bjccovmt7djxwp.instrumentRegion(24, 6);
                    workspaceId = resolved;
                    await this.syncDao.saveResolvedWorkspace(accountId, resolved, new Date().toISOString());
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(24, 1, false);
                }
            }
            catch (e) {
                bjccovmt7djxwp.instrumentRegion(24, 5);
                const msg = `工作区解析失败: ${(e as Error).message}`;
                await this.syncDao.updateSyncStateAndTotals(accountId, 'error', msg, 0);
                this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(25); p.phase = 'error'; bjccovmt7djxwp.instrumentRegion(24, 33); p.message = msg; });
                return { ok: false, error: (e as Error).message, inserted: 0, pages: 0, partial: false, failedPages: 0 };
            }
            let totalInserted = 0;
            const maxPages = mode === 'full' ? (bjccovmt7djxwp.instrumentBranch(24, 2, true), 2000) : (bjccovmt7djxwp.instrumentBranch(24, 2, false), 5);
            let page = 0;
            let emptyBatches = 0;
            let failedPages = 0;
            let windowBoundaryReached = false;
            while (page < maxPages) {
                bjccovmt7djxwp.instrumentRegion(24, 7);
                const batchEnd = Math.min(page + 5, maxPages);
                const batchPages: number[] = [];
                for (let p = page; p < batchEnd; p++) {
                    bjccovmt7djxwp.instrumentRegion(24, 8);
                    batchPages.push(p);
                }
                this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(26); bjccovmt7djxwp.instrumentRegion(26, 1); p.page = page; });
                const results = await this.fetchBatch(token, workspaceId, batchPages);
                let batchInserted = 0;
                let batchFullPages = 0;
                let batchFailed = 0;
                for (const p of batchPages) {
                    bjccovmt7djxwp.instrumentRegion(24, 9);
                    const result = results.get(p);
                    if (result === undefined || result === null) {
                        bjccovmt7djxwp.instrumentBranch(24, 3, true);
                        bjccovmt7djxwp.instrumentRegion(24, 10);
                        batchFailed++;
                        continue;
                    }
                    else {
                        bjccovmt7djxwp.instrumentBranch(24, 3, false);
                    }
                    if (result.length === 0) {
                        bjccovmt7djxwp.instrumentBranch(24, 4, true);
                        bjccovmt7djxwp.instrumentRegion(24, 11);
                        continue; // 空页: 数据结束
                    }
                    else {
                        bjccovmt7djxwp.instrumentBranch(24, 4, false);
                    }
                    if (mode === 'full' && windowDays !== null) {
                        bjccovmt7djxwp.instrumentBranch(24, 5, true);
                        bjccovmt7djxwp.instrumentRegion(24, 12);
                        let earliest = '';
                        for (const r of result) {
                            bjccovmt7djxwp.instrumentRegion(24, 13);
                            if (earliest.length === 0 || r.createdAt < earliest) {
                                bjccovmt7djxwp.instrumentBranch(24, 6, true);
                                bjccovmt7djxwp.instrumentRegion(24, 14);
                                earliest = r.createdAt;
                            }
                            else {
                                bjccovmt7djxwp.instrumentBranch(24, 6, false);
                            }
                        }
                        if (earliest.length > 0) {
                            bjccovmt7djxwp.instrumentBranch(24, 7, true);
                            bjccovmt7djxwp.instrumentRegion(24, 15);
                            try {
                                bjccovmt7djxwp.instrumentRegion(24, 16);
                                const et = Date.parse(earliest);
                                const boundary = Date.now() - windowDays * 24 * 3600 * 1000;
                                if (!Number.isNaN(et) && et < boundary) {
                                    bjccovmt7djxwp.instrumentBranch(24, 8, true);
                                    bjccovmt7djxwp.instrumentRegion(24, 18);
                                    windowBoundaryReached = true;
                                }
                                else {
                                    bjccovmt7djxwp.instrumentBranch(24, 8, false);
                                }
                            }
                            catch (e) {
                                bjccovmt7djxwp.instrumentRegion(24, 17);
                            }
                        }
                        else {
                            bjccovmt7djxwp.instrumentBranch(24, 7, false);
                        }
                    }
                    else {
                        bjccovmt7djxwp.instrumentBranch(24, 5, false);
                    }
                    const syncedAt = new Date().toISOString();
                    const entities: UsageRecordEntity[] = result.map((r) => { bjccovmt7djxwp.instrumentFunction(27); return toEntity(r, syncedAt, accountId); });
                    const inserted = await this.usageDao.insertUsageRecords(entities, accountId);
                    totalInserted += inserted;
                    batchInserted += inserted;
                    if (result.length >= 50) {
                        bjccovmt7djxwp.instrumentBranch(24, 9, true);
                        bjccovmt7djxwp.instrumentRegion(24, 19);
                        batchFullPages++;
                    }
                    else {
                        bjccovmt7djxwp.instrumentBranch(24, 9, false);
                    }
                    bjccovmt7djxwp.instrumentRegion(24, 34);
                    this.updateProgress((p) => { bjccovmt7djxwp.instrumentFunction(28); bjccovmt7djxwp.instrumentRegion(28, 1); p.inserted = totalInserted; });
                }
                page += 5;
                if (windowBoundaryReached) {
                    bjccovmt7djxwp.instrumentBranch(24, 10, true);
                    bjccovmt7djxwp.instrumentRegion(24, 20);
                    break;
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(24, 10, false);
                }
                if (batchFailed > 0) {
                    bjccovmt7djxwp.instrumentBranch(24, 11, true);
                    bjccovmt7djxwp.instrumentRegion(24, 21);
                    failedPages += batchFailed;
                    if (mode === 'incremental') {
                        bjccovmt7djxwp.instrumentBranch(24, 12, true);
                        bjccovmt7djxwp.instrumentRegion(24, 22);
                        const msg = '网络请求失败 (IncompleteRead/超时)';
                        await this.syncDao.updateSyncStateAndTotals(accountId, 'error', `[${name}] 第 ${page - 4} 页拉取失败: ${msg}`, totalInserted);
                        this.updateProgress((p) => {
                            bjccovmt7djxwp.instrumentFunction(29);
                            p.phase = 'error';
                            bjccovmt7djxwp.instrumentRegion(24, 35);
                            p.message = `[${name}] 第 ${page - 4} 页拉取失败: ${msg}`;
                        });
                        return { ok: false, error: msg, inserted: totalInserted, pages: page, partial: false, failedPages: batchFailed };
                    }
                    else {
                        bjccovmt7djxwp.instrumentBranch(24, 12, false);
                    }
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(24, 11, false);
                }
                if (batchFullPages === 0) {
                    bjccovmt7djxwp.instrumentBranch(24, 13, true);
                    bjccovmt7djxwp.instrumentRegion(24, 23);
                    break; // 本批没有满页 -> 到底
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(24, 13, false);
                }
                if (mode === 'incremental' && batchInserted === 0) {
                    bjccovmt7djxwp.instrumentBranch(24, 14, true);
                    bjccovmt7djxwp.instrumentRegion(24, 24);
                    emptyBatches++;
                    if (emptyBatches >= 2) {
                        bjccovmt7djxwp.instrumentBranch(24, 15, true);
                        bjccovmt7djxwp.instrumentRegion(24, 26);
                        break;
                    }
                    else {
                        bjccovmt7djxwp.instrumentBranch(24, 15, false);
                    }
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(24, 14, false);
                    bjccovmt7djxwp.instrumentRegion(24, 25);
                    emptyBatches = 0;
                }
            }
            if (windowDays !== null) {
                bjccovmt7djxwp.instrumentBranch(24, 16, true);
                bjccovmt7djxwp.instrumentRegion(24, 27);
                await this.usageDao.pruneOldRecords(`-${windowDays} days`, accountId);
            }
            // 刷新该账号的 key 显示名称缓存 (失败不影响已有缓存)
            else {
                bjccovmt7djxwp.instrumentBranch(24, 16, false);
            }
            // 刷新该账号的 key 显示名称缓存 (失败不影响已有缓存)
            try {
                bjccovmt7djxwp.instrumentRegion(24, 28);
                const names = await OpenCodeApi.fetchKeyNames(token, workspaceId);
                if (names.size > 0) {
                    bjccovmt7djxwp.instrumentBranch(24, 17, true);
                    bjccovmt7djxwp.instrumentRegion(24, 30);
                    const merged: Map<string, string> = await AppDb.settingsDao().getKeyNames();
                    names.forEach((v, k) => {
                        bjccovmt7djxwp.instrumentFunction(30);
                        bjccovmt7djxwp.instrumentRegion(30, 1);
                        merged.set(k, v);
                    });
                    await AppDb.settingsDao().saveKeyNames(merged);
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(24, 17, false);
                }
            }
            catch (e) {
                bjccovmt7djxwp.instrumentRegion(24, 29);
            }
            if (failedPages > 0) {
                bjccovmt7djxwp.instrumentBranch(24, 18, true);
                bjccovmt7djxwp.instrumentRegion(24, 31);
                const msg = `完成, 但 ${failedPages} 页拉取失败 (数据不完整, 可再次全量同步补全)`;
                await this.syncDao.updateSyncStateAndTotals(accountId, 'partial', msg, totalInserted);
                return { ok: true, error: null, inserted: totalInserted, pages: page, partial: true, failedPages: failedPages };
            }
            else {
                bjccovmt7djxwp.instrumentBranch(24, 18, false);
            }
            bjccovmt7djxwp.instrumentRegion(24, 32);
            await this.syncDao.updateSyncStateAndTotals(accountId, 'ok', null, totalInserted);
            return { ok: true, error: null, inserted: totalInserted, pages: page, partial: false, failedPages: 0 };
        }
        catch (e) {
            bjccovmt7djxwp.instrumentRegion(24, 3);
            const errMsg = (e as Error).message !== undefined ? (bjccovmt7djxwp.instrumentBranch(24, 19, true), (e as Error).message) : (bjccovmt7djxwp.instrumentBranch(24, 19, false), '同步失败');
            await this.syncDao.updateSyncStateAndTotals(accountId, 'error', errMsg, 0);
            return { ok: false, error: errMsg, inserted: 0, pages: 0, partial: false, failedPages: 0 };
        }
    }
    /** 并发抓取最多 5 页; undefined = 失败页。 */
    private async fetchBatch(token: string, workspaceId: string, pages: number[]): Promise<Map<number, UsageRecord[] | null>> {
        bjccovmt7djxwp.instrumentFunction(31);
        const out: Map<number, UsageRecord[] | null> = new Map();
        const tasks: Array<Promise<void>> = [];
        for (const p of pages) {
            bjccovmt7djxwp.instrumentRegion(31, 1);
            tasks.push((async () => {
                bjccovmt7djxwp.instrumentFunction(32);
                try {
                    bjccovmt7djxwp.instrumentRegion(32, 1);
                    out.set(p, await OpenCodeApi.fetchUsagePage(token, workspaceId, p));
                }
                catch (e) {
                    bjccovmt7djxwp.instrumentRegion(32, 2);
                    out.set(p, null);
                }
            })());
        }
        bjccovmt7djxwp.instrumentRegion(31, 2);
        await Promise.all(tasks);
        return out;
    }
    async syncAll(mode: string): Promise<void> {
        bjccovmt7djxwp.instrumentFunction(33);
        bjccovmt7djxwp.instrumentRegion(33, 1);
        await this.ensureQuota();
        await this.syncUsage(mode);
    }
    // ------------------------------------------------------------------
    // 页面 / 设置 / 账号 (server.py API parity — 活跃账号)
    // ------------------------------------------------------------------
    async recordsPage(page: number, pageSize: number, model: string | null, days: number | null): Promise<PageResult<UsageRecordRow>> {
        bjccovmt7djxwp.instrumentFunction(34);
        const aid = await this.syncDao.getActiveAccountId();
        const paged = await this.usageDao.usageRecordsPage(page, pageSize, model, days, aid);
        const records = paged[0];
        const total = paged[1];
        const names = await AppDb.settingsDao().getKeyNames();
        if (names.size > 0) {
            bjccovmt7djxwp.instrumentBranch(34, 0, true);
            bjccovmt7djxwp.instrumentRegion(34, 1);
            for (const r of records) {
                bjccovmt7djxwp.instrumentRegion(34, 2);
                if (r.keyId !== null) {
                    bjccovmt7djxwp.instrumentBranch(34, 1, true);
                    bjccovmt7djxwp.instrumentRegion(34, 3);
                    const n = names.get(r.keyId);
                    if (n !== undefined) {
                        bjccovmt7djxwp.instrumentBranch(34, 2, true);
                        bjccovmt7djxwp.instrumentRegion(34, 4);
                        r.keyName = n;
                    }
                    else {
                        bjccovmt7djxwp.instrumentBranch(34, 2, false);
                    }
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(34, 1, false);
                }
            }
        }
        else {
            bjccovmt7djxwp.instrumentBranch(34, 0, false);
        }
        bjccovmt7djxwp.instrumentRegion(34, 5);
        return { records: records, total: total };
    }
    async sessionsPage(page: number, pageSize: number, days: number | null): Promise<PageResult<SessionStat>> {
        bjccovmt7djxwp.instrumentFunction(35);
        const aid = await this.syncDao.getActiveAccountId();
        const paged = await this.usageDao.sessionStatsPage(page, pageSize, days, aid);
        const records = paged[0];
        const total = paged[1];
        const names = await AppDb.settingsDao().getKeyNames();
        for (const st of records) {
            bjccovmt7djxwp.instrumentRegion(35, 1);
            const keyGroup = st.keyId !== null && st.keyId.length > 0 && st.sessionId.startsWith('key_');
            if (keyGroup) {
                bjccovmt7djxwp.instrumentBranch(35, 0, true);
                bjccovmt7djxwp.instrumentRegion(35, 2);
                st.sessionId = '';
            }
            else {
                bjccovmt7djxwp.instrumentBranch(35, 0, false);
            }
            if (st.keyId !== null) {
                bjccovmt7djxwp.instrumentBranch(35, 1, true);
                bjccovmt7djxwp.instrumentRegion(35, 3);
                const n = names.get(st.keyId);
                if (n !== undefined && n.length > 0) {
                    bjccovmt7djxwp.instrumentBranch(35, 2, true);
                    bjccovmt7djxwp.instrumentRegion(35, 4);
                    st.keyName = n;
                }
                else {
                    bjccovmt7djxwp.instrumentBranch(35, 2, false);
                }
            }
            else {
                bjccovmt7djxwp.instrumentBranch(35, 1, false);
            }
        }
        bjccovmt7djxwp.instrumentRegion(35, 5);
        return { records: records, total: total };
    }
    async listModels(): Promise<string[]> {
        bjccovmt7djxwp.instrumentFunction(36);
        bjccovmt7djxwp.instrumentRegion(36, 1);
        return this.usageDao.listModels(await this.syncDao.getActiveAccountId());
    }
    async syncState(): Promise<SyncState> {
        bjccovmt7djxwp.instrumentFunction(37);
        bjccovmt7djxwp.instrumentRegion(37, 1);
        return this.syncDao.getSyncState();
    }
    async settings(): Promise<AppSettings> {
        bjccovmt7djxwp.instrumentFunction(38);
        bjccovmt7djxwp.instrumentRegion(38, 1);
        return AppDb.settingsDao().getSettings();
    }
    async saveSettings(patch: AppSettings): Promise<AppSettings> {
        bjccovmt7djxwp.instrumentFunction(39);
        bjccovmt7djxwp.instrumentRegion(39, 1);
        return AppDb.settingsDao().saveSettings(patch);
    }
    /** 退出登录当前活跃账号 (清其数据, 保留账号行)。 */
    async logout(): Promise<void> {
        bjccovmt7djxwp.instrumentFunction(40);
        bjccovmt7djxwp.instrumentRegion(40, 1);
        return this.syncDao.clearAccount();
    }
}
export function toEntity(r: UsageRecord, syncedAt: string, accountId: number): UsageRecordEntity {
    bjccovmt7djxwp.instrumentFunction(41);
    bjccovmt7djxwp.instrumentRegion(41, 1);
    return {
        usgId: r.usgId,
        createdAt: r.createdAt,
        model: r.model,
        provider: r.provider,
        inputTokens: r.inputTokens,
        outputTokens: r.outputTokens,
        reasoningTokens: r.reasoningTokens,
        cacheReadTokens: r.cacheReadTokens,
        cacheWrite5mTokens: r.cacheWrite5mTokens,
        cacheWrite1hTokens: r.cacheWrite1hTokens,
        costRaw: r.costRaw,
        costUsd: r.costRaw / 100000000,
        keyId: r.keyId,
        sessionId: r.sessionId,
        plan: r.plan,
        syncedAt: syncedAt,
        accountId: accountId,
    };
}
/** 仓库单例 —— UI/入口层统一入口。 */
export class Repo {
    private static instance: DashboardRepository | null = null;
    static get(): DashboardRepository {
        bjccovmt7djxwp.instrumentFunction(42);
        if (Repo.instance === null) {
            bjccovmt7djxwp.instrumentBranch(42, 0, true);
            bjccovmt7djxwp.instrumentRegion(42, 1);
            Repo.instance = new DashboardRepository();
        }
        else {
            bjccovmt7djxwp.instrumentBranch(42, 0, false);
        }
        bjccovmt7djxwp.instrumentRegion(42, 2);
        return Repo.instance;
    }
}
