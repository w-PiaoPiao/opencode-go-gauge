import type AbilityConstant from "@ohos:app.ability.AbilityConstant";
import hilog from "@ohos:hilog";
import UIAbility from "@ohos:app.ability.UIAbility";
import type Want from "@ohos:app.ability.Want";
import type window from "@ohos:window";
import workScheduler from "@ohos:resourceschedule.workScheduler";
import { AppPrefs } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/common/store/AppPrefs";
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
let bjccovmt7djxv7 = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/entryability/EntryAbility.ets", hash: "53369483c26eebdb8c05f0457b1aea62e5683c1b8b95583b92350a5a7837189b", lineCnt: 89, count: 0, projectPath: "", functions: { 0: { name: "EntryAbility.onCreate", count: 0, regions: { 0: { startLoc: { line: 16, col: 3 }, endLoc: { line: 19, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 17, col: 5 }, endLoc: { line: 19, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "EntryAbility.onDestroy", count: 0, regions: { 0: { startLoc: { line: 21, col: 3 }, endLoc: { line: 23, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 22, col: 5 }, endLoc: { line: 23, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "EntryAbility.onWindowStageCreate", count: 0, regions: { 0: { startLoc: { line: 25, col: 3 }, endLoc: { line: 36, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 26, col: 5 }, endLoc: { line: 36, col: 4 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 33, col: 7 }, endLoc: { line: 34, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 31, col: 9 }, endLoc: { line: 32, col: 8 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 2 }, 3: { name: "anonymous_0", count: 0, regions: { 0: { startLoc: { line: 28, col: 44 }, endLoc: { line: 34, col: 6 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 29, col: 21 }, endLoc: { line: 32, col: 8 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 29, col: 11 }, endLoc: { line: 29, col: 19 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 3 }, 4: { name: "EntryAbility.onWindowStageDestroy", count: 0, regions: { 0: { startLoc: { line: 38, col: 3 }, endLoc: { line: 40, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 39, col: 5 }, endLoc: { line: 40, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 4 }, 5: { name: "EntryAbility.onForeground", count: 0, regions: { 0: { startLoc: { line: 42, col: 3 }, endLoc: { line: 44, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 43, col: 5 }, endLoc: { line: 44, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 5 }, 6: { name: "EntryAbility.onBackground", count: 0, regions: { 0: { startLoc: { line: 46, col: 3 }, endLoc: { line: 48, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 47, col: 5 }, endLoc: { line: 48, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 6 }, 7: { name: "EntryAbility.applyWindowPolicy", count: 0, regions: { 0: { startLoc: { line: 54, col: 3 }, endLoc: { line: 69, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 55, col: 5 }, endLoc: { line: 69, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 7 }, 8: { name: "anonymous_1", count: 0, regions: { 0: { startLoc: { line: 55, col: 38 }, endLoc: { line: 66, col: 6 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 56, col: 11 }, endLoc: { line: 63, col: 8 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 63, col: 9 }, endLoc: { line: 65, col: 8 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 8 }, 9: { name: "anonymous_2", count: 0, regions: { 0: { startLoc: { line: 57, col: 69 }, endLoc: { line: 62, col: 10 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 59, col: 24 }, endLoc: { line: 61, col: 12 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 59, col: 15 }, endLoc: { line: 59, col: 22 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 9 }, 10: { name: "anonymous_3", count: 0, regions: { 0: { startLoc: { line: 66, col: 14 }, endLoc: { line: 68, col: 6 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 67, col: 7 }, endLoc: { line: 68, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 10 }, 11: { name: "EntryAbility.scheduleBackgroundSync", count: 0, regions: { 0: { startLoc: { line: 72, col: 3 }, endLoc: { line: 88, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 73, col: 9 }, endLoc: { line: 85, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 85, col: 7 }, endLoc: { line: 87, col: 6 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 11 } }, exeLine: { 0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 9, 8: 10, 9: 11, 10: 12, 11: 13, 12: 15, 13: 16, 14: 17, 15: 18, 16: 21, 17: 22, 18: 25, 19: 26, 20: 27, 21: 28, 22: 29, 23: 30, 24: 31, 25: 33, 26: 35, 27: 38, 28: 39, 29: 42, 30: 43, 31: 46, 32: 47, 33: 54, 34: 55, 35: 56, 36: 57, 37: 58, 38: 59, 39: 60, 40: 63, 41: 64, 42: 66, 43: 67, 44: 72, 45: 73, 46: 74, 47: 75, 48: 76, 49: 77, 50: 78, 51: 79, 52: 80, 53: 81, 54: 83, 55: 84, 56: 85, 57: 86 } });
const HILOG_DOMAIN = 0x0000;
const TAG = 'GoGauge';
const SYNC_WORK_ID = 1001;
const SYNC_ABILITY_NAME = 'SyncWorkerAbility';
const SYNC_INTERVAL_MS = 20 * 60 * 1000; // HarmonyOS 重复任务最短 20 分钟
export default class EntryAbility extends UIAbility {
    onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
        bjccovmt7djxv7.instrumentFunction(0);
        bjccovmt7djxv7.instrumentRegion(0, 1);
        AppPrefs.init(this.context);
        hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onCreate');
    }
    onDestroy(): void {
        bjccovmt7djxv7.instrumentFunction(1);
        bjccovmt7djxv7.instrumentRegion(1, 1);
        hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onDestroy');
    }
    onWindowStageCreate(windowStage: window.WindowStage): void {
        bjccovmt7djxv7.instrumentFunction(2);
        bjccovmt7djxv7.instrumentRegion(2, 1);
        hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onWindowStageCreate');
        this.applyWindowPolicy(windowStage);
        windowStage.loadContent('pages/Index', (err) => {
            bjccovmt7djxv7.instrumentFunction(3);
            if (err.code) {
                bjccovmt7djxv7.instrumentBranch(3, 0, true);
                bjccovmt7djxv7.instrumentRegion(3, 1);
                hilog.error(HILOG_DOMAIN, TAG, 'Failed to load the content. Cause: %{public}s', JSON.stringify(err));
                bjccovmt7djxv7.instrumentRegion(2, 3);
                return;
            }
            else {
                bjccovmt7djxv7.instrumentBranch(3, 0, false);
            }
            bjccovmt7djxv7.instrumentRegion(2, 2);
            hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Succeeded in loading the content.');
        });
        this.scheduleBackgroundSync();
    }
    onWindowStageDestroy(): void {
        bjccovmt7djxv7.instrumentFunction(4);
        bjccovmt7djxv7.instrumentRegion(4, 1);
        hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onWindowStageDestroy');
    }
    onForeground(): void {
        bjccovmt7djxv7.instrumentFunction(5);
        bjccovmt7djxv7.instrumentRegion(5, 1);
        hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onForeground');
    }
    onBackground(): void {
        bjccovmt7djxv7.instrumentFunction(6);
        bjccovmt7djxv7.instrumentRegion(6, 1);
        hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onBackground');
    }
    /**
     * PC/2in1 形态窗口策略 (M5): 宽窗口设置默认尺寸与最小尺寸;
     * 手机全屏窗口下 resize 由系统忽略, 仅设置最小尺寸不起作用, 无副作用。
     */
    private applyWindowPolicy(windowStage: window.WindowStage): void {
        bjccovmt7djxv7.instrumentFunction(7);
        bjccovmt7djxv7.instrumentRegion(7, 1);
        windowStage.getMainWindow().then((win: window.Window) => {
            bjccovmt7djxv7.instrumentFunction(8);
            try {
                bjccovmt7djxv7.instrumentRegion(8, 1);
                win.setWindowLimits({ minWidth: 760, minHeight: 480 }).then(() => {
                    bjccovmt7djxv7.instrumentFunction(9);
                    const w = win.getWindowProperties().windowRect.width;
                    if (w > 720) {
                        bjccovmt7djxv7.instrumentBranch(9, 0, true);
                        bjccovmt7djxv7.instrumentRegion(9, 1);
                        win.resize(1280, 840);
                    }
                    else {
                        bjccovmt7djxv7.instrumentBranch(9, 0, false);
                    }
                });
            }
            catch (e) {
                bjccovmt7djxv7.instrumentRegion(8, 2);
                hilog.warn(HILOG_DOMAIN, TAG, 'applyWindowPolicy failed %{public}s', (e as Error).message);
            }
        }).catch((e: Error) => {
            bjccovmt7djxv7.instrumentFunction(10);
            bjccovmt7djxv7.instrumentRegion(10, 1);
            hilog.warn(HILOG_DOMAIN, TAG, 'getMainWindow failed %{public}s', e.message);
        });
    }
    /** 注册后台周期同步 (幂等: 同一 workId 重复 start 会更新配置)。 */
    private scheduleBackgroundSync(): void {
        bjccovmt7djxv7.instrumentFunction(11);
        try {
            bjccovmt7djxv7.instrumentRegion(11, 1);
            const info: workScheduler.WorkInfo = {
                workId: SYNC_WORK_ID,
                bundleName: 'io.github.yphyphyph.gogauge',
                abilityName: SYNC_ABILITY_NAME,
                networkType: workScheduler.NetworkType.NETWORK_TYPE_ANY,
                isRepeat: true,
                repeatCycleTime: SYNC_INTERVAL_MS,
                isPersisted: true,
            };
            workScheduler.startWork(info);
            hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'background sync scheduled');
        }
        catch (e) {
            bjccovmt7djxv7.instrumentRegion(11, 2);
            hilog.warn(HILOG_DOMAIN, TAG, 'schedule sync failed %{public}s', (e as Error).message);
        }
    }
}
