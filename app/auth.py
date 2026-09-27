"""WebView 登录: 加载 opencode.ai 控制台登录页, 捕获会话 cookie 与工作区 ID.

原理: pywebview (WebView2) 的 window.get_cookies() 可直接读取 HttpOnly cookie,
登录完成后窗口位于 opencode.ai 域, 从中提取会话 cookie.

2026-09 opencode.ai 前端改版: 旧授权页 ``auth.opencode.ai/authorize`` 与旧会话
cookie ``auth`` 已废弃, 现由 ``/console`` 控制台接管登录, 会话 cookie 为
``__Host-console_session`` (登录入口 https://opencode.ai/console/login)。

2026-09 GitHub 2FA 卡死修复: 控制台登录页 "Continue with GitHub" 会带
``client_id``/``code_challenge``/``redirect_uri`` 跳到 github.com/login; 开启
两步验证 (2FA) 的账号完成验证后, GitHub 可能丢失 OAuth 续跑链路 (return_to),
把窗口留在 github.com/settings/security 等无关页面且不再回跳 opencode.ai。
监听器确认 GitHub 已登录、窗口却停在无关 GitHub 页面超过宽限期时, 自动
重新加载先前记录的授权入口 URL, 依靠刚建立的 GitHub 会话续跑 authorize
→ 回跳 opencode.ai → 捕获会话 cookie。
"""
from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import uuid
from http.cookies import SimpleCookie as SimpleCookieCls
from typing import Callable, Optional
from urllib.parse import unquote

import webview

CONSOLE_LOGIN_URL = "https://opencode.ai/console/login"
LOGIN_NEXT_PATH = "/console/"
# 会话 cookie: 新版 __Host-console_session 优先, 旧版 auth 兼容历史账号
SESSION_COOKIE_NAMES = ("__Host-console_session", "auth")
COOKIE_POLL_SEC = 1.0
_WORKSPACE_URL_RE = re.compile(r"/(?:console|workspace)/(wrk_[A-Za-z0-9]+)")
_LOG_FILE = os.path.join(tempfile.gettempdir(), "gousage_login.log")


def _log(msg: str) -> None:
    """同时输出到 stdout 与日志文件 (便于诊断)."""
    print(msg, flush=True)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def build_login_url() -> str:
    """构造控制台登录页 URL (next 指向控制台首页)."""
    from urllib.parse import quote

    return f"{CONSOLE_LOGIN_URL}?next={quote(LOGIN_NEXT_PATH, safe='')}"


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


def _pick_session_cookie(cookies) -> Optional[tuple[str, str]]:
    """按优先级挑选会话 cookie, 返回 (cookie名, 值)."""
    jar: dict[str, str] = {}
    for cookie in cookies or []:
        jar.update(_cookie_value(cookie))
    for name in SESSION_COOKIE_NAMES:
        value = jar.get(name) or ""
        if value.strip():
            return name, value
    return None


# ── GitHub OAuth 卡死自动续跑 (2FA 登录后 return_to 丢失) ───────────────────
# 授权入口: github.com/login?client_id=... 或 github.com/login/oauth/authorize?client_id=...
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
    (return_to 也可能是未编码/双重编码); 提取 authorize 路径并去掉
    ``prompt=select_account``, 让已登录会话直接续跑授权, 不再弹账号选择器。
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
    target = re.sub(r"([?&])prompt=select_account&?", r"\1", target).rstrip("?&")
    if "client_id=" not in target:
        return None
    return "https://github.com" + target


def _github_logged_user(win) -> str:
    """读取 GitHub 页面的登录用户名 (meta user-login); 未登录/读取失败返回 ''."""
    try:
        result = win.evaluate_js(
            "(document.querySelector('meta[name=user-login]')||{}).content||''"
        )
    except Exception:  # noqa: BLE001 页面未就绪/窗口销毁
        return ""
    return str(result or "").strip()


class LoginWatcher:
    """后台轮询登录窗口, 捕获会话 cookie."""

    def __init__(
        self,
        win,
        on_success: Callable[[str, str], None],
        on_cancelled: Optional[Callable[[], None]] = None,
    ):
        self.win = win
        self.on_success = on_success  # fn(session_cookie, workspace_hint)
        self.on_cancelled = on_cancelled
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.done = False
        # GitHub 卡死自动续跑状态
        self._oauth_entry: Optional[str] = None  # 最近一次授权入口 URL
        self._stuck_since: Optional[float] = None  # 停在无关 GitHub 页面的起始时刻
        self._reloads = 0  # 已自动续跑次数
        self._github_cls: Optional[str] = None  # 上次记录的 GitHub 页面分类 (去重日志)

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

    def _run(self) -> None:
        _log("[login] watcher started")
        while not self._stop.is_set():
            try:
                url = self.win.get_current_url() or ""
            except Exception as exc:  # noqa: BLE001 窗口未加载完成或已销毁
                if not self._window_alive():
                    _log("[login] window closed, watcher exits")
                    break
                self._stop.wait(1.0)
                continue

            if url.startswith("https://opencode.ai"):
                self._stuck_since = None  # 已回到 opencode 域, 卡死计时清除
                try:
                    cookies = self.win.get_cookies() or []
                    raw_desc = [str(c) for c in cookies]
                except Exception as exc:  # noqa: BLE001
                    cookies = []
                    raw_desc = [f"<get_cookies ERROR {type(exc).__name__}: {exc}>"]
                _log(f"[login] on opencode.ai, url={url[:120]}, cookies={raw_desc}")

                picked = _pick_session_cookie(cookies)
                if picked:
                    name, value = picked
                    match = _WORKSPACE_URL_RE.search(url)
                    workspace_hint = match.group(1) if match else "Default"
                    _log(
                        f"[login] SUCCESS: {name} captured (len={len(value)}), ws={workspace_hint}"
                    )
                    self.done = True
                    self._stop.set()
                    self.on_success(f"{name}={value}", workspace_hint)
                    return
            elif _GITHUB_HOST_RE.match(url):
                self._watch_github(url)
            self._stop.wait(COOKIE_POLL_SEC)
        if not self.done and self.on_cancelled:
            self.on_cancelled()

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
        target = _authorize_url_from_entry(self._oauth_entry or "")
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


def clear_login_cookies(win) -> None:
    """清空登录窗口的 Cookie (添加新账号时确保出现登录页, 可切换账号).

    WebView2 的 DeleteAllCookies 是 profile 级操作, 旧会话 token 已落库, 不受影响。
    """
    try:
        win.clear_cookies()
        _log("[login] cookies cleared for fresh sign-in")
    except Exception as exc:  # noqa: BLE001 老版本 pywebview 无此能力: 忽略
        _log(f"[login] clear_cookies unavailable: {exc}")


__all__ = [
    "CONSOLE_LOGIN_URL",
    "LoginWatcher",
    "build_login_url",
    "clear_login_cookies",
]
