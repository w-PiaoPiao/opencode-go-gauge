import { AppDb } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/AppDb";
import { RowReader } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/RowReader";
import { defaultSettings } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/common/model/Models";
import type { AppSettings } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/common/model/Models";
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
let bjccovmt7djy2s = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/data/db/SettingsDao.ets", hash: "5f1999cf5b148be4537e248cd9d8991adc5314de5fd2413794cdbfc336059684", lineCnt: 156, count: 0, projectPath: "", functions: { 0: { name: "SettingsDao.escapeJson", count: 0, regions: { 0: { startLoc: { line: 19, col: 3 }, endLoc: { line: 21, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 20, col: 5 }, endLoc: { line: 21, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "SettingsDao.unescapeJson", count: 0, regions: { 0: { startLoc: { line: 23, col: 3 }, endLoc: { line: 25, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 24, col: 5 }, endLoc: { line: 25, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "SettingsDao.encode", count: 0, regions: { 0: { startLoc: { line: 28, col: 3 }, endLoc: { line: 52, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 35, col: 59 }, endLoc: { line: 37, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 40, col: 35 }, endLoc: { line: 42, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 44, col: 49 }, endLoc: { line: 50, col: 6 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 51, col: 5 }, endLoc: { line: 52, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 33, col: 23 }, endLoc: { line: 33, col: 106 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 35, col: 9 }, endLoc: { line: 35, col: 57 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 36, col: 11 }, endLoc: { line: 36, col: 75 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 38, col: 24 }, endLoc: { line: 38, col: 94 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 40, col: 9 }, endLoc: { line: 40, col: 33 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 5: { startLoc: { line: 44, col: 9 }, endLoc: { line: 44, col: 47 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 }, 3: { name: "anonymous_0", count: 0, regions: { 0: { startLoc: { line: 46, col: 24 }, endLoc: { line: 48, col: 8 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 47, col: 9 }, endLoc: { line: 48, col: 8 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 3 }, 4: { name: "SettingsDao.decode", count: 0, regions: { 0: { startLoc: { line: 55, col: 3 }, endLoc: { line: 90, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 57, col: 28 }, endLoc: { line: 59, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 75, col: 27 }, endLoc: { line: 81, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 78, col: 7 }, endLoc: { line: 80, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 82, col: 5 }, endLoc: { line: 90, col: 4 }, count: 0, ignored: 0 }, 5: { startLoc: { line: 62, col: 7 }, endLoc: { line: 63, col: 6 }, count: 0, ignored: 0 }, 6: { startLoc: { line: 66, col: 7 }, endLoc: { line: 67, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 57, col: 9 }, endLoc: { line: 57, col: 26 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 75, col: 9 }, endLoc: { line: 75, col: 25 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 2: { startLoc: { line: 84, col: 24 }, endLoc: { line: 84, col: 104 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 3: { startLoc: { line: 85, col: 19 }, endLoc: { line: 85, col: 75 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 4: { startLoc: { line: 86, col: 17 }, endLoc: { line: 86, col: 52 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 4 }, 5: { name: "anonymous_1", count: 0, regions: { 0: { startLoc: { line: 60, col: 22 }, endLoc: { line: 63, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 62, col: 14 }, endLoc: { line: 62, col: 46 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 5 }, 6: { name: "anonymous_2", count: 0, regions: { 0: { startLoc: { line: 64, col: 23 }, endLoc: { line: 67, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 66, col: 14 }, endLoc: { line: 66, col: 49 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 6 }, 7: { name: "SettingsDao.rawPayload", count: 0, regions: { 0: { startLoc: { line: 92, col: 3 }, endLoc: { line: 101, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 96, col: 19 }, endLoc: { line: 98, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 99, col: 5 }, endLoc: { line: 101, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 96, col: 9 }, endLoc: { line: 96, col: 17 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 7 }, 8: { name: "SettingsDao.writePayload", count: 0, regions: { 0: { startLoc: { line: 103, col: 3 }, endLoc: { line: 106, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 104, col: 5 }, endLoc: { line: 106, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 8 }, 9: { name: "SettingsDao.getSettings", count: 0, regions: { 0: { startLoc: { line: 108, col: 3 }, endLoc: { line: 111, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 109, col: 5 }, endLoc: { line: 111, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 9 }, 10: { name: "SettingsDao.saveSettings", count: 0, regions: { 0: { startLoc: { line: 113, col: 3 }, endLoc: { line: 123, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 114, col: 5 }, endLoc: { line: 123, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 116, col: 19 }, endLoc: { line: 116, col: 99 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 10 }, 11: { name: "SettingsDao.getKeyNames", count: 0, regions: { 0: { startLoc: { line: 125, col: 3 }, endLoc: { line: 128, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 126, col: 5 }, endLoc: { line: 128, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 11 }, 12: { name: "SettingsDao.saveKeyNames", count: 0, regions: { 0: { startLoc: { line: 130, col: 3 }, endLoc: { line: 139, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 131, col: 5 }, endLoc: { line: 139, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 12 }, 13: { name: "anonymous_3", count: 0, regions: { 0: { startLoc: { line: 132, col: 19 }, endLoc: { line: 136, col: 6 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 133, col: 41 }, endLoc: { line: 135, col: 8 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 133, col: 11 }, endLoc: { line: 133, col: 39 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 13 }, 14: { name: "SettingsDao.readActiveAccountId", count: 0, regions: { 0: { startLoc: { line: 142, col: 3 }, endLoc: { line: 145, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 143, col: 5 }, endLoc: { line: 145, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 14 }, 15: { name: "SettingsDao.writeActiveAccountId", count: 0, regions: { 0: { startLoc: { line: 147, col: 3 }, endLoc: { line: 150, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 148, col: 5 }, endLoc: { line: 150, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 15 }, 16: { name: "SettingsDao.removeActiveAccountId", count: 0, regions: { 0: { startLoc: { line: 152, col: 3 }, endLoc: { line: 155, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 153, col: 5 }, endLoc: { line: 155, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 16 } }, exeLine: { 0: 6, 1: 7, 2: 8, 3: 10, 4: 11, 5: 12, 6: 13, 7: 14, 8: 15, 9: 18, 10: 19, 11: 20, 12: 23, 13: 24, 14: 28, 15: 29, 16: 30, 17: 31, 18: 32, 19: 33, 20: 34, 21: 35, 22: 36, 23: 38, 24: 39, 25: 40, 26: 41, 27: 43, 28: 44, 29: 45, 30: 46, 31: 47, 32: 49, 33: 51, 34: 55, 35: 56, 36: 57, 37: 58, 38: 60, 39: 61, 40: 62, 41: 64, 42: 65, 43: 66, 44: 68, 45: 69, 46: 70, 47: 71, 48: 73, 49: 74, 50: 75, 51: 76, 52: 77, 53: 78, 54: 79, 55: 82, 56: 83, 57: 84, 58: 85, 59: 86, 60: 87, 61: 88, 62: 92, 63: 93, 64: 94, 65: 95, 66: 96, 67: 97, 68: 99, 69: 100, 70: 103, 71: 104, 72: 105, 73: 108, 74: 109, 75: 110, 76: 113, 77: 114, 78: 115, 79: 116, 80: 117, 81: 119, 82: 120, 83: 121, 84: 122, 85: 125, 86: 126, 87: 127, 88: 130, 89: 131, 90: 132, 91: 133, 92: 134, 93: 137, 94: 138, 95: 142, 96: 143, 97: 144, 98: 147, 99: 148, 100: 149, 101: 152, 102: 153, 103: 154 } });
export interface PayloadData {
    syncIntervalSec: number;
    windowDays: number | null;
    autoSync: boolean;
    activeAccountId: number | null;
    keyNames: Map<string, string>;
}
export class SettingsDao {
    private static escapeJson(v: string): string {
        bjccovmt7djy2s.instrumentFunction(0);
        bjccovmt7djy2s.instrumentRegion(0, 1);
        return v.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    }
    private static unescapeJson(v: string): string {
        bjccovmt7djy2s.instrumentFunction(1);
        bjccovmt7djy2s.instrumentRegion(1, 1);
        return v.replace(/\\"/g, '"').replace(/\\\\/g, '\\');
    }
    /** 将已知键序列化为 JSON 文本 (固定键序便于 diff/调试)。 */
    static encode(patch: AppSettings | null, keyNames: Map<string, string> | null, activeAccountId: number | null): string {
        bjccovmt7djy2s.instrumentFunction(2);
        const s: number = patch !== null && patch.syncIntervalSec !== undefined ? (bjccovmt7djy2s.instrumentBranch(2, 0, true), patch.syncIntervalSec) : (bjccovmt7djy2s.instrumentBranch(2, 0, false), 300);
        let w: string = 'null';
        if (patch !== null && patch.windowDays !== undefined) {
            bjccovmt7djy2s.instrumentBranch(2, 1, true);
            bjccovmt7djy2s.instrumentRegion(2, 1);
            w = patch.windowDays === null ? (bjccovmt7djy2s.instrumentBranch(2, 2, true), 'null') : (bjccovmt7djy2s.instrumentBranch(2, 2, false), patch.windowDays.toString());
        }
        else {
            bjccovmt7djy2s.instrumentBranch(2, 1, false);
        }
        const a: boolean = patch !== null && patch.autoSync !== undefined ? (bjccovmt7djy2s.instrumentBranch(2, 3, true), patch.autoSync) : (bjccovmt7djy2s.instrumentBranch(2, 3, false), true);
        let acc: string = 'null';
        if (activeAccountId !== null) {
            bjccovmt7djy2s.instrumentBranch(2, 4, true);
            bjccovmt7djy2s.instrumentRegion(2, 2);
            acc = activeAccountId.toString();
        }
        else {
            bjccovmt7djy2s.instrumentBranch(2, 4, false);
        }
        let kn = '{}';
        if (keyNames !== null && keyNames.size > 0) {
            bjccovmt7djy2s.instrumentBranch(2, 5, true);
            bjccovmt7djy2s.instrumentRegion(2, 3);
            const parts: string[] = [];
            keyNames.forEach((v, k) => {
                bjccovmt7djy2s.instrumentFunction(3);
                bjccovmt7djy2s.instrumentRegion(3, 1);
                parts.push(`"${SettingsDao.escapeJson(k)}":"${SettingsDao.escapeJson(v)}"`);
            });
            kn = `{${parts.join(',')}}`;
        }
        else {
            bjccovmt7djy2s.instrumentBranch(2, 5, false);
        }
        bjccovmt7djy2s.instrumentRegion(2, 4);
        return `{"sync_interval_sec":${s},"window_days":${w},"auto_sync":${a},"active_account_id":${acc},"key_names":${kn}}`;
    }
    /** 从 payload JSON 文本解析已知键 (容错: 缺键/坏文本回退默认)。 */
    static decode(raw: string): PayloadData {
        bjccovmt7djy2s.instrumentFunction(4);
        let text = raw;
        if (text.length === 0) {
            bjccovmt7djy2s.instrumentBranch(4, 0, true);
            bjccovmt7djy2s.instrumentRegion(4, 1);
            text = '{}';
        }
        else {
            bjccovmt7djy2s.instrumentBranch(4, 0, false);
        }
        const parseNum = (key: string): number | null => {
            bjccovmt7djy2s.instrumentFunction(5);
            const m = new RegExp(`"${key}"\\s*:\\s*(-?\\d+)`).exec(text);
            bjccovmt7djy2s.instrumentRegion(4, 5);
            return m === null ? (bjccovmt7djy2s.instrumentBranch(5, 0, true), null) : (bjccovmt7djy2s.instrumentBranch(5, 0, false), Number(m[1]));
        };
        const parseBool = (key: string): boolean | null => {
            bjccovmt7djy2s.instrumentFunction(6);
            const m = new RegExp(`"${key}"\\s*:\\s*(true|false)`).exec(text);
            bjccovmt7djy2s.instrumentRegion(4, 6);
            return m === null ? (bjccovmt7djy2s.instrumentBranch(6, 0, true), null) : (bjccovmt7djy2s.instrumentBranch(6, 0, false), m[1] === 'true');
        };
        const interval = parseNum('sync_interval_sec');
        const days = parseNum('window_days');
        const auto = parseBool('auto_sync');
        const acc = parseNum('active_account_id');
        const keyNames: Map<string, string> = new Map();
        const knBlock = /"key_names"\s*:\s*\{([^}]*)\}/.exec(text);
        if (knBlock !== null) {
            bjccovmt7djy2s.instrumentBranch(4, 1, true);
            bjccovmt7djy2s.instrumentRegion(4, 2);
            const pairRe = /"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"/g;
            let pm: RegExpExecArray | null;
            while ((pm = pairRe.exec(knBlock[1])) !== null) {
                bjccovmt7djy2s.instrumentRegion(4, 3);
                keyNames.set(SettingsDao.unescapeJson(pm[1]), SettingsDao.unescapeJson(pm[2]));
            }
        }
        else {
            bjccovmt7djy2s.instrumentBranch(4, 1, false);
        }
        bjccovmt7djy2s.instrumentRegion(4, 4);
        const def = defaultSettings();
        return {
            syncIntervalSec: interval !== null ? (bjccovmt7djy2s.instrumentBranch(4, 2, true), Math.min(3600, Math.max(30, interval))) : (bjccovmt7djy2s.instrumentBranch(4, 2, false), def.syncIntervalSec),
            windowDays: days !== null ? (bjccovmt7djy2s.instrumentBranch(4, 3, true), Math.min(3650, Math.max(1, days))) : (bjccovmt7djy2s.instrumentBranch(4, 3, false), null),
            autoSync: auto !== null ? (bjccovmt7djy2s.instrumentBranch(4, 4, true), auto) : (bjccovmt7djy2s.instrumentBranch(4, 4, false), def.autoSync),
            activeAccountId: acc,
            keyNames: keyNames,
        };
    }
    private async rawPayload(): Promise<string> {
        bjccovmt7djy2s.instrumentFunction(7);
        const rs = await AppDb.store().querySql('SELECT payload FROM settings WHERE id = 1');
        const r = new RowReader(rs);
        let out = '';
        if (r.next()) {
            bjccovmt7djy2s.instrumentBranch(7, 0, true);
            bjccovmt7djy2s.instrumentRegion(7, 1);
            out = r.getStr('payload');
        }
        else {
            bjccovmt7djy2s.instrumentBranch(7, 0, false);
        }
        bjccovmt7djy2s.instrumentRegion(7, 2);
        r.close();
        return out;
    }
    private async writePayload(payload: string): Promise<void> {
        bjccovmt7djy2s.instrumentFunction(8);
        bjccovmt7djy2s.instrumentRegion(8, 1);
        await AppDb.store().executeSql('UPDATE settings SET payload = ?, updated_at = ? WHERE id = 1', [payload, new Date().toISOString()]);
    }
    async getSettings(): Promise<AppSettings> {
        bjccovmt7djy2s.instrumentFunction(9);
        bjccovmt7djy2s.instrumentRegion(9, 1);
        const d = SettingsDao.decode(await this.rawPayload());
        return { syncIntervalSec: d.syncIntervalSec, windowDays: d.windowDays, autoSync: d.autoSync };
    }
    async saveSettings(patch: AppSettings): Promise<AppSettings> {
        bjccovmt7djy2s.instrumentFunction(10);
        bjccovmt7djy2s.instrumentRegion(10, 1);
        const merged: AppSettings = {
            syncIntervalSec: Math.min(3600, Math.max(30, patch.syncIntervalSec)),
            windowDays: patch.windowDays === null ? (bjccovmt7djy2s.instrumentBranch(10, 0, true), null) : (bjccovmt7djy2s.instrumentBranch(10, 0, false), Math.min(3650, Math.max(1, patch.windowDays))),
            autoSync: patch.autoSync,
        };
        const current = SettingsDao.decode(await this.rawPayload());
        const keyNames = current.keyNames;
        await this.writePayload(SettingsDao.encode(merged, keyNames, current.activeAccountId));
        return merged;
    }
    async getKeyNames(): Promise<Map<string, string>> {
        bjccovmt7djy2s.instrumentFunction(11);
        bjccovmt7djy2s.instrumentRegion(11, 1);
        const d = SettingsDao.decode(await this.rawPayload());
        return d.keyNames;
    }
    async saveKeyNames(names: Map<string, string>): Promise<void> {
        bjccovmt7djy2s.instrumentFunction(12);
        bjccovmt7djy2s.instrumentRegion(12, 1);
        const filtered: Map<string, string> = new Map();
        names.forEach((v, k) => {
            bjccovmt7djy2s.instrumentFunction(13);
            if (k.length > 0 && v.length > 0) {
                bjccovmt7djy2s.instrumentBranch(13, 0, true);
                bjccovmt7djy2s.instrumentRegion(13, 1);
                filtered.set(k, v);
            }
            else {
                bjccovmt7djy2s.instrumentBranch(13, 0, false);
            }
        });
        const current = SettingsDao.decode(await this.rawPayload());
        await this.writePayload(SettingsDao.encode(null, filtered, current.activeAccountId));
    }
    /** 活跃账号 id (settings payload), 无则 null。 */
    async readActiveAccountId(): Promise<number | null> {
        bjccovmt7djy2s.instrumentFunction(14);
        bjccovmt7djy2s.instrumentRegion(14, 1);
        const d = SettingsDao.decode(await this.rawPayload());
        return d.activeAccountId;
    }
    async writeActiveAccountId(accountId: number): Promise<void> {
        bjccovmt7djy2s.instrumentFunction(15);
        bjccovmt7djy2s.instrumentRegion(15, 1);
        const current = SettingsDao.decode(await this.rawPayload());
        await this.writePayload(SettingsDao.encode(null, current.keyNames, accountId));
    }
    async removeActiveAccountId(): Promise<void> {
        bjccovmt7djy2s.instrumentFunction(16);
        bjccovmt7djy2s.instrumentRegion(16, 1);
        const current = SettingsDao.decode(await this.rawPayload());
        await this.writePayload(SettingsDao.encode(null, current.keyNames, null));
    }
}
