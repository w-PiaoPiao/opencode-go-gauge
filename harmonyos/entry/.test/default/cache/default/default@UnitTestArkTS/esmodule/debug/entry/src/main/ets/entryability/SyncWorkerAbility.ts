import WorkSchedulerExtensionAbility from "@ohos:WorkSchedulerExtensionAbility";
import type workScheduler from "@ohos:resourceschedule.workScheduler";
import hilog from "@ohos:hilog";
import { AppDb } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/db/AppDb";
import { Repo } from "@bundle:io.github.yphyphyph.gogauge/entry/ets/data/repository/DashboardRepository";
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
let bjccovmt7djxvr = new BjcCov({ version: "bjc v1.0.0", versionCode: 10000, path: "entry/src/main/ets/entryability/SyncWorkerAbility.ets", hash: "1affef5ba735c32cb6bbc5e65ad136805cb1875c5ba0bd8307d9a06626cb0b1f", lineCnt: 35, count: 0, projectPath: "", functions: { 0: { name: "SyncWorkerAbility.onWorkStart", count: 0, regions: { 0: { startLoc: { line: 14, col: 3 }, endLoc: { line: 17, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 15, col: 5 }, endLoc: { line: 17, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 0 }, 1: { name: "SyncWorkerAbility.onWorkStop", count: 0, regions: { 0: { startLoc: { line: 19, col: 3 }, endLoc: { line: 21, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 20, col: 5 }, endLoc: { line: 21, col: 4 }, count: 0, ignored: 0 } }, branches: {}, ignored: 0, index: 1 }, 2: { name: "SyncWorkerAbility.runSync", count: 0, regions: { 0: { startLoc: { line: 23, col: 3 }, endLoc: { line: 34, col: 4 }, count: 0, ignored: 0 }, 1: { startLoc: { line: 24, col: 9 }, endLoc: { line: 31, col: 6 }, count: 0, ignored: 0 }, 2: { startLoc: { line: 31, col: 7 }, endLoc: { line: 33, col: 6 }, count: 0, ignored: 0 }, 3: { startLoc: { line: 26, col: 29 }, endLoc: { line: 28, col: 8 }, count: 0, ignored: 0 }, 4: { startLoc: { line: 29, col: 7 }, endLoc: { line: 31, col: 6 }, count: 0, ignored: 0 } }, branches: { 0: { startLoc: { line: 26, col: 11 }, endLoc: { line: 26, col: 27 }, trueCount: 0, falseCount: 0, group: {}, ignored: 0 } }, ignored: 0, index: 2 } }, exeLine: { 0: 6, 1: 7, 2: 8, 3: 9, 4: 11, 5: 13, 6: 14, 7: 15, 8: 16, 9: 19, 10: 20, 11: 23, 12: 24, 13: 25, 14: 26, 15: 27, 16: 29, 17: 30, 18: 31, 19: 32 } });
const TAG = 'GoGaugeSync';
export default class SyncWorkerAbility extends WorkSchedulerExtensionAbility {
    onWorkStart(workInfo: workScheduler.WorkInfo): void {
        bjccovmt7djxvr.instrumentFunction(0);
        bjccovmt7djxvr.instrumentRegion(0, 1);
        hilog.info(0x0000, TAG, 'onWorkStart id=%{public}d', workInfo.workId);
        this.runSync();
    }
    onWorkStop(workInfo: workScheduler.WorkInfo): void {
        bjccovmt7djxvr.instrumentFunction(1);
        bjccovmt7djxvr.instrumentRegion(1, 1);
        hilog.info(0x0000, TAG, 'onWorkStop id=%{public}d', workInfo.workId);
    }
    private async runSync(): Promise<void> {
        bjccovmt7djxvr.instrumentFunction(2);
        try {
            bjccovmt7djxvr.instrumentRegion(2, 1);
            await AppDb.init(this.context);
            if (!AppDb.isReady()) {
                bjccovmt7djxvr.instrumentBranch(2, 0, true);
                bjccovmt7djxvr.instrumentRegion(2, 3);
                return;
            }
            else {
                bjccovmt7djxvr.instrumentBranch(2, 0, false);
            }
            bjccovmt7djxvr.instrumentRegion(2, 4);
            const result = await Repo.get().syncUsage('incremental');
            hilog.info(0x0000, TAG, 'sync done ok=%{public}s inserted=%{public}d', `${result.ok}`, result.inserted);
        }
        catch (e) {
            bjccovmt7djxvr.instrumentRegion(2, 2);
            hilog.error(0x0000, TAG, 'sync failed %{public}s', (e as Error).message);
        }
    }
}
