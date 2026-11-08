#!/usr/bin/env python3
"""GoGauge 品牌图标生成器（单一几何来源，可重复执行）。

本文件同时是 scripts/build_icon.py（Windows ICO）与 scripts/build_macos_icon.py
（macOS PNG/ICNS）的实现来源：两脚本 import 这里的 render_logo/write_* 函数；
Android / HarmonyOS 的启动图标资源也由本文件统一导出，避免多端设计分叉。

设计（v2.2.2d 调整）：
- 品牌几何不变：蓝色外环 270° 在左上角留 90° 断口，青色内环缺口朝左上，
  断口处的字母作为「平台标记」。字母按平台取首字母：
    Android = A, macOS = M, Windows = W, HarmonyOS = H
- 两种配色风格（设置「图标风格」切换，默认 blue）：
    blue       深蓝渐变底 + 蓝/青双环（桌面/HarmonyOS 原有品牌色）
    terracotta 陶土橙底 + 米白/浅陶土双环（对齐 Android 暖纸面主题）
- 透明底 Logo 用于应用内/发行素材，不透明满幅图标用于系统启动器/停靠栏。

输出：
- assets/GoGauge.png                512 透明底 blue M（macOS 窗口/菜单栏图标）
- assets/GoGauge.icns               macOS .app 图标（blue M；Big Sur+ 图标网格：
                                    1024 画布 + 824 连续曲率(squircle)圆角 tile）
- assets/GoGauge.ico                Windows exe 图标（blue W，多尺寸）
- assets/appicon-{blue,warm}-mac.png 1024 同上网格的满幅图标（macOS Dock 运行时切风格用）
                                    ⚠️ Dock 运行时图标不会被系统自动遮罩圆角，必须自带 squircle
                                    + 安全边距，否则会显示成一个硬边正方形（v2.2.2e 修复）
- assets/appicon-warm-win.ico       Windows 任务栏运行时切风格用（blue 用 GoGauge.ico）
- assets/GoGauge-harmony.png        1024 透明底 blue H（HarmonyOS 发行素材源）
- app/web/logo-{blue,warm}-{mac,win}.svg  桌面应用内左上角/登录页 Logo
- assets/GoGauge-logo.svg          平台无关品牌标记（无字母，README/文档用）
- android/app/src/main/res/**        两套自适应启动图标（blue A / warm A）
- harmonyos/**/media/*              HarmonyOS 分层图标（blue H）+ 应用内暖色版 icon_warm.png

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
ANDROID_RES = os.path.join(REPO, "android", "app", "src", "main", "res")
WEB = os.path.join(REPO, "app", "web")

BLUE = (24, 144, 255, 255)      # #1890FF
CYAN = (6, 182, 212, 255)       # #06B6D4
# 暖色（陶土）风格：与 Android 暖纸面主题同一组颜色
WARM_OUTER = (217, 119, 87, 255)    # #D97757 陶土橙
WARM_INNER = (237, 165, 139, 255)   # #EDA58B
WARM_LETTER = (192, 86, 52, 255)    # #C05634
CREAM = (250, 249, 245, 255)        # #FAF9F5
PEACH = (242, 201, 184, 255)        # #F2C9B8
NAVY_TOP = (9, 16, 29)              # #09101D
NAVY_BOTTOM = (24, 39, 61)          # #18273D
TERRA_TOP = (224, 138, 108)         # #E08A6C
TERRA_BOTTOM = (198, 95, 61)        # #C65F3D

# 平台标记字母（平台首字母；HarmonyOS 保持 H）
PLATFORM_LETTERS = {"macos": "M", "windows": "W", "android": "A", "harmonyos": "H"}

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

# macOS Big Sur+ 应用图标网格: 1024 画布内居中是 824×824 的圆角 tile（四周 100px 安全边距），
# 圆角为「连续曲率」squircle（超椭圆 |x|^n+|y|^n=1, n=5 的近似；45° 处切点与 Apple
# 约 22% 圆角半径吻合）。应用图标必须自带这层形状 —— 运行时 setApplicationIconImage
# 设置的 Dock 图标不会像 .app 包图标那样被系统再遮罩，直接给满幅方图就是硬边正方形。
MACOS_CANVAS = 1024
MACOS_TILE_RATIO = 824 / 1024       # 图标内容 tile 占画布比例
MACOS_LOGO_RATIO = 0.74            # 品牌环外径占 tile 的比例（视觉与原生 mac 图标接近）
SQUIRCLE_EXPONENT = 5.0

# 断口字母笔画（归一化到 H 的包围盒：u 0..1 从左到右，v 0..1 从上到下）。
# H 保持原有的三段矩形几何（HarmonyOS / 既有发行素材逐像素不变），其余字母用
# 与 H 同宽度的笔画绘制（圆头圆角，视觉上更贴合圆弧仪表盘）。
LETTER_STROKES: dict[str, list[list[tuple[float, float]]]] = {
    "M": [[(0, 1), (0, 0), (0.5, 0.52), (1, 0), (1, 1)]],
    "W": [[(0, 0), (0, 1), (0.5, 0.48), (1, 1), (1, 0)]],
    "A": [[(0, 1), (0.5, 0), (1, 1)], [(0.19, 0.63), (0.81, 0.63)]],
}

# 各风格配色：(外环, 内环, 字母, 不透明底渐变)
STYLE_COLORS = {
    "blue": (BLUE, CYAN, BLUE, (NAVY_TOP, NAVY_BOTTOM)),
    "terracotta": (WARM_OUTER, WARM_INNER, WARM_LETTER, (TERRA_TOP, TERRA_BOTTOM)),
}
# 不透明（系统图标、暖底）专用：暖色底上用米白/浅陶土，保证对比度
OPAQUE_WARM = (CREAM, PEACH, CREAM)


def _arc_ring(draw: ImageDraw.ImageDraw, scale: int, r_in: float, r_out: float,
              spans: list[tuple[float, float]], color: tuple[int, int, int, int]) -> None:
    for start, end in spans:
        draw.arc(
            [(C - r_out) * scale, (C - r_out) * scale,
             (C + r_out) * scale, (C + r_out) * scale],
            start=start, end=end, fill=color, width=int((r_out - r_in) * scale),
        )


def _stroke(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], width: float,
            color: tuple[int, int, int, int]) -> None:
    """画一条圆头圆角折线（矩形段 + 顶点圆补角；与 H 的笔画宽度一致）。"""
    radius = width / 2.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            continue
        nx, ny = -dy / length * radius, dx / length * radius
        draw.polygon(
            [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)],
            fill=color,
        )
    for x, y in points:
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)


def _draw_letter(draw: ImageDraw.ImageDraw, scale: int, letter: str,
                 color: tuple[int, int, int, int]) -> None:
    letter = (letter or "").strip().upper() or "H"
    w = 66 * H_SCALE * scale
    h = 84 * H_SCALE * scale
    bar = 11 * H_SCALE * scale
    cross = 13 * H_SCALE * scale
    cx, cy = H_CENTER[0] * scale, H_CENTER[1] * scale
    ox, oy = cx - w / 2, cy - h / 2
    if letter == "H":  # 与旧版逐像素一致（HarmonyOS / 已发布素材不变）
        draw.rectangle([ox, oy, ox + bar, oy + h], fill=color)
        draw.rectangle([ox + w - bar, oy, ox + w, oy + h], fill=color)
        draw.rectangle([ox, oy + (h - cross) / 2, ox + w, oy + (h + cross) / 2], fill=color)
        return
    strokes = LETTER_STROKES.get(letter)
    if strokes is None:  # 未知字母: 用 H 兜底, 不让生成器崩掉
        _draw_letter(draw, scale, "H", color)
        return
    for stroke in strokes:
        _stroke(draw, [(ox + u * w, oy + v * h) for u, v in stroke], bar, color)


def render_logo(size: int = 512, transparent: bool = True, letter: str = "H",
                style: str = "blue") -> Image.Image:
    """渲染品牌 Logo，返回 size×size。

    Args:
        transparent: True=透明底（应用内/发行素材）; False=满幅不透明底（系统图标）。
        letter: 断口处平台字母（A/M/W/H）。
        style: ``blue`` 或 ``terracotta`` 配色。
    """
    if style not in STYLE_COLORS:
        style = "blue"
    outer, inner, letter_color, (top, bottom) = STYLE_COLORS[style]
    if not transparent and style == "terracotta":
        outer, inner, letter_color = OPAQUE_WARM
    scale = SUPERSAMPLE
    big = Image.new("RGBA", (BASE * scale, BASE * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    _arc_ring(draw, scale, *RING, RING_SPANS, outer)
    _arc_ring(draw, scale, *CYAN_RING, CYAN_SPANS, inner)
    _draw_letter(draw, scale, letter, letter_color)

    logo = big.resize((size, size), Image.LANCZOS)
    if transparent:
        return logo
    bg = gradient_background(size, top, bottom)
    out = bg.copy()
    out.paste(logo, (0, 0), logo)
    return out


def gradient_background(size: int, top: tuple[int, int, int],
                        bottom: tuple[int, int, int]) -> Image.Image:
    """应用图标底色：竖直渐变（blue=深蓝，terracotta=陶土橙）。"""
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        d.line([(0, y), (size, y)],
               fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img.convert("RGBA")


def navy_background(size: int) -> Image.Image:
    """兼容旧调用：深蓝渐变底。"""
    return gradient_background(size, NAVY_TOP, NAVY_BOTTOM)


def fit_content(logo: Image.Image, target: int) -> Image.Image:
    """裁到内容包围盒后等比缩放到 target，居中放到 1024 透明画布（包内 foreground 规范，内容占 58%）。"""
    bbox = logo.split()[-1].getbbox()
    content = logo.crop(bbox) if bbox else logo
    scaled = content.resize((target, target), Image.LANCZOS)
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    canvas.alpha_composite(scaled, ((1024 - target) // 2, (1024 - target) // 2))
    return canvas


def write_windows_ico(path: str) -> None:
    """多尺寸 Windows .ico（blue W，深蓝底满幅）。"""
    render_logo(1024, transparent=False, letter=PLATFORM_LETTERS["windows"], style="blue").save(
        path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def write_warm_windows_ico(path: str) -> None:
    """多尺寸 Windows .ico（terracotta W）：任务栏运行时切风格用。"""
    render_logo(1024, transparent=False, letter=PLATFORM_LETTERS["windows"], style="terracotta").save(
        path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def squircle_mask(size: int, exponent: float = SQUIRCLE_EXPONENT,
                  supersample: int = SUPERSAMPLE) -> Image.Image:
    """连续曲率圆角（超椭圆 squircle）alpha 遮罩，返回 size×size 的 L 图."""
    big = size * supersample
    half = big / 2
    steps = 1440
    points = []
    for i in range(steps):
        theta = 2 * math.pi * i / steps
        ct, st = math.cos(theta), math.sin(theta)
        x = math.copysign(abs(ct) ** (2.0 / exponent), ct) * half
        y = math.copysign(abs(st) ** (2.0 / exponent), st) * half
        points.append((half + x, half + y))
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def macos_icon(size: int = MACOS_CANVAS, letter: str = "M",
               style: str = "blue") -> Image.Image:
    """macOS 应用图标：安全边距 + 连续曲率(tile) 遮罩 + 品牌标记（透明画布）.

    系统（Dock 运行时 setApplicationIconImage / Finder 里的 .app 图标）都按这张
    1024 网格图显示，因此圆角与边距必须烘焙进图片本身。
    """
    tile = int(round(size * MACOS_TILE_RATIO))
    # 品牌环外径原本占正方形画布 342/512；缩放到占 tile 的 MACOS_LOGO_RATIO
    art_size = int(round(tile * MACOS_LOGO_RATIO / (342.0 / BASE)))
    art = render_logo(art_size, transparent=False, letter=letter, style=style)
    tile_img = Image.new("RGBA", (tile, tile), (0, 0, 0, 0))
    tile_img.alpha_composite(art, ((tile - art.width) // 2, (tile - art.height) // 2))
    alpha = tile_img.getchannel("A")
    mask = squircle_mask(tile)
    # ImageChops 在函数内导入: 主输出之外的少量调用点不需要 PIL.ImageChops 常驻
    from PIL import ImageChops

    tile_img.putalpha(ImageChops.multiply(alpha, mask))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = (size - tile) // 2
    canvas.alpha_composite(tile_img, (offset, offset))
    return canvas


def write_macos_icns(path: str) -> None:
    """macOS .icns（blue M，Big Sur+ 图标网格；iconset → iconutil）。"""
    _write_icns(path, letter=PLATFORM_LETTERS["macos"], style="blue")


def _write_icns(path: str, letter: str, style: str) -> None:
    icon1024 = macos_icon(MACOS_CANVAS, letter=letter, style=style)
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "GoGauge.iconset")
        os.makedirs(iconset)
        for px, name in [(16, "icon_16x16"), (32, "icon_16x16@2x"), (32, "icon_32x32"),
                         (64, "icon_32x32@2x"), (128, "icon_128x128"), (256, "icon_128x128@2x"),
                         (256, "icon_256x256"), (512, "icon_256x256@2x"), (512, "icon_512x512"),
                         (1024, "icon_512x512@2x")]:
            icon1024.resize((px, px), Image.LANCZOS).save(os.path.join(iconset, f"{name}.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", path], check=True)


# ---------------------------------------------------------------------------
# 桌面 Web 应用内 Logo（SVG）
# ---------------------------------------------------------------------------

_SVG_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n'
             '  <!-- GoGauge 品牌标记（与 assets/generate_logo.py 同一几何）：\n'
             '       外环左上留 90° 断口，断口处字母为该平台标记（macOS=M / Windows=W）。 -->\n')
_SVG_RINGS = (
    '  <g fill="none">\n'
    '    <circle cx="256" cy="256" r="138.5" stroke="{outer}" stroke-width="65"\n'
    '            stroke-dasharray="652.7 870.2" transform="rotate(-90 256 256)"/>\n'
    '    <circle cx="256" cy="256" r="70" stroke="{inner}" stroke-width="52"\n'
    '            stroke-dasharray="309.1 439.8" transform="rotate(299 256 256)"/>\n'
    '  </g>\n'
)


def _svg_letter(letter: str, color: str) -> str:
    """断口字母 → SVG；H 沿用三段矩形，其他字母用圆头笔画 path；空串 = 不画字母。"""
    if not letter:
        return ""
    w, h, bar = 66 * H_SCALE, 84 * H_SCALE, 11 * H_SCALE
    cross = 13 * H_SCALE
    ox, oy = H_CENTER[0] - w / 2, H_CENTER[1] - h / 2
    if letter == "H":
        return (f'  <g fill="{color}">\n'
                f'    <rect x="{ox:.2f}" y="{oy:.2f}" width="{bar:.2f}" height="{h:.2f}"/>\n'
                f'    <rect x="{ox + w - bar:.2f}" y="{oy:.2f}" width="{bar:.2f}" height="{h:.2f}"/>\n'
                f'    <rect x="{ox:.2f}" y="{oy + (h - cross) / 2:.2f}" width="{w:.2f}" '
                f'height="{cross:.2f}"/>\n'
                f'  </g>\n')
    strokes = LETTER_STROKES.get(letter) or LETTER_STROKES["M"]
    paths = []
    for stroke in strokes:
        pts = [(ox + u * w, oy + v * h) for u, v in stroke]
        d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        paths.append(f'    <path d="{d}" fill="none" stroke="{color}" '
                     f'stroke-width="{bar:.2f}" stroke-linecap="round" stroke-linejoin="round"/>\n')
    return f"  <g>\n{''.join(paths)}  </g>\n"


def logo_svg(letter: str, style: str) -> str:
    """透明底品牌 Logo SVG（桌面应用内使用）。"""
    outer, inner, letter_color, _ = STYLE_COLORS.get(style, STYLE_COLORS["blue"])
    body = _SVG_RINGS.format(outer=_hex(outer), inner=_hex(inner))
    return _SVG_HEAD + body + _svg_letter(letter, _hex(letter_color)) + "</svg>\n"


def _hex(color: tuple[int, int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color[:3])


def write_web_logos() -> None:
    """桌面 Web 应用内 Logo：两种风格 × Mac/Win 两个平台字母。"""
    for style in ("blue", "terracotta"):
        for platform, tag in (("macos", "mac"), ("windows", "win")):
            path = os.path.join(WEB, f"logo-{style}-{tag}.svg")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(logo_svg(PLATFORM_LETTERS[platform], style))


# ---------------------------------------------------------------------------
# Android 自适应启动图标（VectorDrawable）
# ---------------------------------------------------------------------------

# 自适应图标 108dp 视口；内容直径按安全区取 62dp（原图标外径 62dp，< 66dp 安全区）
_AND_VIEWPORT = 108.0
_AND_CONTENT = 62.0
_AND_SCALE = _AND_CONTENT / 342.0  # 342 = 外环外径（512 基准）


def _and_point(radius: float, angle_deg: float) -> tuple[float, float]:
    """512 基准极坐标（屏幕角度，0=右、90=下）→ Android 108dp 坐标。"""
    rad = math.radians(angle_deg)
    x = C + radius * math.cos(rad)
    y = C + radius * math.sin(rad)
    return _AND_VIEWPORT / 2 + (x - C) * _AND_SCALE, _AND_VIEWPORT / 2 + (y - C) * _AND_SCALE


def _and_arc_path(radius: float, start: float, end: float) -> str:
    x1, y1 = _and_point(radius, start)
    x2, y2 = _and_point(radius, end)
    large = 1 if (end - start) % 360 > 180 else 0
    r = radius * _AND_SCALE
    return f"M{x1:.2f},{y1:.2f} A{r:.2f},{r:.2f} 0 {large},1 {x2:.2f},{y2:.2f}"


def _and_letter_paths(letter: str) -> list[str]:
    """字母 → Android pathData 列表（H 用矩形拼，其他用圆头笔画）。"""
    w = 66 * H_SCALE
    h = 84 * H_SCALE
    bar = 11 * H_SCALE
    cross = 13 * H_SCALE
    ox, oy = H_CENTER[0] - w / 2, H_CENTER[1] - h / 2

    def pt(x: float, y: float) -> tuple[float, float]:
        return (_AND_VIEWPORT / 2 + (x - C) * _AND_SCALE,
                _AND_VIEWPORT / 2 + (y - C) * _AND_SCALE)

    if letter == "H":
        paths = []
        for x, y, pw, ph in ((ox, oy, bar, h), (ox + w - bar, oy, bar, h),
                             (ox, oy + (h - cross) / 2, w, cross)):
            x1, y1 = pt(x, y)
            x2, y2 = pt(x + pw, y + ph)
            paths.append(f"M{x1:.2f},{y1:.2f} h{(x2 - x1):.2f} v{(y2 - y1):.2f} h{-(x2 - x1):.2f}z")
        return paths
    out = []
    for stroke in (LETTER_STROKES.get(letter) or LETTER_STROKES["M"]):
        pts = [pt(ox + u * w, oy + v * h) for u, v in stroke]
        d = f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"
        d += "".join(f" L{x:.2f},{y:.2f}" for x, y in pts[1:])
        out.append((d, bar * _AND_SCALE))  # type: ignore[arg-type]
    return out


def _and_foreground(style: str) -> str:
    outer, inner, letter_color, _ = STYLE_COLORS[style]
    if style == "terracotta":
        outer, inner, letter_color = OPAQUE_WARM
    paths = []
    for radius, start, end, color, width in (
        (float(sum(RING) / 2), RING_SPANS[0][0], RING_SPANS[0][1], outer, float(RING[1] - RING[0])),
        (float(sum(RING) / 2), RING_SPANS[1][0], RING_SPANS[1][1], outer, float(RING[1] - RING[0])),
        (float(sum(CYAN_RING) / 2), CYAN_SPANS[0][0], CYAN_SPANS[0][1], inner, float(CYAN_RING[1] - CYAN_RING[0])),
        (float(sum(CYAN_RING) / 2), CYAN_SPANS[1][0], CYAN_SPANS[1][1], inner, float(CYAN_RING[1] - CYAN_RING[0])),
    ):
        paths.append(
            f'    <path android:pathData="{_and_arc_path(radius, start, end)}"\n'
            f'        android:strokeColor="{_hex(color)}"\n'
            f'        android:strokeWidth="{width * _AND_SCALE:.2f}"\n'
            f'        android:fillColor="#00000000" />'
        )
    for item in _and_letter_paths(PLATFORM_LETTERS["android"]):
        if isinstance(item, tuple):
            d, sw = item
            paths.append(
                f'    <path android:pathData="{d}"\n'
                f'        android:strokeColor="{_hex(letter_color)}"\n'
                f'        android:strokeWidth="{sw:.2f}"\n'
                f'        android:strokeLineCap="round" android:strokeLineJoin="round"\n'
                f'        android:fillColor="#00000000" />'
            )
        else:
            paths.append(f'    <path android:pathData="{item}"\n'
                         f'        android:fillColor="{_hex(letter_color)}" />')
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        f'    android:width="{_AND_VIEWPORT:.0f}dp" android:height="{_AND_VIEWPORT:.0f}dp"\n'
        f'    android:viewportWidth="{_AND_VIEWPORT:.0f}" android:viewportHeight="{_AND_VIEWPORT:.0f}">\n'
        "    <!-- GoGauge 品牌标记：外环左上断口 + 平台字母 A（由 assets/generate_logo.py 生成） -->\n"
        + "\n".join(paths) + "\n</vector>\n"
    )


def _and_background(style: str) -> str:
    top, bottom = STYLE_COLORS[style][3]
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    xmlns:aapt="http://schemas.android.com/aapt"\n'
        f'    android:width="{_AND_VIEWPORT:.0f}dp" android:height="{_AND_VIEWPORT:.0f}dp"\n'
        f'    android:viewportWidth="{_AND_VIEWPORT:.0f}" android:viewportHeight="{_AND_VIEWPORT:.0f}">\n'
        '    <path android:pathData="M0,0h108v108h-108z">\n'
        '        <aapt:attr name="android:fillColor">\n'
        '            <gradient android:type="linear"\n'
        '                android:startX="0" android:startY="0"\n'
        '                android:endX="0" android:endY="108"\n'
        f'                android:startColor="#FF{top[0]:02X}{top[1]:02X}{top[2]:02X}"\n'
        f'                android:endColor="#FF{bottom[0]:02X}{bottom[1]:02X}{bottom[2]:02X}" />\n'
        '        </aapt:attr>\n'
        '    </path>\n'
        '</vector>\n'
    )


def write_android_icons() -> None:
    """Android 两套自适应启动图标（blue A / terracotta A）。"""
    drawable = os.path.join(ANDROID_RES, "drawable")
    mipmap = os.path.join(ANDROID_RES, "mipmap-anydpi-v26")
    os.makedirs(drawable, exist_ok=True)
    os.makedirs(mipmap, exist_ok=True)
    for style in ("blue", "terracotta"):
        with open(os.path.join(drawable, f"ic_launcher_background_{style}.xml"), "w",
                  encoding="utf-8") as fh:
            fh.write(_and_background(style))
        with open(os.path.join(drawable, f"ic_launcher_foreground_{style}.xml"), "w",
                  encoding="utf-8") as fh:
            fh.write(_and_foreground(style))
        with open(os.path.join(mipmap, f"ic_launcher_{style}.xml"), "w", encoding="utf-8") as fh:
            fh.write(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                f'    <background android:drawable="@drawable/ic_launcher_background_{style}" />\n'
                f'    <foreground android:drawable="@drawable/ic_launcher_foreground_{style}" />\n'
                f'    <monochrome android:drawable="@drawable/ic_launcher_foreground_{style}" />\n'
                '</adaptive-icon>\n'
            )


# ---------------------------------------------------------------------------
# HarmonyOS 资源（blue H 分层图标 + 应用内暖色版）
# ---------------------------------------------------------------------------


def write_harmony_assets() -> None:
    letter = PLATFORM_LETTERS["harmonyos"]
    logo512 = render_logo(512, letter=letter, style="blue")
    # 发行素材/Promo 用高分辨率透明底源图（Promo 取内容包围盒后缩放）
    render_logo(1024, letter=letter, style="blue").save(
        os.path.join(ASSETS, "GoGauge-harmony.png"), optimize=True)

    # 分层图标：foreground（内容 58%，透明）+ background（深蓝渐变）+ app_icon（合成）
    fg = fit_content(logo512, 592)
    bg = navy_background(1024)
    fg.save(os.path.join(HARM, "AppScope/resources/base/media/foreground.png"), optimize=True)
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
    # 设置「图标风格」切暖色时，应用内 Logo 用暖色满幅版（启动器图标无法运行时切换）
    warm = render_logo(512, transparent=False, letter=letter, style="terracotta")
    warm.save(os.path.join(entry_media, "icon_warm.png"), optimize=True)


def main() -> None:
    logo512 = render_logo(512, letter=PLATFORM_LETTERS["macos"], style="blue")
    logo512.save(os.path.join(ASSETS, "GoGauge.png"), optimize=True)

    write_windows_ico(os.path.join(ASSETS, "GoGauge.ico"))
    write_warm_windows_ico(os.path.join(ASSETS, "appicon-warm-win.ico"))
    write_macos_icns(os.path.join(ASSETS, "GoGauge.icns"))

    # macOS Dock 运行时切风格用（已烘焙安全边距 + 连续曲率圆角，含平台字母 M）
    macos_icon(MACOS_CANVAS, letter=PLATFORM_LETTERS["macos"], style="blue").save(
        os.path.join(ASSETS, "appicon-blue-mac.png"), optimize=True)
    macos_icon(MACOS_CANVAS, letter=PLATFORM_LETTERS["macos"], style="terracotta").save(
        os.path.join(ASSETS, "appicon-warm-mac.png"), optimize=True)

    # README/文档用：平台无关的无字母品牌标记（平台字母只出现在各平台图标里）
    with open(os.path.join(ASSETS, "GoGauge-logo.svg"), "w", encoding="utf-8") as fh:
        fh.write(logo_svg("", "blue"))

    write_web_logos()
    write_android_icons()
    write_harmony_assets()

    print("brand assets written")


if __name__ == "__main__":
    main()
