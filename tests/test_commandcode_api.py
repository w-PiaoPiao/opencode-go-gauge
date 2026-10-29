"""commandcode_api.py 纯函数测试: 配额合并 / usage 解析 / cookie 规范化.

fixture 数据来自 2026-09-02 对 commandcode.ai internal API 的实测响应.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.commandcode_api import (
    CommandCodeAPIError,
    build_cookie_header,
    parse_credits_response,
    parse_usage_response,
)


# ---- 实测响应样例 ----

CREDITS_BODY = {
    "credits": {
        "belowThreshold": False,
        "creditThreshold": 0,
        "monthlyCredits": 67.8799891707,
        "purchasedCredits": 0,
        "premiumMonthlyCredits": 0,
        "opensourceMonthlyCredits": 67.8799891707,
    },
    "windowLimits": {
        "limited": True,
        "exceeded": None,
        "fiveHour": {"used": 0.0648735266, "cap": 14, "exceeded": False, "resetAt": 1788366123616},
        "weekly": {"used": 2.1200108293, "cap": 35, "exceeded": False, "resetAt": 1788916513968},
    },
}

SUBSCRIPTION_BODY = {
    "success": True,
    "data": {
        "id": "sub_1UB2cQDSZgxV3MJKrOXJKlf4",
        "status": "active",
        "userId": "bcd0bc0a-a65a-44dc-9420-ce0acf751ff2",
        "orgId": None,
        "currentPeriodStart": "2026-09-02T01:03:43.000Z",
        "currentPeriodEnd": "2026-10-02T01:03:43.000Z",
        "planId": "individual-goat",
        "pendingPhase": None,
    },
}

USAGE_BODY = {
    "usages": [
        {
            "id": "86c1fefd-2010-46b3-9a69-a65284e99600",
            "createdAt": "2026-09-02T11:31:04.353Z",
            "tokensIn": "69691",
            "tokensOut": "1437",
            "durationTotal": "14976",
            "status": "completed",
            "message": None,
            "meta": {
                "totalCost": 0.002048632,
                "inputCost": 0.0006325,
                "outputCost": 0.00094842,
                "cacheCost": 0.000467712,
                "model": "deepseek/deepseek-v4-flash",
                "traceId": "00b590953f609f5554888ffbe17f0aff",
            },
            "type": "api",
            "mode": "api",
        },
        {
            "id": "2bc6f2b0-824f-46f7-98f3-8b01d9cc7051",
            "createdAt": "2026-09-02T11:30:46.131Z",
            "tokensIn": "66353",
            "tokensOut": "534",
            "durationTotal": "5266",
            "status": "completed",
            "message": None,
            "meta": {
                "totalCost": 0.001563476,
                "inputCost": 0.0007711,
                "outputCost": 0.00035244,
                "cacheCost": 0.000439936,
                "model": "deepseek/deepseek-v4-flash",
                "traceId": "50a716db900f15c9953364341167afb4",
            },
            "type": "api",
            "mode": "api",
        },
    ],
    "nextCursor": "eyJjcmVhdGVkQXQiOiIyMDI2LTA5LTAyVDExOjM5OjUwLjg3NloiLCJpZCI6IjQ2NTQyYjkwLTAyMTMtNDcyNy1hYjNjLTY4NDViM2RlZDQ2ZiIsInNpbmNlIjoiMjAyNi0wOS0wMVQxMTo0MzozNy40MTlaIiwic2VlbiI6M30",
    "limit": 10,
    "periodBasis": "billing-period",
    "window": "month",
}


class TestCookieHeader:
    def test_full_session_token(self):
        h = build_cookie_header("__Secure-commandcode_prod_.session_token=abc123")
        assert h == "__Secure-commandcode_prod_.session_token=abc123"

    def test_plain_value(self):
        h = build_cookie_header("abc123")
        assert h == "__Secure-commandcode_prod_.session_token=abc123"

    def test_cookie_prefix_and_extra_parts(self):
        h = build_cookie_header("Cookie: a=1; __Secure-commandcode_prod_.session_token=xyz; b=2")
        assert h == "__Secure-commandcode_prod_.session_token=xyz"

    def test_empty(self):
        assert build_cookie_header("") == ""
        assert build_cookie_header("   ") == ""


class TestParseCreditsResponse:
    def _now(self):
        # resetAt 毫秒对应的时间, 用固定 now 保证 reset_in_sec 可断言
        return datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)

    def test_three_windows_and_plan(self):
        r = parse_credits_response(CREDITS_BODY, SUBSCRIPTION_BODY, now=self._now())
        assert r.success is True
        assert r.plan == "individual-goat"
        assert r.period_start == "2026-09-02T01:03:43.000Z"
        assert r.period_end == "2026-10-02T01:03:43.000Z"
        labels = [w.label for w in r.windows]
        assert labels == ["5h Rolling", "Weekly", "Monthly"]
        by = {w.label: w for w in r.windows}
        # 5h: used/cap -> 0.06487/14 = 0.463%
        five = by["5h Rolling"]
        assert five.used == pytest.approx(0.0648735266 / 14 * 100, abs=0.01)
        assert five.unit == "$"
        # weekly: 2.12/35 = 6.06%
        weekly = by["Weekly"]
        assert weekly.used == pytest.approx(2.1200108293 / 35 * 100, abs=0.01)
        # monthly: 池 70 - 剩 67.88 = 2.12; 重置时间取 period_end
        monthly = by["Monthly"]
        assert monthly.used == pytest.approx((70 - 67.8799891707) / 70 * 100, abs=0.05)
        assert monthly.reset_in_sec > 0
        # resetAt 换算
        assert five.reset_at.startswith("2026-09-02")

    def test_no_subscription_monthly_from_plan_allowance(self):
        # 无订阅响应, 仍按 plan 未知 + 池 70? plan 缺省, 用 credits.monthlyCredits 作为剩余
        r = parse_credits_response(CREDITS_BODY, None, now=self._now())
        assert r.success is True
        assert r.plan is None
        labels = [w.label for w in r.windows]
        assert "Monthly" in labels

    def test_missing_windows_failure(self):
        r = parse_credits_response({"credits": {}}, None, now=self._now())
        assert r.success is False
        assert r.error


class TestParseUsageResponse:
    def test_records_and_cursor(self):
        records, cursor = parse_usage_response(json.dumps(USAGE_BODY))
        assert len(records) == 2
        assert cursor and cursor.startswith("eyJ")
        r0 = records[0]
        assert r0.usg_id == "86c1fefd-2010-46b3-9a69-a65284e99600"
        assert r0.model == "deepseek/deepseek-v4-flash"
        assert r0.input_tokens == 69691
        assert r0.output_tokens == 1437
        assert r0.cost_usd == pytest.approx(0.002048632)
        assert r0.created_at == "2026-09-02T11:31:04.353Z"
        assert r0.provider == "commandcode"
        # commandcode 无 session/cache 拆分
        assert r0.session_id is None
        assert r0.cache_read_tokens == 0

    def test_empty_usages(self):
        records, cursor = parse_usage_response('{"usages": [], "nextCursor": null}')
        assert records == []
        assert cursor is None

    def test_invalid_json(self):
        with pytest.raises(CommandCodeAPIError):
            parse_usage_response("not json")


# ---------------------------------------------------------------------------
# P3-19: 窗口 kind 稳定协议 / P3-20: 共用重试策略 + 有界响应体
# ---------------------------------------------------------------------------

import urllib.error  # noqa: E402

from app import _http_retry as hr  # noqa: E402
from app import commandcode_api as ccapi  # noqa: E402


def test_quota_windows_expose_stable_kind():
    """to_dict 必须带稳定 kind (rolling/weekly/monthly), label 只是展示文案."""
    result = parse_credits_response(
        CREDITS_BODY, SUBSCRIPTION_BODY, datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc))
    kinds = [w.kind for w in result.windows]
    assert kinds == ["rolling", "weekly", "monthly"]
    payload = result.to_dict()
    assert [w["kind"] for w in payload["windows"]] == kinds
    # label 值本身保持历史不变 (前端文案/旧响应兼容)
    assert [w["label"] for w in payload["windows"]] == ["5h Rolling", "Weekly", "Monthly"]


def test_retryable_status_classification():
    assert hr.is_retryable_status(500)
    assert hr.is_retryable_status(503)
    assert hr.is_retryable_status(429)
    assert hr.is_retryable_status(408)
    assert not hr.is_retryable_status(400)
    assert not hr.is_retryable_status(401)
    assert not hr.is_retryable_status(404)
    assert not hr.is_retryable_status(422)


def test_retry_after_seconds_parses_and_caps():
    assert hr.retry_after_seconds({"Retry-After": "2"}) == 2.0
    assert hr.retry_after_seconds({"Retry-After": "30"}) == hr.MAX_RETRY_AFTER_SEC
    assert hr.retry_after_seconds({"Retry-After": "0"}) == 0.0
    # HTTP-date 形态 (未来 5s) 也可解析
    future = datetime.now(timezone.utc) + __import__("datetime").timedelta(seconds=5)
    http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    parsed = hr.retry_after_seconds({"Retry-After": http_date})
    assert parsed is not None and 0.0 <= parsed <= hr.MAX_RETRY_AFTER_SEC
    # 过去时间按 0 处理; 缺失/垃圾值返回 None (回退指数退避)
    past = datetime.now(timezone.utc) - __import__("datetime").timedelta(seconds=60)
    assert hr.retry_after_seconds(
        {"Retry-After": past.strftime("%a, %d %b %Y %H:%M:%S GMT")}) == 0.0
    assert hr.retry_after_seconds({}) is None
    assert hr.retry_after_seconds({"Retry-After": "not-a-date"}) is None
    assert hr.retry_after_seconds(None) is None


def test_retry_delay_prefers_retry_after_then_backoff():
    assert hr.retry_delay(0, {"Retry-After": "3"}) == 3.0
    assert hr.retry_delay(0) == hr.RETRY_BACKOFF[0]
    assert hr.retry_delay(1) == hr.RETRY_BACKOFF[1]
    # 越界 attempt 用最后一项封顶 (不会 IndexError)
    assert hr.retry_delay(99) == hr.RETRY_BACKOFF[-1]


class _Resp:
    def __init__(self, headers: dict, body: bytes):
        self.headers = headers
        self._body = body
        self._sent = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n: int = -1) -> bytes:
        if self._sent:
            return b""
        self._sent = True
        return self._body[:n] if n and n >= 0 else self._body


def test_read_body_rejects_oversize_by_declared_length():
    resp = _Resp({"Content-Length": "999"}, b"")
    with pytest.raises(hr.ResponseTooLarge, match="响应过大"):
        hr.read_body(resp, 10)


def test_read_body_rejects_oversize_chunked_without_content_length():
    """chunked/无 Content-Length: 只信声明会让超限响应被静默截断后误报 JSON 非法."""
    resp = _Resp({}, b"x" * 11)
    with pytest.raises(hr.ResponseTooLarge, match="响应过大"):
        hr.read_body(resp, 10)


def test_read_body_accepts_exact_limit():
    resp = _Resp({}, b"x" * 10)
    assert hr.read_body(resp, 10) == b"x" * 10


def _http_error(code: int, headers=None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test/x", code, "boom", headers or {}, None)


def test_client_does_not_retry_deterministic_4xx(monkeypatch):
    calls = []

    def _fake_urlopen(*_a, **_k):
        calls.append(1)
        raise _http_error(404)

    monkeypatch.setattr(ccapi.urllib.request, "urlopen", _fake_urlopen)
    with pytest.raises(CommandCodeAPIError, match="404"):
        ccapi._get("/usage", "token")
    assert len(calls) == 1, "确定性 4xx 不应重试"


def test_client_retries_5xx_with_backoff(monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr(ccapi.time, "sleep", lambda s: sleeps.append(s))

    def _fake_urlopen(*_a, **_k):
        calls.append(1)
        raise _http_error(503)

    monkeypatch.setattr(ccapi.urllib.request, "urlopen", _fake_urlopen)
    with pytest.raises(CommandCodeAPIError, match="503"):
        ccapi._get("/usage", "token")
    assert len(calls) == ccapi.FETCH_RETRIES
    assert sleeps == [hr.RETRY_BACKOFF[0], hr.RETRY_BACKOFF[1]]


def test_client_honors_retry_after_capped_at_10s(monkeypatch):
    sleeps = []
    monkeypatch.setattr(ccapi.time, "sleep", lambda s: sleeps.append(s))

    def _fake_urlopen(*_a, **_k):
        raise _http_error(429, {"Retry-After": "30"})

    monkeypatch.setattr(ccapi.urllib.request, "urlopen", _fake_urlopen)
    with pytest.raises(CommandCodeAPIError, match="429"):
        ccapi._get("/usage", "token")
    assert sleeps == [hr.MAX_RETRY_AFTER_SEC, hr.MAX_RETRY_AFTER_SEC], (
        "Retry-After 必须被采纳且封顶 10s, 不能按 30s 把 UI 卡住"
    )


def test_client_maps_oversized_response_to_domain_error(monkeypatch):
    monkeypatch.setattr(
        ccapi.urllib.request, "urlopen",
        lambda *_a, **_k: _Resp({"Content-Length": str(ccapi.MAX_BODY_BYTES + 1)}, b""))
    with pytest.raises(CommandCodeAPIError, match="响应过大"):
        ccapi._get("/usage", "token")
