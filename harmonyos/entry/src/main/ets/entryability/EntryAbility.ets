import AbilityConstant from '@ohos.app.ability.AbilityConstant'
import hilog from '@ohos.hilog'
import UIAbility from '@ohos.app.ability.UIAbility'
import Want from '@ohos.app.ability.Want'
import window from '@ohos.window'

const HILOG_DOMAIN = 0x0000
const TAG = 'GoGauge'

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onCreate')
  }

  onDestroy(): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onDestroy')
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Ability onWindowStageCreate')
    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(HILOG_DOMAIN, TAG, 'Failed to load the content. Cause: %{public}s', JSON.stringify(err))
        return
      }
      hilog.info(HILOG_DOMAIN, TAG, '%{public}s', 'Succeeded in loading the content.')
    })
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
}