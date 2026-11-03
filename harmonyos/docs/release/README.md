# GoGauge HarmonyOS 上架材料包（release/）

> 本目录是 GoGauge 上架 AppGallery 所需的**全部文案、隐私政策、元数据与图片资产**，配合 `../release-guide.md`（逐步指南）与 `../agc-release-checklist.md`（核对清单）使用。
> 目标：华为应用市场（AppGallery / HarmonyOS NEXT）· 包名 `io.github.yphyphyph.gogauge` · 版本 1.0.0 / 1000000。

## 目录内容与状态

| 文件/目录 | 内容 | 状态 | 使用方式 |
| --- | --- | --- | --- |
| `app-intro-zh.md` | 应用名称、一句话简介（17 字符）、长描述、分类/标签/年龄分级建议、版权/开发者信息 | ✅ 可直接用 | 按 §1/§2 粘贴到 AGC；替换 `<待填：邮箱>` 等 |
| `app-intro-en.md` | 英文版同字段 | ✅ 可直接用 | AGC 配置 English 时使用 |
| `privacy-policy-zh.md` | 隐私政策全文（中文） | ⚠️ 需替换占位符 + 托管 | 托管到 HTTPS 后填 AGC「隐私政策网址」；正文同步进应用内 `PrivacyText.ets` |
| `privacy-policy-en.md` | 隐私政策全文（英文） | ⚠️ 同上 | 英文语言/海外可选 |
| `permission-rationale.md` | INTERNET 权限用途、隐私标签/隐私声明要点、审核备注模板 | ✅ 参考 | AGC 隐私标签、审核备注填写依据 |
| `release-notes-1.0.0.md` | 首版发布说明（中英 + 版本号对照） | ✅ 可直接用 | AGC「新版本特性」、GitHub Release |
| `appgallery-metadata.md` | **逐字段填写表**：基础信息/分类标签/隐私/截图规格与文件名映射/图标/审核信息/风险/用户自备清单 | ✅ 主操作手册 | 填 AGC 时对照 |
| `assets/icon-1024.png` | AppGallery 应用图标（1024×1024，品牌版，PNG ≤3MB） | ✅ 主推 | AGC 应用图标；需与包内图标一致（包内已换同源品牌分层图标） |
| `assets/icon-216.png` | 216×216 备用图标 | ✅ | AGC 提示 216 尺寸时用 |
| `assets/icon-512.png` | 512×512 备用 | ✅ | 部分后台位需要时用 |
| `assets/icon-1024-package-match.png` | 以旧 512 占位图标放大的兜底图标 | 🟡 兜底 | 仅当最终 HAP 图标未替换时使用 |
| `assets/promo-2160x1080.png` / `promo-1080x2160.png` | 品牌宣传图（横/竖） | ✅ | 官网/README/推广位；**不是**上架介绍截图 |
| `assets/generate-assets.py` | 上述图片的可复现生成脚本 | ✅ | `python3 assets/generate-assets.py` |
| `tools/prep-screenshots.py` | 截图转换（模拟器原图 → AGC 规格；自动排除 `_degraded/` 与 `smoke-*`，pad 补边色自动采样） | ✅ 已实测 | `--all` 读 `store-assets/screenshots/`，输出 `screenshots-upload/` |
| `screenshots-upload/` | 截图转换产物（AGC 规格，已生成 13 张） | ✅ 手机 9×1080×1920 + PC 4×1920×1080 | 直接按 `appgallery-metadata.md` §5.2 顺序上传；平板不提供（v1.0 不勾平板） |

## 快速开始（5 步）

```bash
cd /Users/yizhiwang/Desktop/opencode/gousage/opencode-go-gauge

# 1) 生成/更新图标与宣传图
.venv/bin/python3 harmonyos/docs/release/assets/generate-assets.py

# 2) 把模拟器截图转成 AGC 规格（流水线已产出 13 张，可随时重跑；已生成 9 phone + 4 pc）
.venv/bin/python3 harmonyos/docs/release/tools/prep-screenshots.py --all

# 3) 替换隐私政策占位符（开发者名称/邮箱/生效日期），然后托管到 HTTPS
grep -n "<待填" harmonyos/docs/release/privacy-policy-zh.md

# 4) 构建 Release .app（需先注入发布证书/Profile 签名）
cd harmonyos && ./scripts/build.sh app

# 5) 按 appgallery-metadata.md 填写 AGC → 上传 .app → 提交审核
```

## 提交前必须替换的占位符（`<待填：…>`）

| 在哪些文件 | 内容 |
| --- | --- |
| `privacy-policy-zh.md` / `privacy-policy-en.md` / 应用内 `PrivacyText.ets` | 开发者/运营者名称（**= AGC 实名主体**）、联系邮箱、生效/更新日期、联系地址（可选） |
| `app-intro-zh.md` / `app-intro-en.md` | 联系邮箱、开发者名称、官网（可选） |
| `appgallery-metadata.md` | 项目名、客服邮箱/电话、隐私政策 URL、版权证书、测试账号、负责人信息 |
| `release-guide.md` | 签名材料路径、密码、CSR Subject、应用负责人信息 |
| `release-notes`（新版本时） | 版本号与版本说明 |

## 关键限制（来自华为官方文档，2026-10 版）

- 一句话简介：中文 **≤17 字符**；应用介绍 **≤8000 字符**；新版本特性（中国大陆）**≤500 字符**。
- 应用图标：216×216 或 1024×1024 PNG **≤3MB**，正方形，**必须与包内图标一致**。
- 截图：手机 1080×1920（9:16）或 1920×1080（16:9），平板 1920×1280 / 1280×1920，PC 1920×1080，**每设备 3–10 张、≤5MB/张**。
- 上架包：**Release `.app`（App Pack）**，不是 HAP；必须发布证书 + 发布 Profile 签名。
- 中国大陆发行：**APP 备案** + 手机应用**版权证书**；隐私政策需含开发者名称、应用名称一致，并提供简体中文版。
- 审核若需登录：必须提供**可用的测试账号**（或自测视频）。

以 AGC 后台实际提示为准；官方链接见 `appgallery-metadata.md` 顶部与 `../release-guide.md` 附录 C。
