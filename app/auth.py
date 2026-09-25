"""WebView 登录: 加载 provider 官方登录页, 捕获会话 cookie.

原理: pywebview (WebView2 / WKWebView) 的 window.get_cookies() 可直接读取 HttpOnly cookie,
登录完成后窗口位于目标 provider 域, 从中提取会话 cookie:
- opencode: opencode.ai 域的 ``auth`` cookie + workspace (wrk_xxx) 提示
- commandcode: commandcode.ai 域的 ``__Secure-commandcode_prod_.session_token``

重新登录前必须清掉残留会话 (见 ``clear_provider_cookies``): pywebview 的
private_mode 只在 create_window 时清理网站数据, 而复用的登录窗口里上一轮的
cookie 还在 —— 既让登录页直接跳转后台 (无法切换账号), 也让 LoginWatcher 把
旧凭证误判为本次登录成功 (窗口秒关 + 凭证未刷新).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid
from http.cookies import SimpleCookie as SimpleCookieCls
from typing import Callable, Iterable, Optional

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

# 登录页 (commandcode.ai/signin) 引用的追踪/分析域. 部分网络环境下不可达
# (实测: connect.facebook.net / static.ads-twitter.com /
# static.cloudflareinsights.com 连接超时), 这些请求会一直 pending, 页面的
# load 事件永不触发, 登录窗口就停在纯白 —— 实测屏蔽后登录页立即完整渲染.
# 只拦这几类域: GitHub 授权、Cloudflare Turnstile 人机验证、api.commandcode.ai
# 等登录必需域一律放行.
LOGIN_BLOCKED_HOSTS = (
    "connect.facebook.net",
    "static.ads-twitter.com",
    "static.cloudflareinsights.com",
    "www.googletagmanager.com",
    "www.google-analytics.com",
)
_RULE_LIST_ID = "gogauge-login-blocklist"
_RULE_COMPILE_TIMEOUT = 10.0
_VIEW_READY_TIMEOUT = 8.0
# 登录页加载看门狗: 进度停滞多久判定为卡死并 reload, 以及总共等多久
_LOAD_STALL_SEC = 8.0
_LOAD_TOTAL_SEC = 45.0
_LOAD_MAX_RELOADS = 2
_SNAPSHOT_TIMEOUT = 10.0
# 引导页渲染后留出的合成时间: 太短则首次合成还没落定就导航, 仍会白屏
BOOT_SETTLE_SEC = 1.2

COOKIE_POLL_SEC = 1.0
# 清残留会话的等待上限: 正常在毫秒级返回, 超时只说明主线程被占, 不阻塞登录
COOKIE_PURGE_TIMEOUT = 5.0
# 读取残留会话基线的上限: 窗口未就绪时 pywebview 的 get_cookies 会一直挂,
# 超时即放弃采集 (退回数据库旧凭证指纹比对)
COOKIE_READ_TIMEOUT = 2.0
_LOG_FILE = os.path.join(tempfile.gettempdir(), "gousage_login.log")


def _log(msg: str) -> None:
    """同时输出到 stdout 与日志文件 (便于诊断)."""
    print(msg, flush=True)
    try:
        # 0600: 该文件位于公共临时目录, 防其他本地用户读取
        fd = os.open(_LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


try:  # 历史版本可能以默认 0644 创建过日志: 收紧权限
    os.chmod(_LOG_FILE, 0o600)
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


def provider_host(provider: str) -> str:
    """provider -> 其会话 cookie 所在的域."""
    return CC_HOST if provider == PROVIDER_COMMANDCODE else OPCODE_HOST


def _domain_matches(domain: str, host: str) -> bool:
    """cookie 的 domain 是否属于 host (兼容 ``.host`` 父域写法)."""
    d = (domain or "").strip().lstrip(".").lower()
    return bool(d) and (d == host or d.endswith("." + host))


def clear_provider_cookies(provider: str) -> int:
    """删除 WebView cookie store 中该 provider 域的会话 cookie, 返回删除条数.

    必须在加载登录页之前调用. pywebview 的 private_mode 只在 create_window 时
    清理网站数据, 而登录窗口是被复用的 (hide/show): 上一轮的会话 cookie 仍在
    store 里, 会让登录页据旧凭证直接跳转后台 (无法重新选择账号), 并让
    LoginWatcher 把这份残留凭证当成"刚登录成功".

    仅 macOS 有精确删除能力 (WKHTTPCookieStore 逐条删除, 不触碰其它域与
    localStorage); 其它平台返回 0, 由 LoginWatcher 的旧凭证比对兜底.
    """
    if sys.platform != "darwin":
        return 0
    # 主线程调用会与 callAfter 互锁 (自身阻塞等待主线程执行该回调): 放弃清理,
    # 交由 LoginWatcher 的旧凭证比对兜底.
    if threading.current_thread() is threading.main_thread():
        _log("[login] cookie purge skipped: called on main thread")
        return 0
    try:
        from PyObjCTools import AppHelper
        from WebKit import WKWebsiteDataStore

        store = WKWebsiteDataStore.defaultDataStore().httpCookieStore()
    except Exception as exc:  # noqa: BLE001 pyobjc/WebKit 不可用
        _log(f"[login] cookie purge unavailable: {exc}")
        return 0

    host = provider_host(provider)
    done = threading.Event()
    removed = {"count": 0}

    def on_cookies(cookies) -> None:
        try:
            targets = [c for c in (cookies or []) if _domain_matches(c.domain(), host)]
        except Exception:  # noqa: BLE001
            done.set()
            return
        if not targets:
            done.set()
            return
        pending = {"left": len(targets)}

        def on_deleted() -> None:
            pending["left"] -= 1
            if pending["left"] <= 0:
                removed["count"] = len(targets)
                done.set()

        try:
            for cookie in targets:
                store.deleteCookie_completionHandler_(cookie, on_deleted)
        except Exception:  # noqa: BLE001
            done.set()

    try:
        AppHelper.callAfter(lambda: store.getAllCookies_(on_cookies))
    except Exception as exc:  # noqa: BLE001
        _log(f"[login] cookie purge callAfter failed: {exc}")
        return 0

    if not done.wait(COOKIE_PURGE_TIMEOUT):
        _log(f"[login] cookie purge TIMEOUT on {host}")
        return 0
    if removed["count"]:
        _log(f"[login] purged {removed['count']} stale cookie(s) on {host}")
    return removed["count"]


def token_fingerprint(value: str) -> str:
    """凭证明文 -> SHA-256 指纹 (与 db 的 token_fp 同算法, 比对时无需明文流转)."""
    return hashlib.sha256((value or "").strip().encode("utf-8")).hexdigest()


def build_token(provider: str, cookie_value: str) -> str:
    """cookie 值 -> 库内凭证形态 (opencode 带 ``auth=`` 前缀, commandcode 带 cookie 名)."""
    if provider == PROVIDER_COMMANDCODE:
        return f"{CC_AUTH_COOKIE_NAME}={cookie_value}"
    return f"auth={cookie_value}"


def wait_window_view(win, timeout: float = _VIEW_READY_TIMEOUT):
    """等待窗口的底层 BrowserView 实例化完成 (create_window 是异步的).

    窗口尚未挂载时返回 None —— 调用方据此降级, 而不是无限等下去.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            from webview.platforms.cocoa import BrowserView  # noqa: E402 仅 macOS

            for view in list(BrowserView.instances.values()):
                if getattr(view, "pywebview_window", None) is not win:
                    continue
                if getattr(view, "webview", None) is not None:
                    return view
        except Exception:  # noqa: BLE001 非 macOS 或 pywebview 内部结构变化
            return None
        time.sleep(0.05)
    return None


def login_block_rules_json() -> str:
    """生成屏蔽追踪域的 WKContentRuleList 规则 (纯函数, 便于单测)."""
    return json.dumps([
        {"trigger": {"url-filter": ".*", "if-domain": [host, "*" + host]},
         "action": {"type": "block"}}
        for host in LOGIN_BLOCKED_HOSTS
    ])


def page_load_state(win):
    """读取窗口页面的加载状态 {"progress", "loading"}; 读不到返回 None.

    直接问底层 WKWebView, 不走 pywebview 的窗口方法 —— 后者用无超时信号量
    等主线程回调, 页面加载中调用会一直挂住 (get_current_url/evaluate_js 都是).
    """
    if sys.platform != "darwin":
        return None
    # 主线程调用会与 callAfter 互锁
    if threading.current_thread() is threading.main_thread():
        return None
    view = wait_window_view(win, timeout=0.5)
    if view is None:
        return None
    box = {}
    done = threading.Event()

    def read() -> None:
        try:
            webview_obj = view.webview
            box["state"] = {
                "progress": float(webview_obj.estimatedProgress()),
                "loading": bool(webview_obj.isLoading()),
            }
        except Exception as exc:  # noqa: BLE001
            box["error"] = repr(exc)
        finally:
            done.set()

    try:
        from PyObjCTools import AppHelper

        AppHelper.callAfter(read)
    except Exception:  # noqa: BLE001
        return None
    if not done.wait(COOKIE_PURGE_TIMEOUT):
        return None
    return box.get("state")


def reload_window(win) -> bool:
    """让窗口重新加载当前页 (需在主线程之外调用)."""
    if sys.platform != "darwin":
        return False
    if threading.current_thread() is threading.main_thread():
        return False
    view = wait_window_view(win, timeout=0.5)
    if view is None:
        return False
    done = threading.Event()
    box = {}

    def do_reload() -> None:
        try:
            view.webview.reload()
            box["ok"] = True
        except Exception as exc:  # noqa: BLE001
            box["error"] = repr(exc)
        finally:
            done.set()

    try:
        from PyObjCTools import AppHelper

        AppHelper.callAfter(do_reload)
    except Exception:  # noqa: BLE001
        return False
    if not done.wait(COOKIE_PURGE_TIMEOUT):
        return False
    return bool(box.get("ok"))


# 登录窗口的引导页: 纯本地内容, 用来触发 WKWebView 的首次合成.
# 背景: 窗口创建后直接加载登录页这种复杂 SPA 时, 首次合成可能根本不发生 ——
# 页面 DOM/样式/文本全都正常 (实测 readyState=interactive、无 pending 资源),
# 但窗口只剩背景色; 先渲染一帧本地内容再导航到登录页就一切正常 (已实测).
_LOGIN_BOOT_HTML = (
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    "<style>html,body{margin:0;height:100%}"
    "body{display:flex;align-items:center;justify-content:center;"
    "background:#f7f6f4;color:#8a8a8a;"
    "font:14px -apple-system,'PingFang SC','Helvetica Neue',sans-serif}"
    "</style></head><body><div>正在打开登录页…</div></body></html>"
)


def render_login_boot_page(win) -> bool:
    """渲染本地引导页, 触发 WKWebView 的首次合成 (必须在导航到登录页之前).

    这是白屏的根治手段: 缺了这一步, 登录页即使完整加载也不会显示出来.
    """
    try:
        win.load_html(_LOGIN_BOOT_HTML, "about:blank")
        return True
    except Exception as exc:  # noqa: BLE001 窗口可能已被关闭
        _log(f"[login] boot page failed: {exc}")
        return False


_SNAPSHOT_JS = (
    "JSON.stringify({"
    "ready:document.readyState,"
    "title:document.title,"
    "len:document.body?document.body.innerHTML.length:-1,"
    "text:document.body?(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,120):null,"
    "sheets:document.styleSheets.length,"
    "done:performance.getEntriesByType('resource').length,"
    "pending:performance.getEntriesByType('resource').filter(function(r){return r.responseEnd===0;}).length"
    "})"
)


def page_snapshot(win) -> Optional[str]:
    """读登录页的内部状态 (诊断用): 直接问 WKWebView, 不经 pywebview.

    pywebview 的 evaluate_js 会挂在无超时信号量上 (页面加载中必挂), 这里用
    pyobjc 的 completion handler 自己收结果, 用来区分"页面没渲染"和
    "渲染了但没显示出来".
    """
    if sys.platform != "darwin":
        return None
    if threading.current_thread() is threading.main_thread():
        return None
    view = wait_window_view(win, timeout=1.0)
    if view is None:
        return None
    box = {}
    done = threading.Event()

    def run() -> None:
        def handler(result, error):
            box["result"] = result
            box["error"] = str(error) if error else None
            done.set()

        try:
            view.webview.evaluateJavaScript_completionHandler_(_SNAPSHOT_JS, handler)
        except Exception as exc:  # noqa: BLE001
            box["error"] = repr(exc)
            done.set()

    try:
        from PyObjCTools import AppHelper

        AppHelper.callAfter(run)
    except Exception:  # noqa: BLE001
        return None
    if not done.wait(_SNAPSHOT_TIMEOUT):
        return "<snapshot timeout>"
    if box.get("error"):
        return f"<snapshot error: {box['error']}>"
    return box.get("result")


def nudge_window_repaint(win, settle: float = 0.4) -> bool:
    """强制窗口重新合成一帧 (macOS).

    实测遇到过: WKWebView 里页面**已经渲染完成** (DOM、可见文本、样式表、
    无 pending 资源都正常), 但窗口只显示背景色、首帧始终不刷新 —— 轻微改动
    窗口尺寸可让 WebKit 重新合成, 这是最后一道兜底.
    """
    if sys.platform != "darwin":
        return False
    # 主线程调用会与 callAfter 互锁
    if threading.current_thread() is threading.main_thread():
        return False
    view = wait_window_view(win, timeout=1.0)
    if view is None:
        return False
    try:
        import Foundation
        from PyObjCTools import AppHelper
    except Exception as exc:  # noqa: BLE001
        _log(f"[login] repaint nudge unavailable: {exc}")
        return False

    state = {}

    def shrink() -> None:
        try:
            window = view.window
            frame = window.frame()
            state["frame"] = frame
            smaller = Foundation.NSMakeRect(
                frame.origin.x, frame.origin.y,
                max(1.0, frame.size.width - 1.0), frame.size.height,
            )
            window.setFrame_display_(smaller, True)
            view.webview.setNeedsDisplay_(True)
            state["ok"] = True
        except Exception as exc:  # noqa: BLE001
            state["error"] = repr(exc)

    def restore() -> None:
        try:
            frame = state.get("frame")
            if frame is not None:
                view.window.setFrame_display_(frame, True)
        except Exception:  # noqa: BLE001 窗口可能已销毁
            pass

    try:
        AppHelper.callAfter(shrink)
    except Exception:  # noqa: BLE001
        return False
    time.sleep(settle)  # 这一段在调用线程上等, 不在主线程
    try:
        AppHelper.callAfter(restore)
    except Exception:  # noqa: BLE001
        return False
    time.sleep(0.2)
    if state.get("error"):
        _log(f"[login] repaint nudge failed: {state['error']}")
    return bool(state.get("ok"))


def ensure_login_page_loaded(
    win, stall_sec: float = _LOAD_STALL_SEC, total_sec: float = _LOAD_TOTAL_SEC
) -> bool:
    """盯住登录页的加载: 停滞就主动 reload 重试, 返回是否加载完成.

    实测: commandcode 登录页在 WKWebView 里首次加载常停在中途 (progress 不再
    前进但 loading 恒为 True), 窗口因此一直是纯白; 主动 reload 一次即可正常
    加载完成. 这里用"进度停滞"而非固定时长判定, 慢网络下不会误伤.
    """
    started = time.time()
    last_progress = -1.0
    last_change = time.time()
    reloads = 0
    while time.time() - started < total_sec:
        state = page_load_state(win)
        if state is None:
            time.sleep(1.0)
            continue
        progress = float(state.get("progress") or 0.0)
        if not state.get("loading") or progress >= 0.999:
            _log(f"[login] page loaded (progress={progress:.2f}, reloads={reloads})")
            return True
        if progress > last_progress + 0.001:
            last_progress = progress
            last_change = time.time()
        elif time.time() - last_change >= stall_sec and reloads < _LOAD_MAX_RELOADS:
            reloads += 1
            _log(f"[login] page stalled at {progress:.2f} -> reload #{reloads}")
            reload_window(win)
            last_change = time.time()
        time.sleep(1.0)
    _log("[login] page load watchdog TIMEOUT")
    return False


def install_login_network_rules(win) -> bool:
    """给登录窗口装上请求拦截规则 (仅 macOS): 屏蔽登录页里的追踪/分析域.

    必须在**导航到登录页之前**调用 —— rule list 只对之后的请求生效.

    背景: 部分网络环境下这些域连接超时 (facebook/twitter 广告、Cloudflare
    前端分析), 请求一直 pending 会让页面 load 事件永不触发, 登录窗口停在
    纯白 (实测屏蔽后立即完整渲染). 失败只是降级为原来的行为, 不影响登录.
    """
    if sys.platform != "darwin":
        return False
    # 主线程调用会与 callAfter 互锁 (自身阻塞等待主线程执行该回调)
    if threading.current_thread() is threading.main_thread():
        return False
    try:
        from PyObjCTools import AppHelper
        from WebKit import WKContentRuleListStore
    except Exception as exc:  # noqa: BLE001 pyobjc/WebKit 不可用
        _log(f"[login] rule list unavailable: {exc}")
        return False

    view = wait_window_view(win)
    if view is None:
        _log("[login] rule list skipped: window view not ready")
        return False

    compiled = {}
    compiled_done = threading.Event()

    def on_compiled(rules, error) -> None:
        compiled["rules"] = rules
        compiled["error"] = str(error) if error else ""
        compiled_done.set()

    try:
        AppHelper.callAfter(
            lambda: WKContentRuleListStore.defaultStore()
            .compileContentRuleListForIdentifier_encodedContentRuleList_completionHandler_(
                _RULE_LIST_ID, login_block_rules_json(), on_compiled
            )
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"[login] rule list compile dispatch failed: {exc}")
        return False

    if not compiled_done.wait(_RULE_COMPILE_TIMEOUT):
        _log("[login] rule list compile TIMEOUT")
        return False
    rules = compiled.get("rules")
    if rules is None or compiled.get("error"):
        _log(f"[login] rule list compile failed: {compiled.get('error')}")
        return False

    applied_done = threading.Event()
    applied = {}

    def apply() -> None:
        try:
            controller = view.webview.configuration().userContentController()
            controller.addContentRuleList_(rules)
            applied["ok"] = True
        except Exception as exc:  # noqa: BLE001
            applied["error"] = repr(exc)
        finally:
            applied_done.set()

    try:
        AppHelper.callAfter(apply)
    except Exception as exc:  # noqa: BLE001
        _log(f"[login] rule list apply dispatch failed: {exc}")
        return False

    if not applied_done.wait(COOKIE_PURGE_TIMEOUT) or not applied.get("ok"):
        _log(f"[login] rule list apply failed: {applied.get('error')}")
        return False
    _log(f"[login] blocked {len(LOGIN_BLOCKED_HOSTS)} analytics host(s) on login page")
    return True


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


def read_provider_cookie(win, provider: str, timeout: float = COOKIE_READ_TIMEOUT) -> Optional[str]:
    """带超时地读取窗口 cookie store 中目标 provider 会话 cookie 的值.

    调用方在打开登录窗口的确定时刻(加载登录页之前)调用, 拿到的值即"残留
    会话"基线.

    必须带超时: pywebview 的 get_cookies 用**无超时**信号量等待主线程回调,
    窗口刚创建 (BrowserView 还没实例化) 时会一直挂住 —— 直接同步调用会把
    open_login 卡死在"启动监听"之前, 登录窗口再也等不到 watcher. 读不到
    (超时/异常)返回 None, 由调用方的旧凭证指纹继续兜底.
    """
    target = CC_AUTH_COOKIE_NAME if provider == PROVIDER_COMMANDCODE else AUTH_COOKIE_NAME
    box: dict[str, Optional[str]] = {}

    def worker() -> None:
        try:
            cookies = win.get_cookies() or []
        except Exception:  # noqa: BLE001 窗口未加载完成/已销毁
            return
        for name, value in _cookie_entries(cookies):
            if name == target and value:
                box["value"] = value
                return

    reader = threading.Thread(target=worker, daemon=True, name="gousage-cookie-read")
    reader.start()
    reader.join(timeout)
    if reader.is_alive():
        _log("[login] cookie snapshot timed out (window not ready) -> no baseline")
        return None
    return box.get("value")


class LoginWatcher:
    """后台轮询登录窗口, 捕获 provider 会话 cookie.

    "首次出现的凭证"不等于"本次登录拿到的凭证": 登录窗口会被复用, cookie
    store 里往往还留着上一轮 (或上一账号) 的会话. 只凭 cookie 存在就判定
    成功, 会让窗口在用户完成授权前秒关, 并把旧凭证原样存回 —— 界面表现为
    "登录闪退 + 登录状态没刷新". 因此这里要求凭证必须与登录前已有的值不同:

    - ``baseline_value``: 打开登录窗口瞬间 store 里已有的凭证 (见
      ``read_provider_cookie``);
    - ``stale_fps``: 数据库里该 provider 名下所有凭证的指纹, 覆盖 baseline
      读不到 (窗口未就绪/非 macOS) 以及换号登录的场景.
    """

    def __init__(
        self,
        win,
        provider: str,
        on_success: Callable[[str, str, str], None],
        on_cancelled: Optional[Callable[[], None]] = None,
        stale_fps: Optional[Iterable[str]] = None,
        baseline_value: Optional[str] = None,
    ):
        self.win = win
        self.provider = provider if provider in (PROVIDER_OPENCODE, PROVIDER_COMMANDCODE) else PROVIDER_OPENCODE
        self.on_success = on_success  # fn(token, workspace_hint, provider)
        self.on_cancelled = on_cancelled
        # 已知旧凭证的指纹: 命中即判定为残留会话, 继续等待真正的登录
        self.stale_fps = {fp for fp in (stale_fps or ()) if fp}
        self.baseline_value = (baseline_value or "").strip() or None
        self._stale_logged = False
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
        return provider_host(self.provider)

    def _target_cookie_name(self) -> str:
        return CC_AUTH_COOKIE_NAME if self.provider == PROVIDER_COMMANDCODE else AUTH_COOKIE_NAME

    def _is_stale(self, value: str) -> bool:
        """该凭证是否为登录开始前就已存在的残留会话 (指纹按库内形态计算)."""
        if self.baseline_value and value == self.baseline_value:
            return True
        return token_fingerprint(build_token(self.provider, value)) in self.stale_fps

    def _run(self) -> None:
        _log(
            f"[login] watcher started provider={self.provider} "
            f"stale={len(self.stale_fps)} baseline={'yes' if self.baseline_value else 'no'}"
        )
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
                    # 只记录 cookie 名, 不落值: 日志在公共临时目录, 防会话凭证泄漏
                    raw_desc = [
                        ",".join(c.keys())
                        if isinstance(c, SimpleCookieCls)
                        else str(c.get("name") or "?")
                        for c in cookies
                    ]
                except Exception as exc:  # noqa: BLE001
                    cookies = []
                    raw_desc = [f"<get_cookies ERROR {type(exc).__name__}: {exc}>"]
                _log(f"[login] on {target_host}, url={url[:120]}, cookie_names={raw_desc}")

                for name, value in _cookie_entries(cookies):
                    if name != target_cookie:
                        continue
                    if self._is_stale(value):
                        # 残留会话: 用户可能还在授权页, 页面也可能被旧凭证直接
                        # 带到后台. 继续轮询, 等真正的新凭证落地再收工.
                        if not self._stale_logged:
                            self._stale_logged = True
                            _log("[login] stale session cookie only, waiting for fresh sign-in")
                        continue
                    workspace_hint = "Default"
                    if self.provider == PROVIDER_OPENCODE:
                        match = _WORKSPACE_URL_RE.search(url)
                        workspace_hint = match.group(1) if match else "Default"
                    _log(f"[login] SUCCESS: cookie {name} captured (len={len(value)}), ws={workspace_hint}")
                    self.done = True
                    self._stop.set()
                    token = build_token(self.provider, value)
                    self.on_success(token, workspace_hint, self.provider)
                    return
            self._stop.wait(COOKIE_POLL_SEC)
        if not self.done and self.on_cancelled:
            self.on_cancelled()
