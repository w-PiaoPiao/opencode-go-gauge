"""WebView 登录: 加载 provider 官方登录页, 捕获会话 cookie.

原理: pywebview (WebView2 / WKWebView) 的 window.get_cookies() 可直接读取 HttpOnly cookie,
登录完成后窗口位于目标 provider 域, 从中提取会话 cookie:
- opencode: opencode.ai 域的会话 cookie + workspace (wrk_xxx) 提示
- commandcode: commandcode.ai 域的 ``__Secure-commandcode_prod_.session_token``

2026-09 opencode.ai 前端改版: 旧授权页 ``auth.opencode.ai/authorize`` 与旧会话
cookie ``auth`` 已废弃, 现由 ``/console`` 控制台接管登录, 会话 cookie 为
``__Host-console_session`` (登录入口 https://opencode.ai/console/login)。
旧 cookie 名 ``auth`` 保留在候选列表尾部兼容 (db 迁移 4 已把旧 token 清空)。

2026-09 GitHub 2FA 卡死修复: 控制台登录页 "Continue with GitHub" 会带
``client_id``/``code_challenge``/``redirect_uri`` 跳到 github.com/login; 开启
两步验证 (2FA) 的账号完成验证后, GitHub 可能丢失 OAuth 续跑链路 (return_to),
把窗口留在 github.com/settings/security 等无关页面且不再回跳 opencode.ai。
监听器确认 GitHub 已登录、窗口却停在无关 GitHub 页面超过宽限期时, 自动
重新加载先前记录的授权入口 URL, 依靠刚建立的 GitHub 会话续跑 authorize
→ 回跳 opencode.ai → 捕获会话 cookie。

重新登录前必须清掉残留会话 (见 ``clear_provider_cookies``): pywebview 的
private_mode 只在 create_window 时清理网站数据, 而复用的登录窗口里上一轮的
cookie 还在 —— 既让登录页直接跳转后台 (无法切换账号), 也让 LoginWatcher 把
旧凭证误判为本次登录成功 (窗口秒关 + 凭证未刷新). macOS 走 WKHTTPCookieStore、
Windows 走 WebView2 CookieManager, 都按 provider 域精确删除.

两平台的底层实现都是"直接问 WebView", 不经 pywebview 的窗口方法: 后者的
get_cookies/evaluate_js 用**无超时**信号量等 UI 线程回调, 任一环节异常都会
永久挂起调用线程 (WKWebView 页面加载中、WebView2 的 GetCookiesAsync 拿到
null URL 时都会触发).
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
from http.cookies import SimpleCookie as SimpleCookieCls
from typing import Callable, Iterable, Optional
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse

import webview

from .db import PROVIDER_COMMANDCODE, PROVIDER_OPENCODE

# opencode: 2026-09 控制台改版后由 /console 接管登录 (旧授权页
# auth.opencode.ai/authorize 已下线, 登录入口即控制台登录页).
OPCODE_HOST = "opencode.ai"
CONSOLE_LOGIN_URL = "https://opencode.ai/console/login"
LOGIN_NEXT_PATH = "/console/"
# 会话 cookie: 新版 __Host-console_session 优先, 旧版 auth 兼容历史账号
SESSION_COOKIE_NAMES = ("__Host-console_session", "auth")
AUTH_COOKIE_NAME = SESSION_COOKIE_NAMES[-1]  # 旧版兼容名 (清库/日志仍引用)
_WORKSPACE_URL_RE = re.compile(r"/(?:console|workspace)/(wrk_[A-Za-z0-9]+)")

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
# 登录入口偏离自愈 (watcher 持续判定) 的限流: 相邻 reset 间隔与总次数上限
_ENTRY_RESET_INTERVAL_SEC = 10.0
_ENTRY_RESET_MAX = 6
# 读取残留会话基线的上限: 窗口未就绪时 pywebview 的 get_cookies 会一直挂,
# 超时即放弃采集 (退回数据库旧凭证指纹比对)
COOKIE_READ_TIMEOUT = 2.0
# 该读取失败时的日志节流间隔 (监听线程每秒轮询, 失败会连片出现)
_CORE_READ_LOG_INTERVAL = 10.0
_LOG_FILE = os.path.join(tempfile.gettempdir(), "gousage_login.log")


def _log(msg: str) -> None:
    """同时输出到 stdout 与日志文件 (便于诊断).

    带时间戳与 PID: 该文件在公共临时目录里是跨进程追加的 (每次启动/每个
    实例都写同一份), 没有时间戳时无法判断某行属于哪一次运行 —— 排查"日志
    停更"这类问题时这是唯一能把时间线钉住的线索.
    """
    line = f"{time.strftime('%m-%d %H:%M:%S')} [pid {os.getpid()}] {msg}"
    print(line, flush=True)
    try:
        # 0600: 该文件位于公共临时目录, 防其他本地用户读取
        fd = os.open(_LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


try:  # 历史版本可能以默认 0644 创建过日志: 收紧权限
    os.chmod(_LOG_FILE, 0o600)
except OSError:
    pass


def build_login_url(provider: str = PROVIDER_OPENCODE) -> str:
    """构造登录入口 URL (opencode: 控制台登录页, next 指向控制台首页)."""
    if provider == PROVIDER_COMMANDCODE:
        return CC_LOGIN_BASE
    return f"{CONSOLE_LOGIN_URL}?next={quote(LOGIN_NEXT_PATH, safe='')}"


def session_cookie_names(provider: str) -> tuple[str, ...]:
    """provider -> 按优先级排列的会话 cookie 候选名."""
    if provider == PROVIDER_COMMANDCODE:
        return (CC_AUTH_COOKIE_NAME,)
    return SESSION_COOKIE_NAMES


def _pick_session_cookie(cookies, provider: str = PROVIDER_OPENCODE) -> Optional[tuple[str, str]]:
    """按优先级挑选 provider 的会话 cookie, 返回 (cookie名, 值)."""
    jar = dict(_cookie_entries(cookies or []))
    for name in session_cookie_names(provider):
        value = jar.get(name) or ""
        if value.strip():
            return name, value
    return None


def provider_host(provider: str) -> str:
    """provider -> 其会话 cookie 所在的域."""
    return CC_HOST if provider == PROVIDER_COMMANDCODE else OPCODE_HOST


def _domain_matches(domain: str, host: str) -> bool:
    """cookie 的 domain 是否属于 host (兼容 ``.host`` 父域写法)."""
    d = (domain or "").strip().lstrip(".").lower()
    return bool(d) and (d == host or d.endswith("." + host))


_GITHUB_HOST_RE = re.compile(r"^https://(?:[\w.-]*\.)?github\.com(?:/|$)", re.IGNORECASE)
_OAUTH_ENTRY_RE = re.compile(
    r"^https://github\.com/login(?:\?|/oauth/authorize\?)", re.IGNORECASE
)
# 登录流程中间页: 登录表单 / 两步验证 / 设备验证等 (这些页面等待用户操作, 不算卡死)
_GITHUB_FLOW_RE = re.compile(
    r"^https://github\.com/(?:login(?:[/?]|$)|sessions(?:/|$)|two_factor)", re.IGNORECASE
)
_RETURN_TO_RE = re.compile(r"[?&]return_to=(.+)$")
# 确认 GitHub 已登录后, 停在无关页面等待这么久才自动续跑 (用户反馈 3s 体验更佳)
_GITHUB_STUCK_GRACE_SEC = 3.0
_GITHUB_MAX_RELOADS = 3

# 登录窗没有浏览器后退按钮 (WebView2 发布版禁用 Alt+←), GitHub 侧误点后无法返回。
# 在非 opencode.ai 页面注入悬浮导航: ← 返回 (history.back) / 继续登录 (续跑授权入口)。
_NAV_HELPER_TEMPLATE = """
(function(){
  var resume = '__RESUME_URL__';
  if (window.__gogaugeNav) { window.__gogaugeResume = resume; return; }
  window.__gogaugeNav = 1;
  window.__gogaugeResume = resume;
  var bar = document.createElement('div');
  bar.style.cssText = 'position:fixed;bottom:10px;left:10px;z-index:2147483647;'
    + 'font:12px/1.2 system-ui,sans-serif;white-space:nowrap;';
  var btn = 'padding:5px 10px;margin-right:6px;border-radius:6px;'
    + 'border:1px solid rgba(0,0,0,.25);background:rgba(255,255,255,.95);'
    + 'color:#111;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.35);';
  var back = document.createElement('button');
  back.textContent = '\\u2190 \\u8fd4\\u56de';
  back.style.cssText = btn;
  back.onclick = function(){ history.back(); };
  bar.appendChild(back);
  if (resume) {
    var go = document.createElement('button');
    go.textContent = '\\u7ee7\\u7eed\\u767b\\u5f55 \\u2192';
    go.style.cssText = btn;
    go.onclick = function(){ location.assign(window.__gogaugeResume); };
    bar.appendChild(go);
  }
  document.documentElement.appendChild(bar);
})();
"""


def _classify_github_url(url: str) -> Optional[str]:
    """GitHub 页面分类: "entry"(授权入口) / "flow"(登录流程页) / "stuck"(无关页) / None."""
    if not _GITHUB_HOST_RE.match(url or ""):
        return None
    if _OAUTH_ENTRY_RE.match(url) and "client_id=" in url:
        return "entry"
    if _GITHUB_FLOW_RE.match(url):
        return "flow"
    return "stuck"


def _authorize_url_from_entry(entry_url: str) -> Optional[str]:
    """从 GitHub 登录入口 URL 提取可续跑的 authorize URL.

    入口形如 ``github.com/login?client_id=...&return_to=%2Flogin%2Foauth%2Fauthorize%3F...``
    (return_to 可能是未编码/编码/混合编码 — WebView2 不同时机返回的地址栏形态不一致);
    提取 authorize 路径后对 query 值做规范化 (解到不含百分号编码为止, 再统一
    单层编码), 并去掉 ``prompt=select_account``, 让已登录会话直接续跑授权。
    """
    if not entry_url:
        return None
    target: Optional[str] = None
    if "/login/oauth/authorize" in entry_url:
        target = entry_url[entry_url.find("/login/oauth/authorize"):]
    else:
        match = _RETURN_TO_RE.search(entry_url)
        if match:
            decoded = unquote(match.group(1))
            idx = decoded.find("/login/oauth/authorize")
            if idx >= 0:
                target = decoded[idx:]
    if not target:
        return None
    return _normalize_authorize_target(target)


def _normalize_authorize_target(target: str) -> Optional[str]:
    """规范化 authorize 目标 URL 的 query (修复混合编码导致的 redirect_uri 失配).

    混合编码形态里 redirect_uri 可能仍是 ``https%253A%252F%252F...`` (双重编码),
    GitHub 解一层后看到的是编码串, 与注册回调不匹配, 会报
    "The redirect_uri is not associated with this application"。这里把每个
    query 值解到不含百分号编码, 再统一单层编码重建 URL。
    """
    path, _, query = target.partition("?")
    pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        if key == "prompt" and value == "select_account":
            continue  # 已登录续跑不需要账号选择器
        for _ in range(3):
            if "%" not in value:
                break
            try:
                decoded = unquote(value)
            except Exception:  # noqa: BLE001 非法编码: 保留原值
                break
            if decoded == value:
                break
            value = decoded
        pairs.append((key, value))
    if not any(key == "client_id" for key, _ in pairs):
        return None
    return "https://github.com" + path + "?" + urlencode(pairs)


def _github_logged_user(win) -> str:
    """读取 GitHub 页面的登录用户名 (meta user-login); 未登录/读取失败返回 ''.

    上游做法: pywebview 的 evaluate_js, 但带超时 —— 它内部用无超时信号量, 页面
    加载中调用会永久挂起监听线程.
    """
    result = _bounded_call(
        lambda: win.evaluate_js(
            "(document.querySelector('meta[name=user-login]')||{}).content||''"
        ),
        COOKIE_READ_TIMEOUT,
    )
    return str(result or "").strip()


# ── 关于 WebView2 原生调用: 登录链路一律不要碰 ────────────────────────────
# 曾经这里有一整套 _win_* 辅助, 通过 pywebview 的 window.native 链
# (BrowserForm -> EdgeChrome -> WebView2 控件 -> CoreWebView2) 直接操作 WebView2,
# 用来按域清 cookie / 读页面状态 / 有界导航。2026-10-10 实测: CoreWebView2 只能
# 在 .NET UI 线程访问, 跨线程读会退化成 COM 封送互锁, 调用线程连同 GIL 一起卡住
# —— 主窗口"无响应" + 本地 HTTP 服务停止 accept, 只能强杀进程 (py-spy 栈停在
# 那次跨线程读上)。整套已删除, 登录链路回归上游: 只用 pywebview 的窗口方法
# (get_current_url / get_cookies / clear_cookies / load_url / evaluate_js), 且一律
# 经 _bounded_call 包裹 —— 它们内部是无超时信号量, 不包裹就可能挂住监听线程。


_core_read_log_at = 0.0


def _log_throttled(msg: str) -> None:
    """轮询路径上的失败日志按 10s 节流 (监听线程每秒都读, 不节流会刷屏)."""
    global _core_read_log_at
    now = time.monotonic()
    if now - _core_read_log_at < _CORE_READ_LOG_INTERVAL:
        return
    _core_read_log_at = now
    _log(msg)
def login_entry_lost(win, provider: str) -> bool:
    """登录窗口是否被残留会话带离了登录入口.

    仅 commandcode 判定: 其登录入口就是 ``/signin`` 单页, 若页面加载完却停在
    该域的其它路径 (官网首页/控制台), 说明服务端按残留会话把我们重定向走了,
    用户根本没有登录的机会. opencode 的 OAuth 流程会合法地跨多域多路径,
    不做判定 (返回 False).

    豁免: 带 ``code=`` 查询参数的 provider 域 URL 是 GitHub 等 OAuth 的成功
    回调 —— 服务端正要据此种会话, 此刻判偏离会把刚建立的会话清掉, 直接
    打断登录. (失败回调带 error= 不带 code=, 不豁免 —— 清会话拉回登录页
    正是期望行为.)
    """
    if provider != PROVIDER_COMMANDCODE:
        return False
    got = _bounded_call(win.get_current_url, COOKIE_READ_TIMEOUT)
    if got is None:  # 窗口未就绪/已销毁: 不判定偏离
        return False
    url = got or ""
    host = provider_host(provider)
    if not url.startswith("https://" + host):
        return False
    parsed = urlparse(url)
    if parsed.path.startswith("/signin"):
        return False
    if any(key == "code" for key, _ in parse_qsl(parsed.query)):
        return False
    return True


def reset_login_session(win, provider: str) -> bool:
    """把被残留会话带走的登录窗口拉回登录入口 (cookie + 页面存储一起清).

    返回是否做过干预. 调用方负责确认"登录尚未成功"再调用 —— 否则会把刚建立
    的会话清掉.

    Windows 的关键顺序: 先把窗口导航到 about:blank **停掉旧页面的 JS**, 再清
    cookie —— 复用窗口里上一个会话的页面 (官网/控制台) 还在运行, 其定时请求
    会拿到服务端续发的 Set-Cookie, "清了又出现"就是这么来的; 直接清 cookie
    时它与旧页面 JS 竞速, 真机上常输. about:blank 提交后旧页面即终止, 清理
    结果才稳定.
    """
    if not login_entry_lost(win, provider):
        return False
    host = provider_host(provider)
    _log(f"[login] fell off the sign-in entry on {host} -> reset session and retry")
    if sys.platform == "win32":
        # 上游做法: 有界导航 + 清 cookie 都走 pywebview, 不再摸 WebView2 原生
        # 对象 (跨线程碰 CoreWebView2 会让整个进程互锁)
        _bounded_ok(lambda: win.load_url("about:blank"), COOKIE_PURGE_TIMEOUT)
        clear_provider_cookies(provider, win)
        if not _bounded_ok(
            lambda: win.load_url(build_login_url(provider)), COOKIE_PURGE_TIMEOUT
        ):
            _log("[login] reload sign-in entry failed (navigate unavailable)")
        return True
    clear_provider_cookies(provider, win)
    try:
        win.load_url(build_login_url(provider))
    except Exception as exc:  # noqa: BLE001 窗口可能已被关闭
        _log(f"[login] reload sign-in entry failed: {exc}")
    return True
def clear_login_cookies(win) -> bool:
    """清空登录窗口的 Cookie, 确保出现登录页 (可切换账号).

    上游做法: pywebview 的 ``clear_cookies`` —— Windows 侧就是 WebView2 的
    profile 级 DeleteAllCookies, 旧会话凭证已落库不受影响; 本应用 WebView 里的
    cookie 只服务于 provider 登录页, 全清是安全的。代价是没有按域回读可验证,
    由 LoginWatcher 的旧凭证指纹比对兜底。

    原生的按域 CookieManager 清理已废弃: 它要跨线程摸 CoreWebView2 (WebView2
    规定该属性只能在 UI 线程访问), 是登录链路上唯一会让整个进程互锁的地方。
    调用带超时 —— pywebview 内部是 Control.Invoke, UI 线程被占住时不返回。
    """
    if win is None:
        return False
    try:
        clear = win.clear_cookies
    except AttributeError:  # 老版本 pywebview 无此能力: 由指纹比对兜底
        _log("[login] clear_cookies unavailable")
        return False
    if not _bounded_ok(clear, COOKIE_PURGE_TIMEOUT):
        _log("[login] clear_cookies did not complete (window not ready)")
        return False
    _log("[login] cookies cleared for fresh sign-in")
    return True


def clear_provider_cookies(provider: str, win=None) -> int:
    """删除 WebView cookie store 中该 provider 域的会话 cookie, 返回删除条数.

    必须在加载登录页之前调用. pywebview 的 private_mode 只在 create_window 时
    清理网站数据, 而登录窗口是被复用的 (hide/show): 上一轮的会话 cookie 仍在
    store 里, 会让登录页据旧凭证直接跳转后台 (无法重新选择账号), 并让
    LoginWatcher 把这份残留凭证当成"刚登录成功".

    - macOS: WKHTTPCookieStore 逐条删除, 不触碰其它域与 localStorage;
    - Windows: 走上游的 clear_cookies (见 clear_login_cookies), 返回 0 ——
      它不报条数, 也不需要: 残留判定由 LoginWatcher 的指纹比对负责;
    - 其它平台返回 0, 由 LoginWatcher 的旧凭证比对兜底.
    """
    if sys.platform == "win32":
        clear_login_cookies(win)
        return 0
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


def build_token(provider: str, cookie_value: str, cookie_name: str = "") -> str:
    """cookie 值 -> 库内凭证形态 (``cookie名=值``, 服务端按该名回填请求头).

    opencode 的会话 cookie 名随控制台改版变化 (``__Host-console_session`` /
    旧版 ``auth``), 捕获时以实际命中的名为准; 旧调用不传名字时按旧版兼容.
    """
    if provider == PROVIDER_COMMANDCODE:
        return f"{CC_AUTH_COOKIE_NAME}={cookie_value}"
    return f"{cookie_name or AUTH_COOKIE_NAME}={cookie_value}"


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

    只服务于 macOS 的加载看门狗 (Windows 不再有看门狗, 见 _arm_login_window):
    直接问底层 WKWebView 的 estimatedProgress/isLoading, 不走 pywebview 的窗口
    方法 —— 后者用无超时信号量等主线程回调, 页面加载中调用会一直挂住.
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
    """让窗口重新加载当前页 (需在主线程之外调用; 仅 macOS 的看门狗用到)."""
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
    """读登录页的内部状态 (诊断用): 直接问底层 WebView, 不经 pywebview.

    pywebview 的 evaluate_js 会挂在无超时信号量上 (页面加载中必挂), 这里用
    pyobjc 的 completion handler 自己收结果, 用来区分"页面没渲染"和"渲染了但
    没显示出来". 仅 macOS 的 arm 侧用到 (Windows 不再做快照).
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

    连续读不到加载状态 (窗口尚未就绪/WebView 不可用) 就提前放弃, 不再空转到
    总超时 —— 登录本身由 LoginWatcher 独立完成, 看门狗只是兜底.
    """
    started = time.time()
    last_progress = -1.0
    last_change = time.time()
    reloads = 0
    unavailable = 0
    while time.time() - started < total_sec:
        state = page_load_state(win)
        if state is None:
            unavailable += 1
            if unavailable >= 3:
                _log("[login] page load watchdog: state unavailable, giving up")
                return False
            time.sleep(1.0)
            continue
        unavailable = 0
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

    Windows 不实现: WebView2 没有等价的导航前规则列表 (要在 UI 线程给每个域
    注册 WebResourceRequested 过滤器并构造空响应, 一旦异常会打到 UI 线程,
    有拖垮整个进程的风险); Chromium 对 pending 第三方资源的容忍度也更高
    (首屏不依赖 load 事件). 登录页卡死的场景由 ensure_login_page_loaded 的
    readyState 看门狗兜底.
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

    走上游的做法: pywebview 的 get_cookies, 但**必须带超时** —— 它内部用无超时
    信号量等待主线程回调, 窗口刚创建 (WebView 还没实例化) 时会一直挂住, 直接把
    open_login 卡死在"启动监听"之前.

    读不到 (超时/异常)返回 None, 由调用方的旧凭证指纹继续兜底.
    """
    targets = session_cookie_names(provider)
    box: dict[str, Optional[str]] = {}

    def worker() -> None:
        try:
            cookies = win.get_cookies() or []
        except Exception:  # noqa: BLE001 窗口未加载完成/已销毁
            return
        for name, value in _cookie_entries(cookies):
            if name in targets and value:
                box["value"] = value
                return

    reader = threading.Thread(target=worker, daemon=True, name="gousage-cookie-read")
    reader.start()
    reader.join(timeout)
    if reader.is_alive():
        _log("[login] cookie snapshot timed out (window not ready) -> no baseline")
        return None
    return box.get("value")


def _bounded_call(fn, timeout: float):
    """在 daemon 子线程里执行 fn, 最多等 timeout 秒 (超时返回 None).

    pywebview 的部分窗口方法内部用**无超时**信号量等 UI 线程回调, 一旦不返回
    就永久挂住调用线程 —— 登录监听会因此变僵尸 (单飞守卫再也不放行, 用户再点
    登录被静默吞掉). 读取类操作用它兜底: 超时即当"读不到"处理, 下一轮照常.
    """
    box: dict[str, object] = {}

    def worker() -> None:
        try:
            box["value"] = fn()
        except Exception:  # noqa: BLE001 窗口未加载完成/已销毁
            return

    thread = threading.Thread(target=worker, daemon=True, name="gousage-bounded-call")
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return None
    return box.get("value")


def _bounded_ok(fn, timeout: float) -> bool:
    """执行 fn 并最多等 timeout 秒, 返回是否在超时前正常跑完 (异常/超时 False).

    pywebview 的窗口方法内部多是 Control.Invoke / 无超时信号量: UI 线程被占住
    就不返回。窗口类操作用它包裹, 失败只当"这次没做成", 不会挂住调用线程。
    """

    def run() -> bool:
        fn()
        return True

    return _bounded_call(run, timeout) is True


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
        # GitHub 卡死自动续跑状态 (仅 opencode 的 OAuth 登录用到)
        self._oauth_entry: Optional[str] = None  # 最近一次授权入口 URL
        self._stuck_since: Optional[float] = None  # 停在无关 GitHub 页面的起始时刻
        self._reloads = 0  # 已自动续跑次数
        self._github_cls: Optional[str] = None  # 上次记录的 GitHub 页面分类 (去重日志)
        self._last_nav = ""
        # 每轮轮询的进展时刻: 供单飞守卫判定监听线程是否已成僵尸
        self._last_tick = time.monotonic()
        # 登录入口偏离自愈状态 (commandcode 单页入口)
        self._entry_resets = 0
        self._last_entry_reset: Optional[float] = None  # None = 还没 reset 过

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="gousage-login")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def seconds_since_tick(self) -> float:
        """距最近一次轮询进展的秒数 (监听线程卡死时持续增长)."""
        return time.monotonic() - self._last_tick

    def _window_alive(self) -> bool:
        try:
            return self.win in webview.windows
        except Exception:  # noqa: BLE001
            return False

    def _target_host(self) -> str:
        return provider_host(self.provider)

    def _target_cookie_names(self) -> tuple[str, ...]:
        return session_cookie_names(self.provider)

    def _read_cookie_pairs(self) -> list[tuple[str, str]]:
        """读取窗口 cookie, 归一为 (name, value) 对, 供命中目标 cookie 用.

        上游做法: pywebview 的 get_cookies。它在 Windows 上内部用**无超时**信号量
        等 UI 线程回调 (轮询撞上导航时 GetCookiesAsync 拿到 null URL, .NET 抛异常
        后信号量不再释放), 所以必须带超时调用 —— 超时只当"这轮读不到", 下一轮
        照常, 不会让监听线程变僵尸 (单飞守卫再也不放行, 用户再点登录被静默吞掉).
        """
        cookies = _bounded_call(self.win.get_cookies, COOKIE_READ_TIMEOUT)
        if cookies is None:
            _log_throttled("[login] cookie read timed out (window not ready)")
            return []
        return _cookie_entries(cookies or [])

    def _is_stale(self, value: str, name: str = "") -> bool:
        """该凭证是否为登录开始前就已存在的残留会话 (指纹按库内形态计算)."""
        if self.baseline_value and value == self.baseline_value:
            return True
        return (
            token_fingerprint(build_token(self.provider, value, name)) in self.stale_fps
        )

    def _run(self) -> None:
        _log(
            f"[login] watcher started provider={self.provider} "
            f"stale={len(self.stale_fps)} baseline={'yes' if self.baseline_value else 'no'}"
        )
        target_host = self._target_host()
        targets = self._target_cookie_names()
        while not self._stop.is_set():
            self._last_tick = time.monotonic()
            # 每轮主动检查窗口存活: macOS 关闭窗口后 get_current_url() 返回 None
            # 而非抛异常, 仅靠异常分支检测会让线程变僵尸 (阻塞单飞守卫, 无法再次登录)
            if not self._window_alive():
                _log("[login] window gone, watcher exits")
                break
            # Windows 也走 pywebview 的 get_current_url (上游做法), 但带超时:
            # 它内部用无超时信号量等 UI 线程回调, UI 线程被页面加载占住时会永久
            # 挂起本线程 (单飞守卫随之卡死, 用户无法再次登录).
            if sys.platform == "win32":
                got = _bounded_call(self.win.get_current_url, COOKIE_READ_TIMEOUT)
                if got is None:
                    # 读不到分两种: 页面还没落地 (正常, 下一轮再看) / 窗口已销毁
                    if not self._window_alive():
                        _log("[login] window closed, watcher exits")
                        break
                    self._stop.wait(1.0)
                    continue
                url = got or ""
            else:
                try:
                    url = self.win.get_current_url() or ""
                except Exception as exc:  # noqa: BLE001 窗口未加载完成或已销毁
                    if not self._window_alive():
                        _log("[login] window closed, watcher exits")
                        break
                    self._stop.wait(1.0)
                    continue

            if url != self._last_nav:  # 任意域名的 URL 变化都记录 (暴露监听盲区)
                _log(f"[login] nav: {url[:180]}")
                self._last_nav = url

            if url.startswith("https://" + target_host):
                if self._capture_session(url, targets):
                    return
                self._check_entry_drift()
            elif _GITHUB_HOST_RE.match(url):
                # 两个 provider 的登录页都有 "Continue with GitHub": GitHub 侧
                # 2FA 后丢 return_to 卡死在无关页面的问题与续跑手段完全一致
                # (授权 URL 重构只依赖 github.com 通用形态, redirect_uri 原样
                # 保留, 授权后自然回各自 provider 域), 不区分 provider
                self._watch_github(url)
            self._stop.wait(COOKIE_POLL_SEC)
        if not self.done and self.on_cancelled:
            self.on_cancelled()

    def _check_entry_drift(self) -> None:
        """登录窗口被残留会话带离登录入口时, 随轮询持续拉回 (commandcode).

        _arm_login_window 的自愈只在页面加载完成时检查一两次, 覆盖不到
        "客户端路由慢跳" —— 登录页加载完时还在 /signin, 之后页面 JS 才检测
        到残留会话并跳去官网, 此后没有任何东西把窗口拉回来, 监听器只能在
        原地永远等新凭证 (真机表现为"打开官网后卡住"). 这里每轮轮询判定,
        偏离即重置会话并拉回; 限流防与 arm 侧自愈 / 连续偏离打环.
        """
        if self.done:
            return
        if not login_entry_lost(self.win, self.provider):
            return
        now = time.monotonic()
        if (
            self._last_entry_reset is not None
            and now - self._last_entry_reset < _ENTRY_RESET_INTERVAL_SEC
        ):
            return  # 限流窗口内: 刚 reset 过, 等导航落地
        if self._entry_resets >= _ENTRY_RESET_MAX:
            return  # 反复被带走说明清不干净, 停止拉回避免无限循环
        self._entry_resets += 1
        self._last_entry_reset = now
        _log(f"[login] entry drift detected -> reset #{self._entry_resets}")
        reset_login_session(self.win, self.provider)

    def _capture_session(self, url: str, targets: tuple[str, ...]) -> bool:
        """窗口已在 provider 域: 读 cookie 并尝试捕获本次登录的新会话.

        返回是否捕获成功 (成功即收工, 监听结束).
        """
        try:
            pairs = self._read_cookie_pairs()
            names_desc = [name for name, _value in pairs]
        except Exception as exc:  # noqa: BLE001
            pairs = []
            names_desc = [f"<read_cookies ERROR {type(exc).__name__}: {exc}>"]
        _log(f"[login] on {self._target_host()}, url={url[:120]}, cookie_names={names_desc}")

        # 按候选名优先级挑会话 cookie (新版 __Host-console_session 优先)
        picked: Optional[tuple[str, str]] = None
        for want in targets:
            picked = next(((n, v) for n, v in pairs if n == want and v), None)
            if picked:
                break
        if not picked:
            return False
        name, value = picked
        if self._is_stale(value, name):
            # 残留会话: 用户可能还在授权页, 页面也可能被旧凭证直接
            # 带到后台. 继续轮询, 等真正的新凭证落地再收工.
            if not self._stale_logged:
                self._stale_logged = True
                _log("[login] stale session cookie only, waiting for fresh sign-in")
            return False
        workspace_hint = "Default"
        if self.provider == PROVIDER_OPENCODE:
            match = _WORKSPACE_URL_RE.search(url)
            workspace_hint = match.group(1) if match else "Default"
        _log(f"[login] SUCCESS: cookie {name} captured (len={len(value)}), ws={workspace_hint}")
        self.done = True
        self._stop.set()
        token = build_token(self.provider, value, name)
        self.on_success(token, workspace_hint, self.provider)
        return True

    def _watch_github(self, url: str) -> None:
        """跟踪 GitHub 页面: 记录授权入口; 已登录却停在无关页面时自动续跑 OAuth."""
        cls = _classify_github_url(url)
        if cls != self._github_cls:  # 页面状态变化时记日志 (诊断用)
            self._github_cls = cls
            _log(f"[login] github page {cls}: {url[:180]}")

        if cls == "entry":
            self._oauth_entry = url
            self._stuck_since = None
        elif cls != "stuck":  # 登录表单/两步验证/设备验证等流程页: 正常等待用户
            self._stuck_since = None
        else:
            self._stuck_handle_stuck()
        self._inject_nav_helper(cls or "entry")

    def _stuck_handle_stuck(self) -> None:
        """已登录 GitHub 但窗口停在无关页面: 宽限后自动重新拉起授权入口."""
        now = time.monotonic()
        if self._stuck_since is None:
            self._stuck_since = now
        if now - self._stuck_since < _GITHUB_STUCK_GRACE_SEC:
            return
        if self._reloads >= _GITHUB_MAX_RELOADS:
            return
        if not _github_logged_user(self.win):
            return  # 仍在登录前状态 (如设置页未登录), 不打扰
        # 交替目标: 奇数次用重构的 authorize URL (全自动); 偶数次用原始入口
        # (GitHub 原生链路, 保真不重构 — 重构 URL 因编码问题失败时的兜底)
        target: Optional[str] = None
        if self._reloads % 2 == 0:
            target = _authorize_url_from_entry(self._oauth_entry or "")
        if not target and self._oauth_entry:
            target = self._oauth_entry
        if not target:
            _log("[login] github signed-in but OAuth entry URL missing; cannot auto-resume")
            self._reloads = _GITHUB_MAX_RELOADS  # 无入口可续跑, 停止重试
            return
        self._reloads += 1
        self._stuck_since = None
        _log(f"[login] github signed-in but OAuth stalled -> resume #{self._reloads}: {target[:180]}")
        if not _bounded_ok(lambda: self.win.load_url(target), COOKIE_PURGE_TIMEOUT):
            _log("[login] resume load_url failed (window busy)")

    def _inject_nav_helper(self, cls: str) -> None:
        """在 GitHub 页面注入导航按钮 (每轮轮询执行, 页面内有去重守卫).

        授权入口/流程页只给 "← 返回"; 真正卡死的页面才显示 "继续登录 →"
        (授权页上 GitHub 自带 Authorize 按钮, 重复注入续跑按钮容易混淆)。
        """
        resume = ""
        if cls == "stuck":
            resume = _authorize_url_from_entry(self._oauth_entry or "") or ""
        js = _NAV_HELPER_TEMPLATE.replace("__RESUME_URL__", resume.replace("'", ""))
        # 上游做法: pywebview 的 evaluate_js, 但带超时 —— 它内部等无超时信号量,
        # UI 线程不泵消息就永久挂住监听线程; 失败只是这轮没注入, 下轮再来
        _bounded_call(lambda: self.win.evaluate_js(js), COOKIE_PURGE_TIMEOUT)
