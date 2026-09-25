"""登录会话复用缺陷的回归测试.

背景: 登录窗口是复用的 (hide/show), 而 pywebview 只在 create_window 时清理
网站数据, 于是 cookie store 里留着上一轮/上一账号的会话. 旧实现只校验
"目标 cookie 存在", 结果把这份残留凭证当成本次登录成功: 窗口在用户完成
授权前就关掉, 凭证被原样存回 (界面表现为"闪退 + 登录状态没刷新").

这里锁定修复后的语义: 只有"登录前不存在的凭证"才算登录成功.
"""
from __future__ import annotations

import json
import time

import pytest

from app import auth, db, server
from app.auth import (
    CC_AUTH_COOKIE_NAME,
    LoginWatcher,
    build_token,
    token_fingerprint,
)

OLD_CC = "cUZ3munSEBkvnE0yce8rwTH2Kq7Th1i7.OLDSESSION"
NEW_CC = "cUZ3munSEBkvnE0yce8rwTH2Kq7Th1i7.NEWSESSION"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


@pytest.fixture()
def fast_poll(monkeypatch):
    """把 1s 轮询压到 20ms, 让用例按秒计而不是按分钟计."""
    monkeypatch.setattr(auth, "COOKIE_POLL_SEC", 0.02)


class FakeWin:
    """最小窗口替身: LoginWatcher 只用 get_current_url / get_cookies."""

    def __init__(self, url: str = "https://commandcode.ai/signin", cookies=None):
        self.url = url
        self.cookies = list(cookies or [])

    def get_current_url(self):
        return self.url

    def get_cookies(self):
        return list(self.cookies)


def _wait_until(pred, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return bool(pred())


def _start(monkeypatch, win, provider="commandcode", **kwargs) -> LoginWatcher:
    monkeypatch.setattr(auth.webview, "windows", [win])
    return LoginWatcher(win, provider, **kwargs)


# ---------------------------------------------------------------------------
# 残留会话不得被判为登录成功
# ---------------------------------------------------------------------------


def test_existing_cookie_at_start_is_not_a_login(monkeypatch, fast_poll):
    """打开登录窗口时 store 里已有的凭证 = 残留会话, 必须等新凭证."""
    win = FakeWin(cookies=[{"name": CC_AUTH_COOKIE_NAME, "value": OLD_CC}])
    # 打开窗口瞬间的基线由 main 采集并传入 (此时 store 里是上一轮的失效凭证)
    baseline = auth.read_provider_cookie(win, "commandcode")
    assert baseline == OLD_CC

    seen: list[tuple] = []
    w = _start(
        monkeypatch, win,
        on_success=lambda *a: seen.append(a),
        baseline_value=baseline,
    )
    w.start()
    try:
        time.sleep(0.15)  # 若干轮轮询
        assert seen == [], "残留会话被误判为登录成功"

        win.cookies = [{"name": CC_AUTH_COOKIE_NAME, "value": NEW_CC}]
        assert _wait_until(lambda: bool(seen)), "新凭证未被捕获"
        assert seen[0][0] == f"{CC_AUTH_COOKIE_NAME}={NEW_CC}"
        assert seen[0][2] == "commandcode"
        assert w.done is True
    finally:
        w.stop()


def test_db_known_credential_is_rejected_even_without_baseline(monkeypatch, fast_poll):
    """baseline 采集不到时 (窗口未就绪), 库内旧凭证指纹仍要拦住残留会话."""
    win = FakeWin(url="https://opencode.ai/workspace/wrk_abc123", cookies=[])
    seen: list[tuple] = []
    w = _start(
        monkeypatch, win, provider="opencode",
        on_success=lambda *a: seen.append(a),
        stale_fps=[token_fingerprint("auth=OLDSESSION")],
    )
    w.start()
    try:
        win.cookies = [{"name": "auth", "value": "OLDSESSION"}]
        time.sleep(0.15)
        assert seen == [], "库内已知旧凭证被误判为登录成功"

        win.cookies = [{"name": "auth", "value": "FRESHSESSION"}]
        assert _wait_until(lambda: bool(seen)), "新凭证未被捕获"
        assert seen[0][0] == "auth=FRESHSESSION"
        assert seen[0][1] == "wrk_abc123"  # workspace 提示仍从 URL 提取
        assert seen[0][2] == "opencode"
    finally:
        w.stop()


def test_fresh_login_still_succeeds(monkeypatch, fast_poll):
    """无残留时正常登录流程不受影响 (防止修复把登录整个拦死)."""
    win = FakeWin(cookies=[])
    seen: list[tuple] = []
    w = _start(monkeypatch, win, on_success=lambda *a: seen.append(a))
    w.start()
    try:
        win.cookies = [{"name": CC_AUTH_COOKIE_NAME, "value": NEW_CC}]
        assert _wait_until(lambda: bool(seen))
        assert seen[0][0] == f"{CC_AUTH_COOKIE_NAME}={NEW_CC}"
    finally:
        w.stop()


def test_window_closed_triggers_cancelled(monkeypatch, fast_poll):
    """窗口被关掉仍要回调 on_cancelled (单飞守卫依赖它释放)."""
    win = FakeWin(cookies=[])
    windows: list = []
    monkeypatch.setattr(auth.webview, "windows", windows)
    cancelled: list[int] = []
    w = LoginWatcher(
        win, "commandcode", lambda *a: None,
        on_cancelled=lambda: cancelled.append(1),
    )
    # _window_alive 用 `win in webview.windows` 判定: 先入列表再启动
    windows.append(win)
    w.start()
    try:
        windows.clear()
        assert _wait_until(lambda: bool(cancelled)), "窗口消失未触发 on_cancelled"
        assert w.done is False
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# 凭证形态与域匹配
# ---------------------------------------------------------------------------


def test_build_token_matches_db_form():
    assert build_token("commandcode", "RAW") == f"{CC_AUTH_COOKIE_NAME}=RAW"
    assert build_token("opencode", "RAW") == "auth=RAW"


@pytest.mark.parametrize(
    "domain,host,expected",
    [
        ("commandcode.ai", "commandcode.ai", True),
        (".commandcode.ai", "commandcode.ai", True),
        ("api.commandcode.ai", "commandcode.ai", True),
        ("opencode.ai", "commandcode.ai", False),
        ("notcommandcode.ai", "commandcode.ai", False),
        ("", "commandcode.ai", False),
    ],
)
def test_domain_matches(domain, host, expected):
    assert auth._domain_matches(domain, host) is expected


def test_clear_provider_cookies_safe_on_main_thread(monkeypatch):
    """主线程调用必须立即返回 (与 callAfter 互锁会挂死登录入口)."""
    monkeypatch.setattr(auth.sys, "platform", "darwin")
    started = time.time()
    assert auth.clear_provider_cookies("commandcode") == 0
    assert time.time() - started < 1.0


def test_clear_provider_cookies_skips_non_macos(monkeypatch):
    monkeypatch.setattr(auth.sys, "platform", "win32")
    assert auth.clear_provider_cookies("opencode") == 0


# ---------------------------------------------------------------------------
# 登录页请求拦截 (白屏修复)
# ---------------------------------------------------------------------------


def test_login_block_rules_shape_and_scope():
    """规则要拦住不可达的追踪域, 且不能误伤登录必需域."""
    rules = json.loads(auth.login_block_rules_json())
    assert isinstance(rules, list) and len(rules) == len(auth.LOGIN_BLOCKED_HOSTS)
    domains: list[str] = []
    for rule in rules:
        assert rule["action"] == {"type": "block"}
        assert rule["trigger"]["url-filter"] == ".*"
        domains.extend(rule["trigger"]["if-domain"])
    # 每个域都要覆盖子域 (WKContentRuleList 语法: 前缀 * 表示该域及其子域)
    assert "connect.facebook.net" in domains
    assert "*connect.facebook.net" in domains
    assert "static.cloudflareinsights.com" in domains
    assert "*static.cloudflareinsights.com" in domains
    # 登录必需域必须放行: 授权跳转、人机验证、业务 API
    for host in domains:
        bare = host.lstrip("*")
        assert bare not in ("commandcode.ai", "api.commandcode.ai", "github.com")
        assert "challenges.cloudflare.com" not in bare
        assert not bare.endswith(".commandcode.ai")


def test_install_login_network_rules_safe_on_main_thread(monkeypatch):
    """主线程调用立即返回 (与 callAfter 互锁会挂死登录入口)."""
    monkeypatch.setattr(auth.sys, "platform", "darwin")
    started = time.time()
    assert auth.install_login_network_rules(object()) is False
    assert time.time() - started < 1.0


def test_install_login_network_rules_skips_non_macos(monkeypatch):
    monkeypatch.setattr(auth.sys, "platform", "win32")
    assert auth.install_login_network_rules(object()) is False


def test_wait_window_view_returns_none_for_unknown_window(monkeypatch):
    """窗口查不到时必须按时返回 None, 不能无限轮询拖死登录流程."""
    monkeypatch.setattr(auth.sys, "platform", "darwin")
    started = time.time()
    assert auth.wait_window_view(object(), timeout=0.3) is None
    assert time.time() - started < 2.0


class _FakeWindow:
    def __init__(self, explode: bool = False):
        self.calls: list = []
        self.explode = explode

    def load_html(self, html, base):
        if self.explode:
            raise RuntimeError("window gone")
        self.calls.append((html, base))
        return True


def test_boot_page_is_self_contained():
    """引导页必须纯本地: 它要赶在首次合成之前渲染, 不能依赖任何网络资源."""
    html = auth._LOGIN_BOOT_HTML
    assert "<html" in html.lower()
    assert "http://" not in html and "https://" not in html
    assert "登录页" in html
    assert auth.BOOT_SETTLE_SEC > 0


def test_render_boot_page_loads_local_html():
    win = _FakeWindow()
    assert auth.render_login_boot_page(win) is True
    assert win.calls and "登录页" in win.calls[0][0]


def test_render_boot_page_survives_closed_window():
    """窗口被用户关掉时不能抛出去打断登录流程."""
    assert auth.render_login_boot_page(_FakeWindow(explode=True)) is False


def test_load_state_helpers_safe_off_darwin(monkeypatch):
    monkeypatch.setattr(auth.sys, "platform", "win32")
    assert auth.page_load_state(object()) is None
    assert auth.reload_window(object()) is False


def test_load_watchdog_safe_on_main_thread(monkeypatch):
    """主线程调用不得发 native 请求 (会与 callAfter 互锁), 到点即返回."""
    monkeypatch.setattr(auth.sys, "platform", "darwin")
    started = time.time()
    assert auth.ensure_login_page_loaded(object(), stall_sec=0.1, total_sec=0.3) is False
    assert time.time() - started < 4.0


# ---------------------------------------------------------------------------
# 凭证指纹查询与配额缓存失效
# ---------------------------------------------------------------------------


def test_list_provider_token_fps_is_provider_scoped(tmp_db):
    db.add_account("auth=AAA", "ws", provider="opencode")
    db.add_account(f"{CC_AUTH_COOKIE_NAME}=BBB", provider="commandcode")
    assert db.list_provider_token_fps("commandcode") == [
        db._token_fp(f"{CC_AUTH_COOKIE_NAME}=BBB")
    ]
    assert db.list_provider_token_fps("opencode") == [db._token_fp("auth=AAA")]
    assert db.list_provider_token_fps("commandcode") != db.list_provider_token_fps("opencode")


def test_invalidate_quota_cache_drops_slot_and_unblocks_refresh():
    server._quota_cache.clear()
    server._quota_refreshing.clear()
    server._quota_cache[7] = {"at": time.time(), "data": {"success": False}}
    server._quota_refreshing.add(7)
    server.invalidate_quota_cache(7)
    assert 7 not in server._quota_cache
    # 不放行会让 _ensure_quota_async 认定"已有线程在跑", 重新登录后永不重拉
    assert 7 not in server._quota_refreshing


class _FakeQuota:
    def to_dict(self):
        return {"success": True, "windows": []}


def test_quota_result_fetched_with_old_credentials_is_not_cached(monkeypatch):
    """拉取途中凭证被更换: 旧结果不能落进新槽 (否则 TTL 内一直显示旧配额)."""
    server._quota_cache.clear()
    server._quota_refreshing.clear()

    def fake_fetch(token, workspace_hint):
        server.invalidate_quota_cache(7)  # 模拟 relogin 发生在拉取期间
        return _FakeQuota()

    monkeypatch.setattr(server, "fetch_quota", fake_fetch)
    data = server._fetch_quota_with_cache(7, "old-token", "Default", "opencode")
    assert data["success"] is True  # 调用方仍拿到本次结果
    assert 7 not in server._quota_cache  # 但不会污染新凭证的缓存槽
