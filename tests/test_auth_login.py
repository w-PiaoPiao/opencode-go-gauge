"""登录监听逻辑测试: 会话 Cookie 挑选 / 工作区提取 / 登录 URL.

auth.py 顶层 import webview (仅打包环境可用), 这里先用空模块占位再导入,
被测函数本身不触碰窗口对象。
"""
from __future__ import annotations

import sys
import types
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

sys.modules.setdefault("webview", types.ModuleType("webview"))

from app import auth  # noqa: E402


def _pywebview_cookie(name: str, value: str) -> SimpleCookie:
    """复刻 pywebview create_cookie 的返回形状 (SimpleCookie 子类)."""
    cookie = SimpleCookie()
    cookie[name] = value
    return cookie


def test_build_login_url_points_to_console():
    url = auth.build_login_url()
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "opencode.ai"
    assert parsed.path == "/console/login"
    assert parse_qs(parsed.query)["next"] == ["/console/"]


def test_pick_console_session_cookie():
    cookies = [
        _pywebview_cookie("__stripe_mid", "845f8920-d140"),
        _pywebview_cookie("__stripe_sid", "6ba0b689-8f51"),
        _pywebview_cookie("__Host-console_session", "st_0019e474-167f"),
    ]
    assert auth._pick_session_cookie(cookies) == (
        "__Host-console_session", "st_0019e474-167f",
    )


def test_pick_prefers_console_session_over_legacy_auth():
    cookies = [
        _pywebview_cookie("auth", "Fe26.2**legacy"),
        _pywebview_cookie("__Host-console_session", "st_new"),
    ]
    assert auth._pick_session_cookie(cookies)[0] == "__Host-console_session"


def test_pick_legacy_auth_cookie_as_fallback():
    """旧账号 token 仍是 auth=... 时, 登录监听也要能接手."""
    cookies = [_pywebview_cookie("auth", "Fe26.2**legacy")]
    assert auth._pick_session_cookie(cookies) == ("auth", "Fe26.2**legacy")


def test_pick_ignores_unrelated_and_empty():
    assert auth._pick_session_cookie([]) is None
    assert auth._pick_session_cookie(None) is None
    assert auth._pick_session_cookie([_pywebview_cookie("foo", "bar")]) is None
    assert auth._pick_session_cookie(
        [_pywebview_cookie("__Host-console_session", "   ")]
    ) is None


def test_pick_handles_dict_style_cookies():
    """兼容 pywebview 某些平台返回的 dict 形状."""
    cookies = [{"name": "__Host-console_session", "value": "st_dict"}]
    assert auth._pick_session_cookie(cookies) == ("__Host-console_session", "st_dict")


def test_workspace_hint_from_console_url():
    wid = "wrk_01KXDVHZMY578NZ300DTR7WYE8"
    for url in (
        f"https://opencode.ai/console/{wid}/go",
        f"https://opencode.ai/console/{wid}",
    ):
        match = auth._WORKSPACE_URL_RE.search(url)
        assert match and match.group(1) == wid


def test_workspace_hint_from_legacy_url():
    wid = "wrk_01KXABCDEF"
    match = auth._WORKSPACE_URL_RE.search(f"https://opencode.ai/workspace/{wid}/usage")
    assert match and match.group(1) == wid


def test_workspace_hint_absent_on_login_page():
    assert auth._WORKSPACE_URL_RE.search("https://opencode.ai/console/login") is None
    assert auth._WORKSPACE_URL_RE.search("https://opencode.ai/console/") is None
