"""WebView 登录: 加载 provider 官方登录页, 捕获会话 cookie.

原理: pywebview (WebView2 / WKWebView) 的 window.get_cookies() 可直接读取 HttpOnly cookie,
登录完成后窗口位于目标 provider 域, 从中提取会话 cookie:
- opencode: opencode.ai 域的 ``auth`` cookie + workspace (wrk_xxx) 提示
- commandcode: commandcode.ai 域的 ``__Secure-commandcode_prod_.session_token``
"""
from __future__ import annotations

import os
import re
import tempfile
import threading
import uuid
from http.cookies import SimpleCookie as SimpleCookieCls
from typing import Callable, Optional

import webview

from .db import PROVIDER_COMMANDCODE, PROVIDER_OPENCODE

# opencode
LOGIN_BASE = "https://auth.opencode.ai/authorize"
LOGIN_CLIENT_ID = "app"
LOGIN_REDIRECT_URI = "https://opencode.ai/auth/callback"
AUTH_COOKIE_NAME = "auth"
OPCODE_HOST = "opencode.ai"
_WORKSPACE_URL_RE = re.compile(r"/workspace/(wrk_[A-Za-z0-9]+)")

# commandcode
CC_LOGIN_BASE = "https://commandcode.ai/signin"
CC_HOST = "commandcode.ai"
CC_AUTH_COOKIE_NAME = "__Secure-commandcode_prod_.session_token"

COOKIE_POLL_SEC = 1.0
_LOG_FILE = os.path.join(tempfile.gettempdir(), "gousage_login.log")


def _log(msg: str) -> None:
    """同时输出到 stdout 与日志文件 (便于诊断)."""
    print(msg, flush=True)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def build_login_url(provider: str = PROVIDER_OPENCODE) -> str:
    """构造授权登录 URL."""
    if provider == PROVIDER_COMMANDCODE:
        return CC_LOGIN_BASE
    params = {
        "client_id": LOGIN_CLIENT_ID,
        "redirect_uri": LOGIN_REDIRECT_URI,
        "response_type": "code",
        "state": uuid.uuid4().hex,
    }
    from urllib.parse import urlencode
    return f"{LOGIN_BASE}?{urlencode(params)}"


def _cookie_entries(cookies: list) -> list[tuple[str, str]]:
    """把 pywebview 的 cookie 列表归一为 (name, value) 列表.

    pywebview 返回 http.cookies.SimpleCookie 对象 (dict 子类!) 或 dict,
    两种都兼容.
    """
    entries: list[tuple[str, str]] = []
    for cookie in cookies or []:
        names: list[str] = []
        if isinstance(cookie, SimpleCookieCls):
            names = list(cookie.keys())
        elif isinstance(cookie, dict):
            names = [cookie.get("name", "")]
        for name in names:
            try:
                value = (
                    cookie[name].value
                    if isinstance(cookie, SimpleCookieCls)
                    else cookie.get("value", "")
                )
            except Exception:  # noqa: BLE001
                value = ""
            if name and value:
                entries.append((name, value))
    return entries


class LoginWatcher:
    """后台轮询登录窗口, 捕获 provider 会话 cookie."""

    def __init__(
        self,
        win,
        provider: str,
        on_success: Callable[[str, str, str], None],
        on_cancelled: Optional[Callable[[], None]] = None,
    ):
        self.win = win
        self.provider = provider if provider in (PROVIDER_OPENCODE, PROVIDER_COMMANDCODE) else PROVIDER_OPENCODE
        self.on_success = on_success  # fn(token, workspace_hint, provider)
        self.on_cancelled = on_cancelled
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.done = False

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

    def _target_host(self) -> str:
        return CC_HOST if self.provider == PROVIDER_COMMANDCODE else OPCODE_HOST

    def _target_cookie_name(self) -> str:
        return CC_AUTH_COOKIE_NAME if self.provider == PROVIDER_COMMANDCODE else AUTH_COOKIE_NAME

    def _run(self) -> None:
        _log(f"[login] watcher started provider={self.provider}")
        target_host = self._target_host()
        target_cookie = self._target_cookie_name()
        while not self._stop.is_set():
            # 每轮主动检查窗口存活: macOS 关闭窗口后 get_current_url() 返回 None
            # 而非抛异常, 仅靠异常分支检测会让线程变僵尸 (阻塞单飞守卫, 无法再次登录)
            if not self._window_alive():
                _log("[login] window gone, watcher exits")
                break
            try:
                url = self.win.get_current_url() or ""
            except Exception as exc:  # noqa: BLE001 窗口未加载完成或已销毁
                if not self._window_alive():
                    _log("[login] window closed, watcher exits")
                    break
                self._stop.wait(1.0)
                continue

            if url.startswith("https://" + target_host):
                try:
                    cookies = self.win.get_cookies() or []
                    raw_desc = [str(c) for c in cookies]
                except Exception as exc:  # noqa: BLE001
                    cookies = []
                    raw_desc = [f"<get_cookies ERROR {type(exc).__name__}: {exc}>"]
                _log(f"[login] on {target_host}, url={url[:120]}, cookies={raw_desc}")

                for name, value in _cookie_entries(cookies):
                    if name != target_cookie:
                        continue
                    workspace_hint = "Default"
                    if self.provider == PROVIDER_OPENCODE:
                        match = _WORKSPACE_URL_RE.search(url)
                        workspace_hint = match.group(1) if match else "Default"
                    _log(f"[login] SUCCESS: cookie {name} captured (len={len(value)}), ws={workspace_hint}")
                    self.done = True
                    self._stop.set()
                    token = value
                    if self.provider == PROVIDER_OPENCODE:
                        token = f"auth={value}"
                    else:
                        token = f"{CC_AUTH_COOKIE_NAME}={value}"
                    self.on_success(token, workspace_hint, self.provider)
                    return
            self._stop.wait(COOKIE_POLL_SEC)
        if not self.done and self.on_cancelled:
            self.on_cancelled()
