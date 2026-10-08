"""OpenCode Console API 客户端 (2026-09 前端改版后).

旧接口链路已随 opencode.ai 改版失效, 本模块改为对接 /console 控制台:

- 会话 Cookie: ``auth`` -> ``__Host-console_session`` (登录页 /console/login)
- 配额: 旧 dashboard HTML 解析 -> GET /console/api/go/status
- 明细: 旧 /_server server-fn -> GET /console/api/request-logs (游标分页)
- 工作区: GET /console/api/orgs ; Key 名称: GET /console/api/service-accounts

所有 /console/api 请求除 Cookie 外还需 ``x-org-id: <wrk_xxx>`` 头 (org 即工作区).
服务端对请求明细只保留 30 天 (响应中的 retentionDays).
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

CONSOLE_ORIGIN = "https://opencode.ai"
CONSOLE_LOGIN_URL = "https://opencode.ai/console/login"
API_BASE = "https://opencode.ai/console/api"

# 会话 Cookie: 新版 __Host-console_session, 旧版 auth (兼容历史 token)
SESSION_COOKIE = "__Host-console_session"
LEGACY_SESSION_COOKIE = "auth"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:148.0) Gecko/20100101 Firefox/148.0"
)
REQUEST_TIMEOUT = 30.0
MAX_BODY_BYTES = 8 << 20  # 8 MiB
FETCH_RETRIES = 3  # 网络抖动重试次数
RETRY_BACKOFF = [0.5, 1.5, 3.0]

LABEL_ROLLING = "5h Rolling"
LABEL_WEEKLY = "Weekly"
LABEL_MONTHLY = "Monthly"

# go/status: access.meters 下的三个额度窗口
METER_ROLLING = "fiveHour"
METER_WEEKLY = "week"
METER_MONTHLY = "month"

# request-logs: 单页条数 (接口上限 100)
USAGE_PAGE_SIZE = 100

# 明细中的推理请求分类 (另一类 "api" 是控制台自身的接口调用, 不计入用量)
CATEGORY_INFERENCE = "inference"

_WORKSPACE_ID_RE = re.compile(r"wrk_[A-Za-z0-9]+")


# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------


@dataclass
class QuotaWindow:
    label: str
    used: float  # 已用百分比 0-100
    remaining: float
    total: float
    unit: str
    reset_at: str  # ISO
    reset_in_sec: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "used": self.used,
            "remaining": self.remaining,
            "total": self.total,
            "unit": self.unit,
            "reset_at": self.reset_at,
            "reset_in_sec": self.reset_in_sec,
        }


@dataclass
class QuotaResult:
    name: str
    workspace_id: str
    success: bool
    updated_at: str
    period_start: Optional[str] = None  # ISO, 订阅计费周期起点 (access.startsAt)
    period_end: Optional[str] = None    # ISO, 订阅计费周期终点 (access.endsAt)
    windows: list[QuotaWindow] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "workspace_id": self.workspace_id,
            "success": self.success,
            "updated_at": self.updated_at,
        }
        if self.period_start:
            payload["period_start"] = self.period_start
        if self.period_end:
            payload["period_end"] = self.period_end
        if self.error:
            payload["error"] = self.error
        if self.windows:
            payload["windows"] = [w.to_dict() for w in self.windows]
        return payload


@dataclass
class UsageRecord:
    usg_id: str
    created_at: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cache_read_tokens: int
    cache_write_5m_tokens: int
    cache_write_1h_tokens: int
    cost_raw: int  # 单位 1e-8 USD
    key_id: str
    session_id: str
    plan: Optional[str] = None

    @property
    def cost_usd(self) -> float:
        return self.cost_raw / 100_000_000.0

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "usg_id": self.usg_id,
            "created_at": self.created_at,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_5m_tokens": self.cache_write_5m_tokens,
            "cache_write_1h_tokens": self.cache_write_1h_tokens,
            "cost_raw": self.cost_raw,
            "cost_usd": self.cost_usd,
            "key_id": self.key_id,
            "session_id": self.session_id,
            "plan": self.plan,
        }


@dataclass
class UsagePage:
    """request-logs 的一页结果 (游标分页)."""

    records: list[UsageRecord] = field(default_factory=list)
    next_cursor: Optional[str] = None
    retention_days: Optional[int] = None


class OpenCodeAPIError(Exception):
    """opencode.ai API 调用失败."""


class AuthError(OpenCodeAPIError):
    """认证失败 (会话无效/过期)."""


# ---------------------------------------------------------------------------
# Cookie / HTTP 工具
# ---------------------------------------------------------------------------


def build_cookie_header(token: str) -> str:
    """把 token 规范化为 Cookie 头.

    支持三种输入:
    - 完整 Cookie 串: ``__Host-console_session=st_xxx`` / ``auth=Fe26...`` (直接透传)
    - ``Cookie: xxx`` 前缀串
    - 纯值: ``st_xxx`` (补上新版会话 Cookie 名)
    """
    raw = token.strip()
    if raw.lower().startswith("cookie:"):
        raw = raw[7:].strip()
    if not raw:
        return ""
    for part in raw.split(";"):
        p = part.strip()
        if not p:
            continue
        name = p.split("=", 1)[0].strip().lower()
        if name in (SESSION_COOKIE.lower(), LEGACY_SESSION_COOKIE):
            return p
    # 形如 name=value 的其它 Cookie 原样透传, 纯值则按新版会话 Cookie 处理
    if re.fullmatch(r"[A-Za-z0-9_.\-]+\s*=\s*\S+", raw):
        return raw
    return f"{SESSION_COOKIE}={raw}"


def _fetch(
    url: str,
    headers: dict[str, str],
    timeout: float = REQUEST_TIMEOUT,
    retries: int = FETCH_RETRIES,
) -> str:
    """GET 请求, 自动重试; 401/403 抛 AuthError, 404 抛 OpenCodeAPIError."""
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(MAX_BODY_BYTES)
                # 截断检测: Content-Length 声明超限时明确报错, 而非静默解析半包丢尾部数据
                declared = resp.headers.get("Content-Length") or ""
                if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
                    raise OpenCodeAPIError(
                        f"响应过大 ({int(declared) // (1 << 20)} MiB, 上限 8 MiB)")
                return body.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise AuthError("登录已过期，请重新登录") from exc
            if exc.code == 403:
                raise OpenCodeAPIError("无访问权限 (HTTP 403)") from exc
            if exc.code == 404:
                raise OpenCodeAPIError("工作区不存在或接口不可用 (HTTP 404)") from exc
            last_exc = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
        if attempt < retries - 1:
            time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
    if isinstance(last_exc, urllib.error.HTTPError):
        raise OpenCodeAPIError(f"请求返回 HTTP {last_exc.code}") from last_exc
    if isinstance(last_exc, urllib.error.URLError):
        raise OpenCodeAPIError(f"网络错误: {last_exc.reason}") from last_exc
    raise OpenCodeAPIError(f"网络错误: {last_exc}") from last_exc


def _api_get(
    path: str,
    token: str,
    org_id: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
    timeout: float = REQUEST_TIMEOUT,
    retries: int = FETCH_RETRIES,
) -> Any:
    """调用 /console/api 下接口, 返回解析后的 JSON."""
    cookie = build_cookie_header(token)
    if not cookie:
        raise OpenCodeAPIError("token 为空")
    url = f"{API_BASE}{path}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    headers = {
        "Cookie": cookie,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "Origin": CONSOLE_ORIGIN,
        "Referer": f"{CONSOLE_ORIGIN}/console/",
    }
    if org_id:
        headers["x-org-id"] = org_id
    text = _fetch(url, headers, timeout=timeout, retries=retries)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise OpenCodeAPIError("接口返回非 JSON 数据") from exc


# ---------------------------------------------------------------------------
# 数值解析小工具 (接口有数字/字符串两种编码)
# ---------------------------------------------------------------------------


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso_from_ms(value: Any) -> str:
    ms = _as_float(value, 0.0)
    if ms <= 0:
        return ""
    try:
        return (
            datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _iso_from_text(value: Any) -> str:
    """把接口返回的 ISO 时间串规范成 ``...Z``."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _seconds_until(iso_text: str, now: datetime) -> int:
    try:
        dt = datetime.fromisoformat(iso_text.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((dt - now).total_seconds()))


# ---------------------------------------------------------------------------
# 工作区 (org)
# ---------------------------------------------------------------------------


def extract_workspace_id(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith("wrk_") and len(value) > 4:
        return value
    match = _WORKSPACE_ID_RE.search(value)
    return match.group(0) if match else ""


def fetch_workspace_refs(token: str) -> list[tuple[str, str]]:
    """获取账号下的工作区列表 [(id, name)]."""
    data = _api_get("/orgs", token)
    refs: list[tuple[str, str]] = []
    seen: set[str] = set()
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            wid = str(item.get("id") or "").strip()
            if not wid or wid in seen:
                continue
            seen.add(wid)
            refs.append((wid, str(item.get("name") or "").strip()))
    if not refs:
        raise OpenCodeAPIError("无法获取工作区列表 (账号下没有工作区)")
    return refs


def _resolve_workspace(hint: str, token: str) -> tuple[str, str]:
    """解析工作区提示 -> (workspace_id, 显示名); 显示名可能为空.

    hint 已是 wrk_xxx 时直接采用 (不做额外请求); 否则拉一次工作区列表按
    ID/名称匹配, 匹配不到则取第一个。
    """
    resolved = extract_workspace_id(hint)
    if resolved:
        return resolved, ""
    refs = fetch_workspace_refs(token)
    hint_l = (hint or "").strip().lower()
    if hint_l:
        for workspace_id, name in refs:
            if workspace_id.lower() == hint_l or name.lower() == hint_l:
                return workspace_id, name
    workspace_id, name = refs[0]
    return workspace_id, name


def resolve_workspace_id(hint: str, token: str) -> str:
    """将工作区提示 (id/名称/Default) 解析为 wrk_xxx ID."""
    return _resolve_workspace(hint, token)[0]


# ---------------------------------------------------------------------------
# 配额 (go/status)
# ---------------------------------------------------------------------------


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def parse_go_status(payload: Any, now: Optional[datetime] = None) -> list[QuotaWindow]:
    """解析 /go/status 响应为三个额度窗口 (5h/weekly/monthly).

    结构: access.meters.{fiveHour,week,month} 各含 limitMicroCents / usedMicroCents
    (1e-8 USD), 以及可选 startsAt / resetsAt; 月额度无 resetsAt 时用 access.endsAt.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload, dict):
        return []
    access = payload.get("access")
    if not isinstance(access, dict):
        return []
    meters = access.get("meters")
    if not isinstance(meters, dict):
        return []
    period_end = _iso_from_text(access.get("endsAt"))
    windows: list[QuotaWindow] = []
    for label, key in (
        (LABEL_ROLLING, METER_ROLLING),
        (LABEL_WEEKLY, METER_WEEKLY),
        (LABEL_MONTHLY, METER_MONTHLY),
    ):
        meter = meters.get(key)
        if not isinstance(meter, dict):
            continue
        limit = _as_float(meter.get("limitMicroCents"))
        used_raw = _as_float(meter.get("usedMicroCents"))
        if limit <= 0:
            continue
        used = _clamp_percent(used_raw / limit * 100.0)
        reset_at = _iso_from_text(meter.get("resetsAt")) or period_end
        windows.append(
            QuotaWindow(
                label=label,
                used=round(used, 2),
                remaining=round(100.0 - used, 2),
                total=100.0,
                unit="%",
                reset_at=reset_at,
                reset_in_sec=_seconds_until(reset_at, now),
            )
        )
    return windows


def parse_go_period(payload: Any) -> tuple[Optional[str], Optional[str]]:
    """解析订阅计费周期起止 (access.startsAt / endsAt, ISO).

    月度 meter 只有 resetsAt(下次重置), 周期起点必须取 access.startsAt —— Go 月度
    周期实测按自然月 (10-08 → 11-08, 31 天), 用「下次重置 - 30 天」推算会落到未来,
    「本周期」筛选随即变成空集.
    """
    if not isinstance(payload, dict):
        return None, None
    access = payload.get("access")
    if not isinstance(access, dict):
        return None, None
    return _iso_or_none(access.get("startsAt")), _iso_or_none(access.get("endsAt"))


def _iso_or_none(value: Any) -> Optional[str]:
    """规范化为 ISO-Z; 无法解析时返回 None (_iso_from_text 原样透传的脏值挡在这里)."""
    text = _iso_from_text(value)
    return text if text.endswith("Z") and "T" in text else None


def fetch_quota(token: str, workspace_hint: str = "Default") -> QuotaResult:
    """获取单个工作区的 Go 配额 (5h/weekly/monthly)."""
    now = datetime.now(timezone.utc)
    updated_at = now.isoformat().replace("+00:00", "Z")
    hint = (workspace_hint or "Default").strip() or "Default"
    if not token.strip():
        return QuotaResult(
            name="Default", workspace_id=hint, success=False,
            updated_at=updated_at, error="未配置 token",
        )
    name = hint
    try:
        workspace_id, ws_name = _resolve_workspace(hint, token)
        if ws_name:
            name = ws_name
        payload = _api_get("/go/status", token, org_id=workspace_id, timeout=20.0, retries=2)
        windows = parse_go_status(payload, now)
        if not windows:
            raise OpenCodeAPIError("账号未订阅 OpenCode Go (接口无额度数据)")
        period_start, period_end = parse_go_period(payload)
        return QuotaResult(
            name=name, workspace_id=workspace_id, success=True, updated_at=updated_at,
            period_start=period_start, period_end=period_end, windows=windows,
        )
    except Exception as exc:  # noqa: BLE001
        return QuotaResult(
            name=name, workspace_id=hint, success=False,
            updated_at=updated_at, error=str(exc),
        )


# ---------------------------------------------------------------------------
# 用量明细 (request-logs)
# ---------------------------------------------------------------------------


def _record_from_item(item: dict[str, Any]) -> Optional[UsageRecord]:
    usg_id = str(item.get("id") or "").strip()
    created_at = _iso_from_ms(item.get("startedAt"))
    if not usg_id or not created_at:
        return None
    cache_write = _as_int(item.get("cacheWriteTokens"))
    return UsageRecord(
        usg_id=usg_id,
        created_at=created_at,
        model=str(item.get("model") or "").strip(),
        provider=str(item.get("provider") or "").strip(),
        input_tokens=_as_int(item.get("inputTokens")),
        output_tokens=_as_int(item.get("outputTokens")),
        reasoning_tokens=_as_int(item.get("reasoningTokens")),
        cache_read_tokens=_as_int(item.get("cacheReadTokens")),
        # 新接口不再区分 5m/1h 缓存写入, 统一记入 5m 列 (合计口径不变)
        cache_write_5m_tokens=cache_write,
        cache_write_1h_tokens=0,
        cost_raw=int(round(_as_float(item.get("cost")) * 100_000_000)),
        key_id=str(item.get("serviceAPIKeyID") or "").strip(),
        session_id=str(item.get("sessionID") or "").strip(),
        plan=str(item.get("product") or "").strip() or None,
    )


def parse_request_logs(payload: Any) -> UsagePage:
    """解析 /request-logs 响应 (只保留 inference 类请求)."""
    if not isinstance(payload, dict):
        return UsagePage()
    items = payload.get("items")
    records: list[UsageRecord] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("category") or "").strip().lower() != CATEGORY_INFERENCE:
                continue  # 控制台自身接口调用, 不计入用量
            rec = _record_from_item(item)
            if rec is not None:
                records.append(rec)
    cursor = payload.get("nextCursor")
    retention = payload.get("retentionDays")
    return UsagePage(
        records=records,
        next_cursor=str(cursor) if cursor else None,
        retention_days=_as_int(retention) if retention is not None else None,
    )


def fetch_usage_page(
    token: str,
    workspace_id: str,
    cursor: Optional[str] = None,
    limit: int = USAGE_PAGE_SIZE,
    since_ms: Optional[int] = None,
) -> UsagePage:
    """拉取一页用量明细 (游标分页, 按时间倒序).

    Args:
        cursor: 上一页返回的 next_cursor; 首页传 None
        limit: 单页条数 (接口上限 100)
        since_ms: 只取该毫秒时间戳之后的记录 (增量同步用)
    """
    params: dict[str, Any] = {"limit": max(1, min(int(limit), 100))}
    if cursor:
        params["cursor"] = cursor
    if since_ms:
        params["since"] = int(since_ms)
    payload = _api_get("/request-logs", token, org_id=workspace_id, params=params)
    return parse_request_logs(payload)


def iso_to_ms(iso_text: str) -> int:
    """ISO 时间 -> 毫秒时间戳 (解析失败返回 0)."""
    text = (iso_text or "").strip()
    if not text:
        return 0
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


# ---------------------------------------------------------------------------
# Key 名称
# ---------------------------------------------------------------------------


def fetch_key_names(token: str, workspace_id: str) -> dict[str, str]:
    """拉取工作区下所有 API key 的名称映射 (key_id -> 名称).

    service-accounts 响应形如 ``{"items":[{account:{...}, keys:[{id,name},...]}]}``,
    失败时返回空 dict (不影响主流程).
    """
    try:
        payload = _api_get(
            "/service-accounts", token, org_id=workspace_id, timeout=15.0, retries=2
        )
    except OpenCodeAPIError:
        return {}
    names: dict[str, str] = {}
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        keys = entry.get("keys")
        if not isinstance(keys, list):
            continue
        for key in keys:
            if not isinstance(key, dict):
                continue
            key_id = str(key.get("id") or "").strip()
            name = str(key.get("name") or "").strip()
            if key_id and name:
                names.setdefault(key_id, name)
    return names
