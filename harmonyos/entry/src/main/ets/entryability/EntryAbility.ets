import AbilityConstant from '@ohos.app.ability.AbilityConstant'
import hilog from '@ohos.hilog'
import UIAbility from '@ohos.app.ability.UIAbility'
import Want from '@ohos.app.ability.Want'
import window from '@ohos.window'
import { workScheduler } from '@kit.BackgroundTasksKit'
import { AppPrefs } from '../common/store/AppPrefs'

const HILOG_DOMAIN = 0x0000
const TAG = 'GoGauge'
const SYNC_WORK_ID = 1001
const SYNC_ABILITY_NAME = 'SyncWorkerAbility'
const SYNC_INTERVAL_MS = 20 * 60 * 1000 // HarmonyOS 重复任务最短 20 分钟

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    AppPrefs.init(this.context)
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onCreate')
  }

  onDestroy(): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onDestroy')
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onWindowStageCreate')
    this.applyWindowPolicy(windowStage)
    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(HILOG_DOMAIN, TAG, 'Failed to load the content. Cause: %{public}s', JSON.stringify(err))
        return
      }
      hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Succeeded in loading the content.')
    })
    this.scheduleBackgroundSync()
  }

  onWindowStageDestroy(): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onWindowStageDestroy')
  }

  onForeground(): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onForeground')
  }

  onBackground(): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onBackground')
  }

  /**
   * PC/2in1 形态窗口策略 (M5): 宽窗口设置默认尺寸与最小尺寸;
   * 手机全屏窗口下 resize 由系统忽略, 仅设置最小尺寸不起作用, 无副作用。
   */
  private applyWindowPolicy(windowStage: window.WindowStage): void {
    windowStage.getMainWindow().then((win: window.Window) => {
      try {
        win.setWindowLimits({ minWidth: 760, minHeight: 480 }).then(() => {
          const w = win.getWindowProperties().windowRect.width
          if (w > 720) {
            win.resize(1280, 840)
          }
        })
      } catch (e) {
        hilog.warn(HILOG_DOMAIN, TAG, 'applyWindowPolicy failed %{public}s', (e as Error).message)
      }
    }).catch((e: Error) => {
      hilog.warn(HILOG_DOMAIN, TAG, 'getMainWindow failed %{public}s', e.message)
    })
  }

  /** 注册后台周期同步 (幂等: 同一 workId 重复 start 会更新配置)。 */
  private scheduleBackgroundSync(): void {
    try {
      const info: workScheduler.WorkInfo = {
        workId: SYNC_WORK_ID,
        bundleName: 'io.github.yphyphyph.gogauge',
        abilityName: SYNC_ABILITY_NAME,
        networkType: workScheduler.NetworkType.NETWORK_TYPE_ANY,
        isRepeat: true,
        repeatCycleTime: SYNC_INTERVAL_MS,
        isPersisted: true,
      }
      workScheduler.startWork(info)
      hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'background sync scheduled')
    } catch (e) {
      hilog.warn(HILOG_DOMAIN, TAG, 'schedule sync failed %{public}s', (e as Error).message)
    }
  }
}