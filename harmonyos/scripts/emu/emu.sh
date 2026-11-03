#!/usr/bin/env bash
# =============================================================================
# GoGauge HarmonyOS — 模拟器运行时工具链
#
# 用途：本机 HarmonyOS 模拟器（DevEco Studio 自带 Emulator）的启停、安装、
#       启动、截图、解锁、日志与 crash 检查。所有设备操作自动发现 hdc target，
#       不写死端口（模拟器重启后端口会漂移）。
#
# 依赖：macOS + DevEco Studio（含 Emulator / hdc）。
#       可用环境变量覆盖路径：DEVECO_HOME / HDC_BIN / EMU_BIN /
#       EMU_INSTANCE_PATH / EMU_IMAGE_ROOT。
#
# 快速开始：
#   ./emu.sh list                  # 看有哪些实例 / 当前 hdc 设备
#   ./emu.sh start-phone           # 启动手机模拟器并等待桌面就绪
#   ./emu.sh install latest        # 安装最新构建的 HAP（未签名）
#   ./emu.sh launch                # 启动应用
#   ./emu.sh shot smoke-welcome    # 截图到 docs/store-assets/screenshots/phone/
#   ./emu.sh crash-check           # 清日志→启动→检查 FATAL/ERROR/进程存活
#   ./emu.sh stop "Pura 90"        # 停止实例（切换设备前必须 stop，16GB 内存）
#
# 说明：
#   * 构建由调用者负责（`./scripts/build.sh hap`，或 `./emu.sh build`）。
#   * 模拟器是 GUI 进程，会在宿主屏幕弹出窗口，不要 kill / 关闭它；用
#     `emu.sh stop <name>` 正常关闭。
#   * 设备操作段用 mkdir 锁 /tmp/gogauge-emu.lock 串行化，避免与人工 hdc
#     操作互相打架；锁超时可调 EMU_LOCK_TIMEOUT，跳过锁用 EMU_NO_LOCK=1。
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# 路径与默认参数
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARMONY_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"          # harmonyos/
REPO_DIR="$(cd "$HARMONY_DIR/.." && pwd)"               # 仓库根

DEVECO_HOME="${DEVECO_HOME:-/Applications/DevEco-Studio.app}"
HDC="${HDC_BIN:-$DEVECO_HOME/Contents/sdk/default/openharmony/toolchains/hdc}"
EMULATOR="${EMU_BIN:-$DEVECO_HOME/Contents/tools/emulator/Emulator}"
INSTANCE_PATH="${EMU_INSTANCE_PATH:-$HOME/.Huawei/Emulator/deployed}"
IMAGE_ROOT="${EMU_IMAGE_ROOT:-$HOME/Library/Huawei/Sdk}"

BUNDLE="${BUNDLE:-io.github.yphyphyph.gogauge}"
ABILITY="${ABILITY:-EntryAbility}"
HAP="${HAP:-$HARMONY_DIR/entry/build/default/outputs/default/entry-default-unsigned.hap}"

# 已部署实例名（devices 子命令里可覆盖）
EMU_PHONE_NAME="${EMU_PHONE_NAME:-Pura 90}"
EMU_2IN1_NAME="${EMU_2IN1_NAME:-MateBook Pro}"
EMU_TABLET_NAME="${EMU_TABLET_NAME:-GoGauge_Tablet}"
TABLET_DEVICE_TYPE="Tablet"
TABLET_OS_VERSION="${TABLET_OS_VERSION:-HarmonyOS 6.1.1(24)}"

SHOT_ROOT="${SHOT_ROOT:-$HARMONY_DIR/docs/store-assets/screenshots}"
LOCK_DIR="${EMU_LOCK_DIR:-/tmp/gogauge-emu.lock}"
LOCK_TIMEOUT="${EMU_LOCK_TIMEOUT:-180}"
BOOT_TIMEOUT="${EMU_BOOT_TIMEOUT:-300}"
STOP_TIMEOUT="${EMU_STOP_TIMEOUT:-120}"
APP_SETTLE="${EMU_APP_SETTLE:-4}"
CRASH_WAIT="${EMU_CRASH_WAIT:-12}"

# 运行期状态
TARGET="${HDC_TARGET:-}"
LOCK_HELD=0

# ---------------------------------------------------------------------------
# 日志与错误
# ---------------------------------------------------------------------------
log()  { printf '[emu] %s\n' "$*"; }
warn() { printf '[emu][warn] %s\n' "$*" >&2; }
die()  { printf '[emu][error] %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1（macOS 自带；或 brew install $1）"
}

need_hdc() {
  [ -x "$HDC" ] || die "找不到 hdc: ${HDC}（设置 HDC_BIN 或 DEVECO_HOME 覆盖）"
}

need_emulator() {
  [ -x "$EMULATOR" ] || die "找不到 Emulator: ${EMULATOR}（设置 EMU_BIN 或 DEVECO_HOME 覆盖；要求已安装 DevEco Studio）"
}

# ---------------------------------------------------------------------------
# 设备操作互斥锁（mkdir 原子锁；trap 释放）
#   - 与 Lead 的人工 hdc 操作共享同一台模拟器，串行化可显著降低冲突概率。
#   - 锁目录写 pid，进程已死则视为过期锁自动清理。
#   - 有人长时间占用时最多等 EMU_LOCK_TIMEOUT 秒。
# ---------------------------------------------------------------------------
release_lock() {
  if [ "$LOCK_HELD" = "1" ]; then
    rm -rf "$LOCK_DIR"
    LOCK_HELD=0
  fi
}

acquire_lock() {
  if [ "${EMU_NO_LOCK:-0}" = "1" ]; then
    log "EMU_NO_LOCK=1：跳过设备锁（仅在确认无人同时操作设备时使用）"
    return 0
  fi
  local waited=0 holder
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    holder="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
      warn "清理过期设备锁（pid $holder 已不存在）"
      rm -rf "$LOCK_DIR"
      continue
    fi
    if [ "$waited" -ge "$LOCK_TIMEOUT" ]; then
      die "等待设备锁超时（${LOCK_TIMEOUT}s）：$LOCK_DIR 被 pid ${holder:-?} 占用。若确认无人操作设备，可 rm -rf $LOCK_DIR 或设 EMU_NO_LOCK=1"
    fi
    if [ "$waited" -eq 0 ]; then
      log "设备正被其它进程占用（pid ${holder:-?}），等待锁 $LOCK_DIR ..."
    fi
    sleep 2
    waited=$((waited + 2))
  done
  printf '%s\n' "$$" >"$LOCK_DIR/pid"
  LOCK_HELD=1
  trap release_lock EXIT INT TERM
}

# ---------------------------------------------------------------------------
# hdc target 自动发现
#   模拟器重启后端口会变（5557/5559/…），因此每次设备操作前都重新探测；
#   一旦在本进程内确定 TARGET 就缓存，避免同一命令内反复扫描。
# ---------------------------------------------------------------------------
list_targets() {
  need_hdc
  "$HDC" list targets 2>/dev/null | tr -d '\r' | sed '/^[[:space:]]*$/d' | grep -v '^\[Empty\]$' || true
}

discover_target() {
  local targets t n
  targets="$(list_targets)"
  if [ -z "$targets" ]; then
    return 1
  fi
  t="$(printf '%s\n' "$targets" | head -1)"
  n="$(printf '%s\n' "$targets" | wc -l | tr -d ' ')"
  if [ "$n" -gt 1 ]; then
    warn "发现 $n 个 hdc target，使用第一个: ${t}（可用 HDC_TARGET=<key> 指定）"
  fi
  printf '%s' "$t"
}

resolve_target() {
  if [ -n "$TARGET" ]; then
    return 0
  fi
  need_hdc
  TARGET="$(discover_target)" || true
  if [ -z "$TARGET" ]; then
    die "未发现可用 hdc target：模拟器未启动或仍在引导。先执行 ./emu.sh start-phone / start-2in1 / start-tablet（用 ./emu.sh list 查看实例）"
  fi
  log "hdc target: $TARGET"
}

# dsh <单条 shell 命令字符串>：在设备 shell 执行并输出到 stdout（自动去 CR）
dsh() {
  resolve_target
  "$HDC" -t "$TARGET" shell "$1" | tr -d '\r'
}

dsh_quiet() { dsh "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
# 模拟器实例状态（解析 `Emulator -list -details` 的 JSON）
# ---------------------------------------------------------------------------
instances_json() {
  need_emulator
  "$EMULATOR" -list -details 2>/dev/null
}

running_instances() {
  instances_json | jq -r '.[] | select(.isRunning == "true") | .name' 2>/dev/null || true
}

instance_exists() {
  local name="$1"
  instances_json | jq -e --arg n "$name" '.[] | select(.name == $n)' >/dev/null 2>&1
}

instance_field() {
  local name="$1" field="$2"
  instances_json | jq -r --arg n "$name" --arg f "$field" '.[] | select(.name == $n) | .[$f] // ""' 2>/dev/null || true
}

emu_process_alive() {
  local name="$1"
  pgrep -f -- "Emulator -start ${name}" >/dev/null 2>&1
}

# 当前设备摘要（需要 hdc target 可用）
device_type() {
  dsh 'param get const.product.devicetype' 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || true
}

device_os_api() {
  dsh 'param get const.ohos.apiversion' 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || true
}

device_sw_version() {
  dsh 'param get const.product.software.version' 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || true
}

# 屏幕分辨率：从 snapshot_display 的输出解析（同时验证截图链路可用）
screen_size() {
  local out w h
  out="$(dsh 'snapshot_display -f /data/local/tmp/gogauge-size-probe.jpeg' 2>/dev/null || true)"
  w="$(printf '%s\n' "$out" | sed -n 's/.*width: \([0-9][0-9]*\).*/\1/p' | head -1)"
  h="$(printf '%s\n' "$out" | sed -n 's/.*height: \([0-9][0-9]*\).*/\1/p' | head -1)"
  if [ -z "$w" ] || [ -z "$h" ]; then
    # 兜底：WindowManagerService 里 SCBScenePanel 的窗口边界 = 全屏尺寸
    out="$(dsh "hidumper -s WindowManagerService -a '-a'" 2>/dev/null || true)"
    w="$(printf '%s\n' "$out" | sed -n 's/.*SCBScenePanel[0-9]*.*\[ *0 *0 *\([0-9][0-9]*\) *\([0-9][0-9]*\) *\].*/\1/p' | head -1)"
    h="$(printf '%s\n' "$out" | sed -n 's/.*SCBScenePanel[0-9]*.*\[ *0 *0 *\([0-9][0-9]*\) *\([0-9][0-9]*\) *\].*/\2/p' | head -1)"
  fi
  [ -n "$w" ] && [ -n "$h" ] || return 1
  printf '%s %s\n' "$w" "$h"
}

device_summary() {
  local dtype api sw res w h
  dtype="$(device_type)"
  api="$(device_os_api)"
  sw="$(device_sw_version)"
  res="$(screen_size 2>/dev/null || true)"
  if [ -n "$res" ]; then
    w="${res% *}"; h="${res#* }"
  else
    w="?"; h="?"
  fi
  printf 'devicetype=%s api=%s screen=%sx%s os=%s target=%s' "${dtype:-?}" "${api:-?}" "$w" "$h" "${sw:-?}" "${TARGET:-?}"
}

# ---------------------------------------------------------------------------
# 等待设备 / 系统 / 桌面就绪
#
# boot 完成判据（按可靠性从低到高，全部满足才算 ready）：
#   1) `hdc list targets` 能列出 target，且 `hdc shell echo` 有返回
#      —— hdc daemon + 设备 shell 已通。
#   2) `param get bootevent.boot.completed` == true
#      —— 系统启动完成事件（模拟器实测唯一稳定可用的 boot 参数；
#         sys.boot.completed / bootevent.bootanim.exit 在 HarmonyOS NEXT
#         模拟器上不存在，会返回 errNum 1002/106）。
#   3) `hidumper -s WindowManagerService -a '-a'` 输出包含 ScreenGroup
#      且包含桌面壁纸/桌面窗口（SCBDesktop / SCBWallpaper / Launcher）
#      —— 窗口服务已就绪、桌面已加载。
#   4) `snapshot_display -f ...` 返回 success
#      —— 合成器可出帧，截图链路可用（也是截图命令的前置条件）。
# ---------------------------------------------------------------------------
wait_for_device_shell() {
  local timeout="${1:-$BOOT_TIMEOUT}" waited=0 t out
  need_hdc
  while [ "$waited" -lt "$timeout" ]; do
    t="$(list_targets | head -1 || true)"
    if [ -n "$t" ]; then
      out="$("$HDC" -t "$t" shell "echo gogauge-shell-ok" 2>/dev/null | tr -d '\r' || true)"
      case "$out" in
        *gogauge-shell-ok*)
          TARGET="$t"
          log "hdc shell 就绪: ${TARGET}（等待 ${waited}s）"
          return 0
          ;;
      esac
    fi
    sleep 3
    waited=$((waited + 3))
  done
  return 1
}

wait_for_boot() {
  local timeout="${1:-$BOOT_TIMEOUT}" waited=0 v=""
  resolve_target
  log "等待 bootevent.boot.completed=true（最多 ${timeout}s）..."
  while [ "$waited" -lt "$timeout" ]; do
    v="$(dsh 'param get bootevent.boot.completed' 2>/dev/null | head -1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || true)"
    if [ "$v" = "true" ]; then
      log "boot 完成（bootevent.boot.completed=true, 等待 ${waited}s）"
      return 0
    fi
    sleep 3
    waited=$((waited + 3))
  done
  return 1
}

wait_for_ui() {
  local timeout="${1:-$BOOT_TIMEOUT}" waited=0 dump="" snap=""
  resolve_target
  log "等待窗口服务与桌面就绪（最多 ${timeout}s）..."
  while [ "$waited" -lt "$timeout" ]; do
    dump="$(dsh "hidumper -s WindowManagerService -a '-a'" 2>/dev/null || true)"
    if printf '%s\n' "$dump" | grep -q "ScreenGroup" \
       && printf '%s\n' "$dump" | grep -qE "SCBDesktop|SCBWallpaper|Launcher"; then
      snap="$(dsh 'snapshot_display -f /data/local/tmp/gogauge-ready-probe.jpeg' 2>/dev/null || true)"
      if printf '%s\n' "$snap" | grep -q "success"; then
        log "桌面/窗口服务就绪（等待 ${waited}s）"
        return 0
      fi
    fi
    sleep 3
    waited=$((waited + 3))
  done
  return 1
}

# ---------------------------------------------------------------------------
# 屏幕锁：用 ScreenlockService 判据（实测可用）
#   hidumper -s ScreenlockService -a '-all' 输出：
#     screenLocked   false / true
# 已解锁则幂等跳过；锁定则优先 uinput 触摸上滑，再退 uitest swipe。
# ---------------------------------------------------------------------------
screen_locked() {
  local out
  out="$(dsh "hidumper -s ScreenlockService -a '-all'" 2>/dev/null || true)"
  printf '%s\n' "$out" | grep -qE 'screenLocked[[:space:]]+true' && return 0
  printf '%s\n' "$out" | grep -qE 'screenLocked[[:space:]]+false' && return 1
  # 服务不可用/解析失败：保守认为已解锁（后续截图会暴露问题）
  return 1
}

wake_screen() {
  # snapshot 失败可能因为屏幕休眠；用 uiInput keyEvent Power 唤醒一次
  dsh 'uitest uiInput keyEvent Power' >/dev/null 2>&1 || true
  sleep 2
}

unlock_screen() {
  resolve_target
  local res w h x y1 y2 attempt
  screen_locked || { log "屏幕已解锁（幂等跳过）"; return 0; }
  log "屏幕已锁定，执行上滑解锁 ..."
  res="$(screen_size 2>/dev/null || true)"
  if [ -n "$res" ]; then w="${res% *}"; h="${res#* }"; else w=1320; h=2856; fi
  x=$((w / 2))
  y1=$((h * 85 / 100))
  y2=$((h * 40 / 100))
  for attempt in 1 2; do
    # uinput -T -m: 触摸下压→平滑移动到目标（第 5 个参数为平滑时间 ms）
    dsh "uinput -T -m $x $y1 $x $y2 600 500" >/dev/null 2>&1 || true
    sleep 2
    screen_locked || { log "解锁成功（uinput 上滑）"; return 0; }
    # 兜底：uitest 注入手势
    dsh "uitest uiInput swipe $x $y1 $x $y2 800" >/dev/null 2>&1 || true
    sleep 2
    screen_locked || { log "解锁成功（uitest swipe）"; return 0; }
  done
  die "解锁失败：请在模拟器窗口手动上滑解锁后重试（解锁逻辑见 emu.sh unlock_screen）"
}

# ---------------------------------------------------------------------------
# 通用子命令
# ---------------------------------------------------------------------------
cmd_list() {
  local json t
  json="$(instances_json || echo '[]')"
  echo "== 模拟器实例（Emulator -list -details）=="
  printf '%-18s %-9s %-24s %-8s %s\n' "NAME" "TYPE" "OS" "RUNNING" "IMAGE"
  if printf '%s' "$json" | jq -e 'type == "array"' >/dev/null 2>&1; then
    # 注意：jq 输出 TSV 后用 awk -F'\t' 解析（bash read 会把连续 tab 当空白折叠，导致空字段错位）
    printf '%s' "$json" | jq -r '.[] | [.name, .deviceType, (.["os.osVersion"] // "-"), .isRunning, (.imageSubPath // "-")] | @tsv' 2>/dev/null |
      awk -F'\t' '{ printf "%-18s %-9s %-24s %-8s %s\n", $1, $2, $3, $4, $5 }'
  else
    warn "无法解析实例列表（jq 输出异常），原始输出："
    printf '%s\n' "$json"
  fi

  echo
  echo "== hdc targets =="
  t="$(list_targets || true)"
  if [ -z "$t" ]; then
    echo "(无)  —— 模拟器未运行或仍在引导"
  else
    printf '%s\n' "$t" | sed 's/^/  /'
  fi

  if [ -n "$t" ]; then
    TARGET="$(printf '%s\n' "$t" | head -1)"
    echo
    echo "== 当前设备 =="
    printf '  %s\n' "$(device_summary 2>/dev/null || echo '(设备信息读取失败)')"
  fi

  echo
  echo "== 应用 =="
  if [ -n "$t" ]; then
    local bm ver_name ver_code pid
    bm="$(dsh "bm dump -n $BUNDLE" 2>/dev/null || true)"
    ver_name="$(printf '%s\n' "$bm" | grep '"versionName"' | tail -1 | sed 's/.*"versionName": *"\([^"]*\)".*/\1/' || true)"
    ver_code="$(printf '%s\n' "$bm" | grep '"versionCode"' | tail -1 | sed 's/.*"versionCode": *\([0-9]*\).*/\1/' || true)"
    pid="$(dsh "pidof $BUNDLE" 2>/dev/null | sed 's/^[[:space:]]*//' || true)"
    printf '  bundle: %s\n' "$BUNDLE"
    if [ -n "$ver_name" ]; then
      printf '  已安装: %s (versionCode=%s)\n' "$ver_name" "${ver_code:-?}"
    else
      printf '  已安装: 否\n'
    fi
    printf '  进程: %s\n' "${pid:-未运行}"
  else
    echo "  (设备不可用，跳过)"
  fi
}

cmd_status() {
  local running
  running="$(running_instances || true)"
  echo "运行中的模拟器: ${running:-（无）}"
  TARGET=""
  if ! discover_target >/dev/null 2>&1; then
    echo "hdc 设备: （无）"
    exit 0
  fi
  TARGET="$(discover_target)"
  echo "hdc 设备: $TARGET"
  echo "设备信息: $(device_summary 2>/dev/null || echo '读取失败')"
  local pid=""
  pid="$(dsh "pidof $BUNDLE" 2>/dev/null | sed 's/^[[:space:]]*//' || true)"
  echo "应用进程: ${pid:-未运行}"
}

cmd_devices() {
  echo "phone  -> ${EMU_PHONE_NAME}（devicetype=phone）"
  echo "2in1   -> ${EMU_2IN1_NAME}（devicetype=2in1 / PC）"
  echo "tablet -> ${EMU_TABLET_NAME}（devicetype=Tablet，需先 create-tablet 且镜像已下载）"
}

# ---------------------------------------------------------------------------
# 模拟器启停
# ---------------------------------------------------------------------------
stop_one() {
  local name="$1" waited=0
  if ! instance_exists "$name"; then
    warn "实例不存在，忽略: $name"
    return 0
  fi
  if ! running_instances | grep -qx "$name"; then
    log "实例未运行，无需停止: $name"
    return 0
  fi
  log "停止模拟器: $name"
  "$EMULATOR" -stop "$name" >/dev/null 2>&1 || warn "Emulator -stop $name 返回非 0（继续等待其退出）"
  while [ "$waited" -lt "$STOP_TIMEOUT" ]; do
    if ! running_instances | grep -qx "$name" && ! emu_process_alive "$name"; then
      log "已停止: ${name}（等待 ${waited}s）"
      return 0
    fi
    sleep 2
    waited=$((waited + 2))
  done
  warn "停止超时（${STOP_TIMEOUT}s）：$name 可能仍在运行，请检查宿主屏幕上的模拟器窗口"
  return 1
}

stop_all_running() {
  local names name
  names="$(running_instances || true)"
  [ -z "$names" ] && return 0
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    stop_one "$name" || true
  done <<<"$names"
  # 清理可能残留的 hdc target（模拟器已退出但 target 未刷新）
  local waited=0
  while [ "$waited" -lt 30 ]; do
    [ -z "$(list_targets || true)" ] && return 0
    sleep 2
    waited=$((waited + 2))
  done
  warn "仍有 hdc target 残留，可用 'hdc kill -r' 重启 hdc server 后重试"
}

start_instance() {
  local name="$1" timeout="${2:-$BOOT_TIMEOUT}" logf waited=0 died=0 t
  need_hdc
  need_emulator
  if ! instance_exists "$name"; then
    die "模拟器实例不存在: ${name}（./emu.sh list 查看已部署实例；平板见 ./emu.sh create-tablet）"
  fi

  local running
  running="$(running_instances || true)"
  if [ -n "$running" ] && ! printf '%s\n' "$running" | grep -qx "$name"; then
    log "16GB 内存约束：同一时间只跑一个模拟器。先停止: $(printf '%s' "$running" | tr '\n' ' ')"
    stop_all_running
  fi

  if printf '%s\n' "$running" | grep -qx "$name"; then
    log "实例已在运行: ${name}，跳过启动，直接等待就绪"
    TARGET=""
    wait_for_device_shell "$timeout" && wait_for_boot "$timeout" && wait_for_ui "$timeout" || {
      tail -30 "$(ls -t /tmp/gogauge-emu-start-*.log 2>/dev/null | head -1)" >&2 2>/dev/null || true
      die "实例 $name 运行中但 ${timeout}s 内未就绪"
    }
    unlock_screen
    log "设备就绪: $(device_summary)"
    return 0
  fi

  # 启动前确保旧 target 已消失，避免连到已死端口
  TARGET=""
  logf="/tmp/gogauge-emu-start-$(printf '%s' "$name" | tr ' /' '__').log"
  log "启动模拟器: $name"
  log "  GUI 窗口会出现在宿主屏幕（勿关闭），启动日志: $logf"
  nohup "$EMULATOR" -start "$name" -instancePath "$INSTANCE_PATH" -imageRoot "$IMAGE_ROOT" >"$logf" 2>&1 &
  local ep=$!
  log "Emulator pid=$ep"

  local shell_out=""
  while [ "$waited" -lt "$timeout" ]; do
    t="$(list_targets | head -1 || true)"
    if [ -n "$t" ]; then
      shell_out="$("$HDC" -t "$t" shell "echo gogauge-shell-ok" 2>/dev/null | tr -d '\r' || true)"
      case "$shell_out" in
        *gogauge-shell-ok*)
          TARGET="$t"
          log "hdc shell 就绪: ${TARGET}（等待 ${waited}s）"
          break
          ;;
      esac
    fi
    # 进程/日志早退检测：避免干等满超时
    if ! kill -0 "$ep" 2>/dev/null && ! emu_process_alive "$name"; then
      died=$((died + 3))
      if [ "$died" -ge 15 ]; then
        warn "Emulator 进程已退出且无对应实例进程，启动日志尾部："
        tail -40 "$logf" >&2 || true
        die "模拟器启动失败: ${name}（完整日志 ${logf}）"
      fi
    fi
    sleep 3
    waited=$((waited + 3))
  done
  [ -n "$TARGET" ] || {
    warn "启动日志尾部（${logf}）："
    tail -40 "$logf" >&2 || true
    die "模拟器启动后 ${timeout}s 内未出现可用的 hdc shell"
  }

  wait_for_boot "$timeout" || { warn "boot 完成标志超时"; die "设备未完成引导（${TARGET}）"; }
  wait_for_ui "$timeout" || die "窗口服务/桌面在 ${timeout}s 内未就绪（${TARGET}）"
  unlock_screen
  log "设备就绪: $(device_summary)"
}

cmd_start_phone() { need_emulator; acquire_lock; start_instance "$EMU_PHONE_NAME" "${1:-$BOOT_TIMEOUT}"; }
cmd_start_2in1()  { need_emulator; acquire_lock; start_instance "$EMU_2IN1_NAME" "${1:-$BOOT_TIMEOUT}"; }
cmd_start_tablet() {
  need_emulator
  acquire_lock
  if ! instance_exists "$EMU_TABLET_NAME"; then
    die "平板实例不存在: ${EMU_TABLET_NAME}。先运行 ./emu.sh create-tablet（需要本机已下载 Tablet 镜像）。替代方案：在 2in1 上用窗口缩放验证平板布局，见 docs/runtime-verification.md"
  fi
  start_instance "$EMU_TABLET_NAME" "${1:-$BOOT_TIMEOUT}"
}

cmd_start() {
  local name="${1:-}"
  [ -n "$name" ] || die "用法: ./emu.sh start <实例名>（./emu.sh list 查看）"
  need_emulator
  acquire_lock
  start_instance "$name" "${2:-$BOOT_TIMEOUT}"
}

cmd_stop() {
  local name="${1:-}"
  [ -n "$name" ] || die "用法: ./emu.sh stop <实例名|all>"
  need_emulator
  acquire_lock
  if [ "$name" = "all" ]; then
    stop_all_running
    return 0
  fi
  stop_one "$name"
}

cmd_wait() {
  local timeout="${1:-$BOOT_TIMEOUT}"
  acquire_lock
  wait_for_device_shell "$timeout" || die "设备 shell 在 ${timeout}s 内不可用"
  wait_for_boot "$timeout" || die "boot 未完成（${timeout}s）"
  wait_for_ui "$timeout" || die "桌面未就绪（${timeout}s）"
  unlock_screen
  log "设备就绪: $(device_summary)"
}

cmd_unlock() {
  acquire_lock
  resolve_target
  if ! dsh_quiet 'echo ok'; then
    wake_screen
  fi
  unlock_screen
}

# ---------------------------------------------------------------------------
# 构建 / 安装 / 启动 / 停止应用
# ---------------------------------------------------------------------------
cmd_build() {
  log "构建 HAP: ./scripts/build.sh hap"
  ( cd "$HARMONY_DIR" && ./scripts/build.sh hap )
  [ -f "$HAP" ] || die "构建后未找到 HAP: $HAP"
  log "构建完成: $HAP ($(du -h "$HAP" | cut -f1))"
}

cmd_install() {
  local arg="${1:-latest}" hap="$HAP"
  case "$arg" in
    latest|hap|"") hap="$HAP" ;;
    *) hap="$arg" ;;
  esac
  [ -f "$hap" ] || die "HAP 不存在: ${hap}（先 ./scripts/build.sh hap 或 ./emu.sh build；也可传路径）"
  acquire_lock
  resolve_target
  log "安装未签名 HAP（仅模拟器可用）: $hap ($(du -h "$hap" | cut -f1))"
  local out
  out="$("$HDC" -t "$TARGET" install -r "$hap" 2>&1 || true)"
  printf '%s\n' "$out" | sed 's/^/[hdc] /'
  if ! printf '%s' "$out" | grep -qiE "success"; then
    die "安装失败（见上方 hdc 输出）。确认已启动模拟器且 HAP 未被签名脚本锁定"
  fi
  log "安装成功: $BUNDLE"
}

cmd_launch() {
  acquire_lock
  resolve_target
  dsh_quiet 'echo ok' || die "设备 shell 不可用"
  screen_locked && unlock_screen || true
  local extra="$*"
  log "启动应用: aa start -a $ABILITY -b $BUNDLE ${extra}"
  local out
  out="$(dsh "aa start -a $ABILITY -b $BUNDLE $extra" 2>&1 || true)"
  printf '%s\n' "$out" | sed 's/^/[aa] /'
  if ! printf '%s' "$out" | grep -qiE "success|already"; then
    warn "aa start 输出中没有成功标记，继续用进程检查兜底"
  fi
  sleep "$APP_SETTLE"
  local pid
  pid="$(dsh "pidof $BUNDLE" 2>/dev/null | sed 's/^[[:space:]]*//' || true)"
  [ -n "$pid" ] || die "启动后未找到应用进程: ${BUNDLE}（查看 ./emu.sh logs --app）"
  log "应用运行中: pid=$pid"
}

cmd_stop_app() {
  acquire_lock
  resolve_target
  log "强制停止应用: $BUNDLE"
  dsh "aa force-stop $BUNDLE" 2>&1 | sed 's/^/[aa] /' || true
  sleep 1
  local pid
  pid="$(dsh "pidof $BUNDLE" 2>/dev/null | sed 's/^[[:space:]]*//' || true)"
  if [ -n "$pid" ]; then
    warn "进程仍存在: ${pid}（可能正在退出）"
  else
    log "应用已停止"
  fi
}

# ---------------------------------------------------------------------------
# 清空应用数据（demo/演示模式截图前的确定性初始化）
#   背景：`hdc install -r` 会保留旧版本数据。若旧数据里存在「token 为空的账号」，
#   DemoSeed.run() 会走 switchAccount 分支而不再创建 demo 账号，导致 demo=1
#   启动后仍停在欢迎页（Index 以 acct.hasToken 判断登录态）。
#   因此演示截图前用 `bm clean -n <bundle> -d -c` 清库，让 DemoSeed 从零 seed。
# ---------------------------------------------------------------------------
cmd_reset_app() {
  acquire_lock
  resolve_target
  log "强制停止应用: $BUNDLE"
  dsh "aa force-stop $BUNDLE" >/dev/null 2>&1 || true
  sleep 1
  log "清空应用数据/缓存: bm clean -n $BUNDLE -d -c"
  local out
  out="$(dsh "bm clean -n $BUNDLE -d -c" 2>&1 || true)"
  printf '%s\n' "$out" | sed 's/^/[bm] /'
  # 校验：数据库目录应被清空（不存在或仅空目录）
  local dbfiles
  dbfiles="$(dsh "find /data/app/el2/100/database/$BUNDLE -type f 2>/dev/null | wc -l" 2>/dev/null | tr -d ' ' || true)"
  log "应用数据已清空（剩余 db 文件数: ${dbfiles:-0}）"
}

# ---------------------------------------------------------------------------
# 截图
#   snapshot_display 在 /data/local/tmp 生成 jpeg，再 file recv 回传。
#   输出目录默认 docs/store-assets/screenshots/<device-type>/
#     phone->phone, 2in1->pc, tablet->tablet
# ---------------------------------------------------------------------------
device_shot_dir() {
  local dtype
  dtype="$(device_type 2>/dev/null || true)"
  case "$dtype" in
    phone) echo "phone" ;;
    2in1) echo "pc" ;;
    tablet) echo "tablet" ;;
    *) echo "${dtype:-unknown}" ;;
  esac
}

cmd_shot() {
  local out="${1:-}"
  acquire_lock
  resolve_target
  local dev_dir ts remote outlog
  dev_dir="$(device_shot_dir)"
  ts="$(date +%Y%m%d-%H%M%S)"
  if [ -z "$out" ]; then
    mkdir -p "$SHOT_ROOT/$dev_dir"
    out="$SHOT_ROOT/$dev_dir/smoke-$ts.jpeg"
  else
    case "$out" in
      */*) mkdir -p "$(dirname "$out")" ;;
      *)
        mkdir -p "$SHOT_ROOT/$dev_dir"
        out="$SHOT_ROOT/$dev_dir/$out"
        case "$out" in
          *.jpeg|*.jpg|*.png) ;;
          *) out="$out.jpeg" ;;
        esac
        ;;
    esac
  fi
  remote="/data/local/tmp/gogauge-shot-$$.jpeg"
  dsh_quiet "rm -f $remote" || true
  outlog="$(dsh "snapshot_display -f $remote" 2>&1 || true)"
  if ! printf '%s' "$outlog" | grep -q "success"; then
    # 屏幕可能休眠：唤醒后重试一次
    warn "首次截图失败，尝试唤醒屏幕后重试"
    wake_screen
    outlog="$(dsh "snapshot_display -f $remote" 2>&1 || true)"
    printf '%s' "$outlog" | grep -q "success" || die "截图失败: $(printf '%s' "$outlog" | tail -3 | tr '\n' ' ')"
  fi
  "$HDC" -t "$TARGET" file recv "$remote" "$out" >/dev/null 2>&1 || die "截图回传失败: $remote -> $out"
  dsh_quiet "rm -f $remote" || true
  [ -s "$out" ] || die "截图文件为空: $out"
  log "截图: $out ($(du -h "$out" | cut -f1))"
  printf '%s\n' "$out"
}

# ---------------------------------------------------------------------------
# 日志 / crash 检查
# ---------------------------------------------------------------------------
hilog_dump() { dsh "hilog -x" 2>/dev/null || true; }

cmd_logs() {
  local clear=0 app=0 lines=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --clear) clear=1; shift ;;
      --app) app=1; shift ;;
      -n) lines="${2:-200}"; shift 2 ;;
      *) die "logs 未知参数: $1（支持 --clear / --app / -n <行数>）" ;;
    esac
  done
  acquire_lock
  resolve_target
  if [ "$clear" = "1" ]; then
    dsh_quiet 'hilog -r' || warn "hilog -r 失败（缓冲区可能不可清）"
    log "已清空 hilog 缓冲区"
  fi
  local dump pid=""
  dump="$(hilog_dump)"
  if [ "$app" = "1" ]; then
    pid="$(dsh "pidof $BUNDLE" 2>/dev/null | tr -d '\r' | awk '{print $1}' || true)"
    if [ -n "$pid" ]; then
      log "过滤应用日志: bundle=$BUNDLE pid=$pid"
      dump="$(printf '%s\n' "$dump" | grep -E -- "$BUNDLE|gogauge|(^|[^0-9])$pid([^0-9]|$)" || true)"
    else
      log "应用未运行，仅按 bundle 名过滤"
      dump="$(printf '%s\n' "$dump" | grep -E -- "$BUNDLE|gogauge" || true)"
    fi
  fi
  if [ -n "$lines" ]; then
    dump="$(printf '%s\n' "$dump" | tail -n "$lines")"
  fi
  printf '%s\n' "$dump"
}

cmd_crash_check() {
  local wait_s="$CRASH_WAIT" clear=1
  while [ $# -gt 0 ]; do
    case "$1" in
      --wait) wait_s="${2:-$CRASH_WAIT}"; shift 2 ;;
      --no-clear) clear=0; shift ;;
      *) die "crash-check 未知参数: $1（支持 --wait <秒> / --no-clear）" ;;
    esac
  done
  acquire_lock
  resolve_target
  local ts pid_before pid_after dump fault_before fault_after verdict=0
  ts="$(date +%Y%m%d-%H%M%S)"
  local logfile="/tmp/gogauge-crashcheck-$ts.log"

  if [ "$clear" = "1" ]; then
    dsh_quiet 'hilog -r' || warn "hilog -r 失败"
    log "已清空 hilog 缓冲区"
  fi
  fault_before="$(dsh 'ls -1 /data/log/faultlog/faultlogger 2>/dev/null' 2>/dev/null | sed '/^[[:space:]]*$/d' || true)"

  dsh_quiet "aa force-stop $BUNDLE" || true
  sleep 1
  log "启动应用并观察 ${wait_s}s（crash 检测窗口）..."
  dsh "aa start -a $ABILITY -b $BUNDLE" >/dev/null 2>&1 || true
  sleep "$wait_s"
  pid_after="$(dsh "pidof $BUNDLE" 2>/dev/null | tr -d '\r' | awk '{print $1}' || true)"

  dump="$(hilog_dump)"
  printf '%s\n' "$dump" >"$logfile"

  # 判据 1：进程存活
  if [ -z "$pid_after" ]; then
    warn "应用进程不存在（可能启动失败或崩溃退出）"
    verdict=1
  else
    log "应用进程存活: pid=$pid_after"
  fi

  # 判据 2：hilog 中与本应用相关的 FATAL / ERROR / 崩溃关键字
  local hits
  hits="$(printf '%s\n' "$dump" | grep -iE "FATAL|cppcrash|jscrash|appfreeze|signal [0-9]+|SIGSEGV|SIGABRT" | grep -iE -- "$BUNDLE|gogauge|$pid_after" || true)"
  if [ -n "$hits" ]; then
    warn "hilog 中发现疑似崩溃/致命错误（$(printf '%s\n' "$hits" | wc -l | tr -d ' ') 行）："
    printf '%s\n' "$hits" | head -20 | sed 's/^/    /' >&2
    verdict=1
  else
    log "hilog 中未发现本应用相关 FATAL/崩溃关键字"
  fi

  # 判据 3：faultlogger 新增文件（含本应用包名）
  fault_after="$(dsh 'ls -1 /data/log/faultlog/faultlogger 2>/dev/null' 2>/dev/null | sed '/^[[:space:]]*$/d' || true)"
  local new_faults
  new_faults="$(comm -13 <(printf '%s\n' "$fault_before" | sort) <(printf '%s\n' "$fault_after" | sort) 2>/dev/null | grep -iE -- "$BUNDLE|gogauge" || true)"
  if [ -n "$new_faults" ]; then
    warn "faultlogger 新增本应用故障文件："
    printf '%s\n' "$new_faults" | sed 's/^/    /' >&2
    verdict=1
  else
    log "faultlogger 无本应用新增故障文件"
  fi

  log "hilog 全量快照: $logfile"
  if [ "$verdict" = "0" ]; then
    log "结论: PASS（无 crash 迹象）"
    return 0
  fi
  warn "结论: FAIL（发现 crash 迹象，详见上方输出与 ${logfile}）"
  return 1
}

# ---------------------------------------------------------------------------
# 平板实例创建（离线不下载镜像）
#   本机镜像目录只有 HarmonyOS-6.1.1/{phone_all_arm,pc_all_arm}，
#   无 tablet 镜像；-imageList -deviceType Tablet 显示 6.1.1(24) downloaded=false。
#   命令仍会尝试一次以记录真实报错，并在失败时给出替代验证方案。
# ---------------------------------------------------------------------------
cmd_create_tablet() {
  need_emulator
  acquire_lock
  if instance_exists "$EMU_TABLET_NAME"; then
    log "平板实例已存在: $EMU_TABLET_NAME"
    return 0
  fi
  log "检查本机 Tablet 镜像（不会触发下载）..."
  local images downloaded
  images="$("$EMULATOR" -imageList -deviceType Tablet 2>/dev/null || true)"
  downloaded="$(printf '%s' "$images" | jq -r --arg os "$TABLET_OS_VERSION" '.[] | select(.osVersion == $os) | .downloaded' 2>/dev/null | head -1 || true)"
  log "Tablet ${TABLET_OS_VERSION} 镜像 downloaded=${downloaded:-未知}"
  if [ "$downloaded" != "true" ]; then
    warn "本地未下载 Tablet ${TABLET_OS_VERSION} 镜像。仍尝试 -create 以记录真实错误（不会下载镜像）..."
  fi
  local out rc=0
  out="$("$EMULATOR" -create "$EMU_TABLET_NAME" -deviceType "$TABLET_DEVICE_TYPE" -osVersion "$TABLET_OS_VERSION" -instancePath "$INSTANCE_PATH" -imageRoot "$IMAGE_ROOT" 2>&1)" || rc=$?
  printf '%s\n' "$out" | sed 's/^/[create] /'
  if [ "$rc" -ne 0 ] || ! instance_exists "$EMU_TABLET_NAME"; then
    cat >&2 <<'EOF'

[emu][error] 平板实例创建失败：本机缺少 Tablet 系统镜像（未下载，且任务禁止下载大镜像）。
[emu] 替代验证方案（已写入 docs/runtime-verification.md）：
[emu]   1) 用 2in1 实例（MateBook Pro, 3120x2080 @304dpi）验证平板/大屏布局：
[emu]      平板布局按 ArkUI 断点（lg: 窗口宽度 > 840vp）生效，2in1 全屏宽度约 1642vp，
[emu]      已覆盖 tablet 的 lg 断点。窗口比例调节实测方法（capture-store-shots.sh 已实现）：
[emu]        a) 点标题栏最左按钮（最大化）→ 3120x1955 全屏；
[emu]        b) `uitest uiInput drag` 拖应用窗口右下角 → 可拉到任意尺寸，
[emu]           例如 2000x1500px ≈ 4:3（1055vp 宽，满足 lg 断点），作为平板比例替代验证；
[emu]      注意：`aa start --ww/--wh` 在 2in1 上被忽略（实测），只能 --wl/--wt 移窗口。
[emu]   2) 如后续允许下载镜像：`Emulator -install -deviceType Tablet -osVersion "HarmonyOS 6.1.1(24)"`
[emu]      然后重新执行 `./emu.sh create-tablet`。
[emu]   3) 真机平板用签名 HAP 验证（scripts/install.sh）。
EOF
    return 3
  fi
  log "平板实例创建成功: $EMU_TABLET_NAME"
}

# ---------------------------------------------------------------------------
# UI 自动化基础能力（capture-store-shots.sh / uitools.py 依赖）
#   系统自带 uitest 提供：dumpLayout（UI 树）、uiInput click/swipe/drag/
#   keyEvent/inputText。layout JSON 用同目录 uitools.py 解析。
# ---------------------------------------------------------------------------
cmd_dump_ui() {
  local out="${1:-/tmp/gogauge-layout.json}" remote="/data/local/tmp/gogauge-layout-$$.json"
  acquire_lock
  resolve_target
  dsh "uitest dumpLayout -p $remote" >/dev/null 2>&1 || true
  rm -f "$out"
  if ! "$HDC" -t "$TARGET" file recv "$remote" "$out" >/dev/null 2>&1 || [ ! -s "$out" ]; then
    dsh_quiet "rm -f $remote" || true
    die "UI layout 导出失败（$remote -> $out）。应用可能未在前台，或 uitest 不可用"
  fi
  dsh_quiet "rm -f $remote" || true
  printf '%s\n' "$out"
}

cmd_tap() {
  local x="${1:-}" y="${2:-}"
  [ -n "$x" ] && [ -n "$y" ] || die "用法: ./emu.sh tap <x> <y>（坐标来自 dump-ui/uitools.py 解析）"
  acquire_lock
  resolve_target
  dsh "uitest uiInput click $x $y" 2>&1 | sed 's/^/[ui] /' || true
}

cmd_swipe() {
  local x1="${1:-}" y1="${2:-}" x2="${3:-}" y2="${4:-}" velocity="${5:-600}"
  [ -n "$y2" ] || die "用法: ./emu.sh swipe <x1> <y1> <x2> <y2> [velocity]"
  acquire_lock
  resolve_target
  dsh "uitest uiInput swipe $x1 $y1 $x2 $y2 $velocity" 2>&1 | sed 's/^/[ui] /' || true
}

cmd_drag() {
  local x1="${1:-}" y1="${2:-}" x2="${3:-}" y2="${4:-}" velocity="${5:-600}"
  [ -n "$y2" ] || die "用法: ./emu.sh drag <x1> <y1> <x2> <y2> [velocity]（用于拖窗口边缘改大小）"
  acquire_lock
  resolve_target
  dsh "uitest uiInput drag $x1 $y1 $x2 $y2 $velocity" 2>&1 | sed 's/^/[ui] /' || true
}

cmd_key() {
  local k="${1:-Back}"
  acquire_lock
  resolve_target
  dsh "uitest uiInput keyEvent $k" 2>&1 | sed 's/^/[ui] /' || true
}

# ---------------------------------------------------------------------------
# usage
# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
GoGauge HarmonyOS 模拟器工具链（emu.sh）

用法: ./emu.sh <命令> [参数]

设备与实例:
  list                     列出已部署模拟器实例、hdc target、当前设备与应用状态
  status                   精简状态：运行中的实例 + hdc 设备 + 应用进程
  devices                  打印 phone / 2in1 / tablet 对应的实例名
  start <name>             启动指定实例（自动停止其它实例，16GB 内存约束）
  start-phone              启动手机实例（默认 "Pura 90"）
  start-2in1               启动 2in1/PC 实例（默认 "MateBook Pro"）
  start-tablet             启动平板实例（默认 "GoGauge_Tablet"，需先 create-tablet）
  stop <name|all>          停止实例（all = 停止所有运行中的实例）
  create-tablet            尝试创建平板实例（镜像未下载时会失败并给出替代方案）

设备就绪:
  wait [timeout]           等待 hdc shell + boot 完成 + 桌面就绪 + 解锁
  unlock                   解锁屏幕（已解锁则幂等跳过）

应用:
  build                    调用 ../build.sh 构建 HAP
  install [latest|<hap>]   安装 HAP（默认最新构建产物；模拟器接受未签名 HAP）
  reset-app                强制停止应用 + 清空应用数据/缓存（demo 截图前确定性初始化）
  launch [--ps k v ...]    启动应用，额外参数透传给 `aa start`
                           ⚠️ --ps 必须是「key value」两个 token：--ps demo 1
  stop-app                 强制停止应用

截图与日志:
  shot [out]               截图；省略 out 时自动命名到
                           docs/store-assets/screenshots/<phone|pc|tablet>/
                           out 不含 / 时作为该目录下的文件名（自动补 .jpeg）
  logs [--clear] [--app] [-n N]
                           导出 hilog（--clear 先清空；--app 仅本应用相关；-n 取尾部）
  crash-check [--wait N] [--no-clear]
                           清日志→停应用→启动→观察 N 秒→检查进程/FATAL/faultlogger

UI 自动化（基于系统 uitest；数据结构由同目录 uitools.py 解析）:
  dump-ui [outfile]        导出当前 UI 树 JSON（默认 /tmp/gogauge-layout.json）
  tap <x> <y>              uiInput 点击
  swipe <x1> <y1> <x2> <y2> [velocity]
                           uiInput 滑动/快速滑动
  drag <x1> <y1> <x2> <y2> [velocity]
                           uiInput 拖拽（2in1 拖窗口右下角可改窗口大小）
  key <Back|Home|Power>    注入按键

环境变量:
  BUNDLE=...               应用包名（默认 io.github.yphyphyph.gogauge）
  ABILITY=...              Ability 名（默认 EntryAbility）
  HAP=...                  HAP 路径（默认 entry/build/.../entry-default-unsigned.hap）
  HDC_BIN / EMU_BIN        hdc / Emulator 路径
  EMU_PHONE_NAME / EMU_2IN1_NAME / EMU_TABLET_NAME
                           实例名覆盖
  SHOT_ROOT=...            截图根目录（默认 harmonyos/docs/store-assets/screenshots）
  EMU_LOCK_DIR=...         设备锁目录（默认 /tmp/gogauge-emu.lock）
  EMU_LOCK_TIMEOUT=180     等锁超时秒数；EMU_NO_LOCK=1 跳过锁
  EMU_BOOT_TIMEOUT=300     启动/引导超时秒数
  HDC_TARGET=...           手动指定 hdc target（默认自动发现唯一/第一个）

示例:
  ./emu.sh list && ./emu.sh start-phone && ./emu.sh install latest
  ./emu.sh launch && ./emu.sh shot smoke-welcome
  ./emu.sh crash-check --wait 15
  ./emu.sh stop all && ./emu.sh start-2in1
EOF
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
  local cmd="${1:-}"
  [ -n "$cmd" ] || { usage; exit 1; }
  shift || true
  case "$cmd" in
    list)          cmd_list "$@" ;;
    status)        cmd_status "$@" ;;
    devices)       cmd_devices "$@" ;;
    start)         cmd_start "$@" ;;
    start-phone)   cmd_start_phone "$@" ;;
    start-2in1)    cmd_start_2in1 "$@" ;;
    start-tablet)  cmd_start_tablet "$@" ;;
    stop)          cmd_stop "$@" ;;
    wait)          cmd_wait "$@" ;;
    unlock)        cmd_unlock "$@" ;;
    build)         cmd_build "$@" ;;
    install)       cmd_install "$@" ;;
    launch)        cmd_launch "$@" ;;
    stop-app)      cmd_stop_app "$@" ;;
    reset-app)     cmd_reset_app "$@" ;;
    shot)          cmd_shot "$@" ;;
    logs)          cmd_logs "$@" ;;
    crash-check)   cmd_crash_check "$@" ;;
    create-tablet) cmd_create_tablet "$@" ;;
    dump-ui)       cmd_dump_ui "$@" ;;
    tap)           cmd_tap "$@" ;;
    swipe)         cmd_swipe "$@" ;;
    drag)          cmd_drag "$@" ;;
    key)           cmd_key "$@" ;;
    help|-h|--help) usage ;;
    *)             usage; die "未知命令: $cmd" ;;
  esac
}

main "$@"
