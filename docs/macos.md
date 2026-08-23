# GoGauge macOS 版说明

macOS 平台的功能差异、构建、分发与常见问题。英文摘要见文末 [English Summary](#english-summary)。

## 🎛 macOS 专属功能

- **菜单栏快捷面板**：点击菜单栏图标即可查看今日费用 / 请求数、配额窗口余量，约 30 秒自动刷新
- **菜单栏图标**：template 单色模式，自动适配浅色 / 深色菜单栏；关闭窗口最小化到菜单栏，从 Dock 或菜单栏唤起时强制置前
- **半自动更新**：检测到新版本后，应用内下载更新包到 `~/Downloads` 并在 Finder 中定位；下载失败时自动兜底打开 Releases 发布页
- **开机自启**：设置页「开机自启」开关（仅打包版展示），通过 LaunchAgent 实现
- **窗口记忆**：记住主窗口位置与尺寸，关闭到菜单栏 / 退出前保存
- **菜单语言**：托盘 / 菜单栏菜单跟随系统首选语言（中文 / English）

## 🏗 构建

环境：macOS 11+、Python 3.12（推荐）、Xcode Command Line Tools。

```bash
./build_macos.sh
```

输出 `dist/GoGauge.app`（无终端窗口，含 `.icns` 图标与菜单栏托盘支持）。

- 依赖锁定：优先使用 `requirements-macos.lock.txt`
- 产物为 **Apple Silicon (arm64)** 原生；Intel Mac 请使用 Releases 中带 `-x86_64` 后缀的包
- 自动构建：推送 `v*-macos` tag 触发 GitHub Actions 双架构矩阵（macos-14 arm64 / macos-13 x86_64），构建产物自动附到同名 release

## 📦 分发与更新

- 安装包发布在本 fork 的 **Releases** 页；若某版本 tag 已推送但 Releases 暂无产物，说明 macOS 构建仍在排队或失败，可查看仓库 Actions 状态或稍后再试
- 更新检查源在打包时写入（默认指向本 fork 仓库），与分发源保持一致；检查时只认 `-macos` 条目，不会被其它平台的 release 带偏

## 🛡 Gatekeeper（首次打开被拦截）

开源版未做 Apple 公证（公证需付费开发者账号）。若首次打开被 Gatekeeper 拦截，在终端执行一次：

```bash
xattr -cr /Applications/GoGauge.app
```

然后正常双击打开即可。

## ⚠ 已知限制

- 未公证（Apple 公证需 $99/年开发者账号）
- 移动 `.app` 位置后需重新开关一次「开机自启」（LaunchAgent plist 记录的是旧路径）
- 半自动更新仅下载并定位，不自动替换安装

## English Summary

The macOS build adds a menu-bar quick panel (today's cost / requests and quota remaining, ~30s auto-refresh), a template monochrome menu-bar icon (auto light/dark), semi-automatic updates (downloads the new build to `~/Downloads` and reveals it in Finder; falls back to the Releases page on failure), launch-at-login (LaunchAgent, toggle in Settings, packaged builds only), window position memory, and menus that follow the system language.

Build with `./build_macos.sh` (requires macOS 11+, Python 3.12, Xcode CLT) → `dist/GoGauge.app`. The build is Apple Silicon (arm64) native; Intel Macs use the `-x86_64` package from Releases. Pushing a `v*-macos` tag triggers dual-arch CI builds (macos-14 arm64 / macos-13 x86_64) that attach artifacts to the matching release.

Packages are published in this fork's **Releases**. The app is **not notarized**; if Gatekeeper blocks first launch, run `xattr -cr /Applications/GoGauge.app` once in Terminal. Known limitations: no Apple notarization ($99/yr account), and after moving the `.app` you must toggle launch-at-login off/on again (the plist records the old path).