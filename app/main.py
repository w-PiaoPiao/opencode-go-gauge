"""GoGauge - OpenCode Go 用量统计面板 (Python + WebView, 跨平台 Windows/macOS).

入口: 启动本地 HTTP 服务 → 创建 WebView 窗口 → 未登录时加载授权页登录,
登录成功后自动进入面板 (首次自动全量同步, 之后读本地数据库).
系统托盘 (Windows) / 菜单栏图标 (macOS): 关闭窗口最小化到托盘/菜单栏,
菜单可显示窗口/退出. 双平台行为一致, 功能完全相同.
"""
from __future__ import annotations

import ctypes  # noqa: F401  跨平台均有, Win32 窗口/互斥体逻辑用到
import ctypes.wintypes  # noqa: F401  Win32 单实例/窗口枚举用 (macOS 可安全 import)

import json
import os
import secrets
import sys
import tempfile
import threading
import time
from typing import Callable, Optional

import webview

from . import __version__, db, https_ca, server
from .auth import (
    BOOT_SETTLE_SEC,
    LoginWatcher,
    _bounded_ok,
    build_login_url,
    clear_provider_cookies,
    ensure_login_page_loaded,
    render_login_boot_page,
    install_login_network_rules,
    nudge_window_repaint,
    page_snapshot,
    read_provider_cookie,
    reset_login_session,
)

APP_TITLE = "GoGauge - OpenCode Go Usage Panel"
WINDOW_SIZE = (1280, 840)
WINDOW_MIN_SIZE = (1000, 680)

_IS_MAC = sys.platform == "darwin"
_IS_WIN = sys.platform == "win32"

_quitting = False  # 托盘"退出"标志: 为 True 时关闭窗口=真正退出
_tray_ready = False  # 托盘是否成功启动 (失败时关闭窗口=直接退出, 避免无法关闭)
_main_win_ref: dict[str, object] = {"win": None}  # 主窗口引用 (macOS delegate 恢复用)
# 登录页被残留会话带离登录入口 (commandcode 停在官网/控制台) 时的重置重试上限
_LOGIN_ENTRY_RETRIES = 2
# 登录监听的"僵尸"判定: 监听每秒轮询一轮, 超过这么久没有进展就认为某个原生
# 调用把它挂住了 (单飞守卫会因此永久静默吞掉用户的点击), 停掉并重建窗口
_LOGIN_WATCHER_STALE_SEC = 20.0
# 登录成功收尾时的跨线程 UI 调用 (hide/load_url/evaluate_js) 等待上限:
# pywebview 这些方法在 UI 线程被占时无超时阻塞; 超时只当"这次没做完"
# (前端登录监视会兜底刷新), 绝不能拖住监听线程并吞掉首次全量同步.
_LOGIN_UI_CALL_TIMEOUT = 3.0
# open_login 非阻塞锁: pywebview 的 js_api 每次调用都是新线程, 快速双击会并发
# 进入 open_login; 拿不到锁说明已有登录流程正在启动, 直接忽略 (与单飞守卫同语义).
_LOGIN_OPEN_LOCK = threading.Lock()
# I4 双保险: 本地 HTTP API token 的进程内引用. 正常路径经 dashboard URL fragment
# 传给前端 (不进请求行/日志); 个别 WebView/导航路径可能丢 fragment, 此时前端用
# js_api 的 get_auth_token() 读这里兜底. 登录窗口不挂 js_api, 主窗口只加载本地
# 页面, 所以该只读方法不会把 token 暴露给外部站点.
_auth_token_ref: dict[str, str] = {"token": ""}


# ── Win32 窗口辅助 (仅 Windows 运行时使用; ctypes 为跨平台标准库) ──
class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _screen_workarea_logical() -> tuple[int, int]:
    """主屏工作区尺寸(逻辑像素): 窗口初始尺寸不超工作区, 避免矮屏上底部被裁."""
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem() or 96
        scale = dpi / 96.0
        rect = _RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            return int(rect.right / scale), int(rect.bottom / scale)
    except Exception:  # noqa: BLE001
        pass
    return WINDOW_SIZE


_move_lock = threading.Lock()  # 拖动 move_by 串行化: 防 js_api 并发读-写丢增量


def _mac_safari_user_agent() -> Optional[str]:
    """macOS 标准 Safari UA (WKWebView 默认 UA 缺 Version/x 段, 易被
    Cloudflare 质询卡在白屏; 换成完整 Safari UA 提升登录页兼容性)."""
    if not _IS_MAC:
        return None
    try:
        import platform
        mac_ver = platform.mac_ver()[0] or "15.0"
        parts = (mac_ver.split(".") + ["0", "0"])[:2]
        os_ver = "_".join(parts)  # Safari UA 中 macOS 版本用下划线, 如 15_6
        saf_ver = "18.6"
        webkit_ver = "605.1.15"
        return (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_ver}) "
            f"AppleWebKit/{webkit_ver} (KHTML, like Gecko) "
            f"Version/{saf_ver} Safari/{webkit_ver}"
        )
    except Exception:  # noqa: BLE001
        return None


def _install_macos_app_delegate() -> None:
    """替换 pywebview 的 macOS AppDelegate, 补齐两个原生行为:

    1. applicationShouldTerminate_: pywebview 原实现退出时会遍历窗口触发 closing
       事件, 而本应用的 on_closing 在托盘可用时返回 False 取消关闭, 导致
       Cmd+Q / Dock 右键 Quit / 菜单 Quit 全部被静默取消. 此处先置 _quitting
       标志, 再调用原逻辑, 使关闭处理放行, 应用正常退出.
    2. applicationShouldHandleReopen:hasVisibleWindows_: pywebview 未实现该方法,
       窗口被 orderOut 隐藏后点击 Dock 图标无法重新显示. 此处补上恢复主窗口.

    必须在 webview.start() 之前调用: pywebview 在创建窗口时才执行
    BrowserView.AppDelegate.alloc().init() (cocoa.py), 替换类属性即可生效.
    """
    if not _IS_MAC:
        return
    from webview.platforms.cocoa import BrowserView  # noqa: E402  仅 macOS 存在

    class _GoGaugeAppDelegate(BrowserView.AppDelegate):  # type: ignore[misc, valid-type]
        def applicationShouldTerminate_(self, app) -> bool:  # noqa: N802
            _prepare_mac_terminate()
            return super().applicationShouldTerminate_(app)

        def applicationShouldHandleReopen_hasVisibleWindows_(self, sender, flag) -> bool:  # noqa: N802
            win = _main_win_ref.get("win")
            if win is not None:
                try:
                    win.show()
                    win.restore()
                except Exception:  # noqa: BLE001
                    pass
            _mac_activate_app()  # 其他 App 全屏/在前台时也能把窗口带到最前
            return True

    BrowserView.AppDelegate = _GoGaugeAppDelegate


# ── macOS 平台辅助: 前台激活 / 单实例 / 小屏钳制 / 窗口位置记忆 ──
_MAC_LOCK_PATH = os.path.expanduser("~/Library/Application Support/GoGauge/GoGauge.lock")
_MAC_NOTIFY_PORT = 57567  # 本机回环 UDP: 第二实例唤起首实例的通道 (非常用端口)
_mac_lock_fd = None  # 首实例持有的锁文件句柄 (存活期间 flock 有效, 引用防回收)
_udp_show_ref: dict[str, object] = {"fn": None}  # 首实例注册的"前置主窗"回调


def _mac_activate_app() -> None:
    """把应用带到前台: Dock 点击/托盘唤起时, 其他 App 全屏时也能正常置前."""
    try:
        from AppKit import NSApplication

        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:  # noqa: BLE001
        pass


def _ensure_single_instance_mac() -> None:
    """macOS 单实例守卫 (仅打包 .app): flock 原子判定, 二次启动唤起首实例后退出.

    Windows 用内核命名互斥体; macOS 等价物为文件锁 flock (进程退出自动释放,
    无残留无 PID 复用问题). 唤醒通道用回环 UDP 而非 AppleScript: 后者发
    Apple Event 可能触发 TCC 自动化权限弹窗, UDP 无任何权限成本; 收包方
    复用 LoginWatcher 的跨线程窗口调用模式. 监听端口被占时静默降级 ——
    单实例仍由 flock 保证, 仅丢失"自动弹窗"能力.
    """
    global _mac_lock_fd
    if not getattr(sys, "frozen", False):
        return  # 源码运行不限制 (与 Windows 开发态行为一致)
    import fcntl
    import socket

    os.makedirs(os.path.dirname(_MAC_LOCK_PATH), exist_ok=True)
    lock_fd = open(_MAC_LOCK_PATH, "w")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # 已有实例: 通知其显示窗口后本进程退出 (锁句柄即弃).
        # 盲发 3 次覆盖首实例尚未完成回调注册的启动竞态窗口.
        lock_fd.close()
        for _ in range(3):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.sendto(b"show", ("127.0.0.1", _MAC_NOTIFY_PORT))
            except OSError:
                pass
            time.sleep(0.4)
        sys.exit(0)
    _mac_lock_fd = lock_fd

    def _listen() -> None:
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.bind(("127.0.0.1", _MAC_NOTIFY_PORT))
                    while True:
                        if s.recvfrom(64)[0].strip() == b"show":
                            fn = _udp_show_ref.get("fn")
                            if callable(fn):
                                fn()
            except Exception:  # noqa: BLE001  端口被占/瞬断: 退避后重建, 不永久失效
                time.sleep(2)

    threading.Thread(target=_listen, daemon=True, name="gousage-single-instance").start()


def _screen_visible_frame_logical() -> tuple[int, int]:
    """macOS 主屏可用区域 (逻辑像素, 已排除菜单栏/Dock): 初始窗口不超屏.

    与 Windows 的 SPI_GETWORKAREA 对应; 旧 MacBook Air (1366x768) 上
    固定 1280x840 会底部溢出, 必须按可用区域钳制.
    """
    try:
        from AppKit import NSScreen

        vf = NSScreen.mainScreen().visibleFrame()
        return max(1, int(vf.size.width)), max(1, int(vf.size.height))
    except Exception:  # noqa: BLE001
        return WINDOW_SIZE


def _win_frame_path() -> str:
    """窗口 frame 记录文件路径 (数据目录内)."""
    return os.path.join(db.data_dir(), "window.json")


def _save_window_frame(win) -> None:
    """记录主窗口位置尺寸 (仅 macOS): 关到菜单栏/退出前调用."""
    if not (_IS_MAC and win is not None):
        return
    try:
        frame = {
            "x": int(win.x), "y": int(win.y),
            "width": int(win.width), "height": int(win.height),
        }
        with open(_win_frame_path(), "w", encoding="utf-8") as fh:
            json.dump(frame, fh)
    except Exception:  # noqa: BLE001  窗口未就绪/磁盘异常均不影响主流程
        pass


def _load_window_frame(max_w: int, max_h: int) -> Optional[dict]:
    """读取上次窗口 frame 并做校验; 无有效记录返回 None.

    x/y 直接沿用上次值 (保存/恢复均走 pywebview 自身坐标系, 往返一致);
    宽高按当前主屏可用区域钳制, 防止换小屏后溢出.
    """
    try:
        with open(_win_frame_path(), "r", encoding="utf-8") as fh:
            d = json.load(fh)
        x, y = int(d["x"]), int(d["y"])
        if not (-max_w < x < 100000 and -100 < y < 100000):
            return None  # 明显异常值 (多屏热插拔等): 回退默认居中
        return {
            "x": x, "y": y,
            "width": min(int(d["width"]), max_w),
            "height": min(int(d["height"]), max_h),
        }
    except Exception:  # noqa: BLE001  文件不存在/损坏/字段缺失
        return None


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

_MAIN_LOG_MAX = 512 * 1024  # 超过后轮转一次 (保留 .old 一份), 防无限增长


def _main_log_path() -> str:
    """日志放数据目录: 含 workspace 等运行信息, 不再写公共 /tmp."""
    try:
        return os.path.join(db.data_dir(), "gousage_main.log")
    except Exception:  # noqa: BLE001  db 未就绪等极端情况回退 /tmp
        return os.path.join(tempfile.gettempdir(), "gousage_main.log")


def _mlog(msg: str) -> None:
    """主流程日志 (exe 无控制台, 落盘便于排查), 带时间戳 + 超限轮转."""
    try:
        path = _main_log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            if os.path.getsize(path) > _MAIN_LOG_MAX:
                os.replace(path, path + ".old")
        except OSError:
            pass
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%m-%d %H:%M:%S ") + msg + "\n")
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



def _arm_quit_fallback(timeout: float = 3.0) -> None:
    """退出兜底: 若 destroy 全部窗口后事件循环未在限时内退出, 强制结束进程.

    pywebview cocoa 在最后一个窗口关闭时会 stop 事件循环, 正常路径无需兜底;
    但若 WebView 进程异常 (崩溃/挂起) 导致循环不退出, 兜底保证应用不会变成
    "隐形进程" 只能强杀. 强退前先执行 shutdown() (停 server/关库连接,
    WAL 落盘 checkpoint), 避免 os._exit 绕过 atexit 造成数据未落盘.
    """
    def _force_quit() -> None:
        try:
            shutdown()
        except Exception:  # noqa: BLE001
            pass
        os._exit(0)

    # 注意: threading.Timer 不接受 name/daemon 关键字 (Py3.9 实测 TypeError,
    # 会导致兜底未武装就抛异常、退出流程中断), 属性需在实例上设置.
    timer = threading.Timer(timeout, _force_quit)
    timer.name = "gousage-quit-fallback"
    timer.daemon = True
    timer.start()


def _prepare_mac_terminate() -> None:
    """macOS Cmd+Q / Dock Quit / 菜单 Quit 的退出前置 (P3-18).

    pywebview 的 js_api / 事件回调线程是**非 daemon** 的, 且其内部原生调用
    有无超时等待: 某个 bridge 线程若卡在原生信号量上, 窗口全部销毁后进程会在
    解释器 shutdown 的 thread join 上挂住 (界面消失但进程残留, 只能强杀).
    托盘退出/前端退出早已武装 os._exit 兜底, 这里让 Cmd+Q 路径也一致 ——
    先置退出标志 (让 on_closing 放行), 再武装 3s 强制退出.
    """
    global _quitting
    _quitting = True
    _arm_quit_fallback()


# ── 单实例检测 (仅 Windows: Win32 命名互斥体; macOS 不走此路径) ──
_LOCK_FILE_NAME = "GoGauge.lock"
_MUTEX_NAME = "GoGauge_SingleInstance_Mutex"
_ERROR_ALREADY_EXISTS = 183  # GetLastError: 命名对象已存在
_ACTIVATE_RETRY_INTERVAL = 0.5  # 激活旧实例窗口的重试间隔(秒)
_SINGLE_INSTANCE_WAIT_SEC = 8.0  # 快速重启竞态: 等待旧实例释放互斥体的最长时间
_SW_SHOW = 5
_SW_RESTORE = 9
_MB_ICONINFORMATION = 0x40
_VK_MENU = 0x12  # ALT 虚拟键码
_KEYEVENTF_KEYUP = 0x0002

_mutex_handle = None  # 首实例持有的互斥体句柄 (全局引用防回收, 进程退出由内核自动释放)


def _is_process_running(pid: int) -> bool:
    """检查指定 PID 的进程是否存活.

    Args:
        pid: 目标进程ID
    Returns:
        True=进程存活 False=已退出
    """
    # 0x1000 = PROCESS_QUERY_LIMITED_INFORMATION, 权限要求最低
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def _get_process_image_name(pid: int) -> str:
    """获取进程可执行文件完整路径, 用于确认锁文件 PID 是否仍属于 GoGauge.

    Args:
        pid: 目标进程ID
    Returns:
        可执行文件路径; 权限不足/进程不存在返回空串
    """
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(1024)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _is_gogauge_process(pid: int) -> bool:
    """确认指定 PID 的进程确为本程序 (打包 GoGauge.exe, 开发 python.exe).

    进程崩溃后锁文件残留, 其 PID 可能被系统其他进程复用. 仅凭"进程存活"会误判为
    旧实例仍在运行, 进而拦截新实例导致无法启动. 必须同时校验进程可执行文件名.
    """
    name = os.path.basename(_get_process_image_name(pid)).lower()
    if getattr(sys, "frozen", False):
        return "gogauge" in name
    return name.startswith("python")


def _activate_existing_instance(old_pid: int) -> bool:
    """激活已运行实例的主窗口.

    窗口可能被隐藏到托盘 (IsWindowVisible=False), 不能按可见性过滤,
    改为枚举窗口, 按标题优先匹配主窗口 (页面 title 恒为 GoGauge).

    Args:
        old_pid: 已运行实例的进程ID; 0 表示不限定进程, 按标题全局匹配 (锁文件失效时兜底)
    Returns:
        True=找到并激活窗口 False=未找到任何窗口
    """
    user32 = ctypes.windll.user32
    candidates: list[tuple[int, str]] = []  # (窗口句柄, 窗口标题)

    # 回调签名必须用 HWND/LPARAM (64位系统下指针宽度), 用 c_int 会截断且吞异常
    @ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def _on_window(hwnd, _lparam):
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if old_pid == 0 or pid.value == old_pid:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value:  # 过滤 WinForms 无标题的消息窗口
                candidates.append((hwnd, buf.value))
        return True

    user32.EnumWindows(_on_window, 0)
    # 优先主窗口: 标题含 GoGauge 且非登录窗; 找不到再退回任一候选
    hwnd = next((h for h, t in candidates if "GoGauge" in t and "Login" not in t), 0)
    if not hwnd:
        hwnd = next((h for h, t in candidates if "GoGauge" in t), 0)
    if not hwnd:
        return False
    # 隐藏窗口用 SW_SHOW 唤起, 最小化窗口用 SW_RESTORE 还原
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, _SW_RESTORE)
    else:
        user32.ShowWindow(hwnd, _SW_SHOW)
    # 后台进程直接 SetForegroundWindow 会被系统前台锁拒绝, 先模拟一次 ALT 击键绕过
    user32.keybd_event(_VK_MENU, 0, 0, 0)
    user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(hwnd)
    return True


def _read_valid_lock_pid() -> int:
    """读取锁文件中的首实例 PID 并校验有效性.

    Returns:
        有效的 GoGauge 进程ID; 锁文件不存在/损坏/PID 已失效时返回 0
    """
    try:
        lock_path = os.path.join(tempfile.gettempdir(), _LOCK_FILE_NAME)
        if os.path.isfile(lock_path):
            with open(lock_path, "r") as fh:
                pid = int(fh.read().strip())
            if _is_process_running(pid) and _is_gogauge_process(pid):
                return pid
    except (ValueError, OSError):
        pass
    return 0


def _ensure_single_instance() -> None:
    """单实例守卫: 命名互斥体原子判定, 已有实例时激活其窗口并结束当前进程.

    主判定用内核命名互斥体 (CreateMutexW): 创建是否冲突由内核原子保证,
    无锁文件方案的竞态窗口 (双击过快/系统卡顿时两个实例互相看不到对方),
    进程崩溃时内核自动回收互斥体, 无残留无 PID 复用问题.
    锁文件降级为辅助: 记录首实例 PID 供激活窗口定位; 失效时按标题全局枚举兜底.

    快速重启竞态处理 (上游 v2.2.0): 用户退出后立刻再次双击时, 旧进程可能仍在
    收尾 (atexit 关服务器/数据库), 窗口已销毁但互斥体尚未释放 — 旧版此时会
    激活一个不存在的窗口后直接退出, 表现为"连开两次窗口都闪退, 第三次才
    正常"。现在激活不到可见窗口时, 先按重试节奏继续尝试 (覆盖旧实例 onefile
    解压/启动中窗口未创建的场景), 到最后再等待互斥体释放 (最多
    _SINGLE_INSTANCE_WAIT_SEC), 由当前进程接管成为首实例, 避免空启动。
    """
    global _mutex_handle
    # use_last_error=True: ctypes 每次调用后私有捕获错误码, 避免被 Python 中间系统调用污染
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    deadline = time.time() + _SINGLE_INSTANCE_WAIT_SEC
    while True:
        handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        if ctypes.get_last_error() != _ERROR_ALREADY_EXISTS:
            # 首实例: 持有互斥体 (全局引用防回收, 进程退出由内核自动释放)
            _mutex_handle = handle
            # 锁文件记录当前 PID, 供后续实例激活窗口定位
            try:
                with open(os.path.join(tempfile.gettempdir(), _LOCK_FILE_NAME), "w") as fh:
                    fh.write(str(os.getpid()))
            except OSError:
                _mlog("[single-instance] 写锁文件失败")
            return
        if handle:
            kernel32.CloseHandle(handle)
        # 已有实例在运行: 激活其窗口后退出 (托盘隐藏窗口也能被找到并唤起)
        if _activate_existing_instance(_read_valid_lock_pid()):
            sys.exit(0)
        if time.time() >= deadline:
            # 超时仍定位不到窗口 (极端情况): 提示从托盘操作
            ctypes.windll.user32.MessageBoxW(
                0, "GoGauge 已在运行, 请从系统托盘打开窗口。", "GoGauge", _MB_ICONINFORMATION
            )
            sys.exit(0)
        # 旧实例找不到窗口 (可能正在退出): 等互斥体释放后由本进程接管
        _mlog("[single-instance] no visible window on existing instance, wait for release")
        time.sleep(_ACTIVATE_RETRY_INTERVAL)


_TRAY_I18N = {
    "zh": {
        "show": "显示窗口", "quit": "退出",
        "today_label": "今日", "req_unit": "次",
        "remaining_prefix": "剩余 ",
        "not_login": "未登录 · 打开窗口登录",
    },
    "en": {
        "show": "Show Window", "quit": "Quit",
        "today_label": "Today", "req_unit": "req",
        "remaining_prefix": "left ",
        "not_login": "Not logged in",
    },
}


def _tray_lang() -> str:
    """菜单栏菜单语言: macOS 跟随系统首选语言, 其余平台默认中文."""
    if not _IS_MAC:
        return "zh"
    try:
        from AppKit import NSUserDefaults

        langs = NSUserDefaults.standardUserDefaults().stringArrayForKey_("AppleLanguages") or []
        first = str(langs[0]).lower() if langs else ""
        return "en" if first.startswith("en") else "zh"
    except Exception:  # noqa: BLE001
        return "zh"


class TrayIcon:
    """系统托盘/菜单栏图标 (pystray): 显示窗口 + 今日用量面板 + 退出 菜单.

    Windows: 在后台线程运行 pystray 自己的事件循环.
    macOS: AppKit 必须在主线程, 且需与 pywebview 共享同一个 NSApplication 事件循环,
    因此在主线程构造图标后调用 run_detached() 注册, 由 webview.start() 驱动菜单栏;
    图标使用 template 模式 (单色剪影), 自动适配深浅色菜单栏.
    """

    _REFRESH_SEC = 30  # 面板数据刷新间隔
    # 面板固定槽位数: 1 行今日用量 + 最多 3 条配额窗口行 (见 _fetch_rows)
    _PANEL_SLOTS = 4
    # 首次刷新前的让位时间: 等 pystray 自己的 _mark_ready()->update_menu() 落地,
    # 避免启动瞬间两个线程同时重建原生菜单 (Win32 DestroyMenu/CreatePopupMenu
    # 不是线程安全的). 面板数据晚 0.5s 出现, 之后每 _REFRESH_SEC 刷新一次.
    _STARTUP_GRACE_SEC = 0.5

    def __init__(self, icon_path: str) -> None:
        self._icon_path = icon_path
        self._icon = None
        self._win_getter = None
        self._lang = "zh"
        # 面板行文本缓存: 仅刷新线程整体替换, 菜单 callable 只读 (见 _info_items)
        self._rows: list[str] = []

    def bind_window(self, getter) -> None:
        self._win_getter = getter

    def _fetch_rows(self) -> list[str]:
        """构建面板行文本 (取数集中在这里, 只在后台刷新线程调用).

        与旧 _info_items 的取数与文案完全一致: 未登录只出一行提示, 已登录出
        用量行 + 最多 3 条配额窗口行; 异常吞掉 (数据未就绪时面板行省略).
        """
        t = _TRAY_I18N.get(self._lang, _TRAY_I18N["zh"])
        rows: list[str] = []
        try:
            if db.get_token():
                today = db.totals("today") or {}
                cost = float(today.get("total_cost_usd") or 0.0)
                req = int(today.get("request_count") or 0)
                rows.append(f"{t['today_label']}: ${cost:.2f} · {req} {t['req_unit']}")
                # 读 server 配额缓存 (只读跨线程安全); 未就绪时自然缺省.
                # 缓存结构为 {account_id: {at, data}}, 需按活跃账号取内层
                quota = (getattr(server, "_quota_cache", {})
                         .get(db.get_active_account_id()) or {}).get("data") or {}
                for w in (quota.get("windows") or [])[: self._PANEL_SLOTS - 1]:
                    label = str(w.get("label") or "").strip()
                    remaining = w.get("remaining")
                    if label and isinstance(remaining, (int, float)):
                        rows.append(f"{label}: {t['remaining_prefix']}{remaining:.0f}%")
            else:
                rows.append(t["not_login"])
        except Exception:  # noqa: BLE001  数据未就绪时面板行省略
            pass
        return rows[: self._PANEL_SLOTS]

    def _info_items(self, pystray) -> list:
        """今日用量快捷面板行 (灰显不可点): 免开主窗即可瞄一眼用量.

        固定 _PANEL_SLOTS 个槽位, text/visible 均为 callable: pystray 只在
        update_menu() 时求值它们 (_base.MenuItem.text -> _wrap, Menu.items ->
        _visible_items), 所以刷新只需换掉 self._rows, 菜单描述本身不必重建.
        求值发生在重建/打开菜单时 (macOS 在 AppKit 侧), 因此这里只允许读内存
        缓存 —— 绝不执行 SQL 或原生调用.

        空槽位 visible=False: 行数不足时不渲染 (pystray 顺带合并相邻分隔符,
        面板整体为空时的菜单形态与旧实现相同).
        """
        def make(idx: int):
            def text(_item=None) -> str:
                rows = self._rows  # 单次取引用: 刷新线程整体替换, 不会读到半更新状态
                return rows[idx] if idx < len(rows) else ""

            def visible(_item=None) -> bool:
                return idx < len(self._rows)

            return pystray.MenuItem(text, None, enabled=False, visible=visible)

        return [make(i) for i in range(self._PANEL_SLOTS)]

    def _refresh_once(self) -> None:
        """取数 -> 换缓存 -> 重建菜单 (cocoa 的 NSMenu 是快照, 必须重建才重新求值).

        异常一律吞掉: 离线/DB 未就绪只让面板行短暂缺失, 不能拖死刷新线程.
        """
        try:
            self._rows = self._fetch_rows()
        except Exception:  # noqa: BLE001
            self._rows = []
        try:
            if self._icon and not _quitting:
                self._icon.update_menu()
        except Exception:  # noqa: BLE001
            pass

    def _refresh_loop(self) -> None:
        """周期刷新面板数据: 取数在后台线程, 菜单 callable 只读缓存."""
        time.sleep(self._STARTUP_GRACE_SEC)
        while not _quitting:
            self._refresh_once()
            time.sleep(self._REFRESH_SEC)

    def start(self) -> bool:
        global _tray_ready
        try:
            from PIL import Image
            import pystray

            if not os.path.isfile(self._icon_path):
                return False
            img = Image.open(self._icon_path).convert("RGBA")
            self._lang = _tray_lang()
            t = _TRAY_I18N.get(self._lang, _TRAY_I18N["zh"])
            # 首帧用空占位行建菜单 (self._rows 此时为空, 槽位 visible=False 不渲染):
            # 托盘取数全部由 _refresh_loop 在后台线程完成, 启动路径不因 DB/钥匙串
            # 阻塞主线程; 数据就绪后再 update_menu() 让 callable 文本生效.
            menu = pystray.Menu(
                pystray.MenuItem(t["show"], self._show, default=True),
                pystray.Menu.SEPARATOR,
                *self._info_items(pystray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(t["quit"], self._quit),
            )
            self._icon = pystray.Icon("GoGauge", img, "GoGauge - OpenCode Go 用量面板", menu)
            if _IS_MAC:
                # macOS: 主线程构造(Icon 里创建 NSStatusItem/NSWindow 需在主线程),
                # run_detached 仅注册, 不启动独立 run loop, 由 pywebview 驱动.
                self._icon.run_detached(setup=lambda i: setattr(i, "visible", True))
                self._apply_template_image()
            else:
                # Windows / 其它: pystray 自带事件循环, 放入后台线程.
                threading.Thread(target=self._icon.run, daemon=True).start()
            threading.Thread(target=self._refresh_loop, daemon=True,
                             name="gousage-tray-refresh").start()
            _tray_ready = True
            return True
        except Exception as exc:  # noqa: BLE001
            _mlog(f"[tray] 托盘启动失败: {exc}")
            _tray_ready = False
            return False

    def _apply_template_image(self) -> None:
        """macOS 菜单栏图标转 template 模式 (按 alpha 渲染单色剪影).

        彩色 logo 在深色菜单栏上突兀; template 由系统自动黑/白反色.
        pystray 未暴露该能力, 直接改其内部 NSImage (_icon_image 引用被
        后续 setImage_ 复用, 原地 setTemplate_ 即可持续生效).
        """
        try:
            nsimg = getattr(self._icon, "_icon_image", None)
            if nsimg is not None:
                nsimg.setTemplate_(True)
        except Exception:  # noqa: BLE001  失败则保持彩色原图
            pass

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
                if _IS_MAC:
                    _mac_activate_app()

    def _quit(self, icon=None, item=None) -> None:
        global _quitting
        _quitting = True
        _arm_quit_fallback()
        try:
            if self._win_getter:
                _save_window_frame(self._win_getter())
        except Exception:  # noqa: BLE001
            pass
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

    def get_auth_token(self) -> str:
        """主窗口前端在 URL fragment 丢失时兜底获取本地 API token (I4 双保险).

        只读、无参数、不触发任何副作用. 登录窗口不挂 js_api, 主窗口只加载本地
        页面 (fragment 本身也不进 HTTP 请求行/Referer/日志), 因此不会把 token
        交给外部站点. 未设置 token (dev/浏览器模式) 返回空串.
        """
        return _auth_token_ref.get("token", "")

    def open_login(self, mode: str = "relogin", provider: str = "opencode") -> bool:
        """前端登录入口: 弹出独立登录窗口. mode: "add"=添加新用户 / "relogin"=重登当前用户."""
        if self._on_open_login:
            self._on_open_login(
                mode if mode in ("add", "relogin") else "relogin",
                provider if provider in ("opencode", "commandcode") else "opencode",
            )
        return True

    def open_login_external(self, provider: str = "opencode") -> bool:
        """系统默认浏览器打开登录页 (内置 WebView 白屏/被 Cloudflare 质询时的兜底):
        用户在外部浏览器完成登录后, 从 DevTools 复制 Cookie 粘贴回来."""
        import webbrowser
        try:
            webbrowser.open(build_login_url(
                provider if provider in ("opencode", "commandcode") else "opencode"
            ))
        except Exception:  # noqa: BLE001
            return False
        return True

    def minimize(self) -> bool:
        if self._win:
            self._win.minimize()
        return True

    def pick_save_path(self, default_name: str = "gogauge-export.csv") -> Optional[str]:
        """系统保存对话框 (导出用); 用户取消返回 None.

        浏览器环境 (无 pywebview 窗口) 返回 None, 前端据此提示需要桌面客户端.
        """
        try:
            import webview

            win = self._win or (webview.windows[0] if webview.windows else None)
            if win is None:
                return None
            result = win.create_file_dialog(webview.SAVE_DIALOG, save_filename=default_name)
            # pywebview 各后端返回 list/tuple/str 不一, 统一取第一个非空项
            if isinstance(result, (list, tuple)):
                picked = str(result[0]) if result else None
            else:
                picked = str(result) if result else None
            # 登记为用户亲自选定的保存路径: /api/export/* 只认登记过的路径, 避免
            # 本机任意进程借本应用覆写任意文件 (confused deputy)
            if picked:
                server.approve_path(picked, server.APPROVAL_SAVE)
            return picked
        except Exception:  # noqa: BLE001
            return None

    def pick_open_path(self) -> Optional[str]:
        """系统打开对话框 (导入备份用); 用户取消返回 None."""
        try:
            import webview

            win = self._win or (webview.windows[0] if webview.windows else None)
            if win is None:
                return None
            result = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("GoGauge 备份 (*.json.gz;*.gz)", "所有文件 (*.*)"),
            )
            if isinstance(result, (list, tuple)):
                picked = str(result[0]) if result else None
            else:
                picked = str(result) if result else None
            # 同 pick_save_path, 但用途是"打开": 这样登记的路径只能被导入读取,
            # 不能被导出覆写 (用户点头的是读它, 不是覆盖它)
            if picked:
                server.approve_path(picked, server.APPROVAL_OPEN)
            return picked
        except Exception:  # noqa: BLE001
            return None

    def move_by(self, dx: float, dy: float) -> bool:
        """标题栏拖动(增量): dx/dy 为屏幕物理像素增量, 直接换算窗口位置.

        自实现拖动替代 pywebview easy_drag: easy_drag 的 JS 用 clientX 记录起点、
        screenX 计算增量 (两坐标系在 DPI 缩放下不同源), 后端 move() 又把参数
        乘一次 DPI 缩放, 高 DPI 屏幕上拖动会漂移抽动. 这里 JS 端 screenX 增量
        已是物理像素, GetWindowRect/SetWindowPos 同为物理坐标, 全程 1:1 跟随.

        加锁: js_api 高频触发时多个调用可能并发进入, 并发读-写会让多个线程
        读到同一旧位置、各自 SetWindowPos, 增量被覆盖丢失 (实测 50 次调用
        只移动了 34 段). 锁保证 GetWindowRect→SetWindowPos 原子, 每次移动
        都基于最新位置.
        """
        try:
            native = self._win.native
            hwnd = int(native.Handle.ToInt32())
            with _move_lock:
                rect = _RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                ctypes.windll.user32.SetWindowPos(
                    hwnd, None, rect.left + int(dx), rect.top + int(dy),
                    0, 0, 0x0001 | 0x0004,  # SWP_NOSIZE | SWP_NOZORDER
                )
        except Exception:  # noqa: BLE001
            pass
        return True

    def close(self) -> bool:
        """关闭按钮: 托盘可用时最小化到托盘, 否则真正关闭."""
        if not self._win:
            return True
        if _quitting or not _tray_ready:
            _arm_quit_fallback()
            self._win.destroy()
        else:
            _save_window_frame(self._win)
            self._win.hide()  # 最小化到托盘
        return True

    def quit(self) -> bool:
        """退出应用 (欢迎页/设置页按钮): 真正退出, 不驻留托盘."""
        global _quitting
        _quitting = True
        _arm_quit_fallback()
        _save_window_frame(self._win)
        _destroy_all_windows()
        return True


def _main_window_close_verdict(hide_window, *, quitting: bool, tray_ready: bool) -> bool:
    """主窗口原生关闭 (macOS 红点 / Windows Alt+F4) 的裁决.

    返回 pywebview ``closing`` handler 的返回值: True = 允许真正关闭,
    False = 取消关闭并把窗口隐藏到托盘/菜单栏驻留.

    仅在托盘/菜单栏可用且非退出中时驻留; 否则放行 —— 托盘没起来时若还拒绝
    关闭, 窗口将彻底无法关闭 (只能强杀进程). Windows 上这条路径尤其重要:
    主窗口若被真正关闭并成为最后一个 pywebview 窗口, winforms 后端会
    Application.Exit() 结束整个进程 (登录窗口开着也会被一起带走).
    """
    if quitting or not tray_ready:
        return True
    try:
        hide_window()
    except Exception:  # noqa: BLE001 隐藏失败时放行关闭, 保证窗口关得掉
        return True
    return False


def _destroy_all_windows() -> None:
    """销毁所有窗口 (含隐藏登录窗), 让 pywebview 事件循环退出, 进程真正结束."""
    for w in list(webview.windows):
        try:
            w.destroy()
        except Exception:  # noqa: BLE001
            pass


def _persist_login_credential(
    auth_cookie: str,
    workspace_hint: str,
    provider: str,
    *,
    mode: str,
    target_account_id: Optional[int],
) -> bool:
    """按登录模式落库凭证, 返回是否成功 (P1-1).

    与旧行为的唯一区别: relogin 使用**发起登录时固化**的 ``target_account_id``,
    而不是回调时刻的活跃账号 —— 登录窗是非模态的, 用户可能在 OAuth 期间切换
    账号, 按活跃账号写会把 A 的新凭证写进 B, 并毁掉 B 的原凭证.

    - add 模式: 新增账号并切换为活跃 (原语义);
    - relogin + 目标账号存在: 只更新该账号; 目标账号已被删除时回退为新增
      (与"无活跃账号"兜底同语义, 避免凭证被静默丢弃);
    - relogin 但没拿到目标快照 (旧调用/DB 异常): 保持旧语义更新活跃账号.
    """
    if mode == "add":
        db.add_account(auth_cookie, workspace_hint, switch=True, provider=provider)
        return True
    # I1: save_token 支持按 id 写入并返回是否成功 (None = 更新活跃账号).
    # target_account_id 为 None 时保持旧的"更新活跃账号"语义 (I1 内部有
    # 无活跃账号的 add_account 兜底).
    if db.save_token(
        auth_cookie,
        workspace_hint,
        provider=provider,
        account_id=target_account_id,
    ):
        return True
    if target_account_id is None:
        return False  # 理论上不可达: 无目标时 I1 要么成功要么抛异常
    # 目标账号已被删除: 回退为新增账号, 避免本次登录凭证被静默丢弃.
    db.add_account(auth_cookie, workspace_hint, switch=True, provider=provider)
    return True


def _complete_login(
    auth_cookie: str,
    workspace_hint: str,
    provider: str,
    *,
    mode: str,
    target_account_id: Optional[int],
    after_save: Optional[Callable[[], None]],
    sync: Callable[[str], None],
    on_ui: Callable[[], None],
    log: Callable[[str], None],
) -> bool:
    """登录成功的落库与副作用顺序 (P2-10), 返回凭证是否保存成功.

    顺序固定为: 保存凭证 -> 后续清理 (配额缓存失效) -> **首次全量同步** -> UI 收尾.
    同步必须先于 UI: UI 调用是跨线程的 pywebview 方法, UI 线程被占时无超时阻塞,
    一旦卡住, 排在它后面的同步就永远不会触发 (新账号面板长时间空白).
    保存失败时: 不跑任何副作用并返回 False, 由调用方保持登录窗打开让用户重试 —
    不允许"窗口关了、界面刷新了、其实没存上"的假成功.
    """
    try:
        saved = _persist_login_credential(
            auth_cookie,
            workspace_hint,
            provider,
            mode=mode,
            target_account_id=target_account_id,
        )
    except Exception as exc:  # noqa: BLE001 DB 锁/磁盘满/账号并发删除
        log(f"  save_token ERROR: {exc}")
        saved = False
    if not saved:
        log("  credential NOT saved -> keep login window open for retry")
        return False
    log("  token saved")
    if after_save is not None:
        try:
            after_save()
        except Exception as exc:  # noqa: BLE001 缓存失效失败不影响已保存的凭证
            log(f"  post-save cleanup ERROR: {exc}")
    sync("full")
    on_ui()
    return True


def _log_runtime_banner() -> None:
    """把运行时版本写进主日志.

    登录链路的故障几乎都在 .NET/WebView2 边界上 (跨线程访问、SDK 与运行时
    版本差异), 而发布包的依赖版本此前未锁定、也无法从日志回看 —— 出问题时
    这一行就是"跑的是哪套栈"的唯一证据.
    """
    parts: list[str] = []
    for dist in ("pywebview", "pythonnet"):
        try:
            from importlib.metadata import version as _dist_version  # noqa: PLC0415

            parts.append(f"{dist}={_dist_version(dist)}")
        except Exception:  # noqa: BLE001 冻结包内无元数据/未安装
            pass
    if _IS_WIN:
        try:
            import winreg  # noqa: PLC0415

            key = (
                r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
                r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
            )
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
                parts.append(f"webview2={winreg.QueryValueEx(handle, 'pv')[0]}")
        except Exception:  # noqa: BLE001 未装 WebView2 运行时/注册表不可读
            parts.append("webview2=unknown")
        try:
            import clr  # noqa: F401, PLC0415 先导入 clr 才能用 System.*

            from System.Runtime.InteropServices import RuntimeInformation  # noqa: PLC0415

            parts.append(f"clr={RuntimeInformation.FrameworkDescription}")
        except Exception as exc:  # noqa: BLE001 无 pythonnet/CLR 起不来
            parts.append(f"clr=unavailable({type(exc).__name__})")
    if parts:
        _mlog("[main] runtime: " + " ".join(parts))


def _arm_watcher_fallback(watcher: dict, w) -> None:
    """兜底: shown 事件在打包环境可能不触发, 3s 后无条件启动登录监听.

    带当前 watcher 校验: 被 recreate 取代的旧 Timer 不拉起过期 watcher.
    daemon 必须设置 —— 用户在 3s 内退出时, 未触发的 Timer 若为普通线程会被
    threading._shutdown 一直 join 到自然结束: 实测让进程退出多等 3031 ms
    (daemon 版 18 ms). 注意 Timer 不接受 name/daemon 关键字参数 (Py3.9 实测
    TypeError), 属性只能在实例上设置 (同 _arm_quit_fallback).
    """
    timer = threading.Timer(3.0, lambda: watcher.get("ref") is w and w.start())
    timer.daemon = True
    timer.start()


def main() -> None:
    # HTTPS 根证书兜底: 冻结包内 OpenSSL 只认构建机的编译期 CA 路径, 用户机
    # 缺该路径时所有请求 CERTIFICATE_VERIFY_FAILED (见 app/https_ca.py).
    # 必须早于任何网络操作 (配额拉取/同步/更新检查) 安装.
    https_ca.install()

    # 单实例守卫: Windows 用命名互斥体, macOS 用 flock (源码运行均不限制).
    if _IS_WIN:
        _ensure_single_instance()
    else:
        _ensure_single_instance_mac()

    db.get_db()  # 初始化数据库
    # 版本号落在日志首行: 真机排查时先确认跑的到底是不是修复版
    _mlog(
        f"=== GoGauge {__version__} starting "
        f"(platform={sys.platform}, frozen={bool(getattr(sys, 'frozen', False))}) ==="
    )
    _log_runtime_banner()

    # I4: 本地 HTTP API token (WebView ↔ 本机 server 的唯一凭证). 用 URL fragment
    # 传给 WebView: fragment 不进入 HTTP 请求行/Referer, server 侧与日志都不会
    # 看到它; server 尚未实现 token 校验的版本上 set_auth_token 不存在, 此时
    # fragment 只被前端忽略 (兼容联调期).
    auth_token = secrets.token_urlsafe(32)
    _auth_token_ref["token"] = auth_token  # WindowApi.get_auth_token 兜底源
    host, port = server.start_server()
    _set_server_auth_token = getattr(server, "set_auth_token", None)
    if callable(_set_server_auth_token):
        _set_server_auth_token(auth_token)
    dashboard_url = f"http://{host}:{port}/#{auth_token}"
    watcher: dict[str, object] = {"ref": None}
    api = WindowApi()

    # 启动窗口: 始终加载本地页面; 未登录时前端显示欢迎页引导登录
    # 初始窗口尺寸:
    # - Windows: 无边框 + 自定义标题栏; 初始尺寸不超过屏幕工作区, 避免矮屏/高分屏
    #   底部被裁. 拖动由前端自实现 (js_api.move_by), 不再用 pywebview easy_drag
    #   (其 JS 用 clientX 记起点/screenX 算增量 + 后端再乘 DPI 缩放, 高 DPI 抽动).
    # - macOS: 原生标题栏 + 红黄绿交通灯 (frameless=False), 原生标题栏本身可拖动,
    #   无需 easy_drag; 尺寸按主屏可用区域钳制 (同 Windows 逻辑), 并恢复上次
    #   窗口位置尺寸 (换小屏时宽高自动收缩, 位置异常则回退默认).
    if _IS_WIN:
        wa_w, wa_h = _screen_workarea_logical()
    elif _IS_MAC:
        wa_w, wa_h = _screen_visible_frame_logical()
    else:
        wa_w, wa_h = WINDOW_SIZE
    win_w = min(WINDOW_SIZE[0], max(1, wa_w - 60))
    win_h = min(WINDOW_SIZE[1], max(1, wa_h - 60))
    saved_frame = _load_window_frame(win_w, win_h) if _IS_MAC else None
    if saved_frame:
        win_w, win_h = saved_frame["width"], saved_frame["height"]
    main_win = webview.create_window(
        APP_TITLE,
        dashboard_url,
        width=win_w,
        height=win_h,
        x=saved_frame["x"] if saved_frame else None,
        y=saved_frame["y"] if saved_frame else None,
        min_size=WINDOW_MIN_SIZE,
        frameless=(not _IS_MAC),
        # 显式关闭 easy_drag: 其默认值为 True, 不传会保持开启;
        # easy_drag 的 JS 用 clientX 记起点/screenX 算增量 + 后端再乘 DPI 缩放,
        # 高 DPI 屏幕拖动漂移抽动. 窗口拖动由前端自实现 (js_api.move_by, Windows);
        # macOS 由原生标题栏承担.
        easy_drag=False,
        js_api=api,
    )
    api.bind(main_win)
    _main_win_ref["win"] = main_win

    def show_main() -> None:
        """前置并恢复主窗口 (单实例唤起/Dock 重开共用)."""
        try:
            main_win.show()
            main_win.restore()
        except Exception:  # noqa: BLE001  窗口可能已销毁 (退出竞态)
            pass

    # 第二实例 UDP 唤起回调 (注册前收到的包会丢失, 仅启动竞态的极端情况)
    _udp_show_ref["fn"] = show_main

    # 独立登录子窗口延迟创建: 启动即建 about:blank 隐藏窗会白占一份 WebView
    # 进程内存; 首次"立即登录"才实例化 (被手动关闭后由 _recreate_login_window 重建).
    login_win_ref: dict[str, object] = {"win": None}

    def _bind_login_close_cleanup(win) -> None:
        """登录窗被手动关闭时: 停掉其监听线程并清理引用 (仅当引用仍指向该窗口).

        修复: 关闭登录窗后旧 Watcher 残留, 再次点击"添加账号/重新登录"被单飞守卫
        静默拦截导致弹不出窗口.
        """
        def _on_closed() -> None:
            w = watcher.get("ref")
            if isinstance(w, LoginWatcher) and getattr(w, "win", None) is win:
                w.stop()
                watcher["ref"] = None
                _mlog("  login window closed -> watcher cleaned")

        try:
            win.events.closed += _on_closed
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  bind login closed event error: {exc}")

    def login_win() -> object:
        w = login_win_ref["win"]
        if w is not None:
            try:
                if w in webview.windows:
                    return w
            except Exception:  # noqa: BLE001
                pass
        w = webview.create_window(
            "GoGauge - Login",
            "about:blank",
            width=720,
            height=640,
            min_size=(560, 500),
            hidden=True,
            background_color="#f7f6f4",
        )
        login_win_ref["win"] = w
        # 创建即绑定红叉关闭清理 (此前在启动时对 None 调用, 首个登录窗从未
        # 绑定, 关闭后 watcher 残留导致单飞守卫拦死后续登录).
        _bind_login_close_cleanup(w)
        return w

    # 登录模式: open_login(mode, provider) 记录意图, on_login_success 按模式落库.
    # account_id 必须在**发起登录时**固化: 登录窗是非模态的, 用户在 OAuth 期间
    # 切换活跃账号时, 回调里再解析活跃账号会把 A 的新凭证写进 B (并毁掉 B 的
    # 原凭证) —— 见 P1-1.
    pending_mode: dict[str, object] = {
        "mode": "relogin",
        "provider": "opencode",
        "account_id": None,
    }

    def _capture_pending_target(mode: str, provider: str) -> None:
        """固化本次登录意图 (必须在登录流程启动前调用)."""
        normalized_mode = mode if mode in ("add", "relogin") else "relogin"
        pending_mode["mode"] = normalized_mode
        pending_mode["provider"] = (
            provider if provider in ("opencode", "commandcode") else "opencode"
        )
        account_id: Optional[int] = None
        if normalized_mode == "relogin":
            try:
                account_id = db.get_active_account_id() or None
            except Exception as exc:  # noqa: BLE001 DB 未就绪: 退回旧语义 (回调时活跃账号)
                _mlog(f"[main] capture login target failed: {exc}")
        pending_mode["account_id"] = account_id

    def _notify_login_failed(message: str) -> None:
        """凭证落库失败: 保持登录窗打开, 尽力通知前端 (可选钩子, 失败只记日志)."""
        js = (
            "window.gousageOnLoginFailed && "
            f"window.gousageOnLoginFailed({json.dumps(message)});"
        )
        try:
            if not _bounded_ok(lambda: main_win.evaluate_js(js), _LOGIN_UI_CALL_TIMEOUT):
                _mlog("  login-failed notify skipped (UI busy)")
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  login-failed notify ERROR: {type(exc).__name__}")

    def _post_login_ui() -> None:
        """登录成功后的 UI 收尾 (顺序与旧实现一致: 先隐藏登录窗, 再刷新主窗).

        三处都是跨线程 pywebview 调用 (WinForms 上是 Invoke + 无超时信号量),
        一律经 _bounded_ok 有界执行: 超时只当"这次没做完", 前端登录监视
        (/api/accounts 轮询) 会兜底刷新; 绝不允许拖住监听线程或延后首次同步.
        """
        try:
            if _login_win_alive():
                if _bounded_ok(login_win_ref["win"].hide, _LOGIN_UI_CALL_TIMEOUT):
                    _mlog("  login window hidden")
                else:
                    _mlog("  login window hide skipped (UI busy)")
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  hide ERROR: {type(exc).__name__}")
        try:
            if _bounded_ok(lambda: main_win.load_url(dashboard_url), _LOGIN_UI_CALL_TIMEOUT):
                _mlog("  dashboard load_url called")
            else:
                _mlog("  dashboard load_url skipped (UI busy)")
        except Exception as exc:  # noqa: BLE001
            # 不打 URL (I4 的 fragment 是 token), 也不打可能夹带 URL 的异常原文
            _mlog(f"  load_url ERROR: {type(exc).__name__}")
        # 同 URL 的 load_url 可能被 WebView 跳过 (不重载): 显式通知前端就地刷新,
        # 否则停留在设置页时看不到新增账号 (需手动切页才会拉取)
        js = "window.gousageOnLoginSuccess && window.gousageOnLoginSuccess();"
        try:
            if _bounded_ok(lambda: main_win.evaluate_js(js), _LOGIN_UI_CALL_TIMEOUT):
                _mlog("  evaluate_js gousageOnLoginSuccess sent")
            else:
                _mlog("  evaluate_js skipped (UI busy)")
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  evaluate_js ERROR: {type(exc).__name__}")

    def _invalidate_login_quota_cache() -> None:
        """凭证已更换: 丢弃旧 token 的配额缓存槽 (after_save 阶段).

        否则面板在 TTL 内仍返回旧凭证的 401 结果, 看起来像"重新登录了但配额
        还是空的". 登录期间切号是合法的, 目标账号与当前活跃账号的槽都清.
        """
        target = pending_mode.get("account_id")
        for aid in {db.get_active_account_id(), target if isinstance(target, int) else None}:
            if aid:
                server.invalidate_quota_cache(int(aid))
        _mlog("  quota cache invalidated")

    def on_login_success(auth_cookie: str, workspace_hint: str, provider: str = "opencode") -> None:
        """登录成功: 按模式保存凭证 → 首次全量同步 → 隐藏登录窗/主窗刷新.

        - add: 新建账号 (同 provider+token 自动去重为既有账号) 并切换为活跃
        - relogin: 更新**发起登录时固化的**账号凭证 (P1-1; 中途切号也不会串号)

        保存失败不假装成功: 保持登录窗打开, 不触发同步与 UI 刷新 (P2-10).
        """
        mode = str(pending_mode.get("mode", "relogin"))
        target = pending_mode.get("account_id")
        target_account_id = target if isinstance(target, int) else None
        provider = provider if provider in ("opencode", "commandcode") else "opencode"
        _mlog(
            f"on_login_success: ws={workspace_hint} mode={mode} "
            f"provider={provider} target={target_account_id}"
        )
        watcher["ref"] = None  # 本次登录已完结: 释放单飞守卫占用
        ok = _complete_login(
            auth_cookie,
            workspace_hint,
            provider,
            mode=mode,
            target_account_id=target_account_id,
            after_save=_invalidate_login_quota_cache,
            sync=server.sync_all_async,
            on_ui=_post_login_ui,
            log=_mlog,
        )
        if not ok:
            _notify_login_failed("登录凭证保存失败, 请重试")

    def _stale_credential_fps(provider: str) -> list[str]:
        """该 provider 名下已知凭证的指纹 (库内旧 token).

        登录窗口是复用的, WebView cookie store 里留着上一轮/上一账号的会话;
        命中这些指纹的凭证是"登录前就有的", 不能算作本次登录的结果.
        """
        try:
            return db.list_provider_token_fps(provider)
        except Exception:  # noqa: BLE001 查不到就不拦截 (仍有 baseline 比对兜底)
            return []

    def _stale_credential_snapshot(lw, provider: str) -> Optional[str]:
        """登录窗口打开瞬间 store 里已有的凭证 = 残留会话基线.

        必须在加载登录页之前、且不在主线程调用: pywebview 的 get_cookies 用
        无超时信号量等主线程回调, 主线程调用会死锁. 读不到时返回 None, 由
        数据库旧凭证指纹继续兜底.
        """
        if threading.current_thread() is threading.main_thread():
            return None
        try:
            return read_provider_cookie(lw, provider)
        except Exception:  # noqa: BLE001 窗口未就绪等
            return None

    def _start_watcher(lw, provider: str = "opencode", snapshot_stale: bool = True) -> None:
        """启动登录监听: 优先等 shown 事件 (避免 hidden 窗口调用窗口方法抛内部异常);
        复用窗口 (已显示过) 直接启动; 事件不触发时 3s 兜底启动 (LoginWatcher 对未就绪窗口有重试).

        snapshot_stale: 是否采集"残留会话基线". 仅复用窗口需要 —— 新建窗口在
        _recreate_login_window 里刚清过残留 cookie (基线必为空), 且此时 BrowserView
        尚未实例化, 读取只会卡到超时.
        """
        def _on_cancelled() -> None:
            # 监听线程退出 (窗口被关/自愈) 后释放单飞守卫引用
            if watcher.get("ref") is w_ref["self"]:
                watcher["ref"] = None
                _mlog("  watcher exited -> ref cleared")

        w_ref: dict[str, object] = {}
        baseline = _stale_credential_snapshot(lw, provider) if snapshot_stale else None
        w = LoginWatcher(
            lw, provider, on_login_success,
            on_cancelled=_on_cancelled,
            stale_fps=_stale_credential_fps(provider),
            baseline_value=baseline,
        )
        w_ref["self"] = w
        watcher["ref"] = w
        if getattr(lw, "_gousage_shown", False):
            w.start()
            _mlog("  watcher started (reused window)")
            return

        def on_shown() -> None:
            setattr(lw, "_gousage_shown", True)
            # 复用窗口时旧 shown 闭包仍挂在事件列表上: 仅当自己仍是当前 watcher 才启动
            if watcher.get("ref") is w:
                w.start()
                _mlog("  watcher started (shown event)")

        # 同一窗口只注册一次 shown 监听: 复用窗口重复 += 会累积旧闭包 (泄漏)
        if not getattr(lw, "_gousage_shown_bound", False):
            setattr(lw, "_gousage_shown_bound", True)
            try:
                lw.events.shown += on_shown
            except Exception as exc:  # noqa: BLE001
                _mlog(f"  shown event register error: {exc}")
        # 兜底: shown 事件在打包环境可能不触发, 3s 后无条件启动监听 (带当前
        # watcher 校验, 且 Timer 必须 daemon —— 见 _arm_watcher_fallback)
        _arm_watcher_fallback(watcher, w)

    def _login_win_alive() -> bool:
        """只读检查登录窗是否存活 (不触发创建副作用, 否则恒为 True 使重建分支失效)."""
        w = login_win_ref["win"]
        if w is None:
            return False
        try:
            return w in webview.windows
        except Exception:  # noqa: BLE001
            return False

    def _prepare_login_session(provider: str, win=None) -> None:
        """加载登录页之前清掉该 provider 域的残留会话.

        pywebview 只在 create_window 时清理网站数据 (private_mode), 而登录窗口
        是复用的 (hide/show): 上一轮的会话 cookie 仍在 store 里, 登录页会据旧
        凭证直接跳转后台 (无法重新选择账号), LoginWatcher 也会把这份残留凭证
        误判为本次登录成功 (窗口秒关 + 凭证未刷新).

        win: 目标登录窗口的引用, 供 Windows 用 WebView2 CookieManager 按域清理
        (传 None 或窗口已销毁时, 内部借任一存活窗口 —— cookie store 进程内共享).
        """
        try:
            purged = clear_provider_cookies(provider, win)
            _mlog(f"[main] login session prepared (purged {purged} stale cookie(s))")
        except Exception as exc:  # noqa: BLE001 清理失败不阻断登录
            _mlog(f"[main] cookie purge ERROR: {exc}")

    def open_login(mode: str = "relogin", provider: str = "opencode") -> None:
        """弹出独立登录窗口并开始监听 (欢迎页/设置页按钮).

        并发保护 (P2-10): pywebview 的 js_api 每次调用都在新线程里, 快速双击会
        并发进入本函数 —— 单飞守卫的 watcher["ref"] 要等窗口创建/清残留 cookie
        之后才写入, 挡不住这段窗口期, 结果是两个登录窗口/两个 watcher (其中
        一个窗口的登录永远不会被捕获). 这里用非阻塞锁把"守卫 + 清残留 + 建窗
        + 起 watcher"整体串行化, 重复点击直接忽略 (与单飞守卫同语义).
        """
        if not _LOGIN_OPEN_LOCK.acquire(blocking=False):
            _mlog("[main] open_login ignored: another login flow is starting")
            return
        try:
            _open_login_locked(mode, provider)
        finally:
            _LOGIN_OPEN_LOCK.release()

    def _open_login_locked(mode: str = "relogin", provider: str = "opencode") -> None:
        """open_login 的实际流程 (调用方已持有 _LOGIN_OPEN_LOCK)."""
        if provider not in ("opencode", "commandcode"):
            provider = "opencode"
        # 登录窗已被手动关闭 => 旧监听已失效: 先停旧线程再重建窗口.
        # (修复: 依赖"线程存活"的单飞守卫会把死窗口场景永久拦截, 导致再次点击无响应)
        if not _login_win_alive():
            w = watcher.get("ref")
            if isinstance(w, LoginWatcher):
                w.stop()
            watcher["ref"] = None
            _mlog("[main] login window gone -> recreate")
            _capture_pending_target(mode, provider)
            _recreate_login_window(provider)
            return
        w = watcher.get("ref")
        if isinstance(w, LoginWatcher) and w._thread and w._thread.is_alive() and not w.done:
            # 线程存活但窗口已死 = 僵尸监听 (红叉关闭后 closed 清理未生效的历史残留):
            # 停掉并继续正常弹出, 不再静默拦截.
            if not _login_win_alive():
                w.stop()
                watcher["ref"] = None
                _mlog("[main] zombie watcher stopped (thread alive, window gone)")
            elif w.seconds_since_tick() > _LOGIN_WATCHER_STALE_SEC:
                # 窗口还在、线程也活着, 但很久没有轮询进展 = 某次原生调用把它挂住
                # 了 (正常情况下这个值只有零点几秒). 不处理的话单飞守卫会永久
                # 静默吞掉后续每一次点击, 用户看到的就是"点登录没反应".
                _mlog(
                    f"[main] zombie watcher stopped (no poll progress for "
                    f"{w.seconds_since_tick():.0f}s) -> recreate window"
                )
                w.stop()
                watcher["ref"] = None
                stale = login_win_ref["win"]
                if stale is not None:
                    try:
                        stale.destroy()
                    except Exception as exc:  # noqa: BLE001 已被用户关闭
                        _mlog(f"[main] stale login window destroy: {exc}")
                    login_win_ref["win"] = None
            else:
                _mlog(f"[main] open_login ignored: login in progress (provider={provider})")
                return
        _capture_pending_target(mode, provider)
        lw = login_win()
        # 清残留会话必须在加载登录页之前完成: 否则登录页带着旧凭证请求, 会被
        # 直接带到套餐后台, 用户根本没有重新选择账号的机会
        _prepare_login_session(provider, lw)
        try:
            lw.show()
            if _IS_WIN:
                # Windows 走上游的登录链路: 显示窗口 → 直接导航到登录页, 不再
                # 装加载看门狗/入口重置 (见 _arm_login_window 的说明)
                lw.load_url(build_login_url(provider))
        except Exception as exc:  # noqa: BLE001 窗口可能被用户手动关闭, 重建
            _mlog(f"[main] login window reopen: {exc}")
            _recreate_login_window(provider)
            return
        _start_watcher(lw, provider)
        if _IS_MAC:
            _arm_login_window(lw, provider)

    def _login_still_pending() -> bool:
        """本次登录是否还没拿到凭证 (允许重置会话的前提).

        watcher 引用为 None 或 done=True 都说明登录已成功/已清理: 此时页面上
        的"离开登录入口"是登录成功的正常跳转, 绝不能清会话 (会把刚建立的
        会话清掉).
        """
        w = watcher.get("ref")
        return isinstance(w, LoginWatcher) and not w.done

    def _arm_login_window(lw, provider: str) -> None:
        """macOS 专用: 后台装请求拦截 → 打开登录页 → 盯加载进度.

        1. rule list 只对之后的请求生效, 必须在导航前装好;
        2. 登录页引用的追踪域在部分网络下不可达, 会让加载卡在半途 (实测窗口
           一直纯白), 由 ensure_login_page_loaded 停滞超时后主动 reload 救回;
        3. 放后台线程, 避免编译规则/看门狗的等待阻塞 open_login 的调用方.

        Windows 不做这一层 (导航在 open_login 里直接完成): WebView2 的 readyState
        只有 loading/complete 两档, 慢网络下任何超过 _LOAD_STALL_SEC 的加载都会被
        判成"停滞"并强制 reload —— 既把页面加载一遍遍清零, 也会吞掉用户此刻的
        点击 (表现为"点 Continue with GitHub 闪一下不跳转"). 上游的登录链路本来
        就没有这一层, Windows 回归上游做法: 导航出去, 剩下的交给页面自己.
        """
        def worker() -> None:
            try:
                render_login_boot_page(lw)
            except Exception as exc:  # noqa: BLE001
                _mlog(f"[main] login boot page ERROR: {exc}")
            time.sleep(BOOT_SETTLE_SEC)
            try:
                ok = install_login_network_rules(lw)
                _mlog(f"[main] login network rules: {'on' if ok else 'skipped'}")
            except Exception as exc:  # noqa: BLE001
                _mlog(f"[main] login network rules ERROR: {exc}")
            try:
                lw.load_url(build_login_url(provider))
            except Exception as exc:  # noqa: BLE001 窗口可能已被关闭
                _mlog(f"[main] login load_url ERROR: {exc}")
                return
            try:
                loaded = ensure_login_page_loaded(lw)
                _mlog(f"[main] login page loaded: {loaded}")
            except Exception as exc:  # noqa: BLE001
                _mlog(f"[main] login load watchdog ERROR: {exc}")
            # 残留会话兜底: 清 cookie 若因页面 JS 续写而部分失效, 登录入口仍会
            # 把页面带到后台 (实测 commandcode 停在官网/控制台), 用户在那种
            # 页面上根本没法登录. 检出"已离开登录入口"就清会话再回来, 最多
            # _LOGIN_ENTRY_RETRIES 次; 登录已成功则立即收手.
            for attempt in range(_LOGIN_ENTRY_RETRIES):
                try:
                    if not _login_still_pending():
                        break
                    if not reset_login_session(lw, provider):
                        break
                    _mlog(f"[main] login fell off sign-in entry -> session reset #{attempt + 1}")
                    ensure_login_page_loaded(lw)
                except Exception as exc:  # noqa: BLE001
                    _mlog(f"[main] login entry check ERROR: {exc}")
                    break
            # 页面内部状态快照: 用来区分"页面没渲染"与"渲染了但没显示"
            try:
                _mlog(f"[main] login page snapshot: {page_snapshot(lw)}")
            except Exception as exc:  # noqa: BLE001
                _mlog(f"[main] login page snapshot ERROR: {exc}")
            # 页面已渲染但窗口不刷新首帧时, 强制重新合成一次
            try:
                _mlog(f"[main] login repaint nudge: {nudge_window_repaint(lw)}")
            except Exception as exc:  # noqa: BLE001
                _mlog(f"[main] login repaint nudge ERROR: {exc}")

        threading.Thread(target=worker, daemon=True, name="gousage-login-arm").start()

    def _recreate_login_window(provider: str = "opencode") -> None:
        """登录窗口被手动关闭后重建 (回调绑定新窗口)."""
        w = watcher.get("ref")
        if isinstance(w, LoginWatcher):
            w.stop()
        old = login_win_ref["win"]
        if old is not None:
            try:
                old.destroy()
            except Exception:  # noqa: BLE001
                pass
        # macOS: 新窗口由 pywebview 的 private_mode 清理网站数据, 但那是异步的:
        # 先显式清一遍目标域会话, 保证登录页拿到的是未登录态.
        # Windows: 不做 (上游做法) —— 旧窗口已销毁, 而 WebView2 每个新窗口初始化
        # 时都会清一次 cookie store (pywebview private_mode), 再清一遍是多余的.
        if not _IS_WIN:
            _prepare_login_session(provider, old)
        new_win = webview.create_window(
            "GoGauge - Login",
            build_login_url(provider) if _IS_WIN else "about:blank",
            width=720,
            height=640,
            min_size=(560, 500),
            background_color="#f7f6f4",
        )
        login_win_ref["win"] = new_win
        _bind_login_close_cleanup(new_win)
        # 新建窗口: 上面刚清过残留 cookie, 基线必为空, 不必再读 (窗口未就绪会卡超时)
        _start_watcher(new_win, provider, snapshot_stale=False)
        if _IS_MAC:
            _arm_login_window(new_win, provider)

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

    # 主窗口原生关闭按钮 (macOS 红点 / Windows Alt+F4、任务栏关闭) 的双平台一致
    # 行为: 托盘/菜单栏可用且非退出中 -> 取消关闭并隐藏窗口驻留; 真正退出(托盘
    # 退出/欢迎页"退出应用")时放行.
    #
    # Windows 必须也绑定: 此前只有 macOS 绑, Windows 上 Alt+F4 (或任务栏"关闭
    # 窗口") 会真正关掉主窗口 —— 一旦它成为最后一个 pywebview 窗口, winforms
    # 后端的 on_close 就 Application.Exit() 结束整个进程, 登录窗口开着也被一起
    # 带走 (表现为"重新登录途中整个项目闪退"), 且与标题栏 X 按钮的最小化到托盘
    # 行为不一致.
    def on_closing() -> bool:
        _save_window_frame(main_win)  # 仅 macOS 生效: 位置记忆
        return _main_window_close_verdict(
            main_win.hide, quitting=_quitting, tray_ready=_tray_ready
        )

    # pywebview closing 事件语义 (两平台一致): handler 返回 False 即取消关闭
    main_win.events.closing += on_closing

    # 系统托盘 (Windows) / 菜单栏图标 (macOS)
    tray = TrayIcon(_app_icon_path())
    tray.bind_window(lambda: main_win if main_win in webview.windows else None)
    tray.start()

    # macOS: 在 pywebview 创建窗口/设置 delegate 前替换 AppDelegate,
    # 补齐 Dock 点击恢复窗口 与 退出放行 (必须在 webview.start() 之前).
    _install_macos_app_delegate()

    # 窗口/Dock 图标: 按平台选择 (Win=ico, macOS 用 png 生成 dock icon 由 .app 提供)
    icon_path = _app_icon_path()
    webview.start(icon=icon_path if icon_path else None, user_agent=_mac_safari_user_agent())

    if not _quitting:
        tray.stop()
    # 正常退出路径 (事件循环已随最后一个窗口销毁而退出): 停 server / 关库连接 /
    # WAL checkpoint. 此前 shutdown 只挂在 3s 兜底 Timer 上, 而本函数返回后进程
    # 即刻结束, daemon Timer 被丢弃 —— checkpoint_wal 在正常退出时从未执行过.
    # 兜底 Timer 再跑一遍是幂等的, 无副作用.
    shutdown()


def shutdown() -> None:
    server.stop_server()
    db.checkpoint_wal()
    db.close_db()


if __name__ == "__main__":
    main()
