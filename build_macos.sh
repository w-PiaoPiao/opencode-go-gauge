#!/usr/bin/env bash
# Build the GoGauge macOS .app via PyInstaller.
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo "  GoGauge macOS 打包脚本 (PyInstaller .app)"
echo "============================================"
echo

echo "[1/4] 安装依赖..."
python3 -m pip install -q --upgrade pywebview pystray pillow pyinstaller

echo "[2/4] 生成图标 assets/GoGauge.icns + GoGauge.png ..."
python3 scripts/build_macos_icon.py

echo "[3/4] 打包 .app (无终端窗口, 含 icon) ..."
# PYINSTALLER_CONFIG_DIR 让 PyInstaller 缓存落在项目内, 便于离线/受限环境打包
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$PWD/.pyicache}"
# macOS 推荐 onedir (.app 目录包); 避免 --onefile 与 .app 的兼容性/签名问题
python3 -m PyInstaller --noconfirm --windowed --name GoGauge \
  --add-data "app/web:app/web" \
  --add-data "assets:assets" \
  --icon assets/GoGauge.icns \
  --osx-bundle-identifier com.opencode.gogauge \
  --collect-submodules webview \
  --hidden-import pystray \
  --exclude-module numpy \
  --exclude-module cryptography \
  --exclude-module PIL._avif \
  entry.py

echo "[4/4] 完成!"
echo
echo "输出: dist/GoGauge.app"
echo "数据目录: ~/Library/Application Support/GoGauge/data"
echo
echo "提示: 若需分发, 可将 GoGauge.app 放入 .dmg 后再分享。"
echo "     首次 macOS 打开若提示“无法验证开发者”, 去 系统设置->隐私与安全性 允许运行。"
