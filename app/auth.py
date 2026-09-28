"""WebView 登录: 加载 opencode.ai 控制台登录页, 捕获会话 cookie 与工作区 ID.

原理: pywebview (WebView2) 的 window.get_cookies() 可直接读取 HttpOnly cookie,
登录完成后窗口位于 opencode.ai 域, 从中提取会话 cookie.

2026-09 opencode.ai 前端改版: 旧授权页 ``auth.opencode.ai/authorize`` 与旧会话
cookie ``auth`` 已废弃, 现由 ``/console`` 控制台接管登录, 会话 cookie 为
``__Host-console_session`` (登录入口 https://opencode.ai/console/login)。
"""
from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import uuid
from http.cookies import SimpleCookie as SimpleCookieCls
from typing import Callable, Optional
from urllib.parse import parse_qsl, unquote, urlencode

import webview

CONSOLE_LOGIN_URL = "https://opencode.ai/console/login"
LOGIN_NEXT_PATH = "/console/"
# 会话 cookie: 新版 __Host-console_session 优先, 旧版 auth 兼容历史账号
SESSION_COOKIE_NAMES = ("__Host-console_session", "auth")
COOKIE_POLL_SEC = 1.0
_WORKSPACE_URL_RE = re.compile(r"/(?:console|workspace)/(wrk_[A-Za-z0-9]+)")
_LOG_FILE = os.path.join(tempfile.gettempdir(), "gousage_login.log")


def _log(msg: str) -> None:
    """同时输出到 stdout 与日志文件 (便于诊断)."""
    print(msg, flush=True)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def build_login_url() -> str:
    """构造控制台登录页 URL (next 指向控制台首页)."""
    from urllib.parse import quote

    return f"{CONSOLE_LOGIN_URL}?next={quote(LOGIN_NEXT_PATH, safe='')}"


def _cookie_value(cookie) -> dict[str, str]:
    """把 pywebview 返回的 cookie 对象摊平成 {name: value}."""
    pairs: dict[str, str] = {}
    if isinstance(cookie, SimpleCookieCls):  # SimpleCookie 是 dict 子类, 需先判断
        for name in list(cookie.keys()):
            try:
                pairs[name] = cookie[name].value
            except Exception:  # noqa: BLE001
                continue
    elif isinstance(cookie, dict):
        name = cookie.get("name") or ""
        if name:
            pairs[name] = cookie.get("value") or ""
    return pairs


def _pick_session_cookie(cookies) -> Optional[tuple[str, str]]:
    """按优先级挑选会话 cookie, 返回 (cookie名, 值)."""
    jar: dict[str, str] = {}
    for cookie in cookies or []:
        jar.update(_cookie_value(cookie))
    for name in SESSION_COOKIE_NAMES:
        value = jar.get(name) or ""
        if value.strip():
            return name, value
    return None


class LoginWatcher:
    """后台轮询登录窗口, 捕获会话 cookie."""

    def __init__(
        self,
        win,
        on_success: Callable[[str, str], None],
        on_cancelled: Optional[Callable[[], None]] = None,
    ):
        self.win = win
        self.on_success = on_success  # fn(session_cookie, workspace_hint)
        self.on_cancelled = on_cancelled
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.done = False
        # GitHub 卡死自动续跑状态
        self._oauth_entry: Optional[str] = None  # 最近一次授权入口 URL
        self._stuck_since: Optional[float] = None  # 停在无关 GitHub 页面的起始时刻
        self._reloads = 0  # 已自动续跑次数
        self._github_cls: Optional[str] = None  # 上次记录的 GitHub 页面分类 (去重日志)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="gousage-login")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _window_alive(self) -> bool:
        try:
            return self.win in webview.windows
        except Exception:  # noqa: BLE001
            return False

    def _run(self) -> None:
        _log("[login] watcher started")
        while not self._stop.is_set():
            try:
                url = self.win.get_current_url() or ""
            except Exception as exc:  # noqa: BLE001 窗口未加载完成或已销毁
                if not self._window_alive():
                    _log("[login] window closed, watcher exits")
                    break
                self._stop.wait(1.0)
                continue

            if url.startswith("https://opencode.ai"):
                self._stuck_since = None  # 已回到 opencode 域, 卡死计时清除
                try:
                    cookies = self.win.get_cookies() or []
                    raw_desc = [str(c) for c in cookies]
                except Exception as exc:  # noqa: BLE001
                    cookies = []
                    raw_desc = [f"<get_cookies ERROR {type(exc).__name__}: {exc}>"]
                _log(f"[login] on opencode.ai, url={url[:120]}, cookies={raw_desc}")

                picked = _pick_session_cookie(cookies)
                if picked:
                    name, value = picked
                    match = _WORKSPACE_URL_RE.search(url)
                    workspace_hint = match.group(1) if match else "Default"
                    _log(
                        f"[login] SUCCESS: {name} captured (len={len(value)}), ws={workspace_hint}"
                    )
                    self.done = True
                    self._stop.set()
                    self.on_success(f"{name}={value}", workspace_hint)
                    return
            self._stop.wait(COOKIE_POLL_SEC)
        if not self.done and self.on_cancelled:
            self.on_cancelled()


def clear_login_cookies(win) -> None:
    """清空登录窗口的 Cookie (添加新账号时确保出现登录页, 可切换账号).

    WebView2 的 DeleteAllCookies 是 profile 级操作, 旧会话 token 已落库, 不受影响。
    """
    try:
        win.clear_cookies()
        _log("[login] cookies cleared for fresh sign-in")
    except Exception as exc:  # noqa: BLE001 老版本 pywebview 无此能力: 忽略
        _log(f"[login] clear_cookies unavailable: {exc}")


__all__ = [
    "CONSOLE_LOGIN_URL",
    "LoginWatcher",
    "build_login_url",
    "clear_login_cookies",
]
