"""Command Code (commandcode.ai) GOAT 套餐 API client.

与 opencode_api 平级的第二个数据源后端:
- 配额 (quota): GET /internal/billing/credits + /internal/billing/subscriptions
  提供 5h / weekly / monthly 三个用量窗口 (monthly = 月池 - 已用)
- 用量记录 (usage): GET /internal/usage?limit=N&cursor=... 游标翻页明细

鉴权: httpOnly cookie ``__Secure-commandcode_prod_.session_token`` (无 CSRF/Origin 校验,
纯 HTTP 客户端可直接携带; 已实测). token 在本应用内统一存为
``__Secure-commandcode_prod_.session_token=<value>`` 形态.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

API_BASE = "https://api.commandcode.ai/internal"
LOGIN_HOST = "commandcode.ai"
AUTH_COOKIE_NAME = "__Secure-commandcode_prod_.session_token"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30.0
MAX_BODY_BYTES = 4 << 20  # 4 MiB
FETCH_RETRIES = 3
RETRY_BACKOFF = [0.5, 1.5, 3.0]

LABEL_ROLLING = "5h Rolling"
LABEL_WEEKLY = "Weekly"
LABEL_MONTHLY = "Monthly"
DEFAULT_LIMIT = 50
MAX_LIMIT = 100


class CommandCodeAPIError(Exception):
    """Command Code API 调用失败."""


class AuthError(CommandCodeAPIError):
    """认证失败 (token 无效/过期)."""


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------


def build_cookie_header(token: str) -> str:
    """规范化 token 为 Cookie 头 (支持直接粘贴完整 Cookie 串/仅 session_token)."""
    cookie = token.strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie[7:].strip()
    if not cookie:
        return ""
    for part in cookie.split(";"):
        p = part.strip()
        if p.startswith(AUTH_COOKIE_NAME + "="):
            return p
    return f"{AUTH_COOKIE_NAME}={cookie}"


def _fetch(url: str, headers: dict[str, str], timeout: float = REQUEST_TIMEOUT) -> str:
    """GET 并返回响应文本; 带重试; 401/403 抛 AuthError."""
    last_exc: Optional[Exception] = None
    for attempt in range(FETCH_RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                if status == 401 or status == 403:
                    raise AuthError("认证失败 (HTTP %d)，请重新登录" % status)
                if status < 200 or status >= 300:
                    raise CommandCodeAPIError(f"请求返回 HTTP {status}")
                return resp.read(MAX_BODY_BYTES).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthError("认证失败 (HTTP %d)，请重新登录" % exc.code) from exc
            raise CommandCodeAPIError(f"请求返回 HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < FETCH_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
    raise CommandCodeAPIError(f"网络错误: {last_exc}") from last_exc


def _get(path: str, token: str, params: Optional[dict[str, Any]] = None) -> Any:
    """GET JSON 接口, 返回解析后的对象 (dict/list)."""
    cookie = build_cookie_header(token)
    if not cookie:
        raise CommandCodeAPIError("token 为空")
    url = API_BASE + path
    if params:
        parts = []
        for k, v in params.items():
            if v is not None:
                parts.append(f"{k}={urllib.parse.quote(str(v))}")
        if parts:
            url += "?" + "&".join(parts)
    headers = {
        "Cookie": cookie,
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    body = _fetch(url, headers)
    try:
        return json.loads(body)
    except ValueError as exc:
        raise CommandCodeAPIError("响应不是合法 JSON") from exc


# ---------------------------------------------------------------------------
# 配额
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
    """与 opencode_api.QuotaResult 同构, 便于 server/前端统一消费."""

    name: str
    workspace_id: str
    success: bool
    updated_at: str
    plan: Optional[str] = None
    period_start: Optional[str] = None  # ISO
    period_end: Optional[str] = None    # ISO
    windows: list[QuotaWindow] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "workspace_id": self.workspace_id,
            "success": self.success,
            "updated_at": self.updated_at,
        }
        if self.plan:
            payload["plan"] = self.plan
        if self.period_start:
            payload["period_start"] = self.period_start
        if self.period_end:
            payload["period_end"] = self.period_end
        if self.error:
            payload["error"] = self.error
        if self.windows:
            payload["windows"] = [w.to_dict() for w in self.windows]
        return payload


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def _ms_to_iso(ms: int) -> str:
    """epoch 毫秒 -> ISO (UTC)."""
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _parse_window_percent(
    used_value: float, cap_value: float, reset_ms: int, now: datetime
) -> QuotaWindow:
    """把 commandcode 的 (used, cap, resetAt) 换算成百分比窗口.

    Command Code 的 cap/used 单位是「金额」($); 为与 opencode 的「百分比」
    窗口口径对齐, used% = used / cap * 100, remaining = 100 - used%.
    """
    if cap_value > 0:
        used_pct = _clamp_percent(used_value / cap_value * 100.0)
    else:
        used_pct = 0.0
    reset_at = _ms_to_iso(reset_ms)
    reset_in = max(0, int(reset_ms / 1000.0 - now.timestamp()))
    return QuotaWindow(
        label="",  # 由调用方回填
        used=used_pct,
        remaining=round(100.0 - used_pct, 1),
        total=cap_value,
        unit="$",  # 底层按金额计
        reset_at=reset_at,
        reset_in_sec=reset_in,
    )


def parse_credits_response(
    credits_body: dict[str, Any],
    subscription_body: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> QuotaResult:
    """把 credits + subscriptions 响应合并为 QuotaResult (纯函数, 便于单测).

    credits_body 形如: {"credits": {"monthlyCredits": 67.88, ...},
                        "windowLimits": {"limited": true, "fiveHour": {used,cap,resetAt},
                                         "weekly": {used,cap,resetAt}}}
    subscription_body 形如: {"data": {"planId": "individual-goat", "status": "active",
                                       "currentPeriodStart": "...", "currentPeriodEnd": "..."}}
    """
    now = now or datetime.now(timezone.utc)
    credits = credits_body.get("credits") or {}
    limits = credits_body.get("windowLimits") or {}
    windows: list[QuotaWindow] = []

    five = limits.get("fiveHour")
    if isinstance(five, dict):
        w = _parse_window_percent(
            float(five.get("used") or 0), float(five.get("cap") or 0),
            int(five.get("resetAt") or 0), now,
        )
        w.label = LABEL_ROLLING
        windows.append(w)
    weekly = limits.get("weekly")
    if isinstance(weekly, dict):
        w = _parse_window_percent(
            float(weekly.get("used") or 0), float(weekly.get("cap") or 0),
            int(weekly.get("resetAt") or 0), now,
        )
        w.label = LABEL_WEEKLY
        windows.append(w)

    # 订阅期 (月度): 月池 = 订阅期总额; 已用 = 月池 - 剩余 credits
    plan: Optional[str] = None
    period_start = period_end = None
    monthly_cap = float(credits.get("monthlyCredits") or 0)
    if subscription_body:
        data = subscription_body.get("data") or {}
        plan = data.get("planId") or None
        if data.get("status") == "active":
            try:
                monthly_cap = float(data.get("amountTotal") or data.get("monthlyCredits")
                                    or credits.get("monthlyCredits") or 0)
            except (TypeError, ValueError):
                pass
            period_start = data.get("currentPeriodStart")
            period_end = data.get("currentPeriodEnd")
    # Command Code 的 credits.monthlyCredits = 剩余额度; 月度窗口总额以官方
    # 计划额度为准 ($70/GOAT), 剩余量即 monthlyCredits. 已用 = 池 - 剩余.
    plan_total = _plan_monthly_allowance(plan) or (monthly_cap if monthly_cap > 0 else 0.0)
    remaining_credits = float(credits.get("monthlyCredits") or 0)
    if plan_total > 0:
        used_val = max(0.0, plan_total - remaining_credits)
        used_pct = _clamp_percent(used_val / plan_total * 100.0)
        # 月度窗口无单独 resetAt, 重置时刻取订阅周期结束
        reset_in = 0
        reset_at_iso = ""
        if period_end:
            try:
                end_dt = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
                reset_at_iso = end_dt.isoformat().replace("+00:00", "Z")
                reset_in = max(0, int(end_dt.timestamp() - now.timestamp()))
            except ValueError:
                pass
        windows.append(
            QuotaWindow(
                label=LABEL_MONTHLY,
                used=used_pct,
                remaining=round(100.0 - used_pct, 1),
                total=plan_total,
                unit="$",
                reset_at=reset_at_iso,
                reset_in_sec=reset_in,
            )
        )

    result = QuotaResult(
        name="Default",
        workspace_id="commandcode",  # commandcode 无 workspace 概念
        success=True,
        updated_at=now.isoformat().replace("+00:00", "Z"),
        plan=plan,
        period_start=period_start,
        period_end=period_end,
        windows=windows,
    )
    if not windows:
        result.success = False
        result.error = "无法从 credits 响应解析额度数据"
    return result


def _plan_monthly_allowance(plan: Optional[str]) -> Optional[float]:
    """已知计划的月度额度池 ($); 未知计划返回 None."""
    if not plan:
        return None
    key = plan.lower().replace("_", "-")
    table = {
        "individual-goat": 70.0,
        "individual-pro": 80.0,
        "individual-go": 10.0,
    }
    return table.get(key)


def fetch_quota(token: str) -> QuotaResult:
    """抓取当前账号配额 (5h/weekly/monthly)."""
    now = datetime.now(timezone.utc)
    updated_at = now.isoformat().replace("+00:00", "Z")
    if not token.strip():
        return QuotaResult(
            name="Default", workspace_id="commandcode", success=False,
            updated_at=updated_at, error="未配置 token",
        )
    try:
        credits_body = _get("/billing/credits", token)
        sub_body = None
        try:
            sub_body = _get("/billing/subscriptions", token)
        except Exception:  # noqa: BLE001 订阅缺失不影响配额主数据
            sub_body = None
        result = parse_credits_response(credits_body, sub_body, now)
        if not result.success:
            result.updated_at = updated_at
        return result
    except Exception as exc:  # noqa: BLE001
        return QuotaResult(
            name="Default", workspace_id="commandcode", success=False,
            updated_at=updated_at, error=str(exc),
        )


# ---------------------------------------------------------------------------
# 用量记录
# ---------------------------------------------------------------------------


@dataclass
class UsageRecord:
    """与 opencode_api.UsageRecord 同构, 供 server 统一入库.

    commandcode 明细字段有限: 无 reasoning/cache 拆分的 token, 无 session/key;
    对应字段留空/0, 费用已是 USD (存 cost_raw=0 占位, cost_usd 生效).
    """

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
    cost_raw: int  # 单位 1e-8 USD (占位 0; 实际费用在 cost_usd)
    cost_usd: float
    key_id: Optional[str]
    session_id: Optional[str]
    plan: Optional[str] = None

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


def _int_or(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_or(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_usage_response(text: str, provider: str = "commandcode") -> tuple[list[UsageRecord], Optional[str]]:
    """解析 /internal/usage 响应为 (records, next_cursor).

    响应形如: {"usages": [{id, createdAt, tokensIn:"69691", tokensOut:"1437",
                            durationTotal, status, message,
                            meta:{totalCost, inputCost, outputCost, cacheCost, model, traceId},
                            type, mode}], "nextCursor": "..."}
    """
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise CommandCodeAPIError("usage 响应不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise CommandCodeAPIError("usage 响应结构异常")
    records: list[UsageRecord] = []
    for item in data.get("usages") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        usg_id = str(item["id"])
        meta = item.get("meta") or {}
        model = str(meta.get("model") or item.get("model") or "unknown")
        # meta.totalCost 已是 USD; 与 opencode 的 1e-8 cost_raw 区分: 只写 cost_usd
        cost_usd = _float_or(meta.get("totalCost"), 0.0)
        records.append(
            UsageRecord(
                usg_id=usg_id,
                created_at=_normalize_created_at(str(item.get("createdAt") or "")),
                model=model,
                provider=provider,
                input_tokens=_int_or(item.get("tokensIn")),
                output_tokens=_int_or(item.get("tokensOut")),
                reasoning_tokens=0,
                cache_read_tokens=0,
                cache_write_5m_tokens=0,
                cache_write_1h_tokens=0,
                cost_raw=0,
                cost_usd=cost_usd,
                key_id=None,
                session_id=None,  # commandcode 无会话概念
                plan=None,
            )
        )
    next_cursor = data.get("nextCursor") or None
    return records, next_cursor


def _normalize_created_at(value: str) -> str:
    """校验并原样保留 ISO 时间串 (与 opencode 记录口径一致, 不做格式改写).

    只做合法性检查, 非法时返回空串 (入库后该行会被裁剪逻辑忽略).
    """
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value if dt.tzinfo is not None else value
    except ValueError:
        return value


def fetch_usage_page(
    token: str, cursor: Optional[str] = None, limit: int = DEFAULT_LIMIT
) -> tuple[list[UsageRecord], Optional[str]]:
    """拉一页用量记录; 返回 (records, next_cursor). 首页不传 cursor."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    data = _get("/usage", token, {"limit": limit, "cursor": cursor})
    return parse_usage_response(json.dumps(data))


def fetch_usage_summary(token: str) -> dict[str, Any]:
    """拉取当前计费周期汇总 (totalCost/totalTokens/totalCount...)."""
    data = _get("/usage/summary", token)
    if not isinstance(data, dict):
        return {}
    return data
