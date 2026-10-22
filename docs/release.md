# 发布流程（统一 Release）

一个版本 tag 发布一个 GitHub Release：**Windows / macOS（arm64 + x86_64）/ Android
安装包都作为同一个 release 的 assets**。自 `v2.2.1d` 起采用此方式。

对应 workflow：`.github/workflows/release.yml`。

## 一次发布要做什么

1. 修改版本号并提交：
   - 桌面端：`app/__init__.py` 的 `__version__`
   - Android：`android/app/build.gradle.kts` 的 `versionName` / `versionCode`
2. 推送 `main`。
3. 打 tag 并推送（**不带平台后缀**）：

   ```bash
   git tag v2.2.1d
   git push origin v2.2.1d
   ```

4. GitHub Actions 的 `release` workflow 并行构建：

   | 平台 | runner | release asset |
   |---|---|---|
   | Windows | `windows-latest` | `GoGauge-v2.2.1d-windows.exe` |
   | macOS arm64 | `macos-14` | `GoGauge-v2.2.1d-macos-arm64.zip` |
   | macOS x86_64 | `macos-15-intel` | `GoGauge-v2.2.1d-macos-x86_64.zip` |
   | Android | `ubuntu-latest` | `GoGauge-v2.2.1d-android.apk` |

   另附 `SHA256SUMS.txt` 校验清单。

5. 三端都构建成功后，`publish` job 创建 release（`--generate-notes`）并把全部
   资产上传到同一个 release。若该 tag 的 release 已存在（重跑/补发），改为
   `gh release upload --clobber` 覆盖资产，不会重复建 release。

## 重跑 / 补发

- Actions 页面 → `release` → **Re-run all jobs**；
- 或 **Run workflow**（`workflow_dispatch`）：
  - 选 tag：完整重跑；release 已存在则覆盖资产；
  - 选 branch：只构建、不发 release（可用于验证构建）。
- 任一平台构建失败时 `publish` job 不执行 —— 不会出现「统一 release 缺平台」，
  修好后重跑即可。

## 更新检查如何识别（已同步改好）

桌面（`app/updater.py`）与 Android（`data/remote/UpdateApi.kt`）同时识别两种形态：

- **旧式平台 tag**：`v2.2.1a-macos` / `v2.2.1b-windows` / `v2.2.1a-android`
  （历史 release 仍在列表里，老版本仍可检测）；
- **统一 release tag**：`v2.2.1d`，但要求该 release 的资产里确实有本平台安装包
  （只发 Android 的 release 不会让桌面端误报更新）。

实现上遍历 release 列表**按版本号取最大**，再按资产名挑包：macOS 按 CPU 架构
优先 `arm64` / `x86_64`，Windows 取 `.exe`，Android 取 `.apk`。

## 旧式「按平台发 release」还留着吗？

留着（`release-macos.yml` / `release-windows.yml` / `release-android.yml` /
`release-harmonyos.yml`），用途：

- **单平台热修**：只修 macOS/Android 时不必三端重发；
- **过渡期兼容**：已安装的旧版本客户端只认带平台后缀的 tag，看不到统一 release。
  升级到首个统一版本时，可以临时用旧 tag（如 `v2.2.1d-macos`）发一次各平台
  release 作过渡，或让用户手动下载一次统一包；装上带新检查逻辑的版本后，
  后续统一 release 就能自动检测；
- **HarmonyOS** 暂未纳入统一发布（需要 DevEco 工具链 + HAP 签名 secrets），仍走
  `v*-harmony` 单平台流程。后续若要并入，在 `release.yml` 增加 build job 和 HAP
  资产即可（桌面/Android 的检查逻辑按资产名识别，不受影响）。

## 资产命名约定（重要）

更新检查按**资产名**识别平台，改名会导致客户端找不到包：

- Windows：`GoGauge-v<版本>-windows.exe`
- macOS：`GoGauge-v<版本>-macos-arm64.zip` / `GoGauge-v<版本>-macos-x86_64.zip`
- Android：`GoGauge-v<版本>-android.apk`
