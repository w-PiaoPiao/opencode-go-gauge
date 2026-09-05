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
  /** 本进程内同步在途标志: onWorkStart 是同步回调, 无法 await,
   *  系统可能在上一轮 runSync 尚未结束时再次回调 (条件抖动), 无守卫会并发双跑。 */
  private static syncInFlight: boolean = false

  onWorkStart(workInfo: workScheduler.WorkInfo): void {
    hilog.info(0x0000, TAG, 'onWorkStart id=%{public}d', workInfo.workId)
    if (SyncWorkerAbility.syncInFlight) {
      hilog.info(0x0000, TAG, 'sync in flight, skip work id=%{public}d', workInfo.workId)
      return
    }
    SyncWorkerAbility.syncInFlight = true
    // 回调无法阻塞等待: 持 Promise 引用跑完即释放守卫; 进程被系统回收时
    // 由 Repo.syncUsage 的单飞守卫 + 下个 20 分钟周期自然补偿
    this.runSync().finally(() => {
      SyncWorkerAbility.syncInFlight = false
    })
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