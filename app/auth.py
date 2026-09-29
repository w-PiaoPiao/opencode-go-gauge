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
    """构造登录入口 URL (opencode: 控制台登录页, next 指向控制台首页)."""
    if provider == PROVIDER_COMMANDCODE:
        return CC_LOGIN_BASE
    return f"{CONSOLE_LOGIN_URL}?next={quote(LOGIN_NEXT_PATH, safe='')}"


def session_cookie_names(provider: str) -> tuple[str, ...]:
    """provider -> 按优先级排列的会话 cookie 候选名."""
    if provider == PROVIDER_COMMANDCODE:
        return (CC_AUTH_COOKIE_NAME,)
    return SESSION_COOKIE_NAMES


def _cookie_value(cookie) -> dict[str, str]:
    """把 pywebview 返回的 cookie 对象摊平成 {name: value}."""
    pairs: dict[str, str] = {}
    if isinstance(cookie, SimpleCookieCls):  # SimpleCookie 是 dict 子类, 需先判断
        for name in list(cookie.keys()):
            try:
                pairs[name] = cookie[name].value
            except Exception:  # noqa: BLE001
                continue
    elif isinstance(cookie, dict):
        name = cookie.get("name") or ""
        if name:
            pairs[name] = cookie.get("value") or ""
    return pairs


def _pick_session_cookie(cookies, provider: str = PROVIDER_OPENCODE) -> Optional[tuple[str, str]]:
    """按优先级挑选 provider 的会话 cookie, 返回 (cookie名, 值)."""
    jar: dict[str, str] = {}
    for cookie in cookies or []:
        jar.update(_cookie_value(cookie))
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
    """读取 GitHub 页面的登录用户名 (meta user-login); 未登录/读取失败返回 ''."""
    try:
        result = win.evaluate_js(
            "(document.querySelector('meta[name=user-login]')||{}).content||''"
        )
    except Exception:  # noqa: BLE001 页面未就绪/窗口销毁
        return ""
    return str(result or "").strip()


# ── Windows (WebView2) 辅助 ────────────────────────────────────────────────
# pywebview 的 winforms 后端把 WebView2 挂在 window.native (BrowserForm) 上:
#   native -> .browser (EdgeChrome) -> .webview (WebView2 控件) -> .CoreWebView2
# 所有窗口共享同一 UserDataFolder (后端的 cache_dir 是进程级全局), cookie store
# 因此也是同一份 —— 登录窗口刚重建 (WebView2 还在异步初始化) 或已被销毁时,
# 借主窗口的实例同样能读到/清掉目标域 cookie.
#
# 为什么不直接调 pywebview 的窗口方法: get_cookies 内部用**无超时**的
# Semaphore.acquire() 等 UI 线程回调, 且读取用 GetCookiesAsync(self.url) ——
# 窗口刚渲染过引导页 (load_html) 时 self.url 为 None, .NET 侧抛异常后信号量
# 不再释放, 调用线程会永久挂起; evaluate_js 同理. 这里自己走 Control.Invoke
# + Task, 每一步都有超时, 任一环节失败只降级不阻塞.


def _win_core_webview(win):
    """Windows: 取窗口底层 WebView2 的 CoreWebView2 (未就绪返回 None)."""
    try:
        native = getattr(win, "native", None)          # BrowserForm
        browser = getattr(native, "browser", None)     # EdgeChrome
        control = getattr(browser, "webview", None)    # WebView2 控件
        return getattr(control, "CoreWebView2", None)  # 未初始化时 .NET null -> None
    except Exception:  # noqa: BLE001 窗口已销毁/pywebview 内部结构变化
        return None


def _win_webview_pair(win, allow_fallback: bool = False):
    """Windows: 返回 (core, control) —— 优先传入窗口.

    ``allow_fallback=True`` 时传入窗口取不到 core 就借其它存活窗口, 仅用于
    cookie 读写: 所有窗口共享同一 cookie store (后端的 cache_dir 是进程级
    全局), 借来的实例效果完全相同, 且登录窗口刚重建 (WebView2 还在异步
    初始化) 或已销毁时这是唯一能清残留的通道.
    页面状态类操作 (执行 JS/加载判定/reload) 必须用窗口自己的实例, 否则会
    读到另一个窗口的页面 (例如把主窗口面板的 readyState 当成登录页的).
    """
    candidates: list = [win] if win is not None else []
    if allow_fallback:
        try:
            candidates += [w for w in list(webview.windows) if w is not win]
        except Exception:  # noqa: BLE001
            pass
    for cand in candidates:
        if cand is None:
            continue
        core = _win_core_webview(cand)
        if core is None:
            continue
        control = getattr(cand, "native", None)
        if control is not None:
            return core, control
    return None, None


def _win_ui_delegate(fn):
    """pythonnet: 把 Python 函数包成 .NET delegate 供 Control.Invoke 使用.

    单独成函数便于测试替身 (非 Windows 平台无 pythonnet).
    """
    from System import Func, Type  # noqa: E402 仅 Windows 运行时可导入

    return Func[Type](fn)


def _win_invoke_bounded(control, fn, timeout: float) -> bool:
    """在 Windows UI 线程执行 fn, 超时即放弃 (不阻塞调用方).

    底层 Control.Invoke 从非 UI 线程调用会阻塞到执行完; UI 线程被模态对话框/
    同步加载占住时会一直等. 因此放进 daemon 子线程并 join 超时 —— 超时后 fn
    仍可能稍后执行 (消息队列排空后), 所以只用于幂等的读取/清理.

    已在 UI 线程时直接放弃: 调用方都要在非 UI 线程等 .NET Task, 在 UI 线程
    等一个需要 UI 线程泵消息才能完成的 Task 会互锁 (与 macOS 侧的 callAfter
    规避同一原理).
    """
    try:
        if not bool(control.InvokeRequired):
            return False
    except Exception:  # noqa: BLE001 句柄未创建/fake 控件
        return False
    outcome: dict[str, object] = {}

    def worker() -> None:
        try:
            control.Invoke(_win_ui_delegate(fn))
            outcome["ok"] = True
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = repr(exc)

    thread = threading.Thread(target=worker, daemon=True, name="gousage-win-ui-invoke")
    thread.start()
    thread.join(timeout)
    return outcome.get("ok") is True


def _remaining(deadline: float, minimum: float = 0.05) -> float:
    """距 deadline 的剩余秒数 (下限兜底, 供多步操作共享一个总超时预算)."""
    return max(minimum, deadline - time.time())


def _win_wait_task(task, timeout: float) -> bool:
    """等 .NET Task 完成 (必须从非 UI 线程调用, 否则与 UI 线程互锁)."""
    try:
        return bool(task.Wait(max(1, int(timeout * 1000))))
    except Exception:  # noqa: BLE001 任务自身失败/超时
        return False


def _win_cookie_operation(win, host: str, handler, timeout: float):
    """Windows: 取 provider 域 cookie 列表并在 UI 线程交给 handler 处理.

    时序: UI 线程发起 GetCookiesAsync -> 调用线程 Wait(Task) -> UI 线程处理
    (WebView2 的 cookie 对象有线程亲和性, 必须在 UI 线程读写). 返回
    (ok, handler 的返回值); 任何一步异常/超时都返回 (False, None).

    允许借其它存活窗口的 core: cookie store 进程内共享 (见 _win_webview_pair).
    """
    core, control = _win_webview_pair(win, allow_fallback=True)
    if core is None or control is None:
        return False, None
    deadline = time.time() + timeout
    box: dict[str, object] = {}

    def start() -> None:
        try:
            box["task"] = core.CookieManager.GetCookiesAsync(f"https://{host}/")
        except Exception as exc:  # noqa: BLE001 WebView2 未就绪等
            box["error"] = repr(exc)

    if not _win_invoke_bounded(control, start, _remaining(deadline)):
        return False, None
    task = box.get("task")
    if task is None or not _win_wait_task(task, _remaining(deadline)):
        return False, None
    result: dict[str, object] = {}

    def handle() -> None:
        try:
            result["value"] = handler(list(task.Result), core.CookieManager)
        except Exception as exc:  # noqa: BLE001
            result["error"] = repr(exc)

    if not _win_invoke_bounded(control, handle, _remaining(deadline)):
        return False, None
    if "error" in result:
        return False, None
    return True, result.get("value")


def _win_read_provider_cookie_pairs(
    win, host: str, cookie_names, timeout: float
) -> Optional[list[tuple[str, str]]]:
    """Windows: 读取 provider 域指定名 cookie 的 (name, value) 对; 失败返回 None.

    ``cookie_names`` 为单个名字或按优先级排列的候选名元组 (opencode 新版
    ``__Host-console_session`` 优先, 旧版 ``auth`` 兼容): 同一 store 出现
    多个候选时, 返回列表按候选名优先级排序.

    空列表与 None 必须区分: 前者是"确实没有残留会话", 后者是"读不到" ——
    清 cookie 后的验证若把两者混同, 真机上就分不清"已清干净"和"清理没生效".
    """
    if isinstance(cookie_names, str):
        cookie_names = (cookie_names,)
    wanted = tuple(cookie_names)

    def collect(cookies, _cm) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for cookie in cookies:
            try:
                name, value = str(cookie.Name), str(cookie.Value)
            except Exception:  # noqa: BLE001 单个 cookie 异常不影响整体
                continue
            if name in wanted and value:
                pairs.append((name, value))
        return pairs

    ok, pairs = _win_cookie_operation(win, host, collect, timeout)
    if not ok:
        return None
    ordered: list[tuple[str, str]] = []
    for name in wanted:
        ordered.extend((n, value) for n, value in (pairs or []) if n == name)
    return ordered


def _win_read_provider_cookies(
    win, host: str, cookie_names, timeout: float
) -> Optional[list[str]]:
    """Windows: 读取 provider 域指定名 cookie 的值列表 (按候选名优先级)."""
    pairs = _win_read_provider_cookie_pairs(win, host, cookie_names, timeout)
    if pairs is None:
        return None
    return [value for _name, value in pairs]


def _win_clear_all_cookies(win, timeout: float) -> bool:
    """Windows: 清空 WebView2 cookie store (CookieManager.DeleteAllCookies).

    profile 级同步操作: 本应用 WebView 里的 cookie 只服务于 provider 登录页
    (会话凭证已入 SQLite), 全清不影响任何已保存账号 —— pywebview 在
    private_mode 下建首个窗口时也这么做, 上游版本的"添加账号前清会话"用的
    同样是 DeleteAllCookies.

    刻意不做"按域逐条删除": 那条链路要 GetCookiesAsync -> 等 Task 完成 ->
    在 UI 线程按域过滤, 任何一环在真机上失败都是静默跳过; 全清只有一次
    UI 线程调用, 失败面最小.
    """
    core, control = _win_webview_pair(win, allow_fallback=True)
    if core is None or control is None:
        _log("[login] cookie purge (win): no CoreWebView2 available")
        return False
    done: dict[str, object] = {}

    def wipe() -> None:
        try:
            core.CookieManager.DeleteAllCookies()
            done["ok"] = True
        except Exception as exc:  # noqa: BLE001 WebView2 未就绪等
            done["error"] = repr(exc)

    if not _win_invoke_bounded(control, wipe, timeout):
        _log("[login] cookie purge (win): UI invoke failed/timed out")
        return False
    if done.get("error"):
        _log(f"[login] cookie purge (win): DeleteAllCookies failed: {done['error']}")
        return False
    return done.get("ok") is True


def _win_clear_page_storage(win, timeout: float) -> bool:
    """Windows: 清当前页面的 localStorage/sessionStorage (best-effort).

    控制台/官网这类 SPA 可能把登录标记放在 localStorage, 由客户端路由直接
    跳到后台 —— 只清 cookie 挡不住. 页面需已位于目标域, 否则清的是空 storage
    (后续页面加载时会自然带上未登录态, 无损).
    """
    script = "try{localStorage.clear();sessionStorage.clear();}catch(e){}"
    return _win_run_js(win, script, timeout) is not None


def _win_current_url(win) -> str:
    """Windows: 读 EdgeChrome 跟踪的当前 URL.

    纯 Python 属性, 不 marshal 到 UI 线程、不等 loaded 事件 —— 可在任意
    后台线程安全调用 (pywebview 的 get_current_url 会等无超时信号量).
    """
    try:
        browser = getattr(getattr(win, "native", None), "browser", None)
        return str(getattr(browser, "url", "") or "")
    except Exception:  # noqa: BLE001
        return ""


def login_entry_lost(win, provider: str) -> bool:
    """登录窗口是否被残留会话带离了登录入口.

    仅 commandcode 判定: 其登录入口就是 ``/signin`` 单页, 若页面加载完却停在
    该域的其它路径 (官网首页/控制台), 说明服务端按残留会话把我们重定向走了,
    用户根本没有登录的机会. opencode 的 OAuth 流程会合法地跨多域多路径,
    不做判定 (返回 False).
    """
    if provider != PROVIDER_COMMANDCODE:
        return False
    if sys.platform == "win32":
        url = _win_current_url(win)
    else:
        try:
            url = win.get_current_url() or ""
        except Exception:  # noqa: BLE001 窗口未就绪/已销毁
            return False
    host = provider_host(provider)
    if not url.startswith("https://" + host):
        return False
    return not urlparse(url).path.startswith("/signin")


def reset_login_session(win, provider: str) -> bool:
    """把被残留会话带走的登录窗口拉回登录入口 (cookie + 页面存储一起清).

    返回是否做过干预. 调用方负责确认"登录尚未成功"再调用 —— 否则会把刚建立
    的会话清掉.
    """
    if not login_entry_lost(win, provider):
        return False
    host = provider_host(provider)
    _log(f"[login] fell off the sign-in entry on {host} -> reset session and retry")
    clear_provider_cookies(provider, win)
    if sys.platform == "win32":
        _win_clear_page_storage(win, COOKIE_PURGE_TIMEOUT)
    try:
        win.load_url(build_login_url(provider))
    except Exception as exc:  # noqa: BLE001 窗口可能已被关闭
        _log(f"[login] reload sign-in entry failed: {exc}")
    return True


def _win_run_js(win, script: str, timeout: float):
    """Windows: 在窗口里执行 JS 并取回结果, 失败/超时返回 None.

    自带超时的 ExecuteScriptAsync 封装 (pywebview 的 evaluate_js 用无超时
    信号量, 页面加载中会永久挂起).
    """
    core, control = _win_webview_pair(win)
    if core is None or control is None:
        return None
    deadline = time.time() + timeout
    box: dict[str, object] = {}

    def start() -> None:
        try:
            box["task"] = core.ExecuteScriptAsync(script)
        except Exception as exc:  # noqa: BLE001
            box["error"] = repr(exc)

    if not _win_invoke_bounded(control, start, _remaining(deadline)):
        return None
    task = box.get("task")
    if task is None or not _win_wait_task(task, _remaining(deadline)):
        return None
    raw: dict[str, object] = {}

    def read() -> None:
        try:
            raw["value"] = str(task.Result)
        except Exception as exc:  # noqa: BLE001
            raw["error"] = repr(exc)

    if not _win_invoke_bounded(control, read, _remaining(deadline)) or "error" in raw:
        return None
    try:
        return json.loads(str(raw.get("value")))
    except Exception:  # noqa: BLE001 非 JSON 结果 (如 undefined)
        return raw.get("value")


def _win_page_load_state(win) -> Optional[dict]:
    """Windows: 用 document.readyState + 当前 Source 判定登录页加载状态.

    WebView2 没有 estimatedProgress/IsLoading. readyState='complete' 表示文档
    及同步子资源就绪; Source 仍为空/about:blank 说明导航还没落地 (引导页阶段),
    视为加载中, 避免看门狗把引导页误判成登录页已加载.
    """
    ready = _win_run_js(win, "document.readyState", COOKIE_PURGE_TIMEOUT)
    if ready is None:
        return None
    core, _control = _win_webview_pair(win)
    try:
        source = str(getattr(core, "Source", "") or "")
    except Exception:  # noqa: BLE001
        source = ""
    loading = str(ready) != "complete" or not source.lower().startswith("http")
    return {"progress": 0.0 if loading else 1.0, "loading": loading}


def _win_reload_window(win) -> bool:
    """Windows: 让 WebView2 重新加载当前页."""
    core, control = _win_webview_pair(win)
    if core is None or control is None:
        return False
    done: dict[str, object] = {}

    def do_reload() -> None:
        try:
            core.Reload()
            done["ok"] = True
        except Exception as exc:  # noqa: BLE001
            done["error"] = repr(exc)

    if not _win_invoke_bounded(control, do_reload, COOKIE_PURGE_TIMEOUT):
        return False
    return done.get("ok") is True


def _win_purge_provider_session(win, provider: str) -> int:
    """Windows: 清空 cookie store 并回读验证 provider 会话确实消失.

    返回清掉的 provider 域会话 cookie 条数; 0 表示"本来就没有"或"清理/验证
    未通过" (区分写进日志 —— 真机排查时这一行是关键证据).
    """
    host = provider_host(provider)
    targets = session_cookie_names(provider)
    deadline = time.time() + COOKIE_PURGE_TIMEOUT * 2
    before = _win_read_provider_cookies(win, host, targets, _remaining(deadline))
    cleared = _win_clear_all_cookies(win, _remaining(deadline))
    after = _win_read_provider_cookies(win, host, targets, _remaining(deadline))
    if not cleared:
        _log(
            f"[login] cookie purge (win) FAILED on {host}: "
            f"before={'?' if before is None else len(before)} (store untouched)"
        )
        return 0
    if after is None:
        # 回读不可用: DeleteAllCookies 是 profile 级操作, 清了就是清了, 按成功处理
        _log(f"[login] cookie store wiped on {host} (verification unavailable)")
        return len(before or [])
    if after:
        # 清了又出现 (旧页面 JS 续写等): 如实上报, 由"偏离登录入口"的兜底重试处理
        _log(f"[login] cookie purge (win) incomplete on {host}: {len(after)} still present")
        return 0
    if before:
        _log(f"[login] purged {len(before)} stale cookie(s) on {host}")
    return len(before or [])


def clear_provider_cookies(provider: str, win=None) -> int:
    """删除 WebView cookie store 中该 provider 域的会话 cookie, 返回删除条数.

    必须在加载登录页之前调用. pywebview 的 private_mode 只在 create_window 时
    清理网站数据, 而登录窗口是被复用的 (hide/show): 上一轮的会话 cookie 仍在
    store 里, 会让登录页据旧凭证直接跳转后台 (无法重新选择账号), 并让
    LoginWatcher 把这份残留凭证当成"刚登录成功".

    - macOS: WKHTTPCookieStore 逐条删除, 不触碰其它域与 localStorage;
    - Windows: WebView2 DeleteAllCookies 全清 + 回读验证 (profile 级操作,
      本应用 WebView 里的 cookie 只服务于 provider 登录页; win 为目标登录
      窗口, 传 None 或该窗口 WebView2 未就绪时借任一存活窗口 —— cookie store
      进程内共享);
    - 其它平台返回 0, 由 LoginWatcher 的旧凭证比对兜底.
    """
    if sys.platform == "win32":
        try:
            return _win_purge_provider_session(win, provider)
        except Exception as exc:  # noqa: BLE001 清不掉不阻断登录 (有指纹兜底)
            _log(f"[login] cookie purge (win) failed: {exc}")
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

    不走 pywebview 的窗口方法 —— 后者用无超时信号量等主线程回调, 页面加载中
    调用会一直挂住 (get_current_url/evaluate_js 都是):
    - macOS: 直接问底层 WKWebView 的 estimatedProgress/isLoading;
    - Windows: ExecuteScriptAsync 读 document.readyState (自带超时).
    """
    if sys.platform == "win32":
        return _win_page_load_state(win)
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
    """让窗口重新加载当前页 (需在主线程之外调用; macOS/Windows 均有实现)."""
    if sys.platform == "win32":
        return _win_reload_window(win)
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
    pyobjc 的 completion handler / WebView2 的 Task 自己收结果, 用来区分
    "页面没渲染"和"渲染了但没显示出来".
    """
    if sys.platform == "win32":
        return _win_run_js(win, _SNAPSHOT_JS, _SNAPSHOT_TIMEOUT)
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

    - Windows: 走 WebView2 CookieManager 按域读取 (GetCookiesAsync 需要有效
      URL, 而 pywebview 的实现传的 self.url 在窗口刚渲染过引导页时为 None,
      会抛异常并让无超时信号量永久挂起);
    - macOS: pywebview 的 get_cookies, 必须带超时 —— 它用**无超时**信号量等待
      主线程回调, 窗口刚创建 (BrowserView 还没实例化) 时会一直挂住, 直接把
      open_login 卡死在"启动监听"之前.

    读不到 (超时/异常)返回 None, 由调用方的旧凭证指纹继续兜底.
    """
    if sys.platform == "win32":
        host = provider_host(provider)
        targets = session_cookie_names(provider)
        values = _win_read_provider_cookies(win, host, targets, timeout)
        if values:
            return values[0]
        _log("[login] cookie snapshot on win: no stale credential -> no baseline")
        return None
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

    def _target_cookie_names(self) -> tuple[str, ...]:
        return session_cookie_names(self.provider)

    def _read_cookie_pairs(self) -> list[tuple[str, str]]:
        """读取窗口 cookie, 归一为 (name, value) 对, 供命中目标 cookie 用.

        Windows 主路径不走 pywebview 的 get_cookies: 它内部用无超时信号量等
        UI 线程回调, 且以 EdgeChrome 自己跟踪的 URL 作 GetCookiesAsync 入参 ——
        轮询恰好撞上导航时该值可能为 None, .NET 抛异常后信号量不再释放, 监听
        线程会永久挂死 (单飞守卫再也不释放, 用户再点登录被静默拦截).

        但读取是登录能否被识别的唯一通道: 自带的按域读取不可用 (返回 None)
        时仍回退到 pywebview 的实现 —— 此刻 URL 已确认在 provider 域、页面
        也已加载完, 挂起风险低, 总比永远读不到 cookie 强.
        """
        if sys.platform == "win32":
            pairs = _win_read_provider_cookie_pairs(
                self.win, self._target_host(), self._target_cookie_names(), COOKIE_READ_TIMEOUT
            )
            if pairs is None:
                _log("[login] win cookie read unavailable -> falling back to pywebview")
                return _cookie_entries(self.win.get_cookies() or [])
            return list(pairs)
        return _cookie_entries(self.win.get_cookies() or [])

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

            if url != self._last_nav:  # 任意域名的 URL 变化都记录 (暴露监听盲区)
                _log(f"[login] nav: {url[:180]}")
                self._last_nav = url

            if url.startswith("https://" + target_host):
                if self._capture_session(url, targets):
                    return
            elif self.provider == PROVIDER_OPENCODE and _GITHUB_HOST_RE.match(url):
                self._watch_github(url)
            self._stop.wait(COOKIE_POLL_SEC)
        if not self.done and self.on_cancelled:
            self.on_cancelled()

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
        try:
            self.win.load_url(target)
        except Exception as exc:  # noqa: BLE001 窗口可能正忙, 下轮再试
            _log(f"[login] resume load_url ERROR: {exc}")

    def _inject_nav_helper(self, cls: str) -> None:
        """在 GitHub 页面注入导航按钮 (每轮轮询执行, 页面内有去重守卫).

        授权入口/流程页只给 "← 返回"; 真正卡死的页面才显示 "继续登录 →"
        (授权页上 GitHub 自带 Authorize 按钮, 重复注入续跑按钮容易混淆)。
        """
        resume = ""
        if cls == "stuck":
            resume = _authorize_url_from_entry(self._oauth_entry or "") or ""
        js = _NAV_HELPER_TEMPLATE.replace("__RESUME_URL__", resume.replace("'", ""))
        try:
            self.win.evaluate_js(js)
        except Exception:  # noqa: BLE001 页面未就绪/窗口销毁: 下轮再注入
            pass


def clear_login_cookies(win, provider: str = PROVIDER_OPENCODE) -> None:
    """清空登录窗口的 Cookie (添加新账号时确保出现登录页, 可切换账号).

    上游 v2.2.0 引入的通用入口; 本 fork 的 ``clear_provider_cookies`` 覆盖
    更多平台分支 (macOS 按域删除 / Windows DeleteAllCookies+回读验证),
    这里委托之, 保留两套调用方的同名习惯.
    """
    try:
        clear_provider_cookies(provider, win)
        _log("[login] cookies cleared for fresh sign-in")
    except Exception as exc:  # noqa: BLE001 清不掉不阻断登录 (有指纹兜底)
        _log(f"[login] clear cookies unavailable: {exc}")
