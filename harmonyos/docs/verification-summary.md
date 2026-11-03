# GoGauge HarmonyOS — 验证与交接总结 (M1–M6)

> 本文件汇总全部可自动验证的证据与剩余需 GUI/账号执行的交接步骤。

## 1. 已自动验证的证据

| 项 | 命令 | 结果 |
| --- | --- | --- |
| Debug 构建 | `./scripts/build.sh hap` (环境探测见脚本) | ✅ BUILD SUCCESSFUL → `entry/build/default/outputs/default/entry-default-unsigned.hap` |
| Release 构建 | `./hvigorw --mode module -p product=default assembleHap -p buildMode=release` | ✅ BUILD SUCCESSFUL (未混淆, 签名待注入) |
| 本地单元测试 | `./scripts/build.sh test`（= hvigorw test） | ✅ **Tests run: 35, Failure: 0, Error: 0, Pass: 35, Ignore: 0** (结果文件 `entry/.test/default/intermediates/test/coverage_data/test_result.txt`) |
| Release App Pack | `./scripts/build.sh app`（= hvigorw assembleApp -p buildMode=release） | ✅ BUILD SUCCESSFUL → `build/outputs/default/harmonyos-default-unsigned.app`（注入 AGC 签名材料后产出 signed，上架包为 `.app` 而非 HAP） |
| 四页运行渲染 | 模拟器 demo=1 冷启动：home/stats/records/settings | ✅ 四页均正常渲染无 jscrash（2026-11-03，debug HAP 22:32+；此前 @BuilderParam this 绑定问题已修，见 design-spec §2 警告） |
| 隐私合规 | 首启弹窗 + 欢迎页/设置页入口 + `pages/PrivacyPage` | ✅ release 包实测：清数据首启必弹窗、拒绝后登录再次弹窗、demo 启动参数无法绕过、同意态落盘；证据见 `docs/runtime-evidence/release-privacy/` |
| 签名注入脚本 | `HAP_* 环境变量 bash scripts/inject-signing.sh` | ✅ 冒烟通过 (hex 编码 `abc123456`→`616263313233343536`, 已还原配置) |
| 模拟器运行时验证 | `scripts/emu/emu.sh start-phone / install latest / launch / shot / crash-check`（详见 `docs/runtime-verification.md`） | ✅ 手机 `Pura 90` + 2in1 `MateBook Pro` 均通过：未签名 HAP 安装/启动/截图/crash 检查全链路可用（此前「CLI 无法引导模拟器」结论已作废） |
| release 隐私合规回归（A 阶段） | release HAP 冷启动/隐私弹窗/拒绝与同意流程/demo 参数绕过尝试/crash-check | ✅ 8/8 PASS：首启弹窗、拒绝不可绕过、同意前不落盘、release 下 demo/lang/theme/page 参数全部失效、无 demo 数据、登录页无崩溃；证据 `docs/runtime-evidence/release-privacy/`（§10.1） |
| debug demo + 壳层即时刷新回归（B 阶段） | 23:46/23:52/00:02/00:08 debug HAP：四页 demo 渲染、P1 主题语言即时刷新、autoSync 开关、crash-check | ✅ 最终 00:08 HAP 全部 PASS：四页渲染无 crash/无调试 UI；P1 三项断言 a/b/c 通过（当前页立即英文+深色、Tab 英文+深色、跨 tab 正确，无需重启；代价：外观切换滚动位置重置）；autoSync 关闭取消 WorkScheduler 且无 GoGaugeSync 日志；crash-check PASS（§10.2） |
| Git 卫生 | `git ls-files` | ✅ 56 个 harmonyos 文件入库, 无 oh_modules/.test/构建产物混入 |
| 工程对账 | M1–M6 里程碑 | 代码/材料/CI 全部落库 (见本文件 §3) |

单元测试覆盖: QuotaParser(4) / UsageParser(3) / Fmt(7) / 活跃账号策略(7)。

> 活跃账号策略的 7 个用例此前在测试文件内**复制了一份 resolveActive 实现**，
> 生产逻辑漂移时测试仍会通过。现已改为直接调用生产代码
> `SyncDao.resolveActive`（该静态方法为此改为公开），这 7 个用例因此首次真正
> 覆盖了发布逻辑。

## 1.1 尚未实现的能力 (勿按"功能一致"理解)

- **Command Code / GOAT provider** —— 无 `provider` 列、无 `usage_charts` 聚合表，
  登录域名与 cookie 名硬编码为 opencode。桌面/安卓均已支持。
- **账户总览面板** —— 跨账号聚合 KPI 与 7 日趋势对比。
- **`loginMode === 'add'` 的账号去重** —— 依赖 `token_fp` 列，鸿蒙 schema 无此列。

上述任一项落地时，必须同时递增 `AppDb.SCHEMA_VERSION` 并补 `migrate()` 分支。

## 2. 运行验证 (模拟器 CLI 已完全跑通；真机/上架需 GUI + 华为账号)

> ✅ **此前「CLI 无法引导模拟器」的结论已作废（2026-11-03 实测推翻）。**
> DevEco 自带模拟器可完全由 CLI 驱动：启动 → `hdc install` 未签名 HAP → `aa start`
> → `snapshot_display` 截图 → hilog/faultlogger crash 检查。详见
> [`runtime-verification.md`](runtime-verification.md)（环境矩阵/命令/证据/限制/截图流水线）。

**模拟器（已实测通过）**
- 设备矩阵：`Pura 90`(phone, HarmonyOS 6.1.1/API24, 1320×2856, density 560)、
  `MateBook Pro`(2in1, 6.1.1/API24, 3120×2080, density 304)；
  `Huawei_Phone`(5.0.1/API13) 不满足 API24，不可用。
- 工具链：`/Applications/DevEco-Studio.app/Contents/tools/emulator/Emulator`（GUI 进程，勿 kill）+
  `.../sdk/default/openharmony/toolchains/hdc`（Ver 3.2.0d）。
- 一键脚本（本次新增，全部实测）：
  - `scripts/emu/emu.sh` — `list / start-phone / start-2in1 / start-tablet / stop / wait /
    install / launch / stop-app / shot / unlock / logs / crash-check / build / create-tablet /
    dump-ui / tap / swipe / drag / key`；自动发现 hdc target（端口会漂移）、mkdir 设备锁、
    启动后按 `bootevent.boot.completed` + WindowManager 桌面窗口 + snapshot 探针判定就绪并自动解锁。
  - `scripts/emu/capture-store-shots.sh` — 商店截图流水线（页面 × 亮/暗、页面去重校验、
    PC 窗口最大化、平板缺失时 2in1 4:3 退化并标记 DEGRADED）。
  - `scripts/emu/uitools.py` — UI 树解析（文本坐标/窗口 bounds/最大化与缩放拖拽坐标）。
- 实测结果（最终 HAP 2026-11-03 22:53，debug 构建）：
  - 未签名 HAP 可直接 `hdc install -r` 到模拟器并 `aa start` 启动（手机、2in1 均成功）。
  - 调试参数全部生效：`--ps demo 1 --ps lang zh --ps theme light --ps page <home|stats|records|settings>`
    （EntryAbility → LaunchParams → Index/AppRoot；demo 模式 seed 180 天 ~1.1 万条演示数据、
    账号名 OpenCode Go、设置页调试分组自动隐藏）。
  - 四页（home/stats/records/settings）在 demo 模式下均正常渲染，逐页启动 6s 进程存活、无 crash；
    `crash-check`（hilog + faultlogger + 进程存活）PASS。
  - 登录页回归通过：点击「立即登录」→ WebView 正常加载 opencode.ai 登录页，不再触发此前的
    `LoginPage.ets:27 TypeError`（已修）。
  - **商店截图已产出**：手机 9 张（home/stats/stats-scrolled/records/settings × light + 4 张 dark）、
    PC 4 张（最大化窗口）→ `docs/store-assets/screenshots/{phone,pc}/`，
    清单 `docs/store-assets/screenshot-manifest.md`（由 `release-materials` 的
    `prep-screenshots.py` 转为 AGC 规格 1080×1920 / 1920×1080）。
  - 运行验证期间发现并修复的问题（登录页 jscrash / DemoSeed 占位账号 / GgCard `@BuilderParam`
    this 绑定 / 图表轴标签等）记录在 `runtime-verification.md` §2.3。
- 限制：未签名 HAP 仅模拟器可用；模拟器 GUI 会显示在宿主屏幕；16GB 内存需单实例串行；
  hdc 端口会变化（脚本自动发现）；本机**无 Tablet 镜像**（`Emulator -create -deviceType Tablet`
  报 `Cannot find image`），平板用 2in1 窗口 4:3 作布局替代验证。**v1.0 AGC 建议只上传
  手机+PC 截图、平板不提供独立素材**（见 `runtime-verification.md` §9）。

**真机** (鸿蒙 NEXT PC / 手机)
- 签名后 `./scripts/install.sh` (hdc install + aa start + 截图)
- 签名链路: AGC 签发证书 → `HAP_STORE_FILE=… HAP_STORE_PASSWORD=… HAP_KEY_ALIAS=… HAP_KEY_PASSWORD=… HAP_PROFILE_P7B=… HAP_SIGN_CER=… bash scripts/inject-signing.sh` → rebuild → install

## 3. 里程碑对账 (已落库)

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M1 | 脚手架 + Web 登录闭环 (Web 组件 + fetchCookieSync) | ✅ 提交 9369657 |
| M2 | RDB 四表 + API/解析器 + 多账号同步引擎 | ✅ 提交 e518986/eff1072 |
| M3 | 首页/统计/记录 + 原生图表 + 一多自适应主壳 | ✅ 提交 3b46433 |
| M4 | 设置页/多账号/双主题/中英 i18n | ✅ 提交 4c6079a |
| M5 | PC/2in1 窗口策略 + 前台定时同步 + WorkScheduler | ✅ 提交 5a1329a |
| M6 | 上架材料（docs/release/**）· 发布指南 · 单测 35/35 · 商店截图 · `.app` 构建链路 · CI 模板 | ✅ 代码/材料/运行验证完成；证书签发、AGC 上传与审核为账号侧操作（见 docs/release-guide.md） |

## 4. 关键产物路径

- 工程根: `harmonyos/`
- HAP: `harmonyos/entry/build/default/outputs/default/entry-default-unsigned.hap`
- 单测: `harmonyos/entry/src/test/` (结果 `entry/.test/default/intermediates/test/coverage_data/test_result.txt`)
- 上架清单: `harmonyos/docs/agc-release-checklist.md`
- 运行时验证报告: `harmonyos/docs/runtime-verification.md`（环境矩阵/命令/证据/限制/截图流水线）
- 模拟器与截图工具: `harmonyos/scripts/emu/{emu.sh,capture-store-shots.sh,uitools.py}`
- 商店截图: `harmonyos/docs/store-assets/screenshots/{phone,pc,tablet}/`
- 工具: `harmonyos/scripts/{build.sh,install.sh,inject-signing.sh,gen_icons.py}`
- CI: `.github/workflows/release-harmonyos.yml` (tag `v*-harmony`)