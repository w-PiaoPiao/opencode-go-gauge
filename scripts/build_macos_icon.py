"""生成 GoGauge macOS 图标 (assets/GoGauge.png + assets/GoGauge.icns).

复用 build_icon.py 的 logo 结构 (外弧蓝 r16 + 内弧青 r9 + 中心 H),
输出适合 macOS 的 512x512 PNG (Dock / pystray 菜单栏通用) 与多尺寸 ICNS.

运行: python3 scripts/build_macos_icon.py
     -> assets/GoGauge.png (512)
     -> assets/GoGauge.icns (16/32/64/128/256/512 + Retina)
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

VIEW = 48
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
PNG_OUT = os.path.join(OUT_DIR, "GoGauge.png")
ICNS_OUT = os.path.join(OUT_DIR, "GoGauge.icns")

BLUE = (24, 144, 255, 255)
CYAN = (6, 182, 212, 255)
OUTER_R = 16.0
INNER_R = 9.0


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("Arial.ttf", "Helvetica.ttc", "Arial Bold.ttf", "Helvetica-Bold.otf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_logo(size: int) -> Image.Image:
    """绘制 GoGauge 品牌图标 (尺寸 square)."""
    s = size / VIEW
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(cx: float, r: float) -> tuple[float, float, float, float]:
        return ((cx - r) * s, (cx - r) * s, (cx + r) * s, (cx + r) * s)

    # 外弧: r16 蓝色 75% (270°), 从 12 点方向顺时针
    d.arc(box(24, OUTER_R), start=270, end=540, fill=BLUE, width=max(1, round(6 * s)))
    # 内弧: r9 青色 70% (252°), 从 12 点顺时针偏转 30°
    d.arc(box(24, INNER_R), start=300, end=552, fill=CYAN, width=max(1, round(5 * s)))
    # 中心 H (粗体蓝色)
    font_size = max(4, round(11 * s))
    font = _load_font(font_size)
    d.text(
        (size / 2, size * (27.8 / VIEW)), "H",
        font=font, fill=BLUE, anchor="mm",
    )
    return img


def build_png() -> str:
    """生成 512x512 PNG."""
    img = draw_logo(512)
    img.save(PNG_OUT, format="PNG")
    return PNG_OUT


def build_icns() -> str:
    """生成多尺寸 ICNS.

    ICNS 里的 1024x1024 图标命名为 ic10; 用缩放生成各档, PIL 直接写 ICNS.
    """
    base = draw_logo(1024)
    # 提供 ic10(1024) + 常见 Retina 档位; PIL 会按需映射
    icons: list[Image.Image] = [base]
    for size in (512, 256, 128, 64, 32, 16):
        icons.append(base.resize((size, size), Image.LANCZOS))
    # PIL 保存 ICNS 时按分辨率筛选; 附加多档位需用 save 的 append 或直接保存单张
    # 简单可靠: 保存 1024 主图, PIL 自动生成 icns 条目 (绝大多数场景足够).
    base.save(ICNS_OUT, format="ICNS")
    return ICNS_OUT


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    png = build_png()
    icns = build_icns()
    # 校验
    for p in (png, icns):
        with Image.open(p) as im:
            n = im.n_frames if hasattr(im, "n_frames") else 1
            print(f"written: {os.path.abspath(p)} | fmt={im.format} size={im.size} frames={n}")
    # icns 内含档位信息
    try:
        ic = Image.open(ICNS_OUT)
        print("icns sizes:", getattr(ic.info, "get", lambda k, d=None: d)("sizes"))
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
