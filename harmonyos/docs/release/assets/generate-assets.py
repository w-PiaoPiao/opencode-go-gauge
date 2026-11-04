#!/usr/bin/env python3
"""生成 GoGauge AppGallery 上架用图标与宣传图（纯 PIL，可重复执行）。

输入（只读，不修改）：
- 品牌标识：仓库根 ``assets/GoGauge.icns``（1024x1024，优先）或 ``assets/GoGauge.png``（512x512）
- 当前工程图标：``harmonyos/entry/src/main/resources/base/media/icon.png``（仅用于对比/参考）

输出（本目录）：
- ``icon-1024.png``        1024x1024 AppGallery 应用图标（不透明、满幅、无圆角）
- ``icon-512.png`` / ``icon-216.png``  备用尺寸（AGC「应用信息-应用图标」按后台提示取用）
- ``promo-2160x1080.png``  横版宣传图（品牌色/名称/一句话简介/仪表盘图形，非 UI 截图）
- ``promo-1080x2160.png``  竖版宣传图

用法：
    cd <repo>
    .venv/bin/python3 harmonyos/docs/release/assets/generate-assets.py

设计约束：
- 图标满幅方形、不透明：AGC / 应用市场会自行做圆角与投影遮罩，自行加圆角会二次裁切。
- 宣传图不绘制任何应用界面元素（避免伪造 UI 截图），只用品牌 Logo、色块与仪表盘几何图形。
- 文案不写未实现能力（Command Code / GOAT、账户总览面板）。
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

# 品牌色（取自 assets/GoGauge.png 的蓝色/青色 + 工程图标底色）
BLUE = (30, 144, 255)        # #1E90FF 主蓝
CYAN = (38, 198, 218)        # #26C6DA 青
NAVY_TOP = (9, 16, 29)       # #09101D
NAVY_BOTTOM = (24, 39, 61)   # #18273D
TEXT = (233, 241, 252)
SUB = (150, 172, 202)


# ----------------------------------------------------------------------------
# 字体
# ----------------------------------------------------------------------------
def font(size: int, bold: bool = False, zh: bool = False) -> ImageFont.FreeTypeFont:
    """挑一个本机可用的字体；中文优先 Hiragino Sans GB/Arial Unicode，英文用 Arial。"""
    if zh:
        path = "/System/Library/Fonts/Hiragino Sans GB.ttc"
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=2 if bold else 0)
            except OSError:
                pass
        path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


# ----------------------------------------------------------------------------
# 通用绘制
# ----------------------------------------------------------------------------
def vertical_gradient(size: tuple[int, int], top: tuple[int, int, int],
                      bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)],
               fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img


def radial_glow(size: tuple[int, int], center: tuple[int, int], radius: int,
                color: tuple[int, int, int]) -> Image.Image:
    """返回一张只含柔光（RGBA）的图层，可直接 alpha_composite。"""
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    steps = 40
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        alpha = int(40 * (1 - i / steps) ** 1.5)
        d.ellipse([center[0] - r, center[1] - r, center[0] + r, center[1] + r],
                  fill=(*color, alpha))
    return glow.filter(ImageFilter.GaussianBlur(radius // 4))


def trim_alpha(img: Image.Image) -> Image.Image:
    bbox = img.split()[-1].getbbox()
    return img.crop(bbox) if bbox else img


def load_brand() -> Image.Image:
    """品牌 Logo（最高可用分辨率，透明底）。"""
    icns = os.path.join(REPO, "assets", "GoGauge.icns")
    if os.path.exists(icns):
        try:
            img = Image.open(icns)
            sizes = img.info.get("sizes") or []
            if sizes:
                img.size = sizes[0]  # ICNS 最大表示（512@2x = 1024px）
            img.load()
            return trim_alpha(img.convert("RGBA"))
        except Exception:  # noqa: BLE001 - 回退到 png
            pass
    png = os.path.join(REPO, "assets", "GoGauge.png")
    return trim_alpha(Image.open(png).convert("RGBA"))


def fit_contain(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    ratio = min(box_w / img.width, box_h / img.height)
    return img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
                      Image.LANCZOS)


def paste_center(canvas: Image.Image, img: Image.Image, cx: int, cy: int) -> None:
    canvas.alpha_composite(img, (cx - img.width // 2, cy - img.height // 2))


# ----------------------------------------------------------------------------
# 应用图标
# ----------------------------------------------------------------------------
def make_icon(size: int = 1024) -> Image.Image:
    # 优先直接使用包内 AppScope 图标（foreground+background 合成），保证 AGC
    # 「应用图标必须与包内图标一致」逐像素一致；文件不存在时才按品牌 Logo 重绘。
    pkg_icon = os.path.join(REPO, "harmonyos", "AppScope", "resources",
                            "base", "media", "app_icon.png")
    if os.path.exists(pkg_icon):
        return Image.open(pkg_icon).convert("RGB").resize((size, size), Image.LANCZOS)
    canvas = vertical_gradient((size, size), NAVY_TOP, NAVY_BOTTOM).convert("RGBA")
    canvas.alpha_composite(radial_glow((size, size), (size // 2, int(size * 0.44)),
                                       int(size * 0.62), BLUE))
    # 细环背景（仪表盘意象，很轻，不抢 Logo）
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rr = int(size * 0.415)
    rd.ellipse([size // 2 - rr, size // 2 - rr, size // 2 + rr, size // 2 + rr],
               outline=(*BLUE, 46), width=max(3, size // 200))
    canvas.alpha_composite(ring)
    # 品牌 Logo：内容占画布 ~58%（AGC 圆角裁切后四周仍有安全边）
    logo = fit_contain(load_brand(), int(size * 0.58), int(size * 0.58))
    paste_center(canvas, logo, size // 2, size // 2)
    return canvas.convert("RGB")


# ----------------------------------------------------------------------------
# 宣传图
# ----------------------------------------------------------------------------
def draw_gauge_overlay(size: tuple[int, int], cx: int, cy: int, radius: int,
                       alpha_scale: float = 1.0) -> Image.Image:
    """在透明图层上画「仪表盘」几何装饰：外弧 + 内弧 + 指针 + 轴心（无 UI 元素）。"""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    width = max(8, radius // 20)
    start, end = -152, -28
    d.arc([cx - radius, cy - radius, cx + radius, cy + radius], start=start, end=end,
          fill=(*BLUE, int(200 * alpha_scale)), width=width)
    r2 = int(radius * 0.70)
    d.arc([cx - r2, cy - r2, cx + r2, cy + r2], start=start + 22, end=end - 22,
          fill=(*CYAN, int(150 * alpha_scale)), width=max(5, width * 3 // 5))
    # 指针
    ang = math.radians(start + (end - start) * 0.62)
    tip = (cx + int(r2 * 0.86 * math.cos(ang)), cy + int(r2 * 0.86 * math.sin(ang)))
    d.line([(cx, cy), tip], fill=(255, 255, 255, int(210 * alpha_scale)),
           width=max(5, width // 3))
    dot = max(6, width // 2)
    d.ellipse([cx - dot, cy - dot, cx + dot, cy + dot],
              fill=(255, 255, 255, int(225 * alpha_scale)))
    return layer


def draw_chips(draw: ImageDraw.ImageDraw, chips: list[str], x: int, y: int,
               fnt: ImageFont.FreeTypeFont, pad_x: int = 26, pad_y: int = 12,
               gap: int = 20) -> None:
    """实心 chips（画在已合成的 RGB 画布上，颜色为实色，避免 alpha 直绘导致的色块）。"""
    cx = x
    h = fnt.size + pad_y * 2
    for text in chips:
        w = int(draw.textlength(text, font=fnt)) + pad_x * 2
        draw.rounded_rectangle([cx, y, cx + w, y + h], radius=h // 2,
                               fill=(36, 55, 82), outline=(58, 96, 138), width=2)
        draw.text((cx + pad_x, y + pad_y - 1), text, font=fnt, fill=TEXT)
        cx += w + gap


def chip_row_width(draw: ImageDraw.ImageDraw, chips: list[str],
                   fnt: ImageFont.FreeTypeFont, pad_x: int = 26, gap: int = 20) -> int:
    return sum(int(draw.textlength(c, font=fnt)) + pad_x * 2 for c in chips) + gap * (len(chips) - 1)


def make_promo_landscape() -> Image.Image:
    W, H = 2160, 1080
    canvas = vertical_gradient((W, H), (8, 13, 24), (27, 44, 68)).convert("RGBA")
    canvas.alpha_composite(radial_glow((W, H), (int(W * 0.82), int(H * 0.52)),
                                       int(H * 0.85), BLUE))
    canvas.alpha_composite(draw_gauge_overlay((W, H), int(W * 0.805), int(H * 0.66),
                                              int(H * 0.36)))

    brand = load_brand()
    logo = fit_contain(brand, int(H * 0.20), int(H * 0.20))
    paste_center(canvas, logo, int(W * 0.093) + logo.width // 2, int(H * 0.235))
    canvas = canvas.convert("RGB")
    d = ImageDraw.Draw(canvas)

    x = int(W * 0.075)
    f_title = font(int(H * 0.135), bold=True)
    f_zh = font(int(H * 0.058), bold=True, zh=True)
    f_en = font(int(H * 0.030))
    f_chip = font(int(H * 0.026), zh=True)
    f_small = font(int(H * 0.019))
    f_small_zh = font(int(H * 0.019), zh=True)

    d.text((x, int(H * 0.385)), "GoGauge", font=f_title, fill=TEXT)
    d.text((x, int(H * 0.555)), "OpenCode Go 用量仪表盘", font=f_zh, fill=CYAN)
    d.text((x, int(H * 0.645)), "Quota windows · usage stats · request records · multi-account",
           font=f_en, fill=SUB)
    draw_chips(d, ["配额窗口", "用量统计", "使用记录", "多账号", "双主题", "中英"],
               x, int(H * 0.735), f_chip)

    d.text((x, H - int(H * 0.075)), "HarmonyOS NEXT · 本地优先 · 无遥测",
           font=f_small_zh, fill=SUB)
    d.text((W - x, H - int(H * 0.075)), "github.com/w-PiaoPiao/opencode-go-gauge",
           font=f_small, fill=SUB, anchor="ra")
    return canvas


def make_promo_portrait() -> Image.Image:
    W, H = 1080, 2160
    canvas = vertical_gradient((W, H), (8, 13, 24), (27, 44, 68)).convert("RGBA")
    canvas.alpha_composite(radial_glow((W, H), (W // 2, int(H * 0.24)),
                                       int(W * 0.85), BLUE))
    # 中下部仪表盘背景图形（品牌意象，低透明度，不画任何 UI 元素）
    canvas.alpha_composite(draw_gauge_overlay((W, H), W // 2, int(H * 0.850),
                                              int(W * 0.30), alpha_scale=0.50))

    brand = load_brand()
    logo = fit_contain(brand, int(W * 0.34), int(W * 0.34))
    paste_center(canvas, logo, W // 2, int(H * 0.235))
    canvas = canvas.convert("RGB")
    d = ImageDraw.Draw(canvas)

    f_title = font(int(W * 0.125), bold=True)
    f_zh = font(int(W * 0.055), bold=True, zh=True)
    f_en = font(int(W * 0.030))
    f_chip = font(int(W * 0.028), zh=True)
    f_small = font(int(W * 0.022))
    f_small_zh = font(int(W * 0.022), zh=True)

    d.text((W // 2, int(H * 0.415)), "GoGauge", font=f_title, fill=TEXT, anchor="ma")
    d.text((W // 2, int(H * 0.495)), "OpenCode Go 用量仪表盘", font=f_zh, fill=CYAN, anchor="ma")
    d.text((W // 2, int(H * 0.560)),
           "Quota windows · usage stats · records · multi-account", font=f_en, fill=SUB, anchor="ma")

    row1 = ["配额窗口", "用量统计"]
    row2 = ["使用记录", "多账号"]
    draw_chips(d, row1, (W - chip_row_width(d, row1, f_chip)) // 2, int(H * 0.615), f_chip)
    draw_chips(d, row2, (W - chip_row_width(d, row2, f_chip)) // 2, int(H * 0.665), f_chip)

    d.text((W // 2, int(H * 0.925)), "HarmonyOS NEXT · 本地优先 · 无遥测",
           font=f_small_zh, fill=SUB, anchor="ma")
    d.text((W // 2, int(H * 0.955)), "github.com/w-PiaoPiao/opencode-go-gauge",
           font=f_small, fill=SUB, anchor="ma")
    return canvas


def make_package_icon(size: int = 1024) -> Image.Image | None:
    """以 HAP 内置图标为源，放大到 1024（备用：不改包内图标时，保证商店图标与包内一致）。

    AGC 要求「应用图标必须与软件包中的应用图标一致」。当前包内图标是
    ``harmonyos/entry/src/main/resources/base/media/icon.png``（512，占位设计）。
    如果最终 HAP 未替换为品牌分层图标，请上传本函数产出的
    ``icon-1024-package-match.png``，而不是品牌版 icon-1024.png。
    """
    src = os.path.join(REPO, "harmonyos", "entry", "src", "main", "resources",
                       "base", "media", "icon.png")
    if not os.path.exists(src):
        return None
    im = Image.open(src).convert("RGBA")
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(im.resize((size, size), Image.LANCZOS))
    return canvas.convert("RGB")


def main() -> None:
    os.makedirs(HERE, exist_ok=True)
    icon = make_icon(1024)
    icon.save(os.path.join(HERE, "icon-1024.png"), optimize=True)
    pkg_icon = make_package_icon(1024)
    if pkg_icon is not None:
        pkg_icon.save(os.path.join(HERE, "icon-1024-package-match.png"), optimize=True)
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "icon-512.png"), optimize=True)
    icon.resize((216, 216), Image.LANCZOS).save(os.path.join(HERE, "icon-216.png"), optimize=True)
    make_promo_landscape().save(os.path.join(HERE, "promo-2160x1080.png"), optimize=True)
    make_promo_portrait().save(os.path.join(HERE, "promo-1080x2160.png"), optimize=True)
    print("assets written ->", HERE)


if __name__ == "__main__":
    main()
