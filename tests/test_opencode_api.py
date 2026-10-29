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


def test_parse_go_status_idle_rolling_window_has_no_reset():
    """5h 窗口空闲 (窗口内无请求) 时 meter 只有金额字段, 没有 startsAt/resetsAt.

    实测 2026-10-14: 09:29 (UTC 01:29) 的配额快照里滚动窗口 0%、重置时间等于月
    周期结束; 09:31 窗口内第一条请求发出后 resetsAt 才出现 (= startsAt + 5h). 此时
    不能借月周期结束兜底 —— 那会把滚动窗口显示成「重置于 24 天 23 小时」.
    """
    idle = {
        "access": {
            "startsAt": "2026-10-08T01:01:55.000Z",
            "endsAt": "2026-11-08T01:01:55.000Z",
            "meters": {
                "fiveHour": {"limitMicroCents": "1200000000", "usedMicroCents": "0"},
                "week": {
                    "startsAt": "2026-10-12T00:00:00.000Z",
                    "resetsAt": "2026-10-19T00:00:00.000Z",
                    "limitMicroCents": "3000000000",
                    "usedMicroCents": "351654258",
                },
                "month": {"limitMicroCents": "6000000000", "usedMicroCents": "1052219276"},
            },
        }
    }
    rolling, weekly, monthly = api.parse_go_status(idle, NOW)
    assert rolling.used == 0.0
    assert rolling.reset_at == ""          # 窗口未开始: 重置时间未知
    assert rolling.reset_in_sec == 0
    # 月额度缺 resetsAt 仍走周期结束兜底 (与上一条用例同口径)
    assert monthly.reset_at == "2026-11-08T01:01:55Z"
    # 周期边界只影响窗口自身, 不泄漏到 5h/周窗口
    assert weekly.reset_at == "2026-10-19T00:00:00Z"


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


def test_parse_go_period_reads_access_bounds():
    """订阅周期起止取 access.startsAt/endsAt —— 月 meter 只有 resetsAt, 周期起点
    缺失时「本周期」筛选退回「重置 - 30 天」推算, 对自然月周期会算出未来起点."""
    assert api.parse_go_period(GO_STATUS) == (
        "2026-09-26T12:06:25Z", "2026-10-26T12:06:25Z",
    )


def test_parse_go_period_missing_fields():
    assert api.parse_go_period({}) == (None, None)
    assert api.parse_go_period(None) == (None, None)
    assert api.parse_go_period({"access": {"startsAt": "2026-09-26T12:06:25.000Z"}}) == (
        "2026-09-26T12:06:25Z", None,
    )
    assert api.parse_go_period({"access": {"startsAt": "not-a-date"}}) == (None, None)


def test_quota_result_dict_carries_period():
    """period_start/period_end 随 to_dict 出库, server._record_cycle_bounds 靠它落库."""
    import datetime as _dt

    result = api.QuotaResult(
        name="Default", workspace_id="wrk", success=True,
        updated_at="2026-09-26T13:00:00Z",
        period_start="2026-09-26T12:06:25Z", period_end="2026-10-26T12:06:25Z",
        windows=api.parse_go_status(GO_STATUS, NOW),
    )
    payload = result.to_dict()
    assert payload["period_start"] == "2026-09-26T12:06:25Z"
    assert payload["period_end"] == "2026-10-26T12:06:25Z"
    assert _dt.datetime.fromisoformat(payload["period_start"].replace("Z", "+00:00"))
    # 无周期时不出现该键 (前端/落库侧判空一致)
    bare = api.QuotaResult(name="D", workspace_id="w", success=True, updated_at="x").to_dict()
    assert "period_start" not in bare and "period_end" not in bare


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


# ---------------------------------------------------------------------------
# P3-19: 窗口 kind 稳定协议 / P3-20: 重试分类与 Retry-After
# ---------------------------------------------------------------------------

import urllib.error  # noqa: E402

import pytest  # noqa: E402

from app import _http_retry as _hr  # noqa: E402


def test_go_status_windows_expose_stable_kind():
    """to_dict 必须带稳定 kind (rolling/weekly/monthly); server 不再按 label 字面量判协议."""
    windows = api.parse_go_status(GO_STATUS, NOW)
    assert [w.kind for w in windows] == ["rolling", "weekly", "monthly"]
    payload = [w.to_dict() for w in windows]
    assert [w["kind"] for w in payload] == ["rolling", "weekly", "monthly"]
    assert [w["label"] for w in payload] == ["5h Rolling", "Weekly", "Monthly"]


def _http_error(code: int, headers=None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test/x", code, "boom", headers or {}, None)


def _fake_response(headers: dict, body: bytes):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, _n=-1):
            return body

    resp = _Resp()
    resp.headers = headers
    return resp


def test_opencode_does_not_retry_deterministic_4xx(monkeypatch):
    calls = []

    def _fake_urlopen(*_a, **_k):
        calls.append(1)
        raise _http_error(422)

    monkeypatch.setattr(api.urllib.request, "urlopen", _fake_urlopen)
    with pytest.raises(api.OpenCodeAPIError, match="422"):
        api._api_get("/go/status", "token", org_id="wrk_x")
    assert len(calls) == 1


def test_opencode_retries_5xx(monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr(api.time, "sleep", lambda s: sleeps.append(s))

    def _fake_urlopen(*_a, **_k):
        calls.append(1)
        raise _http_error(503)

    monkeypatch.setattr(api.urllib.request, "urlopen", _fake_urlopen)
    with pytest.raises(api.OpenCodeAPIError, match="503"):
        api._api_get("/go/status", "token", org_id="wrk_x")
    assert len(calls) == api.FETCH_RETRIES
    assert sleeps == [_hr.RETRY_BACKOFF[0], _hr.RETRY_BACKOFF[1]]


def test_opencode_honors_retry_after_capped(monkeypatch):
    sleeps = []
    monkeypatch.setattr(api.time, "sleep", lambda s: sleeps.append(s))

    def _fake_urlopen(*_a, **_k):
        raise _http_error(429, {"Retry-After": "60"})

    monkeypatch.setattr(api.urllib.request, "urlopen", _fake_urlopen)
    with pytest.raises(api.OpenCodeAPIError, match="429"):
        api._api_get("/go/status", "token", org_id="wrk_x")
    assert sleeps == [_hr.MAX_RETRY_AFTER_SEC, _hr.MAX_RETRY_AFTER_SEC]


def test_opencode_auth_and_404_not_retried(monkeypatch):
    calls = []

    def _fake_urlopen(*_a, **_k):
        calls.append(1)
        raise _http_error(401)

    monkeypatch.setattr(api.urllib.request, "urlopen", _fake_urlopen)
    with pytest.raises(api.AuthError):
        api._api_get("/go/status", "token", org_id="wrk_x")
    assert len(calls) == 1


def test_opencode_maps_oversized_response_to_domain_error(monkeypatch):
    monkeypatch.setattr(
        api.urllib.request, "urlopen",
        lambda *_a, **_k: _fake_response(
            {"Content-Length": str(api.MAX_BODY_BYTES + 1)}, b""))
    with pytest.raises(api.OpenCodeAPIError, match="响应过大"):
        api._api_get("/request-logs", "token", org_id="wrk_x")
