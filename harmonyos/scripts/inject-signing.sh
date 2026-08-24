#!/usr/bin/env bash
# 从环境变量注入签名配置到 build-profile.json5 (CI 与本地通用, 幂等)。
# 密码按鸿蒙 hex 编码规则转写 (对照 FinanceNumberConverter 真实工程格式)。
set -euo pipefail
cd "$(dirname "$0")/.."

: "${HAP_STORE_FILE:?need HAP_STORE_FILE (release.p12 路径)}"
: "${HAP_STORE_PASSWORD:?need HAP_STORE_PASSWORD}"
: "${HAP_KEY_ALIAS:?need HAP_KEY_ALIAS}"
: "${HAP_KEY_PASSWORD:?need HAP_KEY_PASSWORD}"
: "${HAP_PROFILE_P7B:?need HAP_PROFILE_P7B (签名 Profile 路径)}"
: "${HAP_SIGN_CER:?need HAP_SIGN_CER (发布证书路径)}"

python3 - "$HAP_STORE_FILE" "$HAP_STORE_PASSWORD" "$HAP_KEY_ALIAS" "$HAP_KEY_PASSWORD" "$HAP_PROFILE_P7B" "$HAP_SIGN_CER" <<'PY'
import json, sys
store, sp, alias, kp, profile, cert = sys.argv[1:7]

def hexenc(s: str) -> str:
    return s.encode('utf-8').hex().upper()

bp = 'build-profile.json5'
with open(bp, encoding='utf-8') as f:
    d = json.load(f)

d['app']['signingConfigs'] = [{
    'name': 'release',
    'type': 'HarmonyOS',
    'material': {
        'storeFile': store,
        'storePassword': hexenc(sp),
        'keyAlias': alias,
        'keyPassword': hexenc(kp),
        'signAlg': 'SHA256withECDSA',
        'profile': profile,
        'certpath': cert,
    },
}]
for p in d['app']['products']:
    p['signingConfig'] = 'release'

with open(bp, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('signingConfigs injected ->', bp)
PY