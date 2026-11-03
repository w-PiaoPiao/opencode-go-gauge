# GoGauge HarmonyOS NEXT — OpenCode Go 用量仪表盘（鸿蒙版）

鸿蒙 NEXT 原生实现：**ArkTS + ArkUI（Stage 模型）**，单工程一多开发：

- **手机**：布局对标安卓版 —— 底部 Tab（首页/统计/记录/设置）、页头（标题 + 账号胶囊 + 刷新）、
  周期胶囊、配额卡、编辑式数据格、下拉刷新；
- **平板 / PC（2in1）**：布局对标桌面版 —— 顶部工具栏（品牌/同步摘要/主题/刷新/账号胶囊）、
  左侧图标导航、页头右侧周期胶囊、多列栅格、记录页表格；
- **鸿蒙独有适配**：一多断点（`Dimens.SHELL_WIDE_BREAKPOINT=600` 切桌面壳、
  内容栅格 840/1000 断点）、ArkUI 原生过渡动效（页面淡入上移、图标侧栏弹性高亮、
  配额进度条生长）、下拉刷新（`Refresh`）、2in1 窗口最小尺寸与系统栏配色、
  键盘快捷键（Ctrl+1..4 切页 / Ctrl+R、F5 刷新）、账号切换底部 Sheet、品牌分层图标与启动窗口。

> 解析器/格式化/SQL 与桌面版、安卓版 1:1 移植；若 opencode.ai 接口格式变化，
> 需同步修改三处（Python / Kotlin / ArkTS）。

## 当前状态（v1.0.0，可提审）

- 功能：登录闭环（内置 WebView 捕获会话 Cookie）、多账号、配额窗口、用量概览、
  Token 构成、模型排行/趋势、使用记录/会话分页、日历热力图、自动/全量同步、
  双主题、中英 i18n、按范围清理。
- 合规：**首次启动隐私政策弹窗**（同意/拒绝）、**应用内隐私政策页**（欢迎页 + 设置→关于入口）、
  仅申请 `ohos.permission.INTERNET`、无第三方统计/广告/SDK。
- 发布：release `.app`（App Pack）构建链路、品牌分层图标、上架材料与逐步发布指南齐备（见下文文档索引）。
- 未实现（勿按"三端功能一致"理解）：Command Code / GOAT provider、账户总览面板
  （两者依赖 provider 列/跨账号聚合，见 `data/db/AppDb.ets` 的 `SCHEMA_VERSION`/`migrate()`）。

## 快速开始

```bash
cd harmonyos

# 1) 构建调试 HAP（模拟器/真机侧载）
./scripts/build.sh hap
#   -> entry/build/default/outputs/default/entry-default-unsigned.hap

# 2) 单元测试（hypium，纯逻辑用例）
./scripts/build.sh test
#   -> Tests run: 35, Failure: 0, Error: 0, Pass: 35

# 3) 上架用 Release App Pack（.app）—— 需先在 DevEco 配好发布签名，或命令行：
node scripts/gen-signing-material.js --signing-dir <p12目录> \
  --store-password <p12密码> --key-password <key密码> --force
HAP_STORE_FILE=... HAP_KEY_ALIAS=... HAP_PROFILE_P7B=... HAP_SIGN_CER=... \
  HAP_SIGNING_PASSWORDS_JSON=... bash scripts/inject-signing.sh
./scripts/build.sh app
#   -> build/outputs/default/*.app
```

环境：DevEco Studio **6.1.1**（自带 SDK 6.1.1 / API 24）+ 自带 hvigor/node。
命令行构建脚本已自动探测 DevEco 路径，可用 `DEVECO_HOME/DEVECO_SDK_HOME/NODE_HOME` 覆盖。

> ⚠️ `assembleApp`（release）会把同路径的 `entry-default-unsigned.hap` 覆盖为 release 版；
> 之后若要调试包或演示模式截图，需重新执行 `./scripts/build.sh hap`。

## 模拟器运行时验证与截图流水线

DevEco 自带模拟器可完全用 CLI 驱动（启动 → 安装未签名 HAP → 启动 → 截图 → crash 检查）：

```bash
# 手机 / 2in1 实例（本机已部署 Pura 90、MateBook Pro）
bash scripts/emu/emu.sh start-phone
bash scripts/emu/emu.sh install
bash scripts/emu/emu.sh launch --ps demo 1 --ps lang zh --ps theme light --ps page home
bash scripts/emu/emu.sh shot phone/home-light     # -> docs/store-assets/screenshots/phone/
bash scripts/emu/emu.sh crash-check

# 商店截图批量流水线（手机 4 页×亮暗 + PC + 平板退化组）
bash scripts/emu/capture-store-shots.sh --all
```

- 详细环境矩阵/命令/证据/限制：[docs/runtime-verification.md](docs/runtime-verification.md)。
- 演示模式（`--ps demo 1`，仅 debug 构建）：注入 180 天合成用量 + 演示配额，
  自动视为已同意隐私政策、隐藏设置页调试工具，用于生成商店截图；release 构建不含此路径。

## 上架材料与发布指南

| 文档 | 内容 |
| --- | --- |
| [docs/release-guide.md](docs/release-guide.md) | **从零到 AppGallery 在架**逐步指南（账号/备案/版权 → 证书 Profile → 签名 → `.app` 构建 → 上传 → 审核 → 升级） |
| [docs/agc-release-checklist.md](docs/agc-release-checklist.md) | 上架检查清单（签名/素材规格/隐私合规/风险表/用户自备项） |
| [docs/release/README.md](docs/release/README.md) | 材料包索引、占位符清单、快速开始 |
| [docs/release/app-intro-zh.md](docs/release/app-intro-zh.md) / [app-intro-en.md](docs/release/app-intro-en.md) | AGC 可直接粘贴的应用介绍（一句话简介/长描述/分类标签/年龄分级） |
| [docs/release/privacy-policy-zh.md](docs/release/privacy-policy-zh.md) / [privacy-policy-en.md](docs/release/privacy-policy-en.md) | 隐私政策全文（与代码行为逐条对齐；提交前替换 `<待填>` 占位符） |
| [docs/release/appgallery-metadata.md](docs/release/appgallery-metadata.md) | AGC 后台逐字段填写表 + 截图/图标规格 + 风险与用户自备清单 |
| [docs/release/assets/](docs/release/assets/) | 商店图标 1024/512/216、宣传图、可复跑生成脚本 |
| [docs/store-assets/screenshots/](docs/store-assets/screenshots/) | 商店截图原图（手机/PC/平板，亮暗主题） |
| [docs/design-spec.md](docs/design-spec.md) | 设计契约（令牌/组件/断点/页面布局/鸿蒙适配/开发约束） |

发布前唯一需要用户侧完成的事项：华为开发者账号实名、发布证书/Profile、隐私政策托管 URL、
APP 备案 + 软著（大陆）、可用 OpenCode Go 审核测试账号等（见 checklist §11）。

## 技术栈

- 语言/框架：ArkTS（严格 TS）+ ArkUI（Stage 模型，V1 状态管理 `@State/@Prop/@Builder`）。
- 构建：hvigor 6.24.2（DevEco 内置）。
- 存储：`@ohos.data.relationalStore`（RDB 四表，schema v2，`(account_id, usg_id)` 复合主键）+ `preferences`。
- 网络：`@ohos.net.http`；登录：`@ohos.web.webview`；后台任务：`workScheduler`。
- 图表：全 ArkUI 原生实现（布局型柱状图/热力图 + Canvas 环形/折线/堆叠面积），零三方图表依赖。

## 目录结构

```
entry/src/main/ets/
├── entryability/EntryAbility.ets        # 窗口策略/系统栏/启动参数透传 + 后台同步注册
├── pages/                               # Index(欢迎+隐私门) / LoginPage / PrivacyPage
├── common/
│   ├── auth/Login.ets                   # 登录 URL 构造 + cookie 提取（auth.py 移植）
│   ├── dev/{LaunchParams,DemoSeed}.ets  # 调试启动参数 + 演示数据（仅 debug）
│   ├── legal/PrivacyText.ets            # 应用内隐私政策正文（中英）
│   ├── i18n/I18n.ets                    # 中英文案表
│   ├── store/AppPrefs.ets               # preferences（语言/主题/货币/隐私同意态）
│   └── model/Models.ets                 # 数据模型（对齐 Android data/model）
├── data/
│   ├── db/                              # RDB 四表 + DAO（对齐 db.py / Room）
│   ├── remote/                          # OpenCodeApi/解析器/汇率/更新检查
│   └── repository/                      # 同步引擎 + Dashboard 聚合
├── ui/
│   ├── theme/Theme.ets                  # 暖色设计令牌（对齐安卓 Color.kt）+
│   ├── components/{Cards,Charts}.ets    # 卡片/胶囊/数据格 + 原生图表
│   ├── AppRoot.ets                      # 一多主壳（手机底部 Tab / 宽屏桌面壳）
│   └── pages/{Home,Stats,Records,Settings}Page.ets
└── resources/                           # 分层图标/layered_image/UI 图标/衬线字体 rawfile
```

## 与桌面版/安卓版的平台差异（替代清单）

| 桌面/安卓能力 | 鸿蒙方案 |
| --- | --- |
| Windows 托盘 / macOS 菜单栏 | 无第三方托盘 API：关闭窗口=退出应用；同步由前台定时器 + 后台 WorkScheduler 保证 |
| 开机自启（autostart.py） | 暂无第三方自启 API，已知缺口 |
| 后台同步间隔 15 分钟（WorkManager） | WorkScheduler 重复任务最短 **20 分钟**；前台 1/5/15/30 分钟精确 |
| WebView2 cookie 读取 | ArkUI Web 组件 + `webview.WebCookieManager.fetchCookieSync` 轮询 |
| 电脑端一次性更新（updater.py） | 上架 AppGallery 后用应用市场版本升级能力 |

## 开发约束（重要，避免线上 jscrash）

1. **禁止把 `@Builder` 方法当参数传给 `@BuilderParam`**（如 `content: this.xxx`）：
   ArkUI 子组件会以自身 `this` 调用该 builder，导致父页面成员取不到（`xxx is not callable`）。
   统一用**尾随闭包**（编译期捕获父组件 this）：`GgCard({ title }) { this.contentBuilder() }`。
2. 组件 `@State` 不要命名为 `width`/`height`（与 CustomComponent 内置属性方法冲突）。
3. 所有颜色走 `Theme` 令牌，所有文案走 `I18n.t`；新增文案必须 ZH+EN 同步。
4. AppDb 结构变更必须递增 `SCHEMA_VERSION` 并补 `migrate()` 分支。

## 验证记录

- 构建：`./scripts/build.sh hap` BUILD SUCCESSFUL（debug HAP 2.0MB）；
  `./scripts/build.sh app` BUILD SUCCESSFUL（release App Pack）。
- 单测：**Tests run: 35, Failure: 0, Error: 0, Pass: 35**。
- 模拟器运行时：手机 `Pura 90`（6.1.1/API24）+ 2in1 `MateBook Pro` 安装/启动/四页渲染/
  截图/crash-check 全部通过（详见 docs/runtime-verification.md）。
- 商店截图：手机亮/暗、PC、平板退化组已产出（docs/store-assets/screenshots/）。
- 合规/运行回归：**release 包 A1-A6 全部 PASS**（首启隐私弹窗、拒绝不可绕过、demo 参数无效、无 demo 数据/调试 UI，证据 `docs/runtime-evidence/release-privacy/`）；debug 包 B1-B3 PASS（四页渲染、设置页切主题/语言后壳层与当前页即时刷新、autoSync 开关联动；外观切换会重置当前页滚动位置，已知代价）。
- 上架：证书/Profile 签发、AGC 上传与审核需用户账号侧完成（见发布指南）。

> 历史记录：早期 README 中的「21/21 单测」「模拟器镜像为空 / CLI 无法引导」等描述已过期，
> 以本文与 `docs/verification-summary.md`、`docs/runtime-verification.md` 为准。
