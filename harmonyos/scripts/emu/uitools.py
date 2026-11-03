#!/usr/bin/env python3
"""GoGauge HarmonyOS — uitest dumpLayout JSON 解析小工具。

配合 emu.sh dump-ui / tap / drag 使用。系统 `uitest dumpLayout` 输出的
JSON 树结构不固定（不同版本字段/层级不同），这里用宽松遍历提取需要的信息。

用法（FILE 为 dumpLayout 导出的 json 文件）：
  uitools.py texts FILE                    列出所有非空 text/description
  uitools.py find FILE TEXT                列出包含 TEXT 的节点（区分大小写子串）
  uitools.py center FILE TEXT              输出第一个匹配节点的中心坐标 "x y"
  uitools.py exists FILE TEXT              找到退出码 0，否则 1
  uitools.py screen FILE                   输出屏幕 "宽 高"
  uitools.py window FILE                   输出应用窗口（ContainerModal）"x y w h"
  uitools.py maximized FILE                应用窗口是否已最大化（退出码）
  uitools.py titlebar-buttons FILE         标题栏右侧按钮 "x y maximize|minimize|close"
  uitools.py drag-plan FILE W H            拖窗口右下角到目标尺寸的 drag 坐标
  uitools.py shellplan FILE TEXT ACTION    找到 TEXT 并输出 "<action> x y"（调试用）

坐标均为设备像素（与 snapshot_display 截图同坐标系）。
"""
import json
import sys


# ---------------------------------------------------------------------------
# 宽松遍历
# ---------------------------------------------------------------------------
def walk(node):
    """深度优先遍历所有节点。"""
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("children", []) or []:
        yield from walk(child)


def attrs(node):
    a = node.get("attributes")
    return a if isinstance(a, dict) else {}


def node_text(node):
    a = attrs(node)
    return (a.get("text") or a.get("description") or "").strip()


def parse_bounds(b):
    """解析 "[x1,y1][x2,y2]" → (x1, y1, x2, y2)；失败返回 None。"""
    if not isinstance(b, str) or "][" not in b:
        return None
    try:
        left, right = b.split("][")
        x1, y1 = [int(v) for v in left.strip().strip("[]").split(",")]
        x2, y2 = [int(v) for v in right.strip().strip("[]").split(",")]
    except (ValueError, TypeError):
        return None
    if x2 < x1 or y2 < y1:
        return None
    return x1, y1, x2, y2


def node_bounds(node):
    return parse_bounds(attrs(node).get("bounds"))


def node_type(node):
    return (attrs(node).get("type") or "").strip()


def center(bounds):
    x1, y1, x2, y2 = bounds
    return (x1 + x2) // 2, (y1 + y2) // 2


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def screen_size(tree):
    """屏幕尺寸：根节点 bounds（dumpLayout 的第一个根即全屏）。"""
    roots = tree if isinstance(tree, list) else [tree]
    for root in roots:
        b = node_bounds(root)
        if b:
            return b[2] - b[0], b[3] - b[1]
    return None


def app_window(tree):
    """应用窗口：优先 ContainerModal（含标题栏的完整窗口），取面积最大者。"""
    candidates = []
    for n in walk(tree):
        if node_type(n) == "ContainerModal":
            b = node_bounds(n)
            if b:
                candidates.append(b)
    if candidates:
        return max(candidates, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    # 兜底：带 abilityName/bundleName 的根节点
    for n in walk(tree):
        a = attrs(n)
        if a.get("abilityName") or a.get("bundleName"):
            b = node_bounds(n)
            if b:
                return b
    return None


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------
def cmd_texts(tree):
    seen = set()
    for n in walk(tree):
        t = node_text(n)
        if t and t not in seen:
            seen.add(t)
            print(t)
    return 0


def find_matches(tree, needle):
    matches = []
    for n in walk(tree):
        t = node_text(n)
        if needle in t:
            b = node_bounds(n)
            if b:
                matches.append((t, b))
    return matches


def cmd_find(tree, needle):
    matches = find_matches(tree, needle)
    for t, b in matches:
        x, y = center(b)
        print(f"{x} {y} | {t[:80]} | {b}")
    return 0 if matches else 1


def cmd_center(tree, needle):
    matches = find_matches(tree, needle)
    if not matches:
        return 1
    x, y = center(matches[0][1])
    print(f"{x} {y}")
    return 0


def cmd_exists(tree, needle):
    return 0 if find_matches(tree, needle) else 1


def cmd_screen(tree):
    size = screen_size(tree)
    if not size:
        return 1
    print(f"{size[0]} {size[1]}")
    return 0


def cmd_window(tree):
    b = app_window(tree)
    if not b:
        return 1
    print(f"{b[0]} {b[1]} {b[2] - b[0]} {b[3] - b[1]}")
    return 0


def cmd_maximized(tree):
    b = app_window(tree)
    screen = screen_size(tree)
    if not b or not screen:
        return 1
    sw = screen[0]
    wx, _, ww, _ = b
    # 2in1 最大化时窗口占满屏宽，仅高度扣掉任务栏
    return 0 if wx <= 4 and ww >= sw - 8 else 1


def cmd_titlebar_buttons(tree):
    b = app_window(tree)
    if not b:
        return 1
    x1, y1, x2, y2 = b
    win_w = x2 - x1
    title_h = max(56, (y2 - y1) // 20)
    buttons = []
    for n in walk(tree):
        a = attrs(n)
        if a.get("clickable") != "true":
            continue
        nb = node_bounds(n)
        if not nb:
            continue
        nx1, ny1, nx2, ny2 = nb
        nw, nh = nx2 - nx1, ny2 - ny1
        if nh < 24 or nh > 96 or nw < 24 or nw > 160:
            continue
        # 在窗口标题栏内、且位于窗口右半部分
        if ny1 < y1 + 4 or ny2 > y1 + title_h + 40:
            continue
        if nx1 < x1 + win_w // 2:
            continue
        buttons.append(nb)
    buttons.sort(key=lambda nb: nb[0])
    if len(buttons) < 2:
        return 1
    names = ["maximize", "minimize", "close"]
    # 通常 3 个按钮（部分系统可能 2 个：minimize/close，此时第一个是 minimize）
    offset = 0 if len(buttons) >= 3 else 1
    for i, nb in enumerate(buttons):
        x, y = center(nb)
        name = names[offset + i] if offset + i < len(names) else f"button{i}"
        print(f"{x} {y} {name}")
    return 0


def cmd_drag_plan(tree, target_w, target_h):
    b = app_window(tree)
    if not b:
        return 1
    x1, y1, x2, y2 = b
    # 右下角内缩 4px，避免拖到窗口阴影；目标窗口左上角保持不变
    sx, sy = x2 - 4, y2 - 4
    ex, ey = x1 + target_w - 4, y1 + target_h - 4
    print(f"{sx} {sy} {ex} {ey} {abs(ex - sx) + abs(ey - sy)}")
    return 0


def main(argv):
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, path = argv[1], argv[2]
    tree = load(path)
    rest = argv[3:]
    if cmd == "texts":
        return cmd_texts(tree)
    if cmd == "find":
        return cmd_find(tree, rest[0])
    if cmd == "center":
        return cmd_center(tree, rest[0])
    if cmd == "exists":
        return cmd_exists(tree, rest[0])
    if cmd == "screen":
        return cmd_screen(tree)
    if cmd == "window":
        return cmd_window(tree)
    if cmd == "maximized":
        return cmd_maximized(tree)
    if cmd == "titlebar-buttons":
        return cmd_titlebar_buttons(tree)
    if cmd == "drag-plan":
        return cmd_drag_plan(tree, int(rest[0]), int(rest[1]))
    print(f"未知子命令: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
