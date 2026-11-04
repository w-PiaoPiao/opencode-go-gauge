# GoGauge HarmonyOS 上架发布指南（从零到 AppGallery 在架）

> 适用工程：`harmonyos/`（ArkTS + ArkUI，Stage 模型）
> 应用：**GoGauge**　包名：`io.github.yphyphyph.gogauge`　版本：`1.0.0` / `versionCode 1000000`
> 目标：华为应用市场（AppGallery / HarmonyOS NEXT）
> 环境基线：DevEco Studio **6.1.1**（HarmonyOS SDK 6.1.1 / API 24）、macOS；命令均在本仓库 `harmonyos/` 目录下执行（标注除外）。
>
> **官方文档会更新，本文所有规格以 AGC 后台实际提示为准。** 主要官方来源见文末附录 C。

---

## 0. 最快路径（TL;DR，10 步）

1. 注册并实名认证华为开发者账号 → 2. 完成 **APP 备案** + 准备 **软著/版权证书**（并行、周期长）→ 3. AGC 创建应用（包名绑定）→ 4. DevEco 生成密钥 `.p12` + `.csr` → 5. AGC 申请**发布证书** `.cer` → 6. AGC 申请**发布 Profile** `.p7b` → 7. 配置签名并构建 **Release `.app`** → 8. AGC 上传 `.app`（合法性检测 + 上架自检）→ 9. 填写应用信息/隐私/版权/备案/审核信息 → 10. 提交审核、发布。

> ⚠️ 三个最容易踩的坑：
> 1. **上架包是 `.app`（App Pack），不是 `.hap`**。HAP 只用于本地调试安装。
> 2. **必须用「发布证书 + 发布 Profile」签名**；DevEco 的「自动签名」生成的是**调试证书**，只能真机调试，不能上架。
> 3. **商店图标必须与包内图标一致**；应用内必须有可点击的隐私政策入口，首次启动/登录前要有隐私政策弹窗（见 §9 与 `release/appgallery-metadata.md` §7）。

---

## 1. 准备清单

### 1.1 账号与资质（用户自行完成，均需时间，建议最先启动）

| # | 事项 | 说明 | 参考 |
| --- | --- | --- | --- |
| 1 | 华为开发者账号 + 实名认证 | 个人/企业均可；实名主体名称将用于隐私政策与版权信息 | <https://developer.huawei.com/consumer/cn/doc/app/agc-help-create-app-0000002247955506> |
| 2 | **APP 备案（工信部核准）** | 在接入商（华为云/阿里云等）备案系统选择「鸿蒙」平台并填写包名 `io.github.yphyphyph.gogauge`；未备案影响搜索/展示 | <https://developer.huawei.com/consumer/cn/doc/app/50130> |
| 3 | **应用版权证书**（中国大陆 + 手机设备时必选） | 通常为计算机软件著作权登记证书（软著）或代理授权；JPG/PNG/BMP，≤15MB/张，最多 10 张 | <https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-copyright-0000002278981450> |
| 4 | 隐私政策托管 URL | 公网 HTTPS 可访问，内容与 `release/privacy-policy-zh.md` 一致；可用 GitHub Pages / 自有域名 / 对象存储静态站 | <https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-privacy-state-0000002278878296> |
| 5 | 客服邮箱（可选电话/官网） | 写进隐私政策与 AGC | — |
| 6 | 审核测试账号（OpenCode Go） | 审核人员需登录后验证功能；无账号时准备 `.mp4` 自测视频 | <https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-reviewinfo-0000002320780365> |

### 1.2 本机工具

```bash
# DevEco Studio 6.1.1（含 SDK 6.1.1 / API 24、hvigor、Node、JBR）
export DEVECO_HOME="/Applications/DevEco-Studio.app"
export DEVECO_SDK_HOME="$DEVECO_HOME/Contents/sdk"
export NODE_HOME="$DEVECO_HOME/Contents/tools/node"
export JAVA="$DEVECO_HOME/Contents/jbr/Contents/Home/bin/java"
export HAP_SIGN_TOOL="$DEVECO_SDK_HOME/default/openharmony/toolchains/lib/hap-sign-tool.jar"
export PACKING_TOOL="$DEVECO_SDK_HOME/default/openharmony/toolchains/lib/app_packing_tool.jar"

# 自检：版本与工具是否存在
"$JAVA" -version
ls -lh "$HAP_SIGN_TOOL" "$PACKING_TOOL"
./hvigorw -v
```

> 以上路径已在当前工程环境中验证存在（`hap-sign-tool.jar`、`app_packing_tool.jar`、JBR 21）。

### 1.3 本仓库已有脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/build.sh hap` | 构建 HAP（调试/本地安装，产物 `entry/build/default/outputs/default/entry-default-unsigned.hap` 或 `-signed.hap`） |
| `scripts/build.sh app` | 构建 **Release `.app`（App Pack，上架用）**，产物 `build/outputs/default/*.app`（工程根 build 目录）；需先配置签名（见 §5） |
| `scripts/build.sh test` | 运行本地单元测试（hypium；结果见 `entry/.test/default/intermediates/test/coverage_data/test_result.txt`） |
| `scripts/gen-signing-material.js` | 生成 hvigor 兼容的签名材料（`material/` + 加密密码 hex；hvigor 6.x 不接受明文密码） |
| `scripts/inject-signing.sh` | 把签名材料/路径/加密密码注入 `build-profile.json5`（配合上一个脚本使用） |
| `scripts/install.sh [hap]` | `hdc install` + 启动应用（真机/模拟器侧载验证） |
| `scripts/gen_icons.py` | 生成占位应用图标（正式上架建议换品牌分层图标） |
| `docs/release/tools/prep-screenshots.py` | 截图批量转换为 AGC 要求尺寸 |
| `docs/release/assets/generate-assets.py` | 生成 AppGallery 图标与宣传图 |

---

## 2. 阶段一：AGC 创建 HarmonyOS 应用（APP ID）

前置：账号已实名认证。

1. 登录 **HarmonyOS 开发者中心**（AppGallery Connect，<https://developer.huawei.com/consumer/cn/>）。
2. 进入「**开发者管理**」→ 左侧「**ID、证书和 Profile**」→「**APP ID**」→ 左上角下拉选择 **HarmonyOS** → 右上角「**创建**」。
3. 填写「新建 APP ID」：

| 字段 | 本应用取值 |
| --- | --- |
| 应用类型 | HarmonyOS 应用 |
| 应用名称 | `GoGauge`（须与包内 `app_name` 一致） |
| 应用包名 | `io.github.yphyphyph.gogauge`（**创建后不可修改**，须与 `AppScope/app.json5` 的 `bundleName` 一致） |
| 应用分类 | 应用 |
| 支持设备 | **手机、PC/2in1**（v1.0 不勾选平板；见下方说明） |
| 默认语言 | 简体中文 |
| 应用所属项目 | 新建或选择已有项目 |

4. 点「确认」→ 生成 APP ID。后续在「**应用管理**」中即可看到该应用。

> **支持设备决策（v1.0，Lead 已拍板）**：包内 `deviceTypes` 为 `phone/tablet/2in1`，但 AGC **只勾选「手机 + PC/2in1」**，不单独勾选平板。原因：本机无 Tablet 系统镜像，无法产出真实平板截图；按官方规则「当设备类型包含手机时，即便包里未声明平板，应用也会默认以兼容的方式分发到 HarmonyOS NEXT 平板」，平板用户仍可通过兼容方式安装使用。包内声明范围 ≥ AGC 勾选范围，符合提交规则。后续版本补齐平板素材后可再勾选平板（发布后只能增加设备）。
>
> 名称/包名规则：包名至少三段、仅字母数字下划线、7–128 字符；不能使用保留字（`oh`/`ohos`/`harmony`/`harmonyos`/`openharmony`/`system`）；不能与其他应用（含 Android）重名。若名称被占用需更换（会连带影响包内 label、隐私政策与所有文案）。
> 官方文档：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-create-app-0000002247955506>

---

## 3. 阶段二：生成密钥库（.p12）与证书请求文件（.csr）

### 方式 A（推荐，图形界面）：DevEco Studio

1. 打开工程 `harmonyos/`。
2. 主菜单 **Build → Generate Key and CSR**。
3. 新建密钥库（或 `Select an existing key` 选择已有 `.p12`）：
   - **Keystore Name**：如 `gogauge-release.p12`（仅字母/数字/`_`/`-`/`.`）；
   - **Key store password**：至少 8 位、含大写/小写/数字/特殊符号中的**两种以上**（请务必记录并离线备份）；
   - **Alias**：如 `gogauge`（务必记录）；
   - **Validity (years)**：建议 ≥25 年；
   - 其余证书主体信息选填。
4. 下一步生成 **CSR**：文件名如 `gogauge-release.csr`，选择保存路径 → Finish。
5. 得到 `gogauge-release.p12` + `gogauge-release.csr`。

> 官方文档：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-signing-manual>（手动签名）

### 方式 B（命令行/CI，可复现）：`hap-sign-tool generate-keypair` + `generate-csr`

```bash
cd /Users/yizhiwang/Desktop/opencode/gousage/opencode-go-gauge/harmonyos
export DEVECO_HOME="/Applications/DevEco-Studio.app"
export JAVA="$DEVECO_HOME/Contents/jbr/Contents/Home/bin/java"
export HAP_SIGN_TOOL="$DEVECO_HOME/Contents/sdk/default/openharmony/toolchains/lib/hap-sign-tool.jar"

# ⚠️ 以下密码/主体信息为占位符，请替换；产物请放在仓库外或已被 .gitignore 忽略的目录
STORE_PWD='<待填：至少8位，两类以上字符>'
KEY_PWD="$STORE_PWD"          # 与密钥库密码保持一致（推荐）
KEY_ALIAS='gogauge'
P12='/secure/path/gogauge-release.p12'
CSR='/secure/path/gogauge-release.csr'

# 1) 生成 ECC P-256 密钥对（NIST-P-256 为 HarmonyOS 推荐）
"$JAVA" -jar "$HAP_SIGN_TOOL" generate-keypair \
  -keyAlias "$KEY_ALIAS" -keyPwd "$KEY_PWD" \
  -keyAlg ECC -keySize NIST-P-256 \
  -keystoreFile "$P12" -keystorePwd "$STORE_PWD"

# 2) 生成 CSR（Subject 按实际主体修改；个人开发者可只保留 C/CN）
"$JAVA" -jar "$HAP_SIGN_TOOL" generate-csr \
  -keyAlias "$KEY_ALIAS" -keyPwd "$KEY_PWD" \
  -subject "C=CN,O=<待填：公司/个人名称>,OU=<待填：部门>,CN=GoGauge" \
  -signAlg SHA256withECDSA \
  -keystoreFile "$P12" -keystorePwd "$STORE_PWD" \
  -outFile "$CSR"
```

> `hap-sign-tool` 支持的子命令：`generate-keypair` / `generate-csr` / `generate-cert` / `generate-app-cert` / `generate-profile-cert` / `sign-profile` / `sign-app` / `verify-app` 等。查看帮助：`"$JAVA" -jar "$HAP_SIGN_TOOL" -help`。

---

## 4. 阶段三：在 AGC 申请发布证书（.cer）与发布 Profile（.p7b）

### 4.1 申请发布证书

1. 「开发者管理」→「**ID、证书和 Profile**」→「**证书**」→「**新增证书**」。
2. 填写：
   - 证书名称：如 `gogauge-release-cert`（≤100 字符）；
   - 证书类型：**发布证书**；
   - 选取证书请求文件（CSR）：上传上一阶段生成的 `.csr`。
3. 提交 → 状态「生效」→ 点「**下载**」得到 `.cer`（如 `gogauge-release-cert.cer`）。

要点：
- 每个账号最多 **3 个发布证书**；实名开发者发布证书有效期 **3 年**。
- 证书到期不影响已上架应用，但更新版本时用过期证书签名会失败 → 需更新证书与 Profile。
- **更新证书时需使用同一 CSR（同一密钥库）生成的证书**，并用新证书更新 Profile。

> 官方文档：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-cert-0000002283336729>

### 4.2 申请发布 Profile

1. 「开发者管理」→「**ID、证书和 Profile**」→「**Profile**」→ 右上角「**添加**」。
2. 填写：
   - 应用名称：选择刚创建的 `GoGauge`（包名自动带出 `io.github.yphyphyph.gogauge`）；
   - Profile 名称：如 `gogauge-release-profile`（≤100 字符）；
   - 类型：**发布**；
   - 选择证书：选择 4.1 的发布证书。
   - （本应用无 ACL 权限，无需勾选「受限 ACL 权限」。）
3. 点「添加」→ 生效 → 点「**下载**」得到 `.p7b`（如 `gogauge-release-profile.p7b`）。

> 官方文档：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-profile-0000002248341090>
> 每应用最多 100 个 Profile。

---

## 5. 阶段四：签名配置（三条路径，按场景选）

### 路径 A：DevEco **自动签名**（仅调试/真机验证，❌ 不能上架）

适用：本机真机/模拟器调试、跑通 UI 与截图流水线。

1. 连接设备（真机开启「开发者选项 → USB 调试」；模拟器由 DevEco Device Manager 启动）。
2. **File → Project Structure… → Project → Signing Configs**
3. 勾选 `Automatically generate signature`（未登录先 `Sign In`）；DevEco 会按包名自动申请调试证书/调试 Profile，生成本地 `.p12/.cer/.p7b` 并写入 `build-profile.json5`。
4. 直接 Run 即可。

> ⚠️ 自动签名生成的是**调试证书 + 调试 Profile**，AGC 不接受调试签名的包；上架必须走路径 B 或 C。
> 本机模拟器接受**未签名 HAP**（`hdc install` 可直接装），调试阶段也可完全跳过签名。
> 官方文档：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-signing-auto>

### 路径 B：DevEco 图形界面**手动发布签名**（推荐给个人开发者）

1. 把 4.1 的 `.cer`、4.2 的 `.p7b`、3.1 的 `.p12` 放到本机**仓库外**的安全目录（或 `harmonyos/` 下但已被 `.gitignore` 排除；`*.p12/*.p7b/*.cer/*.csr` 已在 `harmonyos/.gitignore` 中）。
2. **File → Project Structure… → Project → Signing Configs**
3. **取消勾选** `Automatically generate signature` 与 `Associate with registered application`。
4. 填写：

| 字段 | 值 |
| --- | --- |
| Store file | `…/gogauge-release.p12` |
| Store password | 密钥库密码（与生成时一致） |
| Key alias | `gogauge` |
| Key password | 密钥密码（与 Store password 一致） |
| Sign alg | `SHA256withECDSA`（固定） |
| Profile file | `…/gogauge-release-profile.p7b` |
| Certpath file | `…/gogauge-release-cert.cer` |

5. 点 `Apply`。此时工程级 `build-profile.json5` 的 `app.signingConfigs` 会被写入（DevEco 自动加密密码字段）。
6. **Build → Build Hap(s)/APP(s) → Build APP(s)**，得到可上架的 **`.app`**。

> 「Store file / Profile file / Certpath file」支持相对工程根目录的路径。三者必须配套，否则签名失败。
> 若你的 DevEco Studio 支持 **Build → Upload Product**（文档标注 26.0.0 及以上），也可在构建 `.app` 后上传时由 AGC 云管理证书自动重签名（支持使用开发者证书），见 <https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-publish-app>。本工程验证环境为 6.1.1，按上面的手动签名流程即可。

### 路径 C：命令行签名构建（可复现，适合自动化/无 GUI 环境）

> **hvigor 6.x 不接受明文密码**：`build-profile.json5` 里的 `storePassword/keyPassword`
> 必须是 AES-128-GCM 密文（hex），且 `.p12` **同目录**下必须有 `material/`（`fd/ac/ce`）——
> hvigor 用 material 派生密钥解密密码。直接写明文/普通 hex 会报
> `Signature material verification failed` 或 `KEY_PASSWORD_VALID_FAILED`。
> 本仓库脚本按 hvigor `DecipherUtil` 格式生成 material 与密文（已实测可通过 hvigor 材料校验）。

```bash
cd harmonyos
# 0) 把 AGC 下载的发布材料放到一个安全目录（示例），三者必须配套：
#    gogauge-release.p12 / gogauge-release.p7b / gogauge-release.cer
SIGN_DIR="$HOME/.gogauge-signing"          # 自选，勿提交仓库
export P12_PASSWORD="<待填：p12 密码>"
export KEY_PASSWORD="<待填：key 密码>"

# 1) 生成 hvigor 兼容 material + 加密密码（material 会生成在 p12 同目录）
node scripts/gen-signing-material.js \
  --signing-dir "$SIGN_DIR" \
  --store-password "$P12_PASSWORD" --key-password "$KEY_PASSWORD" --force

# 2) 注入签名配置（写入 build-profile.json5，含绝对路径与加密密码）
export HAP_STORE_FILE="$SIGN_DIR/gogauge-release.p12"
export HAP_KEY_ALIAS="<待填：key alias>"
export HAP_PROFILE_P7B="$SIGN_DIR/gogauge-release.p7b"
export HAP_SIGN_CER="$SIGN_DIR/gogauge-release.cer"
export HAP_SIGNING_PASSWORDS_JSON="$SIGN_DIR/signing-passwords.json"
bash scripts/inject-signing.sh

# 3) 构建 Release App Pack（.app）
./scripts/build.sh app
# 产物: build/outputs/default/harmonyos-default-signed.app（成功签名时文件名含 signed）
```

注入后 `build-profile.json5` 形如（密码字段为**密文 hex**；提交前务必恢复该文件）：

```json5
{
  "app": {
    "signingConfigs": [{
      "name": "release", "type": "HarmonyOS",
      "material": {
        "storeFile": "/secure/path/gogauge-release.p12",
        "storePassword": "<AES-GCM 密文 HEX>",
        "keyAlias": "gogauge",
        "keyPassword": "<AES-GCM 密文 HEX>",
        "signAlg": "SHA256withECDSA",
        "profile": "/secure/path/gogauge-release.p7b",
        "certpath": "/secure/path/gogauge-release.cer"
      }
    }],
    "products": [{ "name": "default", "signingConfig": "release", "compatibleSdkVersion": "6.1.1(24)", "targetSdkVersion": "6.1.1(24)", "runtimeOS": "HarmonyOS" }]
  }
}
```

> ⚠️ 若证书/Profile/私钥三者不配套，签名阶段会报 `verify certificate chain failed` 或
> `Certificate format is incorrect`：请确认 `.cer` 是**发布证书链**（与 p12 私钥匹配）、
> `.p7b` 是用该证书签发的发布 Profile 且 `bundle-name` 为本应用包名。
>
> ⚠️ 本机实测：`gen-signing-material.js` 生成的 material 已能通过 hvigor 的材料/密码解密校验；
> 最终签名能否成功取决于用户 AGC 材料是否配套（本仓库无用户证书，无法端到端代签）。

> CI 说明：`.github/workflows/release-harmonyos.yml` 只产 unsigned 产物（GitHub Release 用）；
> 签名密钥不放 CI。若要在 CI 签名，需把上述 `SIGN_DIR`（p12 + material + p7b + cer）与密码
> 作为 secrets 以 base64 落盘后执行同样两步，并校验产物为 `*-signed.app`。

### 路径 D：`hap-sign-tool` 手动签名 HAP（本机安装/侧载用；AGC 不接受 HAP）

当只有**未签名 HAP**、需要真机安装验证时：

```bash
cd /Users/yizhiwang/Desktop/opencode/gousage/opencode-go-gauge/harmonyos
export JAVA="/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home/bin/java"
export HAP_SIGN_TOOL="/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/lib/hap-sign-tool.jar"

# 先构建未签名 HAP（或使用已有产物）
./hvigorw --mode module -p product=default assembleHap --no-daemon

"$JAVA" -jar "$HAP_SIGN_TOOL" sign-app \
  -mode localSign \
  -keyAlias "gogauge" -keyPwd "<待填：密钥密码>" \
  -appCertFile "/secure/path/gogauge-release-cert.cer" \
  -profileFile "/secure/path/gogauge-release-profile.p7b" \
  -inFile "entry/build/default/outputs/default/entry-default-unsigned.hap" \
  -signAlg SHA256withECDSA \
  -keystoreFile "/secure/path/gogauge-release.p12" -keystorePwd "<待填：密钥库密码>" \
  -outFile "entry/build/default/outputs/default/entry-default-signed.hap" \
  -compatibleVersion 24 -signCode 1

# 安装到设备（需 hdc 可连设备）
HDC="/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc"
"$HDC" install -r entry/build/default/outputs/default/entry-default-signed.hap
"$HDC" shell aa start -a EntryAbility -b io.github.yphyphyph.gogauge
```

参数要点（来自本机 `hap-sign-tool.jar -help`）：
- `-mode localSign`：本地证书签名；`-appCertFile` 为发布证书；`-profileFile` 为 Release Profile（`.p7b`）；
- `-compatibleVersion`：按 `compatibleSdkVersion` 填 **24**；`-signCode 1` 对 HAP 启用代码签名；
- `sign-app` 仅支持 `.hap/.bin/.elf`，**不支持 `.app`** —— 上架 `.app` 请用路径 B/C 的 hvigor 签名构建。

> ⚠️ 不要把调试签名/自签名 HAP 改名成 `.app` 上传，AGC 会判定签名或包格式不合法。

---

## 6. 阶段五：Release 构建与自检

### 6.1 构建前检查

1. `AppScope/app.json5`：`versionCode` / `versionName` 已递增（首次为 `1000000` / `1.0.0`）；`bundleName` 正确。
2. `entry/src/main/module.json5`：`deviceTypes` 与 AGC 勾选设备一致；权限仅 `ohos.permission.INTERNET`。
3. `entry/build-profile.json5`：`release` 构建 `obfuscation.enable=false`（当前为关闭；如需混淆，先回归测试再开）。
4. 包内 `debug` 不为 true（release 构建自动保证；可用 `app_unpacking_tool.jar` 或 DevEco 检查）。
5. 图标：确认包内图标即商店要展示的图标（见 `release/appgallery-metadata.md` §6）。

### 6.2 本地单元测试

```bash
cd /Users/yizhiwang/Desktop/opencode/gousage/opencode-go-gauge/harmonyos
./scripts/build.sh test
# 查看结果（通过数/失败数）
cat entry/.test/default/intermediates/test/coverage_data/test_result.txt 2>/dev/null
```

> 单测覆盖 QuotaParser / UsageParser / Fmt / 活跃账号策略等。**具体用例数以最新一次运行为准**：当前 `./scripts/build.sh test` 为 **Tests run: 35, Failure: 0, Error: 0, Pass: 35**。

### 6.3 构建 Release `.app`

- GUI：**Build → Build Hap(s)/APP(s) → Build APP(s)**；
- CLI（推荐）：`./scripts/build.sh app`；等价手动命令 `./hvigorw assembleApp -p product=default -p buildMode=release --no-daemon`；
- 产物：`build/outputs/default/*.app`（本机实测 `harmonyos-default-unsigned.app`；注入签名后为 signed）。
- ⚠️ **构建副作用**：`assembleApp`（release）会把 `entry/build/default/outputs/default/entry-default-unsigned.hap`
  覆盖成 release 版（`BuildProfile.DEBUG=false`，无调试入口/无 demo 数据）。如果需要调试包或商店截图
  （demo 模式），在 `assembleApp` 之后重新执行 `./scripts/build.sh hap`。

### 6.4 上架前自检（强烈建议，能显著降低驳回率）

1. **DevEco AppAnalyzer 上架前体检**（DevEco 6.0.0+）：菜单 **Tools → AppAnalyzer** → 「上架前体检」→ 选择待上架产物 + 调试签名 → 体检；100 分可 **Sync To AG** 上传报告供审核参考。官方：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-app-analyzer-before-appgallery>
2. **DevEco Testing 上架预检（本地）**：DevEco Testing → 测试服务 → 上架预检 → 应用上架预检（本地），覆盖兼容性/性能/稳定性/UX/功耗。官方：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/publish-testing>
3. 本仓库脚本冒烟：`./scripts/build.sh hap`、`scripts/install.sh`（真机）。

---

## 7. 阶段六：AGC 上传软件包

1. 「**应用管理**」→ 选择 `GoGauge` → 左侧「**应用上架 → 软件包管理**」→ 右上角「**上传**」。
2. 选择使用场景：**测试和正式上架**（正式发布必须选此项；仅测试选「仅测试」）。
3. 上传 **`.app`** 文件，等待解析完成。
4. 查看结果：
   - **合法性 = 已达标**：可提交上架；
   - **待优化**：允许提交，但存在驳回风险（点「报告」按修改意见优化）；
   - **不通过**：不可发布（点错误码/报告修复后重新上传）。
5. （推荐）点「**启动自检**」，等待邮件通知 → 查看上架自检报告（兼容性/稳定性/性能/功耗/UX/隐私）。

> 官方文档：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-upload-pkg-0000002277983368>
> 包体限制：APP 包 ≤4GB；手机/平板/PC 单 HAP ≤4GB；API Level ≥10（本工程 24）；包内不得含调试信息（`debug=true`）。

---

## 8. 阶段七：填写应用信息与版本信息

逐字段内容见 **`release/appgallery-metadata.md`**（含字数、规格、勾选项与来源链接），本节约 20 分钟即可填完。要点顺序：

1. **应用信息**：可本地化基础信息（名称/图标，多语言分别保存）→ 支持设备（**手机 + PC/2in1**，v1.0 不勾平板）→ 应用分类/标签 → 开发者服务信息。
2. **版本信息**（待发布版本）：
   - 可本地化基础信息：应用介绍、一句话简介、新版本特性、介绍截图/视频（见 `appgallery-metadata.md` §5）；
   - 隐私声明：自定义隐私政策 URL（或隐私托管）；
   - 隐私说明：本应用仅 INTERNET normal 权限，预计无需填写（如后台提示，用 `permission-rationale.md` §2）；
   - 隐私标签信息录入：如实填写（见 `permission-rationale.md` §3）；
   - 内容分级：填问卷（预期 3+）；
   - AI 功能声明：不涉及生成式 AI 服务；
   - 版权信息：上传版权证书（大陆 + 手机必选）；
   - 核准（备案）信息：按备案结果填写；
   - 应用审核信息与联系方式：勾选「需要登录进行审核」+ 提供测试账号/自测文件 + 备注（模板见 `permission-rationale.md` §5）。
3. **上架时间**：立即上架或指定时间。
4. 右上角「**提交审核**」（可选择智能预检）。

> 版本状态流转：准备提交 → 正在等待审核 → 正在审核 → 待上架/已上架；被驳回为「待修改」，按「审核报告」修改后可重新提交。催审/撤销见 <https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-push-0000002312626049>。

---

## 9. 阶段八：审核前必须补齐的代码侧事项（Lead 已安排实现，上架前逐项确认）

以下事项不属于本文档写作范围，但缺了大概率被驳回。相关代码已由 Lead/UI 实现（2026-11），**提交审核前仍需按验收标准人工复核**：

| # | 事项 | 依据 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | 应用内可点击的隐私政策页 | 应用审核指南 7.1：AGC 平台**及应用内部**均需提供可便捷查看的隐私政策链接 | 新增 `pages/PrivacyPage`；入口：欢迎页底部 + 设置 → 关于 → 隐私政策；正文与托管 URL 内容一致 | ✅ 已实现（`pages/PrivacyPage.ets` + `common/legal/PrivacyText.ets`；上架前人工复核入口可点开） |
| 2 | 首次启动隐私政策弹窗 | 审核指南 7.5 / 审核 Checklist：未同意前不得收集个人信息；弹窗须有「同意/拒绝」，不得默认勾选 | 首次启动弹窗；同意后才允许进入 opencode.ai 登录，同意状态写入本地 preferences（可再次查看）；拒绝则不得登录/联网 | ✅ 已实现（`Index.ets` 首启弹窗 + `AppPrefs` 同意状态；上架前复核“拒绝后无法登录”） |
| 3 | 商店图标与包内图标一致 | 应用名称/图标一致性检测 | 包内已替换品牌分层图标（`AppScope/resources/base/media/layered_image.json` + `foreground/background`）；商店用 `release/assets/icon-1024.png`（同源） | ✅ 已实现（上架前比对桌面图标与商店图标） |
| 4 | 第三方账号登录未提供华为账号登录选项 | 审核指南 3.16 | 产品决策不接入 Account Kit；在审核备注说明「本应用是 OpenCode Go 第三方客户端，无自有账号体系，登录即 OpenCode 官方授权」，并列为已知审核风险 | **待审核验证** |
| 5 | 审核测试账号 | 审核信息要求（需登录才可用的功能必须提供测试账号） | 提供一组可用的 OpenCode Go 测试账号/密码；无法提供时提交 `.mp4` 自测视频 | **用户自备（必须）** |

补充说明：
- 应用内隐私政策正文已内嵌为 `common/legal/PrivacyText.ets`（开发者身份=AGC 实名主体「王逸之」、联系方式=开源仓库 Issues，无 `<待填>` 占位符）。托管隐私政策 URL 使用仓库 `docs/privacy-policy-zh.html`（GitHub Pages），内容与本文件一致；若 AGC 实名主体变化，需同步替换该文件并重新构建。
- **AGC 隐私政策 URL 仍需用户自行托管**（GitHub Pages / 个人站点 / 静态对象存储均可，HTTPS 公网可访问），并保证托管内容与应用内展示内容一致；只做应用内页面、不提供 AGC URL 无法通过审核。
- 若 1/2 未完成，**不要提交审核**——这是隐私合规的高频驳回项。

---

## 10. 阶段九：常见驳回原因与排查

| 驳回/问题 | 常见原因 | 排查与修复 |
| --- | --- | --- |
| 隐私政策缺失/不一致 | AGC 未填 URL；URL 打不开；政策无开发者名称；应用内无入口 | 补 HTTPS URL；政策内开发者名称 = AGC 实名主体、应用名称 = GoGauge；应用内加可点击入口（§9） |
| 未同意隐私政策前收集信息 | 欢迎页直接打开第三方登录 WebView；无隐私弹窗 | 增加首次启动隐私弹窗，同意后才允许登录/联网（§9） |
| 应用信息与实际不符 | 介绍/截图写了未实现功能（GOAT、账户总览） | 文案已排除；截图不要出现相关入口 |
| 应用名称/图标与包内不一致 | 包内仍是占位图标；或改名未同步 | 统一包内 `label` 与图标；商店图必须与包内一致 |
| 图标不合规 | 非正方形/含圆角/透明底/超过 3MB | 用 `release/assets/icon-1024.png`（或 `icon-216.png`），PNG ≤3MB |
| 截图不合规 | 尺寸不对（非 1080×1920 等）、带调试入口、含真实个人信息 | 用 `tools/prep-screenshots.py` 转换；用 release 构建截图；示例账号/Key 名称 |
| 审核无法登录 | 未提供测试账号、账号无 OpenCode Go 订阅、账号被风控 | 提供可用的测试账号与密码；备注说明登录流程；必要时附自测视频 |
| 包签名问题 | 用调试证书/自签名；`.hap` 冒充 `.app`；证书与 Profile 不配套 | 用发布证书 + 发布 Profile 重新签名构建 `.app`；证书/Profile/密钥三者配套 |
| versionCode 问题 | 未递增、与在架相同、超过 2,147,483,647 | 按 §11 规则递增后重新构建上传 |
| 备案问题 | 未备案；包名/名称/主体与备案不一致；未选「鸿蒙」平台 | 在接入商备案系统完成/变更，确保与 AGC 信息一致（§1.1） |
| 版权材料缺失 | 大陆 + 手机应用未传版权证书 | 上传软著/版权证书（≤15MB/张、最多 10 张） |
| 广告法/测试字样 | 文案含「最/第一/国家级」或 test/demo/beta | 全文搜索替换 |
| 内容分级未填 | 未完成问卷 | 版本信息 → 内容分级 → 填写问卷并提交 |
| 崩溃/闪退/UX 差 | 未做上架自检 | AppAnalyzer 上架前体检 + DevEco Testing 上架预检 + 云测试，修复后重提 |
| AI 声明未填 | 后台要求填写 | 选「不涉及」（本应用不提供 AI 生成服务） |

> 被驳回后：版本信息页看「审核报告」，若涉及日志可点「日志下载」；修改后重新构建上传并提交。加急/催审：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-push-0000002312626049>

---

## 11. 阶段十：发布后维护与版本升级

### 11.1 versionCode / versionName 规则（重要且不可逆）

- 两个字段都在 **`AppScope/app.json5`**；AGC 以 `versionCode` 判断版本先后，**必须严格递增**，且 ≤ **2,147,483,647**。
- `versionName` 面向用户，建议语义化版本；`versionCode` 只增不减（回退版本也要用更大的 versionCode 发修复包）。
- 本工程当前 `1.0.0` → `1000000`，建议编码公式：

```
versionCode = major × 1,000,000 + minor × 10,000 + patch × 100
```

| 版本 | versionName | versionCode |
| --- | --- | --- |
| 首发 | 1.0.0 | 1,000,000 |
| 修复 | 1.0.1 | 1,000,100 |
| 功能 | 1.1.0 | 1,010,000 |
| 大版本 | 2.0.0 | 2,000,000 |

升级发版流程：
1. 修改 `AppScope/app.json5` 的 `versionCode`/`versionName`；
2. 更新 `docs/release/release-notes-1.0.0.md` 对应版本说明（新建 `release-notes-<版本>.md`）；
3. 用同一套发布证书/Profile 构建签名 `.app`；
4. AGC → 软件包管理上传新包 → 版本信息 → **升级** → 填写新版本特性 → 提交审核；
5. 审核通过后按设置上架。

### 11.2 只更新应用信息（不上新包）

AGC 支持「升级同版本」：版本信息页右上角「升级」→ 修改应用信息 → 在「软件版本」处「去选择」**当前在架软件包** → 提交审核；版本号不变。若选择了不同的包（即使 versionCode 相同）则不支持同版本升级，必须升版本。

> 官方：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-maintain-update-0000002271413697>

### 11.3 分阶段发布 / 回退 / 下架

- **分阶段发布**：发布后可设置灰度比例与 7 天内自动更新策略：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-maintain-phased-release-0000002271493785>
- **回退**：AGC 不支持 versionCode 回退；发一个 versionCode 更大的修复版本。
- **下架/删除**：应用上架 → 维护/下架（谨慎；删除不可恢复）。
- **证书到期**：发布证书 3 年有效；到期前用**同一密钥库/CSR** 更新证书与 Profile，再发新版本。

---

## 附录 A：完整命令速查

```bash
# 0) 环境
cd /Users/yizhiwang/Desktop/opencode/gousage/opencode-go-gauge/harmonyos
export DEVECO_HOME="/Applications/DevEco-Studio.app"
export DEVECO_SDK_HOME="$DEVECO_HOME/Contents/sdk"
export NODE_HOME="$DEVECO_HOME/Contents/tools/node"
export JAVA="$DEVECO_HOME/Contents/jbr/Contents/Home/bin/java"
export HAP_SIGN_TOOL="$DEVECO_SDK_HOME/default/openharmony/toolchains/lib/hap-sign-tool.jar"

# 1) 单元测试
./scripts/build.sh test
cat entry/.test/default/intermediates/test/coverage_data/test_result.txt 2>/dev/null

# 2) 调试 HAP（未签名；模拟器可直接装）
./scripts/build.sh hap
# 产物: entry/build/default/outputs/default/entry-default-unsigned.hap

# 3) 上架签名（二选一）：
#    A. DevEco Studio：File → Project Structure → Signing Configs 配好发布证书/Profile（推荐）
#    B. 命令行：先生成 material/加密密码，再注入（详见 §5 路径 C）
# node scripts/gen-signing-material.js --signing-dir "$SIGN_DIR" --store-password ... --key-password ...
# bash scripts/inject-signing.sh

# 4) 构建可上架的 Release .app（签名为 signed，否则 unsigned 不可上架）
./scripts/build.sh app
# 等价手动命令（assembleApp 是工程级任务，不能加 --mode module）：
# ./hvigorw assembleApp -p product=default -p buildMode=release --no-daemon
# 产物：build/outputs/default/*.app

# 6) (可选) 手动签 HAP 供真机侧载
./hvigorw --mode module -p product=default assembleHap --no-daemon
"$JAVA" -jar "$HAP_SIGN_TOOL" sign-app -mode localSign \
  -keyAlias "gogauge" -keyPwd "<密钥密码>" \
  -appCertFile "/secure/path/gogauge-release-cert.cer" \
  -profileFile "/secure/path/gogauge-release-profile.p7b" \
  -inFile "entry/build/default/outputs/default/entry-default-unsigned.hap" \
  -signAlg SHA256withECDSA \
  -keystoreFile "/secure/path/gogauge-release.p12" -keystorePwd "<密钥库密码>" \
  -outFile "entry/build/default/outputs/default/entry-default-signed.hap" \
  -compatibleVersion 24 -signCode 1
./scripts/install.sh

# 7) 截图转换（AGC 规格）
cd /Users/yizhiwang/Desktop/opencode/gousage/opencode-go-gauge
.venv/bin/python3 harmonyos/docs/release/tools/prep-screenshots.py --all

# 8) 上架资产再生成（图标/宣传图）
.venv/bin/python3 harmonyos/docs/release/assets/generate-assets.py
```

## 附录 B：故障排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `hvigorw: command not found` / SDK 找不到 | 未设置 `DEVECO_SDK_HOME`/`NODE_HOME`，或用了旧的 `~/Library/OpenHarmony/Sdk/13` | 用 DevEco 自带 SDK（6.1.1/API 24），按附录 A 导出环境变量 |
| `assembleApp` 无产物/报签名错误 | `signingConfigs` 为空或路径/密码不匹配 | 先 `scripts/inject-signing.sh` 或 DevEco Signing Configs 配置；确认 `.p12/.cer/.p7b` 三者配套 |
| `KEY_PASSWORD_ERROR` / `SIGN_ERROR` | 密钥密码错、证书与密钥不匹配 | 密码与生成时一致；`-keyAlias`/`-appCertFile` 对应同一密钥 |
| AGC 提示签名非法/包不合法 | 上传了 HAP、调试签名包或包内 `debug=true` | 上传 release `.app`；用发布证书+发布 Profile；重新构建 |
| `hdc install` 失败 `9568320` 等签名错误 | 设备不接受未签名/签名不匹配的 HAP | 模拟器可装未签名 HAP；真机需签名（路径 A/C/D） |
| 构建被 obfuscation 报错 | 混淆规则不完整 | `entry/build-profile.json5` 中保持 `obfuscation.enable=false`，或补规则并回归测试 |
| 应用启动即崩溃 / 白屏 | 数据库迁移、WebView 或权限异常 | 看 hilog；跑上架自检；回归 `AppDb.migrate` 场景（降级安装会显式报错） |
| 上传的 `.app` 超过 4GB | 资源/依赖过大 | 检查 HAP 体积、依赖与资源；本工程通常远小于限制 |
| 图标被驳回 | 与包内不一致/非正方形/带圆角透明/超 3MB | 见 `release/appgallery-metadata.md` §6 |

## 附录 C：官方文档链接

- 发布 HarmonyOS 应用（总览）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-0000002271695230>
- 发布指引：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-guide-0000002287176372>
- 发布准备工作：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-prepare-0000002306311921>
- 素材规范（图标/截图）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-app-visual-asset-spec-0000002277607976>
- 创建 HarmonyOS 应用：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-create-app-0000002247955506>
- 申请发布证书：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-cert-0000002283336729>
- 申请发布 Profile：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-profile-0000002248341090>
- 手动签名：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-signing-manual>
- 自动签名：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-signing-auto>
- DevEco 发布应用（Build APP / Upload Product）：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-publish-app>
- 命令行构建 hvigorw：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-hvigor-commandline>
- 上传软件包：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-upload-pkg-0000002277983368>
- 配置本地化基础信息（名称/图标）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-nameicon-0000002306265009>
- 配置本地化基础信息（介绍/特性/素材）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-intro-0000002313477961>
- 配置应用分类、标签：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-class-tag-0000002271695234>
- 配置隐私声明：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-privacy-state-0000002278878296>
- 配置隐私标签信息：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-privacy-tag-0000002316420993>
- 配置版权信息：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-copyright-0000002278981450>
- 填写审核信息与联系方式：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-reviewinfo-0000002320780365>
- 配置支持设备：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-devicetype-0000002271592112>
- 提交审核：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-submit-0000002286180890>
- 更新应用信息（同版本升级）：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-maintain-update-0000002271413697>
- 升级版本：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-maintain-upgrade-0000002236494386>
- 分阶段发布：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-maintain-phased-release-0000002271493785>
- 应用审核指南：<https://developer.huawei.com/consumer/cn/doc/app/50104>
- 应用审核 Checklist：<https://developer.huawei.com/consumer/cn/doc/app/50170>
- APP 核准（备案）指引：<https://developer.huawei.com/consumer/cn/doc/app/50130>
- AppGallery 隐私标签服务说明：<https://developer.huawei.com/consumer/cn/doc/app/privacy-label>
- 隐私政策（HarmonyOS 应用）配置：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-privacy-policy-app-0000002282162168>
- AppAnalyzer 上架前体检：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/ide-app-analyzer-before-appgallery>
- DevEco Testing 上架预检：<https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/publish-testing>

---

## 附录 D：仍需用户自行完成/提供的事项（汇总）

- [ ] 华为开发者账号 + 实名认证
- [ ] APP 备案（工信部，选择「鸿蒙」平台）
- [ ] 应用版权证书/软著（大陆 + 手机必选）
- [ ] AGC 创建应用（包名绑定）
- [ ] 发布证书 `.cer` + 发布 Profile `.p7b`（以及 `.p12` 与密码，妥善备份）
- [ ] 隐私政策托管 URL（HTTPS 可访问，含开发者名称，与本文档一致）
- [ ] 客服邮箱、官网（可选）、应用负责人手机号/邮箱/姓名
- [ ] 审核测试账号（OpenCode Go）或 `.mp4` 自测视频
- [ ] 内容分级问卷、AI 功能声明、隐私标签信息（按后台如实填写）
- [x] 代码侧已补齐：应用内隐私政策入口（欢迎页/设置→关于）+ 首次启动隐私弹窗（见 §9）
- [ ] 确认商店图标方案（品牌版 vs 包内一致版）
