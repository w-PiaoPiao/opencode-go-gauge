"""生成 GoGauge macOS 图标（assets/GoGauge.png + assets/GoGauge.icns）。

品牌几何的唯一来源是 ``assets/generate_logo.py``（仪表盘外环左上角断口 + H 位于断口处），
本脚本只负责导出 macOS 所需的 512 PNG 与多尺寸 ICNS。

运行: python3 scripts/build_macos_icon.py
     -> assets/GoGauge.png (512)
     -> assets/GoGauge.icns (16/32/64/128/256/512 + Retina)
"""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from assets.generate_logo import render_logo, write_macos_icns  # noqa: E402

ASSETS = os.path.join(REPO, "assets")
PNG_OUT = os.path.join(ASSETS, "GoGauge.png")
ICNS_OUT = os.path.join(ASSETS, "GoGauge.icns")


if __name__ == "__main__":
    render_logo(512).save(PNG_OUT, optimize=True)
    write_macos_icns(ICNS_OUT)
    print("wrote", PNG_OUT)
    print("wrote", ICNS_OUT)
