/**
 * 应用内隐私政策正文（中英）—— 与 docs/release/privacy-policy-*.md 保持一致。
 *
 * 合规要求（AppGallery 审核 7.1/7.5）：应用内必须可点击查看隐私政策，且首次启动
 * 需用户明确同意。实际行为见 common/auth/Login.ets、common/store/AppPrefs.ets、
 * data/db/AppDb.ets、data/repository/DashboardRepository.ets、data/remote/*。
 *
 * 开发者身份默认为 GoGauge（yphyphyph），联系方式 = 开源仓库 Issues；
 * 若上架主体不同，发布前需替换为 AGC 实名主体名称并重新构建（保持与托管隐私政策一致）。
 */

export interface PrivacySection {
  title: string
  body: string
}

const ZH: PrivacySection[] = [
  {
    title: '引言',
    body: 'GoGauge 是 OpenCode Go 用量仪表盘，由 GoGauge（yphyphyph）开发。本应用不设开发者服务器，不向开发者上传任何个人信息或用量数据；所有数据仅保存在您的设备本地。本应用为第三方非官方客户端，与 OpenCode / OpenCode Go 运营方无隶属或合作关系。',
  },
  {
    title: '一、我们如何处理您的信息',
    body: '仅在实现功能所必需的范围内、在设备本地处理：\n1) 账号登录凭证：您在应用内完成 opencode.ai 登录后，应用从 WebView 读取并保存会话 Cookie（__Host-console_session=…，兼容旧 auth=…），保存在应用私有数据库 accounts.token 列，仅用于以您的身份请求 opencode.ai 官方接口；\n2) 用量数据：请求明细（时间、模型、输入/输出/推理/缓存 Token、费用、会话/Key 标识）、配额窗口、同步状态、Key 名称缓存，保存在应用私有数据库；\n3) 偏好设置：界面语言、深色模式、货币单位，保存在应用私有 preferences；\n4) 工作区标识：用于请求对应工作区数据。\n我们不会收集通讯录、短信、位置、相册、相机、麦克风、剪贴板、设备标识符、应用列表、广告标识或生物特征信息，也不做用户画像。登录凭证受 HarmonyOS 应用沙箱保护，本应用未对其再做额外的自定义加密。',
  },
  {
    title: '二、网络访问与第三方服务',
    body: '以下请求由您的设备直接发出，不经过开发者服务器；请求会包含 IP 等网络层信息，由相应服务按其隐私政策处理：\n1) opencode.ai（必需）：登录页 https://opencode.ai/console/login，数据接口 /console/api/go/status、/request-logs、/orgs、/service-accounts；请求携带您的会话 Cookie，仅用于读取您本人数据；登录成功后应用会清空 WebView Cookie，退出登录时再次清空；\n2) open.er-api.com（可选）：仅在展示人民币金额时请求汇率，结果缓存 6 小时，仅带 User-Agent，不携带 Cookie/账号/用量数据；\n3) GitHub（仅您主动点「检查更新」时）：请求开源仓库 Releases，不携带 Cookie/账号/用量数据。\n本应用不含任何第三方统计/分析/广告/推送 SDK。',
  },
  {
    title: '三、设备权限',
    body: '仅申请 ohos.permission.INTERNET（normal 普通权限，安装即授予），用于访问 opencode.ai、汇率接口及您主动触发的更新检查。不申请位置、相机、麦克风、通讯录、相册、通知等任何敏感或受限权限，不读取设备标识符。',
  },
  {
    title: '四、信息的存储',
    body: '全部信息仅存储在您的 HarmonyOS 设备上的应用私有目录（/data/app/el2/…/io.github.yphyphyph.gogauge），开发者没有服务器，不存储任何用户数据。本地数据保存至您主动删除或卸载应用为止；您可在「设置 → 按同步范围清理」删除超出所选同步范围的本地记录。开发者不会将您的个人信息传输至境外；但您使用本应用时设备会直接连接可能位于境外的 opencode.ai、open.er-api.com、GitHub。',
  },
  {
    title: '五、我们如何保护您的信息',
    body: '应用数据位于 HarmonyOS 应用沙箱内，其他应用无法直接读取；登录凭证仅保存在应用私有数据库，不上传、不写日志、不写入剪贴板；发布版本无调试工具入口；通信使用 HTTPS。互联网环境并非绝对安全，请妥善保管您的 opencode.ai 账号。',
  },
  {
    title: '六、共享、转让和公开披露',
    body: '我们不会向任何第三方出售、共享或公开披露您的个人信息。除为完成您请求的功能而直接连接上述第三方服务外，本应用不存在数据共享行为。',
  },
  {
    title: '七、您的权利',
    body: '您对保存在本机的数据拥有完全控制权：\n• 查阅：在首页/统计/使用记录/设置页查看本地用量与账号信息；\n• 更正：在「设置 → 账户管理」重命名账号、重新登录更新凭证；\n• 删除：「退出登录」清除当前账号凭证、本地用量与同步状态并清空 WebView Cookie；「删除账号」删除账号条目及其全部本地数据（不可恢复）；「按同步范围清理」删除超出范围的本地记录；卸载应用删除全部本地数据；\n• 撤回同意：通过上述删除操作或卸载应用撤回；\n• 反馈：通过下方联系方式与我们联系，我们将在 15 个工作日内答复。\n本应用无开发者侧账号体系，不涉及向开发者申请注销账号。',
  },
  {
    title: '八、未成年人保护',
    body: '本应用是面向开发者的用量查看工具，不面向未成年人，也不会有意收集未成年人个人信息。若您是未满 14 周岁的儿童，请在监护人指导下使用。',
  },
  {
    title: '九、本政策的变更',
    body: '我们可能因功能变化或法规要求更新本政策，并通过应用内提示或华为应用市场版本更新说明告知您；重大变更会再次征得您的同意。您可随时在本页面查看最新版本。',
  },
  {
    title: '十、如何联系我们',
    body: '开发者/运营者：GoGauge（yphyphyph）\n联系方式：通过下方开源仓库的 Issues 反馈（15 个工作日内答复）\n开源仓库：https://github.com/w-PiaoPiao/opencode-go-gauge/issues\n原始项目：https://github.com/yphyphyph/opencode-go-gauge',
  },
]

const EN: PrivacySection[] = [
  {
    title: 'Introduction',
    body: 'GoGauge is a usage dashboard for OpenCode Go, developed by GoGauge (yphyphyph). The app has no developer-run server and uploads no personal information or usage data to the developer; all data stays on your device. This is an unofficial third-party client and is not affiliated with the OpenCode / OpenCode Go operators.',
  },
  {
    title: '1. How we process your information',
    body: 'We only process the following locally on your device, as necessary for the features:\n1) Login credential: after you sign in to opencode.ai in the built-in page, the app reads and stores the session cookie (__Host-console_session=…, legacy auth=… supported) in the app-private database column accounts.token, used only to call opencode.ai official APIs as you;\n2) Usage data: request details (time, model, input/output/reasoning/cached tokens, cost, session/key ids), quota windows, sync status and cached key names, stored in the app-private database;\n3) Preferences: UI language, dark mode, currency, stored in app-private preferences;\n4) Workspace identifier used to request the corresponding workspace data.\nWe do NOT collect contacts, SMS, location, photos, camera, microphone, clipboard, device identifiers, installed-app lists, advertising IDs or biometrics, and we do not profile users. The credential is protected by the HarmonyOS app sandbox; the app applies no additional custom encryption.',
  },
  {
    title: '2. Network access and third-party services',
    body: 'The following requests are sent directly from your device, not through a developer server; they include network-level information such as your IP address and are handled by those providers under their own privacy policies:\n1) opencode.ai (required): login page https://opencode.ai/console/login and the /console/api/go/status, /request-logs, /orgs, /service-accounts endpoints; requests carry your session cookie solely to read your own data. The app clears WebView cookies after login and again on sign-out;\n2) open.er-api.com (optional): USD→CNY exchange rate only when CNY amounts are displayed, cached for 6 hours, sent with User-Agent only and no cookie/account/usage data;\n3) GitHub (only when you tap "Check updates"): reads the open-source repository releases, with no cookie/account/usage data.\nThe app bundles no third-party analytics, advertising or push SDK.',
  },
  {
    title: '3. Permissions',
    body: 'Only ohos.permission.INTERNET (a normal permission granted at install) is requested, used to access opencode.ai, the exchange-rate endpoint and update checks you trigger. No location, camera, microphone, contacts, photos, notifications or other sensitive/restricted permissions are requested, and no device identifiers are read.',
  },
  {
    title: '4. Storage',
    body: 'All information is stored only in the app-private directory on your HarmonyOS device (/data/app/el2/…/io.github.yphyphyph.gogauge); the developer has no server and stores no user data. Local data is kept until you delete it or uninstall the app. You can purge records beyond the selected sync range via Settings → Purge by Range. The developer does not transfer your personal information abroad; however, your device connects directly to opencode.ai, open.er-api.com and GitHub, which may be located outside your region.',
  },
  {
    title: '5. Security',
    body: 'App data lives inside the HarmonyOS app sandbox and cannot be read by other apps; credentials are stored only in the app-private database, never uploaded, logged or copied to the clipboard; release builds contain no debug tools; communication uses HTTPS. The Internet is not absolutely secure — please protect your opencode.ai account.',
  },
  {
    title: '6. Sharing, transfer and disclosure',
    body: 'We never sell, share or publicly disclose your personal information. Apart from direct connections to the third-party services above to fulfil features you requested, the app performs no data sharing.',
  },
  {
    title: '7. Your rights',
    body: 'You fully control the data stored on this device:\n• Access: view local usage and account information on Home, Stats, Records and Settings pages;\n• Rectify: rename accounts or re-login under Settings → Accounts;\n• Delete: "Sign out" clears the current account credential, local usage and sync state and clears WebView cookies; "Delete account" removes the account and all its local data (irreversible); "Purge by Range" removes records beyond the selected range; uninstalling removes all local data;\n• Withdraw consent: via the above deletions or uninstalling;\n• Feedback: contact us via the details below; we reply within 15 business days.\nThe app has no developer-side account system, so there is no developer account to delete.',
  },
  {
    title: '8. Minors',
    body: 'This app is a usage viewer for developers and is not aimed at minors; we do not intentionally collect minors\' personal information. Children under 14 should use it under guardian supervision.',
  },
  {
    title: '9. Changes to this policy',
    body: 'We may update this policy due to feature or legal changes and will inform you via in-app notices or AppGallery release notes; material changes require your consent again. The latest version is always available on this page.',
  },
  {
    title: '10. Contact us',
    body: 'Developer/operator: GoGauge (yphyphyph)\nContact: via Issues in the open-source repository below (reply within 15 business days)\nIssues: https://github.com/w-PiaoPiao/opencode-go-gauge/issues\nUpstream: https://github.com/yphyphyph/opencode-go-gauge',
  },
]

export class PrivacyText {
  static sections(lang: string): PrivacySection[] {
    return lang === 'en' ? EN : ZH
  }

  /** 首次启动弹窗用摘要（保持简短，完整内容在应用内隐私政策页）。 */
  static summary(lang: string): string {
    if (lang === 'en') {
      return 'GoGauge stores your OpenCode Go login credential and usage data only on this device. It accesses opencode.ai to sync your own data, optionally fetches an exchange rate, and never uploads data to the developer. No analytics, ads or third-party tracking SDKs are included. Please read the full Privacy Policy before continuing.'
    }
    return 'GoGauge 仅在本机保存你的 OpenCode Go 登录凭证与用量数据，仅访问 opencode.ai 同步你本人的数据，可选获取汇率，不会向开发者上传任何数据；不含统计、广告或第三方追踪 SDK。继续前请阅读完整《隐私政策》。'
  }
}
