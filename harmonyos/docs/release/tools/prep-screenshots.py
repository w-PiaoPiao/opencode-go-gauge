#!/usr/bin/env python3
"""把模拟器/真机原始截图转换为 AppGallery「素材规范」要求的尺寸。

官方素材规范（2026-10，V10）：
- 手机：介绍截图 横向 3-10 张 16:9 1920×1080 或 竖向 3-10 张 9:16 1080×1920，
        PNG/JPG/JPEG ≤5MB；应用图标 216×216 或 1024×1024，PNG ≤3MB。
- 平板：横向 3-10 张 3:2 1920×1280 或 竖向 2:3 1280×1920，≤5MB。
- PC/2in1：3-10 张 16:9 1920×1080，≤5MB。
来源：https://developer.huawei.com/consumer/cn/doc/app/agc-help-app-visual-asset-spec-0000002277607976
（以 AGC 后台实际提示为准）

用法：
    # 全部设备、默认 pad 模式（等比缩放后留边，不裁掉界面内容）
    .venv/bin/python3 harmonyos/docs/release/tools/prep-screenshots.py --all

    # 只处理手机，改用裁切模式；自定义背景色
    .venv/bin/python3 harmonyos/docs/release/tools/prep-screenshots.py \
        --device phone --mode crop --background "#12141A"

输入默认目录：harmonyos/docs/store-assets/screenshots/{phone,tablet,pc}/
输出默认目录：harmonyos/docs/release/screenshots-upload/{phone,tablet,pc}/
（不覆盖原始截图；只写 release/ 下，符合本仓库的写入范围约定）

自动排除（避免把非上架资产转成“素材”）：
- `_degraded/` 子目录（退化验证/页面参数未生效的中间资产，禁止上架）
- `smoke-*` 文件（运行时验证证据，不是商店素材；需要时加 --include-evidence）

pad 模式背景色默认 auto：从截图边缘采样应用背景色后补边，避免亮色主题截图上出现
深色留边（也可显式传 --background "#FAFAFC"）。

命名约定（由截图流水线产出，最终以 screenshot-manifest.md 为准）：
    {page}-{light|dark}.jpeg   page ∈ home | stats | records | settings | login | welcome

注意：
- pad 模式会在两侧/上下补品牌底色；crop 模式会裁掉边缘内容。商店审核要求截图真实
  反映应用功能，不得出现真实个人信息（账号、邮箱、Key 名称等）或调试入口。
- 手机默认输出竖向 1080×1920；如果输入是横向，则输出 1920×1080。
- 平板默认输出横向 1920×1280；输入为竖向时输出 1280×1920。
- PC/2in1 固定输出 1920×1080。
"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RELEASE_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(RELEASE_DIR, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO, "harmonyos", "docs", "store-assets", "screenshots")
OUT_ROOT = os.path.join(RELEASE_DIR, "screenshots-upload")

DEVICES = ("phone", "tablet", "pc")


def parse_hex(color: str) -> tuple[int, int, int]:
    c = color.strip().lstrip("#")
    if len(c) != 6:
        raise argparse.ArgumentTypeError("背景色格式应为 #RRGGBB")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def target_size(device: str, src_size: tuple[int, int]) -> tuple[int, int]:
    w, h = src_size
    portrait = h > w
    if device == "phone":
        return (1080, 1920) if portrait else (1920, 1080)
    if device == "tablet":
        return (1280, 1920) if portrait else (1920, 1280)
    return (1920, 1080)


def sample_background(src: Image.Image) -> tuple[int, int, int]:
    """从截图边缘采样应用背景色（用于 pad 补边，尽量无缝）。"""
    im = src.convert("RGB")
    w, h = im.size
    pts = [(w // 2, 2), (w // 2, h - 3), (2, h // 2), (w - 3, h // 2)]
    vals = [im.getpixel(p) for p in pts]
    return tuple(sum(v[i] for v in vals) // len(vals) for i in range(3))  # type: ignore[return-value]


def convert(src: Image.Image, size: tuple[int, int], mode: str,
            bg: tuple[int, int, int] | None) -> Image.Image:
    src = src.convert("RGB")
    tw, th = size
    sw, sh = src.size
    if mode == "crop":
        scale = max(tw / sw, th / sh)
        nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
        resized = src.resize((nw, nh), Image.LANCZOS)
        left = (nw - tw) // 2
        top = (nh - th) // 2
        return resized.crop((left, top, left + tw, top + th))
    # pad: 等比缩放到目标框内，剩余区域补背景色（默认取截图边缘色）
    if bg is None:
        bg = sample_background(src)
    scale = min(tw / sw, th / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    resized = src.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", size, bg)
    canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
    return canvas


def iter_inputs(device: str, include_evidence: bool = False,
                input_root: str | None = None):
    root = os.path.join(input_root or SRC_ROOT, device)
    if not os.path.isdir(root):
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "_degraded")
        for name in sorted(filenames):
            if name.lower().startswith("smoke-") and not include_evidence:
                continue  # 运行时验证证据，不是商店素材
            if name.lower().endswith((".jpeg", ".jpg", ".png")):
                yield os.path.join(dirpath, name)


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert screenshots to AppGallery spec sizes")
    ap.add_argument("--device", choices=DEVICES, help="只处理某一种设备")
    ap.add_argument("--all", action="store_true", help="处理 phone/tablet/pc 全部")
    ap.add_argument("--mode", choices=("pad", "crop"), default="pad",
                    help="pad=等比缩放留边（默认，不丢内容）；crop=等比覆盖裁切")
    ap.add_argument("--background", type=parse_hex, default=None,
                    help="pad 模式背景色，默认 auto（采样截图边缘色）；也可传 #RRGGBB")
    ap.add_argument("--include-evidence", action="store_true",
                    help="同时转换 smoke-* 运行时验证证据（默认排除，不用于上架）")
    ap.add_argument("--input-root", default=SRC_ROOT, help="输入根目录")
    ap.add_argument("--output-root", default=OUT_ROOT, help="输出根目录")
    ap.add_argument("--quality", type=int, default=92, help="JPEG 质量，默认 92")
    args = ap.parse_args()

    devices = DEVICES if args.all or not args.device else (args.device,)
    total = 0
    for device in devices:
        src_dir = os.path.join(args.input_root, device)
        if not os.path.isdir(src_dir):
            print(f"[skip] {src_dir} 不存在（截图流水线尚未产出？）")
            continue
        for path in iter_inputs(device, args.include_evidence, args.input_root):
            rel = os.path.relpath(path, args.input_root)
            out_path = os.path.join(args.output_root, rel)
            out_path = os.path.splitext(out_path)[0] + ".jpeg"
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            try:
                with Image.open(path) as im:
                    size = target_size(device, im.size)
                    out = convert(im, size, args.mode, args.background)
                    out.save(out_path, "JPEG", quality=args.quality, optimize=True)
                total += 1
                print(f"[ok] {rel} -> {os.path.relpath(out_path, REPO)} ({size[0]}x{size[1]})")
            except Exception as exc:  # noqa: BLE001
                print(f"[error] {rel}: {exc}", file=sys.stderr)
    print(f"done: {total} image(s); output -> {args.output_root}")
    if total == 0:
        print("提示：把上架截图放到 docs/store-assets/screenshots/{phone,tablet,pc}/ 后再运行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
