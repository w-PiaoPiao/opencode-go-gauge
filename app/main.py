"""GoGauge - OpenCode Go 用量统计面板 (Python + WebView, 跨平台 Windows/macOS).

入口: 启动本地 HTTP 服务 → 创建 WebView 窗口 → 未登录时加载授权页登录,
登录成功后自动进入面板 (首次自动全量同步, 之后读本地数据库).
系统托盘 (Windows) / 菜单栏图标 (macOS): 关闭窗口最小化到托盘/菜单栏,
菜单可显示窗口/退出. 双平台行为一致, 功能完全相同.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading

import webview

from . import db, server
from .auth import LoginWatcher, build_login_url

APP_TITLE = "GoGauge - OpenCode Go Usage Panel"
WINDOW_SIZE = (1280, 840)
WINDOW_MIN_SIZE = (1000, 680)

_IS_MAC = sys.platform == "darwin"
_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    import ctypes  # noqa: E402  仅 Windows 需要 Win32 API

_quitting = False  # 托盘"退出"标志: 为 True 时关闭窗口=真正退出
_tray_ready = False  # 托盘是否成功启动 (失败时关闭窗口=直接退出, 避免无法关闭)


def _enable_taskbar_minimize(win) -> None:
    """无边框窗口修复 (仅 Windows): 补上 WS_MINIMIZEBOX 样式.

    pywebview frameless @ Windows -> WinForms FormBorderStyle.None, 该样式不包含
    WS_MINIMIZEBOX (初始样式仅含 WS_MAXIMIZEBOX), 系统会忽略任务栏按钮的
    最小化请求. 给窗口句柄补上该样式, 恢复标准任务栏行为.
    macOS 无此 API, 跳过 (Cocoa 窗口本身支持最小化).
    """
    if not _IS_WIN:
        return
    try:
        # pythonnet IntPtr 需先 ToInt32() 再转 int (直接 int() 会抛 TypeError)
        hwnd = int(win.native.Handle.ToInt32())
        GWL_STYLE = -16
        WS_MINIMIZEBOX = 0x00020000
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
        if style and not (style & WS_MINIMIZEBOX):
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_MINIMIZEBOX)
    except Exception:  # noqa: BLE001
        pass

_MAIN_LOG = os.path.join(tempfile.gettempdir(), "gousage_main.log")


def _mlog(msg: str) -> None:
    """主流程日志 (exe 无控制台, 落盘便于排查)."""
    try:
        with open(_MAIN_LOG, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def _asset_path(rel: str) -> str:
    """定位资源文件 (开发/打包后通用)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "assets", rel)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", rel)


def _app_icon_path() -> str:
    """按平台选择应用/托盘图标.

    Windows 使用 .ico; macOS 使用 .png (Dock 与菜单栏图标通用, WKWebView
    无 .ico 支持, pystray 走菜单栏也只需 PNG). 优先返回实际存在的文件.
    """
    candidates = ["GoGauge.png"] if _IS_MAC else ["GoGauge.ico"]
    for name in candidates:
        p = _asset_path(name)
        if os.path.isfile(p):
            return p
    # 兜底: 任一可用图标
    for name in ("GoGauge.png", "GoGauge.ico"):
        p = _asset_path(name)
        if os.path.isfile(p):
            return p
    return ""



class TrayIcon:
    """系统托盘/菜单栏图标 (pystray): logo + 显示窗口/退出 菜单.

    Windows: 在后台线程运行 pystray 自己的事件循环.
    macOS: AppKit 必须在主线程, 且需与 pywebview 共享同一个 NSApplication 事件循环,
    因此在主线程构造图标后调用 run_detached() 注册, 由 webview.start() 驱动菜单栏.
    """

    def __init__(self, icon_path: str) -> None:
        self._icon_path = icon_path
        self._icon = None
        self._win_getter = None

    def bind_window(self, getter) -> None:
        self._win_getter = getter

    def start(self) -> bool:
        global _tray_ready
        try:
            from PIL import Image
            import pystray

            if not os.path.isfile(self._icon_path):
                return False
            img = Image.open(self._icon_path).convert("RGBA")
            menu = pystray.Menu(
                pystray.MenuItem("显示窗口", self._show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._quit),
            )
            self._icon = pystray.Icon("GoGauge", img, "GoGauge - OpenCode Go 用量面板", menu)
            if _IS_MAC:
                # macOS: 主线程构造(Icon 里创建 NSStatusItem/NSWindow 需在主线程),
                # run_detached 仅注册, 不启动独立 run loop, 由 pywebview 驱动.
                self._icon.run_detached(setup=lambda i: setattr(i, "visible", True))
            else:
                # Windows / 其它: pystray 自带事件循环, 放入后台线程.
                threading.Thread(target=self._icon.run, daemon=True).start()
            _tray_ready = True
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[tray] 托盘启动失败: {exc}", flush=True)
            _tray_ready = False
            return False

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:  # noqa: BLE001
                pass

    def _show(self, icon=None, item=None) -> None:
        if self._win_getter:
            win = self._win_getter()
            if win:
                win.show()
                win.restore()

    def _quit(self, icon=None, item=None) -> None:
        global _quitting
        _quitting = True
        if icon:
            try:
                icon.stop()
            except Exception:  # noqa: BLE001
                pass
        _destroy_all_windows()


class WindowApi:
    """通过 js_api 暴露给前端的窗口控制 (自定义标题栏按钮).

    最大化状态由前端维护 (frameless 窗口下用户只能通过按钮切换),
    后端只执行窗口操作, 避免依赖可能不同步的窗口状态属性.
    """

    def __init__(self) -> None:
        self._win = None
        self._on_open_login = None

    def bind(self, win) -> None:
        self._win = win

    def set_login_callback(self, cb) -> None:
        self._on_open_login = cb

    def open_login(self) -> bool:
        """前端"立即登录"点击: 弹出独立登录窗口."""
        if self._on_open_login:
            self._on_open_login()
        return True

    def minimize(self) -> bool:
        if self._win:
            self._win.minimize()
        return True

    def close(self) -> bool:
        """关闭按钮: 托盘可用时最小化到托盘, 否则真正关闭."""
        global _quitting, _tray_ready
        if not self._win:
            return True
        if _quitting or not _tray_ready:
            self._win.destroy()
        else:
            self._win.hide()  # 最小化到托盘
        return True

    def quit(self) -> bool:
        """退出应用 (欢迎页/设置页按钮): 真正退出, 不驻留托盘."""
        global _quitting
        _quitting = True
        _destroy_all_windows()
        return True


def _destroy_all_windows() -> None:
    """销毁所有窗口 (含隐藏登录窗), 让 pywebview 事件循环退出, 进程真正结束."""
    for w in list(webview.windows):
        try:
            w.destroy()
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    global _quitting
    db.get_db()  # 初始化数据库

    host, port = server.start_server()
    dashboard_url = f"http://{host}:{port}/"
    watcher: dict[str, object] = {"ref": None}
    api = WindowApi()

    # 启动窗口: 始终加载本地页面; 未登录时前端显示欢迎页引导登录
    # 平台窗口风格:
    # - macOS: 使用原生标题栏 (frameless=False), 左上角红黄绿交通灯提供原生
    #   关闭/最小化/缩放(最大化). 原生标题栏本身可拖动, 无需 easy_drag.
    # - Windows: 无边框 + 自定义标题栏 (后端/前端窗口按钮), easy_drag 拖动.
    main_win = webview.create_window(
        APP_TITLE,
        dashboard_url,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN_SIZE,
        frameless=(not _IS_MAC),
        easy_drag=_IS_WIN,
        js_api=api,
    )
    api.bind(main_win)

    # 预创建独立登录子窗口 (hidden, 系统边框含关闭按钮; 点击"立即登录"时弹出)
    # 用可变引用: 窗口被手动关闭后可重建, 回调始终指向当前登录窗
    login_win_ref: dict[str, object] = {"win": webview.create_window(
        "GoGauge - OpenCode Go Login",
        "about:blank",
        width=720,
        height=640,
        min_size=(560, 500),
        hidden=True,
        background_color="#f7f6f4",
    )}

    def login_win() -> object:
        return login_win_ref["win"]

    def on_login_success(auth_cookie: str, workspace_hint: str) -> None:
        """登录成功: 保存 token → 隐藏登录窗口 → 主窗口进入面板 → 首次全量同步."""
        _mlog(f"on_login_success: ws={workspace_hint}")
        try:
            db.save_token(auth_cookie, workspace_hint)
            _mlog("  token saved")
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  save_token ERROR: {exc}")
        try:
            login_win().hide()
            _mlog("  login window hidden")
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  hide ERROR: {exc}")
        try:
            main_win.load_url(dashboard_url)
            _mlog("  dashboard load_url called")
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  load_url ERROR: {exc}")
        server.sync_all_async("full")

    def _start_watcher(lw) -> None:
        """启动登录监听: 优先等 shown 事件 (避免 hidden 窗口调用窗口方法抛内部异常);
        复用窗口 (已显示过) 直接启动; 事件不触发时 3s 兜底启动 (LoginWatcher 对未就绪窗口有重试)."""
        w = LoginWatcher(lw, on_login_success)
        watcher["ref"] = w
        if getattr(lw, "_gousage_shown", False):
            w.start()
            _mlog("  watcher started (reused window)")
            return

        def on_shown() -> None:
            setattr(lw, "_gousage_shown", True)
            w.start()
            _mlog("  watcher started (shown event)")

        try:
            lw.events.shown += on_shown
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  shown event register error: {exc}")
        # 兜底: shown 事件在打包环境可能不触发, 3s 后无条件启动监听
        threading.Timer(3.0, w.start).start()

    def open_login() -> None:
        """弹出独立登录窗口并开始监听 (欢迎页/设置页按钮). 单飞守卫: 已有登录流程时忽略."""
        w = watcher.get("ref")
        if isinstance(w, LoginWatcher) and w._thread and w._thread.is_alive() and not w.done:
            return  # 已有登录监听进行中
        lw = login_win()
        try:
            lw.show()
            lw.load_url(build_login_url())
        except Exception as exc:  # noqa: BLE001 窗口可能被用户手动关闭, 重建
            print(f"[main] login window reopen: {exc}", flush=True)
            _recreate_login_window()
            return
        _start_watcher(lw)

    def _recreate_login_window() -> None:
        """登录窗口被手动关闭后重建 (回调绑定新窗口)."""
        w = watcher.get("ref")
        if isinstance(w, LoginWatcher):
            w.stop()
        try:
            login_win().destroy()
        except Exception:  # noqa: BLE001
            pass
        new_win = webview.create_window(
            "GoGauge - OpenCode Go Login",
            build_login_url(),
            width=720,
            height=640,
            min_size=(560, 500),
            background_color="#f7f6f4",
        )
        login_win_ref["win"] = new_win
        _start_watcher(new_win)

    api.set_login_callback(open_login)
    server.set_login_callback(open_login)  # /api/relogin 兼容 (浏览器环境/兜底)

    # 首次启动未登录: 主窗口欢迎页; 已登录但数据库为空: 自动全量同步
    if db.get_token() and not db.get_sync_state().get("total_records"):
        server.sync_all_async("full")

    def on_window_closed() -> None:
        w = watcher.get("ref")
        if isinstance(w, LoginWatcher):
            w.stop()

    def on_shown() -> None:
        # 窗口显示后 native 句柄才可用: 补 WS_MINIMIZEBOX, 修复任务栏点击不最小化
        _enable_taskbar_minimize(main_win)

    def on_restored() -> None:
        # 窗口最小化->恢复过程中 WinForms 可能重建句柄导致样式丢失, 恢复后重新补上
        _enable_taskbar_minimize(main_win)

    main_win.events.closed += on_window_closed
    main_win.events.shown += on_shown
    main_win.events.restored += on_restored

    if _IS_MAC:
        def on_closing() -> bool:
            # macOS 原生红点关闭按钮: 托盘/菜单栏可用时 -> 只隐藏窗口(驻留菜单栏);
            # 真正退出(托盘退出或欢迎页"退出应用")时 -> 返回 True 允许关闭.
            global _quitting, _tray_ready
            if _quitting or not _tray_ready:
                return True  # 允许真正关闭
            try:
                main_win.hide()  # 驻留菜单栏
            except Exception:  # noqa: BLE001
                return True
            return False  # 取消本次关闭

        # 返回 False 即取消原生关闭 (pywebview closing 事件语义)
        main_win.events.closing += on_closing

    # 系统托盘 (Windows) / 菜单栏图标 (macOS)
    tray = TrayIcon(_app_icon_path())
    tray.bind_window(lambda: main_win if main_win in webview.windows else None)
    tray.start()

    # 窗口/Dock 图标: 按平台选择 (Win=ico, macOS 用 png 生成 dock icon 由 .app 提供)
    icon_path = _app_icon_path()
    webview.start(icon=icon_path if icon_path else None)

    if not _quitting:
        tray.stop()


def shutdown() -> None:
    server.stop_server()
    db.close_db()


if __name__ == "__main__":
    main()
