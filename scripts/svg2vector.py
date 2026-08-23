#!/usr/bin/env python3
"""Convert desktop model icons (app/web/icons/*.svg) to Android VectorDrawable XMLs.

Usage: python3 scripts/svg2vector.py  (run from repo root)
Outputs: android/app/src/main/res/drawable/ic_model_<name>.xml

规则:
- path d 直接作为 android:pathData (SVG path 语法兼容)
- circle → 两段圆弧路径近似
- 线性渐变 (minimax/qwen) → aapt:attr 内嵌 gradient
- meta 的多段相似蓝色渐变在 16dp 下不可辨, 拍平为品牌蓝 #0082FB
- fill="currentColor"/缺省 → #FFFFFF, 渲染层用 Icon tint 动态着色
"""
import re
import sys
from pathlib import Path

SRC = Path("app/web/icons")
DST = Path("android/app/src/main/res/drawable")

META_FLAT = "#0082FB"

HEADER = (
    '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
    '    xmlns:aapt="http://schemas.android.com/aapt"\n'
    '    android:width="24dp"\n    android:height="24dp"\n'
    '    android:viewportWidth="24"\n    android:viewportHeight="24">\n'
)


def circle_to_path(cx, cy, r):
    return (
        f"M{cx - r},{cy} a{r},{r} 0 1,0 {2 * r},0 a{r},{r} 0 1,0 {-2 * r},0z"
    )


def parse_gradient(svg, gid):
    m = re.search(
        rf'<linearGradient[^>]*id="{gid}"[^>]*>(.*?)</linearGradient>', svg, re.S
    )
    if not m:
        return None
    body = m.group(0)
    attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', body.split(">", 1)[0]))
    items = []
    for s in re.finditer(r"<stop\b([^>]*?)(?:/>|>(.*?)</stop>)", body, re.S):
        sa = dict(re.findall(r'([\w-]+)="([^"]*)"', s.group(1)))
        off = float(sa.get("offset", "0").rstrip("%")) / 100
        col = sa.get("stop-color", "#000000")
        op = sa.get("stop-opacity", "1")
        try:
            a = round(float(op) * 255)
        except ValueError:
            a = 255
        alpha = f"{a:02X}"
        items.append((off, alpha + col.lstrip("#").upper()))
    return attrs, items


def grad_fill(gid, svg):
    g = parse_gradient(svg, gid)
    if not g:
        return f'android:fillColor="{META_FLAT}"'
    attrs, items = g

    def pct(v):
        return round(float(v.rstrip("%")) / 100 * 24, 4)

    start = f'{pct(attrs.get("x1", "0%"))},{pct(attrs.get("y1", "50%"))}'
    end = f'{pct(attrs.get("x2", "100%"))},{pct(attrs.get("y2", "50%"))}'
    lines = [
        "<aapt:attr name=\"android:fillColor\">",
        "  <gradient",
        "      android:type=\"linear\"",
        f"      android:startX=\"{start.split(',')[0]}\" android:startY=\"{start.split(',')[1]}\"",
        f"      android:endX=\"{end.split(',')[0]}\" android:endY=\"{end.split(',')[1]}\">",
    ]
    for off, col in items:
        lines.append(f"    <item android:offset=\"{off}\" android:color=\"#{col}\"/>")
    lines += ["  </gradient>", "</aapt:attr>"]
    return "\n".join(lines)


def convert(name: str) -> str:
    svg = (SRC / f"{name}.svg").read_text()
    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    vw, vh = vb.group(1), vb.group(2)
    root_fill_m = re.search(r'<svg[^>]*\bfill="(#[0-9A-Fa-f]{6}|currentColor)"', svg)
    root_fill = root_fill_m.group(1) if root_fill_m else None
    evenodd = 'fill-rule="evenodd"' in svg

    parts = []
    # circles first (preserve z-order roughly: hy draws circle then paths; regex order suffices)
    for tag in re.finditer(r"<circle[^>]*/?>", svg):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', tag.group(0)))
        cx, cy, r = a["cx"], a["cy"], a["r"]
        fill = a.get("fill", "#000")
        d = circle_to_path(float(cx), float(cy), float(r))
        parts.append(f'  <path\n      android:pathData="{d}"\n      android:fillColor="{fill}"/>')

    for m in re.finditer(r"<path\b[^>]*>", svg):
        tag = m.group(0)
        dm = re.search(r'\bd="([^"]+)"', tag)
        if not dm:
            continue
        d = dm.group(1).replace("\n", " ")
        fm = re.search(r'\bfill="([^"]+)"', tag)
        fill = fm.group(1) if fm else None
        fr = 'evenOdd' if ('fill-rule="evenodd"' in tag or evenodd) else None
        if fill is None or fill == "currentColor":
            if root_fill == "currentColor":
                fill = "#FFFFFF"
            elif root_fill:
                fill = root_fill
            else:
                fill = "#000000"
        if fill.startswith("url("):
            gid = fill[5:-1]
            if name == "meta":
                fa = f'android:fillColor="{META_FLAT}"'
            else:
                fa = grad_fill(gid, svg)
            ft = f'\n      android:fillType="{fr}"' if fr else ""
            # 渐变填充以 aapt:attr 子元素表达, path 不能自闭合
            parts.append(
                f'  <path\n      android:pathData="{d}"{ft}>\n      {fa}\n  </path>'
            )
        else:
            fa = f'android:fillColor="{fill.upper()}"'
            ft = f'\n      android:fillType="{fr}"' if fr else ""
            parts.append(f'  <path\n      android:pathData="{d}"\n      {fa}{ft}/>')
    return HEADER + "\n".join(parts) + "\n</vector>\n"


def main():
    names = sys.argv[1:] or [
        "deepseek", "glm", "gpt", "gpt-color", "grok", "grok-color", "hy",
        "kimi", "meta", "mimo", "mimo-color", "minimax", "qwen",
    ]
    DST.mkdir(parents=True, exist_ok=True)
    for n in names:
        xml = convert(n)
        out = DST / f"ic_model_{n.replace('-', '_')}.xml"
        out.write_text(xml)
        print(f"wrote {out} ({len(xml)} bytes)")


if __name__ == "__main__":
    main()
