"""生成 GoGauge Windows 应用图标（多尺寸 ICO）。

品牌几何的唯一来源是 ``assets/generate_logo.py``（仪表盘外环左上角断口 + H 位于断口处）。
本脚本只负责把它导出成 Windows .ico，避免与 macOS/鸿蒙图标出现两套设计。

运行: python scripts/build_icon.py  ->  assets/GoGauge.ico
"""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from assets.generate_logo import write_windows_ico  # noqa: E402

OUT = os.path.join(REPO, "assets", "GoGauge.ico")


if __name__ == "__main__":
    write_windows_ico(OUT)
    print("wrote", OUT)
