"""Windows 平台 (WebView2) 登录流程的回归测试.

背景: macOS 已修掉"重新登录跳转后台 + 窗口秒关"的一整套缺陷, 但那些实现
最初全部限定在 darwin —— ``clear_provider_cookies`` 在其它平台直接 return 0,
于是 Windows 上残留会话照旧: 复用的登录窗口里还留着上一轮的 commandcode
会话 cookie, 登录页带着它请求、被服务端直接 302 到 commandcode.ai 主页
(无法重新选择账号), LoginWatcher 的残留会话基线也采集不到 (pywebview 的
get_cookies 在 WebView2 上用 self.url 作 GetCookiesAsync 的入参, 窗口刚渲染
过引导页时该值为 None, .NET 抛异常后无超时信号量不再释放, 调用线程永久挂起).

这里锁定 Windows 侧的等价实现:
- 按 provider 域读写 WebView2 cookie (CookieManager, 不碰其它域);
- 登录页加载状态用 document.readyState + Source 判定 (WebView2 没有
  estimatedProgress/IsLoading);
- 所有 native 调用都必须带超时/可降级, 且不在 UI 线程上等 .NET Task
  (会与 UI 线程互锁).
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from app import auth


# ---------------------------------------------------------------------------
# WebView2 替身 (非 Windows 环境没有 pythonnet/WebView2, 按鸭子类型模拟)
# ---------------------------------------------------------------------------


class _FakeCookie:
    def __init__(self, name: str, value: str, domain: str) -> None:
        self.Name = name
        self.Value = value
        self.Domain = domain


class _FakeTask:
    """模拟 .NET Task[String]/Task[List[Cookie]] (本进程内立即可用)."""

    def __init__(self, result) -> None:
        self._result = result

    def Wait(self, timeout_ms: int) -> bool:
        return True

    @property
    def Result(self):
        return self._result


class _FakeCookieManager:
    def __init__(self, cookies: list) -> None:
        self.cookies = list(cookies)
        self.deleted: list = []
        self.uris: list[str] = []
        self.delete_all_calls = 0

    def GetCookiesAsync(self, uri: str) -> _FakeTask:
        self.uris.append(uri)
        return _FakeTask(list(self.cookies))

    def DeleteAllCookies(self) -> None:
        self.delete_all_calls += 1
        self.cookies = []

    def DeleteCookie(self, cookie) -> None:
        self.deleted.append(cookie)
        self.cookies = [c for c in self.cookies if c is not cookie]


class _FakeCore:
    def __init__(self, cm: _FakeCookieManager, source: str = "https://commandcode.ai/signin") -> None:
        self.CookieManager = cm
        self.Source = source
        self.ready = "complete"
        self.scripts: list[str] = []
        self.reloads = 0
        self.navigations: list[str] = []

    def ExecuteScriptAsync(self, script: str) -> _FakeTask:
        self.scripts.append(script)
        return _FakeTask(json.dumps(self.ready))

    def Reload(self) -> None:
        self.reloads += 1

    def Navigate(self, url: str) -> None:
        self.navigations.append(url)
        self.Source = url


class _FakeForm:
    """模拟 pywebview 的 BrowserForm: 既是 WinForms 控件 (Invoke/InvokeRequired),
    又挂着 browser (EdgeChrome) -> webview (WebView2 控件) -> CoreWebView2.

    browser.url 对应 EdgeChrome 自己跟踪的当前 URL —— Windows 侧读它判断
    "登录页是否被残留会话带离了登录入口".
    """

    def __init__(
        self,
        core: _FakeCore | None,
        invoke_required: bool = True,
        url: str = "https://commandcode.ai/signin",
    ) -> None:
        self.InvokeRequired = invoke_required
        self.invocations = 0
        self.browser = SimpleNamespace(webview=SimpleNamespace(CoreWebView2=core), url=url)

    def Invoke(self, delegate) -> None:
        self.invocations += 1
        delegate()


class _FakeWin:
    """最小 pywebview 窗口替身: native 即 BrowserForm (与真实结构一致)."""

    def __init__(
        self,
        core: _FakeCore | None = None,
        invoke_required: bool = True,
        url: str = "https://commandcode.ai/signin",
    ) -> None:
        self.native = _FakeForm(core, invoke_required=invoke_required, url=url)

    @property
    def control(self) -> _FakeForm:
        return self.native

    @property
    def url(self) -> str:
        return self.native.browser.url

    @url.setter
    def url(self, value: str) -> None:
        self.native.browser.url = value

    def get_current_url(self):
        return self.url

    def get_cookies(self):
        raise AssertionError("Windows 分支不得回落到 pywebview 的 get_cookies (会挂死)")


def _wait_until(pred, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return bool(pred())


@pytest.fixture()
def win_platform(monkeypatch):
    """切到 win32, 并把 Control.Invoke 的 .NET delegate 包装降级为直调.

    其余逻辑 (域过滤 / 超时预算 / UI 线程规避 / 降级路径) 全部走真实实现.
    """
    monkeypatch.setattr(auth.sys, "platform", "win32")
    monkeypatch.setattr(auth, "_win_ui_delegate", lambda fn: fn)
    monkeypatch.setattr(auth.webview, "windows", [])
    return monkeypatch


# ---------------------------------------------------------------------------
# 按域清残留会话 (跳转主页的直接原因)
# ---------------------------------------------------------------------------


def test_win_purge_clears_store_via_delete_all_and_verifies(win_platform):
    """Windows 清残留会话 = DeleteAllCookies (profile 级) + 回读验证.

    刻意不走"GetCookiesAsync -> Task -> 逐条 DeleteCookie": 那条链路真机上
    任何一环失败都是静默跳过 (实测残留会话仍在, 登录页被带到官网).
    """
    cm = _FakeCookieManager([
        _FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", ".commandcode.ai"),
        _FakeCookie("other", "KEEP", "example.com"),
    ])
    win = _FakeWin(_FakeCore(cm))

    removed = auth.clear_provider_cookies("commandcode", win)

    assert removed == 1, "应报告清掉的 provider 域会话条数"
    assert cm.delete_all_calls == 1, "必须走 DeleteAllCookies"
    assert cm.cookies == [], "store 必须真的空了"
    assert cm.deleted == [], "不再依赖逐条 DeleteCookie"
    assert cm.uris == ["https://commandcode.ai/"] * 2, "清前/清后回读都要带有效 URL"


def test_win_purge_reports_zero_when_verification_still_sees_session(win_platform):
    """清完回读仍有残留 (页面 JS 续写等) 必须如实报 0, 不能谎报已清."""

    class _StubbornCM(_FakeCookieManager):
        def DeleteAllCookies(self) -> None:
            self.delete_all_calls += 1  # 假装清了, 但 cookie 还在

    cm = _StubbornCM([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", "commandcode.ai")])
    win = _FakeWin(_FakeCore(cm))

    assert auth.clear_provider_cookies("commandcode", win) == 0
    assert cm.cookies, "残留仍在时不得假装成功"


def test_win_read_distinguishes_empty_from_unavailable(win_platform):
    """空列表 = 确实没有残留; None = 读不到 —— 验证逻辑必须能区分."""
    win = _FakeWin(_FakeCore(_FakeCookieManager([])))
    assert auth._win_read_provider_cookies(win, "commandcode.ai", "auth", 1.0) == []

    no_core = _FakeWin(None)
    assert auth._win_read_provider_cookies(no_core, "commandcode.ai", "auth", 1.0) is None


def test_win_purge_skips_when_no_window_and_none_alive(win_platform):
    """窗口已销毁且无其它存活窗口时安全返回 0 (由指纹比对兜底)."""
    assert auth.clear_provider_cookies("opencode", None) == 0


def test_win_purge_never_runs_on_ui_thread(win_platform):
    """已在 UI 线程时必须放弃: 上层要在调用线程等 .NET Task, 会互锁."""
    cm = _FakeCookieManager([_FakeCookie("auth", "STALE", "opencode.ai")])
    win = _FakeWin(_FakeCore(cm), invoke_required=False)

    assert auth.clear_provider_cookies("opencode", win) == 0
    assert cm.delete_all_calls == 0
    assert win.control.invocations == 0


def test_win_purge_falls_back_to_any_alive_window(win_platform):
    """登录窗口刚重建 (WebView2 未就绪) 时借其它窗口的 store —— 进程内共享."""
    cm = _FakeCookieManager([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", "commandcode.ai")])
    dead = _FakeWin(None)  # 新窗口: CoreWebView2 还是 None
    alive = _FakeWin(_FakeCore(cm))
    win_platform.setattr(auth.webview, "windows", [alive])

    assert auth.clear_provider_cookies("commandcode", dead) == 1
    assert cm.delete_all_calls == 1


# ---------------------------------------------------------------------------
# 残留会话基线读取 (LoginWatcher 的 stale 比对输入)
# ---------------------------------------------------------------------------


def test_win_read_baseline_returns_first_matching_value(win_platform):
    cm = _FakeCookieManager([
        _FakeCookie("unrelated", "x", "commandcode.ai"),
        _FakeCookie(auth.CC_AUTH_COOKIE_NAME, "OLDSESSION", "commandcode.ai"),
        _FakeCookie(auth.CC_AUTH_COOKIE_NAME, "ANOTHER", "commandcode.ai"),
    ])
    win = _FakeWin(_FakeCore(cm))

    assert auth.read_provider_cookie(win, "commandcode") == "OLDSESSION"


def test_win_read_baseline_none_when_store_empty(win_platform):
    win = _FakeWin(_FakeCore(_FakeCookieManager([])))
    assert auth.read_provider_cookie(win, "commandcode") is None


def test_win_read_baseline_none_without_webview2(win_platform):
    """窗口/WebView2 未就绪时返回 None, 让库内旧凭证指纹继续兜底."""
    assert auth.read_provider_cookie(_FakeWin(None), "opencode") is None


def test_win_baseline_feeds_stale_detection(win_platform, monkeypatch):
    """基线采到的残留凭证必须能让 LoginWatcher 判为 stale (闭环)."""
    cm = _FakeCookieManager([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "OLDSESSION", "commandcode.ai")])
    win = _FakeWin(_FakeCore(cm))
    baseline = auth.read_provider_cookie(win, "commandcode")
    watcher = auth.LoginWatcher(win, "commandcode", lambda *a: None, baseline_value=baseline)
    assert watcher._is_stale("OLDSESSION") is True
    assert watcher._is_stale("FRESHSESSION") is False


def test_win_purge_still_clears_when_verification_unavailable(win_platform):
    """回读验证不可用不影响清理本身: DeleteAllCookies 是 profile 级操作.

    真机上"读得到但删不掉"和"读不到"是两种不同的失败: 前者要如实上报,
    后者不能因为验证手段不可用就放弃清理 (或谎报失败).
    """

    class _OnceReadableCM(_FakeCookieManager):
        def __init__(self, cookies: list) -> None:
            super().__init__(cookies)
            self.reads = 0

        def GetCookiesAsync(self, uri: str):
            self.reads += 1
            if self.reads > 1:  # 清前可读, 清后回读不可用
                raise RuntimeError("verification unavailable")
            return super().GetCookiesAsync(uri)

    cm = _OnceReadableCM([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", "commandcode.ai")])
    win = _FakeWin(_FakeCore(cm))

    assert auth.clear_provider_cookies("commandcode", win) == 1
    assert cm.delete_all_calls == 1
    assert cm.cookies == []


def test_win_watcher_falls_back_to_pywebview_when_read_unavailable(win_platform, monkeypatch):
    """自带读取不可用时监听线程必须回退到 pywebview 的 get_cookies.

    读取是"登录能否被识别"的唯一通道 —— 宁可走备选通道, 也不能永远读不到
    凭证 (登录窗会一直不关).
    """
    monkeypatch.setattr(auth, "COOKIE_POLL_SEC", 0.02)
    win = _FakeWin(None)  # 无 CoreWebView2 → 自带按域读取返回 None
    win.get_cookies = lambda: [{"name": auth.CC_AUTH_COOKIE_NAME, "value": "FRESHSESSION"}]
    win_platform.setattr(auth.webview, "windows", [win])

    seen: list[tuple] = []
    watcher = auth.LoginWatcher(win, "commandcode", lambda *a: seen.append(a))
    watcher.start()
    try:
        assert _wait_until(lambda: bool(seen)), "回退通道拿到的凭证未被识别"
        assert seen[0][0] == f"{auth.CC_AUTH_COOKIE_NAME}=FRESHSESSION"
        assert watcher.done is True
    finally:
        watcher.stop()


def test_win_watcher_reads_cookies_without_pywebview(win_platform, monkeypatch):
    """Windows 上监听线程必须走带超时的 WebView2 读取, 且保留残留会话判定.

    pywebview 的 get_cookies 在 WebView2 上可能永久挂起 (无超时信号量 + 导航
    竞态下 GetCookiesAsync 收到 null URL), 监听线程一挂, 单飞守卫就再也不释放.
    """
    monkeypatch.setattr(auth, "COOKIE_POLL_SEC", 0.02)
    cm = _FakeCookieManager([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "OLDSESSION", "commandcode.ai")])
    win = _FakeWin(_FakeCore(cm))
    win_platform.setattr(auth.webview, "windows", [win])

    seen: list[tuple] = []
    watcher = auth.LoginWatcher(
        win, "commandcode", lambda *a: seen.append(a),
        stale_fps=[auth.token_fingerprint(auth.build_token("commandcode", "OLDSESSION"))],
    )
    watcher.start()
    try:
        time.sleep(0.2)
        assert seen == [], "残留会话被误判为登录成功"

        cm.cookies = [_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "FRESHSESSION", "commandcode.ai")]
        assert _wait_until(lambda: bool(seen)), "新凭证未被捕获"
        assert seen[0][0] == f"{auth.CC_AUTH_COOKIE_NAME}=FRESHSESSION"
        assert seen[0][2] == "commandcode"
        assert watcher.done is True
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# 登录页加载看门狗 (WebView2: readyState + Source)
# ---------------------------------------------------------------------------


def test_win_load_state_complete_on_provider_page(win_platform):
    core = _FakeCore(_FakeCookieManager([]), source="https://commandcode.ai/signin")
    core.ready = "complete"
    assert auth.page_load_state(_FakeWin(core)) == {"progress": 1.0, "loading": False}


def test_win_load_state_loading_while_interactive(win_platform):
    core = _FakeCore(_FakeCookieManager([]), source="https://commandcode.ai/signin")
    core.ready = "interactive"
    assert auth.page_load_state(_FakeWin(core)) == {"progress": 0.0, "loading": True}


def test_win_load_state_treats_boot_page_as_loading(win_platform):
    """引导页 (about:blank) 即使 readyState=complete 也不能算登录页加载完成."""
    core = _FakeCore(_FakeCookieManager([]), source="about:blank")
    core.ready = "complete"
    assert auth.page_load_state(_FakeWin(core))["loading"] is True


def test_win_load_state_none_without_webview2(win_platform):
    assert auth.page_load_state(_FakeWin(None)) is None


def test_win_reload_calls_webview2_reload(win_platform):
    core = _FakeCore(_FakeCookieManager([]))
    assert auth.reload_window(_FakeWin(core)) is True
    assert core.reloads == 1


def test_win_reload_safe_without_webview2(win_platform):
    assert auth.reload_window(_FakeWin(None)) is False


def test_win_page_ops_never_borrow_another_window(win_platform):
    """页面状态类操作必须用窗口自己的实例.

    cookie 可以借 (store 进程内共享), 但 readyState/reload 借来的实例读到的是
    另一个窗口的页面 —— 必须退化为"读不到"而不是拿错数据.
    """
    other = _FakeWin(_FakeCore(_FakeCookieManager([]), source="https://commandcode.ai/"))
    win_platform.setattr(auth.webview, "windows", [other])
    fresh = _FakeWin(None)  # 登录窗口的 WebView2 还在异步初始化

    assert auth.page_load_state(fresh) is None
    assert auth.reload_window(fresh) is False
    assert auth.page_snapshot(fresh) is None
    assert other.native.invocations == 0, "不得把主窗口面板的状态当成登录页的"


def test_win_watchdog_gives_up_when_state_unavailable(win_platform, monkeypatch):
    """连续读不到加载状态时必须提前放弃, 不再空转到总超时 (45s)."""
    monkeypatch.setattr(auth, "page_load_state", lambda win: None)
    started = time.time()
    loaded = auth.ensure_login_page_loaded(_FakeWin(None), stall_sec=0.1, total_sec=45.0)
    assert loaded is False
    assert time.time() - started < 10.0


def test_win_snapshot_reads_page_state(win_platform):
    core = _FakeCore(_FakeCookieManager([]), source="https://commandcode.ai/signin")
    core.ready = "complete"
    snapshot = auth.page_snapshot(_FakeWin(core))
    assert snapshot == "complete"  # ExecuteScriptAsync 的 JSON 字符串被解码
    assert core.scripts, "快照脚本必须真的下发到页面"


# ---------------------------------------------------------------------------
# 残留会话把登录页带离入口 (commandcode 停在官网/控制台)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://commandcode.ai/signin", False),
        ("https://commandcode.ai/signin?next=%2F", False),
        ("https://commandcode.ai/", True),
        ("https://commandcode.ai/dashboard", True),
        ("https://github.com/login?client_id=x", False),  # 授权流程在别的域
        # OAuth 成功回调 (带 code=): 服务端正要据此种会话, 不得判偏离清会话
        ("https://commandcode.ai/api/auth/callback/github?code=abc&state=st", False),
        # 失败回调 (error= 不带 code=): 清会话拉回登录页正是期望行为
        ("https://commandcode.ai/auth/github?error=access_denied", True),
        ("about:blank", False),
        ("", False),
    ],
)
def test_login_entry_lost_flags_only_commandcode_off_entry(win_platform, url, expected):
    win = _FakeWin(_FakeCore(_FakeCookieManager([])), url=url)
    assert auth.login_entry_lost(win, "commandcode") is expected


def test_login_entry_lost_ignores_other_providers(win_platform):
    """opencode 的 OAuth 会合法地跨域跨路径, 不做判定 (避免误清刚建立的会话)."""
    win = _FakeWin(_FakeCore(_FakeCookieManager([])), url="https://opencode.ai/workspace/wrk_1")
    assert auth.login_entry_lost(win, "opencode") is False


def test_reset_login_session_purges_and_reloads_entry(win_platform):
    """被带到官网/控制台时: 先驶离旧页 (终止其 JS) → 清 store → 清页面存储 → 回登录入口."""
    cm = _FakeCookieManager([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", "commandcode.ai")])
    core = _FakeCore(cm)
    win = _FakeWin(core, url="https://commandcode.ai/")

    assert auth.reset_login_session(win, "commandcode") is True
    assert cm.delete_all_calls == 1
    # about:blank 先行: 终止旧页面 JS, 防其定时请求把会话 cookie 续写回来
    assert core.navigations == ["about:blank", auth.build_login_url("commandcode")]
    scripts = win.control.browser.webview.CoreWebView2.scripts
    assert any("localStorage.clear" in s for s in scripts), (
        "还要清 localStorage/sessionStorage —— 控制台可能据此在客户端直接跳后台"
    )


def test_reset_login_session_noop_when_still_on_entry(win_platform):
    cm = _FakeCookieManager([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", "commandcode.ai")])
    core = _FakeCore(cm)
    win = _FakeWin(core, url="https://commandcode.ai/signin")

    assert auth.reset_login_session(win, "commandcode") is False
    assert cm.delete_all_calls == 0, "仍在登录入口时不得清会话"
    assert core.navigations == [], "仍在登录入口时不得导航"


def _drift_watcher(cm, core, win, monkeypatch):
    """起一个 commandcode watcher: 旧凭证指纹命中 STALE, 窗口被带离 /signin."""
    monkeypatch.setattr(auth, "COOKIE_POLL_SEC", 0.02)
    monkeypatch.setattr(auth.webview, "windows", [win])  # 窗口存活判定用
    w = auth.LoginWatcher(
        win, "commandcode",
        lambda token, ws, provider: None,
        stale_fps=[auth.token_fingerprint(auth.build_token("commandcode", "STALE"))],
    )
    w.start()
    return w


def test_watcher_pulls_back_when_off_signin_entry(win_platform, monkeypatch):
    """回归: 客户端路由把窗口带到官网后, 监听器持续拉回登录入口.

    _arm 侧自愈只覆盖"页面加载完成时"的快照判定, 客户端路由慢跳 (登录页
    加载完成后 JS 才跳官网) 会错过 —— 此前窗口从此停在官网, 监听器在原地
    永远等新凭证, 表现为"打开官网后卡住".
    """
    cm = _FakeCookieManager([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", "commandcode.ai")])
    core = _FakeCore(cm, source="https://commandcode.ai/")
    win = _FakeWin(core, url="https://commandcode.ai/")
    w = _drift_watcher(cm, core, win, monkeypatch)
    try:
        # reset 是"驶离旧页 → 清 cookie → 清页面存储 → 回登录入口"的多步序列,
        # 跑在监听线程上. 必须等整条走完 (最后一步落地) 再断言中间步骤 —— 观察到
        # 前一步就断言后一步"已经发生"是竞态, 全量跑负载高时随机失败.
        # 预算给整个序列 (单步各自带 COOKIE_PURGE_TIMEOUT, 逐步叠加).
        ok = _wait_until(
            lambda: auth.build_login_url("commandcode") in core.navigations, timeout=5.0
        )
        assert ok, f"watcher 应重置会话并拉回登录入口: {core.navigations}"
        assert cm.delete_all_calls >= 1, "重置应清掉残留会话 cookie"
        assert core.navigations[0] == "about:blank", "先驶离旧页终止其 JS 再清 cookie"
        assert w._entry_resets >= 1
        assert not w.done, "旧凭证不算登录成功, 监听继续等真正的新凭证"
    finally:
        w.stop()


def test_watcher_entry_reset_is_rate_limited(win_platform, monkeypatch):
    """自愈限流: 一次 reset 后的间隔窗口内不重复清会话 (防与 arm 侧自愈打环)."""
    cm = _FakeCookieManager([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", "commandcode.ai")])
    core = _FakeCore(cm, source="https://commandcode.ai/")
    win = _FakeWin(core, url="https://commandcode.ai/")
    w = _drift_watcher(cm, core, win, monkeypatch)
    try:
        assert _wait_until(lambda: w._entry_resets >= 1)
        time.sleep(0.12)  # 若干轮轮询过去 (间隔远小于 _ENTRY_RESET_INTERVAL_SEC)
        assert w._entry_resets == 1, "限流窗口内不得连续 reset"
    finally:
        w.stop()


def test_watcher_github_resume_works_for_commandcode(win_platform, monkeypatch):
    """GitHub 2FA 卡死续跑对 commandcode 同样生效 (登录页也有 Continue with GitHub).

    2FA 后 GitHub 丢 return_to 把窗口留在无关页面 (settings/security), 监听器
    确认已登录后应自动续跑授权入口 —— 授权 URL 重构只依赖 github.com 通用
    形态, 与 provider 无关.
    """
    cm = _FakeCookieManager([_FakeCookie(auth.CC_AUTH_COOKIE_NAME, "STALE", "commandcode.ai")])
    core = _FakeCore(cm, source="https://github.com/settings/security")
    win = _FakeWin(core, url="https://github.com/settings/security")
    monkeypatch.setattr(auth, "COOKIE_POLL_SEC", 0.02)
    monkeypatch.setattr(auth, "_GITHUB_STUCK_GRACE_SEC", 0.05)
    monkeypatch.setattr(auth.webview, "windows", [win])
    w = auth.LoginWatcher(
        win, "commandcode",
        lambda token, ws, provider: None,
        stale_fps=[auth.token_fingerprint(auth.build_token("commandcode", "STALE"))],
    )
    w._oauth_entry = "https://github.com/login?client_id=abc&state=st_flow"  # 已记录的授权入口
    w.start()
    try:
        # watcher 先记录授权入口; 已登录 (_win_run_js 读到页面内容) + 卡在
        # 无关页面超宽限 -> 自动续跑 (Windows 走有界 core.Navigate)
        ok = _wait_until(lambda: core.navigations and w._reloads >= 1)
        assert ok, "commandcode 登录在 GitHub 卡住时也应自动续跑"
        assert core.navigations[-1].startswith("https://github.com/")
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# 主窗口关闭裁决 (Windows 上原生关闭会带走整个进程)
# ---------------------------------------------------------------------------


def test_main_window_close_hides_when_tray_available():
    from app.main import _main_window_close_verdict

    hidden: list[int] = []
    # 返回 False = 取消关闭 (pywebview closing 语义), 窗口隐藏驻留托盘
    assert _main_window_close_verdict(
        lambda: hidden.append(1), quitting=False, tray_ready=True
    ) is False
    assert hidden == [1]


def test_main_window_close_allowed_while_quitting():
    from app.main import _main_window_close_verdict

    hidden: list[int] = []
    assert _main_window_close_verdict(
        lambda: hidden.append(1), quitting=True, tray_ready=True
    ) is True
    assert hidden == [], "退出流程里不允许再隐藏窗口"


def test_main_window_close_allowed_without_tray():
    from app.main import _main_window_close_verdict

    hidden: list[int] = []
    # 托盘没起来时若还拒绝关闭, 窗口将彻底关不掉 (只能强杀进程)
    assert _main_window_close_verdict(
        lambda: hidden.append(1), quitting=False, tray_ready=False
    ) is True
    assert hidden == []


def test_main_window_close_allowed_when_hide_fails():
    from app.main import _main_window_close_verdict

    def boom():
        raise RuntimeError("window gone")

    assert _main_window_close_verdict(boom, quitting=False, tray_ready=True) is True
