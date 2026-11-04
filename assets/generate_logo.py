#!/usr/bin/env python3
"""GoGauge 品牌图标生成器（单一几何来源，可重复执行）。

本文件同时是 scripts/build_icon.py（Windows ICO）与 scripts/build_macos_icon.py
（macOS PNG/ICNS）的实现来源：两脚本 import 这里的 render_logo/write_* 函数。

设计（v1.0.1 调整）：仪表盘圆弧的断口在左上角，字母 H 移入断口处作为「开口标记」。
- 外环：蓝色 #1890FF，内半径 106 / 外半径 171（512 基准），屏幕角度 270°→180°（顺时针，
  即顶部竖直切边 → 右侧 → 底部 → 左侧水平切边），左上角留出 90° 断口。
- 内环：青色 #06B6D4，半径 44–96，屏幕角度 299°→192°，缺口朝左上。
- H：蓝色 #1890FF，等比缩放 0.92，居中于断口处（沿 225° 方向、半径 121 处）。

输出：
- assets/GoGauge.png               512×512 透明底品牌 Logo
- assets/GoGauge.ico               Windows 多尺寸图标（深蓝底 + Logo 满幅）
- assets/GoGauge.icns              macOS 图标（深蓝底 + Logo 满幅）
- harmonyos/AppScope/resources/base/media/{foreground,background,app_icon}.png
- harmonyos/entry/src/main/resources/base/media/{foreground,background,app_icon,icon,startIcon}.png

用法：.venv/bin/python assets/generate_logo.py
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ASSETS = os.path.join(REPO, "assets")
HARM = os.path.join(REPO, "harmonyos")

BLUE = (24, 144, 255, 255)
CYAN = (6, 182, 212, 255)

# 512 基准几何
BASE = 512
C = BASE / 2
RING = (106, 171)          # 外环内/外半径
CYAN_RING = (44, 96)       # 内环内/外半径
RING_SPANS = [(270, 360), (0, 180)]     # 屏幕角度（0=右，90=下，180=左，270=上）
CYAN_SPANS = [(299, 360), (0, 192)]
H_SCALE = 0.92
H_CENTER = (C - 85.6, C - 85.6)          # 沿 225° 方向、半径 121（512 基准）
SUPERSAMPLE = 4


def _arc_ring(draw: ImageDraw.ImageDraw, scale: int, r_in: float, r_out: float,
              spans: list[tuple[float, float]], color: tuple[int, int, int, int]) -> None:
    for start, end in spans:
        draw.arc(
            [(C - r_out) * scale, (C - r_out) * scale,
             (C + r_out) * scale, (C + r_out) * scale],
            start=start, end=end, fill=color, width=int((r_out - r_in) * scale),
        )


def render_logo(size: int = 512, transparent: bool = True) -> Image.Image:
    """渲染品牌 Logo（透明底或深蓝底），返回 size×size。"""
    scale = SUPERSAMPLE
    big = Image.new("RGBA", (BASE * scale, BASE * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    _arc_ring(draw, scale, *RING, RING_SPANS, BLUE)
    _arc_ring(draw, scale, *CYAN_RING, CYAN_SPANS, CYAN)

    # H：两根竖杆 + 横杆（比例与原 Logo 一致：宽 66 / 高 84 / 杆宽 11 / 横杆 13 @512）
    w = 66 * H_SCALE * scale
    h = 84 * H_SCALE * scale
    bar = 11 * H_SCALE * scale
    cross = 13 * H_SCALE * scale
    ox = H_CENTER[0] * scale - w / 2
    oy = H_CENTER[1] * scale - h / 2
    draw.rectangle([ox, oy, ox + bar, oy + h], fill=BLUE)
    draw.rectangle([ox + w - bar, oy, ox + w, oy + h], fill=BLUE)
    draw.rectangle([ox, oy + (h - cross) / 2, ox + w, oy + (h + cross) / 2], fill=BLUE)

    logo = big.resize((size, size), Image.LANCZOS)
    if transparent:
        return logo
    bg = navy_background(size)
    out = bg.copy()
    out.paste(logo, (0, 0), logo)
    return out


def navy_background(size: int) -> Image.Image:
    """应用图标底色：与包内 background.png 一致的深蓝渐变（#09101D → #18273D）。"""
    top = (9, 16, 29)
    bottom = (24, 39, 61)
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        d.line([(0, y), (size, y)],
               fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img.convert("RGBA")


def fit_content(logo: Image.Image, target: int) -> Image.Image:
    """裁到内容包围盒后等比缩放到 target，居中放到 1024 透明画布（包内 foreground 规范，内容占 58%）。"""
    bbox = logo.split()[-1].getbbox()
    content = logo.crop(bbox) if bbox else logo
    scaled = content.resize((target, target), Image.LANCZOS)
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    canvas.alpha_composite(scaled, ((1024 - target) // 2, (1024 - target) // 2))
    return canvas


def write_windows_ico(path: str) -> None:
    """多尺寸 Windows .ico（深蓝底满幅）。"""
    render_logo(1024, transparent=False).save(
        path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def write_macos_icns(path: str) -> None:
    """macOS .icns（深蓝底满幅，iconset → iconutil）。"""
    icon1024 = render_logo(1024, transparent=False)
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "GoGauge.iconset")
        os.makedirs(iconset)
        for px, name in [(16, "icon_16x16"), (32, "icon_16x16@2x"), (32, "icon_32x32"),
                         (64, "icon_32x32@2x"), (128, "icon_128x128"), (256, "icon_128x128@2x"),
                         (256, "icon_256x256"), (512, "icon_256x256@2x"), (512, "icon_512x512"),
                         (1024, "icon_512x512@2x")]:
            icon1024.resize((px, px), Image.LANCZOS).save(os.path.join(iconset, f"{name}.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", path], check=True)


def main() -> None:
    logo512 = render_logo(512)
    logo512.save(os.path.join(ASSETS, "GoGauge.png"), optimize=True)

    write_windows_ico(os.path.join(ASSETS, "GoGauge.ico"))
    write_macos_icns(os.path.join(ASSETS, "GoGauge.icns"))

    # HarmonyOS 分层图标：foreground（内容 58%，透明）+ background（深蓝渐变）+ app_icon（合成）
    fg = fit_content(logo512, 592)
    fg.save(os.path.join(HARM, "AppScope/resources/base/media/foreground.png"), optimize=True)
    bg = navy_background(1024)
    bg.save(os.path.join(HARM, "AppScope/resources/base/media/background.png"), optimize=True)
    app_icon = bg.copy()
    app_icon.alpha_composite(fg)
    app_icon.save(os.path.join(HARM, "AppScope/resources/base/media/app_icon.png"), optimize=True)

    entry_media = os.path.join(HARM, "entry/src/main/resources/base/media")
    fg.save(os.path.join(entry_media, "foreground.png"), optimize=True)
    bg.save(os.path.join(entry_media, "background.png"), optimize=True)
    app_icon.save(os.path.join(entry_media, "app_icon.png"), optimize=True)
    app_icon.resize((512, 512), Image.LANCZOS).save(os.path.join(entry_media, "icon.png"), optimize=True)
    app_icon.resize((144, 144), Image.LANCZOS).save(os.path.join(entry_media, "startIcon.png"), optimize=True)

    print("brand assets written")


if __name__ == "__main__":
    main()
