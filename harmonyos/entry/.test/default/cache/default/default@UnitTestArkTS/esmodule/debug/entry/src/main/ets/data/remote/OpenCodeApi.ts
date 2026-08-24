import { HttpFetch } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/remote/HttpFetch";
import { QuotaParser } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/remote/QuotaParser";
import { UsageParser } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/remote/UsageParser";
import type { QuotaResult, UsageRecord } from '../../common/model/Models';
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
let bjccovmt7djy3l = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/remote/OpenCodeApi.ets", hash: "3aaa8ca1c7ffa35c942feebf21dc2cc5902d0a9ec96d8d77da1cbec609f92b0d", lineCnt: 249, count: 0, projectPath: "", functions: { 0: { name: "OpenCodeApi.buildCookieHeader", count: 0, regions: { 0: { startLoc: { line: 25, col: 3 }, endLoc: { line: 40, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 27, col: 53 }, endLoc: { line: 29, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 30, col: 30 }, endLoc: { line: 32, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 33, col: 5 }, endLoc: { line: 38, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 35, col: 34 }, endLoc: { line: 37, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 39, col: 5 }, endLoc: { line: 40, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 27, col: 9 }, endLoc: { line: 27, col: 51 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 30, col: 9 }, endLoc: { line: 30, col: 28 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 35, col: 11 }, endLoc: { line: 35, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 0 }, 1: { name: "OpenCodeApi.argsToJson", count: 0, regions: { 0: { startLoc: { line: 42, col: 3 }, endLoc: { line: 59, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 44, col: 5 }, endLoc: { line: 56, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 45, col: 18 }, endLoc: { line: 47, col: 8 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 49, col: 23 }, endLoc: { line: 51, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 51, col: 14 }, endLoc: { line: 55, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 51, col: 41 }, endLoc: { line: 53, col: 8 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 53, col: 14 }, endLoc: { line: 55, col: 8 }, count: 0, ignored: 0 }, 7: { startLoc: { line: 57, col: 5 }, endLoc: { line: 59, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 45, col: 11 }, endLoc: { line: 45, col: 16 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 49, col: 11 }, endLoc: { line: 49, col: 21 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 51, col: 18 }, endLoc: { line: 51, col: 39 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 1 }, 2: { name: "OpenCodeApi.serverCall", count: 0, regions: { 0: { startLoc: { line: 61, col: 3 }, endLoc: { line: 81, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 65, col: 30 }, endLoc: { line: 67, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 68, col: 5 }, endLoc: { line: 81, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 65, col: 9 }, endLoc: { line: 65, col: 28 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 }, 3: { name: "OpenCodeApi.extractWorkspaceId", count: 0, regions: { 0: { startLoc: { line: 87, col: 3 }, endLoc: { line: 97, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 89, col: 29 }, endLoc: { line: 91, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 92, col: 55 }, endLoc: { line: 94, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 95, col: 5 }, endLoc: { line: 97, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 89, col: 9 }, endLoc: { line: 89, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 92, col: 9 }, endLoc: { line: 92, col: 53 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 96, col: 12 }, endLoc: { line: 96, col: 34 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 3 }, 4: { name: "OpenCodeApi.fetchWorkspaceRefs", count: 0, regions: { 0: { startLoc: { line: 100, col: 3 }, endLoc: { line: 132, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 102, col: 30 }, endLoc: { line: 104, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 119, col: 5 }, endLoc: { line: 127, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 122, col: 34 }, endLoc: { line: 124, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 128, col: 28 }, endLoc: { line: 130, col: 6 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 131, col: 5 }, endLoc: { line: 132, col: 4 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 125, col: 7 }, endLoc: { line: 127, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 102, col: 9 }, endLoc: { line: 102, col: 28 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 122, col: 11 }, endLoc: { line: 122, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 128, col: 9 }, endLoc: { line: 128, col: 26 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 4 }, 5: { name: "OpenCodeApi.resolveWorkspaceId", count: 0, regions: { 0: { startLoc: { line: 135, col: 3 }, endLoc: { line: 153, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 137, col: 30 }, endLoc: { line: 139, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 142, col: 27 }, endLoc: { line: 148, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 143, col: 7 }, endLoc: { line: 147, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 144, col: 79 }, endLoc: { line: 146, col: 10 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 149, col: 26 }, endLoc: { line: 151, col: 6 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 152, col: 5 }, endLoc: { line: 153, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 137, col: 9 }, endLoc: { line: 137, col: 28 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 142, col: 9 }, endLoc: { line: 142, col: 25 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 144, col: 13 }, endLoc: { line: 144, col: 77 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 149, col: 9 }, endLoc: { line: 149, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 5 }, 6: { name: "OpenCodeApi.fetchQuota", count: 0, regions: { 0: { startLoc: { line: 160, col: 3 }, endLoc: { line: 191, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 163, col: 29 }, endLoc: { line: 165, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 166, col: 9 }, endLoc: { line: 185, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 185, col: 7 }, endLoc: { line: 190, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 169, col: 32 }, endLoc: { line: 171, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 181, col: 33 }, endLoc: { line: 183, col: 8 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 184, col: 7 }, endLoc: { line: 185, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 162, col: 19 }, endLoc: { line: 162, col: 73 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 163, col: 9 }, endLoc: { line: 163, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 169, col: 11 }, endLoc: { line: 169, col: 30 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 181, col: 11 }, endLoc: { line: 181, col: 31 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 188, col: 16 }, endLoc: { line: 188, col: 82 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 6 }, 7: { name: "OpenCodeApi.fetchUsagePage", count: 0, regions: { 0: { startLoc: { line: 198, col: 3 }, endLoc: { line: 216, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 202, col: 25 }, endLoc: { line: 209, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 209, col: 12 }, endLoc: { line: 211, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 203, col: 21 }, endLoc: { line: 206, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 206, col: 14 }, endLoc: { line: 208, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 209, col: 26 }, endLoc: { line: 211, col: 6 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 212, col: 5 }, endLoc: { line: 216, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 202, col: 9 }, endLoc: { line: 202, col: 23 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 203, col: 11 }, endLoc: { line: 203, col: 19 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 209, col: 16 }, endLoc: { line: 209, col: 24 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 7 }, 8: { name: "OpenCodeApi.fetchKeyNames", count: 0, regions: { 0: { startLoc: { line: 219, col: 3 }, endLoc: { line: 248, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 221, col: 30 }, endLoc: { line: 223, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 232, col: 9 }, endLoc: { line: 245, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 245, col: 7 }, endLoc: { line: 247, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 237, col: 7 }, endLoc: { line: 243, col: 8 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 240, col: 65 }, endLoc: { line: 242, col: 10 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 244, col: 7 }, endLoc: { line: 245, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 221, col: 9 }, endLoc: { line: 221, col: 28 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 240, col: 13 }, endLoc: { line: 240, col: 63 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 8 } }, exeLine: { 0: 7, 1: 8, 2: 9, 3: 10, 4: 12, 5: 13, 6: 14, 7: 15, 8: 16, 9: 17, 10: 19, 11: 20, 12: 21, 13: 22, 14: 25, 15: 26, 16: 27, 17: 28, 18: 30, 19: 31, 20: 33, 21: 34, 22: 35, 23: 36, 24: 39, 25: 42, 26: 43, 27: 44, 28: 45, 29: 46, 30: 48, 31: 49, 32: 50, 33: 51, 34: 52, 35: 53, 36: 54, 37: 57, 38: 58, 39: 61, 40: 62, 41: 63, 42: 64, 43: 65, 44: 66, 45: 68, 46: 69, 47: 70, 48: 71, 49: 72, 50: 73, 51: 74, 52: 75, 53: 76, 54: 77, 55: 78, 56: 80, 57: 87, 58: 88, 59: 89, 60: 90, 61: 92, 62: 93, 63: 95, 64: 96, 65: 100, 66: 101, 67: 102, 68: 103, 69: 105, 70: 106, 71: 107, 72: 108, 73: 109, 74: 110, 75: 111, 76: 112, 77: 113, 78: 115, 79: 116, 80: 117, 81: 118, 82: 119, 83: 120, 84: 121, 85: 122, 86: 123, 87: 125, 88: 126, 89: 128, 90: 129, 91: 131, 92: 135, 93: 136, 94: 137, 95: 138, 96: 140, 97: 141, 98: 142, 99: 143, 100: 144, 101: 145, 102: 149, 103: 150, 104: 152, 105: 160, 106: 161, 107: 162, 108: 163, 109: 164, 110: 166, 111: 167, 112: 168, 113: 169, 114: 170, 115: 172, 116: 173, 117: 174, 118: 175, 119: 176, 120: 179, 121: 180, 122: 181, 123: 182, 124: 184, 125: 185, 126: 186, 127: 187, 128: 188, 129: 198, 130: 199, 131: 200, 132: 201, 133: 202, 134: 203, 135: 204, 136: 205, 137: 206, 138: 207, 139: 209, 140: 210, 141: 212, 142: 213, 143: 215, 144: 219, 145: 220, 146: 221, 147: 222, 148: 224, 149: 225, 150: 226, 151: 227, 152: 228, 153: 229, 154: 230, 155: 232, 156: 233, 157: 234, 158: 235, 159: 236, 160: 237, 161: 238, 162: 239, 163: 240, 164: 241, 165: 244, 166: 245, 167: 246 } });
export class OpenCodeApi {
    static readonly DASHBOARD_BASE = 'https://opencode.ai/workspace';
    static readonly WORKSPACE_SERVER_ID = 'def39973159c7f0483d8793a822b8dbb10d067e12c65455fcb4608459ba0234f';
    static readonly DEFAULT_USAGE_SERVER_ID = 'bfd684bfc2e4eed05cd0b518f5e4eafd3f3376e3938abb9e536e7c03df831e5c';
    static readonly USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/148.0';
    private static readonly WORKSPACE_ID_RE = /wrk_[A-Za-z0-9]+/;
    private static readonly WORKSPACE_ENTRY_RE = /id\s*:\s*"(wrk_[^"]+)"[^{}]*?name\s*:\s*"([^"]*)"/gs;
    private static readonly KEY_ENTRY_RE = /\{id:"(key_[A-Za-z0-9]+)",name:"([^"]*)"/g;
    /** 归一化 token 为 auth cookie 段。 */
    static buildCookieHeader(token: string): string {
        bjccovmt7djy3l.instrumentFunction(0);
        let cookie = token.trim();
        if (cookie.toLowerCase().startsWith('cookie:')) {
            bjccovmt7djy3l.instrumentBranch(0, 0, true);
            bjccovmt7djy3l.instrumentRegion(0, 1);
            cookie = cookie.slice(7).trim();
        }
        else {
            bjccovmt7djy3l.instrumentBranch(0, 0, false);
        }
        if (cookie.length === 0) {
            bjccovmt7djy3l.instrumentBranch(0, 1, true);
            bjccovmt7djy3l.instrumentRegion(0, 2);
            return '';
        }
        else {
            bjccovmt7djy3l.instrumentBranch(0, 1, false);
        }
        for (const part of cookie.split(';')) {
            bjccovmt7djy3l.instrumentRegion(0, 3);
            const p = part.trim();
            if (p.startsWith('auth=')) {
                bjccovmt7djy3l.instrumentBranch(0, 2, true);
                bjccovmt7djy3l.instrumentRegion(0, 4);
                return p;
            }
            else {
                bjccovmt7djy3l.instrumentBranch(0, 2, false);
            }
        }
        bjccovmt7djy3l.instrumentRegion(0, 5);
        return `auth=${cookie}`;
    }
    private static argsToJson(args: Array<string | number | null>): string {
        bjccovmt7djy3l.instrumentFunction(1);
        const sb: string[] = ['['];
        for (let i = 0; i < args.length; i++) {
            bjccovmt7djy3l.instrumentRegion(1, 1);
            if (i > 0) {
                bjccovmt7djy3l.instrumentBranch(1, 0, true);
                bjccovmt7djy3l.instrumentRegion(1, 2);
                sb.push(',');
            }
            else {
                bjccovmt7djy3l.instrumentBranch(1, 0, false);
            }
            const a = args[i];
            if (a === null) {
                bjccovmt7djy3l.instrumentBranch(1, 1, true);
                bjccovmt7djy3l.instrumentRegion(1, 3);
                sb.push('null');
            }
            else {
                bjccovmt7djy3l.instrumentBranch(1, 1, false);
                bjccovmt7djy3l.instrumentRegion(1, 4);
                if (typeof a === 'string') {
                    bjccovmt7djy3l.instrumentBranch(1, 2, true);
                    bjccovmt7djy3l.instrumentRegion(1, 5);
                    sb.push(`"${a.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`);
                }
                else {
                    bjccovmt7djy3l.instrumentBranch(1, 2, false);
                    bjccovmt7djy3l.instrumentRegion(1, 6);
                    sb.push(a.toString());
                }
            }
        }
        bjccovmt7djy3l.instrumentRegion(1, 7);
        sb.push(']');
        return sb.join('');
    }
    private static async serverCall(serverId: string, args: Array<string | number | null>, refererPath: string, token: string): Promise<string> {
        bjccovmt7djy3l.instrumentFunction(2);
        const cookie = OpenCodeApi.buildCookieHeader(token);
        if (cookie.length === 0) {
            bjccovmt7djy3l.instrumentBranch(2, 0, true);
            bjccovmt7djy3l.instrumentRegion(2, 1);
            throw new Error('token 为空');
        }
        else {
            bjccovmt7djy3l.instrumentBranch(2, 0, false);
        }
        bjccovmt7djy3l.instrumentRegion(2, 2);
        const url = 'https://opencode.ai/_server?id=' +
            encodeURIComponent(serverId) +
            '&args=' + encodeURIComponent(OpenCodeApi.argsToJson(args));
        const headers: Record<string, string> = {
            'Cookie': cookie,
            'X-Server-Id': serverId,
            'X-Server-Instance': `server-fn:${Date.now() * 1000}`,
            'User-Agent': OpenCodeApi.USER_AGENT,
            'Origin': 'https://opencode.ai',
            'Referer': `https://opencode.ai${refererPath}`,
            'Accept': 'text/javascript, application/json;q=0.9, */*;q=0.8',
        };
        return HttpFetch.fetch(url, headers);
    }
    // ------------------------------------------------------------------
    // 工作区解析
    // ------------------------------------------------------------------
    static extractWorkspaceId(raw: string): string {
        bjccovmt7djy3l.instrumentFunction(3);
        const value = raw.trim();
        if (value.length === 0) {
            bjccovmt7djy3l.instrumentBranch(3, 0, true);
            bjccovmt7djy3l.instrumentRegion(3, 1);
            return '';
        }
        else {
            bjccovmt7djy3l.instrumentBranch(3, 0, false);
        }
        if (value.startsWith('wrk_') && value.length > 4) {
            bjccovmt7djy3l.instrumentBranch(3, 1, true);
            bjccovmt7djy3l.instrumentRegion(3, 2);
            return value;
        }
        else {
            bjccovmt7djy3l.instrumentBranch(3, 1, false);
        }
        bjccovmt7djy3l.instrumentRegion(3, 3);
        const m = OpenCodeApi.WORKSPACE_ID_RE.exec(value);
        return m === null ? (bjccovmt7djy3l.instrumentBranch(3, 2, true), '') : (bjccovmt7djy3l.instrumentBranch(3, 2, false), m[0]);
    }
    /** 拉取账号下全部工作区 (id, name)。 */
    static async fetchWorkspaceRefs(token: string): Promise<Array<[
        string,
        string
    ]>> {
        bjccovmt7djy3l.instrumentFunction(4);
        const cookie = OpenCodeApi.buildCookieHeader(token);
        if (cookie.length === 0) {
            bjccovmt7djy3l.instrumentBranch(4, 0, true);
            bjccovmt7djy3l.instrumentRegion(4, 1);
            throw new Error('token 为空');
        }
        else {
            bjccovmt7djy3l.instrumentBranch(4, 0, false);
        }
        const url = 'https://opencode.ai/_server?id=' + encodeURIComponent(OpenCodeApi.WORKSPACE_SERVER_ID);
        const headers: Record<string, string> = {
            'Cookie': cookie,
            'X-Server-Id': OpenCodeApi.WORKSPACE_SERVER_ID,
            'X-Server-Instance': `server-fn:${Date.now() * 1000}`,
            'User-Agent': OpenCodeApi.USER_AGENT,
            'Origin': 'https://opencode.ai',
            'Referer': 'https://opencode.ai',
            'Accept': 'text/javascript, application/json;q=0.9, */*;q=0.8',
        };
        const text = await HttpFetch.fetch(url, headers);
        const refs: Array<[
            string,
            string
        ]> = [];
        const seen: Set<string> = new Set();
        let m: RegExpExecArray | null;
        while ((m = OpenCodeApi.WORKSPACE_ENTRY_RE.exec(text)) !== null) {
            bjccovmt7djy3l.instrumentRegion(4, 2);
            const workspaceId = m[1];
            const name = m[2].trim();
            if (seen.has(workspaceId)) {
                bjccovmt7djy3l.instrumentBranch(4, 1, true);
                bjccovmt7djy3l.instrumentRegion(4, 3);
                continue;
            }
            else {
                bjccovmt7djy3l.instrumentBranch(4, 1, false);
            }
            bjccovmt7djy3l.instrumentRegion(4, 6);
            seen.add(workspaceId);
            refs.push([workspaceId, name]);
        }
        if (refs.length === 0) {
            bjccovmt7djy3l.instrumentBranch(4, 2, true);
            bjccovmt7djy3l.instrumentRegion(4, 4);
            throw new Error('无法从账号数据解析工作区 ID');
        }
        else {
            bjccovmt7djy3l.instrumentBranch(4, 2, false);
        }
        bjccovmt7djy3l.instrumentRegion(4, 5);
        return refs;
    }
    /** 将工作区 hint (id / name / Default) 解析为 wrk_xxx ID。 */
    static async resolveWorkspaceId(hint: string, token: string): Promise<string> {
        bjccovmt7djy3l.instrumentFunction(5);
        const resolved = OpenCodeApi.extractWorkspaceId(hint);
        if (resolved.length > 0) {
            bjccovmt7djy3l.instrumentBranch(5, 0, true);
            bjccovmt7djy3l.instrumentRegion(5, 1);
            return resolved;
        }
        else {
            bjccovmt7djy3l.instrumentBranch(5, 0, false);
        }
        const refs = await OpenCodeApi.fetchWorkspaceRefs(token);
        const hintL = hint.trim().toLowerCase();
        if (hintL.length > 0) {
            bjccovmt7djy3l.instrumentBranch(5, 1, true);
            bjccovmt7djy3l.instrumentRegion(5, 2);
            for (const ref of refs) {
                bjccovmt7djy3l.instrumentRegion(5, 3);
                if (ref[0].toLowerCase() === hintL || ref[1].toLowerCase() === hintL) {
                    bjccovmt7djy3l.instrumentBranch(5, 2, true);
                    bjccovmt7djy3l.instrumentRegion(5, 4);
                    return ref[0];
                }
                else {
                    bjccovmt7djy3l.instrumentBranch(5, 2, false);
                }
            }
        }
        else {
            bjccovmt7djy3l.instrumentBranch(5, 1, false);
        }
        if (refs.length > 0) {
            bjccovmt7djy3l.instrumentBranch(5, 3, true);
            bjccovmt7djy3l.instrumentRegion(5, 5);
            return refs[0][0];
        }
        else {
            bjccovmt7djy3l.instrumentBranch(5, 3, false);
        }
        bjccovmt7djy3l.instrumentRegion(5, 6);
        throw new Error(`无法从 "${hint}" 解析工作区 ID`);
    }
    // ------------------------------------------------------------------
    // Quota
    // ------------------------------------------------------------------
    /** 抓取工作区配额窗口。绝不抛异常 —— 失败返回带 error 的 QuotaResult。 */
    static async fetchQuota(token: string, workspaceHint: string = 'Default'): Promise<QuotaResult> {
        bjccovmt7djy3l.instrumentFunction(6);
        const nowIso = new Date().toISOString();
        const hint = (workspaceHint.length === 0 ? (bjccovmt7djy3l.instrumentBranch(6, 0, true), 'Default') : (bjccovmt7djy3l.instrumentBranch(6, 0, false), workspaceHint)).trim();
        if (token.length === 0) {
            bjccovmt7djy3l.instrumentBranch(6, 1, true);
            bjccovmt7djy3l.instrumentRegion(6, 1);
            return { name: 'Default', workspaceId: hint, success: false, updatedAt: nowIso, windows: [], error: '未配置 token' };
        }
        else {
            bjccovmt7djy3l.instrumentBranch(6, 1, false);
        }
        try {
            bjccovmt7djy3l.instrumentRegion(6, 2);
            const workspaceId = await OpenCodeApi.resolveWorkspaceId(hint, token);
            const cookie = OpenCodeApi.buildCookieHeader(token);
            if (cookie.length === 0) {
                bjccovmt7djy3l.instrumentBranch(6, 2, true);
                bjccovmt7djy3l.instrumentRegion(6, 4);
                throw new Error('token 为空');
            }
            else {
                bjccovmt7djy3l.instrumentBranch(6, 2, false);
            }
            const url = `${OpenCodeApi.DASHBOARD_BASE}/${encodeURIComponent(workspaceId)}/go`;
            const headers: Record<string, string> = {
                'Cookie': cookie,
                'User-Agent': OpenCodeApi.USER_AGENT,
                'Accept': 'text/html, application/xhtml+xml',
            };
            // dashboard HTML 较慢: 2 次尝试 + 500ms 退避 (desktop parity)
            const html = await HttpFetch.fetch(url, headers, 2);
            const windows = QuotaParser.parseQuotaHtml(html);
            if (windows.length === 0) {
                bjccovmt7djy3l.instrumentBranch(6, 3, true);
                bjccovmt7djy3l.instrumentRegion(6, 5);
                throw new Error('无法从 Dashboard HTML 解析额度数据');
            }
            else {
                bjccovmt7djy3l.instrumentBranch(6, 3, false);
            }
            bjccovmt7djy3l.instrumentRegion(6, 6);
            return { name: 'Default', workspaceId: workspaceId, success: true, updatedAt: nowIso, windows: windows, error: null };
        }
        catch (e) {
            bjccovmt7djy3l.instrumentRegion(6, 3);
            return {
                name: 'Default', workspaceId: hint, success: false, updatedAt: nowIso, windows: [],
                error: (e as Error).message !== undefined ? (bjccovmt7djy3l.instrumentBranch(6, 4, true), (e as Error).message) : (bjccovmt7djy3l.instrumentBranch(6, 4, false), '未知错误'),
            };
        }
    }
    // ------------------------------------------------------------------
    // Usage records
    // ------------------------------------------------------------------
    /** 拉取一页用量记录 (每页 50 条, page 从 0 开始)。 */
    static async fetchUsagePage(token: string, workspaceId: string, page: number = 0, keyId: string | null = null): Promise<UsageRecord[]> {
        bjccovmt7djy3l.instrumentFunction(7);
        const args: Array<string | number | null> = [workspaceId];
        if (keyId !== null) {
            bjccovmt7djy3l.instrumentBranch(7, 0, true);
            bjccovmt7djy3l.instrumentRegion(7, 1);
            if (page > 0) {
                bjccovmt7djy3l.instrumentBranch(7, 1, true);
                bjccovmt7djy3l.instrumentRegion(7, 3);
                args.push(page);
                args.push(keyId);
            }
            else {
                bjccovmt7djy3l.instrumentBranch(7, 1, false);
                bjccovmt7djy3l.instrumentRegion(7, 4);
                args.push(keyId);
            }
        }
        else {
            bjccovmt7djy3l.instrumentBranch(7, 0, false);
            bjccovmt7djy3l.instrumentRegion(7, 2);
            if (page > 0) {
                bjccovmt7djy3l.instrumentBranch(7, 2, true);
                bjccovmt7djy3l.instrumentRegion(7, 5);
                args.push(page);
            }
            else {
                bjccovmt7djy3l.instrumentBranch(7, 2, false);
            }
        }
        bjccovmt7djy3l.instrumentRegion(7, 6);
        const text = await OpenCodeApi.serverCall(OpenCodeApi.DEFAULT_USAGE_SERVER_ID, args, `/workspace/${workspaceId}/usage`, token);
        return UsageParser.parseUsageResponse(text);
    }
    /** 拉取工作区下所有 API key 的名称映射 (key_id -> 名称)。失败返回空 map。 */
    static async fetchKeyNames(token: string, workspaceId: string): Promise<Map<string, string>> {
        bjccovmt7djy3l.instrumentFunction(8);
        const cookie = OpenCodeApi.buildCookieHeader(token);
        if (cookie.length === 0) {
            bjccovmt7djy3l.instrumentBranch(8, 0, true);
            bjccovmt7djy3l.instrumentRegion(8, 1);
            return new Map();
        }
        else {
            bjccovmt7djy3l.instrumentBranch(8, 0, false);
        }
        const url = `${OpenCodeApi.DASHBOARD_BASE}/${workspaceId}/keys`;
        const headers: Record<string, string> = {
            'Cookie': cookie,
            'User-Agent': OpenCodeApi.USER_AGENT,
            'Origin': 'https://opencode.ai',
            'Referer': `${OpenCodeApi.DASHBOARD_BASE}/${workspaceId}/keys`,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        };
        try {
            bjccovmt7djy3l.instrumentRegion(8, 2);
            const html = await HttpFetch.fetch(url, headers);
            const names: Map<string, string> = new Map();
            let m: RegExpExecArray | null;
            OpenCodeApi.KEY_ENTRY_RE.lastIndex = 0;
            while ((m = OpenCodeApi.KEY_ENTRY_RE.exec(html)) !== null) {
                bjccovmt7djy3l.instrumentRegion(8, 4);
                const id = m[1];
                const name = m[2].trim();
                if (id.length > 0 && name.length > 0 && !names.has(id)) {
                    bjccovmt7djy3l.instrumentBranch(8, 1, true);
                    bjccovmt7djy3l.instrumentRegion(8, 5);
                    names.set(id, name);
                }
                else {
                    bjccovmt7djy3l.instrumentBranch(8, 1, false);
                }
            }
            bjccovmt7djy3l.instrumentRegion(8, 6);
            return names;
        }
        catch (e) {
            bjccovmt7djy3l.instrumentRegion(8, 3);
            return new Map();
        }
    }
}
