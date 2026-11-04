# AGENTS.md — GoGauge 项目协作说明

本文件供 AI 代理/协作者快速接手本项目时阅读，记录仓库结构、构建命令与**发布签名配置**。
（签名材料本身不在仓库内；密码等敏感信息**永远不要写入本文件或任何仓库文件**。）

## 1. 项目构成

| 端 | 目录 | 技术栈 | 构建/校验 |
| --- | --- | --- | --- |
| 桌面（Windows/macOS） | `app/`、`app/web/` | Python + pywebview | `.venv/bin/python -m pytest -q` |
| Android | `android/` | Kotlin + Jetpack Compose | `cd android && ./gradlew :app:compileDebugKotlin --offline` |
| 鸿蒙 NEXT | `harmonyos/` | ArkTS + ArkUI（Stage 模型） | `cd harmonyos && ./scripts/build.sh {test,hap,app}` |

- Python 测试：`.venv/bin/python -m pytest -q`（当前全绿）。
- 鸿蒙单测：`./scripts/build.sh test`（当前 **35/35**）。
- 鸿蒙 debug HAP：`./scripts/build.sh hap` → `harmonyos/entry/build/default/outputs/default/entry-default-unsigned.hap`。
- 鸿蒙 Release App Pack：`./scripts/build.sh app` → `harmonyos/build/outputs/default/harmonyos-default-{signed|unsigned}.app`。
- ⚠️ `assembleApp` 会把同路径 debug HAP 覆盖成 release 版；之后需重新 `./scripts/build.sh hap`。
- 上架材料与发布指南：`harmonyos/docs/release-guide.md`、`harmonyos/docs/release/`、`harmonyos/docs/agc-release-checklist.md`；设计契约 `harmonyos/docs/design-spec.md`。

## 2. 鸿蒙发布签名配置（2026-11-04 用户本机填写）

> 仅记录**非敏感**配置项；密钥库密码/密钥密码由用户自设并保存在密码管理器中，**不记录、不提交**。

| 项 | 值 |
| --- | --- |
| 密钥库文件 | `/Users/yizhiwang/Desktop/opencode/gousage/harmonyRelease/gogauge-release.p12` |
| 证书请求文件 CSR | `/Users/yizhiwang/Desktop/opencode/gousage/harmonyRelease/gogauge-release.csr` |
| hvigor 签名材料目录 | `/Users/yizhiwang/Desktop/opencode/gousage/harmonyRelease/material/`（由 DevEco 生成，**必须与 p12 同目录**，勿删/勿动） |
| 开发者/运营者（AGC 实名主体） | `王逸之`（隐私政策与应用内文案必须一致） |
| 别名 alias | `gogauge` |
| 签名算法 | `SHA256withECDSA`（DevEco 高级设置默认：ECC 256 位 / 有效期 25 年） |
| 密钥库密码 / 密钥密码 | 用户自设（≥8 位，含字母+数字），仅存于密码管理器 |

注意事项：

- 签名目录在 **git 仓库之外**（仓库是 `gousage/opencode-go-gauge`，签名目录是同级的 `gousage/harmonyRelease`）；不要把它移入仓库。
- `harmonyos/.gitignore` 已排除 `*.p12 / *.p7b / *.cer / *.csr`；`material/` 也不应提交。
- DevEco 配置签名后会修改 `harmonyos/build-profile.json5`（含绝对路径与加密密码）：**不要提交该改动**，需要时
  `git checkout -- harmonyos/build-profile.json5` 还原。
- **`.p12` + 密码是应用签名身份**，丢失会导致后续无法更新版本，请立即备份（密码管理器/私有存储）。

### 2.1 后续上架链路（当前进度：已生成 p12 + CSR，待 AGC 换取证书）

1. AGC →「证书、APP ID 和 Profile」→ **发布证书**：上传 `gogauge-release.csr`，下载 `gogauge-release.cer`；
2. 同页 → **发布 Profile**：类型 **Release**、绑定包名 `io.github.yphyphyph.gogauge`、选择该发布证书，下载 `gogauge-release.p7b`；
3. 两个文件放到签名目录（与 `.p12` 同目录）；
4. DevEco → **文件 → 项目结构 → 签名配置**：取消「自动生成签名」，填写 Store file(`.p12`)/Store password/Key alias `gogauge`/Key password/Sign alg `SHA256withECDSA`/Profile file(`.p7b`)/Certpath file(`.cer`) → Apply；
5. `cd harmonyos && ./scripts/build.sh app` → 产物 `harmonyos/build/outputs/default/harmonyos-default-signed.app`；
6. AGC → 版本选取 →「上传新版本」→ 选择 **signed `.app`**（**不要**传 `.hap` / `-unsigned.app`）。

> 命令行替代方案：`scripts/gen-signing-material.js`（生成 hvigor 兼容 material + 加密密码）+ `scripts/inject-signing.sh`，
> 详见 `harmonyos/docs/release-guide.md` §5 路径 C。

## 2.2 隐私政策托管（AGC「隐私声明 → 自定义隐私政策」）

- 源文件：`harmonyos/docs/release/privacy-policy-zh.md` / `privacy-policy-en.md`（开发者名称已填 AGC 实名主体「王逸之」）
- 静态 HTML：`docs/privacy-policy-zh.html` / `docs/privacy-policy-en.html`（由 `harmonyos/docs/release/tools/render-policy-html.py` 从 Markdown 生成）
- 托管：GitHub Pages（仓库 `main` 分支 `/docs` 目录），AGC 填写：
  `https://w-piaopiao.github.io/opencode-go-gauge/privacy-policy-zh.html`
- 应用内 `common/legal/PrivacyText.ets` 必须与该页面内容一致（当前开发者：王逸之 / Wang Yizhi；联系方式：GitHub Issues）
- 用户协议：AGC 该字段无红星，可留空；如审核要求，再补一份静态 EULA 页面

## 3. AGC / 应用信息

| 项 | 值 |
| --- | --- |
| 应用名称 | `GoGauge` |
| 包名 / bundleName | `io.github.yphyphyph.gogauge`（AGC 创建后不可修改） |
| 版本 | `versionName 1.0.0` / `versionCode 1000000` |
| 上架设备 | 手机 + PC/2in1（v1.0 不提供平板独立截图，平板由手机兼容分发；包内 deviceTypes 仍含 tablet） |
| 应用图标 | `harmonyos/docs/release/assets/icon-1024.png`（与包内 AppScope 分层图标逐像素一致） |
| 商店截图 | `harmonyos/docs/release/screenshots-upload/phone/*.jpeg`（9 张 1080×1920）、`pc/*.jpeg`（4 张 1920×1080） |
| 应用介绍/隐私政策 | `harmonyos/docs/release/app-intro-zh.md`；隐私政策托管 URL：`https://w-piaopiao.github.io/opencode-go-gauge/privacy-policy-zh.html`（内容与应用内 `PrivacyText.ets` 一致） |

## 4. 已知限制 / 易踩坑

- 鸿蒙无真实 Tablet 模拟器镜像：平板布局仅用 2in1 窗口 4:3 验证，相关截图标记 `_degraded` 不用于上架。
- `harmonyos/entry/src/main/ets` 中所有颜色走 `Theme` 令牌、文案走 `I18n.t`；新增文案必须中英同步。
- `@Builder` 方法**不能**作为 `@BuilderParam` 传值（this 绑定会失效导致 jscrash），统一用尾随闭包。
- release 构建启动参数（`--ps demo/lang/theme/page`）被 `BuildProfile.DEBUG` 守卫，release 下无效；隐私政策首启弹窗不可绕过。
- 改包名/版本号需同步：`harmonyos/AppScope/app.json5`、`android/app/build.gradle.kts`、`harmonyos/entry/src/main/ets/common/BackgroundSync.ets`、隐私政策与文档中的包名引用。
- 桌面图标品牌几何唯一来源：`assets/generate_logo.py`；`scripts/build_icon.py` / `build_macos_icon.py` 只是导出器。
