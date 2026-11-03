#!/usr/bin/env bash
# GoGauge HarmonyOS 构建/测试入口。
#   ./build.sh        -> assembleHap (HAP)
#   ./build.sh test   -> 本地单元测试 (hypium)
# 环境: 自动探测 DevEco; 可用 DEVECO_HOME/DEVECO_SDK_HOME/NODE_HOME 覆盖。
set -euo pipefail
# 脚本在 scripts/ 下, hvigorw 在工程根 —— 必须先回到根目录, 否则 ./hvigorw 找不到
cd "$(dirname "$0")/.."

DEVECO_HOME="${DEVECO_HOME:-/Applications/DevEco-Studio.app}"
export DEVECO_SDK_HOME="${DEVECO_SDK_HOME:-$DEVECO_HOME/Contents/sdk}"
export NODE_HOME="${NODE_HOME:-$DEVECO_HOME/Contents/tools/node}"

mode="${1:-hap}"
case "$mode" in
  hap)
    echo "== assembleHap (debug HAP, 模拟器/真机调试用) =="
    ./hvigorw --mode module -p product=default assembleHap --no-daemon
    ls -lh entry/build/default/outputs/default/*.hap 2>/dev/null || true
    ;;
  app)
    # AppGallery 上架必须提交 .app(App Pack)，HAP 仅用于本地调试/安装。
    # 签名配置由 scripts/inject-signing.sh 注入 build-profile.json5 后才会产出签名 .app。
    echo "== assembleApp (release App Pack, 上架用) =="
    # assembleApp 是工程级任务（不是 module 级）: 不能带 --mode module
    ./hvigorw assembleApp -p product=default -p buildMode=release --no-daemon
    # App Pack 产物在工程根 build/outputs/default/（unsigned 或 signed 取决于 signingConfigs）
    ls -lh build/outputs/default/*.app 2>/dev/null || true
    ;;
  test)
    echo "== unit tests (hvigorw test) =="
    ./hvigorw --mode module -p product=default test --no-daemon
    echo "== result =="
    tail -1 entry/.test/default/intermediates/test/coverage_data/test_result.txt 2>/dev/null || true
    ;;
  *)
    echo "usage: $0 [hap|app|test]"
    exit 1
    ;;
esac