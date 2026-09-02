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
import sys
import tempfile
import threading
import time
from typing import Optional

import webview

from . import db, server
from .auth import LoginWatcher, build_login_url

APP_TITLE = "GoGauge - OpenCode Go Usage Panel"
WINDOW_SIZE = (1280, 840)
WINDOW_MIN_SIZE = (1000, 680)

_IS_MAC = sys.platform == "darwin"
_IS_WIN = sys.platform == "win32"

_quitting = False  # 托盘"退出"标志: 为 True 时关闭窗口=真正退出
_tray_ready = False  # 托盘是否成功启动 (失败时关闭窗口=直接退出, 避免无法关闭)
_main_win_ref: dict[str, object] = {"win": None}  # 主窗口引用 (macOS delegate 恢复用)


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
            global _quitting
            _quitting = True
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


# ── 单实例检测 (仅 Windows: Win32 命名互斥体; macOS 不走此路径) ──
_LOCK_FILE_NAME = "GoGauge.lock"
_MUTEX_NAME = "GoGauge_SingleInstance_Mutex"
_ERROR_ALREADY_EXISTS = 183  # GetLastError: 命名对象已存在
_ACTIVATE_RETRY_INTERVAL = 0.5  # 激活旧实例窗口的重试间隔(秒)
_ACTIVATE_RETRY_TIMES = 30  # 重试次数 (共约15秒, 覆盖旧实例 onefile 解压+启动耗时)
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


def _activate_with_retry() -> bool:
    """带重试激活旧实例窗口.

    第二实例与首实例几乎同时启动时 (快速连击双击), 首实例可能仍在 onefile
    解压/初始化, 窗口尚未创建. 此时需轮询等待其窗口就绪后再激活,
    否则会误弹提示框并残留为第二个可见窗口.

    Returns:
        True=成功激活旧实例窗口 False=超时仍未找到窗口
    """
    for _ in range(_ACTIVATE_RETRY_TIMES):
        if _activate_existing_instance(_read_valid_lock_pid()):
            return True
        time.sleep(_ACTIVATE_RETRY_INTERVAL)
    return False


def _ensure_single_instance() -> None:
    """单实例守卫: 命名互斥体原子判定, 已有实例时激活其窗口并结束当前进程.

    主判定用内核命名互斥体 (CreateMutexW): 创建是否冲突由内核原子保证,
    无锁文件方案的竞态窗口 (双击过快/系统卡顿时两个实例互相看不到对方),
    进程崩溃时内核自动回收互斥体, 无残留无 PID 复用问题.
    锁文件降级为辅助: 记录首实例 PID 供激活窗口定位; 失效时按标题全局枚举兜底.
    """
    global _mutex_handle
    # use_last_error=True: ctypes 每次调用后私有捕获错误码, 避免被 Python 中间系统调用污染
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        # 互斥体已存在 = 旧实例一定在运行, 激活其窗口后退出
        if handle:
            kernel32.CloseHandle(handle)
        if not _activate_with_retry():
            # 超时仍定位不到窗口 (极端情况): 提示从托盘操作
            ctypes.windll.user32.MessageBoxW(
                0, "GoGauge 已在运行, 请从系统托盘打开窗口。", "GoGauge", _MB_ICONINFORMATION
            )
        sys.exit(0)
    # 首实例: 持有互斥体 (全局引用防回收, 进程退出由内核自动释放)
    _mutex_handle = handle
    # 锁文件记录当前 PID, 供后续实例激活窗口定位
    try:
        with open(os.path.join(tempfile.gettempdir(), _LOCK_FILE_NAME), "w") as fh:
            fh.write(str(os.getpid()))
    except OSError:
        _mlog("[single-instance] 写锁文件失败")


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

    def __init__(self, icon_path: str) -> None:
        self._icon_path = icon_path
        self._icon = None
        self._win_getter = None
        self._lang = "zh"

    def bind_window(self, getter) -> None:
        self._win_getter = getter

    def _info_items(self, pystray) -> list:
        """今日用量快捷面板行 (灰显不可点): 免开主窗即可瞄一眼用量."""
        t = _TRAY_I18N.get(self._lang, _TRAY_I18N["zh"])
        rows: list = []
        try:
            if db.get_token():
                today = db.totals("today") or {}
                cost = float(today.get("total_cost_usd") or 0.0)
                req = int(today.get("request_count") or 0)
                rows.append(pystray.MenuItem(
                    f"{t['today_label']}: ${cost:.2f} · {req} {t['req_unit']}",
                    None, enabled=False))
                # 读 server 配额缓存 (只读跨线程安全); 未就绪时自然缺省
                quota = getattr(server, "_quota_cache", {}).get("data") or {}
                for w in (quota.get("windows") or [])[:3]:
                    label = str(w.get("label") or "").strip()
                    remaining = w.get("remaining")
                    if label and isinstance(remaining, (int, float)):
                        rows.append(pystray.MenuItem(
                            f"{label}: {t['remaining_prefix']}{remaining:.0f}%",
                            None, enabled=False))
            else:
                rows.append(pystray.MenuItem(t["not_login"], None, enabled=False))
        except Exception:  # noqa: BLE001  数据未就绪时面板行省略
            pass
        return rows

    def _refresh_loop(self) -> None:
        """周期 update_menu 让动态行取到最新数据 (cocoa 的 NSMenu 是快照)."""
        while not _quitting:
            time.sleep(self._REFRESH_SEC)
            try:
                if self._icon and not _quitting:
                    self._icon.update_menu()
            except Exception:  # noqa: BLE001
                pass

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
            print(f"[tray] 托盘启动失败: {exc}", flush=True)
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
        global _quitting, _tray_ready
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


def _destroy_all_windows() -> None:
    """销毁所有窗口 (含隐藏登录窗), 让 pywebview 事件循环退出, 进程真正结束."""
    for w in list(webview.windows):
        try:
            w.destroy()
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    global _quitting

    # 单实例守卫: Windows 用命名互斥体, macOS 用 flock (源码运行均不限制).
    if _IS_WIN:
        _ensure_single_instance()
    else:
        _ensure_single_instance_mac()

    db.get_db()  # 初始化数据库

    host, port = server.start_server()
    dashboard_url = f"http://{host}:{port}/"
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

    # 登录模式: open_login(mode, provider) 记录意图, on_login_success 按模式落库
    pending_mode = {"mode": "relogin", "provider": "opencode"}

    def on_login_success(auth_cookie: str, workspace_hint: str, provider: str = "opencode") -> None:
        """登录成功: 按模式保存 → 隐藏登录窗口 → 主窗口进入面板 → 全量同步.

        - add: 新建账号 (同 provider+token 自动去重为既有账号) 并切换为活跃
        - relogin: 更新当前活跃账号凭证 (含 provider)
        """
        mode = pending_mode.get("mode", "relogin")
        provider = provider if provider in ("opencode", "commandcode") else "opencode"
        _mlog(f"on_login_success: ws={workspace_hint} mode={mode} provider={provider}")
        watcher["ref"] = None  # 本次登录已完结: 释放单飞守卫占用
        try:
            if mode == "add":
                db.add_account(auth_cookie, workspace_hint, switch=True, provider=provider)
            else:
                db.save_token(auth_cookie, workspace_hint, provider=provider)
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
        # 同 URL 的 load_url 可能被 WebView 跳过 (不重载): 显式通知前端就地刷新,
        # 否则停留在设置页时看不到新增账号 (需手动切页才会拉取)
        try:
            main_win.evaluate_js(
                "window.gousageOnLoginSuccess && window.gousageOnLoginSuccess();"
            )
            _mlog("  evaluate_js gousageOnLoginSuccess sent")
        except Exception as exc:  # noqa: BLE001
            _mlog(f"  evaluate_js ERROR: {exc}")
        server.sync_all_async("full")

    def _start_watcher(lw, provider: str = "opencode") -> None:
        """启动登录监听: 优先等 shown 事件 (避免 hidden 窗口调用窗口方法抛内部异常);
        复用窗口 (已显示过) 直接启动; 事件不触发时 3s 兜底启动 (LoginWatcher 对未就绪窗口有重试)."""
        def _on_cancelled() -> None:
            # 监听线程退出 (窗口被关/自愈) 后释放单飞守卫引用
            if watcher.get("ref") is w_ref["self"]:
                watcher["ref"] = None
                _mlog("  watcher exited -> ref cleared")

        w_ref: dict[str, object] = {}
        w = LoginWatcher(lw, provider, on_login_success, on_cancelled=_on_cancelled)
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
        # 兜底: shown 事件在打包环境可能不触发, 3s 后无条件启动监听
        # (同样带当前 watcher 校验: 被 recreate 取代的旧 Timer 不拉起过期 watcher)
        threading.Timer(3.0, lambda: watcher.get("ref") is w and w.start()).start()

    def _login_win_alive() -> bool:
        """只读检查登录窗是否存活 (不触发创建副作用, 否则恒为 True 使重建分支失效)."""
        w = login_win_ref["win"]
        if w is None:
            return False
        try:
            return w in webview.windows
        except Exception:  # noqa: BLE001
            return False

    def open_login(mode: str = "relogin", provider: str = "opencode") -> None:
        """弹出独立登录窗口并开始监听 (欢迎页/设置页按钮). 单飞守卫: 已有登录流程时忽略."""
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
            pending_mode["mode"] = mode if mode in ("add", "relogin") else "relogin"
            pending_mode["provider"] = provider
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
            else:
                _mlog(f"[main] open_login ignored: login in progress (provider={provider})")
                return
        pending_mode["mode"] = mode if mode in ("add", "relogin") else "relogin"
        pending_mode["provider"] = provider
        lw = login_win()
        try:
            lw.show()
            lw.load_url(build_login_url(provider))
        except Exception as exc:  # noqa: BLE001 窗口可能被用户手动关闭, 重建
            print(f"[main] login window reopen: {exc}", flush=True)
            _recreate_login_window(provider)
            return
        _start_watcher(lw, provider)

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
        new_win = webview.create_window(
            "GoGauge - Login",
            build_login_url(provider),
            width=720,
            height=640,
            min_size=(560, 500),
            background_color="#f7f6f4",
        )
        login_win_ref["win"] = new_win
        _bind_login_close_cleanup(new_win)
        _start_watcher(new_win, provider)

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
                _save_window_frame(main_win)
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

    # macOS: 在 pywebview 创建窗口/设置 delegate 前替换 AppDelegate,
    # 补齐 Dock 点击恢复窗口 与 退出放行 (必须在 webview.start() 之前).
    _install_macos_app_delegate()

    # 窗口/Dock 图标: 按平台选择 (Win=ico, macOS 用 png 生成 dock icon 由 .app 提供)
    icon_path = _app_icon_path()
    webview.start(icon=icon_path if icon_path else None, user_agent=_mac_safari_user_agent())

    if not _quitting:
        tray.stop()


def shutdown() -> None:
    server.stop_server()
    db.close_db()


if __name__ == "__main__":
    main()
