#!/usr/bin/env bash
# 真机/模拟器安装辅助: 安装 HAP 并启动应用。
# 前置: 已签名 HAP (DevEco 自动签名或 scripts/inject-signing.sh + AGC 材料), hdc 可连设备。
set -euo pipefail
cd "$(dirname "$0")/.."

HAP="${1:-entry/build/default/outputs/default/entry-default-signed.hap}"
BUNDLE="io.github.yphyphyph.gogauge"
ABIL="EntryAbility"
HDC="${HDC:-$HOME/Library/OpenHarmony/Sdk/13/toolchains/hdc}"

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