# GoGauge HarmonyOS — 模拟器运行时验证（环境 / 命令 / 证据 / 限制）

> 最后更新：2026-11-03 23:10（Asia/Shanghai）
> 最终验证 HAP：`entry-default-unsigned.hap`（2026-11-03 22:53，2,059,501 bytes，
> `BuildProfile: BUILD_MODE_NAME=debug / DEBUG=true`）
> 结论：DevEco Studio 自带 HarmonyOS 模拟器**可以完全用 CLI 驱动**完成
> 「启动 → 安装未签名 HAP → 启动应用 → 截图 → 解锁 → hilog/faultlogger 检查」全链路。
> 手机（Pura 90）与 2in1（MateBook Pro）均实测通过，并产出 **13 张正式商店截图**
> （手机 9 + PC 4，见 `docs/store-assets/screenshot-manifest.md`）与 4 张平板退化验证图。
> 平板（Tablet）因本机无系统镜像，只能用 2in1 窗口 4:3 做布局替代验证 → **v1.0 AGC
> 建议只上传手机+PC 截图，平板不提供独立素材**（详见 §9）。

相关脚本（均在 `harmonyos/scripts/emu/`，本次新增）：

| 文件 | 作用 |
| --- | --- |
| `emu.sh` | 模拟器/设备/应用/截图/日志/crash 检查统一 CLI（自动发现 hdc target、mkdir 设备锁、UI 自动化命令） |
| `capture-store-shots.sh` | 商店截图流水线：按设备形态 × 页面 × 亮/暗批量截图 + 页面去重校验 + 清单生成 |
| `uitools.py` | 解析 `uitest dumpLayout` 的 UI 树（文本坐标、窗口 bounds、最大化/缩放拖拽坐标） |

---

## 1. 环境矩阵（实测）

| 形态 | 实例名 | deviceType | OS / API | 分辨率(px) | density | host hdc target | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 手机 | `Pura 90` | phone | HarmonyOS 6.1.1(24) | 1320×2856（竖屏 377×816vp） | 560 | `127.0.0.1:5557` | ✅ 通过（9 张正式截图） |
| PC / 2in1 | `MateBook Pro` | 2in1 | HarmonyOS 6.1.1(24) | 3120×2080（横屏 1642×1095vp） | 304 | `127.0.0.1:5557`（重启后端口可能变化） | ✅ 通过（4 张正式截图） |
| 平板 | `GoGauge_Tablet`（未创建） | Tablet | HarmonyOS 6.1.1(24) | — | — | — | ❌ 本机无 Tablet 系统镜像（`Cannot find image`） |
| 旧手机 | `Huawei_Phone` | phone | HarmonyOS 5.0.1(13) | — | — | — | ❌ API 13 < 应用要求 API 24，不可用 |

工具链版本（实测）：

| 组件 | 路径 | 版本 |
| --- | --- | --- |
| DevEco Studio | `/Applications/DevEco-Studio.app` | — |
| SDK | `/Applications/DevEco-Studio.app/Contents/sdk` | 6.1.1（compileSdk 6.1.1.125） |
| Emulator | `.../Contents/tools/emulator/Emulator` | HarmonyOS Emulator 6.1.1.200 |
| hdc | `.../Contents/sdk/default/openharmony/toolchains/hdc` | Ver 3.2.0d |
| 设备侧系统 | — | `emulator 6.1.0.125(SP9DEVC00E120R4P11)` / `OpenHarmony-6.1.1.125` |
| 应用 | `entry-default-unsigned.hap` | 1.0.0 (versionCode 1000000)，debug 构建 |

镜像目录（`~/Library/Huawei/Sdk/system-image/`）实际内容：

```
HarmonyOS-6.1.1/phone_all_arm   ✅ 已下载
HarmonyOS-6.1.1/pc_all_arm      ✅ 已下载
HarmonyOS-5.0.1/phone_arm       ✅ 已下载（API13，不可用）
HarmonyOS-7.0.0-B1/*            ⚠️ 未部署成功（忽略）
（无 tablet / wear 等镜像）
```

---

## 2. 最终结果速览

### 2.1 商店截图产物（`docs/store-assets/screenshots/`）

清单（唯一依据）：[`docs/store-assets/screenshot-manifest.md`](../store-assets/screenshot-manifest.md)

| 形态 | 数量 | 文件 | 分辨率 |
| --- | --- | --- | --- |
| 手机 light | 5 | `home-light` `stats-light` `stats-scrolled-light` `records-light` `settings-light` | 1320×2856 |
| 手机 dark | 4 | `home-dark` `stats-dark` `records-dark` `settings-dark` | 1320×2856 |
| PC (2in1 最大化) | 4 | `home-light` `stats-light` `records-light` `settings-light` | 3120×2080 |
| 平板（退化，不可上架） | 4 | `tablet/_degraded/*-light.jpeg` | 2000×1500（窗口裁剪） |

- 所有正式素材均通过流水线校验：**页面截图去重通过**（证明 `--ps page` 生效）、
  **设置页无调试 UI 文本**（`SHOW_DEBUG_TOOLS` 在 demo 模式下隐藏）。
- `phone/smoke-*.jpeg`、`tablet/_degraded/` 为运行时验证/退化证据，**不是上架素材**。

### 2.2 运行时验证结论

| 验证项 | 结果 |
| --- | --- |
| 未签名 HAP 安装（`hdc install -r`） | ✅ 手机/2in1 均成功（模拟器接受未签名 HAP） |
| 应用启动（`aa start`）与 demo 调试参数 | ✅ `--ps demo 1 --ps lang zh --ps theme light --ps page home/stats/records/settings` 全部生效 |
| 四页渲染（demo 数据 180 天 seed） | ✅ home/stats/records/settings 均正常渲染，无 crash（最终 HAP 逐页启动 6s 后进程存活） |
| 登录页（点击「立即登录」） | ✅ jscrash 已修复：进入「连接 OpenCode Go」页 + WebView 正常加载 opencode.ai 登录页 |
| crash-check（hilog + faultlogger + 进程存活） | ✅ PASS，无 FATAL、无 faultlogger 新增应用故障文件 |
| 设置页调试入口 | ✅ demo 模式下隐藏，无「注入模拟数据/调试」文本 |
| 商店截图流水线 | ✅ 13 张正式素材 + manifest；`--clean-data` 保证账号名 OpenCode Go / 180 天数据完整 |

### 2.3 运行验证中发现并已修复的问题（时间线）

| 版本 | 问题（运行时验证发现） | 修复 |
| --- | --- | --- |
| 旧 HAP（M6） | 点击「立即登录」JS 崩溃：`LoginPage.ets:27 TypeError: Cannot load property of null or undefined`（`router.getParams()` 返回 undefined 却按 null 判断） | Lead 重写 `LoginPage.aboutToAppear`（改 optional/undefined 判断） |
| 22:14 首版新 UI | demo=1 停在欢迎页：`AppDb.seed()` 总会插入 token 为空的占位账号，导致 `DemoSeed.run()` 走 `switchAccount` 分支、从不写 demo token | `DemoSeed.run()` 增加 `!hasLogged` 分支：给占位账号写 token |
| 22:25 debug | HomePage/StatsPage/SettingsPage/RecordsPage 渲染即崩（`overviewCells is not callable`、`Cannot read property length of undefined` 等）：页面成员 `@Builder` 作为 `GgCard` 的 `@BuilderParam` 传入后 `this` 指向子组件 | GgCard 改为单一 `content` 尾随闭包，全部调用点改闭包（20 处） |
| 22:36 | 视觉问题（刷新图标空白 / 概览文案截断 / 账号名 Default / 重置文案 / Token 构成与 KPI 不一致 / 同步开关状态） | Lead 逐项修复 |
| 22:44 | 统计页 X 轴 30 个标签逐字换行（`10/20` 被挤成三行） | 22:53 改为「首/中/尾 3 标签 SpaceBetween」 |
| 22:44（2in1 窗口缩放） | 窗口 1280→2000px 时 `EditorialGrid` 列数 3→6，旧行残留 → 用量概览 9 格（`dumpLayout` 中 总请求/总费用/会话数 各 2 节点）；等待/滚动/二次缩放均不消失，切 tab 重建页面才清除。**调研结论：ArkUI ForEach 差异更新在行数减少时残留子节点** | 截图流水线 workaround：缩放后切 tab 强制重建页面再截图（`force_page_rerender`）；建议源码把 `EditorialGrid` 的 ForEach key 改为包含 `columns`（如 `row_${this.columns}_${ri}`）彻底修复（不影响本次素材） |

---

## 3. 模拟器 CLI（宿主侧）

```bash
EMU=/Applications/DevEco-Studio.app/Contents/tools/emulator/Emulator
HDC=/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc

"$EMU" -list -details                    # 实例列表（JSON：isRunning / osVersion / 分辨率 / imageSubPath）
"$EMU" -start "Pura 90" -instancePath "$HOME/.Huawei/Emulator/deployed" -imageRoot "$HOME/Library/Huawei/Sdk" &
"$EMU" -stop "Pura 90"                   # 正常关闭（等价于关 GUI 窗口）
"$EMU" -imageList -deviceType Tablet     # 查看可用镜像（downloaded=true/false）
```

实例配置在 `~/.Huawei/Emulator/deployed/<name>/config.ini`（分辨率/density/imageSubPath 等）。

- **内存约束**：16GB 宿主同时只跑一台模拟器；切换设备必须先 stop 再 start（`emu.sh start-*` 自动处理）。
- **模拟器是 GUI 进程**：会出现在宿主屏幕，**不要 kill**（用 `Emulator -stop`），否则 userdata 可能损坏。

---

## 4. boot 就绪判据（`emu.sh wait` 采用，实测可靠）

1. **hdc target 出现**：`hdc list targets` 有 `127.0.0.1:<port>`，且
   `hdc -t <target> shell "echo gogauge-shell-ok"` 有返回；
2. **系统 boot 完成**：`param get bootevent.boot.completed` → `true`
   （`sys.boot.completed` / `bootevent.bootanim.exit` 不存在，返回 errNum 1002/106）；
3. **窗口服务/桌面就绪**：`hidumper -s WindowManagerService -a '-a'` 含 `ScreenGroup` 且含
   `SCBDesktop/SCBWallpaper/Launcher`；
4. **合成器可出帧**：`snapshot_display -f /data/local/tmp/probe.jpeg` 返回 success。

`emu.sh wait` / `start-*` 在 ready 后自动解锁屏幕。

---

## 5. 解锁（锁屏 → 桌面）

判据：`hdc shell "hidumper -s ScreenlockService -a '-all'"` 中 `screenLocked false`（已解锁）。

```bash
# 主方案：uinput 触摸上滑（h*85% -> h*40%，平滑 500ms）
hdc shell "uinput -T -m 660 2427 660 1142 600 500"
# 兜底：uitest 手势（本机多次实测由它解锁成功）
hdc shell "uitest uiInput swipe 660 2427 660 1142 800"
```

`emu.sh unlock` 幂等：已解锁直接跳过；锁定则先 uinput 再 uitest 兜底。

---

## 6. 安装 / 启动 / 停止应用（模拟器接受未签名 HAP）

```bash
HAP=harmonyos/entry/build/default/outputs/default/entry-default-unsigned.hap
hdc install -r "$HAP"                                     # 成功输出 msg:install bundle successfully.
hdc shell "aa start -a EntryAbility -b io.github.yphyphyph.gogauge --ps demo 1 --ps lang zh --ps theme light --ps page home"
hdc shell "aa force-stop io.github.yphyphyph.gogauge"
hdc shell "pidof io.github.yphyphyph.gogauge"             # 进程存活验证
```

⚠️ **`--ps` 语法（易错）**：`--ps <key> <value>` 是**两个独立 token**；
`--ps demo=1` 会被 aa 拒绝（`invalid number of parameters for option --ps`）。

最终约定调试参数（EntryAbility 写入 `LaunchParams`，Index/AppRoot 消费）：

| key | 值 | 语义 |
| --- | --- | --- |
| `demo` | `1` | 演示模式：seed demo 账号（OpenCode Go）+ 180 天用量（~1.1 万条）+ 配额窗口 + 30 天趋势；仅 debug 构建生效 |
| `lang` | `zh` / `en` | 强制语言 |
| `theme` | `light` / `dark` | 强制主题 |
| `page` | `home` / `stats` / `records` / `settings` | 初始 tab |

> 注意：`hdc install -r` **不会清沙箱数据**。旧数据里若已有可用账号，DemoSeed 会走
> `switchAccount` 分支、不重新 seed，账号名/数据可能是旧的。**演示截图前用
> `emu.sh reset-app`（`bm clean -n <bundle> -d -c`）清数据**，再冷启动让 DemoSeed 从零 seed。

---

## 7. 截图

```bash
hdc shell "snapshot_display -f /data/local/tmp/shot.jpeg"   # 设备侧合成（返回 success 即成功）
hdc file recv /data/local/tmp/shot.jpeg /tmp/shot.jpeg      # 回传
hdc shell "uitest screenCap -p /data/local/tmp/ui.jpeg"     # 备选（uitest 自带）
```

- `snapshot_display` 实测输出：手机 1320×2856、2in1 3120×2080（jpeg）。
- ⚠️ `snapshot_display -w 1080 -h 1920` 虽能直接输出指定尺寸，但**非等比拉伸会变形**
  （实测图标 w/h 0.98→1.19，横向拉宽约 21%），**不要**用于商店图；尺寸转换交给
  release-materials 的 `prep-screenshots.py`（等比缩放+品牌底色 pad）。
- 默认输出目录：`docs/store-assets/screenshots/<phone|pc|tablet>/`（`emu.sh shot` 自动创建）。

---

## 8. UI 自动化（uitest）与 2in1 窗口控制

```bash
hdc shell "uitest dumpLayout -p /data/local/tmp/layout.json"    # UI 树 JSON
hdc shell "uitest uiInput click 660 1840"
hdc shell "uitest uiInput swipe 660 2400 660 800 600"
hdc shell "uitest uiInput drag 1791 1117 2511 1777 800"         # 拖拽（改窗口大小）
hdc shell "uitest uiInput keyEvent Back|Home|Power"
```

`emu.sh dump-ui / tap / swipe / drag / key` 是上述命令的封装（含设备锁与 target 自动发现）；
`uitools.py` 提供 `texts / find / center / window / maximized / titlebar-buttons / drag-plan` 等解析。

### 2in1 窗口尺寸（实测方法）

| 方式 | 结果 |
| --- | --- |
| `aa start --wl <x> --wt <y>` | ✅ 可移动窗口位置 |
| `aa start --ww <w> --wh <h>` | ❌ 被忽略（窗口保持 1280×840） |
| 点标题栏最左按钮（窗口控制 maximize） | ✅ 最大化 3120×1955（扣任务栏）；再点一次恢复 1280×840 |
| `uitest uiInput drag` 拖窗口右下角 | ✅ 任意缩放（实测 1280×840 → 2000×1500） |
| ⚠️ 缩放后立即截图 | ❌ 可能残留旧布局（EditorialGrid 9 格 bug，见 §2.3）→ 需切 tab 强制重建页面 |

`capture-store-shots.sh` 已封装 PC 最大化、平板退化 4:3 缩放 + 页面重建 + `sips` 窗口裁剪。

---

## 9. 平板（Tablet）：镜像缺失、替代验证与 AGC 结论

创建平板实例（未下载任何镜像）：

```bash
"$EMU" -create "GoGauge_Tablet" -deviceType Tablet -osVersion "HarmonyOS 6.1.1(24)" \
  -instancePath "$HOME/.Huawei/Emulator/deployed" -imageRoot "$HOME/Library/Huawei/Sdk"
# 实际输出：
# Cannot find image, please verify your SDK installation.
# Device create fail.
```

`-imageList -deviceType Tablet` 显示 6.1.1(24) `downloaded=false`（任务约束：不下载大镜像）。

**替代验证（已实测）**：2in1（MateBook Pro）窗口拉成 **2000×1500 ≈ 4:3**
（density 304 → 1053vp 宽，满足 ArkUI `lg` 断点 >840vp），`sips` 裁剪窗口区域，
产出 `tablet/_degraded/` 4 张，标注 DEGRADED（README 说明「非真实平板产物，不得上架」）。

**AGC 结论（v1.0）**：**只上传手机 + PC 截图，平板不提供独立素材**。
- 本机无 Tablet 镜像，退化图是 PC 宽屏布局而非真实平板 UI，不能冒充；
- 包内已声明 tablet（`deviceType: phone/tablet/2in1`），lg 断点布局已通过 2in1 全屏/4:3 窗口验证；
- 若 AGC 强制要求平板图，只能用 2in1 4:3 转 1920×1280 后人工复核并注明（不推荐）。

---

## 10. 日志与 crash 检查

```bash
hdc shell "hilog -r"                              # 清空缓冲区
hdc shell "hilog -x"                              # 非阻塞导出
hdc shell "hilog -x -L E,F"                       # 只看 ERROR/FATAL
hdc shell "ls -1t /data/log/faultlog/faultlogger" # 系统/JS 崩溃记录（可拉取）
hdc file recv /data/log/faultlog/faultlogger/<file>.log /tmp/crash.log
```

`emu.sh crash-check` 判据：① 进程存活；② hilog 无本应用相关 FATAL/cppcrash/jscrash/SIGSEGV/SIGABRT；
③ faultlogger 无本应用新增故障文件。

**最终结果（22:53 HAP）**：
- 逐页启动（demo=1，page=home/stats/records/settings）：进程均存活（6s 检查点），faultlogger 无新增；
- `./emu.sh crash-check --wait 10` → **PASS**（`/tmp/gogauge-crashcheck-20261103-230825.log`）；
- 登录页回归：点击「立即登录」→ 显示「连接 OpenCode Go / 正在加载授权页…」+ WebView 加载
  `opencode.ai/console/login` 页面（Continue with Google/GitHub/email），进程存活、无 jscrash。

---

## 10.1 release 包安全/合规回归（A 阶段，实测）

> 验证对象：release 构建 HAP（23:11 产物，1.24MB，`BUILD_MODE_NAME=release`/`DEBUG=false`）。
> 注意：`./scripts/build.sh app` 生成的 release HAP 会被后续 debug 构建覆盖（同路径），
> 本次从 `build/outputs/default/harmonyos-default-unsigned.app` 解包出的
> `entry-default.hap` 作为 release 验证对象；解包件保存在 `/tmp/appx/entry-default.hap`。

| 步骤 | 操作 | 结果 |
| --- | --- | --- |
| A1 | uninstall → install release HAP → 冷启动（无 `--ps` 参数） | ✅ 首启弹隐私政策弹窗（含「查看《隐私政策》/不同意/同意并继续」）；欢迎页无「演示模式」按钮（确认 release）；prefs 未创建；DB `usage_records=0` |
| A2 | 弹窗内点「查看《隐私政策》」→ Back | ✅ 隐私页正常展示完整政策；Back 回欢迎页，链接可再点（弹窗不自动重现） |
| A3 | 点「不同意」→ 再点「立即登录」 | ✅ 不同意后停欢迎页；再点登录**再次弹隐私弹窗**（不可绕过）；prefs 仍未创建 |
| A4 | 点「同意并继续」→「立即登录」 | ✅ 进欢迎页（未登录、非主界面、无 demo 数据）；`privacy_accepted=1` 落盘；登录页 WebView 正常加载 OpenCode 登录页，无 jscrash |
| A5 | 未同意时 force-stop → 带 `--ps demo 1 --ps lang zh --ps theme light --ps page home` 冷启动 | ✅ **调试参数不能绕过隐私**：仍先弹隐私弹窗、prefs 未创建、不进主界面、无 demo seed（`usage_records=0`、accounts 仅占位行） |
| A5-2 | 再次 force-stop + demo 参数冷启动 | ✅ 仍弹隐私弹窗，参数依旧无效 |
| A5-3 | release 下 `--ps lang en --ps theme dark` | ✅ 完全无效：prefs 未创建（无 language/dark_mode），UI 仍中文亮色 |
| A6 | `emu.sh crash-check --wait 10`（无参数） | ✅ PASS：进程存活、hilog 无 FATAL/崩溃关键字、faultlogger 无新增 |

证据截图（`docs/store-assets/screenshots/phone/`）：
`smoke-release-A1-first-launch-privacy.jpeg`、`smoke-release-A2-privacy-page.jpeg`、
`smoke-release-A2-back-welcome.jpeg`、`smoke-release-A3-declined-welcome.jpeg`、
`smoke-release-A3-login-reprompt.jpeg`、`smoke-release-A4-agreed-welcome.jpeg`、
`smoke-release-A4-login-webview.jpeg`、`smoke-release-A5-demo-params.jpeg`、
`smoke-release-A5-lang-theme-params.jpeg`；hilog 快照 `/tmp/release-A-hilog.log`、
`/tmp/gogauge-crashcheck-20261103-232437.log`。

**结论**：release 包隐私合规行为符合预期（首启弹窗、拒绝不可绕过、同意前不落盘、
release 下 demo/lang/theme/page 调试参数全部失效、无 demo 数据与调试 UI、登录页无崩溃）。

---

## 10.2 debug 包 demo / 壳层即时刷新 / 后台同步回归（B 阶段，最终 00:08 HAP）

> 验证对象：debug HAP（最终 00:08，2.0MB，`BUILD_MODE_NAME=debug`/`DEBUG=true`；B1/B3 于 23:36 版验证，B2 于 00:08 版修复后复测）。
> 环境：`bm uninstall` → `install` → `emu.sh reset-app`（clean-data）后执行。

| 项 | 操作 | 结果 |
| --- | --- | --- |
| B1 四页渲染 | clean-data 后 `--ps demo 1 --ps lang zh --ps theme light --ps page home/stats/records/settings` 各冷启一次 | ✅ 四页均正常渲染、进程存活、无 crash；设置页无调试 UI 文本（zh/en 各查一遍） |
| B2 P1 壳层即时刷新 | 设置页切「深色 + English」→ 不重启切首页/设置页 | ✅ **PASS（00:08 HAP 最终版）**：当前设置页 3s 内立即英文+深色（内容像素 (31,30,26)）；切首页后 Tab 文本 `Home/Stats/Records/Settings`、Tab 栏像素 (36,35,31) 深色；依次切 4 tab 均正确；pid 不变（无重启）。已知代价：remount 方案会使当前页滚动位置重置到顶部 |
| B3 后台同步联动 | 关闭「自动增量同步」→ 冷启动 → 观察日志 | ✅ `WORK_SCHEDULER: StopAndCancelWork workId:1001`；冷启动日志 `background sync applied: false`；30s 观察窗 `GoGaugeSync` = 0 行；重新开启后 `AddWork/StartWork` + `applied: true` |
| B4 配额卡下拉刷新（可选） | demo 配额固定值下拉刷新 | N/A（固定 seed 值下进度条宽度无可观测变化）；下拉刷新无 crash/异常 |
| crash-check | `emu.sh crash-check --wait 10` | ✅ PASS（hilog 无 FATAL，faultlogger 无新增） |

**B2 根因（23:46 迭代后精确版，供继续修复）**：
1. `AppRoot.ets` 的 `@StorageLink('ggChromeToken') chromeToken` 最初只在方法中自增、build 未读取
   → 23:46 已在两处 Tab ForEach 的 key 中读取（`` `${item.key}_${this.chromeToken}` ``），
   **Tab 文案因此修复**；
2. **Tab 栏容器背景仍未刷新**：`Row.backgroundColor(Theme.surface())`、`Divider.color`、
   sideRail/topBar 背景等属性不读取 chromeToken → ArkUI 只重建 ForEach 子项、不重算父容器属性。
   建议颜色改用读取 chromeToken 的 helper，或把 bottomBar/sideRail/topBar 抽成 @Component 并以
   chromeToken 作 @Prop（prop 变化整组件重建）；
3. **设置页自身内容不刷新（最终已修复）**：多轮验证确认 ArkUI 状态只绑定到读取它的节点
   （隐藏 Text / @StorageLink 局部读取 / 同构 if-else 分支均不足以整页 remount）；
   00:08 版改用 `pageSlot()` 的 `ForEach([this.chromeToken], …, (t) => `page_${t}`)`
   以 key 变化强制销毁重建页面子树，并把 chromeToken 收敛为普通 @State、单通道
   `onAppearanceChanged` 递增（避免净 +2），最终 PASS。代价：外观切换后当前页滚动位置重置。
   额外观察：安装后首次冷启动偶发 1 次系统 `sysfreeze … LIFECYCLE_TIMEOUT`
   （模拟器负载/连续安装噪声，重试未复现、无业务崩溃），不阻塞验收。
冷启动对照已证明 i18n/Theme 令牌本身正确（冷启动后 Tab 英文+深色、页面英文+深色）。

证据截图（`docs/store-assets/screenshots/phone/`）：
`smoke-B1-{home,stats,records,settings}.jpeg`、`smoke-B2-settings-before-switch.jpeg`、
`smoke-B2-settings-after-switch.jpeg`（23:46：Tab 已英文 + 设置内容仍中文 + 白 Tab 栏）、
`smoke-B2-home-after-switch.jpeg`（首页内容英文+深色、Tab 英文但白条）、
`smoke-B2-settings-back.jpeg`（切回后设置内容英文）、`smoke-B2-coldstart-en-dark.jpeg`（冷启动对照）、
`smoke-B2-final-restored.jpeg`（恢复演示态）、`smoke-B3-autosync-off.jpeg`。

---

## 11. 最终截图流水线使用说明

脚本：`harmonyos/scripts/emu/capture-store-shots.sh`（依赖 `emu.sh` / `uitools.py`、macOS `sips`）

### 11.1 输出约定

```
harmonyos/docs/store-assets/
├── screenshot-manifest.md                 # 自动生成：正式素材清单（路径/形态/页面/主题/分辨率/大小）
└── screenshots/
    ├── phone/<page>-<light|dark>.jpeg     # 手机 9 张
    ├── pc/<page>-light.jpeg               # PC 4 张
    ├── tablet/_degraded/*.jpeg            # 平板退化验证（不可上架）
    └── <device>/smoke-*.jpeg              # 运行时验证证据（不可上架）
```

`<page>` ∈ `home | stats | records | settings`；额外 `stats-scrolled`（进 stats 页后下滑一屏，
展示「用量趋势 + 日历热力图 + 模型用量趋势」，命名 `stats-scrolled-<theme>.jpeg`）。

### 11.2 常用命令（最终版）

```bash
cd harmonyos

# 手机：5 亮 + 4 暗 = 9 张（正式素材，自动清数据 seed + 页面去重校验）
./scripts/emu/capture-store-shots.sh --device phone --theme light \
  --pages home,stats,stats-scrolled,records,settings
./scripts/emu/capture-store-shots.sh --device phone --theme dark \
  --pages home,stats,records,settings

# PC：4 张（自动窗口最大化）
./scripts/emu/capture-store-shots.sh --device pc --theme light

# 平板：无镜像时自动退化 2in1 4:3（结果标 DEGRADED，不产生正式素材）
./scripts/emu/capture-store-shots.sh --device tablet --theme light

# 只验证流程不操作设备
./scripts/capture-store-shots.sh --all --dry-run   # 实际路径：scripts/emu/capture-store-shots.sh

# 重要开关：
#   --clean-data（默认开）拍摄前 bm clean 应用数据 + 预热 demo seed（账号名/数据一致）
#   --no-clean-data       保留现有数据（只补拍个别页面时用，避免重新 seed）
#   --no-install          不重装 HAP      --build  先构建
#   --settle <秒>         每页启动后等待（默认 5；demo 首次 seed 时可调大）
```

单页拍摄会因「无法用页面去重校验 page 参数」标为 UNVERIFIED（移入 `_degraded/`），
至少 2 页才能验证页面切换；正式拍摄请按整套页面执行。

### 11.3 尺寸转换（release-materials 负责）

```bash
.venv/bin/python3 harmonyos/docs/release/tools/prep-screenshots.py --all
# → docs/release/screenshots-upload/{phone,pc}/：1080×1920 / 1920×1080（pad 模式等比缩放+品牌底色）
```

---

## 12. AGC 截图选取顺序建议

- **手机 9 张（AGC 3-10 张内全部可传）**：
  `home-light → stats-light → stats-scrolled-light → records-light → settings-light →
   home-dark → stats-dark → records-dark → settings-dark`
  （只传 5 张时：`home-light → stats-scrolled-light → records-light → settings-light → home-dark`）
- **PC 4 张**：`home-light → stats-light → records-light → settings-light`
- **平板**：不提供独立素材（见 §9）。

---

## 13. 已知限制（重要）

1. **未签名 HAP 仅模拟器可用**：真机/上架必须 AGC 签名（`scripts/inject-signing.sh`、`docs/agc-release-checklist.md`）。
2. **模拟器是 GUI 进程**：会占用宿主屏幕，不要 kill/关闭窗口；正常停止用 `Emulator -stop`。
3. **hdc 端口漂移**：target 形如 `127.0.0.1:<port>`，每次启动可能变化；脚本自动发现，禁止写死端口（可 `HDC_TARGET=` 指定）。
4. **内存限制**：16GB 宿主同时只跑一台模拟器；切换设备必须先 stop 再 start。
5. **平板镜像缺失**：本机无 Tablet 镜像，平板形态只能退化验证（见 §9）。
6. **release vs debug 构建互相覆盖**：`./scripts/build.sh app`（assembleApp/release）会把
   `entry/build/default/outputs/default/entry-default-unsigned.hap` 覆盖成 release 版
   （`BuildProfile.DEBUG=false`，demo/调试入口全部失效）。**拍商店截图前必须重新跑
   `./scripts/build.sh hap`（debug）**。发布 release `.app` 后如再补截图，务必重跑 debug。
7. **2in1 窗口尺寸不能通过 aa 参数设定**：`--ww/--wh` 被忽略；用标题栏最大化或 `uitest drag` 拖窗口边缘（见 §8）。
8. **2in1 窗口缩放后布局残留（应用 bug）**：EditorialGrid 列数变化会残留旧行（9 格），
   流水线用「切 tab 重建页面」规避；根治建议见 §2.3。
9. **调试参数语法**：`--ps` 必须 key/value 两个 token（`--ps demo 1`）。
10. **锁屏**：冷启动会锁屏，`emu.sh wait/start-*` 自动解锁。
11. **真机差异**：2in1 模拟器默认浮动窗口 + 任务栏，真机 PC 窗口策略可能不同，商店图以模拟器结果为准时需在 release 文档注明。

---

## 14. 证据清单（本次实测）

| 证据 | 路径 | 说明 |
| --- | --- | --- |
| 正式素材清单 | `docs/store-assets/screenshot-manifest.md` | 13 张正式截图（路径/尺寸/大小） |
| 手机欢迎页（旧 HAP，历史） | `screenshots/phone/smoke-welcome.jpeg` | 早期冒烟证据 |
| 手机登录崩溃现场（已修复） | `screenshots/phone/smoke-login-attempt-crashed.jpeg` | jscrash 历史证据（LoginPage.ets:27） |
| 登录页（修复后） | `screenshots/phone/smoke-login.jpeg` | WebView 加载 opencode.ai 登录页 |
| release 构建欢迎页 | `screenshots/phone/smoke-release-welcome.jpeg` | 上架 release HAP 无调试入口的证据 |
| 2in1 窗口模式证据 | `screenshots/pc/smoke-welcome.jpeg`、`smoke-window-maximized.jpeg`、`smoke-window-4x3.jpeg` | 浮动窗口/最大化/4:3 窗口 |
| 平板退化验证 | `screenshots/tablet/_degraded/`（含 README） | 2in1 4:3 窗口裁剪，标注不可上架 |
| crash 日志（历史） | `/tmp/jscrash-2226.log`、`/tmp/jscrash-latest.log`；设备 `/data/log/faultlog/faultlogger/jscrash-*.log` | LoginPage / GgCard this 绑定等崩溃全文 |
| crash-check 快照 | `/tmp/gogauge-crashcheck-20261103-230825.log` | 最终 HAP crash-check PASS |
| 流水线工作目录 | `/tmp/gogauge-capture-*/` | 每次拍摄的中间截图/layout json/汇总 |

---

## 15. 速查（复制即用）

```bash
cd harmonyos/scripts/emu

./emu.sh list                    # 实例 + hdc target + 设备 + 应用状态
./emu.sh start-phone             # 启动手机并等待就绪（含解锁）
./emu.sh install latest          # 安装最新构建的未签名 HAP（debug 构建！）
./emu.sh reset-app               # 清应用数据（demo 截图前让 DemoSeed 从零 seed）
./emu.sh launch --ps demo 1 --ps lang zh --ps theme dark --ps page stats
./emu.sh stop-app
./emu.sh shot smoke-welcome      # -> docs/store-assets/screenshots/phone/smoke-welcome.jpeg
./emu.sh unlock
./emu.sh logs --app -n 100
./emu.sh crash-check --wait 15
./emu.sh dump-ui /tmp/layout.json
./emu.sh tap 660 1840 ; ./emu.sh swipe 660 2400 660 800
./emu.sh stop all
./emu.sh create-tablet           # 预期失败：本机无 Tablet 镜像（见 §9）
./emu.sh build

# 商店截图（最终）
cd ..
./scripts/emu/capture-store-shots.sh --device phone --theme light --pages home,stats,stats-scrolled,records,settings
./scripts/emu/capture-store-shots.sh --device phone --theme dark  --pages home,stats,records,settings
./scripts/emu/capture-store-shots.sh --device pc --theme light
```
