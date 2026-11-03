#!/usr/bin/env bash
# 真机/模拟器安装辅助: 安装 HAP 并启动应用。
# 前置: 已签名 HAP (DevEco 自动签名或 scripts/inject-signing.sh + AGC 材料), hdc 可连设备。
set -euo pipefail
cd "$(dirname "$0")/.."

HAP="${1:-entry/build/default/outputs/default/entry-default-signed.hap}"
BUNDLE="io.github.yphyphyph.gogauge"
ABIL="EntryAbility"
# hdc 自动探测: DevEco Studio 自带 SDK -> 旧版 OpenHarmony SDK
if [ -z "${HDC:-}" ]; then
  for cand in \
    "/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc" \
    "$HOME/Library/OpenHarmony/Sdk/13/toolchains/hdc" \
    "$(command -v hdc 2>/dev/null || true)"; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then HDC="$cand"; break; fi
  done
fi
: "${HDC:?找不到 hdc，请设置 HDC=/path/to/hdc}"

[ -f "$HAP" ] || { echo "HAP 不存在: $HAP (先构建并签名)"; exit 1; }

echo "== hdc list targets =="
"$HDC" list targets

echo "== install $HAP =="
"$HDC" install "$HAP" || "$HDC" install -r "$HAP"

echo "== launch $BUNDLE =="
"$HDC" shell aa start -a "$ABIL" -b "$BUNDLE"

sleep 3
"$HDC" shell snapshot_display /tmp/gogauge_screen.png >/dev/null 2>&1 && {
  mkdir -p docs/screenshots
  "$HDC" file recv /tmp/gogauge_screen.png docs/screenshots/home.png >/dev/null 2>&1 && echo "截图已存 docs/screenshots/home.png"
}
echo "== done =="