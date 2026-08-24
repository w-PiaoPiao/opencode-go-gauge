# GoGauge HarmonyOS — 验证与交接总结 (M1–M6)

> 本文件汇总全部可自动验证的证据与剩余需 GUI/账号执行的交接步骤。

## 1. 已自动验证的证据

| 项 | 命令 | 结果 |
| --- | --- | --- |
| Debug 构建 | `./scripts/build.sh hap` (环境探测见脚本) | ✅ BUILD SUCCESSFUL → `entry/build/default/outputs/default/entry-default-unsigned.hap` |
| Release 构建 | `./hvigorw --mode module -p product=default assembleHap -p buildMode=release` | ✅ BUILD SUCCESSFUL (未混淆, 签名待注入) |
| 本地单元测试 | `./scripts/build.sh test` | ✅ **Tests run: 21, Failure: 0, Error: 0, Pass: 21, Ignore: 0** |
| 签名注入脚本 | `HAP_* 环境变量 bash scripts/inject-signing.sh` | ✅ 冒烟通过 (hex 编码 `abc123456`→`616263313233343536`, 已还原配置) |
| Git 卫生 | `git ls-files` | ✅ 56 个 harmonyos 文件入库, 无 oh_modules/.test/构建产物混入 |
| 工程对账 | M1–M6 里程碑 | 代码/材料/CI 全部落库 (见本文件 §3) |

单元测试覆盖: QuotaParser(4) / UsageParser(3) / Fmt(7) / 活跃账号策略(7) ——
与安卓版用例逐条对应 (GET/POST 双格式、null→0、字段顺序双兼容、钳制、格式化边界)。

## 2. 运行验证交接 (需 DevEco GUI + 华为账号)

**模拟器** —— 系统镜像已就位!
- 镜像: `~/Library/Huawei/Sdk/system-image/HarmonyOS-6.1.1/phone_all_arm` (+`pc_all_arm` 2in1 形态), host arm64 匹配
- 步骤: ① DevEco Studio 打开 `harmonyos/` ② Device Manager 用上述镜像创建设备 (手机/2in1)
  ③ Run 'entry' → 欢迎页登录 (或设置页「注入模拟数据 (调试)」先出数据验证图表)
  ④ 截图: 首页/统计/记录/设置 × 亮/暗 (上架材料)
- 注: CLI 无法引导该模拟器 (QEMU 内嵌于 GUI 二进制且需先建 AVD 实例) — 已确认此限制

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
| M6 | 材料清单 docs/agc-release-checklist.md · 单测 21/21 · 工具脚本 · CI release-harmonyos.yml | ✅ 代码侧完成; 证书签发/上架/运行验证为账号与 GUI 侧交接项 |

## 4. 关键产物路径

- 工程根: `harmonyos/`
- HAP: `harmonyos/entry/build/default/outputs/default/entry-default-unsigned.hap`
- 单测: `harmonyos/entry/src/test/` (结果 `entry/.test/default/intermediates/test/coverage_data/test_result.txt`)
- 上架清单: `harmonyos/docs/agc-release-checklist.md`
- 工具: `harmonyos/scripts/{build.sh,install.sh,inject-signing.sh,gen_icons.py}`
- CI: `.github/workflows/release-harmonyos.yml` (tag `v*-harmony`)