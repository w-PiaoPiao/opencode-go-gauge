#!/usr/bin/env bash
# 把「DevEco 兼容格式」的签名配置注入 build-profile.json5（上架 .app 构建用）。
#
# ⚠️ hvigor 6.x 不接受明文密码：storePassword/keyPassword 必须是 AES-128-GCM 密文
# (hex)，并且 p12 同目录下必须有 material/（fd/ac/ce），否则报
#   "Signature material verification failed" / "KEY_PASSWORD_VALID_FAILED"。
#
# 两种密码来源（任选其一）：
#   A) 推荐：先跑 scripts/gen-signing-material.js 生成 material + 密文密码：
#        node scripts/gen-signing-material.js \
#          --signing-dir "$PWD/../.signing" \
#          --store-password "$P12_PASSWORD" --key-password "$KEY_PASSWORD" --force
#        export HAP_SIGNING_PASSWORDS_JSON="$PWD/../.signing/signing-passwords.json"
#   B) 从 DevEco Studio 已经配置好的工程里复制 build-profile.json5 的 signingConfigs
#      （DevEco 会自动生成密文与 material 目录，本机 CLI 构建可直接用）。
#      这种情况不需要本脚本，直接在 DevEco 配好后 `./scripts/build.sh app` 即可。
#
# 必填环境变量：
#   HAP_STORE_FILE             签名 p12（其同目录下应有 material/）
#   HAP_KEY_ALIAS              key alias
#   HAP_PROFILE_P7B            AGC 签发的发布 Profile
#   HAP_SIGN_CER               签名证书链 .cer/.pem（与 p12 中私钥匹配）
#   HAP_SIGNING_PASSWORDS_JSON gen-signing-material.js 的输出 JSON
# 可选：
#   HAP_SIGN_TYPE              HarmonyOS（默认）| OpenHarmony
set -euo pipefail
cd "$(dirname "$0")/.."

: "${HAP_STORE_FILE:?need HAP_STORE_FILE (签名 p12 路径)}"
: "${HAP_KEY_ALIAS:?need HAP_KEY_ALIAS}"
: "${HAP_PROFILE_P7B:?need HAP_PROFILE_P7B (发布 Profile 路径)}"
: "${HAP_SIGN_CER:?need HAP_SIGN_CER (签名证书链路径)}"
: "${HAP_SIGNING_PASSWORDS_JSON:?need HAP_SIGNING_PASSWORDS_JSON (gen-signing-material.js 的输出)}"
SIGN_TYPE="${HAP_SIGN_TYPE:-HarmonyOS}"

for f in "$HAP_STORE_FILE" "$HAP_PROFILE_P7B" "$HAP_SIGN_CER" "$HAP_SIGNING_PASSWORDS_JSON"; do
  [ -f "$f" ] || { echo "ERROR: 文件不存在: $f" >&2; exit 1; }
done
MATERIAL_DIR="$(cd "$(dirname "$HAP_STORE_FILE")" && pwd)/material"
if [ ! -d "$MATERIAL_DIR" ]; then
  echo "ERROR: 找不到签名材料目录: $MATERIAL_DIR" >&2
  echo "       请先运行: node scripts/gen-signing-material.js --signing-dir \"$(dirname "$HAP_STORE_FILE")\" --store-password ... --key-password ... --force" >&2
  exit 1
fi

python3 - "$HAP_STORE_FILE" "$HAP_KEY_ALIAS" "$HAP_PROFILE_P7B" "$HAP_SIGN_CER" "$HAP_SIGNING_PASSWORDS_JSON" "$SIGN_TYPE" <<'PY'
import json
import os
import sys

store, alias, profile, cert, pw_json, sign_type = sys.argv[1:7]
with open(pw_json, encoding='utf-8') as f:
    pw = json.load(f)
store_pwd = pw['storePassword']
key_pwd = pw['keyPassword']
for name, value in (('storePassword', store_pwd), ('keyPassword', key_pwd)):
    # hvigor 校验：密文 hex 至少 32 字符且长度为偶数
    if len(value) < 32 or len(value) % 2 != 0:
        raise SystemExit(f'ERROR: {name} 不是 hvigor 兼容的密文 hex（请用 gen-signing-material.js 生成）')

bp_path = 'build-profile.json5'
with open(bp_path, encoding='utf-8') as f:
    d = json.load(f)

d['app']['signingConfigs'] = [{
    'name': 'release',
    'type': sign_type,
    'material': {
        'storeFile': os.path.abspath(store),
        'storePassword': store_pwd,
        'keyAlias': alias,
        'keyPassword': key_pwd,
        'signAlg': 'SHA256withECDSA',
        'profile': os.path.abspath(profile),
        'certpath': os.path.abspath(cert),
    },
}]
for p in d['app']['products']:
    p['signingConfig'] = 'release'

with open(bp_path, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('signingConfigs injected ->', bp_path)
print('  注意: 该文件含加密密码与绝对路径, 不要把 build-profile.json5 的改动提交到仓库')
PY
