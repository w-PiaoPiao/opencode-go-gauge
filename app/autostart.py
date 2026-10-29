"""开机自启 (macOS LaunchAgent).

实现取舍: SMAppService (macOS 13+) 要求 app 正式签名且常驻标准位置,
对 ad-hoc 签名的开源分发包不可靠; LaunchAgent plist 全版本通用、无签名要求.
代价: 用户移动 .app 位置后需重新开关一次该设置 (plist 记录的是旧路径).

2026-10 修复 (P2-4): 自启启动时本进程就是该 LaunchAgent 的 job, 关闭自启时
``launchctl unload`` 会给当前进程发 SIGTERM —— 设置虽已落库, 但响应发不出,
用户看到的是"一点关闭自启, app 就退出". 因此 disable() 先判断"当前进程是否
就是该 job", 是则只删 plist (下次登录不再拉起, 当前会话随 logout 回收).
"""
from __future__ import annotations

import logging
import os
import plistlib
import re
import subprocess
import sys

PLIST_ID = "com.opencode.gogauge"

_log = logging.getLogger(__name__)


def _plist_path() -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_ID}.plist")


def supported() -> bool:
    """仅 macOS 打包版支持 (源码运行注册自启无意义)."""
    return sys.platform == "darwin" and bool(getattr(sys, "frozen", False))


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
        if _job_loaded():
            # 已加载的 job 再 load 会因 RunAtLoad 立刻再起一个实例: 单实例守卫
            # 会给首实例发"显示窗口", 表现为"点一下自启设置, 窗口自己跳出来".
            # plist 已刷新, 下次登录按新路径生效; 这里不需要也不应该再 load.
            _log.info("launch-at-login already loaded; plist refreshed only")
            return True
        _launchctl(["load", path])
        _log.info("launch-at-login enabled: %s", exe)
        return True
    except Exception as exc:  # noqa: BLE001
        _log.warning("launch-at-login enable failed: %s", exc)
        return False


def disable() -> bool:
    path = _plist_path()
    if not os.path.isfile(path):
        return True
    try:
        if _running_as_launch_agent():
            # P2-4: unload 会 SIGTERM 当前进程 (自启启动时本进程即该 job).
            # 只删 plist 即可达成"下次登录不自启": launchd 在下次登录重建 job;
            # 当前会话的 in-memory job 随 logout 回收, KeepAlive=false 不会拉起.
            _log.warning(
                "launch-at-login disabled from the agent process itself; "
                "skip launchctl unload to avoid SIGTERM"
            )
            os.remove(path)
            return True
        _launchctl(["unload", path])
        _log.info("launch-at-login disabled")
        os.remove(path)
        return True
    except Exception as exc:  # noqa: BLE001
        _log.warning("launch-at-login disable failed: %s", exc)
        return False


def _job_loaded() -> bool:
    """本 LaunchAgent 是否已加载到当前用户 domain (launchctl list <label> 成功)."""
    try:
        completed = subprocess.run(
            ["launchctl", "list", PLIST_ID],
            capture_output=True,
            timeout=5,
        )
    except Exception:  # noqa: BLE001 launchctl 不可用按"未加载"处理 (走 load)
        return False
    return completed.returncode == 0


def _running_as_launch_agent() -> bool:
    """当前进程是否就是本 LaunchAgent 的 job 进程 (即由自启拉起).

    ``launchctl list <label>`` 会打印 job 状态, 其中 ``"PID" = N`` 是运行中的
    进程号; 等于 ``os.getpid()`` 说明本进程由 launchd 拉起 —— 此时 unload 会
    停掉这个 job 并 SIGTERM 自己. launchctl 不可用/未加载/解析失败一律按
    "不是"处理, 维持原 unload 行为 (失败也不影响下次登录是否自启).
    """
    try:
        completed = subprocess.run(
            ["launchctl", "list", PLIST_ID],
            capture_output=True,
            timeout=5,
        )
    except Exception:  # noqa: BLE001
        return False
    if completed.returncode != 0:
        return False
    output = completed.stdout or b""
    if isinstance(output, bytes):
        output = output.decode("utf-8", "replace")
    match = re.search(r'"PID"\s*=\s*(\d+)', output)
    if not match:
        return False
    try:
        return int(match.group(1)) == os.getpid()
    except ValueError:  # pragma: no cover - 正则已保证是数字
        return False


def _launchctl(args: list[str]) -> None:
    try:
        subprocess.run(["launchctl"] + args, capture_output=True, timeout=5)
    except Exception:  # noqa: BLE001  load/unload 失败不阻塞 (登录时仍按 plist 生效)
        pass
