#!/usr/bin/env bash
# =============================================================================
# GoGauge HarmonyOS — 商店截图流水线
#
# 按「设备形态 × 页面 × 亮/暗」批量截图，输出到
#   docs/store-assets/screenshots/{phone,pc,tablet}/<page>-<light|dark>.jpeg
#
# 每页流程（与 Lead 约定一致）：
#   1) emu.sh stop-app            —— 保证每次都是冷启动（demo 参数幂等）
#   2) aa start 带调试参数         —— demo=1 / lang=zh|en / theme=light|dark / page=<page>
#      参数格式必须是 `--ps <key> <value>`（两个独立 token；`--ps page=home`
#      会被 aa 拒绝，见 docs/runtime-verification.md）
#   3) 等待 settle 秒（默认 3）
#   4) 设备形态适配：手机直接截；PC 最大化窗口；平板（镜像缺失）用 2in1
#      窗口拉成 4:3 并裁剪 —— 标记为 degraded
#   5) snapshot_display 截图 + 页面去重校验（若各页截图完全相同，说明 page
#      参数未生效，资产移入 _degraded/ 并在汇总中记录，不冒充最终图）
#
# 依赖：同目录 emu.sh / uitools.py；macOS 的 sips（裁剪）。
#
# 示例：
#   ./capture-store-shots.sh --device phone --theme both
#   ./capture-store-shots.sh --device pc --pages home,stats
#   ./capture-store-shots.sh --all --build
#   ./capture-store-shots.sh --device tablet --no-crop --dry-run
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARMONY_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
EMU="$SCRIPT_DIR/emu.sh"
UITOOLS="$SCRIPT_DIR/uitools.py"
DEFAULT_OUT="$HARMONY_DIR/docs/store-assets/screenshots"

ALL_PAGES="home stats records settings"
TABLET_W=2000
TABLET_H=1500

DEVICES=""
PAGES=""
THEMES=""
OUT="$DEFAULT_OUT"
HAP="latest"
DO_BUILD=0
DO_INSTALL=1
DEMO_MODE="auto"          # auto|on|off
LANG_SEL="zh"
SETTLE=5
DRY_RUN=0
KEEP_RUNNING=0
TABLET_FALLBACK=1
CROP_TABLET=1
PC_MODE="maximized"       # maximized|windowed
PC_WINDOW_W=1280
PC_WINDOW_H=840
RESTORE_PHONE=0
TABLET_REAL=0
TABLET_DEGRADED=0        # 平板镜像缺失→用 2in1 窗口近似验证，产物一律标 DEGRADED
CLEAN_DATA=1             # 拍摄前清空应用数据（让 demo 从零 seed，账号名/数据一致）
TS="$(date +%Y%m%d-%H%M%S)"
WORK_ROOT="/tmp/gogauge-capture-$TS"
SUMMARY_FILE="$WORK_ROOT/summary.txt"

log()  { printf '[shots] %s\n' "$*"; }
warn() { printf '[shots][warn] %s\n' "$*" >&2; }
die()  { printf '[shots][error] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
GoGauge HarmonyOS 商店截图流水线（capture-store-shots.sh）

用法: ./capture-store-shots.sh --device <phone|pc|tablet>[,<...>] [选项]
      ./capture-store-shots.sh --all [选项]

必选（二选一）:
  --device <列表>          设备形态，逗号分隔：phone / pc / tablet
  --all                    等价 --device phone,pc,tablet

页面与主题:
  --pages <列表>           要拍的页面，逗号分隔（默认 home,stats,records,settings）
                           额外支持 stats-scrolled：进统计页后下滑一屏，用于
                           展示趋势/热力图（命名 stats-scrolled-<theme>.jpeg）
  --theme <light|dark|both>
                           主题。默认：phone=both（亮+暗），pc/tablet=light；
                           显式指定后对所有设备生效
  --lang <zh|en>           语言（默认 zh）

调试参数（demo 模式）:
  --demo-mode <auto|on|off>
                           auto（默认）：携带 demo/lang/theme/page 参数启动，
                                        并用「页面截图去重」判断参数是否生效，
                                        未生效的资产移入 _degraded/
                           on：同上，但参数未生效时仍记录为 FAIL
                           off：普通启动（不传参数；需要人工/UI 导航，未实现→全 degraded）

输出:
  --out <目录>             截图根目录（默认 docs/store-assets/screenshots）
  --no-crop                tablet 退化模式不做窗口裁剪（默认裁剪为应用窗口）

设备形态适配:
  --pc-mode <maximized|windowed>
                           PC 截图窗口模式（默认 maximized：点标题栏最大化按钮；
                           windowed：缩放到 --pc-window 尺寸）
  --pc-window <WxH>         windowed 模式窗口尺寸（默认 1280x840）
  --tablet-window <WxH>     tablet 退化模式窗口尺寸（默认 2000x1500 ≈ 4:3）
  --no-tablet-fallback      平板镜像缺失时直接失败（默认退化到 2in1 4:3）
  --restore-phone          全部拍完后切回手机模拟器（默认保留最后一台）

构建与安装:
  --hap <latest|路径>      安装的 HAP（默认最新构建产物）
  --build                  先执行 emu.sh build
  --no-install             不重装（用设备上已安装版本）
  --clean-data / --no-clean-data
                           拍摄前清空应用数据并预热 seed（默认 --clean-data：
                           保证 demo 账号名为 OpenCode Go、数据为完整 180 天；
                           旧沙箱数据不会被 install -r 清除）

其它:
  --settle <秒>            每页启动后等待（默认 5）
  --keep-running           结束后不打印关机提示（脚本本就不会自动关模拟器）
  --dry-run                只打印计划，不操作设备
  -h, --help               显示本帮助

输出命名: <out>/<phone|pc|tablet>/<page>-<light|dark>.jpeg
退化/未生效的图: <out>/<phone|pc|tablet>/_degraded/<page>-<light|dark>.jpeg

注意：流水线会对每个设备执行 start-*（自动 stop 其它实例，16GB 单实例约束），
      全程约 3-6 分钟/设备。运行期间请勿手动操作模拟器。
      平板镜像未下载（本机只有 phone/pc 6.1.1 镜像），tablet 形态默认用
      2in1 窗口 4:3 缩放近似验证，会在汇总中标注 DEGRADED。
EOF
}

# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
add_device() {
  local d
  for d in $(printf '%s' "$1" | tr ',' ' '); do
    case "$d" in
      phone|pc|tablet) ;;
      *) die "未知设备形态: ${d}（支持 phone/pc/tablet）" ;;
    esac
    DEVICES="${DEVICES:+$DEVICES }$d"
  done
}

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --device)      [ $# -ge 2 ] || die "--device 需要参数"; add_device "$2"; shift 2 ;;
      --all)         add_device "phone,pc,tablet"; shift ;;
      --pages)       PAGES="${2//,/ }"; shift 2 ;;
      --theme)       THEMES="$2"; shift 2 ;;
      --out)         OUT="$2"; shift 2 ;;
      --hap)         HAP="$2"; shift 2 ;;
      --build)       DO_BUILD=1; shift ;;
      --no-install)  DO_INSTALL=0; shift ;;
      --clean-data)  CLEAN_DATA=1; shift ;;
      --no-clean-data) CLEAN_DATA=0; shift ;;
      --demo-mode)   DEMO_MODE="$2"; shift 2 ;;
      --lang)        LANG_SEL="$2"; shift 2 ;;
      --settle)      SETTLE="$2"; shift 2 ;;
      --tablet-window)
        TABLET_W="${2%x*}"; TABLET_H="${2#*x}"; shift 2 ;;
      --no-tablet-fallback) TABLET_FALLBACK=0; shift ;;
      --no-crop)     CROP_TABLET=0; shift ;;
      --pc-mode)     PC_MODE="$2"; shift 2 ;;
      --pc-window)
        PC_WINDOW_W="${2%x*}"; PC_WINDOW_H="${2#*x}"; shift 2 ;;
      --restore-phone) RESTORE_PHONE=1; shift ;;
      --keep-running) KEEP_RUNNING=1; shift ;;
      --dry-run)     DRY_RUN=1; shift ;;
      -h|--help)     usage; exit 0 ;;
      *) usage; die "未知参数: $1" ;;
    esac
  done
  [ -n "$DEVICES" ] || { usage; die "必须指定 --device 或 --all"; }
  [ -n "$PAGES" ] || PAGES="$ALL_PAGES"
  case "$DEMO_MODE" in auto|on|off) ;; *) die "--demo-mode 只支持 auto|on|off" ;; esac
  case "$PC_MODE" in maximized|windowed) ;; *) die "--pc-mode 只支持 maximized|windowed" ;; esac
  case "$LANG_SEL" in zh|en) ;; *) die "--lang 只支持 zh|en" ;; esac
  # 页面名合法性（与 AppRoot 约定一致）
  local p
  for p in $PAGES; do
    case "$p" in
      home|stats|records|settings|stats-scrolled) ;;
      *) die "未知页面: ${p}（支持 home/stats/records/settings/stats-scrolled）" ;;
    esac
  done
}

# ---------------------------------------------------------------------------
# 设备与页面操作封装
# ---------------------------------------------------------------------------
run_emu() { "$EMU" "$@"; }

ensure_device() {
  local dev="$1"
  case "$dev" in
    phone)
      log "启动手机模拟器 ..."
      if [ "$DRY_RUN" = "1" ]; then log "[dry-run] emu.sh start-phone"; return 0; fi
      run_emu start-phone ;;
    pc)
      log "启动 2in1 模拟器 ..."
      if [ "$DRY_RUN" = "1" ]; then log "[dry-run] emu.sh start-2in1"; return 0; fi
      run_emu start-2in1 ;;
    tablet)
      if [ "$DRY_RUN" = "1" ]; then log "[dry-run] emu.sh start-tablet（失败则 2in1 退化）"; return 0; fi
      if run_emu start-tablet >"$WORK_ROOT/tablet-start.log" 2>&1; then
        TABLET_REAL=1
        log "平板实例启动成功（真实 tablet 形态）"
      else
        tail -5 "$WORK_ROOT/tablet-start.log" | sed 's/^/[shots] /' >&2 || true
        [ "$TABLET_FALLBACK" = "1" ] || die "平板实例不可用且 --no-tablet-fallback 已指定"
        warn "平板镜像/实例不可用，退化：用 2in1（MateBook Pro）窗口 ${TABLET_W}x${TABLET_H}（≈4:3）验证平板布局"
        TABLET_REAL=0
        TABLET_DEGRADED=1
        run_emu start-2in1
      fi ;;
  esac
}

install_hap() {
  [ "$DO_INSTALL" = "1" ] || { log "跳过安装（--no-install）"; return 0; }
  if [ "$DRY_RUN" = "1" ]; then log "[dry-run] emu.sh install $HAP"; return 0; fi
  log "安装 HAP: $HAP"
  run_emu install "$HAP"
}

dump_layout() {
  # 输出 layout JSON 的本机路径（emu.sh dump-ui 的最后一行）
  "$EMU" dump-ui "$1" 2>/dev/null | tail -1
}

# 确保 PC 应用窗口最大化（2in1 默认以 1280x840 浮动窗口打开）
maximize_window() {
  local layout tb bx by
  layout="$(dump_layout "$WORK_ROOT/layout-pc.json")"
  [ -n "$layout" ] || { warn "无法导出 UI 布局，跳过最大化"; return 1; }
  if python3 "$UITOOLS" maximized "$layout" >/dev/null 2>&1; then
    log "窗口已最大化"
    return 0
  fi
  tb="$(python3 "$UITOOLS" titlebar-buttons "$layout" 2>/dev/null | awk '$3=="maximize"{print $1, $2; exit}' || true)"
  if [ -z "$tb" ]; then
    warn "未找到窗口最大化按钮（可能非 2in1 窗口模式），按当前窗口截图"
    return 1
  fi
  read -r bx by <<<"$tb"
  log "点击最大化按钮 ($bx,$by)"
  "$EMU" tap "$bx" "$by" >/dev/null 2>&1 || true
  sleep 1
  layout="$(dump_layout "$WORK_ROOT/layout-pc.json")"
  if python3 "$UITOOLS" maximized "$layout" >/dev/null 2>&1; then
    log "窗口已最大化"
    return 0
  fi
  warn "最大化后未检测到全屏窗口，按当前窗口截图"
  return 1
}

# 若窗口已最大化先恢复，再拖右下角调整到目标尺寸
window_to_size() {
  local target_w="$1" target_h="$2"
  local layout tb b bx by cur wx wy ww wh plan
  layout="$(dump_layout "$WORK_ROOT/layout-size.json")"
  [ -n "$layout" ] || { warn "无法导出 UI 布局，跳过窗口缩放"; return 1; }
  if python3 "$UITOOLS" maximized "$layout" >/dev/null 2>&1; then
    tb="$(python3 "$UITOOLS" titlebar-buttons "$layout" 2>/dev/null | awk '$3=="maximize"{print $1, $2; exit}' || true)"
    if [ -n "$tb" ]; then
      log "先恢复窗口化: 点击 ($tb)"
      # shellcheck disable=SC2086
      "$EMU" tap $tb >/dev/null 2>&1 || true
      sleep 1
      layout="$(dump_layout "$WORK_ROOT/layout-size.json")"
    fi
  fi
  cur="$(python3 "$UITOOLS" window "$layout" 2>/dev/null || true)"
  if [ -z "$cur" ]; then
    warn "无法获取窗口 bounds，跳过缩放"
    return 1
  fi
  read -r wx wy ww wh <<<"$cur"
  if [ "$ww" = "$target_w" ] && [ "$wh" = "$target_h" ]; then
    log "窗口尺寸已满足 ${target_w}x${target_h}"
    return 0
  fi
  plan="$(python3 "$UITOOLS" drag-plan "$layout" "$target_w" "$target_h" 2>/dev/null || true)"
  if [ -z "$plan" ]; then
    warn "无法计算窗口缩放拖拽坐标"
    return 1
  fi
  log "调整窗口 ${ww}x${wh} -> ${target_w}x${target_h}: drag $plan"
  # shellcheck disable=SC2086
  "$EMU" drag $plan 800 >/dev/null 2>&1 || true
  sleep 1
  layout="$(dump_layout "$WORK_ROOT/layout-size.json")"
  cur="$(python3 "$UITOOLS" window "$layout" 2>/dev/null || true)"
  if [ -z "$cur" ]; then
    warn "缩放后无法读取窗口 bounds"
    return 1
  fi
  read -r wx wy ww wh <<<"$cur"
  if [ "$ww" != "$target_w" ] || [ "$wh" != "$target_h" ]; then
    warn "窗口缩放未达目标：期望 ${target_w}x${target_h}，实际 ${ww}x${wh}（按实际尺寸继续）"
    return 1
  fi
  log "窗口尺寸调整完成: ${ww}x${wh}"
  return 0
}

# 用 sips 把整屏截图裁剪为应用窗口区域（tablet 退化形态用）
crop_to_window() {
  local src="$1" dst="$2"
  local layout cur wx wy ww wh
  layout="$(dump_layout "$WORK_ROOT/layout-crop.json")"
  cur="$(python3 "$UITOOLS" window "$layout" 2>/dev/null || true)"
  if [ -z "$cur" ]; then
    warn "无法获取窗口 bounds，跳过裁剪（保留整屏图）"
    cp "$src" "$dst"
    return 0
  fi
  read -r wx wy ww wh <<<"$cur"
  if ! sips -c "$wh" "$ww" --cropOffset "$wy" "$wx" "$src" --out "$dst" >/dev/null 2>&1; then
    warn "sips 裁剪失败，保留整屏图"
    cp "$src" "$dst"
    return 0
  fi
  log "已裁剪为应用窗口 ${ww}x${wh}（offset ${wx},${wy}）"
}

# 强制页面重建：点侧边导航到别的页再切回。
# 背景（实测）：2in1 窗口从默认 1280px 拖大到 2000px 时，EditorialGrid 的列数
# 3->6 变化会残留旧行（用量概览出现 9 格、dumpLayout 里 总请求/总费用/会话数 各 2 个节点），
# 且等待/滚动/主题切换都不会消失，只有页面级重建（切 tab）能清掉。
# 平板退化截图在窗口缩放后调用本函数，保证画面正确。
force_page_rerender() {
  local page="$1" layout target_label other_label xy
  [ "$DRY_RUN" = "1" ] && return 0
  case "$page" in
    home) target_label="首页" ;;
    stats|stats-scrolled) target_label="统计" ;;
    records) target_label="使用记录" ;;
    settings) target_label="设置" ;;
    *) return 0 ;;
  esac
  if [ "$target_label" = "设置" ]; then other_label="首页"; else other_label="设置"; fi
  # 在侧边栏（x 最小）找导航项中心
  find_nav_xy() {
    local label="$1" l="$2"
    python3 "$UITOOLS" find "$l" "$label" 2>/dev/null | awk -F'|' '{split($1,a," "); if (a[1] != "") print a[1], a[2]}' | sort -n -k1,1 | head -1
  }
  layout="$(dump_layout "$WORK_ROOT/layout-rerender.json" 2>/dev/null || true)"
  [ -n "$layout" ] && [ -f "$layout" ] || return 1
  xy="$(find_nav_xy "$other_label" "$layout")"
  [ -n "$xy" ] || { log "未找到侧边导航「${other_label}」，跳过重渲染"; return 1; }
  log "窗口缩放后强制页面重建（→ ${other_label}）"
  # shellcheck disable=SC2086
  "$EMU" tap $xy >/dev/null 2>&1 || true
  sleep 1.5
  layout="$(dump_layout "$WORK_ROOT/layout-rerender2.json" 2>/dev/null || true)"
  [ -n "$layout" ] && [ -f "$layout" ] || return 1
  xy="$(find_nav_xy "$target_label" "$layout")"
  [ -n "$xy" ] || { log "切回「${target_label}」失败"; return 1; }
  # shellcheck disable=SC2086
  "$EMU" tap $xy >/dev/null 2>&1 || true
  sleep 1.5
  return 0
}

# 页内滚动一屏（用于 stats-scrolled：展示趋势图/热力图等首屏以下内容）
scroll_content() {
  local layout size w h
  layout="$(dump_layout "$WORK_ROOT/layout-scroll.json" 2>/dev/null || true)"
  [ -n "$layout" ] && [ -f "$layout" ] || return 1
  size="$(python3 "$UITOOLS" screen "$layout" 2>/dev/null || true)"
  [ -n "$size" ] || return 1
  w="${size% *}"
  h="${size#* }"
  # 实测最优构图：2 次标准上滑 + 2 次小幅上滑 →
  # 完整「用量趋势」+「日历热力图」+「模型用量趋势」同屏（且状态栏保持亮色）。
  log "页内下滑（${w}x${h}）"
  "$EMU" swipe "$((w / 2))" "$((h * 72 / 100))" "$((w / 2))" "$((h * 32 / 100))" 1200 >/dev/null 2>&1 || true
  sleep 1
  "$EMU" swipe "$((w / 2))" "$((h * 72 / 100))" "$((w / 2))" "$((h * 32 / 100))" 1200 >/dev/null 2>&1 || true
  sleep 1
  "$EMU" swipe "$((w / 2))" "$((h * 72 / 100))" "$((w / 2))" "$((h * 54 / 100))" 900 >/dev/null 2>&1 || true
  sleep 1
  "$EMU" swipe "$((w / 2))" "$((h * 72 / 100))" "$((w / 2))" "$((h * 54 / 100))" 900 >/dev/null 2>&1 || true
  sleep 1
}

# 启动某页：stop-app -> aa start（带 demo 参数）-> settle
launch_page() {
  local page="$1" theme="$2"
  if [ "$DRY_RUN" = "1" ]; then
    log "[dry-run] stop-app; aa start --ps demo 1 --ps lang $LANG_SEL --ps theme $theme --ps page $page"
    return 0
  fi
  "$EMU" stop-app >/dev/null 2>&1 || true
  sleep 1
  local page_param="$page"
  [ "$page" = "stats-scrolled" ] && page_param="stats"
  if [ "$DEMO_MODE" = "off" ]; then
    "$EMU" launch >/dev/null 2>&1 || die "应用启动失败（page=$page theme=${theme}）"
  else
    "$EMU" launch --ps demo 1 --ps lang "$LANG_SEL" --ps theme "$theme" --ps page "$page_param" \
      >/dev/null 2>&1 || die "应用启动失败（page=$page theme=${theme}，含 demo 参数）"
  fi
  sleep "$SETTLE"
  # 特殊页：进 stats 后下滑一屏
  if [ "$page" = "stats-scrolled" ]; then
    scroll_content || warn "stats-scrolled 下滑失败，按首屏截图"
  fi
}

# 截屏 -> 临时文件
capture_temp() {
  local file="$1"
  local got
  if [ "$DRY_RUN" = "1" ]; then
    log "[dry-run] emu.sh shot $file"
    return 0
  fi
  got="$("$EMU" shot "$file" 2>/dev/null | tail -1)"
  [ -f "$got" ] || die "截图失败: $file"
}

# 设置页检查：demo 模式下不应出现「调试」分组（SHOW_DEBUG_TOOLS 应被隐藏）。
# 上架截图拍到调试 UI 会被 AGC 审核挑出，故对 settings 页做文本检查并记录。
check_settings_debug_ui() {
  local theme="$1" layout texts leaks
  [ "$DEMO_MODE" = "off" ] && return 0
  layout="$(dump_layout "$WORK_ROOT/layout-settings-check-$theme.json" 2>/dev/null || true)"
  [ -n "$layout" ] && [ -f "$layout" ] || return 0
  texts="$(python3 "$UITOOLS" texts "$layout" 2>/dev/null || true)"
  leaks="$(printf '%s\n' "$texts" | grep -E "注入模拟数据|清除模拟数据|注入模拟|调试|Debug tools|Debug" || true)"
  if [ -n "$leaks" ]; then
    warn "【上架风险】设置页出现调试 UI 文本（demo 模式下 SHOW_DEBUG_TOOLS 未隐藏？）："
    printf '%s\n' "$leaks" | sed 's/^/[shots]   /' >&2
    printf '%s\n' "$leaks" >"$WORK_ROOT/SETTINGS_DEBUG_UI_LEAK-$theme.txt"
  else
    log "设置页调试 UI 检查通过（无调试文本）"
  fi
}

# 设备形态适配 + 截图
capture_page() {
  local dev="$1" page="$2" theme="$3" tmp="$4"
  if [ "$DRY_RUN" = "1" ]; then
    log "[dry-run] 设备形态适配 + 截图 $dev/$page/$theme -> $tmp"
    return 0
  fi
  case "$dev" in
    phone)
      capture_temp "$tmp" ;;
    pc)
      if [ "$PC_MODE" = "maximized" ]; then
        maximize_window >/dev/null 2>&1 || true
      else
        window_to_size "$PC_WINDOW_W" "$PC_WINDOW_H" >/dev/null 2>&1 || true
      fi
      capture_temp "$tmp" ;;
    tablet)
      if [ "$TABLET_REAL" = "1" ]; then
        capture_temp "$tmp"
      else
        # 退化：2in1 窗口拉到 4:3
        window_to_size "$TABLET_W" "$TABLET_H" >/dev/null 2>&1 || true
        # 窗口列数变化会让 EditorialGrid 残留旧行（实测 9 格 bug），必须重建页面
        force_page_rerender "$page" || true
        capture_temp "$tmp"
        if [ "$CROP_TABLET" = "1" ]; then
          local cropped="${tmp%.jpeg}.crop.jpeg"
          crop_to_window "$tmp" "$cropped"
          mv "$cropped" "$tmp"
        fi
      fi ;;
  esac
  # 设置页：拍摄后检查是否泄漏调试 UI（demo 模式）
  if [ "$page" = "settings" ]; then
    check_settings_debug_ui "$theme" || true
  fi
}

# 去重：同一设备+主题下，若多个页面截图完全相同 → page 参数未生效
# 返回 0 表示全部页面各不同（可信），1 表示存在重复（有页面需标记 degraded）
pages_distinct() {
  local files=("$@")
  local n=${#files[@]}
  [ "$n" -le 1 ] && return 0
  local hashes=() f h i j dup=0
  for f in "${files[@]}"; do
    hashes+=("$(md5 -q "$f" 2>/dev/null || echo "missing-$f")")
  done
  for ((i = 0; i < n; i++)); do
    for ((j = i + 1; j < n; j++)); do
      if [ "${hashes[$i]}" = "${hashes[$j]}" ]; then
        dup=1
      fi
    done
  done
  [ "$dup" = "0" ]
}

# 保存结果：唯一截图 -> 正式目录；重复截图 -> _degraded/
save_results() {
  local devdir="$1" theme="$2"
  shift 2
  local pairs=("$@")   # "page:tmpfile" ...
  local final_dir="$OUT/$devdir"
  local degraded_dir="$final_dir/_degraded"
  local pages=() files=() pair page tmp
  for pair in "${pairs[@]}"; do
    page="${pair%%:*}"
    tmp="${pair#*:}"
    pages+=("$page")
    files+=("$tmp")
  done
  local force_degraded=0
  if [ "$devdir" = "tablet" ] && [ "$TABLET_DEGRADED" = "1" ]; then
    force_degraded=1
  fi
  if [ "${#pages[@]}" -eq 1 ] && [ "$DEMO_MODE" != "off" ]; then
    # 单页无法通过「页面截图去重」验证 page 参数是否生效 → 保守标记 UNVERIFIED
    mkdir -p "$degraded_dir"
    for i in "${!pages[@]}"; do
      mv "${files[$i]}" "$degraded_dir/${pages[$i]}-${theme}.jpeg"
      record_summary "$devdir" "$theme" "${pages[$i]}" "UNVERIFIED" "$degraded_dir/${pages[$i]}-${theme}.jpeg"
      warn "UNVERIFIED $devdir/${pages[$i]}-${theme}.jpeg（只拍 1 页，无法验证 page 参数；至少拍 2 页才能去重校验）"
    done
  elif [ "$force_degraded" = "0" ] && pages_distinct "${files[@]}"; then
    mkdir -p "$final_dir"
    for i in "${!pages[@]}"; do
      mv "${files[$i]}" "$final_dir/${pages[$i]}-${theme}.jpeg"
      record_summary "$devdir" "$theme" "${pages[$i]}" "OK" "$final_dir/${pages[$i]}-${theme}.jpeg"
      log "OK   $devdir/${pages[$i]}-${theme}.jpeg"
    done
    # 整套默认页面全部通过校验时，清理之前旧版本遗留的 _degraded 残留
    if [ "$(echo $PAGES | wc -w | tr -d ' ')" -ge "$(echo $ALL_PAGES | wc -w | tr -d ' ')" ]; then
      rm -rf "$degraded_dir"
    fi
  else
    mkdir -p "$degraded_dir"
    local degrade_note=""
    if [ "$devdir" = "tablet" ] && [ "$TABLET_DEGRADED" = "1" ]; then
      degrade_note="【本机无 Tablet 系统镜像】用 2in1 窗口 ${TABLET_W}x${TABLET_H}（≈4:3）近似验证平板布局；非真实平板产物，不得作为平板商店图。"
    fi
    cat >"$degraded_dir/README.txt" <<EOF
DEGRADED 截图（$devdir / ${theme}）
$degrade_note
================================
本目录的图片不满足页面区分校验：多个 page 的截图完全相同，说明
--ps page <page> 启动参数未生效（旧 HAP 或 AppRoot 未支持初始 tab），
因此不能作为商店素材使用。
验证方式：capture-store-shots.sh 对同一设备+主题下各页截图做 md5 对比，
存在重复即视为参数未生效。
待 Lead 新 HAP（支持 demo/lang/theme/page 调试参数）构建并安装后，重新运行：
  ./capture-store-shots.sh --device $devdir --theme $theme
EOF
    for i in "${!pages[@]}"; do
      mv "${files[$i]}" "$degraded_dir/${pages[$i]}-${theme}.jpeg"
      record_summary "$devdir" "$theme" "${pages[$i]}" "DEGRADED" "$degraded_dir/${pages[$i]}-${theme}.jpeg"
      warn "DEGRADED $devdir/${pages[$i]}-${theme}.jpeg（各页截图相同，page 参数可能未生效）"
    done
  fi
}

record_summary() {
  mkdir -p "$WORK_ROOT"
  printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" >>"$SUMMARY_FILE"
}

# ---------------------------------------------------------------------------
# 单设备主流程
# ---------------------------------------------------------------------------
themes_for_device() {
  local dev="$1"
  if [ -n "$THEMES" ]; then
    case "$THEMES" in
      light|dark) echo "$THEMES" ;;
      both) echo "light dark" ;;
      *) die "--theme 只支持 light|dark|both" ;;
    esac
    return 0
  fi
  case "$dev" in
    phone) echo "light dark" ;;   # 手机亮/暗各一套
    *) echo "light" ;;            # PC/平板默认只拍亮色（暗色可选 --theme both）
  esac
}

dev_dir_name() {
  case "$1" in
    phone) echo "phone" ;;
    pc) echo "pc" ;;
    tablet) echo "tablet" ;;
  esac
}

capture_device() {
  local dev="$1"
  local devdir themes theme page tmp list file
  devdir="$(dev_dir_name "$dev")"
  log "========== 设备形态: $dev =========="
  ensure_device "$dev"
  install_hap
  if [ "$CLEAN_DATA" = "1" ]; then
    if [ "$DRY_RUN" = "1" ]; then
      log "[dry-run] emu.sh reset-app + 预热 demo seed"
    else
      log "清空应用数据（消除旧 seed 残留，确保 demo 账号名 OpenCode Go / 180 天数据完整）"
      "$EMU" reset-app >/dev/null 2>&1 || warn "reset-app 失败（继续，可能沿用旧数据）"
      # 预热：首次启动执行 180 天 seed（约 2-5s）；用 home 页预热避免首张截图拍到加载态
      log "预热 demo seed（首次启动注入 180 天数据）..."
      "$EMU" launch --ps demo 1 --ps lang "$LANG_SEL" --ps theme light --ps page home \
        >/dev/null 2>&1 || warn "预热启动失败（继续）"
      sleep 9
      "$EMU" stop-app >/dev/null 2>&1 || true
      sleep 1
    fi
  fi
  themes="$(themes_for_device "$dev")"
  for theme in $themes; do
    log "---------- $dev / $theme ----------"
    local workdir="$WORK_ROOT/$dev-$theme"
    mkdir -p "$workdir"
    local pairs=()
    for page in $PAGES; do
      log "拍摄 $dev / $page / $theme ..."
      tmp="$workdir/$page.jpeg"
      if [ "$DRY_RUN" = "1" ]; then
        log "[dry-run] 将截图 $tmp"
        capture_page "$dev" "$page" "$theme" "$tmp"
        continue
      fi
      launch_page "$page" "$theme"
      capture_page "$dev" "$page" "$theme" "$tmp"
      [ -s "$tmp" ] || die "截图文件为空: $tmp"
      pairs+=("$page:$tmp")
    done
    if [ "$DRY_RUN" = "1" ]; then
      log "[dry-run] 将保存 $dev/$theme 的 $(echo $PAGES | wc -w | tr -d ' ') 张到 $OUT/$devdir/"
      continue
    fi
    save_results "$devdir" "$theme" "${pairs[@]}"
  done
}

# ---------------------------------------------------------------------------
# 商店素材清单（供 release-materials 的 appgallery-metadata.md 引用）
# ---------------------------------------------------------------------------
write_manifest() {
  # 扫描输出目录下所有正式素材（顶层 *.jpeg，排除 smoke-* 证据图与 _degraded/）
  # 约定：清单放在 docs/store-assets/screenshot-manifest.md（与 screenshots/ 同级），
  # release-materials 的 appgallery-metadata.md 与 AGC 清单都引用该路径。
  local manifest
  manifest="$(cd "$OUT/.." && pwd)/screenshot-manifest.md"
  local rows="" devdir file page theme dim size dtype devname
  for devdir in phone pc tablet; do
    [ -d "$OUT/$devdir" ] || continue
    for file in "$OUT/$devdir"/*.jpeg; do
      [ -f "$file" ] || continue
      case "$(basename "$file")" in
        smoke-*) continue ;;
      esac
      page="$(basename "$file" .jpeg)"
      theme="light"
      case "$page" in
        *-dark) theme="dark"; page="${page%-dark}" ;;
        *-light) theme="light"; page="${page%-light}" ;;
      esac
      dim="$(sips -g pixelWidth -g pixelHeight "$file" 2>/dev/null | awk '/pixelWidth/{w=$2} /pixelHeight/{h=$2} END{printf "%sx%s", w, h}')"
      size="$(du -h "$file" | cut -f1 | tr -d ' ')"
      rows="${rows}| \`$devdir/$(basename "$file")\` | $devdir | $page | $theme | $dim | $size |\n"
    done
  done
  if [ -z "$rows" ]; then
    return 0
  fi
  {
    echo "# GoGauge HarmonyOS 商店截图清单（screenshot-manifest）"
    echo
    echo "> 自动生成于 $(date '+%Y-%m-%d %H:%M:%S %Z')，由 \`scripts/emu/capture-store-shots.sh\` 扫描输出目录生成。"
    echo "> 本清单仅收录正式素材（顶层 <page>-<theme>.jpeg）；\`_degraded/\` 与 \`smoke-*\` 为验证/退化资产，**不得用于上架**。"
    echo
    echo "| 文件（相对 docs/store-assets/screenshots/） | 形态 | 页面 | 主题 | 分辨率 | 大小 |"
    echo "| --- | --- | --- | --- | --- | --- |"
    printf "%b" "$rows"
    echo
    echo "AppGallery 上传规格（由 release-materials 的 prep-screenshots.py 转换）："
    echo "- 手机：1080x1920（竖向 9:16）；PC/2in1：1920x1080（16:9）；平板：1920x1280（横向 3:2）。"
    echo "- 本 manifest 记录的是模拟器原始截图（手机 1320x2856 / PC 3120x2080）；"
    echo "  转换后上传文件见 \`docs/release/screenshots-upload/\`。"
    echo "- 平板：本机无 Tablet 镜像，仅提供 2in1 窗口 4:3 退化验证图（在 tablet/_degraded/），不得作为平板商店图。"
  } >"$manifest"
  log "素材清单已写入: $manifest"
}

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
print_summary() {
  echo
  echo "================ 截图流水线汇总 ================"
  if [ -f "$SUMMARY_FILE" ] && [ -s "$SUMMARY_FILE" ]; then
    printf '%-8s %-6s %-9s %-10s %s\n' "DEVICE" "THEME" "PAGE" "STATUS" "PATH"
    while IFS=$'\t' read -r d th p st path; do
      printf '%-8s %-6s %-9s %-10s %s\n' "$d" "$th" "$p" "$st" "$path"
    done <"$SUMMARY_FILE"
    local ok degraded
    ok="$(awk -F'\t' '$4=="OK"' "$SUMMARY_FILE" | wc -l | tr -d ' ')"
    degraded="$(awk -F'\t' '$4=="DEGRADED"' "$SUMMARY_FILE" | wc -l | tr -d ' ')"
    echo
    echo "正式素材: $ok 张；DEGRADED: $degraded 张"
    if [ "$degraded" != "0" ]; then
      warn "存在 DEGRADED 资产：page 参数未生效（旧 HAP）或形态为平板退化，勿直接用于商店"
    fi
    if [ "$ok" = "0" ]; then
      warn "没有产出正式素材：请确认已安装支持 demo/page 参数的新 HAP 后重跑"
    fi
  else
    echo "(dry-run 或未执行任何截图)"
  fi
  if ls "$WORK_ROOT"/SETTINGS_DEBUG_UI_LEAK-*.txt >/dev/null 2>&1; then
    warn "注意：设置页截图存在调试 UI 泄漏（见 $WORK_ROOT/SETTINGS_DEBUG_UI_LEAK-*.txt），不可直接上架"
  fi
  echo "工作目录（原始/中间文件）: $WORK_ROOT"
  echo "==============================================="
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
  parse_args "$@"
  mkdir -p "$WORK_ROOT"
  : >"$SUMMARY_FILE"
  log "输出目录: $OUT"
  log "设备: $DEVICES"
  log "页面: $PAGES"
  log "demo 参数模式: ${DEMO_MODE}（lang=${LANG_SEL}）"
  log "工作目录: $WORK_ROOT"

  if [ "$DO_BUILD" = "1" ]; then
    if [ "$DRY_RUN" = "1" ]; then
      log "[dry-run] emu.sh build"
    else
      log "构建 HAP ..."
      "$EMU" build
    fi
  fi

  local dev
  for dev in $DEVICES; do
    capture_device "$dev"
  done

  if [ "$RESTORE_PHONE" = "1" ] && [ "$DRY_RUN" = "0" ]; then
    log "切回手机模拟器 ..."
    "$EMU" start-phone
  fi

  write_manifest
  print_summary
  local ok
  ok="$(awk -F'\t' '$4=="OK"' "$SUMMARY_FILE" 2>/dev/null | wc -l | tr -d ' ' || echo 0)"
  [ "${ok:-0}" -gt 0 ] && exit 0 || exit 2
}

main "$@"
