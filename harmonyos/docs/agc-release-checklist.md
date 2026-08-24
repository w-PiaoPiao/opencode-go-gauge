# GoGauge HarmonyOS — AppGallery 上架材料清单与签名流程

> 目标: 上架华为应用市场 (AppGallery)。功能交付不阻塞于上架审批; 上架流程可并行推进。
> 前提: 已注册并实名的华为开发者账号 (个人/企业均可), 已安装 DevEco Studio 6.x。

## 0. 产物与包名

- `bundleName`: `io.github.yphyphyph.gogauge` (与 `AppScope/app.json5` 一致)
- 应用类型: HarmonyOS NEXT 应用 (非元服务)
- HAP 来源: `./hvigorw --mode module -p product=default assembleHap`

## 1. 签名步骤 (本地/CI 通用)

1. **生成密钥库 (p12)** — DevEco: File → Project Structure → Signing Configs → 新建;
   或命令行 `keytool -genkeypair` 生成 `release.p12` (建议口令 8+ 位、密钥库别名如 `gogauge`)。
2. **申请发布证书 (cer)** — AGC (AppGallery Connect) → 证书管理: 上传 CSR (由 p12 导出) →
   生成鸿蒙发布证书。
3. **申请 Profile (p7b)** — AGC → 我的项目 → 应用 → 签名/Profile: 选择应用 `io.github.yphyphyph.gogauge`、
   设备类型 (phone/tablet/2in1)、勾选发布证书 → 下载 `*.p7b`。
4. **配置到工程** — `build-profile.json5` 的 `app.signingConfigs` 填入 storeFile/storePassword/
   keyAlias/keyPassword + signAlg; `signingConfig` 指向该配置。
5. **签名构建** — 重新 `assembleHap`, 产物变为 `entry-default-signed.hap`。

> 材料密级: p12 / p7b / cer 一律进仓库 Secrets (GitHub Actions) / 本地私密目录,
> `.gitignore` 已排除 `*.p12` `*.p7b` `*.cer` `*.csr`。

## 2. 上架材料清单 (对照检查 / 预填用)

| 类别 | 材料 | 状态与备注 |
| --- | --- | --- |
| 账号 | 华为开发者账号实名认证 | ✅ 用户已有 |
| 应用信息 | 应用名称 (中/英)、简介、分类 (工具 → 开发者工具) | 待填, 名称建议 "GoGauge" |
| 图标 | 分层图标 (前景 288×288 无透明/背景, 参考 DevEco 图标规范) | 当前为单层 PNG 占位, 需替换正式分层图标 |
| 截图 | 手机形态 2~4 张 + PC/2in1 宽屏 1~2 张 (真实界面截图) | 需模拟器跑通后截图 |
| 隐私 | 隐私政策 URL 或文本: 声明「登录 cookie 仅存本机、不上传、无遥测、数据本地 SQLite」 | 以仓库 README 隐私段为基础改写为正式政策页 |
| 合规 | 在线签署《HarmonyOS 应用隐私保护指引》《网络安全承诺函》; 个人账号需完成实名认证+银行卡/身份证认证 | AGC 引导式提交 |
| 权限 | 仅声明 `ohos.permission.INTERNET` (normal 权限, 自动授予) | 无需敏感权限申请 |
| 版本 | `versionCode`/`versionName` 与 `AppScope/app.json5` 一致; 版本说明 (change log) | 首版 1000000 / 1.0.0 |
| 发布 | 发布证书 + Profile (第 1 节) + 上架审核（功能审核 + 合规审核） | 侧载验证先行 |

## 3. 审核注意点

- 应用为「本地工具 + 远程数据展示」: 需要有明确的登录/数据来源说明 (README 已含)。
- 中英文案需覆盖应用可见文本 (M4 已完成核心 i18n 字典; 页面级文案后续同步)。
- 上架后建议启用「应用市场版本升级」向用户推送新版本 (替代侧载阶段 GitHub 更新检查)。

## 4. CI (可选, 跟随 android/macos 工作流模式)

- `release-harmonyos.yml`: tag `v*-harmony` 触发; Ubuntu runner + 鸿蒙 Command Line Tools
  (含 hvigor/ohpm) + SDK (API 24); 签名材料走 Secrets; 产物附 Releases。
- 备注: GitHub Actions 公网 runner 需能访问华为 SDK 下载源; 若受限可先在本地/自建 runner 构建。

## 5. 真机侧载 (正式签名前的中间验证)

- DevEco 调试签名构建 HAP → `hdc install entry-default-signed.hap` 安装到鸿蒙 NEXT 设备
  (需在设备「开发者选项」开启 USB 调试; PC 形态设备同)。