"""opencode_api 新版控制台客户端测试: Cookie 归一化 / 配额解析 / 明细解析.

夹具取自 2026-09 改版后 /console/api 的真实响应结构 (值已改写)。
"""
from __future__ import annotations

from datetime import datetime, timezone

from app import opencode_api as api

# ---------------------------------------------------------------------------
# 夹具: /console/api/go/status
# ---------------------------------------------------------------------------

GO_STATUS = {
    "subscriberUserId": "acc_01KXDVHYS30679FFKQ113J8FWY",
    "product": "go",
    "useBalance": False,
    "access": {
        "startsAt": "2026-09-26T12:06:25.000Z",
        "endsAt": "2026-10-26T12:06:25.000Z",
        "cancelAtPeriodEnd": False,
        "meters": {
            "fiveHour": {
                "startsAt": "2026-09-26T12:27:01.804Z",
                "resetsAt": "2026-09-26T17:27:01.804Z",
                "limitMicroCents": "1200000000",
                "usedMicroCents": "7632295",
            },
            "week": {
                "startsAt": "2026-09-21T00:00:00.000Z",
                "resetsAt": "2026-09-28T00:00:00.000Z",
                "limitMicroCents": "3000000000",
                "usedMicroCents": "7632295",
            },
            # 月额度没有 resetsAt, 重置时间取 access.endsAt
            "month": {"limitMicroCents": "6000000000", "usedMicroCents": "7632295"},
        },
    },
}

NOW = datetime(2026, 9, 26, 12, 56, 25, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# 夹具: /console/api/request-logs
# ---------------------------------------------------------------------------

REQUEST_LOGS = {
    "items": [
        {
            "id": "c34d84dc-d6e8-4d09-8a48-55d636a772d2",
            "requestID": "c34d84dc-d6e8-4d09-8a48-55d636a772d2",
            "workspaceID": "wrk_01KXDVHZMY578NZ300DTR7WYE8",
            "startedAt": 1790427391447,
            "finishedAt": 1790427392447,
            "outcome": "succeeded",
            "category": "inference",
            "protocol": "openai-chat",
            "product": "go",
            "sessionID": "1e2a34d4-f057-45bd-8f0f-21c05481fa00",
            "serviceAPIKeyID": "sk_01M3ESWS60E7J9STN1MHFQPYRM",
            "requestedModel": "deepseek-v4.1-flash",
            "model": "deepseek-v4.1-flash",
            "provider": "opencode",
            "inputTokens": 2480,
            "outputTokens": 1273,
            "reasoningTokens": 629,
            "cacheReadTokens": 130944,
            "cacheWriteTokens": 0,
            "cost": 0.00152863,
        },
        {  # 控制台自身接口调用: 无 model/product, 不应计入用量
            "id": "287fbd65-5f3c-405a-b16b-4501c49c064d",
            "startedAt": 1790427749237,
            "category": "api",
            "serviceAPIKeyID": None,
            "model": None,
            "inputTokens": 0,
            "cost": 0,
        },
        {  # 缓存写入 (新接口只有单一字段)
            "id": "9d42a3c0-20b4-4354-9bfe-82d7a2f36058",
            "startedAt": 1790427740000,
            "category": "inference",
            "product": "go",
            "sessionID": "",
            "serviceAPIKeyID": "sk_01M3ESWS60E7J9STN1MHFQPYRM",
            "model": "kimi-k3",
            "provider": "opencode",
            "inputTokens": 100,
            "outputTokens": 20,
            "reasoningTokens": 0,
            "cacheReadTokens": 0,
            "cacheWriteTokens": 4096,
            "cost": "0.0000387",  # 字符串数字也应兼容
        },
    ],
    "nextCursor": '{"v":2,"kind":"list","until":1790427382939}',
    "until": 1790427382939,
    "retentionDays": 30,
}


# ---------------------------------------------------------------------------
# Cookie 归一化
# ---------------------------------------------------------------------------


def test_cookie_raw_value_gets_new_name():
    assert api.build_cookie_header("st_0019e474-abcd") == (
        "__Host-console_session=st_0019e474-abcd"
    )


def test_cookie_full_pair_passthrough():
    assert api.build_cookie_header("__Host-console_session=st_abc") == (
        "__Host-console_session=st_abc"
    )


def test_cookie_legacy_auth_pair_passthrough():
    assert api.build_cookie_header("auth=Fe26.2**deadbeef") == "auth=Fe26.2**deadbeef"


def test_cookie_strips_prefix_and_extra_cookies():
    raw = "Cookie: foo=1; __Host-console_session=st_xyz; bar=2"
    assert api.build_cookie_header(raw) == "__Host-console_session=st_xyz"


def test_cookie_empty_token():
    assert api.build_cookie_header("   ") == ""


# ---------------------------------------------------------------------------
# 配额解析
# ---------------------------------------------------------------------------


def test_parse_go_status_windows():
    windows = api.parse_go_status(GO_STATUS, NOW)
    assert [w.label for w in windows] == [
        api.LABEL_ROLLING, api.LABEL_WEEKLY, api.LABEL_MONTHLY,
    ]
    rolling, weekly, monthly = windows
    # 7632295 / 1200000000 = 0.636% (控制台显示 1%)
    assert rolling.used == 0.64
    assert rolling.remaining == 99.36
    assert rolling.reset_at == "2026-09-26T17:27:01.804000Z"
    assert rolling.reset_in_sec == 16236
    assert weekly.used == 0.25
    assert weekly.reset_at == "2026-09-28T00:00:00Z"
    # 月额度无 resetsAt -> 用 access.endsAt (30 天 - 50 分钟)
    assert monthly.reset_at == "2026-10-26T12:06:25Z"
    assert monthly.reset_in_sec == 2589000
    assert all(w.unit == "%" and w.total == 100.0 for w in windows)


def test_parse_go_status_clamps_over_limit():
    payload = {
        "access": {"meters": {"fiveHour": {
            "limitMicroCents": "100", "usedMicroCents": "250"}}}
    }
    windows = api.parse_go_status(payload, NOW)
    assert windows[0].used == 100.0
    assert windows[0].remaining == 0.0


def test_parse_go_status_without_subscription():
    assert api.parse_go_status({}, NOW) == []
    assert api.parse_go_status({"access": {}}, NOW) == []
    assert api.parse_go_status({"access": {"meters": {}}}, NOW) == []
    assert api.parse_go_status(None, NOW) == []


def test_parse_go_status_zero_limit_skipped():
    payload = {"access": {"meters": {"fiveHour": {
        "limitMicroCents": "0", "usedMicroCents": "10"}}}}
    assert api.parse_go_status(payload, NOW) == []


# ---------------------------------------------------------------------------
# 明细解析
# ---------------------------------------------------------------------------


def test_parse_request_logs_filters_and_maps():
    page = api.parse_request_logs(REQUEST_LOGS)
    assert len(page.records) == 2  # category=api 的一条被过滤
    assert page.retention_days == 30
    assert page.next_cursor and page.next_cursor.startswith('{"v":2')

    first = page.records[0]
    assert first.usg_id == "c34d84dc-d6e8-4d09-8a48-55d636a772d2"
    assert first.created_at == "2026-09-26T12:56:31.447000Z"
    assert first.model == "deepseek-v4.1-flash"
    assert first.provider == "opencode"
    assert (first.input_tokens, first.output_tokens, first.reasoning_tokens) == (2480, 1273, 629)
    assert first.cache_read_tokens == 130944
    assert first.key_id == "sk_01M3ESWS60E7J9STN1MHFQPYRM"
    assert first.session_id == "1e2a34d4-f057-45bd-8f0f-21c05481fa00"
    assert first.plan == "go"
    # cost 由 USD 浮点转 1e-8 USD 整数
    assert first.cost_raw == 152863
    assert first.cost_usd == 0.00152863


def test_parse_request_logs_cache_write_and_string_cost():
    second = api.parse_request_logs(REQUEST_LOGS).records[1]
    assert second.cache_write_5m_tokens == 4096
    assert second.cache_write_1h_tokens == 0
    assert second.cost_raw == 3870
    assert second.session_id == ""  # 无会话 -> 前端按 key 归属


def test_parse_request_logs_skips_missing_id_or_time():
    payload = {"items": [
        {"category": "inference", "id": "", "startedAt": 1790427391447},
        {"category": "inference", "id": "x", "startedAt": None},
        {"category": "inference", "id": "y", "startedAt": 1790427391447},
    ]}
    page = api.parse_request_logs(payload)
    assert [r.usg_id for r in page.records] == ["y"]
    assert page.next_cursor is None
    assert page.retention_days is None


def test_parse_request_logs_bad_payload():
    assert api.parse_request_logs(None).records == []
    assert api.parse_request_logs({}).records == []
    assert api.parse_request_logs({"items": "nope"}).records == []


def test_to_db_dict_roundtrip():
    rec = api.parse_request_logs(REQUEST_LOGS).records[0]
    row = rec.to_db_dict()
    assert set(row) == {
        "usg_id", "created_at", "model", "provider", "input_tokens", "output_tokens",
        "reasoning_tokens", "cache_read_tokens", "cache_write_5m_tokens",
        "cache_write_1h_tokens", "cost_raw", "cost_usd", "key_id", "session_id", "plan",
    }
    assert row["cost_usd"] == rec.cost_usd


# ---------------------------------------------------------------------------
# 时间 / 工作区工具
# ---------------------------------------------------------------------------


def test_iso_to_ms_matches_started_at():
    assert api.iso_to_ms("2026-09-26T12:56:31.447000Z") == 1790427391447


def test_iso_to_ms_invalid():
    assert api.iso_to_ms("") == 0
    assert api.iso_to_ms("not-a-date") == 0


def test_extract_workspace_id():
    wid = "wrk_01KXDVHZMY578NZ300DTR7WYE8"
    assert api.extract_workspace_id(wid) == wid
    assert api.extract_workspace_id(f"/console/{wid}/go") == wid
    assert api.extract_workspace_id("Default") == ""
    assert api.extract_workspace_id("") == ""


def test_iso_from_ms_invalid_returns_empty():
    assert api._iso_from_ms(None) == ""
    assert api._iso_from_ms(0) == ""
