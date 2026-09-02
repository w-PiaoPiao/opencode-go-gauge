"""commandcode_api.py 纯函数测试: 配额合并 / usage 解析 / cookie 规范化.

fixture 数据来自 2026-09-02 对 commandcode.ai internal API 的实测响应.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app import commandcode_api as cc
from app.commandcode_api import (
    AuthError,
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
