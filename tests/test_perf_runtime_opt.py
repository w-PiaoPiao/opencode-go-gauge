"""运行时与登录链路性能修复的回归测试 (性能集群 C).

覆盖四项改动:
1. ``main._arm_watcher_fallback`` 的兜底 Timer 必须是 daemon —— 否则用户在
   打开登录窗后 3s 内退出, 进程会被这个未触发的 Timer 拖住 (实测 +3031 ms);
2. 托盘面板行 (``TrayIcon._info_items``) 的 text 必须是 callable 且求值只读
   内存缓存 ``self._rows`` —— 旧实现把文本固化成常量, pystray 只在 callable 时
   重新求值, 于是"今日用量/配额"永远停在启动瞬间, 且取数跑在主线程;
3. ``login_entry_lost(win, provider, url)`` 复用调用方本轮已读到的 URL ——
   commandcode 每次漂移判定不再做第二次原生往返;
4. ``LoginWatcher._run`` 每轮读 URL 一律经 ``_bounded_call`` (macOS 分支与
   Windows 一致) —— pywebview cocoa 后端的 ``get_current_url`` 是无超时信号量,
   主线程被占时直接调用会让监听线程永久挂起.

约束: 不启动 GUI (不执行 ``webview.start()`` / ``TrayIcon.start()``); 需要跑真实
轮询循环时用等价假窗口; ``auth._LOG_FILE`` 一律重定向到 pytest 临时目录,
绝不写公共 ``/tmp/gousage_login.log``.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

# webview 占位模块由 tests/conftest.py 统一注入 (无 pywebview 的 CI 也能导入).
from app import auth, main  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolated_login_log(tmp_path, monkeypatch):
    """登录日志写临时目录: 不污染公共 /tmp/gousage_login.log."""
    monkeypatch.setattr(auth, "_LOG_FILE", str(tmp_path / "gousage_login.log"))


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """每个用例全程把 db 数据目录钳在 tmp —— 用户真实库零接触 (安全红线).

    源码运行的默认数据目录在 macOS 上是
    ``~/Library/Application Support/GoGauge/data``, 那里是用户真实登录库;
    任何忘记切目录的 db 调用都会跑迁移/读写真实凭证.
    双保险: set_data_dir (override) + GOUSAGE_DATA (环境变量).
    """
    from app import db as _db

    monkeypatch.setenv("GOUSAGE_DATA", str(tmp_path))
    _db.close_db()
    _db.set_data_dir(str(tmp_path))
    try:
        yield
    finally:
        try:
            _db.close_db()
        finally:
            _db.set_data_dir(None)


@pytest.fixture(autouse=True)
def _drain_main_background_threads():
    """兜底: 本文件假跑 main() 后不允许残留 main/sync 后台线程污染后续文件.

    正常情况下 sync/quota 都已被替身; 这里再按线程名有界等待一次 (≤5s),
    确认本文件对全局线程状态零副作用.
    """
    yield
    watched = ("gousage-sync", "gousage-quota", "gousage-update-dl", "gousage-login-arm")
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        alive = [t for t in threading.enumerate() if t.name in watched and t.is_alive()]
        if not alive:
            return
        time.sleep(0.05)


@pytest.fixture(autouse=True)
def _reset_main_module_globals():
    """假跑 main() 会写模块级引用 (token/窗口/UDP 回调): 用例后复位, 防跨用例污染."""
    yield
    main._auth_token_ref["token"] = ""
    main._main_win_ref["win"] = None
    main._udp_show_ref["fn"] = None
    main._quitting = False


@pytest.fixture(autouse=True)
def _fresh_bounded_worker():
    """每个用例前后重置 auth 的有界 worker: 挂死用例不能污染后续用例.

    P2-10 之后 _bounded_call 使用单例 worker, 一旦某个用例把它挂在原生调用上,
    后续用例都会快速拿到 None. 测试侧用 _reset_bounded_worker 换一个新 worker
    (卡死的旧线程会随 release 自行退出).
    """
    auth._reset_bounded_worker()
    yield
    auth._reset_bounded_worker()


@pytest.fixture(scope="module")
def pystray_mod():
    """真实 pystray (托盘用例要验证它的 callable/visible 求值语义).

    pystray 在 import 时就按平台挑后端, Linux 上依次试 appindicator/gtk/xorg.
    没有图形栈的机器 (典型如无头 CI runner) 上 ``import pystray`` 会失败, 但抛的
    未必是 ImportError: pystray 的候选循环只捕获 ImportError, 而 ``_xorg`` 后端在
    模块顶层就 ``Xlib.display.Display()`` —— 没有 $DISPLAY 时抛的是
    ``Xlib.error.DisplayNameError``, 谁的 except 都不接, 会直接穿透出来
    (2026-10-19 ubuntu-latest 实测: 2 errors). 因此这里捕获 Exception 而非只捕
    ImportError. 那种环境跳过后两个托盘用例即可: 二者只验证菜单描述 (text/visible
    callable 的求值时机), 与后端无关; Windows/macOS 上 pystray 恒可导入, 断言照常真跑.
    module 作用域: 跳过按用例记, 不把整个测试文件拖成 error.
    """
    try:
        import pystray  # noqa: PLC0415  仅托盘用例需要; 不涉及 Icon/窗口创建
    except Exception as exc:  # noqa: BLE001  无图形栈时后端探测的抛法不止一种
        # 只有无头 Linux CI 才允许跳过: Windows/macOS 上 pystray 导入失败是真的
        # 回归, 必须让用例红, 不能被笼统的 skip 掩盖.
        if not sys.platform.startswith("linux"):
            raise
        pytest.skip(f"本机没有可用的 pystray 后端 ({type(exc).__name__}: {exc}); 托盘用例需要真实 pystray")

    return pystray


def _wait_until(pred, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return bool(pred())


# ---------------------------------------------------------------------------
# ① 登录窗兜底 Timer: daemon
# ---------------------------------------------------------------------------


def test_watcher_fallback_timer_is_daemon(monkeypatch):
    """未触发的 3s Timer 若是普通线程, threading._shutdown 会 join 到它结束."""
    created: list[threading.Timer] = []

    class RecordingTimer(threading.Timer):
        def __init__(self, *args, **kwargs):
            # 顺带锁定"不接受 daemon= 关键字"这一约束: 传了就在这里 TypeError
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(main.threading, "Timer", RecordingTimer)

    class _W:
        def start(self) -> None:  # pragma: no cover - Timer 未触发
            raise AssertionError("兜底 Timer 不应在本用例内触发")

    w = _W()
    main._arm_watcher_fallback({"ref": w}, w)

    assert len(created) == 1, "兜底 Timer 没被武装"
    timer = created[0]
    try:
        assert timer.daemon is True, "兜底 Timer 必须是 daemon, 否则退出被拖 3s"
        assert timer.interval == 3.0
    finally:
        timer.cancel()  # 别把 3s 的待触发 Timer 留给测试会话


def test_fallback_timer_does_not_delay_process_exit():
    """子进程实测: 武装兜底 Timer 后立刻退出, 不得等满 3s.

    非 daemon 版实测退出耗时 3023 ms (daemon 版 18 ms, 空载 ~40 ms).
    """
    code = textwrap.dedent(
        """
        import sys, types
        stub = types.ModuleType("webview")
        stub.windows = []
        sys.modules.setdefault("webview", stub)
        from app import main

        class W:
            def start(self):
                raise AssertionError("兜底 Timer 不应在退出前触发")

        w = W()
        main._arm_watcher_fallback({"ref": w}, w)
        """
    )
    started = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    elapsed = time.monotonic() - started
    assert proc.returncode == 0, proc.stderr
    assert elapsed < 1.5, f"进程退出被兜底 Timer 拖了 {elapsed * 1000:.0f} ms"


# ---------------------------------------------------------------------------
# ② 托盘面板行: callable 文本 + 求值不触达 DB
# ---------------------------------------------------------------------------


def _tray(tmp_path, lang: str = "zh") -> main.TrayIcon:
    tray = main.TrayIcon(str(tmp_path / "icon.png"))
    tray._lang = lang
    return tray


def test_tray_panel_rows_are_dynamic_and_db_free(tmp_path, monkeypatch, pystray_mod):
    """text 必须是 callable: 换缓存即出新文本, 且求值路径不执行任何 DB 调用."""
    hits = {"token": 0, "totals": 0}

    def _bump(key: str):
        hits[key] += 1

    def fake_token():
        _bump("token")
        return "tok"

    def fake_totals(*_args, **_kwargs):
        _bump("totals")
        return {}

    monkeypatch.setattr(main.db, "get_token", fake_token)
    monkeypatch.setattr(main.db, "totals", fake_totals)

    tray = _tray(tmp_path)
    tray._rows = ["今日: $1.23 · 4 次", "5 小时: 剩余 42%"]
    items = tray._info_items(pystray_mod)
    assert len(items) == main.TrayIcon._PANEL_SLOTS

    # pystray 的 MenuItem.text / .visible 属性每次访问都会求值 callable
    assert [i.text for i in items] == [
        "今日: $1.23 · 4 次", "5 小时: 剩余 42%", "", "",
    ]
    assert [i.visible for i in items] == [True, True, False, False]
    assert hits == {"token": 0, "totals": 0}, "菜单求值路径不得触达 DB"

    # 真正的刷新: 同一批 MenuItem 立刻给出新文本 (固化常量做不到这一点)
    tray._rows = ["今日: $9.99 · 40 次"]
    assert items[0].text == "今日: $9.99 · 40 次"
    assert items[0].visible is True
    assert items[1].visible is False
    assert hits == {"token": 0, "totals": 0}


def test_empty_panel_keeps_legacy_menu_shape(tmp_path, pystray_mod):
    """面板为空时菜单形态与旧实现一致 (相邻分隔符被 pystray 合并)."""
    tray = _tray(tmp_path)
    t = main._TRAY_I18N["zh"]
    menu = pystray_mod.Menu(
        pystray_mod.MenuItem(t["show"], None, default=True),
        pystray_mod.Menu.SEPARATOR,
        *tray._info_items(pystray_mod),
        pystray_mod.Menu.SEPARATOR,
        pystray_mod.MenuItem(t["quit"], None),
    )
    assert [i.text for i in menu] == [t["show"], "- - - -", t["quit"]]

    # 数据就绪后无需重建菜单描述: 迭代时重新求值即可见
    tray._rows = ["今日: $1.00 · 1 次"]
    assert [i.text for i in menu] == [
        t["show"], "- - - -", "今日: $1.00 · 1 次", "- - - -", t["quit"],
    ]


def test_refresh_once_fetches_in_background_then_rebuilds_menu(tmp_path, monkeypatch):
    """取数搬进刷新线程: _refresh_once 先换缓存, 再 update_menu 让 callable 生效."""
    class FakeIcon:
        def __init__(self) -> None:
            self.updates = 0

        def update_menu(self) -> None:
            self.updates += 1

    monkeypatch.setattr(main.db, "get_token", lambda: "tok")
    monkeypatch.setattr(
        main.db, "totals",
        lambda *_a, **_k: {"total_cost_usd": 1.234, "request_count": 7},
    )
    monkeypatch.setattr(main.db, "get_active_account_id", lambda: "acc1")
    monkeypatch.setattr(main.server, "_quota_cache", {
        "acc1": {"at": 0, "data": {"windows": [
            {"label": "5h", "remaining": 41.6},
            {"label": "Week", "remaining": 88},
            {"label": "Extra", "remaining": 5},
            {"label": "第 4 条不该出现", "remaining": 1},
        ]}},
    })

    tray = _tray(tmp_path)
    assert tray._rows == [], "start() 时必须是空占位行 (不阻塞主线程取数)"
    icon = FakeIcon()
    tray._icon = icon
    tray._refresh_once()

    assert icon.updates == 1
    assert tray._rows == [
        "今日: $1.23 · 7 次",
        "5h: 剩余 42%",
        "Week: 剩余 88%",
        "Extra: 剩余 5%",
    ]


@pytest.mark.parametrize("lang,expected", [("zh", "未登录 · 打开窗口登录"),
                                           ("en", "Not logged in")])
def test_refresh_once_keeps_not_logged_in_branch(tmp_path, monkeypatch, lang, expected):
    monkeypatch.setattr(main.db, "get_token", lambda: "")
    tray = _tray(tmp_path, lang)
    tray._refresh_once()
    assert tray._rows == [expected]


def test_refresh_once_swallows_errors(tmp_path, monkeypatch):
    """数据未就绪时面板行省略, 且不得把异常抛出刷新线程."""
    def boom(*_a, **_k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(main.db, "get_token", boom)
    tray = _tray(tmp_path)
    tray._rows = ["旧行"]
    tray._refresh_once()  # 不得抛出
    assert tray._rows == []


# ---------------------------------------------------------------------------
# ③④ 登录轮询: 每轮只读一次 URL, 且读取一律有界
# ---------------------------------------------------------------------------


class _CountWin:
    """最小窗口替身: 统计 get_current_url 的原生往返次数."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.url_reads = 0

    def get_current_url(self):
        self.url_reads += 1
        return self.url

    def get_cookies(self):
        return []


def test_login_entry_lost_reuses_supplied_url():
    """传入 url 时不得再取一次原生 URL; 未传时保持老路 (自己读一次)."""
    win = _CountWin("https://commandcode.ai/dashboard")
    assert auth.login_entry_lost(win, "commandcode", win.url) is True
    assert win.url_reads == 0, "已给出 URL 却又做了一次原生往返"

    fresh = _CountWin("https://commandcode.ai/dashboard")
    assert auth.login_entry_lost(fresh, "commandcode") is True
    assert fresh.url_reads == 1, "未传 url 时必须保持原有的自行读取"

    # 空串 = "本轮已读到的空 URL": 不判偏离, 同样不再读
    blank = _CountWin("https://commandcode.ai/signin")
    assert auth.login_entry_lost(blank, "commandcode", "") is False
    assert blank.url_reads == 0


def test_entry_drift_check_does_not_reread_url(monkeypatch):
    """_check_entry_drift 复用 _run 本轮读到的 URL (旧实现每轮读两次)."""
    win = _CountWin("https://commandcode.ai/dashboard")
    w = auth.LoginWatcher(win, "commandcode", lambda *_a: None)
    # 到重置上限: 判定偏离后不再触发 reset_login_session (那里还会读一次 URL)
    w._entry_resets = auth._ENTRY_RESET_MAX
    w._check_entry_drift(win.url)
    assert win.url_reads == 0, "漂移判定又读了一次原生 URL"


def test_watcher_reads_url_once_per_round(monkeypatch):
    """整轮跑真实 _run: commandcode 每轮只有 1 次 URL 读取 (修复前 2 次)."""
    win = _CountWin("https://commandcode.ai/dashboard")  # 停在非 /signin 的 provider 域
    monkeypatch.setattr(auth, "COOKIE_POLL_SEC", 30.0)  # 第一轮后进入长等待, 轮数可控
    monkeypatch.setattr(auth.webview, "windows", [win])

    w = auth.LoginWatcher(win, "commandcode", lambda *_a: None)
    w._entry_resets = auth._ENTRY_RESET_MAX  # 隔离 reset 路径的额外读取
    w.start()
    try:
        assert _wait_until(lambda: win.url_reads >= 1, timeout=2.0), "监听线程没跑起来"
        time.sleep(0.3)  # 同轮内的第二次读取 (旧实现) 必然紧随第一次
        assert win.url_reads == 1, f"每轮读取次数不是 1: {win.url_reads}"
    finally:
        w.stop()


def test_watcher_url_read_is_bounded(monkeypatch):
    """macOS(cocoa) 的 get_current_url 是无超时信号量: 必须经 _bounded_call.

    假窗口的 get_current_url 永久挂住 (等价 cocoa.py:869-877 的 acquire 不返回):
    直接调用会让监听线程就此僵尸化 (单飞守卫拦死后续登录); 经 _bounded_call 则
    每轮按超时放弃, 轮询继续推进.
    """
    # 显式钉在 macOS 分支上: 修复前该分支是直调, Windows 分支才是 _bounded_call
    monkeypatch.setattr(auth.sys, "platform", "darwin")
    monkeypatch.setattr(auth, "COOKIE_READ_TIMEOUT", 0.05)
    monkeypatch.setattr(auth, "COOKIE_POLL_SEC", 0.02)

    release = threading.Event()
    calls = {"url": 0, "bounded": 0}

    class HangingWin:
        def get_current_url(self):
            calls["url"] += 1
            release.wait(30)  # 模拟无超时信号量: 永不返回
            return "https://commandcode.ai/signin"

        def get_cookies(self):  # pragma: no cover - 只在超时竞态下被摸到
            return []

    win = HangingWin()
    monkeypatch.setattr(auth.webview, "windows", [win])

    real_bounded = auth._bounded_call

    def spy(fn, timeout):
        calls["bounded"] += 1
        return real_bounded(fn, timeout)

    monkeypatch.setattr(auth, "_bounded_call", spy)

    w = auth.LoginWatcher(win, "commandcode", lambda *_a: None)
    w._window_alive = lambda: True  # 假窗口不在 webview.windows 里, 直接放行
    ticks: list[float] = []
    last = None
    try:
        w.start()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            tick = w._last_tick
            if tick != last:
                ticks.append(tick)
                last = tick
            if calls["bounded"] >= 2 and len(ticks) >= 2:
                break
            time.sleep(0.01)
    finally:
        w.stop()
        # 先确认轮询线程退出, 再放掉卡在原生等待里的单例 worker (避免它把 URL
        # 送回已经超时的调用方, 让观测出现竞态)
        if w._thread is not None:
            w._thread.join(timeout=2.0)
        release.set()

    assert calls["url"] >= 1, "假窗口的 URL 读取没被调用, 用例没走到目标路径"
    assert calls["bounded"] >= 2, "URL 读取未经 _bounded_call: macOS 上会永久挂起"
    assert len(ticks) >= 2, f"监听线程卡住未继续推进 (ticks={len(ticks)})"


def test_bounded_call_reuses_single_worker_thread(monkeypatch):
    """P2-10: 超时不再每次新建线程 —— 挂 N 次后 worker 线程数不增长 (≤1).

    旧实现每次 `_bounded_call` 都起一个新线程, 超时即丢弃 (不可回收): 主线程
    被占住时登录监听按轮询频率累积线程. 新实现是单例 worker: 超时丢弃任务,
    worker 忙碌期间新调用直接返回 None, 线程数恒定.
    """
    release = threading.Event()

    def hang():
        release.wait(30)

    worker_name = "gousage-bounded-call"
    before = {t.ident for t in threading.enumerate()}
    try:
        for _ in range(5):
            started = time.monotonic()
            assert auth._bounded_call(hang, 0.02) is None
            assert time.monotonic() - started < 1.0, "超时没有及时返回"
        new_workers = [
            t for t in threading.enumerate()
            if t.name == worker_name and t.ident not in before
        ]
        assert len(new_workers) <= 1, f"每次超时都新建线程: {len(new_workers)} 个"
    finally:
        release.set()

    # release 后单例 worker 应自行回到空闲 (下一单可正常执行); worker 完成挂住
    # 的那一单需要一点时间, 轮询等待而不是立刻断言
    assert _wait_until(lambda: auth._bounded_call(lambda: "ok", 0.5) == "ok", timeout=2.0), (
        "单例 worker 在原生调用返回后没有恢复可用"
    )


def test_bounded_call_returns_none_on_hang():
    """机制基线: _bounded_call 超时返回 None 而不挂住调用线程."""
    release = threading.Event()
    try:
        started = time.monotonic()
        got = auth._bounded_call(lambda: release.wait(30), 0.05)
        elapsed = time.monotonic() - started
    finally:
        release.set()
    assert got is None
    assert elapsed < 1.0


# ---------------------------------------------------------------------------
# ⑤ open_login 并发锁 + I4 dashboard token (用假 webview 跑真实 main())
# ---------------------------------------------------------------------------
# 不启动 GUI: `webview.create_window` / `webview.start` / 托盘 / 单实例全部替身,
# 只验证 main() 的装配逻辑 (登录窗并发与 dashboard URL 的 token 传递).


from types import SimpleNamespace


class _FakeEvent:
    def __init__(self) -> None:
        self.handlers: list = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self, *args) -> None:  # pragma: no cover - 用例不触发原生事件
        for handler in list(self.handlers):
            handler(*args)


class _FakeWindow:
    def __init__(self, title: str, url: str) -> None:
        self.title = title
        self.url = url
        self.destroyed = False
        self.loaded_urls: list[str] = []
        self.js_calls: list[str] = []
        self.events = SimpleNamespace(
            closed=_FakeEvent(),
            shown=_FakeEvent(),
            restored=_FakeEvent(),
            closing=_FakeEvent(),
            loaded=_FakeEvent(),
        )
        self.native = SimpleNamespace(Handle=None)
        self.x = self.y = 0
        self.width, self.height = 1280, 840

    # pywebview Window 的最小替身 (登录链路只用到这些)
    def get_current_url(self):
        return self.url

    def get_cookies(self):
        return []

    def clear_cookies(self):
        pass

    def load_url(self, url):
        self.loaded_urls.append(url)
        self.url = url
        _FakeAppState.calls.append(("load_url", self.title))

    def load_html(self, html, base):
        pass

    def evaluate_js(self, script):
        self.js_calls.append(script)
        _FakeAppState.calls.append(("evaluate_js", self.title))
        return None

    def create_file_dialog(self, *args, **kwargs):  # pragma: no cover
        return None

    def show(self):
        _FakeAppState.calls.append(("show", self.title))

    def restore(self):
        pass

    def hide(self):
        _FakeAppState.calls.append(("hide", self.title))

    def minimize(self):
        pass

    def destroy(self):
        self.destroyed = True
        if self in _FakeAppState.windows:
            _FakeAppState.windows.remove(self)


class _FakeAppState:
    windows: list = []
    calls: list = []


class _StubLoginWatcher:
    """替代真实 LoginWatcher: 只记录创建/引用关系, 不轮询."""

    created: list = []

    def __init__(self, win, provider, on_success, on_cancelled=None,
                 stale_fps=None, baseline_value=None):
        self.win = win
        self.provider = provider
        self.on_success = on_success
        self.done = False
        self._thread = None
        self.started = False
        _StubLoginWatcher.created.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        pass

    def seconds_since_tick(self) -> float:
        return 0.0


class _FakeApp:
    def __init__(self) -> None:
        self.dashboard_url = ""
        self.auth_token_calls: list[str] = []
        self.logs: list[str] = []
        self.open_login = None
        # main() 启动路径 (已登录但空库) 会触发首次全量同步: 测试里必须替身掉,
        # 否则会真的起后台线程拿假 token 打网络, 并把 server._sync_state 置为
        # running=True 污染后续 HTTP 缓存用例 (T6 实测跨文件污染).
        self.sync_calls: list[str] = []


def _build_fake_app(monkeypatch, tmp_path, clear_delay: float = 0.0) -> _FakeApp:
    """把 main() 的外部依赖全部替身化并真实跑一遍 main() (不启动 GUI)."""
    app = _FakeApp()
    _FakeAppState.windows = []
    _FakeAppState.calls = []
    _StubLoginWatcher.created = []

    def _create_window(title, url="", **kwargs):
        win = _FakeWindow(title, url)
        _FakeAppState.windows.append(win)
        if title == main.APP_TITLE:
            app.dashboard_url = url
        return win

    monkeypatch.setattr(main.webview, "windows", _FakeAppState.windows)
    monkeypatch.setattr(main.webview, "create_window", _create_window)
    monkeypatch.setattr(main.webview, "start", lambda *a, **k: None)
    monkeypatch.setattr(main, "_ensure_single_instance", lambda: None)
    monkeypatch.setattr(main, "_ensure_single_instance_mac", lambda: None)
    monkeypatch.setattr(main, "_screen_workarea_logical", lambda: (1440, 900))
    monkeypatch.setattr(main, "_screen_visible_frame_logical", lambda: (1440, 900))
    monkeypatch.setattr(main, "_install_macos_app_delegate", lambda: None)
    monkeypatch.setattr(main, "_log_runtime_banner", lambda: None)
    # 固定成"非 Windows 非 macOS"分支: 登录窗装配走纯 Python 路径, 不依赖宿主
    # 平台, 也不会拉起 macOS 的登录页看门狗线程 (那是真实 GUI 行为, 测试不跑).
    monkeypatch.setattr(main, "_IS_MAC", False)
    monkeypatch.setattr(main, "_IS_WIN", False)
    monkeypatch.setattr(main.https_ca, "install", lambda: None)
    monkeypatch.setattr(main.TrayIcon, "start", lambda self: False)
    monkeypatch.setattr(main, "LoginWatcher", _StubLoginWatcher)
    monkeypatch.setattr(main, "_mlog", app.logs.append)

    def _fake_sync(mode: str) -> None:
        # 替身而非真跑: main() 启动路径/登录成功路径都会触发首次全量同步,
        # 真跑会起 gousage-sync 线程拿假 token 打网络, 并残留 _sync_state
        # running=True 污染后续 HTTP 缓存用例 (T2/T6 实测跨文件假红).
        app.sync_calls.append(mode)
        _FakeAppState.calls.append(("sync", mode))

    monkeypatch.setattr(main.server, "sync_all_async", _fake_sync)

    def _slow_clear(provider, win=None):
        if clear_delay:
            time.sleep(clear_delay)
        return 0

    monkeypatch.setattr(main, "clear_provider_cookies", _slow_clear)

    import app.server as _server  # noqa: PLC0415

    monkeypatch.setattr(_server, "start_server", lambda *a, **k: ("127.0.0.1", 12345))
    monkeypatch.setattr(
        _server,
        "set_login_callback",
        lambda cb: setattr(app, "open_login", cb),
    )
    from app import db as _db  # noqa: PLC0415

    # 数据目录在调用 main() **之前**切到 tmp: main() 里 db.get_db() 会跑迁移,
    # 绝不能落到用户真实数据目录 (源码运行默认是 ~/Library/Application Support/...).
    # 保持到用例结束, 由文件级 _isolated_data_dir fixture 统一复位.
    _db.set_data_dir(str(tmp_path))
    main.main()
    assert app.open_login is not None, "main() 未注册登录回调"
    return app


def test_main_dashboard_url_passes_http_token_in_fragment(monkeypatch, tmp_path):
    """I4: main 生成随机 token 交给 server, 并用 URL fragment 传给 WebView.

    fragment 不进 HTTP 请求行/Referer; 日志里不得出现含 token 的 URL.
    """
    import app.server as _server  # noqa: PLC0415

    tokens: list[str] = []
    monkeypatch.setattr(_server, "set_auth_token", tokens.append, raising=False)

    app = _build_fake_app(monkeypatch, tmp_path)

    assert app.dashboard_url.startswith("http://127.0.0.1:12345/")
    assert "#" in app.dashboard_url, "dashboard URL 必须用 fragment 传 token"
    token = app.dashboard_url.split("#", 1)[1]
    assert len(token) >= 20, "HTTP token 太短 (需要 secrets.token_urlsafe(32) 量级)"
    assert tokens == [token], "server.set_auth_token 必须收到同一个 token"

    assert main._auth_token_ref["token"] == token
    assert main.WindowApi().get_auth_token() == token, "js_api 兜底拿不到 token"
    assert app.sync_calls == [], "空库启动不应触发全量同步 (根因: 替身未生效)"

    joined = "\n".join(app.logs)
    assert token not in joined, "日志泄漏了 HTTP token"
    assert "127.0.0.1:12345/#" not in joined, "日志打印了含 token 的完整 URL"


def test_login_success_writes_back_captured_target_account(monkeypatch, tmp_path):
    """P1-1 端到端: 经真实 main() 走一遍 open_login -> 登录中途切号 -> on_success.

    目标账号在 open_login 发起时固化; 回调时活跃账号已变成 B, 新凭证仍必须写回 A.
    """
    from app import db as _db  # noqa: PLC0415

    _db.set_data_dir(str(tmp_path))
    try:
        aid_a = _db.add_account("__Host-console_session=OLD_A", "wsA", switch=True)
        aid_b = _db.add_account("__Host-console_session=B", "wsB", switch=True)
        _db.set_active_account(aid_a)
    finally:
        _db.close_db()

    app = _build_fake_app(monkeypatch, tmp_path)
    startup_syncs = list(app.sync_calls)  # 已登录但空库: main() 启动路径会触发一次

    # I1: db.save_token 支持 account_id, 这里用等价替身避免依赖真实凭证加密: 模拟"db.save_token 支持 account_id 且按 id 写入"
    def _fake_save(token, workspace_id="Default", provider="opencode", account_id=None):
        if account_id is None:
            return False
        conn = _db.get_db()
        conn.execute(
            "UPDATE accounts SET token = ?, token_fp = ?, provider = ?,"
            " workspace_id = ?, updated_at = ? WHERE id = ?",
            (token, _db._token_fp(token), provider, workspace_id,
             "2026-10-27T00:00:00Z", int(account_id)),
        )
        conn.commit()
        _db._invalidate_cred_cache(int(account_id))
        return True

    monkeypatch.setattr(_db, "save_token", _fake_save)

    app.open_login("relogin", "opencode")
    assert _StubLoginWatcher.created, "open_login 没有启动 watcher"
    watcher = _StubLoginWatcher.created[-1]

    # OAuth 期间用户在主窗口切到 B (数据目录仍是本用例的 tmp, 与 main() 一致)
    _db.set_active_account(aid_b)
    _db.close_db()

    watcher.on_success("__Host-console_session=NEW_A", "wsA", "opencode")

    try:
        assert _db.get_account_credentials(aid_a)[0] == "__Host-console_session=NEW_A"
        assert _db.get_account_credentials(aid_b)[0] == "__Host-console_session=B"
        assert _db.get_active_account_id() == aid_b
        assert app.sync_calls == startup_syncs + ["full"], (
            "登录成功必须先触发首次全量同步 (且只多触发一次)"
        )
    finally:
        _db.close_db()


def test_login_success_syncs_before_ui_wiring(monkeypatch, tmp_path):
    """P2-10 端到端: 登录成功后先触发全量同步, 再隐藏登录窗/刷新主窗."""
    app = _build_fake_app(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "_persist_login_credential", lambda *a, **k: True)

    app.open_login("relogin", "opencode")
    watcher = _StubLoginWatcher.created[-1]
    watcher.on_success("__Host-console_session=NEW", "ws", "opencode")

    assert app.sync_calls == ["full"], "登录成功必须恰好触发一次首次全量同步"
    calls = _FakeAppState.calls
    assert ("sync", "full") in calls
    assert ("hide", "GoGauge - Login") in calls
    sync_index = calls.index(("sync", "full"))
    hide_index = calls.index(("hide", "GoGauge - Login"))
    assert sync_index < hide_index, "全量同步必须排在 UI 收尾之前"
    assert any(
        "gousageOnLoginSuccess" in script for script in _FakeAppState.windows[-1].js_calls
    ) or any(
        "gousageOnLoginSuccess" in script
        for win in _FakeAppState.windows for script in win.js_calls
    )


def test_login_success_failure_keeps_login_window_and_skips_sync(monkeypatch, tmp_path):
    """P2-10: 凭证保存失败 -> 不隐藏登录窗、不刷新、不触发同步, 并尽量提示."""
    app = _build_fake_app(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "_persist_login_credential", lambda *a, **k: False)

    app.open_login("relogin", "opencode")
    watcher = _StubLoginWatcher.created[-1]
    watcher.on_success("__Host-console_session=NEW", "ws", "opencode")

    calls = _FakeAppState.calls
    assert app.sync_calls == [], "保存失败不得触发全量同步"
    assert ("sync", "full") not in calls, "保存失败不得触发全量同步"
    assert ("hide", "GoGauge - Login") not in calls, "保存失败必须保持登录窗打开"
    assert any("credential NOT saved" in line for line in app.logs)
    assert any(
        "gousageOnLoginFailed" in script
        for win in _FakeAppState.windows for script in win.js_calls
    ), "保存失败应尽力通知前端"


def test_open_login_concurrent_click_creates_single_window(monkeypatch, tmp_path):
    """P2-10: 快速双击 (并发进入 open_login) 只能产生一个登录窗口/一个 watcher."""
    app = _build_fake_app(monkeypatch, tmp_path, clear_delay=0.3)

    first = threading.Thread(target=app.open_login, args=("relogin", "opencode"))
    first.start()
    time.sleep(0.05)  # 让第一次调用进入 _prepare_login_session (慢路径)

    started = time.monotonic()
    app.open_login("relogin", "opencode")  # 第二次点击: 非阻塞锁应直接忽略
    second_elapsed = time.monotonic() - started
    first.join(timeout=5.0)

    login_windows = [w for w in _FakeAppState.windows if w.title == "GoGauge - Login"]
    assert len(login_windows) == 1, f"并发双击创建了 {len(login_windows)} 个登录窗口"
    assert len(_StubLoginWatcher.created) == 1, "并发双击创建了多个 watcher"
    assert second_elapsed < 0.2, "重复点击没有被非阻塞锁立即忽略"
