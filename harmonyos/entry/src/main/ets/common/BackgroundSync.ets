/**
 * 后台周期同步注册（WorkScheduler）—— 统一入口，供 EntryAbility 启动时与设置页
 * 切换「自动增量同步」开关时使用。
 *
 * HarmonyOS 重复任务最短周期为 20 分钟；前台精确间隔由 Index 的定时器负责。
 * 关闭自动同步时应调用 disable()（stopWork），worker 内部也会再次校验 autoSync。
 */
import { workScheduler } from '@kit.BackgroundTasksKit'

export class BackgroundSync {
  static readonly WORK_ID: number = 1001
  static readonly ABILITY_NAME: string = 'SyncWorkerAbility'
  static readonly BUNDLE: string = 'io.github.yphyphyph.gogauge'
  /** 最短重复周期 20 分钟（系统限制）。 */
  static readonly INTERVAL_MS: number = 20 * 60 * 1000

  private static workInfo(): workScheduler.WorkInfo {
    return {
      workId: BackgroundSync.WORK_ID,
      bundleName: BackgroundSync.BUNDLE,
      abilityName: BackgroundSync.ABILITY_NAME,
      networkType: workScheduler.NetworkType.NETWORK_TYPE_ANY,
      isRepeat: true,
      repeatCycleTime: BackgroundSync.INTERVAL_MS,
      isPersisted: true,
    }
  }

  /** 注册/更新周期任务（幂等）。 */
  static enable(): void {
    try {
      workScheduler.startWork(BackgroundSync.workInfo())
    } catch (e) {
      // 注册失败不阻塞主流程；下次启动会重试
    }
  }

  /** 取消周期任务。 */
  static disable(): void {
    try {
      workScheduler.stopWork(BackgroundSync.workInfo(), true)
    } catch (e) {
      // 未注册/系统不支持时忽略
    }
  }

  static apply(enabled: boolean): void {
    if (enabled) {
      BackgroundSync.enable()
    } else {
      BackgroundSync.disable()
    }
  }
}
