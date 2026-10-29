#!/usr/bin/env bash
# GoGauge macOS 打包入口 (薄包装): 安装锁定依赖 -> scripts/build.py 统一构建.
#
# 所有 PyInstaller 参数 (hiddenimports/excludes/--add-data/icns 图标/Info.plist 版本/
# ad-hoc 重签) 都在 scripts/build.py; 本脚本只负责可复现地装依赖。参数原样透传
# (如 --repo owner/name), 详见 scripts/build.py --help。
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo "  GoGauge macOS 打包 (PyInstaller .app)"
echo "============================================"
echo

echo "[1/2] 安装锁定依赖..."
# 优先锁定版本 (可复现构建); 无锁文件时回退最新版
if [ -f requirements-macos.lock.txt ]; then
  python3 -m pip install -q -r requirements-macos.lock.txt
else
  echo "  ⚠️ 未找到 requirements-macos.lock.txt, 回退安装最新版依赖 (不保证可复现)"
  python3 -m pip install -q --upgrade pywebview pystray pillow pyinstaller
fi

echo "[2/2] 构建 dist/GoGauge.app ..."
exec python3 scripts/build.py --platform macos "$@"
