/**
 * 设置页 —— 账户管理 / 自动同步 / 外观(语言·主题·货币) / 更新 / 关于。
 * (android SettingsScreen 移植; M4)
 */
import router from '@ohos.router'
import { promptAction } from '@kit.ArkUI'
import { Repo } from '../../data/repository/DashboardRepository'
import { UpdateApi } from '../../data/remote/UpdateApi'
import { AppPrefs } from '../../common/store/AppPrefs'
import { I18n } from '../../common/i18n/I18n'
import { Theme } from '../theme/Theme'
import { AccountInfo, AppSettings } from '../../common/model/Models'
import { SectionCard } from '../components/Cards'

const APP_VERSION = '1.0.0'

@Component
export struct SettingsPage {
  @State private accounts: AccountInfo[] = []
  @State private activeId: number = 0
  @State private settings: AppSettings = { syncIntervalSec: 300, windowDays: 60, autoSync: true }
  @State private lang: string = 'zh'
  @State private dark: boolean = false
  @State private currency: string = 'USD'
  @State private renamingId: number = -1
  @State private renameText: string = ''
  @State private updateMsg: string = ''
  @Prop @Watch('onRefresh') refreshToken: number = 0

  aboutToAppear(): void {
    this.loadAll()
  }

  onRefresh(): void {
    this.loadAll()
  }

  private async loadAll(): Promise<void> {
    this.lang = AppPrefs.getLanguage()
    this.dark = AppPrefs.isDarkMode()
    this.currency = AppPrefs.getCurrency()
    try {
      const repo = Repo.get()
      this.accounts = await repo.accounts()
      this.activeId = await repo.activeAccountId()
      this.settings = await repo.settings()
    } catch (e) {
      // ignore
    }
  }

  private async saveSettings(): Promise<void> {
    const repo = Repo.get()
    await repo.saveSettings(this.settings)
  }

  private async saveAppearance(): Promise<void> {
    AppPrefs.setLanguage(this.lang)
    AppPrefs.setDarkMode(this.dark)
    AppPrefs.setCurrency(this.currency)
  }

  private async checkUpdate(): Promise<void> {
    this.updateMsg = I18n.t('update_checking')
    try {
      const info = await UpdateApi.checkUpdate(APP_VERSION)
      this.updateMsg = info.hasUpdate ? I18n.t('update_has') : I18n.t('update_none')
    } catch (e) {
      this.updateMsg = I18n.t('update_fail')
    }
  }

  private async confirmDelete(accountId: number): Promise<void> {
    const res = await promptAction.showDialog({
      title: I18n.t('settings_delete'),
      message: I18n.t('settings_delete_confirm'),
      buttons: [
        { text: I18n.t('cancel'), color: '#888888' },
        { text: I18n.t('settings_delete'), color: Theme.danger() },
      ],
    })
    if (res.index === 1) {
      await Repo.get().deleteAccount(accountId)
      await this.loadAll()
    }
  }

  build() {
    Scroll() {
      Column({ space: 12 }) {
        this.accountSection()
        this.syncSection()
        this.appearanceSection()
        this.updateSection()
        this.aboutSection()
      }
      .width('100%')
      .padding(12)
    }
    .width('100%')
    .height('100%')
    .backgroundColor(Theme.bg())
  }

  @Builder
  accountSection() {
    SectionCard({ title: I18n.t('settings_account'), subtitle: `${I18n.t('account')} ${this.accounts.length}` }) {
      Column({ space: 8 }) {
        ForEach(this.accounts, (a: AccountInfo) => {
          Column({ space: 6 }) {
            Row({ space: 8 }) {
              if (this.renamingId === a.id) {
                TextInput({ text: this.renameText, placeholder: a.name })
                  .layoutWeight(1)
                  .height(36)
                  .onChange((v: string) => {
                    this.renameText = v
                  })
                Button(I18n.t('settings_save'))
                  .fontSize(12)
                  .height(32)
                  .backgroundColor(Theme.accent())
                  .onClick(async () => {
                    await Repo.get().renameAccount(a.id, this.renameText)
                    this.renamingId = -1
                    await this.loadAll()
                  })
              } else {
                Column({ space: 2 }) {
                  Text(a.name)
                    .fontSize(14)
                    .fontWeight(FontWeight.Medium)
                    .fontColor(Theme.text())
                  Text(a.hasToken ? `${a.workspaceId}` : I18n.t('notLoggedIn'))
                    .fontSize(11)
                    .fontColor(Theme.sub())
                    .maxLines(1)
                }
                .alignItems(HorizontalAlign.Start)
                .layoutWeight(1)
                if (a.id === this.activeId) {
                  Text(I18n.t('current'))
                    .fontSize(11)
                    .fontColor('#FFFFFF')
                    .padding({ left: 8, right: 8, top: 3, bottom: 3 })
                    .backgroundColor(Theme.accent())
                    .borderRadius(10)
                }
                if (!a.hasToken) {
                  Button(I18n.t('settings_relogin'))
                    .fontSize(11)
                    .height(28)
                    .backgroundColor(Theme.surfaceSoft())
                    .fontColor(Theme.accent())
                    .onClick(() => {
                      router.pushUrl({ url: 'pages/LoginPage', params: { mode: 'relogin' } })
                    })
                }
                Button(a.id === this.activeId ? '✓' : I18n.t('settings_switch'))
                  .fontSize(11)
                  .height(28)
                  .backgroundColor(a.id === this.activeId ? '#00000000' : Theme.surfaceSoft())
                  .fontColor(Theme.accent())
                  .enabled(a.id !== this.activeId)
                  .onClick(async () => {
                    await Repo.get().switchAccount(a.id)
                    await this.loadAll()
                  })
                Button(I18n.t('settings_rename'))
                  .fontSize(11)
                  .height(28)
                  .backgroundColor(Theme.surfaceSoft())
                  .fontColor(Theme.text())
                  .onClick(() => {
                    this.renamingId = a.id
                    this.renameText = a.name
                  })
                Button(I18n.t('settings_delete'))
                  .fontSize(11)
                  .height(28)
                  .backgroundColor(Theme.surfaceSoft())
                  .fontColor(Theme.danger())
                  .onClick(() => {
                    this.confirmDelete(a.id)
                  })
              }
            }
            .width('100%')
            if (this.renamingId !== a.id) {
              Divider()
                .color(Theme.divider())
            }
          }
          .width('100%')
          .padding({ top: 6, bottom: 6 })
        }, (a: AccountInfo) => a.id.toString())

        Button(I18n.t('settings_add'))
          .width('100%')
          .height(40)
          .backgroundColor(Theme.accent())
          .onClick(() => {
            router.pushUrl({ url: 'pages/LoginPage', params: { mode: 'add' } })
          })
      }
    }
  }

  @Builder
  syncSection() {
    SectionCard({ title: I18n.t('sync_title') }) {
      Column({ space: 10 }) {
        Row() {
          Text(I18n.t('sync_interval'))
            .fontSize(13)
            .fontColor(Theme.text())
          Blank()
          Select(this.intervalOptions())
            .selected(this.intervalIndex())
            .value(this.intervalLabel())
            .onSelect((idx: number) => {
              const values: number[] = [60, 300, 900, 1800]
              this.settings.syncIntervalSec = values[idx]
              this.saveSettings()
            })
            .width(120)
        }
        .width('100%')

        Row() {
          Text(I18n.t('sync_range'))
            .fontSize(13)
            .fontColor(Theme.text())
          Blank()
          Select(this.rangeOptions())
            .selected(this.rangeIndex())
            .value(this.rangeLabel())
            .onSelect((idx: number) => {
              const values: Array<number | null> = [30, 60, 90, 180, null]
              this.settings.windowDays = values[idx]
              this.saveSettings()
            })
            .width(120)
        }
        .width('100%')
      }
    }
  }

  @Builder
  appearanceSection() {
    SectionCard({ title: I18n.t('appearance') }) {
      Column({ space: 10 }) {
        Row() {
          Text(I18n.t('language'))
            .fontSize(13)
            .fontColor(Theme.text())
          Blank()
          Select([{ value: '中文' }, { value: 'English' }])
            .selected(this.lang === 'zh' ? 0 : 1)
            .value(this.lang === 'zh' ? '中文' : 'English')
            .onSelect((idx: number) => {
              this.lang = idx === 0 ? 'zh' : 'en'
              this.saveAppearance()
            })
            .width(130)
        }
        .width('100%')

        Row() {
          Text(I18n.t('theme'))
            .fontSize(13)
            .fontColor(Theme.text())
          Blank()
          Select([{ value: I18n.t('themeLight') }, { value: I18n.t('themeDark') }])
            .selected(this.dark ? 1 : 0)
            .value(this.dark ? I18n.t('themeDark') : I18n.t('themeLight'))
            .onSelect((idx: number) => {
              this.dark = idx === 1
              this.saveAppearance()
            })
            .width(130)
        }
        .width('100%')

        Row() {
          Text(I18n.t('currency'))
            .fontSize(13)
            .fontColor(Theme.text())
          Blank()
          Select([{ value: I18n.t('currencyUsd') }, { value: I18n.t('currencyCny') }])
            .selected(this.currency === 'CNY' ? 1 : 0)
            .value(this.currency === 'CNY' ? I18n.t('currencyCny') : I18n.t('currencyUsd'))
            .onSelect((idx: number) => {
              this.currency = idx === 1 ? 'CNY' : 'USD'
              this.saveAppearance()
            })
            .width(130)
        }
        .width('100%')
      }
    }
  }

  @Builder
  updateSection() {
    SectionCard({ title: I18n.t('update_title') }) {
      Column({ space: 8 }) {
        if (this.updateMsg.length > 0) {
          Text(this.updateMsg)
            .fontSize(12)
            .fontColor(Theme.sub())
        }
        Button(I18n.t('update_check'))
          .width('100%')
          .height(38)
          .backgroundColor(Theme.surfaceSoft())
          .fontColor(Theme.accent())
          .onClick(() => {
            this.checkUpdate()
          })
      }
    }
  }

  @Builder
  aboutSection() {
    SectionCard({ title: I18n.t('about_title') }) {
      Column({ space: 6 }) {
        Text(`GoGauge ${I18n.t('version')} ${APP_VERSION}`)
          .fontSize(13)
          .fontColor(Theme.text())
        Text('HarmonyOS NEXT · ArkTS/ArkUI')
          .fontSize(11)
          .fontColor(Theme.sub())
        Text(I18n.t('privacy'))
          .fontSize(11)
          .fontColor(Theme.sub())
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }
  }

  private intervalOptions(): Array<SelectOption> {
    return [
      { value: I18n.t('min1') },
      { value: I18n.t('min5') },
      { value: I18n.t('min15') },
      { value: I18n.t('min30') },
    ]
  }

  private intervalIndex(): number {
    const values: number[] = [60, 300, 900, 1800]
    const i = values.indexOf(this.settings.syncIntervalSec)
    return i >= 0 ? i : 1
  }

  private intervalLabel(): string {
    const labels: Array<[number, string]> = [[60, '1'], [300, '5'], [900, '15'], [1800, '30']]
    for (const p of labels) {
      if (p[0] === this.settings.syncIntervalSec) {
        return `${p[1]} min`
      }
    }
    return '5 min'
  }

  private rangeOptions(): Array<SelectOption> {
    return [
      { value: '30' }, { value: '60' }, { value: '90' }, { value: '180' }, { value: I18n.t('daysAll') },
    ]
  }

  private rangeIndex(): number {
    const values: Array<number | null> = [30, 60, 90, 180, null]
    const i = values.indexOf(this.settings.windowDays)
    return i >= 0 ? i : 1
  }

  private rangeLabel(): string {
    const v = this.settings.windowDays
    return v === null ? I18n.t('daysAll') : `${v}`
  }
}