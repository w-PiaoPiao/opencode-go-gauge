#!/usr/bin/env bash
# Build the GoGauge macOS .app via PyInstaller.
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo "  GoGauge macOS 打包脚本 (PyInstaller .app)"
echo "============================================"
echo

echo "[1/5] 安装依赖..."
# 优先锁定版本 (可复现构建); 无锁文件时回退最新版
if [ -f requirements-macos.lock.txt ]; then
  python3 -m pip install -q -r requirements-macos.lock.txt
else
  python3 -m pip install -q --upgrade pywebview pystray pillow pyinstaller
fi

echo "[2/5] 读取版本号 + 生成本次构建信息..."
APP_VERSION="$(python3 -c 'from app import __version__; print(__version__)')"
# 打包产物的更新检查仓库: 默认本 fork (mac 版实际发布处), 可用环境变量覆盖
UPDATE_REPO="${GOUSAGE_UPDATE_REPO:-w-PiaoPiao/opencode-go-gauge}"
cat > app/_build_info.py <<EOF
"""构建时自动生成 (gitignored): 打包产物元信息, 供更新检查使用."""
UPDATE_REPO = "${UPDATE_REPO}"
BUILD_VERSION = "${APP_VERSION}"
EOF
echo "    version=${APP_VERSION}  update_repo=${UPDATE_REPO}"

echo "[3/5] 生成图标 assets/GoGauge.icns + GoGauge.png ..."
python3 scripts/build_macos_icon.py

echo "[4/5] 打包 .app (无终端窗口, 含 icon) ..."
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

echo "[5/5] 写入 Info.plist 版本号 (${APP_VERSION}) ..."
PLIST="dist/GoGauge.app/Contents/Info.plist"
# PyInstaller 模板可能缺 CFBundleVersion 键: Set 失败(键不存在)时用 Add 创建
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${APP_VERSION}" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string ${APP_VERSION}" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${APP_VERSION}" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string ${APP_VERSION}" "$PLIST"
# 改动 Info.plist 会使 PyInstaller 的 ad-hoc 签名失效, 必须重签
codesign --force --deep --sign - dist/GoGauge.app

echo
echo "完成!"
echo "输出: dist/GoGauge.app"
echo "版本: ${APP_VERSION}  更新检查仓库: ${UPDATE_REPO}"
echo "数据目录: ~/Library/Application Support/GoGauge/data"
echo
echo "提示: 分发 zip 建议命名 GoGauge-v${APP_VERSION}-macos.zip,"
echo "     例如: ditto -c -k --keepParent dist/GoGauge.app dist/GoGauge-v${APP_VERSION}-macos.zip"
echo "     首次 macOS 打开若提示“无法验证开发者”, 去 系统设置->隐私与安全性 允许运行。"
