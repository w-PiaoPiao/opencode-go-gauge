import preferences from "@ohos:data.preferences";
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
let bjccovmt7djxvz = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/common/store/AppPrefs.ets", hash: "8b9261a3eefe1573e7975c040d1c61db34ddd21986fded6a4db8e255927b9c4a", lineCnt: 132, count: 0, projectPath: "", functions: { 0: { name: "AppPrefs.init", count: 0, regions: { 0: { startLoc: { line: 20, col: 3 }, endLoc: { line: 29, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 21, col: 34 }, endLoc: { line: 23, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 24, col: 9 }, endLoc: { line: 26, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 26, col: 7 }, endLoc: { line: 28, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 21, col: 9 }, endLoc: { line: 21, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 0 }, 1: { name: "AppPrefs.getAuthCookie", count: 0, regions: { 0: { startLoc: { line: 31, col: 3 }, endLoc: { line: 36, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 32, col: 34 }, endLoc: { line: 34, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 35, col: 5 }, endLoc: { line: 36, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 32, col: 9 }, endLoc: { line: 32, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 1 }, 2: { name: "AppPrefs.setAuthCookie", count: 0, regions: { 0: { startLoc: { line: 38, col: 3 }, endLoc: { line: 48, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 39, col: 34 }, endLoc: { line: 41, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 42, col: 9 }, endLoc: { line: 45, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 45, col: 7 }, endLoc: { line: 47, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 39, col: 9 }, endLoc: { line: 39, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 }, 3: { name: "AppPrefs.getWorkspaceHint", count: 0, regions: { 0: { startLoc: { line: 50, col: 3 }, endLoc: { line: 56, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 51, col: 34 }, endLoc: { line: 53, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 54, col: 5 }, endLoc: { line: 56, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 51, col: 9 }, endLoc: { line: 51, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 55, col: 12 }, endLoc: { line: 55, col: 40 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 3 }, 4: { name: "AppPrefs.setWorkspaceHint", count: 0, regions: { 0: { startLoc: { line: 58, col: 3 }, endLoc: { line: 68, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 59, col: 34 }, endLoc: { line: 61, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 62, col: 9 }, endLoc: { line: 65, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 65, col: 7 }, endLoc: { line: 67, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 59, col: 9 }, endLoc: { line: 59, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 4 }, 5: { name: "AppPrefs.clearAuth", count: 0, regions: { 0: { startLoc: { line: 70, col: 3 }, endLoc: { line: 80, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 71, col: 34 }, endLoc: { line: 73, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 74, col: 9 }, endLoc: { line: 77, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 77, col: 7 }, endLoc: { line: 79, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 71, col: 9 }, endLoc: { line: 71, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 5 }, 6: { name: "AppPrefs.getLanguage", count: 0, regions: { 0: { startLoc: { line: 86, col: 3 }, endLoc: { line: 92, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 87, col: 34 }, endLoc: { line: 89, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 90, col: 5 }, endLoc: { line: 92, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 87, col: 9 }, endLoc: { line: 87, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 91, col: 12 }, endLoc: { line: 91, col: 36 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 6 }, 7: { name: "AppPrefs.setLanguage", count: 0, regions: { 0: { startLoc: { line: 94, col: 3 }, endLoc: { line: 96, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 95, col: 5 }, endLoc: { line: 96, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 95, col: 41 }, endLoc: { line: 95, col: 69 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 7 }, 8: { name: "AppPrefs.isDarkMode", count: 0, regions: { 0: { startLoc: { line: 98, col: 3 }, endLoc: { line: 103, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 99, col: 34 }, endLoc: { line: 101, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 102, col: 5 }, endLoc: { line: 103, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 99, col: 9 }, endLoc: { line: 99, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 8 }, 9: { name: "AppPrefs.setDarkMode", count: 0, regions: { 0: { startLoc: { line: 105, col: 3 }, endLoc: { line: 107, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 106, col: 5 }, endLoc: { line: 107, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 106, col: 42 }, endLoc: { line: 106, col: 58 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 9 }, 10: { name: "AppPrefs.getCurrency", count: 0, regions: { 0: { startLoc: { line: 109, col: 3 }, endLoc: { line: 115, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 110, col: 34 }, endLoc: { line: 112, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 113, col: 5 }, endLoc: { line: 115, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 110, col: 9 }, endLoc: { line: 110, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 }, 1: { startLoc: { line: 114, col: 12 }, endLoc: { line: 114, col: 39 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 10 }, 11: { name: "AppPrefs.setCurrency", count: 0, regions: { 0: { startLoc: { line: 117, col: 3 }, endLoc: { line: 119, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 118, col: 5 }, endLoc: { line: 119, col: 4 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 118, col: 41 }, endLoc: { line: 118, col: 72 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 11 }, 12: { name: "AppPrefs.put", count: 0, regions: { 0: { startLoc: { line: 121, col: 3 }, endLoc: { line: 131, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 122, col: 34 }, endLoc: { line: 124, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 125, col: 9 }, endLoc: { line: 128, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 128, col: 7 }, endLoc: { line: 130, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 122, col: 9 }, endLoc: { line: 122, col: 32 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 12 } }, exeLine: { 0: 6, 1: 8, 2: 9, 3: 11, 4: 12, 5: 13, 6: 14, 7: 15, 8: 17, 9: 20, 10: 21, 11: 22, 12: 24, 13: 25, 14: 26, 15: 27, 16: 31, 17: 32, 18: 33, 19: 35, 20: 38, 21: 39, 22: 40, 23: 42, 24: 43, 25: 44, 26: 45, 27: 50, 28: 51, 29: 52, 30: 54, 31: 55, 32: 58, 33: 59, 34: 60, 35: 62, 36: 63, 37: 64, 38: 65, 39: 70, 40: 71, 41: 72, 42: 74, 43: 75, 44: 76, 45: 77, 46: 86, 47: 87, 48: 88, 49: 90, 50: 91, 51: 94, 52: 95, 53: 98, 54: 99, 55: 100, 56: 102, 57: 105, 58: 106, 59: 109, 60: 110, 61: 111, 62: 113, 63: 114, 64: 117, 65: 118, 66: 121, 67: 122, 68: 123, 69: 125, 70: 126, 71: 127, 72: 128 } });
export class AppPrefs {
    static readonly PREFS_NAME: string = 'gogauge';
    static readonly KEY_AUTH_COOKIE: string = 'auth_cookie'; // "auth=<value>"
    static readonly KEY_WORKSPACE_HINT: string = 'workspace_hint'; // "wrk_xxx" | "Default"
    static readonly KEY_LANGUAGE: string = 'language'; // 'zh' | 'en'
    static readonly KEY_DARK_MODE: string = 'dark_mode'; // '0' | '1'
    static readonly KEY_CURRENCY: string = 'currency'; // 'USD' | 'CNY'
    private static store: preferences.Preferences | null = null;
    /** 需在 UIAbility/页面上下文可用后调用一次。 */
    static init(context: Context): void {
        bjccovmt7djxvz.instrumentFunction(0);
        if (AppPrefs.store !== null) {
            bjccovmt7djxvz.instrumentBranch(0, 0, true);
            bjccovmt7djxvz.instrumentRegion(0, 1);
            return;
        }
        else {
            bjccovmt7djxvz.instrumentBranch(0, 0, false);
        }
        try {
            bjccovmt7djxvz.instrumentRegion(0, 2);
            AppPrefs.store = preferences.getPreferencesSync(context, { name: AppPrefs.PREFS_NAME });
        }
        catch (e) {
            bjccovmt7djxvz.instrumentRegion(0, 3);
            AppPrefs.store = null;
        }
    }
    static getAuthCookie(): string {
        bjccovmt7djxvz.instrumentFunction(1);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(1, 0, true);
            bjccovmt7djxvz.instrumentRegion(1, 1);
            return '';
        }
        else {
            bjccovmt7djxvz.instrumentBranch(1, 0, false);
        }
        bjccovmt7djxvz.instrumentRegion(1, 2);
        return AppPrefs.store.getSync(AppPrefs.KEY_AUTH_COOKIE, '') as string;
    }
    static setAuthCookie(value: string): void {
        bjccovmt7djxvz.instrumentFunction(2);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(2, 0, true);
            bjccovmt7djxvz.instrumentRegion(2, 1);
            return;
        }
        else {
            bjccovmt7djxvz.instrumentBranch(2, 0, false);
        }
        try {
            bjccovmt7djxvz.instrumentRegion(2, 2);
            AppPrefs.store.putSync(AppPrefs.KEY_AUTH_COOKIE, value);
            AppPrefs.store.flush();
        }
        catch (e) {
            bjccovmt7djxvz.instrumentRegion(2, 3);
        }
    }
    static getWorkspaceHint(): string {
        bjccovmt7djxvz.instrumentFunction(3);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(3, 0, true);
            bjccovmt7djxvz.instrumentRegion(3, 1);
            return 'Default';
        }
        else {
            bjccovmt7djxvz.instrumentBranch(3, 0, false);
        }
        bjccovmt7djxvz.instrumentRegion(3, 2);
        const v = AppPrefs.store.getSync(AppPrefs.KEY_WORKSPACE_HINT, 'Default') as string;
        return v.length > 0 ? (bjccovmt7djxvz.instrumentBranch(3, 1, true), v) : (bjccovmt7djxvz.instrumentBranch(3, 1, false), 'Default');
    }
    static setWorkspaceHint(value: string): void {
        bjccovmt7djxvz.instrumentFunction(4);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(4, 0, true);
            bjccovmt7djxvz.instrumentRegion(4, 1);
            return;
        }
        else {
            bjccovmt7djxvz.instrumentBranch(4, 0, false);
        }
        try {
            bjccovmt7djxvz.instrumentRegion(4, 2);
            AppPrefs.store.putSync(AppPrefs.KEY_WORKSPACE_HINT, value);
            AppPrefs.store.flush();
        }
        catch (e) {
            bjccovmt7djxvz.instrumentRegion(4, 3);
        }
    }
    static clearAuth(): void {
        bjccovmt7djxvz.instrumentFunction(5);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(5, 0, true);
            bjccovmt7djxvz.instrumentRegion(5, 1);
            return;
        }
        else {
            bjccovmt7djxvz.instrumentBranch(5, 0, false);
        }
        try {
            bjccovmt7djxvz.instrumentRegion(5, 2);
            AppPrefs.store.putSync(AppPrefs.KEY_AUTH_COOKIE, '');
            AppPrefs.store.flush();
        }
        catch (e) {
            bjccovmt7djxvz.instrumentRegion(5, 3);
        }
    }
    // ------------------------------------------------------------------
    // 外观 / 语言 / 货币 (M4)
    // ------------------------------------------------------------------
    static getLanguage(): string {
        bjccovmt7djxvz.instrumentFunction(6);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(6, 0, true);
            bjccovmt7djxvz.instrumentRegion(6, 1);
            return 'zh';
        }
        else {
            bjccovmt7djxvz.instrumentBranch(6, 0, false);
        }
        bjccovmt7djxvz.instrumentRegion(6, 2);
        const v = AppPrefs.store.getSync(AppPrefs.KEY_LANGUAGE, 'zh') as string;
        return v === 'en' ? (bjccovmt7djxvz.instrumentBranch(6, 1, true), 'en') : (bjccovmt7djxvz.instrumentBranch(6, 1, false), 'zh');
    }
    static setLanguage(value: string): void {
        bjccovmt7djxvz.instrumentFunction(7);
        bjccovmt7djxvz.instrumentRegion(7, 1);
        AppPrefs.put(AppPrefs.KEY_LANGUAGE, value === 'zh' ? (bjccovmt7djxvz.instrumentBranch(7, 0, true), 'zh') : (bjccovmt7djxvz.instrumentBranch(7, 0, false), 'en'));
    }
    static isDarkMode(): boolean {
        bjccovmt7djxvz.instrumentFunction(8);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(8, 0, true);
            bjccovmt7djxvz.instrumentRegion(8, 1);
            return false;
        }
        else {
            bjccovmt7djxvz.instrumentBranch(8, 0, false);
        }
        bjccovmt7djxvz.instrumentRegion(8, 2);
        return (AppPrefs.store.getSync(AppPrefs.KEY_DARK_MODE, '0') as string) === '1';
    }
    static setDarkMode(dark: boolean): void {
        bjccovmt7djxvz.instrumentFunction(9);
        bjccovmt7djxvz.instrumentRegion(9, 1);
        AppPrefs.put(AppPrefs.KEY_DARK_MODE, dark ? (bjccovmt7djxvz.instrumentBranch(9, 0, true), '1') : (bjccovmt7djxvz.instrumentBranch(9, 0, false), '0'));
    }
    static getCurrency(): string {
        bjccovmt7djxvz.instrumentFunction(10);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(10, 0, true);
            bjccovmt7djxvz.instrumentRegion(10, 1);
            return 'USD';
        }
        else {
            bjccovmt7djxvz.instrumentBranch(10, 0, false);
        }
        bjccovmt7djxvz.instrumentRegion(10, 2);
        const v = AppPrefs.store.getSync(AppPrefs.KEY_CURRENCY, 'USD') as string;
        return v === 'CNY' ? (bjccovmt7djxvz.instrumentBranch(10, 1, true), 'CNY') : (bjccovmt7djxvz.instrumentBranch(10, 1, false), 'USD');
    }
    static setCurrency(value: string): void {
        bjccovmt7djxvz.instrumentFunction(11);
        bjccovmt7djxvz.instrumentRegion(11, 1);
        AppPrefs.put(AppPrefs.KEY_CURRENCY, value === 'CNY' ? (bjccovmt7djxvz.instrumentBranch(11, 0, true), 'CNY') : (bjccovmt7djxvz.instrumentBranch(11, 0, false), 'USD'));
    }
    private static put(key: string, value: string): void {
        bjccovmt7djxvz.instrumentFunction(12);
        if (AppPrefs.store === null) {
            bjccovmt7djxvz.instrumentBranch(12, 0, true);
            bjccovmt7djxvz.instrumentRegion(12, 1);
            return;
        }
        else {
            bjccovmt7djxvz.instrumentBranch(12, 0, false);
        }
        try {
            bjccovmt7djxvz.instrumentRegion(12, 2);
            AppPrefs.store.putSync(key, value);
            AppPrefs.store.flush();
        }
        catch (e) {
            bjccovmt7djxvz.instrumentRegion(12, 3);
        }
    }
}
