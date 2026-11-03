# GoGauge HarmonyOS — AppGallery 上架核对清单（1.0.0）

> 目标：华为应用市场（AppGallery / HarmonyOS NEXT），应用 **GoGauge**，包名 **`io.github.yphyphyph.gogauge`**。
> 本文与当前工程状态对齐（2026-11）。配套材料：
> - 逐字段填写表：`release/appgallery-metadata.md`
> - 逐步发布指南：`release-guide.md`
> - 文案：`release/app-intro-zh.md` / `release/app-intro-en.md`
> - 隐私政策：`release/privacy-policy-zh.md` / `release/privacy-policy-en.md`
> - 权限/隐私声明：`release/permission-rationale.md`
> - 图标/宣传图：`release/assets/`
> - 截图转换：`release/tools/prep-screenshots.py`
>
> 官方规格以 AGC 后台实际提示为准；来源链接见文末。

## 0. 产物与包标识

| 项 | 当前值 | 来源 |
| --- | --- | --- |
| 应用名称 | `GoGauge` | `AppScope` / `entry` 的 `app_name` |
| bundleName | `io.github.yphyphyph.gogauge` | `AppScope/app.json5` |
| versionName / versionCode | `1.0.0` / `1000000` | `AppScope/app.json5` |
| 应用类型 | HarmonyOS 应用（非元服务/非游戏） | `AppScope/app.json5` |
| 设备类型 | phone / tablet / 2in1 | `entry/src/main/module.json5` `deviceTypes` |
| SDK | compatible/target = `6.1.1(24)`（HarmonyOS 6.1.1+） | `build-profile.json5` |
| 权限 | 仅 `ohos.permission.INTERNET`（normal） | `entry/src/main/module.json5` |
| 第三方依赖 | 无（仅 devDependency `@ohos/hypium` 单测框架） | `oh-package.json5` |

> ⚠️ **上架包是 `.app`（App Pack），不是 `.hap`。** HAP 只用于本地/模拟器安装调试。

## 1. Release 构建与自检

- [ ] 版本号已按发布计划设置（首版 1.0.0 / 1000000；升级规则见 `release-guide.md` §11）
- [ ] `entry/build-profile.json5` 的 release 构建配置符合预期（当前 `obfuscation.enable=false`；如开启混淆需回归测试）
- [ ] Release `.app` 构建成功：
  - 推荐：`./scripts/build.sh app`（已实现；默认 release，产物 `build/outputs/default/*.app`（工程根 build 目录））
  - GUI：**Build → Build Hap(s)/APP(s) → Build APP(s)**
  - 等价 CLI：`./hvigorw assembleApp -p product=default -p buildMode=release --no-daemon`（assembleApp 是工程级任务，**不能**加 `--mode module`）
  - 本机实测产物：`build/outputs/default/harmonyos-default-unsigned.app`（注入签名后为 `harmonyos-default-signed.app`）
  - ⚠️ 注意：`assembleApp`（release）会同时把 `entry/build/default/outputs/default/entry-default-unsigned.hap`
    覆盖为 release 版（`BuildProfile.DEBUG=false`）。拍商店截图/需要 demo 调试数据前，必须重新执行
    `./scripts/build.sh hap` 生成 debug HAP。
- [ ] HAP 仅用于模拟器/真机调试：`./scripts/build.sh hap` → `entry/build/default/outputs/default/entry-default-unsigned.hap`
- [ ] 本地单元测试通过：`./scripts/build.sh test`
  - 以 **最新一次运行结果**为准：`entry/.test/default/intermediates/test/coverage_data/test_result.txt`
  - 单测以最新一次运行为准：当前 `./scripts/build.sh test` 结果为 **Tests run: 35, Pass: 35**；docs 中出现的 21/28 等旧数字均为历史记录，不要引用
- [ ] 上架前体检（推荐）：DevEco **Tools → AppAnalyzer → 上架前体检**，目标 100 分并可 Sync To AG
- [ ] 上架预检（推荐）：DevEco Testing → 测试服务 → 上架预检
- [ ] 包内无调试信息（release 构建保证 `debug=false`；发布版本不显示调试工具入口）

## 2. 签名（发布证书 + 发布 Profile，缺一不可）

- [ ] 生成密钥库 `.p12` + CSR `.csr`（DevEco **Build → Generate Key and CSR**，或 `hap-sign-tool generate-keypair/generate-csr`；**密码/别名/文件离线备份**）
- [ ] AGC 申请**发布证书** `.cer`（每个账号最多 3 个；实名开发者有效期 3 年）
- [ ] AGC 申请**发布 Profile** `.p7b`（类型=发布，选择上述证书；每个应用最多 100 个）
- [ ] 签名配置（二选一）：
  - DevEco：File → Project Structure → Signing Configs → 取消自动签名 → 填 Store file/Store password/Key alias/Key password/Sign alg=`SHA256withECDSA`/Profile file/Certpath file → Apply
  - 命令行：先 `node scripts/gen-signing-material.js --signing-dir <p12目录> --store-password … --key-password …` 生成 material+加密密码，再 `HAP_STORE_FILE=… HAP_KEY_ALIAS=… HAP_PROFILE_P7B=… HAP_SIGN_CER=… HAP_SIGNING_PASSWORDS_JSON=… bash scripts/inject-signing.sh`（hvigor 6.x 不接受明文密码，详见 release-guide §5 路径 C）
- [ ] 用发布签名材料重新构建 **Release `.app`**（调试签名/自动签名不能上架）
- [ ] 签名材料安全：`.p12/.cer/.p7b/.csr/material/` 与 `signing-passwords.json` 不提交仓库（已在 `.gitignore` 排除）；签名后恢复 `build-profile.json5`（`git checkout -- harmonyos/build-profile.json5`）
- [ ] 真机侧载（可选，验证包）：`hap-sign-tool sign-app` 签 HAP → `./scripts/install.sh`

> 参考：`release-guide.md` §3–§5（含完整可复制命令与 `hap-sign-tool` 模板）。

## 3. AGC 应用与版本信息

- [ ] 华为开发者账号已实名认证（个人/企业）
- [ ] AGC 创建 HarmonyOS 应用：名称 `GoGauge`、包名 `io.github.yphyphyph.gogauge`、分类=应用、**支持设备=手机 + PC/2in1（v1.0 不勾平板；平板由手机兼容分发，包内 deviceTypes 仍含 tablet，符合子集规则）**、默认语言=简体中文
- [ ] 应用信息：可本地化基础信息（名称/图标，中文 + English）、支持设备、分类/标签（主标签 `工具`，次标签 `AI`，≤5 个）、开发者服务信息（客服邮箱等）
- [ ] 版本信息：简介/长描述/新版本特性（用 `release/app-intro-*.md`、`release-notes-1.0.0.md`）
- [ ] 上传 **Release `.app`**（软件包管理 → 使用场景「测试和正式上架」），合法性检测 = **已达标**
- [ ] （推荐）启动上架自检，报告 = 通过/待优化项已修复
- [ ] 内容分级问卷完成（预期 3+）
- [ ] AI 功能声明：不涉及生成式 AI 服务
- [ ] 上架时间已设置
- [ ] 「提交审核」完成

## 4. 素材规格（摘要，详见 `release/appgallery-metadata.md` §5）

| 素材 | 规格 | 本仓库资产 |
| --- | --- | --- |
| 应用图标 | 216×216 或 1024×1024，PNG ≤3MB，正方形，**与包内图标一致** | `release/assets/icon-1024.png`（品牌版；包内图标正由 platform-settings 成员替换为同源品牌分层图标）、`icon-216.png`、`icon-1024-package-match.png`（兜底） |
| 手机截图 | 竖向 9:16 1080×1920，**9 张**，JPG ≤5MB | ✅ 已就绪：`release/screenshots-upload/phone/`（源图 `docs/store-assets/screenshots/phone/`） |
| PC/2in1 截图 | 16:9 1920×1080，**4 张**，JPG ≤5MB | ✅ 已就绪：`release/screenshots-upload/pc/` |
| 平板截图 | —（v1.0 不提供） | 本机无 Tablet 镜像，`tablet/_degraded/` 仅布局验证，禁止上架；AGC 不勾选平板 |
| 介绍视频（可选） | MOV/MP4，15 秒–2 分钟，≤500MB | 不提供 |
| 宣传图（非上架截图） | — | `promo-2160x1080.png` / `promo-1080x2160.png`（仅供推广位/README，不得冒充真实界面） |

截图要求（审核硬性）：
- [ ] 尺寸/比例符合上表（原始模拟器截图需先转换：`.venv/bin/python3 docs/release/tools/prep-screenshots.py --all`）
- [ ] 每设备 3–10 张，覆盖首页/统计/使用记录/设置，建议含亮/暗主题
- [ ] **画面不含真实个人信息**（真实账号名、邮箱、Key 名称、workspace、token 等）
- [ ] **不含调试入口**（「注入模拟数据 (调试)」等；Lead 已安排演示/截图模式隐藏，release 构建本就没有）
- [ ] 不含 test/demo/beta 等测试字样，不含未实现功能入口
- [ ] 截图文件名以 `harmonyos/docs/store-assets/screenshot-manifest.md` 为准（13 张正式素材；已转换到 `release/screenshots-upload/`，手机 9 + PC 4）
- [ ] 平板：不提供独立截图，AGC 支持设备只勾手机 + PC/2in1（Lead 已拍板）

## 5. 隐私与合规

- [ ] 隐私政策已托管到 **HTTPS 公网 URL**（可用 GitHub Pages/自有站点/静态存储），内容与 `release/privacy-policy-zh.md` 一致；**占位符全部替换**（开发者名称、邮箱、生效日期等）
- [ ] 隐私政策内开发者名称 = AGC 实名主体名称；应用名称 = `GoGauge`；含简体中文版；敏感信息已加粗
- [ ] AGC「隐私声明」已配置（自定义 URL 或隐私托管）
- [x] **应用内**隐私合规（✅ 代码已实现，上架前人工复核）：
  - [ ] 首次启动**隐私政策弹窗**：明确「同意/拒绝」、不得默认勾选；同意后写入本地 preferences；拒绝后无法登录（`Index.ets` + `AppPrefs`）
  - [ ] 应用内可点击的隐私政策页（`pages/PrivacyPage`）：欢迎页底部 + 设置 → 关于 → 隐私政策（正文 `common/legal/PrivacyText.ets`）
  - [ ] 弹窗/页面内隐私政策正文与托管 URL 内容一致（提交前逐段比对）
- [ ] AGC「隐私标签信息录入」如实填写（是否涉及个人信息收集、业务场景=应用功能、无广告/分析/共享；见 `release/permission-rationale.md` §3）
- [ ] 「应用隐私说明」：仅 INTERNET normal 权限，预计无需填写；如后台要求，粘贴 `release/permission-rationale.md` §2
- [ ] 版权信息：上传**应用版权证书/代理证书**（中国大陆 + 手机设备必选；JPG/PNG/BMP ≤15MB/张、≤10 张）
- [ ] APP 备案（工信部核准）已完成，AGC 核准（备案）信息填写并通过校验
- [ ] 权限与实际一致：包内仅声明 `ohos.permission.INTERNET`，无敏感/受限权限，无需 ACL/场景视频

## 6. 审核信息与联系方式

- [ ] 勾选「需要登录进行审核」，提供**可用的 OpenCode Go 测试账号/密码**（须能完成登录→同步→查看→退出全流程；不可有会员/权限限制）
- [ ] 若无法提供测试账号：准备自测文件（`.docx` ≤15MB 或 `.mp4`；≤5 个、总 ≤500MB）演示全流程
- [ ] 应用负责人姓名/手机号/邮箱（含短信验证码验证；中国大陆开发者必填）
- [ ] 审核备注（模板见 `release/permission-rationale.md` §5）：说明「第三方非官方客户端、无自有账号体系、登录即 OpenCode 官方授权、数据仅本机」
- [ ] 客服邮箱已确认（用于接收审核结果/下架通知）

## 7. 审核风险与对策（当前状态）

| # | 风险 | 依据 | 状态/对策 |
| --- | --- | --- | --- |
| 1 | 应用内隐私政策入口 | 审核指南 7.1 | ✅ 已实现 `pages/PrivacyPage` + 欢迎页/设置入口；上架前人工复核 |
| 2 | 首次启动隐私弹窗 | 审核指南 7.5 / Checklist | ✅ 已实现首启弹窗（同意/拒绝）；未同意不得登录；上架前复核拒绝路径 |
| 3 | 第三方账号登录未提供华为账号登录 | 审核指南 3.16 | 产品决策不接 Account Kit；在审核备注说明「本应用是 OpenCode Go 第三方客户端，无自有账号体系，登录即 OpenCode 官方授权」，列为已知审核风险 |
| 4 | 商店图标与包内图标一致 | 名称/图标一致性检测 | ✅ 包内已替换品牌分层图标（`AppScope` layered_image，与 `icon-1024.png` 同源）；`icon-1024-package-match.png` 仅兜底 |
| 5 | 审核需登录但依赖用户自己的账号 | 审核信息要求 | 用户必须提供可用测试账号；否则提供自测视频 |
| 6 | 大陆需 APP 备案 + 版权证书 | 发布准备/Checklist | 用户自行办理（周期长，尽早启动） |
| 7 | 应用名称可能重名 | 创建应用规则 | 若被占用需改名（同步包内 label、隐私政策、全部文案） |
| 8 | 文案/截图不得出现未实现功能 | 审核 Checklist | 文案已排除 GOAT/账户总览；截图不得出现相关入口 |
| 9 | 截图含调试入口/真实个人信息 | 审核指南 1.19 / Checklist | 用演示/截图模式 + release 构建；示例数据；截图由流水线统一产出 |

## 8. CI（可选）

- `release-harmonyos.yml`：tag `v*-harmony` 触发；Ubuntu runner + 鸿蒙 Command Line Tools（含 hvigor/ohpm）+ SDK（API 24）；只产 unsigned HAP/.app 附 Releases（签名在本地完成，CI 不存密钥）。
- 备注：GitHub Actions 公网 runner 需能访问华为 SDK 下载源；受限时用本地/自建 runner 构建。
- 若 CI 只构建 `.app` 并上传 AGC，可改用 AGC Publishing API（可选）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-publish-api-guide-0000002271134665>

## 9. 真机/模拟器侧载（正式签名前的中间验证）

- 模拟器：接受**未签名 HAP**（`hdc install entry-default-unsigned.hap` 可直接装；用于 UI 走查与截图）
- 真机：需签名 HAP（发布证书 + 发布 Profile，或 DevEco 自动调试签名）
- 安装辅助：`./scripts/install.sh [signed.hap]`（hdc install + aa start）
- 设备开启「开发者选项 → USB 调试」；PC/2in1 形态同理

## 10. 发布后维护

- [ ] versionCode 严格递增（当前 `1000000`；建议 `major×1,000,000 + minor×10,000 + patch×100`，≤2,147,483,647）
- [ ] 升级时保持同一套发布证书/Profile；证书到期前用同一密钥库/CSR 更新证书与 Profile
- [ ] 只改应用信息可用「升级同版本」（选择在架软件包，版本号不变）
- [ ] 分阶段发布/回退/下架按 AGC 文档操作；回退需发更大 versionCode 的修复版
- [ ] 上架后建议关注 APMS / 云监控与用户评论

## 11. 仍需用户自行提供/完成

1. 华为开发者账号 + 实名认证
2. AGC 创建应用（绑定包名）
3. 发布证书 `.cer` + 发布 Profile `.p7b`（+ `.p12` 与密码，离线备份）
4. 隐私政策托管 URL（HTTPS；可用 GitHub Pages/自有站点）
5. 客服邮箱、官网（可选）、应用负责人手机号/邮箱/姓名
6. 应用版权证书/软著（大陆 + 手机必选）
7. APP 备案（工信部；选择「鸿蒙」平台并填写包名）
8. 审核测试账号（可用的 OpenCode Go 账号；否则提供自测视频）
9. 内容分级问卷、AI 声明、隐私标签信息（按后台如实填写）
10. 确认商店图标最终方案（品牌版为主；`package-match` 兜底）
11. 开发者显示名称与版权行确认（建议 `© 2026 GoGauge (yphyphyph)`）

## 12. 官方来源

- 发布 HarmonyOS 应用：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-0000002271695230>
- 素材规范：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-app-visual-asset-spec-0000002277607976>
- 应用审核指南：<https://developer.huawei.com/consumer/cn/doc/app/50104>
- 应用审核 Checklist：<https://developer.huawei.com/consumer/cn/doc/app/50170>
- 发布准备工作：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-prepare-0000002306311921>
- 上传软件包：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-upload-pkg-0000002277983368>
- 申请发布证书 / Profile：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-cert-0000002283336729>、<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-profile-0000002248341090>
- APP 核准（备案）指引：<https://developer.huawei.com/consumer/cn/doc/app/50130>
- 隐私标签服务说明：<https://developer.huawei.com/consumer/cn/doc/app/privacy-label>
- 更新应用信息：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-maintain-update-0000002271413697>
- 升级版本：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-maintain-upgrade-0000002236494386>
