# GoGauge — OpenCode Go 用量仪表盘

<p align="center">
  <img src="assets/GoGauge.ico" width="64" alt="GoGauge">
</p>

<p align="center">
  <b>本地优先的 OpenCode Go 用量统计面板</b>：配额窗口、Token 构成、模型排行、使用记录，打开即见。
</p>

<p align="center">
  <a href="./README_en.md">🌐 English</a>
</p>

> 🔀 本仓库 fork 自 [yphyphyph/opencode-go-gauge](https://github.com/yphyphyph/opencode-go-gauge)，
> 在原 Windows 版基础上新增 **macOS** 与 **Android** 平台支持。
> macOS / Android 安装包发布在本仓库 [Releases](releases)，Windows 安装包由上游仓库发布。

## 🗺 平台支持

| 平台 | 状态 | 安装包 | 文档 |
|:---:|:---:|:---|:---|
| **Windows** | ✅ 正式版 | [上游 Releases](https://github.com/yphyphyph/opencode-go-gauge/releases)：`GoGauge.exe`（单文件，无需安装） | — |
| **macOS** | ✅ 正式版 | [本仓库 Releases](releases)：arm64 / x86_64 分包（以 Releases 页实际产物为准） | [docs/macos.md](docs/macos.md) |
| **Android** | ✅ 正式版 | [本仓库 Releases](releases)：`GoGauge-v2.1.0-android.apk`（APK 侧载） | [android/README.md](android/README.md) |
| **HarmonyOS NEXT** | 🚧 开发中（M1 骨架与登录已提交） | HAP（构建/签名/上架见 [harmonyos/README.md](harmonyos/README.md)） | [harmonyos/README.md](harmonyos/README.md) |

---

## 📸 截图

| 主页（亮色） | 主页（暗色） |
|:---:|:---:|
| ![Home Light](assets/screenshots/home-light.png) | ![Home Dark](assets/screenshots/home-dark.png) |

| 用量统计 | 使用记录 |
|:---:|:---:|
| ![Stats](assets/screenshots/stats.png) | ![Records](assets/screenshots/records.png) |

| 设置 | 登录 | 关于 |
|:---:|:---:|:---:|
| ![Settings](assets/screenshots/settings.png) | ![Login](assets/screenshots/login.png) | ![About](assets/screenshots/about.png) |

---

## ✨ 功能

- **配额窗口实时监控**：滚动 5 小时 / 每周 / 每月，进度条 + 剩余比例 + 重置倒计时
- **用量概览**：缓存命中率 / 命中量 / 总 TOKEN（含缓存命中）/ 请求数 / 费用 / 会话数
- **今日趋势**：24 小时输入 / 输出柱状图
- **用量统计**：Token 构成（输入 / 输出 / 推理 / 缓存读 / 缓存写 / 会话）、模型用量环形图 + 排行、费用/请求/总 TOKEN 三线趋势
- **会话历史**：按会话聚合请求数 / 输入 / 输出 / 推理 / 总 Token / 成本，分页浏览
- **使用记录**：请求级明细分页浏览，支持模型筛选，含模型 / Key 名称列
- **多账号支持**：用户管理（添加 / 切换 / 重命名 / 删除 / 重新登录），用量按账号隔离，记录与会话表显示 Key 名称列
- **账户总览面板**：设置中可开关，聚合展示各账户配额三窗口、今日用量与跨账号合计 KPI、7 日费用趋势对比
- **内置 WebView 登录**：独立登录窗口打开官方授权页，自动回填 cookie 与工作区，无需手动复制
- **自动同步**：增量同步（1/5/15/30 分钟可选）+ 同步范围设置（30/60/90/180 天 / 所有）
- **双主题**：亮色 / 深色一键切换；中英双语界面
- **系统托盘 / 菜单栏**：Windows 关闭窗口最小化到托盘，macOS 关闭窗口最小化到菜单栏；应用图标使用品牌 Logo
- **macOS 增强**：菜单栏今日用量快捷面板（30s 刷新）、半自动更新、开机自启 —— 详见 [docs/macos.md](docs/macos.md)
- **本地优先**：所有数据保存在本机 SQLite，登录凭据仅用于同步官方接口

## 🖥 快速开始

### Windows

从上方 [平台支持](#-平台支持) 的**上游 Releases** 下载 `GoGauge.exe`（单文件，无需安装）：

1. 双击运行，欢迎页点击「立即登录」弹出官方授权窗口
2. 完成登录后自动进入面板并同步用量数据
3. 数据保存在 exe 同目录 `data\` 文件夹

> 需要 Windows 10/11（自带 WebView2 Runtime）。关闭窗口会最小化到系统托盘。
> Windows 安装包由上游仓库维护发布。

### macOS

从本仓库 [Releases](releases) 下载对应架构的安装包（arm64 / x86_64），解压后将 `GoGauge.app` 拖入「应用程序」。

> 菜单栏快捷面板 / 开机自启 / 半自动更新 / Gatekeeper 放行等说明见 [docs/macos.md](docs/macos.md)。

### Android

从本仓库 [Releases](releases) 下载 `GoGauge-v2.1.0-android.apk`，在系统设置中允许「安装未知来源应用」后侧载安装。

> Android 版为 Kotlin + Jetpack Compose 原生实现，功能与桌面版一致，
> 构建 / 技术栈 / 与桌面版的差异详见 [android/README.md](android/README.md)。

### 源码运行

```bash
pip install -r requirements.txt
python entry.py
```

### 打包

**Windows**

```bash
build.bat
```

输出 `dist\GoGauge.exe`（约 38 MB，--noconsole 无黑窗，含 logo 图标与托盘支持）。

**macOS**

```bash
./build_macos.sh
```

输出 `dist/GoGauge.app`（无终端窗口，含 `.icns` 图标与菜单栏托盘支持）。

> 需要 macOS 11+（内置 WebKit，pywebview 使用 WKWebView）。关闭窗口会最小化到菜单栏。
> 双架构 / 依赖锁定 / CI 自动构建等详见 [docs/macos.md](docs/macos.md)。

## 📊 数据说明

- **数据来源**：opencode.ai 工作区用量接口（`/_server` server-fn）+ 配额页 HTML 解析
- **总 TOKEN** = 输入（含缓存命中）+ 输出 + 推理
- **缓存命中率** = 命中 /（命中 + 未命中）
- **费用**：USD 原始值，人民币按 open.er-api.com 实时汇率换算（24h 缓存）

## 🔒 隐私

- 登录 cookie 仅保存在本机，绝不写入日志、绝不上传
- 用量数据全部本地存储，应用不含任何遥测

## 🛠 技术栈

Python · pywebview (WebView2 / WKWebView) · SQLite · Chart.js · pystray

## 📬 联系

- GitHub：[yphyphyph/opencode-go-gauge](https://github.com/yphyphyph/opencode-go-gauge)
- CSDN：[Ying_ph](https://blog.csdn.net/Ying_ph)

## 📄 License

[MIT](LICENSE) © GoGauge