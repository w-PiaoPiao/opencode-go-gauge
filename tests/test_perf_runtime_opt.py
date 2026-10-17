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
import types
from pathlib import Path

import pytest

# app.auth/app.main 顶层 import webview (仅打包环境可用): 与 test_auth_login.py
# 一致, 先补一个占位模块再导入被测模块.
_webview_stub = types.ModuleType("webview")
_webview_stub.windows = []
sys.modules.setdefault("webview", _webview_stub)

from app import auth, main  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolated_login_log(tmp_path, monkeypatch):
    """登录日志写临时目录: 不污染公共 /tmp/gousage_login.log."""
    monkeypatch.setattr(auth, "_LOG_FILE", str(tmp_path / "gousage_login.log"))


@pytest.fixture(scope="module")
def pystray_mod():
    """真实 pystray (托盘用例要验证它的 callable/visible 求值语义)."""
    import pystray  # noqa: PLC0415  仅托盘用例需要; 不涉及 Icon/窗口创建

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
        # 先确认轮询线程退出, 再放掉被超时抛弃的 worker (避免它把 URL 送回
        # 已经超时的调用方, 让观测出现竞态)
        if w._thread is not None:
            w._thread.join(timeout=2.0)
        release.set()

    assert calls["url"] >= 1, "假窗口的 URL 读取没被调用, 用例没走到目标路径"
    assert calls["bounded"] >= 2, "URL 读取未经 _bounded_call: macOS 上会永久挂起"
    assert len(ticks) >= 2, f"监听线程卡住未继续推进 (ticks={len(ticks)})"


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
