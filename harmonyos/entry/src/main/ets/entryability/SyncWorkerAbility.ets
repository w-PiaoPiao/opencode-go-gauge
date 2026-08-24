/**
 * 后台增量同步 —— WorkSchedulerExtensionAbility。
 * Android SyncWorker (WorkManager) 移植: HarmonyOS 重复任务最短 20 分钟。
 * 未登录时静默跳过; 失败不重试 (下次周期自然补偿)。
 */
import { WorkSchedulerExtensionAbility, workScheduler } from '@kit.BackgroundTasksKit'
import { hilog } from '@kit.PerformanceAnalysisKit'
import { AppDb } from '../data/db/AppDb'
import { Repo } from '../data/repository/DashboardRepository'

const TAG = 'GoGaugeSync'

export default class SyncWorkerAbility extends WorkSchedulerExtensionAbility {
  onWorkStart(workInfo: workScheduler.WorkInfo): void {
    hilog.info(0x0000, TAG, 'onWorkStart id=%{public}d', workInfo.workId)
    this.runSync()
  }

  onWorkStop(workInfo: workScheduler.WorkInfo): void {
    hilog.info(0x0000, TAG, 'onWorkStop id=%{public}d', workInfo.workId)
  }

  private async runSync(): Promise<void> {
    try {
      await AppDb.init(this.context)
      if (!AppDb.isReady()) {
        return
      }
      const result = await Repo.get().syncUsage('incremental')
      hilog.info(0x0000, TAG, 'sync done ok=%{public}s inserted=%{public}d', `${result.ok}`, result.inserted)
    } catch (e) {
      hilog.error(0x0000, TAG, 'sync failed %{public}s', (e as Error).message)
    }
  }
}