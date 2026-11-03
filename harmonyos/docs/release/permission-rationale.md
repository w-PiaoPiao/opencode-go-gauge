# INTERNET 权限用途说明与隐私声明要点

> 用于 AGC「应用隐私说明」「隐私标签信息录入」「隐私声明」及审核沟通。
> 代码依据：`harmonyos/entry/src/main/module.json5`（`requestPermissions` 仅一项）。
> 官方规则：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-privacy-desc-0000002313477969>、
> <https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-privacy-tag-0000002316420993>（以 AGC 后台实际提示为准）

## 1. 权限清单（与包内声明完全一致）

`module.json5` 中仅声明：

```json5
"requestPermissions": [
  { "name": "ohos.permission.INTERNET" }
]
```

| 权限 | 权限级别 | 是否敏感/受限 | 是否需要 AGC 隐私说明 | 是否需要单独弹窗授权 |
| --- | --- | --- | --- | --- |
| `ohos.permission.INTERNET` | normal（普通） | 否 | **否**（AGC 仅在检测到敏感隐私权限或受限开放权限时才要求填写「应用隐私说明」） | 否（安装时自动授予） |

**结论**：本应用不涉及敏感隐私权限，也不涉及受限开放权限（ACL），因此：

- AGC「应用隐私说明」区域预计**无需逐项填写权限理由**（以后台检测结果为准；若后台仍要求填写，直接粘贴 §2 文案即可）；
- **不需要**申请 ACL 权限、不需要录制权限使用场景视频、发布 Profile 无需勾选任何受限 ACL 权限；
- 无需在 `module.json5` 增加 `reason` / `usedScene` 字段（normal 权限不强制）。

## 2. 权限用途说明（中文，可直接粘贴；≤500 字符）

`ohos.permission.INTERNET`（网络访问，普通权限）：用于在您登录后访问 opencode.ai 官方控制台接口，读取您本人账号的配额窗口、用量统计与请求明细，并同步到本机展示；可选用于获取美元兑人民币汇率（open.er-api.com）以及您主动点击“检查更新”时访问 GitHub Releases。本应用不上传任何数据到开发者服务器，不申请也不使用位置、相机、麦克风、通讯录、相册等任何敏感权限。

**English (for reference)**

`ohos.permission.INTERNET` (normal): used to call official opencode.ai console APIs to read the quota, usage stats and request records of your own account; optionally to fetch a USD→CNY FX rate (open.er-api.com) and, only when you tap "Check for updates", to read GitHub Releases. The app never uploads data to a developer server and does not request or use location, camera, microphone, contacts, photos or any other sensitive permission.

## 3. 隐私标签信息录入建议

AGC「隐私标签信息录入」是手机/平板/PC/2in1 应用必填项。填写时以 AGC 隐私标签的业务场景 + 数据项清单为准，建议如下（**须与开发确认后如实勾选**，虚假申报可能被下架）：

| 问题 | 建议选择 | 依据 |
| --- | --- | --- |
| 是否涉及个人信息收集 | **是**（如后台将“本机处理、不上传”也纳入判断，以 AGC 说明为准） | 应用在本机保存账号会话凭证（Cookie）与账号用量数据，用于“应用功能”场景 |
| 业务场景 | `应用功能`（必选） | 配额查询、用量统计、使用记录、多账号同步均属于应用基本功能 |
| 数据项（参考） | `账号信息`（会话凭证/登录态）、`应用设置信息`、`其他使用应用的信息`（用量记录、模型与费用统计）、`IP 地址`（网络请求由系统直接发出） | 以 AGC 数据项清单为准，只勾选实际涉及的项 |
| 是否涉及广告与营销 | **否** | 无广告、无营销、无推送 |
| 是否涉及分析 | **否**（本应用无统计/分析 SDK，不向任何服务器上报行为数据） | `oh-package.json5` 无第三方依赖；代码无埋点 |
| 是否涉及向第三方披露/共享 | **否**（开发者侧无共享；请求由设备直接发往 opencode.ai / open.er-api.com / GitHub，属于用户主动使用服务） | 无后端、无共享 SDK |
| 是否涉及跨境传输 | 按 AGC 说明判断；如将“设备直连境外服务器”计入，则**是**，数据接收方为 OpenCode / open.er-api.com / GitHub | 见隐私政策 §二、§四 |

> 注意：如果“是否涉及个人信息收集”选择“否”，则无需继续配置；但本应用确实在本机保存账号凭证与用量数据，建议按“是 + 应用功能”申报更稳妥。最终以 AGC 隐私标签说明与审核意见为准。

## 4. 隐私声明（AGC「配置隐私声明」）填写要点

两种方式（见官方文档）：

1. **自定义隐私政策（推荐）**：
   - 隐私政策网址：`<待填：隐私政策托管 URL>`（必须可公开访问、HTTPS、内容与 `privacy-policy-zh.md` 一致、含开发者名称与联系方式；不能是本地文件或需登录的页面）；
   - 隐私权利网址：可与隐私政策同一 URL（政策内已包含删除/更正/投诉路径），或另建“隐私权利”页面。
2. **隐私托管**：仅当发布地区包含中国大陆、设备为手机/平板/PC 2in1 时可用；按后台模板填写后与版本关联。若使用托管，建议同时保留本仓库 `privacy-policy-zh.md` 作为模板底稿。

**审核硬性要求（来自应用审核指南 7.1 / 7.5）**

- [ ] 隐私政策内必须有**真实完整有效的开发者名称**，且与 AGC 实名主体一致；
- [ ] 隐私政策内的**应用名称**必须与提交上架的应用名称一致（GoGauge）；
- [ ] AGC 提交的隐私政策网址内容必须与**应用内展示的隐私政策内容一致**；
- [ ] 必须提供**简体中文版**，且排版可读（无过小字体/过淡颜色）；
- [ ] 处理个人敏感信息的目的、方式和范围需以加粗/增大字号等醒目方式突出（本政策已用粗体标注凭证与账号信息）；
- [ ] 应用**内部**需提供可便捷查看的隐私政策链接；
- [ ] 首次启动或登录前需以**隐私政策弹窗**等显著方式获取用户主动同意，且提供明确的“同意/拒绝”选项，不得默认勾选；
- [ ] 用户未同意前，应用及第三方 SDK 不得收集个人信息或发起相关网络请求。

> 📌 状态：✅ 代码已实现「首次启动隐私政策弹窗（同意/拒绝，未同意不得登录）+ 应用内可点击隐私政策页（`pages/PrivacyPage`，欢迎页底部与 设置→关于 双入口）」；**提交审核前仍需人工复核并替换应用内 `<待填>` 占位符**。同时 AGC 的隐私政策 URL 仍需用户自行托管，且内容与应用内页面一致。详见 `appgallery-metadata.md` §7 与 `agc-release-checklist.md` §5。

## 5. 上架时如何在审核备注里解释（可选，提高通过率）

在 AGC「应用审核信息 → 备注」可填写：

> 本应用为 OpenCode Go 第三方非官方客户端，无自有账号体系；登录即通过 opencode.ai 官方控制台完成 OpenCode 官方授权，仅读取本人账号的只读用量数据；数据仅保存在本机、不上传开发者服务器；不含广告、内购、统计 SDK。审核测试账号：<填写一组可用的 OpenCode Go 测试账号与密码>。隐私政策：<URL>。应用内可在「设置 → 关于 → 隐私政策」及首次启动弹窗查看同一份隐私政策。

说明：应用支持第三方账号登录（OpenCode），产品上不接入华为账号登录（无自有账号体系、无 Account Kit 集成）。如审核对该点有异议（审核指南 3.16），将按审核意见评估处理，见 `appgallery-metadata.md` §7 风险 3。

同时若无法提供第三方测试账号，需按官方要求准备**自测文件**（.docx ≤15MB 或 .mp4，最多 5 个、总 ≤500MB），演示登录、同步、查看数据全流程。
