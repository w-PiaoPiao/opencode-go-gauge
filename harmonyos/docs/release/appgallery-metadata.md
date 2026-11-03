# AppGallery 元数据逐字段填写表（GoGauge 1.0.0 / HarmonyOS）

> 用途：照表在 HarmonyOS 开发者中心（AppGallery Connect）逐字段填写，避免漏项。
> 所有规格来自华为官方文档（2026-10 版），**最终以 AGC 后台实际提示为准**。
> 官方入口：
> - 发布 HarmonyOS 应用总览：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-0000002271695230>
> - 素材规范（图标/截图/视频）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-app-visual-asset-spec-0000002277607976>
> - 本地化基础信息（名称/图标）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-nameicon-0000002306265009>
> - 本地化基础信息（介绍/特性/素材）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-intro-0000002313477961>
> - 应用分类/标签：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-class-tag-0000002271695234>
> - 隐私声明：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-privacy-state-0000002278878296>
> - 隐私标签：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-privacy-tag-0000002316420993>
> - 版权信息：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-copyright-0000002278981450>
> - 审核信息/联系方式：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-reviewinfo-0000002320780365>
> - 配置支持设备：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-devicetype-0000002271592112>
> - 上传软件包：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-upload-pkg-0000002277983368>
> - 提交审核：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-submit-0000002286180890>

---

## 0. 一句话结论（先看这个）

| 项 | 结论 |
| --- | --- |
| 上架包类型 | **`.app`（App Pack）**，不是 HAP。HAP 只用于本地安装调试；AGC 上传的必须是 release 构建的 `.app` |
| 包名 | `io.github.yphyphyph.gogauge`（创建应用后不可修改） |
| 版本 | `versionName=1.0.0`、`versionCode=1000000`，与包内 `AppScope/app.json5` 一致 |
| 支持设备 | **AGC 只勾选：手机、PC/2in1**（v1.0 决策：平板不单独勾选，由「手机」默认兼容分发到 HarmonyOS NEXT 平板；包内仍声明 phone/tablet/2in1，满足「包内范围 ≥ AGC 勾选范围」） |
| 应用图标 | 216×216 或 1024×1024 PNG ≤3MB，正方形，**必须与包内图标一致** |
| 截图 | **已转换就绪：手机 9 张（1080×1920 竖向 9:16，≤10 上限）+ PC/2in1 4 张（1920×1080 16:9）；平板不提供独立截图**；JPG ≤5MB。见 §5 |
| 一句话简介 | 中文 ≤17 字符（本应用：`OpenCode Go 用量仪表盘`，恰好 17） |
| 应用介绍 | ≤8000 字符 |
| 新版本特性 | 中国大陆 ≤500 字符 |
| 分类/标签 | 应用 → 工具；最多 5 个标签，1 个主标签 |
| 隐私政策 | 自定义 URL 或隐私托管；应用内已有首启弹窗 + 可点击 `PrivacyPage`（见 §7） |
| 中国大陆发行 | 需 APP 备案（工信部）+ 手机应用需版权证书；个人开发者同样适用 |

---

## 1. 创建应用（APP ID）阶段

| 字段 | 填写/选择 | 说明 | 来源字段 |
| --- | --- | --- | --- |
| 应用类型 | HarmonyOS 应用 | 非元服务、非游戏 | `AppScope/app.json5` |
| 应用名称 | `GoGauge` | 须与包内 `app_name` 一致；不能与其他开发者同名（大陆） | `AppScope`/`entry` 的 `app_name` |
| 应用包名 | `io.github.yphyphyph.gogauge` | 创建后不可改；须与 `bundleName` 一致 | `AppScope/app.json5` |
| 应用分类 | 应用 | 创建后不可改 | — |
| 支持设备 | **手机、PC/2in1**（v1.0 不勾平板；平板由手机兼容分发） | 创建后可在应用信息中调整（发布后只能增加）；包内 deviceTypes 仍为 phone/tablet/2in1，满足包内范围 ≥ 勾选范围 | `module.json5` `deviceTypes` |
| 默认语言 | 简体中文 | 可另加 English | — |
| 所属项目 | `<待填：项目名>` | 可新建 | — |

> 前提：华为开发者账号已完成**实名认证**（个人/企业均可）。实名主体名称 = 后续隐私政策与版权信息中的开发者名称。

## 2. 应用信息（App information）阶段

### 2.1 可本地化基础信息（名称、图标）

| 字段 | 中文（默认） | English | 规格/备注 |
| --- | --- | --- | --- |
| 应用名称 | `GoGauge` | `GoGauge` | 与包内一致 |
| 应用图标 | `release/assets/icon-1024.png`（或 AGC 提示的 216×216 版本 `icon-216.png`） | 同左 | 216×216 或 1024×1024，PNG ≤3MB，正方形 |
| 图标一致性 | ✅ 包内已替换为品牌分层图标 | — | 包内 `AppScope/.../layered_image.json`（foreground/background）与 `icon-1024.png` 同源；上架前比对桌面图标与商店图标（见 §6） |

### 2.2 支持设备（v1.0 只勾手机 + PC/2in1）

- **勾选：手机、PC/2in1。不勾选平板。**
- 原因：v1.0 没有真实平板素材（本机无 Tablet 系统镜像，2in1 窗口 4:3 截图仅为布局验证，不可作为平板商店图）。
- 官方规则（可直接引用）：「当设备类型包含手机时，即便包里未声明平板，应用也会默认以兼容的方式分发到 HarmonyOS NEXT 平板。」——因此平板用户仍可通过兼容方式安装使用；包内 `deviceTypes: ["phone","tablet","2in1"]` ≥ AGC 勾选范围，符合提交规则。
- 发布后升级版本只能**增加**设备、不能删除；后续补齐平板素材后可再勾「平板」。
- 系统版本：包内 `compatibleSdkVersion = 6.1.1(24)`，即要求 **HarmonyOS 6.1.1 / API 24 及以上**。请在应用介绍中写明系统要求（本仓库 `app-intro-zh.md` 已写明）。

### 2.3 应用分类、标签

| 字段 | 填写 | 备注 |
| --- | --- | --- |
| 一级分类 | 应用 | — |
| 二级分类 | 工具 → 工具 | 参考《鸿蒙应用分类》列表 |
| 标签（≤5，必须 1 个主标签） | 主标签 `工具`；次标签 `AI` | 主标签须与二级分类关联；不要选广告营销类标签 |

### 2.4 开发者服务信息

| 字段 | 填写 |
| --- | --- |
| 官网 | `<待填：官网 URL，可填 GitHub 仓库或项目页>` |
| 客服邮箱 | `<待填：邮箱>` |
| 客服电话（可选） | `<待填：电话>` |

## 3. 版本信息（Version information）阶段

### 3.1 软件包

- 上传文件：`build/outputs/default/GoGauge-default-signed.app`（名称以实际构建产物为准；**.app 不是 .hap**）。
- 上传时使用场景选「测试和正式上架」。
- 上传后等待「合法性检测」：**已达标** 才能发布；「待优化」可提交但存在驳回风险；「不通过」必须修复。
- 建议同时跑「上架自检」（每应用最多 2 个并发任务）：兼容性/稳定性/性能/功耗/UX/隐私，报告可提前暴露问题。

### 3.2 可本地化基础信息（介绍、特性、素材）

| 字段 | 中文 | English | 限制 |
| --- | --- | --- | --- |
| 应用介绍 | 见 `app-intro-zh.md` §2（约 1,350 字符） | 见 `app-intro-en.md` §2（约 3,000 字符） | ≤8000 字符 |
| 一句话简介 | `OpenCode Go 用量仪表盘` | `OpenCode Go usage dashboard` | 中文 ≤17 字符；其他语言 ≤80 字符 |
| 新版本特性 | 见 `release-notes-1.0.0.md` | 同文件 English 段 | 中国大陆 ≤500 字符；非大陆 ≤1000 |
| 介绍截图 | 见 §5 文件清单 | 同左 | 见 §5 规格 |
| 介绍视频（可选） | 不提供 | — | MOV/MP4，15 秒–2 分钟，≤500MB |

### 3.3 隐私声明

| 字段 | 填写 |
| --- | --- |
| 隐私政策网址 | `<待填：隐私政策托管 URL>`（HTTPS、公开可访问、与提交内容一致） |
| 隐私权利网址 | 同隐私政策 URL（政策内已含删除/更正/投诉路径），或单独页面 |

- 也可用 AGC **隐私托管**（需发布地区含中国大陆且设备为手机/平板/PC 2in1）：按模板生成后关联版本。
- 本仓库底稿：`privacy-policy-zh.md` / `privacy-policy-en.md`（提交前替换占位符）。

### 3.4 隐私说明（敏感权限）

- 本应用仅 `ohos.permission.INTERNET`（normal，非敏感、非受限），预计**无需**填写权限使用理由、无需场景视频；如后台仍提示填写，用 `permission-rationale.md` §2 文案。

### 3.5 隐私标签信息录入（手机/平板/PC 必填）

| 问题 | 建议 | 说明 |
| --- | --- | --- |
| 是否涉及个人信息收集 | **是** → 业务场景 `应用功能` | 本机保存登录凭证与用量数据；详见 `permission-rationale.md` §3 |
| 广告与营销 | 否 | 无广告 |
| 分析 | 否 | 无统计 SDK/埋点 |
| 向第三方披露 | 否 | 无后端共享；请求由设备直连官方 API |
| 跨境传输 | 按后台定义判断（设备直连境外服务器） | 与隐私政策 §二/§四保持一致 |

### 3.6 内容分级

- 按 AGC 问卷如实作答（无社交、无 UGC、无广告、无内购、无抽奖），预期结果 **3+**；如计算更低龄需确认是否仅面向儿童 → 选「否」。

### 3.7 AI 功能声明

- 本应用**不提供**生成式 AI 功能（仅展示第三方用量数据），按后台问卷选「不涉及」。如后台提示必须填写，说明“应用不提供 AI 生成合成服务”。

### 3.8 版权信息

| 材料 | 要求 | 状态 |
| --- | --- | --- |
| 应用版权证书/代理证书 | 发布地区包含中国大陆且含手机设备时**必选**；JPG/PNG/BMP，每张 ≤15MB，最多 10 张 | `<待用户提供>` |
| 电子版权证书（可选） | PDF ≤5MB | `<待用户提供或跳过>` |
| 授权书及其他材料（可选） | ZIP ≤200MB，仅 JPG/JPEG/BMP/PDF，≤3 层目录、≤200 张 | 视情况 |

> 版权证书通常指**计算机软件著作权登记证书**（软著）或应用版权证明/代理授权。个人开发者也可申请软著，周期较长，请尽早准备。

### 3.9 核准（备案）信息

- 中国大陆发行必须完成 **APP 备案（工信部核准）**：在接入商（如华为云）备案系统选择「鸿蒙」平台并填写本包名；未备案会影响搜索与展示，甚至无法上架。
- AGC 填写时选择「您的 APP 服务器在中国大陆 / 不在中国大陆 / 单机 APP」。
  - 本应用无开发者服务器，但会连接 opencode.ai 等互联网服务，**不属于“单机应用”**；建议按实际主体与服务器情况如实选择（通常为「服务器在中国大陆」并完成备案，或按接入商指引操作）。**以备案接入商与 AGC 后台指引为准。**

### 3.10 审核信息与联系方式

| 字段 | 填写 | 说明 |
| --- | --- | --- |
| 需要登录进行审核 | **勾选** | 应用核心功能需登录 opencode.ai 后才能使用 |
| 测试账号 | `<待填：一组可用的 OpenCode Go 测试账号/密码>` | 审核人员需能完成登录→同步→查看→退出全流程；若无法提供，需提供自测视频/文档 |
| 备注 | 见 `permission-rationale.md` §5 | 解释第三方登录与数据仅本机 |
| 自测文件（可选但推荐） | `.docx`（≤15MB）或 `.mp4`，最多 5 个、总 ≤500MB | 演示登录与各页面 |
| 应用负责人手机号/邮箱/验证码/姓名 | `<待用户填写>` | 中国大陆开发者必填；审核结果会发到邮箱 |

### 3.11 上架时间

- 建议先「审核通过后立即上架」，或指定时间；审核通过后也可手动发布。

## 4. 上传与提交清单（勾选式）

- [ ] 已创建 HarmonyOS 应用，包名 `io.github.yphyphyph.gogauge`
- [ ] 已申请**发布证书**（`.cer`）与**发布 Profile**（`.p7b`），并用其签名构建 **release `.app`**
- [ ] `.app` 已上传，「合法性检测」= 已达标
- [ ] 应用名称/图标与包内一致
- [ ] 一句话简介 ≤17 字符、应用介绍 ≤8000 字符（已校验）
- [ ] 截图符合 §5 规格与数量（手机 9 张 1080×1920、PC 4 张 1920×1080；平板不提供，v1.0 不勾平板）
- [ ] 隐私政策 URL 可访问、含开发者名称、与 `privacy-policy-zh.md` 一致
- [ ] 隐私标签信息已如实填写
- [ ] 内容分级问卷已完成
- [ ] 版权证书已上传（手机 + 中国大陆）
- [ ] APP 备案已完成并在 AGC 正确填写
- [ ] 审核测试账号与备注已填写
- [ ] 点击「提交审核」

## 5. 截图规格与最终文件名映射

### 5.1 官方规格（2026-10 V10，必读）

| 设备 | 方向 | 比例 | 分辨率 | 数量 | 格式/大小 |
| --- | --- | --- | --- | --- | --- |
| 手机 | 竖向 | 9:16 | 1080×1920 | 3–10 | PNG/JPG/JPEG ≤5MB |
| 手机 | 横向 | 16:9 | 1920×1080 | 3–10 | 同上 |
| 平板 | 横向 | 3:2 | 1920×1280 | 3–10 | 同上 |
| 平板 | 竖向 | 2:3 | 1280×1920 | 3–10 | 同上 |
| PC/2in1 | 横向 | 16:9 | 1920×1080 | 3–10 | 同上 |

> 同一设备类型下，如同时上传横向与竖向截图，截图方向与介绍视频方向需保持一致；本应用手机只传竖向、PC 只传横向。
> 原始截图（模拟器 1320×2856 / 3120×2080 等）**不能直接上传**，已用 `tools/prep-screenshots.py` 转换（见 §5.4）。
> **平板行仅作官方规格备查**：v1.0 不提供平板截图、AGC 不勾选平板（Lead 决策，见 §2.2）。

### 5.2 最终截图清单（已就绪，2026-11-03 流水线产出）

**唯一原始清单**：`harmonyos/docs/store-assets/screenshot-manifest.md`（13 张正式素材）。
**上传用已转换文件**：`harmonyos/docs/release/screenshots-upload/`（AGC 规格，共 13 张）。

#### 手机（上传 9 张，竖向 1080×1920，9:16）

| 上传序 | 页面 | 上传文件 | 说明 |
| --- | --- | --- | --- |
| 1 | 首页-亮 | `phone/home-light.jpeg` | 配额三窗口 + 6 KPI（首图最重要） |
| 2 | 统计-亮 | `phone/stats-light.jpeg` | 4 KPI + Token 构成 + 模型排行/趋势 |
| 3 | 统计-下滑-亮 | `phone/stats-scrolled-light.jpeg` | 趋势 + **日历热力图** + 模型用量趋势（非独立 tab，是统计页下滑后的画面，AGC 按顺序上传即可） |
| 4 | 使用记录-亮 | `phone/records-light.jpeg` | 会话 / 请求明细 + 模型筛选 |
| 5 | 设置-亮 | `phone/settings-light.jpeg` | 多账号 + 同步 + 外观（不得出现调试入口） |
| 6 | 首页-暗 | `phone/home-dark.jpeg` | 双主题能力 |
| 7 | 统计-暗 | `phone/stats-dark.jpeg` | 主题一致性 |
| 8 | 使用记录-暗 | `phone/records-dark.jpeg` | 主题一致性 |
| 9 | 设置-暗 | `phone/settings-dark.jpeg` | 主题一致性 |

#### PC/2in1（上传 4 张，横向 1920×1080，16:9）

| 上传序 | 页面 | 上传文件 |
| --- | --- | --- |
| 1 | 首页 | `pc/home-light.jpeg` |
| 2 | 统计 | `pc/stats-light.jpeg` |
| 3 | 使用记录 | `pc/records-light.jpeg` |
| 4 | 设置 | `pc/settings-light.jpeg` |

#### 平板

**不提供独立截图**：本机无 Tablet 系统镜像，`tablet/_degraded/` 的 2in1 窗口 4:3 图只用于布局验证，**不得上架**；v1.0 在 AGC 不勾选平板（平板由手机兼容分发，见 §2.2）。

### 5.3 目录与转换说明

```
harmonyos/docs/store-assets/screenshots/        # 原始截图（emu-verify 流水线产出）
├── phone/   <page>-<light|dark>.jpeg           # 9 张正式素材（1320×2856）
├── pc/      <page>-light.jpeg                  # 4 张正式素材（3120×2080）
├── tablet/_degraded/                           # 退化验证图（2000×1500），禁止上架
├── <device>/_degraded/                         # 其他退化/中间资产，禁止上架
└── smoke-*.jpeg                                # 运行时验证证据，不是商店素材

harmonyos/docs/release/screenshots-upload/      # 已转换的上传文件（AGC 规格）
├── phone/   9 × 1080×1920 JPEG（~140–210KB/张，远低于 5MB）
└── pc/      4 × 1920×1080 JPEG（~120–200KB/张）
```

> 转换规则：pad 模式（等比缩放 + 自动采样边缘底色补边，不裁剪界面内容）；手机原图 1320×2856（0.462）比 9:16 狭长，左右补边；PC 原图 3120×2080（3:2）比 16:9 高，左右补边。补边色自动取截图边缘色，亮/暗主题均自然融合。
> `smoke-*`、`_degraded/` 已被脚本自动排除（需要转换证据图时加 `--include-evidence`）。
> 截图数量：手机 9 张（AGC 3–10 张上限内）、PC 4 张（3–10 张内）；平板 0 张（不勾选平板）。

### 5.4 转换命令（可直接复制）

```bash
cd /Users/yizhiwang/Desktop/opencode/gousage/opencode-go-gauge

# 全部设备：等比缩放 + 自动采样边缘底色留边（推荐，不裁掉界面内容）
.venv/bin/python3 harmonyos/docs/release/tools/prep-screenshots.py --all

# 或仅手机，改用裁切模式（铺满、无留边，会裁掉上下部分状态栏/导航，谨慎）
.venv/bin/python3 harmonyos/docs/release/tools/prep-screenshots.py --device phone --mode crop

# 显式指定留边颜色（默认 auto 采样截图边缘色，亮色主题不会出现深色留边）
.venv/bin/python3 harmonyos/docs/release/tools/prep-screenshots.py --all --background "#FAFAFC"
```

工具行为说明：
- 自动**排除** `_degraded/` 子目录与 `smoke-*` 验证证据（避免误转成上架素材）；确需转换证据图时加 `--include-evidence`。
- pad 模式按截图边缘采样背景色补边，手机原图 1320×2856（比例 0.462）比 9:16（0.5625）更狭长，pad 会左右留边但**不丢内容**；crop 模式满幅但会裁掉上下（状态栏/底部导航），商店素材建议统一用 pad。
- ⚠️ **不要用 `snapshot_display -w 1080 -h 1920` 在拍摄端直接改分辨率**：该参数为非等比拉伸（实测横向拉宽约 21%，图标变形），必须原生分辨率拍摄后用本工具做等比缩放。

**截图内容红线（审核 Checklist 与审核指南要求）**

- 不得出现真实个人信息：真实账号名、邮箱、Key 名称、workspace 名、token 等（审核指南 1.19）；建议用示例账号/示例 Key 名称。
- 不得出现「注入模拟数据 (调试)」「清除模拟数据」等调试入口（debug 构建的 Settings 页会显示；release 构建本就没有，Lead 同时安排演示/截图模式下隐藏该分组）。
- 截图统一由模拟器流水线产出；演示数据为合成数据，不含真实账号/Key（审核指南 1.19：应用信息不得展示真实个人信息）。
- 不得出现 test/demo/beta 等测试字样。
- 截图须与应用实际功能一致，不得用宣传图/合成图冒充真实界面（宣传图见 §6，仅用于推广位，不作为介绍截图）。

### 5.5 宣传图（非上架截图）

| 文件 | 尺寸 | 用途 |
| --- | --- | --- |
| `release/assets/promo-2160x1080.png` | 2160×1080（16:9） | 官网/README/推广位横版 |
| `release/assets/promo-1080x2160.png` | 1080×2160（9:16） | 官网/推广位竖版 |

> 两张宣传图由 PIL 生成，仅含品牌 Logo、名称、一句话简介与仪表盘几何图形，**不含任何伪造 UI 截图**，因此不能作为「应用介绍截图」提交。

## 6. 图标资产（上传主推 `icon-1024.png`）

| 文件 | 尺寸 | 何时使用 |
| --- | --- | --- |
| `release/assets/icon-1024.png` | 1024×1024 | **主推**：品牌 Logo 版；包内图标已替换为**同源**品牌分层图标（`AppScope/resources/base/media/layered_image.json` + foreground/background），两者视觉一致，满足「商店图标 = 包内图标」要求（上架前仍建议比对一次桌面图标） |
| `release/assets/icon-216.png` | 216×216 | AGC 提示 216 尺寸时使用（与 1024 同源） |
| `release/assets/icon-512.png` | 512×512 | 备用（部分后台位会要求 512） |
| `release/assets/icon-1024-package-match.png` | 1024×1024 | **仅兜底**：若最终 HAP 仍使用旧的 512 占位图标（`scripts/gen_icons.py` 产物），用这张保证「与包内图标一致」；正常情况下不需要 |

规格：PNG ≤3MB、正方形（216×216 或 1024×1024 均可）。图标均由 `release/assets/generate-assets.py` 复现（源图：`assets/GoGauge.icns` 1024 品牌标识）。

**一致性要求**：AGC 审核会做「应用名称/图标一致性检测」——商店图标必须与安装后桌面图标一致。若包内图标最终未替换为品牌图标，请改传 `icon-1024-package-match.png`，不要混用。

## 7. 审核风险与代码侧待补（必须在上架前处理）

| # | 风险 | 依据 | 状态/处理 |
| --- | --- | --- | --- |
| 1 | 应用内隐私政策入口 | 审核指南 7.1：AGC 平台**及应用内部**均需提供可便捷查看的隐私政策链接 | ✅ 已实现：`pages/PrivacyPage`（正文 `common/legal/PrivacyText.ets`）；入口 = 欢迎页底部 + 设置 → 关于 → 隐私政策。上架前人工复核可点开 |
| 2 | 首次启动隐私政策弹窗与主动同意 | 审核 Checklist / 审核指南 7.5：未同意前不得收集个人信息；不得默认勾选，须有明确同意/拒绝 | ✅ 已实现：`Index.ets` 首启弹窗（拒绝/同意），同意写入 `AppPrefs`、可再次查看；未同意不进入 opencode.ai 登录。上架前复核拒绝路径 |
| 3 | 第三方账号登录未提供华为账号登录选项 | 审核指南 3.16：若应用支持第三方账号登录，需提供华为账号登录选项 | 产品决策不接入 Account Kit（需 AGC 应用与账号体系）；在 AGC 审核备注说明「本应用是 OpenCode Go 第三方客户端，无自有账号体系，登录即 OpenCode 官方授权」，并作为已知审核风险跟踪 |
| 4 | 包内图标与商店图标一致性 | 应用名称/图标一致性检测 | ✅ 已替换为品牌分层图标（`layered_image.json` + foreground/background，与 `icon-1024.png` 同源）；`icon-1024-package-match.png` 仅作图备兜底 |
| 5 | 审核需要登录，但应用依赖用户自己的 OpenCode 账号 | 审核信息要求提供测试账号 | **用户必须提供**一组可用 OpenCode Go 测试账号/密码；无法提供时提前准备 .mp4 自测文件 |
| 6 | AGC 隐私政策 URL 需自行托管 | 审核指南 7.1 | 用户自行托管（GitHub Pages/个人站点/静态存储，HTTPS 公网可访问），内容与应用内 `PrivacyPage` 一致 |
| 6 | 中国大陆发行需 APP 备案 + 手机应用版权证书 | 发布准备工作 / 审核 Checklist | 用户自行完成备案与软著/版权材料 |
| 7 | 应用名称「GoGauge」可能与其他开发者重名 | 创建应用规则 | 若提示占用，需更换名称（会连带影响包内 label、隐私政策、文案） |
| 8 | 详情页文案与截图不得出现未实现功能（GOAT/账户总览） | 审核 Checklist：应用介绍/截图须与实际功能相符 | 文案已排除；截图不要出现相关入口（当前代码也没有） |

## 8. 需用户自行提供/完成的信息清单

| # | 事项 | 说明 |
| --- | --- | --- |
| 1 | 华为开发者账号 + 实名认证 | 个人或企业；实名主体名称将写入隐私政策与版权信息 |
| 2 | AGC 创建应用（包名绑定） | 包名 `io.github.yphyphyph.gogauge`，创建后不可改 |
| 3 | 发布证书 `.cer` + 发布 Profile `.p7b` | 需 AGC 权限；发布证书有效期 3 年（实名开发者） |
| 4 | 签名密钥库 `.p12` 及密码 | 建议至少 8 位、两类以上字符；妥善备份，丢失无法更新已上架应用 |
| 5 | 隐私政策托管 URL | HTTPS 公网可访问；可用 GitHub Pages（需公开仓库）/自有域名/对象存储静态站。注意：应用内 `pages/PrivacyPage` 只能满足「应用内入口」，**AGC 仍要求独立的隐私政策 URL**，两者内容须一致 |
| 6 | 客服邮箱（及可选电话、官网） | 写进隐私政策与 AGC 联系方式 |
| 7 | 应用版权证书/代理证书（手机 + 中国大陆必选） | 软著证书等；JPG/PNG/BMP ≤15MB/张，最多 10 张 |
| 8 | APP 备案（工信部） | 接入商备案系统选择「鸿蒙」平台并填写包名；周期较长，尽早启动 |
| 9 | 审核测试账号（OpenCode Go）或自测视频 | 供华为审核人员登录验证；无测试账号时按 §3.10 提供自测文件 |
| 10 | 应用负责人姓名/手机号/邮箱（含短信验证） | 中国大陆开发者必填 |
| 11 | 开发者显示名称、版权行文案确认 | 当前建议 `© 2026 GoGauge (yphyphyph)`，可按主体调整 |
| 12 | 是否替换包内图标 + 最终 icon 选择 | 见 §6（品牌版 vs 包内一致版） |

## 9. 本地资源文件索引

| 文件 | 用途 |
| --- | --- |
| `app-intro-zh.md` / `app-intro-en.md` | 应用名称、一句话简介、长描述、分类/标签/年龄分级建议、版权信息 |
| `privacy-policy-zh.md` / `privacy-policy-en.md` | 隐私政策全文（与代码行为一致） |
| `release-notes-1.0.0.md` | 新版本特性（中英） |
| `permission-rationale.md` | INTERNET 权限用途、隐私标签/隐私声明要点、审核备注模板 |
| `assets/icon-*.png`、`assets/promo-*.png` | 图标与宣传图 |
| `tools/prep-screenshots.py` | 截图批量转换为 AGC 规格 |
| `../release-guide.md` | 从注册账号到提交审核的逐步指南（含签名两种路径） |
| `../agc-release-checklist.md` | 上架前核对清单 |
