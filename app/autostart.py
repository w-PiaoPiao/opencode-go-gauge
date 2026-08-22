"""开机自启 (macOS LaunchAgent).

实现取舍: SMAppService (macOS 13+) 要求 app 正式签名且常驻标准位置,
对 ad-hoc 签名的开源分发包不可靠; LaunchAgent plist 全版本通用、无签名要求.
代价: 用户移动 .app 位置后需重新开关一次该设置 (plist 记录的是旧路径).
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys

PLIST_ID = "com.opencode.gogauge"


def _plist_path() -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_ID}.plist")


def supported() -> bool:
    """仅 macOS 打包版支持 (源码运行注册自启无意义)."""
    return sys.platform == "darwin" and bool(getattr(sys, "frozen", False))


def is_enabled() -> bool:
    return supported() and os.path.isfile(_plist_path())


def enable() -> bool:
    if not supported():
        return False
    try:
        exe = os.path.abspath(sys.executable)  # GoGauge.app/Contents/MacOS/GoGauge
        plist = {
            "Label": PLIST_ID,
            "ProgramArguments": [exe],
            "RunAtLoad": True,
            "KeepAlive": False,
            "ProcessType": "Interactive",
        }
        path = _plist_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            plistlib.dump(plist, fh)
        _launchctl(["load", path])
        return True
    except Exception:  # noqa: BLE001
        return False


def disable() -> bool:
    if not os.path.isfile(_plist_path()):
        return True
    try:
        _launchctl(["unload", _plist_path()])
        os.remove(_plist_path())
        return True
    except Exception:  # noqa: BLE001
        return False


def _launchctl(args: list[str]) -> None:
    try:
        subprocess.run(["launchctl"] + args, capture_output=True, timeout=5)
    except Exception:  # noqa: BLE001  load/unload 失败不阻塞 (登录时仍按 plist 生效)
        pass
