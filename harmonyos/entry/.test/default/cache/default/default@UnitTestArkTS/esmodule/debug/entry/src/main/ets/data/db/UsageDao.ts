import type relationalStore from "@ohos:data.relationalStore";
import { AppDb } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/AppDb";
import { RowReader } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/RowReader";
import type { DailyStat, HourStat, ModelStat, SessionStat, Totals, UsageRecordRow } from '../../common/model/Models';
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
let bjccovmt7djy10 = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/db/UsageDao.ets", hash: "90c320642cef85251c530c8f72f24e9e6b315b5e40124cb50b3bec5574fb7fb1", lineCnt: 488, count: 0, projectPath: "", functions: { 0: { name: "UsageDao.store", count: 0, regions: { 0: { startLoc: { line: 37, col: 3 }, endLoc: { line: 39, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 38, col: 5 }, endLoc: { line: 39, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "UsageDao.placeholders", count: 0, regions: { 0: { startLoc: { line: 45, col: 3 }, endLoc: { line: 51, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 47, col: 5 }, endLoc: { line: 49, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 50, col: 5 }, endLoc: { line: 51, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "UsageDao.insertUsageRecords", count: 0, regions: { 0: { startLoc: { line: 54, col: 3 }, endLoc: { line: 105, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 55, col: 31 }, endLoc: { line: 57, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 66, col: 5 }, endLoc: { line: 68, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 73, col: 9 }, endLoc: { line: 100, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 100, col: 7 }, endLoc: { line: 103, col: 6 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 74, col: 7 }, endLoc: { line: 98, col: 8 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 75, col: 43 }, endLoc: { line: 85, col: 10 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 85, col: 16 }, endLoc: { line: 97, col: 10 }, count: 0, ignored: 0 }, 8: { startLoc: { line: 104, col: 5 }, endLoc: { line: 105, col: 4 }, count: 0, ignored: 0 }, 9: { startLoc: { line: 99, col: 7 }, endLoc: { line: 100, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 55, col: 9 }, endLoc: { line: 55, col: 29 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 75, col: 13 }, endLoc: { line: 75, col: 41 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 93, col: 57 }, endLoc: { line: 94, col: 59 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 102, col: 14 }, endLoc: { line: 102, col: 58 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 }, 3: { name: "anonymous_0", count: 0, regions: { 0: { startLoc: { line: 59, col: 39 }, endLoc: { line: 59, col: 53 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 3 }, 4: { name: "UsageDao.pruneOldRecords", count: 0, regions: { 0: { startLoc: { line: 107, col: 3 }, endLoc: { line: 112, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 108, col: 5 }, endLoc: { line: 112, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 4 }, 5: { name: "UsageDao.deleteAll", count: 0, regions: { 0: { startLoc: { line: 114, col: 3 }, endLoc: { line: 116, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 115, col: 5 }, endLoc: { line: 116, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 5 }, 6: { name: "UsageDao.periodClause", count: 0, regions: { 0: { startLoc: { line: 122, col: 3 }, endLoc: { line: 142, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 124, col: 7 }, endLoc: { line: 125, col: 75 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 126, col: 7 }, endLoc: { line: 127, col: 99 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 128, col: 7 }, endLoc: { line: 129, col: 26 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 130, col: 7 }, endLoc: { line: 140, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 133, col: 25 }, endLoc: { line: 138, col: 10 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 135, col: 33 }, endLoc: { line: 137, col: 12 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 139, col: 9 }, endLoc: { line: 140, col: 8 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 124, col: 12 }, endLoc: { line: 124, col: 16 }, trueCount: 0, falseCount: 0, group: { 0: 0, 1: 1, 2: 2, 3: 3 }, ignored: 0 }, 1: { startLoc: { line: 126, col: 12 }, endLoc: { line: 126, col: 19 }, trueCount: 0, falseCount: 0, group: { 0: 0, 1: 1, 2: 2, 3: 3 }, ignored: 0 }, 2: { startLoc: { line: 128, col: 12 }, endLoc: { line: 128, col: 17 }, trueCount: 0, falseCount: 0, group: { 0: 0, 1: 1, 2: 2, 3: 3 }, ignored: 0 }, 3: { startLoc: { line: 130, col: 7 }, endLoc: { line: 130, col: 7 }, trueCount: 0, falseCount: 0, group: { 0: 0, 1: 1, 2: 2, 3: 3 }, ignored: 0 }, 4: { startLoc: { line: 133, col: 13 }, endLoc: { line: 133, col: 23 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 135, col: 15 }, endLoc: { line: 135, col: 31 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 6 }, 7: { name: "UsageDao.buildWhere", count: 0, regions: { 0: { startLoc: { line: 144, col: 3 }, endLoc: { line: 156, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 149, col: 5 }, endLoc: { line: 151, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 152, col: 26 }, endLoc: { line: 154, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 155, col: 5 }, endLoc: { line: 156, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 152, col: 9 }, endLoc: { line: 152, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 7 }, 8: { name: "UsageDao.totalsSql", count: 0, regions: { 0: { startLoc: { line: 158, col: 3 }, endLoc: { line: 170, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 159, col: 5 }, endLoc: { line: 170, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 8 }, 9: { name: "UsageDao.totals", count: 0, regions: { 0: { startLoc: { line: 172, col: 3 }, endLoc: { line: 206, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 183, col: 24 }, endLoc: { line: 203, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 204, col: 5 }, endLoc: { line: 206, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 183, col: 9 }, endLoc: { line: 183, col: 22 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 186, col: 23 }, endLoc: { line: 186, col: 68 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 9 }, 10: { name: "UsageDao.dailyStats", count: 0, regions: { 0: { startLoc: { line: 209, col: 3 }, endLoc: { line: 248, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 229, col: 5 }, endLoc: { line: 245, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 246, col: 5 }, endLoc: { line: 248, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 232, col: 23 }, endLoc: { line: 232, col: 68 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 10 }, 11: { name: "UsageDao.todayTrend", count: 0, regions: { 0: { startLoc: { line: 251, col: 3 }, endLoc: { line: 285, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 264, col: 5 }, endLoc: { line: 272, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 275, col: 5 }, endLoc: { line: 283, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 284, col: 5 }, endLoc: { line: 285, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 279, col: 16 }, endLoc: { line: 279, col: 45 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 280, col: 17 }, endLoc: { line: 280, col: 47 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 281, col: 20 }, endLoc: { line: 281, col: 53 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 11 }, 12: { name: "UsageDao.modelStats", count: 0, regions: { 0: { startLoc: { line: 288, col: 3 }, endLoc: { line: 331, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 311, col: 5 }, endLoc: { line: 328, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 329, col: 5 }, endLoc: { line: 331, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 314, col: 23 }, endLoc: { line: 314, col: 68 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 12 }, 13: { name: "UsageDao.sessionStatsPage", count: 0, regions: { 0: { startLoc: { line: 338, col: 3 }, endLoc: { line: 399, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 343, col: 24 }, endLoc: { line: 346, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 355, col: 29 }, endLoc: { line: 357, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 361, col: 5 }, endLoc: { line: 363, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 383, col: 5 }, endLoc: { line: 396, col: 6 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 397, col: 5 }, endLoc: { line: 399, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 343, col: 9 }, endLoc: { line: 343, col: 22 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 355, col: 9 }, endLoc: { line: 355, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 393, col: 16 }, endLoc: { line: 393, col: 72 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 13 }, 14: { name: "UsageDao.usageRecordsPage", count: 0, regions: { 0: { startLoc: { line: 402, col: 3 }, endLoc: { line: 456, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 407, col: 45 }, endLoc: { line: 410, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 411, col: 24 }, endLoc: { line: 414, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 421, col: 29 }, endLoc: { line: 423, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 427, col: 5 }, endLoc: { line: 429, col: 6 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 436, col: 5 }, endLoc: { line: 453, col: 6 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 454, col: 5 }, endLoc: { line: 456, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 407, col: 9 }, endLoc: { line: 407, col: 43 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 411, col: 9 }, endLoc: { line: 411, col: 22 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 421, col: 9 }, endLoc: { line: 421, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 441, col: 19 }, endLoc: { line: 441, col: 79 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 448, col: 20 }, endLoc: { line: 448, col: 84 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 449, col: 15 }, endLoc: { line: 449, col: 67 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 6: { startLoc: { line: 450, col: 16 }, endLoc: { line: 450, col: 72 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 14 }, 15: { name: "UsageDao.listModels", count: 0, regions: { 0: { startLoc: { line: 458, col: 3 }, endLoc: { line: 469, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 464, col: 5 }, endLoc: { line: 466, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 467, col: 5 }, endLoc: { line: 469, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 15 }, 16: { name: "UsageDao.recordBounds", count: 0, regions: { 0: { startLoc: { line: 471, col: 3 }, endLoc: { line: 487, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 478, col: 24 }, endLoc: { line: 484, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 485, col: 5 }, endLoc: { line: 487, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 478, col: 9 }, endLoc: { line: 478, col: 22 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 481, col: 17 }, endLoc: { line: 481, col: 73 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 482, col: 17 }, endLoc: { line: 482, col: 73 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 16 } }, exeLine: { 0: 5, 1: 6, 2: 7, 3: 8, 4: 10, 5: 11, 6: 12, 7: 13, 8: 14, 9: 15, 10: 16, 11: 17, 12: 18, 13: 19, 14: 20, 15: 21, 16: 22, 17: 23, 18: 24, 19: 25, 20: 26, 21: 27, 22: 30, 23: 31, 24: 32, 25: 33, 26: 36, 27: 37, 28: 38, 29: 45, 30: 46, 31: 47, 32: 48, 33: 50, 34: 54, 35: 55, 36: 56, 37: 58, 38: 59, 39: 60, 40: 61, 41: 62, 42: 63, 43: 65, 44: 66, 45: 67, 46: 69, 47: 71, 48: 72, 49: 73, 50: 74, 51: 75, 52: 76, 53: 77, 54: 81, 55: 82, 56: 83, 57: 85, 58: 86, 59: 87, 60: 91, 61: 92, 62: 93, 63: 94, 64: 96, 65: 99, 66: 100, 67: 101, 68: 102, 69: 104, 70: 107, 71: 108, 72: 109, 73: 110, 74: 114, 75: 115, 76: 122, 77: 123, 78: 124, 79: 125, 80: 126, 81: 127, 82: 128, 83: 129, 84: 130, 85: 131, 86: 132, 87: 133, 88: 134, 89: 135, 90: 136, 91: 139, 92: 144, 93: 145, 94: 146, 95: 147, 96: 148, 97: 149, 98: 150, 99: 152, 100: 153, 101: 155, 102: 158, 103: 159, 104: 169, 105: 172, 106: 173, 107: 174, 108: 175, 109: 176, 110: 177, 111: 178, 112: 179, 113: 180, 114: 181, 115: 183, 116: 184, 117: 185, 118: 186, 119: 187, 120: 188, 121: 189, 122: 190, 123: 191, 124: 192, 125: 193, 126: 194, 127: 195, 128: 196, 129: 197, 130: 198, 131: 199, 132: 200, 133: 201, 134: 204, 135: 205, 136: 209, 137: 210, 138: 211, 139: 212, 140: 225, 141: 227, 142: 228, 143: 229, 144: 230, 145: 231, 146: 232, 147: 233, 148: 234, 149: 235, 150: 236, 151: 237, 152: 238, 153: 239, 154: 240, 155: 241, 156: 242, 157: 243, 158: 246, 159: 247, 160: 251, 161: 252, 162: 253, 163: 260, 164: 262, 165: 263, 166: 264, 167: 265, 168: 266, 169: 267, 170: 268, 171: 269, 172: 270, 173: 273, 174: 274, 175: 275, 176: 276, 177: 277, 178: 278, 179: 279, 180: 280, 181: 281, 182: 284, 183: 288, 184: 289, 185: 290, 186: 291, 187: 292, 188: 293, 189: 304, 190: 307, 191: 309, 192: 310, 193: 311, 194: 312, 195: 313, 196: 314, 197: 315, 198: 316, 199: 317, 200: 318, 201: 319, 202: 320, 203: 321, 204: 322, 205: 323, 206: 324, 207: 325, 208: 326, 209: 329, 210: 330, 211: 333, 212: 334, 213: 338, 214: 339, 215: 340, 216: 341, 217: 342, 218: 343, 219: 344, 220: 345, 221: 347, 222: 348, 223: 350, 224: 351, 225: 353, 226: 354, 227: 355, 228: 356, 229: 358, 230: 360, 231: 361, 232: 362, 233: 364, 234: 365, 235: 366, 236: 375, 237: 376, 238: 379, 239: 381, 240: 382, 241: 383, 242: 384, 243: 385, 244: 386, 245: 387, 246: 388, 247: 389, 248: 390, 249: 391, 250: 392, 251: 393, 252: 394, 253: 397, 254: 398, 255: 402, 256: 403, 257: 404, 258: 405, 259: 406, 260: 407, 261: 408, 262: 409, 263: 411, 264: 412, 265: 413, 266: 415, 267: 416, 268: 418, 269: 419, 270: 420, 271: 421, 272: 422, 273: 424, 274: 426, 275: 427, 276: 428, 277: 430, 278: 431, 279: 432, 280: 434, 281: 435, 282: 436, 283: 437, 284: 438, 285: 439, 286: 440, 287: 441, 288: 442, 289: 443, 290: 444, 291: 445, 292: 446, 293: 447, 294: 448, 295: 449, 296: 450, 297: 451, 298: 454, 299: 455, 300: 458, 301: 459, 302: 460, 303: 462, 304: 463, 305: 464, 306: 465, 307: 467, 308: 468, 309: 471, 310: 472, 311: 473, 312: 474, 313: 476, 314: 477, 315: 478, 316: 479, 317: 480, 318: 481, 319: 482, 320: 485, 321: 486 } });
export interface UsageRecordEntity {
    usgId: string;
    createdAt: string;
    model: string;
    provider: string;
    inputTokens: number;
    outputTokens: number;
    reasoningTokens: number;
    cacheReadTokens: number;
    cacheWrite5mTokens: number;
    cacheWrite1hTokens: number;
    costRaw: number;
    costUsd: number;
    keyId: string;
    sessionId: string;
    plan: string | null;
    syncedAt: string;
    accountId: number;
}
interface BoundsRow {
    count: number;
    oldest: string | null;
    newest: string | null;
}
export class UsageDao {
    private store(): relationalStore.RdbStore {
        bjccovmt7djy10.instrumentFunction(0);
        bjccovmt7djy10.instrumentRegion(0, 1);
        return AppDb.store();
    }
    // ------------------------------------------------------------------
    // Write
    // ------------------------------------------------------------------
    private static placeholders(n: number): string {
        bjccovmt7djy10.instrumentFunction(1);
        const parts: string[] = [];
        for (let i = 0; i < n; i++) {
            bjccovmt7djy10.instrumentRegion(1, 1);
            parts.push('?');
        }
        bjccovmt7djy10.instrumentRegion(1, 2);
        return parts.join(',');
    }
    /** 批量插入去重; 返回新增行数。已存在的记录保留原归属账号 (desktop ON CONFLICT 语义)。 */
    async insertUsageRecords(records: UsageRecordEntity[], accountId: number): Promise<number> {
        bjccovmt7djy10.instrumentFunction(2);
        if (records.length === 0) {
            bjccovmt7djy10.instrumentBranch(2, 0, true);
            bjccovmt7djy10.instrumentRegion(2, 1);
            return 0;
        }
        else {
            bjccovmt7djy10.instrumentBranch(2, 0, false);
        }
        const store = this.store();
        const ids: string[] = records.map((r) => { bjccovmt7djy10.instrumentFunction(3); return r.usgId; });
        const existingAccount: Map<string, number> = new Map();
        const rs = await store.querySql(`SELECT usg_id, account_id FROM usage_records WHERE usg_id IN (${UsageDao.placeholders(ids.length)})`, ids);
        const reader = new RowReader(rs);
        while (reader.next()) {
            bjccovmt7djy10.instrumentRegion(2, 2);
            existingAccount.set(reader.getStr('usg_id'), reader.getLong('account_id'));
        }
        reader.close();
        let inserted = 0;
        store.beginTransaction();
        try {
            bjccovmt7djy10.instrumentRegion(2, 3);
            for (const r of records) {
                bjccovmt7djy10.instrumentRegion(2, 5);
                if (existingAccount.has(r.usgId)) {
                    bjccovmt7djy10.instrumentBranch(2, 1, true);
                    bjccovmt7djy10.instrumentRegion(2, 6);
                    await store.executeSql(`UPDATE usage_records SET created_at=?, model=?, provider=?, input_tokens=?, output_tokens=?,
               reasoning_tokens=?, cache_read_tokens=?, cache_write_5m_tokens=?, cache_write_1h_tokens=?,
               cost_raw=?, cost_usd=?, key_id=?, session_id=?, plan=?, synced_at=?
             WHERE usg_id=?`, [r.createdAt, r.model, r.provider, r.inputTokens, r.outputTokens, r.reasoningTokens,
                        r.cacheReadTokens, r.cacheWrite5mTokens, r.cacheWrite1hTokens, r.costRaw, r.costUsd,
                        r.keyId, r.sessionId, r.plan, r.syncedAt, r.usgId]);
                }
                else {
                    bjccovmt7djy10.instrumentBranch(2, 1, false);
                    bjccovmt7djy10.instrumentRegion(2, 7);
                    await store.executeSql(`INSERT INTO usage_records (usg_id, created_at, model, provider, input_tokens, output_tokens,
               reasoning_tokens, cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens,
               cost_raw, cost_usd, key_id, session_id, plan, synced_at, account_id)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`, [r.usgId, r.createdAt, r.model, r.provider, r.inputTokens, r.outputTokens, r.reasoningTokens,
                        r.cacheReadTokens, r.cacheWrite5mTokens, r.cacheWrite1hTokens, r.costRaw, r.costUsd,
                        r.keyId, r.sessionId, r.plan, r.syncedAt, existingAccount.get(r.usgId) !== undefined
                            ? (bjccovmt7djy10.instrumentBranch(2, 2, true), existingAccount.get(r.usgId)) : (bjccovmt7djy10.instrumentBranch(2, 2, false), accountId)]);
                    inserted++;
                }
            }
            bjccovmt7djy10.instrumentRegion(2, 9);
            store.commit();
        }
        catch (e) {
            bjccovmt7djy10.instrumentRegion(2, 4);
            store.rollBack();
            throw (e instanceof Error ? (bjccovmt7djy10.instrumentBranch(2, 3, true), e) : (bjccovmt7djy10.instrumentBranch(2, 3, false), new Error('批量插入失败')));
        }
        bjccovmt7djy10.instrumentRegion(2, 8);
        return inserted;
    }
    async pruneOldRecords(intervalArg: string, accountId: number): Promise<void> {
        bjccovmt7djy10.instrumentFunction(4);
        bjccovmt7djy10.instrumentRegion(4, 1);
        await this.store().executeSql(`DELETE FROM usage_records WHERE account_id = ? AND datetime(created_at) < datetime('now', ?)`, [accountId, intervalArg]);
    }
    async deleteAll(): Promise<void> {
        bjccovmt7djy10.instrumentFunction(5);
        bjccovmt7djy10.instrumentRegion(5, 1);
        await this.store().executeSql('DELETE FROM usage_records');
    }
    // ------------------------------------------------------------------
    // Aggregations
    // ------------------------------------------------------------------
    private static periodClause(period: string): [
        string | null,
        Array<string>
    ] {
        bjccovmt7djy10.instrumentFunction(6);
        switch (period) {
            case '5h':
                bjccovmt7djy10.instrumentBranch(6, 0, true);
                bjccovmt7djy10.instrumentRegion(6, 1);
                return [`datetime(created_at) >= datetime('now', '-5 hours')`, []];
            case 'today':
                bjccovmt7djy10.instrumentBranch(6, 1, true);
                bjccovmt7djy10.instrumentRegion(6, 2);
                return [`substr(datetime(created_at, 'localtime'), 1, 10) = date('now', 'localtime')`, []];
            case 'all':
                bjccovmt7djy10.instrumentBranch(6, 2, true);
                bjccovmt7djy10.instrumentRegion(6, 3);
                return [null, []];
            default:
                bjccovmt7djy10.instrumentBranch(6, 3, true);
                bjccovmt7djy10.instrumentRegion(6, 4);
                {
                    const m = /^(\d+)d$/.exec(period);
                    let days = 30;
                    if (m !== null) {
                        bjccovmt7djy10.instrumentBranch(6, 4, true);
                        bjccovmt7djy10.instrumentRegion(6, 5);
                        const n = Number(m[1]);
                        if (!Number.isNaN(n)) {
                            bjccovmt7djy10.instrumentBranch(6, 5, true);
                            bjccovmt7djy10.instrumentRegion(6, 6);
                            days = Math.min(365, Math.max(1, n));
                        }
                        else {
                            bjccovmt7djy10.instrumentBranch(6, 5, false);
                        }
                    }
                    else {
                        bjccovmt7djy10.instrumentBranch(6, 4, false);
                    }
                    bjccovmt7djy10.instrumentRegion(6, 7);
                    return [`datetime(created_at) >= datetime('now', ?)`, [`-${days} days`]];
                }
        }
    }
    private static buildWhere(period: string, accountId: number): [
        string,
        Array<string>
    ] {
        bjccovmt7djy10.instrumentFunction(7);
        const pc = UsageDao.periodClause(period);
        const clause = pc[0];
        const args = pc[1];
        const allArgs: Array<string> = [accountId.toString()];
        for (const a of args) {
            bjccovmt7djy10.instrumentRegion(7, 1);
            allArgs.push(a);
        }
        if (clause === null) {
            bjccovmt7djy10.instrumentBranch(7, 0, true);
            bjccovmt7djy10.instrumentRegion(7, 2);
            return ['WHERE account_id = ?', allArgs];
        }
        else {
            bjccovmt7djy10.instrumentBranch(7, 0, false);
        }
        bjccovmt7djy10.instrumentRegion(7, 3);
        return [`WHERE account_id = ? AND ${clause}`, allArgs];
    }
    private static totalsSql(where: string): string {
        bjccovmt7djy10.instrumentFunction(8);
        bjccovmt7djy10.instrumentRegion(8, 1);
        return `SELECT COALESCE(COUNT(*), 0) AS request_count,
                   COALESCE(COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id END), 0) AS session_count,
                   COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
                   COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
                   COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
                   COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
                   COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
                   COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                   COALESCE(SUM(cost_usd), 0) AS total_cost_usd
            FROM usage_records
            ${where}`;
    }
    async totals(period: string, accountId: number): Promise<Totals> {
        bjccovmt7djy10.instrumentFunction(9);
        const bw = UsageDao.buildWhere(period, accountId);
        const where = bw[0];
        const args = bw[1];
        const rs = await this.store().querySql(UsageDao.totalsSql(where), args);
        const reader = new RowReader(rs);
        let t: Totals = {
            requestCount: 0, sessionCount: 0, totalInputTokens: 0, uncachedInputTokens: 0,
            totalReasoningTokens: 0, cacheHitTokens: 0, cacheWriteTokens: 0, totalOutputTokens: 0,
            totalCostUsd: 0, hitRate: 0, totalTokens: 0,
        };
        if (reader.next()) {
            bjccovmt7djy10.instrumentBranch(9, 0, true);
            bjccovmt7djy10.instrumentRegion(9, 1);
            const hit = reader.getLong('cache_hit_tokens');
            const miss = reader.getLong('uncached_input_tokens');
            const hitRate = hit + miss > 0 ? (bjccovmt7djy10.instrumentBranch(9, 1, true), hit / (hit + miss) * 100) : (bjccovmt7djy10.instrumentBranch(9, 1, false), 0);
            const ti = reader.getLong('total_input_tokens');
            const to = reader.getLong('total_output_tokens');
            const tr = reader.getLong('total_reasoning_tokens');
            t = {
                requestCount: reader.getLong('request_count'),
                sessionCount: reader.getLong('session_count'),
                totalInputTokens: ti,
                uncachedInputTokens: miss,
                totalReasoningTokens: tr,
                cacheHitTokens: hit,
                cacheWriteTokens: reader.getLong('cache_write_tokens'),
                totalOutputTokens: to,
                totalCostUsd: reader.getDouble('total_cost_usd'),
                hitRate: Math.round(hitRate * 100) / 100,
                totalTokens: ti + to + tr,
            };
        }
        else {
            bjccovmt7djy10.instrumentBranch(9, 0, false);
        }
        bjccovmt7djy10.instrumentRegion(9, 2);
        reader.close();
        return t;
    }
    /** 每日聚合 —— db.daily_stats (按账号)。 */
    async dailyStats(days: number, accountId: number): Promise<DailyStat[]> {
        bjccovmt7djy10.instrumentFunction(10);
        const clamped = Math.min(365, Math.max(1, days));
        const rs = await this.store().querySql(`SELECT substr(datetime(created_at, 'localtime'), 1, 10) AS date,
              COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
              COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
              COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
              COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
              COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
              COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
              COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
              COALESCE(COUNT(*), 0) AS request_count
       FROM usage_records
       WHERE account_id = ? AND substr(datetime(created_at, 'localtime'), 1, 10) >= date('now', 'localtime', ?)
       GROUP BY substr(datetime(created_at, 'localtime'), 1, 10)
       ORDER BY date ASC`, [accountId.toString(), `-${clamped} days`]);
        const reader = new RowReader(rs);
        const out: DailyStat[] = [];
        while (reader.next()) {
            bjccovmt7djy10.instrumentRegion(10, 1);
            const hit = reader.getLong('cache_hit_tokens');
            const miss = reader.getLong('uncached_input_tokens');
            const hitRate = hit + miss > 0 ? (bjccovmt7djy10.instrumentBranch(10, 0, true), hit / (hit + miss) * 100) : (bjccovmt7djy10.instrumentBranch(10, 0, false), 0);
            out.push({
                date: reader.getStr('date'),
                totalInputTokens: reader.getLong('total_input_tokens'),
                uncachedInputTokens: miss,
                totalReasoningTokens: reader.getLong('total_reasoning_tokens'),
                cacheHitTokens: hit,
                cacheWriteTokens: reader.getLong('cache_write_tokens'),
                totalOutputTokens: reader.getLong('total_output_tokens'),
                totalCostUsd: reader.getDouble('total_cost_usd'),
                requestCount: reader.getLong('request_count'),
                hitRate: Math.round(hitRate * 100) / 100,
            });
        }
        bjccovmt7djy10.instrumentRegion(10, 2);
        reader.close();
        return out;
    }
    /** 今日 24 小时趋势 (零填充) —— db.today_trend (按账号)。 */
    async todayTrend(accountId: number): Promise<HourStat[]> {
        bjccovmt7djy10.instrumentFunction(11);
        const rs = await this.store().querySql(`SELECT CAST(strftime('%H', datetime(created_at, 'localtime')) AS INTEGER) AS hour,
              COALESCE(SUM(input_tokens), 0) AS input,
              COALESCE(SUM(output_tokens), 0) AS output,
              COALESCE(SUM(reasoning_tokens), 0) AS reasoning
       FROM usage_records
       WHERE account_id = ? AND substr(datetime(created_at, 'localtime'), 1, 10) = date('now', 'localtime')
       GROUP BY hour`, [accountId.toString()]);
        const reader = new RowReader(rs);
        const byHour: Map<number, HourStat> = new Map();
        while (reader.next()) {
            bjccovmt7djy10.instrumentRegion(11, 1);
            const h = reader.getLong('hour');
            byHour.set(h, {
                hour: '',
                input: reader.getLong('input'),
                output: reader.getLong('output'),
                reasoning: reader.getLong('reasoning'),
            });
        }
        reader.close();
        const out: HourStat[] = [];
        for (let h = 0; h < 24; h++) {
            bjccovmt7djy10.instrumentRegion(11, 2);
            const r = byHour.get(h);
            out.push({
                hour: `${String(h).padStart(2, '0')}:00`,
                input: r !== undefined ? (bjccovmt7djy10.instrumentBranch(11, 0, true), r.input) : (bjccovmt7djy10.instrumentBranch(11, 0, false), 0),
                output: r !== undefined ? (bjccovmt7djy10.instrumentBranch(11, 1, true), r.output) : (bjccovmt7djy10.instrumentBranch(11, 1, false), 0),
                reasoning: r !== undefined ? (bjccovmt7djy10.instrumentBranch(11, 2, true), r.reasoning) : (bjccovmt7djy10.instrumentBranch(11, 2, false), 0),
            });
        }
        bjccovmt7djy10.instrumentRegion(11, 3);
        return out;
    }
    /** 单模型聚合 —— db.model_stats (按账号)。 */
    async modelStats(period: string, accountId: number): Promise<ModelStat[]> {
        bjccovmt7djy10.instrumentFunction(12);
        const bw = UsageDao.buildWhere(period, accountId);
        const where = bw[0];
        const args = bw[1];
        const rs = await this.store().querySql(`SELECT model,
              COALESCE(COUNT(*), 0) AS request_count,
              COALESCE(COUNT(DISTINCT CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id END), 0) AS session_count,
              COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
              COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
              COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
              COALESCE(SUM(cache_read_tokens), 0) AS cache_hit_tokens,
              COALESCE(SUM(cache_write_5m_tokens + cache_write_1h_tokens), 0) AS cache_write_tokens,
              COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
              COALESCE(SUM(cost_usd), 0) AS total_cost_usd
       FROM usage_records
       ${where}
       GROUP BY model
       ORDER BY (COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) + COALESCE(SUM(output_tokens), 0)) DESC`, args);
        const reader = new RowReader(rs);
        const out: ModelStat[] = [];
        while (reader.next()) {
            bjccovmt7djy10.instrumentRegion(12, 1);
            const hit = reader.getLong('cache_hit_tokens');
            const miss = reader.getLong('uncached_input_tokens');
            const hitRate = hit + miss > 0 ? (bjccovmt7djy10.instrumentBranch(12, 0, true), hit / (hit + miss) * 100) : (bjccovmt7djy10.instrumentBranch(12, 0, false), 0);
            out.push({
                model: reader.getStr('model'),
                requestCount: reader.getLong('request_count'),
                sessionCount: reader.getLong('session_count'),
                totalInputTokens: reader.getLong('total_input_tokens'),
                uncachedInputTokens: miss,
                totalReasoningTokens: reader.getLong('total_reasoning_tokens'),
                cacheHitTokens: hit,
                cacheWriteTokens: reader.getLong('cache_write_tokens'),
                totalOutputTokens: reader.getLong('total_output_tokens'),
                totalCostUsd: reader.getDouble('total_cost_usd'),
                hitRate: Math.round(hitRate * 100) / 100,
            });
        }
        bjccovmt7djy10.instrumentRegion(12, 2);
        reader.close();
        return out;
    }
    private static readonly SESSION_KEY = `CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id
          WHEN key_id IS NOT NULL AND key_id != '' THEN key_id ELSE '' END`;
    /** 会话聚合 + 分页 —— db.session_stats_page (按账号)。 */
    async sessionStatsPage(page: number, pageSize: number, days: number | null, accountId: number): Promise<[
        SessionStat[],
        number
    ]> {
        bjccovmt7djy10.instrumentFunction(13);
        const whereParts: string[] = ['account_id = ?'];
        const params: Array<string> = [accountId.toString()];
        if (days !== null) {
            bjccovmt7djy10.instrumentBranch(13, 0, true);
            bjccovmt7djy10.instrumentRegion(13, 1);
            whereParts.push(`datetime(created_at) >= datetime('now', ?)`);
            params.push(`-${Math.min(365, Math.max(1, days))} days`);
        }
        else {
            bjccovmt7djy10.instrumentBranch(13, 0, false);
        }
        const where = `WHERE ${whereParts.join(' AND ')}`;
        const store = this.store();
        const totalRs = await store.querySql(`SELECT COUNT(DISTINCT ${UsageDao.SESSION_KEY}) AS count FROM usage_records ${where}`, params);
        const totalReader = new RowReader(totalRs);
        let total = 0;
        if (totalReader.next()) {
            bjccovmt7djy10.instrumentBranch(13, 1, true);
            bjccovmt7djy10.instrumentRegion(13, 2);
            total = totalReader.getLong('count');
        }
        else {
            bjccovmt7djy10.instrumentBranch(13, 1, false);
        }
        totalReader.close();
        const pageArgs: Array<string> = [];
        for (const pv of params) {
            bjccovmt7djy10.instrumentRegion(13, 3);
            pageArgs.push(pv);
        }
        pageArgs.push(pageSize.toString(), ((page - 1) * pageSize).toString());
        const rs = await store.querySql(`SELECT ${UsageDao.SESSION_KEY} AS session_id,
              MAX(key_id) AS key_id,
              COALESCE(COUNT(*), 0) AS request_count,
              COALESCE(SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens), 0) AS total_input_tokens,
              COALESCE(SUM(input_tokens), 0) AS uncached_input_tokens,
              COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
              COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning_tokens,
              COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
              MAX(created_at) AS last_at
       FROM usage_records ${where}
       GROUP BY ${UsageDao.SESSION_KEY}
       ORDER BY last_at DESC
       LIMIT ? OFFSET ?`, pageArgs);
        const reader = new RowReader(rs);
        const records: SessionStat[] = [];
        while (reader.next()) {
            bjccovmt7djy10.instrumentRegion(13, 4);
            records.push({
                sessionId: reader.getStr('session_id'),
                requestCount: reader.getLong('request_count'),
                totalInputTokens: reader.getLong('total_input_tokens'),
                uncachedInputTokens: reader.getLong('uncached_input_tokens'),
                totalOutputTokens: reader.getLong('total_output_tokens'),
                totalReasoningTokens: reader.getLong('total_reasoning_tokens'),
                totalCostUsd: reader.getDouble('total_cost_usd'),
                lastAt: reader.getStr('last_at'),
                keyId: reader.isNull('key_id') ? (bjccovmt7djy10.instrumentBranch(13, 2, true), null) : (bjccovmt7djy10.instrumentBranch(13, 2, false), reader.getStr('key_id')),
                keyName: null,
            });
        }
        bjccovmt7djy10.instrumentRegion(13, 5);
        reader.close();
        return [records, total];
    }
    /** 分页用量记录 —— db.usage_records_page (按账号)。 */
    async usageRecordsPage(page: number, pageSize: number, model: string | null, days: number | null, accountId: number): Promise<[
        UsageRecordRow[],
        number
    ]> {
        bjccovmt7djy10.instrumentFunction(14);
        const whereParts: string[] = ['account_id = ?'];
        const params: Array<string> = [accountId.toString()];
        if (model !== null && model.length > 0) {
            bjccovmt7djy10.instrumentBranch(14, 0, true);
            bjccovmt7djy10.instrumentRegion(14, 1);
            whereParts.push(`model = ?`);
            params.push(model);
        }
        else {
            bjccovmt7djy10.instrumentBranch(14, 0, false);
        }
        if (days !== null) {
            bjccovmt7djy10.instrumentBranch(14, 1, true);
            bjccovmt7djy10.instrumentRegion(14, 2);
            whereParts.push(`datetime(created_at) >= datetime('now', ?)`);
            params.push(`-${Math.min(365, Math.max(1, days))} days`);
        }
        else {
            bjccovmt7djy10.instrumentBranch(14, 1, false);
        }
        const where = `WHERE ${whereParts.join(' AND ')}`;
        const store = this.store();
        const totalRs = await store.querySql(`SELECT COUNT(*) AS count FROM usage_records ${where}`, params);
        const totalReader = new RowReader(totalRs);
        let total = 0;
        if (totalReader.next()) {
            bjccovmt7djy10.instrumentBranch(14, 2, true);
            bjccovmt7djy10.instrumentRegion(14, 3);
            total = totalReader.getLong('count');
        }
        else {
            bjccovmt7djy10.instrumentBranch(14, 2, false);
        }
        totalReader.close();
        const pageArgs: Array<string> = [];
        for (const pv of params) {
            bjccovmt7djy10.instrumentRegion(14, 4);
            pageArgs.push(pv);
        }
        pageArgs.push(pageSize.toString(), ((page - 1) * pageSize).toString());
        const rs = await store.querySql(`SELECT * FROM usage_records ${where} ORDER BY created_at DESC LIMIT ? OFFSET ?`, pageArgs);
        const reader = new RowReader(rs);
        const records: UsageRecordRow[] = [];
        while (reader.next()) {
            bjccovmt7djy10.instrumentRegion(14, 5);
            records.push({
                usgId: reader.getStr('usg_id'),
                createdAt: reader.getStr('created_at'),
                model: reader.getStr('model'),
                provider: reader.isNull('provider') ? (bjccovmt7djy10.instrumentBranch(14, 3, true), null) : (bjccovmt7djy10.instrumentBranch(14, 3, false), reader.getStr('provider')),
                inputTokens: reader.getLong('input_tokens'),
                outputTokens: reader.getLong('output_tokens'),
                reasoningTokens: reader.getLong('reasoning_tokens'),
                cacheReadTokens: reader.getLong('cache_read_tokens'),
                cacheWriteTokens: reader.getLong('cache_write_5m_tokens') + reader.getLong('cache_write_1h_tokens'),
                costUsd: reader.getDouble('cost_usd'),
                sessionId: reader.isNull('session_id') ? (bjccovmt7djy10.instrumentBranch(14, 4, true), null) : (bjccovmt7djy10.instrumentBranch(14, 4, false), reader.getStr('session_id')),
                plan: reader.isNull('plan') ? (bjccovmt7djy10.instrumentBranch(14, 5, true), null) : (bjccovmt7djy10.instrumentBranch(14, 5, false), reader.getStr('plan')),
                keyId: reader.isNull('key_id') ? (bjccovmt7djy10.instrumentBranch(14, 6, true), null) : (bjccovmt7djy10.instrumentBranch(14, 6, false), reader.getStr('key_id')),
                keyName: null,
            });
        }
        bjccovmt7djy10.instrumentRegion(14, 6);
        reader.close();
        return [records, total];
    }
    async listModels(accountId: number): Promise<string[]> {
        bjccovmt7djy10.instrumentFunction(15);
        const rs = await this.store().querySql('SELECT DISTINCT model FROM usage_records WHERE account_id = ? ORDER BY model', [accountId.toString()]);
        const reader = new RowReader(rs);
        const out: string[] = [];
        while (reader.next()) {
            bjccovmt7djy10.instrumentRegion(15, 1);
            out.push(reader.getStr('model'));
        }
        bjccovmt7djy10.instrumentRegion(15, 2);
        reader.close();
        return out;
    }
    async recordBounds(accountId: number): Promise<BoundsRow> {
        bjccovmt7djy10.instrumentFunction(16);
        const rs = await this.store().querySql(`SELECT COUNT(*) AS count, MIN(created_at) AS oldest, MAX(created_at) AS newest
       FROM usage_records WHERE account_id = ?`, [accountId.toString()]);
        const reader = new RowReader(rs);
        let out: BoundsRow = { count: 0, oldest: null, newest: null };
        if (reader.next()) {
            bjccovmt7djy10.instrumentBranch(16, 0, true);
            bjccovmt7djy10.instrumentRegion(16, 1);
            out = {
                count: reader.getLong('count'),
                oldest: reader.isNull('oldest') ? (bjccovmt7djy10.instrumentBranch(16, 1, true), null) : (bjccovmt7djy10.instrumentBranch(16, 1, false), reader.getStr('oldest')),
                newest: reader.isNull('newest') ? (bjccovmt7djy10.instrumentBranch(16, 2, true), null) : (bjccovmt7djy10.instrumentBranch(16, 2, false), reader.getStr('newest')),
            };
        }
        else {
            bjccovmt7djy10.instrumentBranch(16, 0, false);
        }
        bjccovmt7djy10.instrumentRegion(16, 2);
        reader.close();
        return out;
    }
}
