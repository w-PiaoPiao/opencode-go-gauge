/**
 * 启动参数暂存（调试/截图流水线用）。
 *
 * UIAbility 拿到的 Want 参数无法跨层直接传给页面，用这个静态容器在
 * EntryAbility.onCreate / onNewWant 时写入，Index 首帧读取。
 * 生产环境（无 --ps 参数）下全部为默认值，不产生任何行为变化。
 *
 * 约定：
 *   aa start -a EntryAbility -b io.github.yphyphyph.gogauge \
 *     --ps demo=1 --ps lang=zh --ps theme=dark --ps page=stats
 */
export class LaunchParams {
  static demo: boolean = false
  static lang: string = ''
  static theme: string = ''
  static page: string = ''

  /** EntryAbility 在 onCreate / onNewWant 调用；parameters 可能为 undefined。 */
  static apply(parameters: Record<string, Object> | undefined): void {
    if (parameters === undefined || parameters === null) {
      return
    }
    LaunchParams.demo = LaunchParams.boolOf(parameters, 'demo')
    LaunchParams.lang = LaunchParams.strOf(parameters, 'lang')
    LaunchParams.theme = LaunchParams.strOf(parameters, 'theme')
    LaunchParams.page = LaunchParams.strOf(parameters, 'page')
  }

  private static strOf(parameters: Record<string, Object>, key: string): string {
    const raw: Object = parameters[key]
    if (raw === undefined || raw === null) {
      return ''
    }
    return String(raw)
  }

  private static boolOf(parameters: Record<string, Object>, key: string): boolean {
    const v = LaunchParams.strOf(parameters, key)
    return v === '1' || v === 'true'
  }

  static clear(): void {
    LaunchParams.demo = false
    LaunchParams.lang = ''
    LaunchParams.theme = ''
    LaunchParams.page = ''
  }
}
