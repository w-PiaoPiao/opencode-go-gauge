# GoGauge HarmonyOS NEXT — OpenCode Go 用量仪表盘（鸿蒙版）

与桌面版（`app/`，Python+pywebview）和安卓版（`android/`，Kotlin+Compose）功能一致的
鸿蒙 NEXT 原生实现：**ArkTS + ArkUI（Stage 模型）**，单工程一多开发，同时适配
**手机/平板**（对标安卓版）与 **PC/2in1**（对标 Windows 版）两种形态。

> 解析器/格式化/SQL 与本仓库桌面版、安卓版 1:1 移植；
> 若 opencode.ai 接口格式变化，需同步修改三处（Python / Kotlin / ArkTS）。

## 技术栈与工具链

- 语言/框架：ArkTS（严格 TS）+ ArkUI，状态管理 V2（`@ObservedV2`/`@Trace`）。
- DevEco Studio **6.1.1** + 自带 HarmonyOS SDK **6.1.1（API 24）**。
- 构建：hvigor 6.24.2（DevEco 内置），`hvigorw` 脚本代理到 DevEco 工具目录。
- 存储：`@ohos.data.relationalStore`（RDB，对应 `db.py` 四表）+ `preferences`。
- 网络：`@ohos.net.http`；后台任务：`@ohos.resourceschedule.workScheduler`。

### 命令行构建

```bash
# 本仓库 harmonyos/ 目录下
export DEVECO_SDK_HOME="/Applications/DevEco-Studio.app/Contents/sdk"   # 自带 SDK 根
export NODE_HOME="/Applications/DevEco-Studio.app/Contents/tools/node"
./hvigorw --mode module -p product=default assembleHap --no-daemon
# 产物: entry/build/default/outputs/default/entry-default-signed.hap
```

> 注意：本机用户目录 `~/Library/OpenHarmony/Sdk/13`（API 13）是旧版 SDK，
> hvigor 6.24.2 无法识别该目录布局（缺少 `sdk-pkg.json`），统一使用 DevEco
> 自带 SDK（6.1.1 / API 24）。因此 **HAP 要求设备运行 HarmonyOS 6.1.1+**；
> 若需兼容 5.x 设备，请用 DevEco Studio 的 SDK Manager 另行下载对应的旧 SDK 并调整
> `build-profile.json5` 的 `compatibleSdkVersion`。

## 与桌面版/安卓版的平台差异（替代清单）

| 桌面/安卓能力 | 鸿蒙方案 |
| --- | --- |
| Windows 托盘 / macOS 菜单栏 | 无第三方托盘 API：关闭窗口=退出或隐藏主界面；同步由前台定时器 + 后台 WorkScheduler 保证 |
| 开机自启（autostart.py） | 暂无第三方自启 API，已知缺口 |
| 后台同步间隔 15 分钟（WorkManager） | WorkScheduler 重复任务最短 **20 分钟**；前台 1/5/15/30 分钟精确 |
| WebView2 cookie 读取 | ArkUI Web 组件 + `webview.WebCookieManager.fetchCookieSync` 轮询 |
| 电脑端一次性更新（updater.py） | 上架 AppGallery 后用应用市场版本升级能力 |

## 目录结构

```
entry/src/main/ets/
├── entryability/EntryAbility.ets        # UIAbility 入口
├── pages/                               # Index(根/欢迎) / LoginPage(Web 登录)
├── common/
│   ├── auth/Login.ets                   # 登录 URL 构造 + cookie 提取（auth.py 移植）
│   ├── store/AppPrefs.ets               # preferences 封装（cookie/工作区/设置）
│   └── model/ ...                       # 数据模型（对齐 Android data/model）
├── data/
│   ├── db/                              # RDB 四表 + DAO（对齐 db.py / Room）
│   ├── remote/                          # OpenCodeApi + Quota/Usage 解析器
│   └── repository/                      # 同步引擎（对标 server.py / DashboardRepository）
├── sync/                                # WorkScheduler 后台同步
└── ui/                                  # 页面组件（home/stats/records/settings/…）
```

## 里程碑

- [x] M1 脚手架与登录闭环（登录页 Web 组件捕获 auth cookie + 工作区）
- [x] M2 数据层与同步引擎（RDB 四表、API/解析器、增量/全量同步）
- [x] M3 主界面（首页/统计/记录 + ArkUI 原生图表 + 一多自适应主壳）
- [x] M4 设置/多账号/双主题/中英 i18n
- [x] M5 PC/2in1 窗口策略 + 前台定时同步 + WorkScheduler 后台任务
- [ ] M6 正式签名与上架（材料清单/CI 模板/单测已就绪; 证书签发与上架需用户 AGC 操作）

## 验证记录

- [x] `hvigorw assembleHap` 编译通过，产出 `entry-default-unsigned.hap`
- [x] `hvigorw test` 本地单元测试 **21/21 通过**（Quota/Usage 解析器、Fmt、活跃账号策略，对齐安卓用例）
- [ ] 运行时全流程验证（DevEco 模拟器: 登录→同步→三页出数→截图，供上架材料）