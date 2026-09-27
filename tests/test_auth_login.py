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


# ── GitHub OAuth 卡死自动续跑 (2FA 登录后 return_to 丢失) ──────────────────


def test_authorize_url_from_mixed_decoded_return_to():
    """复刻打包版实测失败场景: WebView2 返回混合解码形态的入口 URL.

    地址栏里 return_to 路径已解码, 但其中 redirect_uri 仍是双重编码
    (https%253A%252F%252F...); 直接切片不二次解码会生成 GitHub 不认的
    redirect_uri (报 not associated with this application)。
    """
    entry = (
        "https://github.com/login?client_id=Ov23lilNxFR08yhwthpz"
        "&return_to=/login/oauth/authorize?client_id=Ov23lilNxFR08yhwthpz"
        "&code_challenge=CAmwEOrlEO2NgvdoKmAuDeFLxAxfLXaSQfv99-D2tXQ"
        "&code_challenge_method=S256&prompt=select_account"
        "&redirect_uri=https%253A%252F%252Fopencode.ai%252Fconsole%252Fauth%252Fsocial%252Fgithub%252Fcallback"
        "&response_type=code&scope=read%3Auser+user%3Aemail&state=st_flow"
    )
    url = auth._authorize_url_from_entry(entry)
    assert url is not None
    # redirect_uri 必须被解回真实回调地址 (单层编码), GitHub 才能匹配注册回调
    assert "redirect_uri=https%3A%2F%2Fopencode.ai%2Fconsole%2Fauth%2Fsocial%2Fgithub%2Fcallback" in url
    assert "https%253A" not in url  # 不允许残留双重编码
    assert "prompt=select_account" not in url
    assert "client_id=Ov23lilNxFR08yhwthpz" in url
    assert "code_challenge=CAmwEOrlEO2NgvdoKmAuDeFLxAxfLXaSQfv99-D2tXQ" in url
    assert "state=st_flow" in url


def test_normalize_strips_only_malformed_encoding():
    """普通已编码值保持原样, 不会多解一层 (加号/冒号语义不变)."""
    target = (
        "/login/oauth/authorize?client_id=abc"
        "&redirect_uri=https%3A%2F%2Fopencode.ai%2Fcb&scope=read%3Auser+user%3Aemail"
    )
    url = auth._normalize_authorize_target(target)
    assert url is not None
    assert "redirect_uri=https%3A%2F%2Fopencode.ai%2Fcb" in url
    assert "scope=read%3Auser+user%3Aemail" in url


def test_classify_github_oauth_entry():
    """授权入口: github.com/login?client_id=... / authorize?client_id=..."""
    entry = (
        "https://github.com/login?client_id=Ov23lilNxFR08yhwthpz"
        "&return_to=%2Flogin%2Foauth%2Fauthorize%3Fclient_id%3DOv23lilNxFR08yhwthpz"
    )
    assert auth._classify_github_url(entry) == "entry"
    direct = (
        "https://github.com/login/oauth/authorize?client_id=Ov23lilNxFR08yhwthpz"
        "&code_challenge=abc&redirect_uri=https%3A%2F%2Fopencode.ai%2Fcallback"
    )
    assert auth._classify_github_url(direct) == "entry"


def test_classify_github_flow_pages():
    """登录表单/两步验证等流程页不算卡死."""
    for url in (
        "https://github.com/login",
        "https://github.com/login?next=/dashboard",
        "https://github.com/login/oauth/authorize?error=access_denied",
        "https://github.com/sessions/two-factor/app",
        "https://github.com/sessions/two-factor/recovery",
        "https://github.com/sessions/verified-device",
    ):
        assert auth._classify_github_url(url) == "flow", url


def test_classify_github_stuck_pages():
    """2FA 后落在的无关页面 (settings/security 等) 必须识别为 stuck."""
    for url in (
        "https://github.com/settings/security",
        "https://github.com/settings/profile",
        "https://github.com/",
        "https://github.com",
        "https://github.com/dashboard",
    ):
        assert auth._classify_github_url(url) == "stuck", url


def test_classify_github_other_domains():
    assert auth._classify_github_url("https://opencode.ai/console/") is None
    assert auth._classify_github_url("") is None


def test_authorize_url_from_encoded_return_to():
    """复刻实测: github.com/login?...&return_to=<双重编码的 authorize>."""
    entry = (
        "https://github.com/login?client_id=Ov23lilNxFR08yhwthpz"
        "&return_to=%2Flogin%2Foauth%2Fauthorize%3Fclient_id%3DOv23lilNxFR08yhwthpz"
        "%26code_challenge%3D2r5S_XcVYr8tvyeVjxwDjBBJ65GB6U4xi9v3eObkeUY"
        "%26code_challenge_method%3DS256%26prompt%3Dselect_account"
        "%26redirect_uri%3Dhttps%253A%252F%252Fopencode.ai%252Fauth%252Fsocial%252Fgithub%252Fcallback"
        "%26state%3Dst_xxx"
    )
    url = auth._authorize_url_from_entry(entry)
    assert url is not None
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=Ov23lilNxFR08yhwthpz" in url
    assert "code_challenge=2r5S_XcVYr8tvyeVjxwDjBBJ65GB6U4xi9v3eObkeUY" in url
    assert "code_challenge_method=S256" in url
    # redirect_uri/state 需保持编码原样, 便于 GitHub 侧解析
    assert "redirect_uri=https%3A%2F%2Fopencode.ai%2Fauth%2Fsocial%2Fgithub%2Fcallback" in url
    assert "state=st_xxx" in url
    # 已登录续跑不需要账号选择器
    assert "prompt=select_account" not in url


def test_authorize_url_from_raw_return_to():
    """return_to 未编码 (地址栏原样) 时同样可提取."""
    entry = (
        "https://github.com/login?client_id=abc"
        "&return_to=/login/oauth/authorize?client_id=abc&code_challenge=xy&state=st"
    )
    url = auth._authorize_url_from_entry(entry)
    assert url == "https://github.com/login/oauth/authorize?client_id=abc&code_challenge=xy&state=st"


def test_authorize_url_direct_passthrough():
    """入口本身就是 authorize URL: 原样续跑."""
    direct = "https://github.com/login/oauth/authorize?client_id=abc&state=st"
    assert auth._authorize_url_from_entry(direct) == direct


def test_authorize_url_missing_entry():
    assert auth._authorize_url_from_entry("") is None
    assert auth._authorize_url_from_entry("https://github.com/settings/security") is None


def test_github_logged_user_reads_meta():
    class FakeWin:
        def __init__(self, result):
            self._result = result

        def evaluate_js(self, _script):
            return self._result

    assert auth._github_logged_user(FakeWin("octocat")) == "octocat"
    assert auth._github_logged_user(FakeWin("")) == ""
    assert auth._github_logged_user(FakeWin(None)) == ""

    class BrokenWin:
        def evaluate_js(self, _script):
            raise RuntimeError("page gone")

    assert auth._github_logged_user(BrokenWin()) == ""
