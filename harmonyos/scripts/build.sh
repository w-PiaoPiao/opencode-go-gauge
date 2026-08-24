#!/usr/bin/env bash
# GoGauge HarmonyOS 构建/测试入口。
#   ./build.sh        -> assembleHap (HAP)
#   ./build.sh test   -> 本地单元测试 (hypium)
# 环境: 自动探测 DevEco; 可用 DEVECO_HOME/DEVECO_SDK_HOME/NODE_HOME 覆盖。
set -euo pipefail
cd "$(dirname "$0")"

DEVECO_HOME="${DEVECO_HOME:-/Applications/DevEco-Studio.app}"
export DEVECO_SDK_HOME="${DEVECO_SDK_HOME:-$DEVECO_HOME/Contents/sdk}"
export NODE_HOME="${NODE_HOME:-$DEVECO_HOME/Contents/tools/node}"

mode="${1:-hap}"
case "$mode" in
  hap)
    echo "== assembleHap =="
    ./hvigorw --mode module -p product=default assembleHap --no-daemon
    ls -lh entry/build/default/outputs/default/*.hap 2>/dev/null || true
    ;;
  test)
    echo "== unit tests (hvigorw test) =="
    ./hvigorw --mode module -p product=default test --no-daemon
    echo "== result =="
    tail -1 entry/.test/default/intermediates/test/coverage_data/test_result.txt 2>/dev/null || true
    ;;
  *)
    echo "usage: $0 [hap|test]"
    exit 1
    ;;
esac