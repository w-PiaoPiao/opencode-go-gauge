#!/usr/bin/env python3
"""生成 GoGauge 鸿蒙应用图标 (entry/src/main/resources/base/media/icon.png)。

画法: 深蓝底色圆角方块 + 白色 270° 圆弧仪表盘 + 指针, 简单纯 Python+PIL 实现,
避免引入字体/素材依赖。上架 AppGallery 时再替换为正式分层图标。
"""
import math
import os
from PIL import Image, ImageDraw

SIZE = 512
OUT = os.path.join(os.path.dirname(__file__), "..", "entry", "src", "main", "resources", "base", "media", "icon.png")


def main() -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 圆角方形背景
    bg = (31, 41, 55, 255)       # #1F2937 深蓝灰
    radius = 110
    d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=radius, fill=bg)

    cx, cy, r = SIZE // 2, SIZE // 2, 170
    thick = 34
    white = (255, 255, 255, 255)
    gap_color = bg

    # 270° 圆弧仪表盘 (自 -225° 到 45°, 即 9 点钟 → 3 点钟, 上方留缺口)
    start_deg, end_deg = -225, 45
    steps = 200
    arc_px = []
    for i in range(steps + 1):
        a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
        arc_px.append((cx + (r - thick / 2) * math.cos(a), cy + (r - thick / 2) * math.sin(a)))
    # 首尾各画一小段缺口背景色, 形成断开效果
    for i, p in enumerate(arc_px):
        w = max(2, int(thick * 0.55))
        d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=white)
    # 缺口: 起始端
    a0 = math.radians(start_deg)
    g = (cx + (r - thick / 2) * math.cos(a0), cy + (r - thick / 2) * math.sin(a0))
    d.ellipse([g[0] - thick / 2, g[1] - thick / 2, g[0] + thick / 2, g[1] + thick / 2], fill=gap_color)

    # 指针 (指向约 60% 位置)
    pa = math.radians(start_deg + (end_deg - start_deg) * 0.62)
    tip = (cx + (r - thick - 24) * math.cos(pa), cy + (r - thick - 24) * math.sin(pa))
    d.line([(cx, cy), tip], fill=white, width=16)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=white)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()