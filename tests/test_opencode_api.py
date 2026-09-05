"""opencode_api 解析器测试: 配额 HTML 正则 (双字段序/钳制) 与 server-fn 用量响应切分.

桌面端最脆弱的两段代码 (正则解析序列化 JS) 此前无单测覆盖.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.opencode_api import parse_quota_html, parse_usage_response


def test_quota_html_three_windows():
    html = (
        'rollingUsage: $R[12] = {usagePercent: 12.5, resetInSec: 3600, other: 1} '
        'weeklyUsage: $R[13] = {resetInSec: 86400, usagePercent: 55} '
        'monthlyUsage: $R[14] = {usagePercent: 30, resetInSec: 900}'
    )
    now = datetime.now(timezone.utc)
    windows = parse_quota_html(html, now)
    assert [w.label for w in windows] == ["5h Rolling", "Weekly", "Monthly"]

    rolling, weekly, monthly = windows
    assert rolling.used == 12.5
    assert rolling.remaining == 87.5
    assert rolling.reset_in_sec == 3600
    assert rolling.reset_at == (now + timedelta(seconds=3600)).isoformat().replace("+00:00", "Z")
    assert weekly.used == 55.0
    assert weekly.reset_in_sec == 86400  # resetInSec 在前的字段序也要能解析
    assert monthly.used == 30.0


def test_quota_html_clamps_and_negative_reset():
    html = 'monthlyUsage: $R[1] = {usagePercent: 150, resetInSec: -5}'
    windows = parse_quota_html(html)
    assert len(windows) == 1
    assert windows[0].used == 100.0
    assert windows[0].remaining == 0.0
    assert windows[0].reset_in_sec == -5  # 桌面端不钳制负重置时间, 由前端展示兜底


def test_quota_html_no_match_returns_empty():
    assert parse_quota_html("<html>nothing here</html>") == []


def test_usage_response_get_format():
    text = (
        'id:"usg_a",kind:0,enrichment:$R[9]={plan:"lite"},model:"m1",provider:"p1",'
        'inputTokens:100,outputTokens:20,reasoningTokens:5,'
        'cacheReadTokens:7,cacheWrite5mTokens:1,cacheWrite1hTokens:2,'
        'cost:12345,keyID:"key_1",sessionID:"ses_1",'
        'timeCreated: $R[3] = new Date("2026-01-02T10:00:00Z")'
    )
    records = parse_usage_response(text)
    assert len(records) == 1
    r = records[0]
    assert r.usg_id == "usg_a"
    assert r.created_at == "2026-01-02T10:00:00Z"
    assert r.model == "m1"
    assert r.plan == "lite"
    assert r.input_tokens == 100
    assert r.output_tokens == 20
    assert r.reasoning_tokens == 5
    assert r.cache_read_tokens == 7
    assert r.cache_write_5m_tokens == 1
    assert r.cache_write_1h_tokens == 2
    assert r.cost_raw == 12345
    assert abs(r.cost_usd - 12345 / 100_000_000.0) < 1e-12
    assert r.key_id == "key_1"
    assert r.session_id == "ses_1"


def test_usage_response_post_format_with_spaces():
    # 新格式: 冒号后带空格
    text = (
        'id: "usg_b", model: "m2", inputTokens: 5, outputTokens: 6, cost: 7, '
        'keyID: "key_2", sessionID: "", '
        'timeCreated: $R[4] = new Date("2026-01-03T11:00:00Z")'
    )
    records = parse_usage_response(text)
    assert len(records) == 1
    assert records[0].usg_id == "usg_b"
    assert records[0].input_tokens == 5
    assert records[0].plan is None  # 无 enrichment 块 -> 无 plan
    assert records[0].session_id == ""


def test_usage_response_two_records_split_by_anchor():
    text = (
        'id:"usg_a",model:"m1",inputTokens:100,'
        'timeCreated: $R[3] = new Date("2026-01-02T10:00:00Z")'
        '|||'
        'id:"usg_b",model:"m2",inputTokens:5,'
        'timeCreated: $R[4] = new Date("2026-01-03T11:00:00Z")'
    )
    records = parse_usage_response(text)
    assert [r.usg_id for r in records] == ["usg_a", "usg_b"]
    # 各自字段只取自己区间内的值: usg_b 的 inputTokens 不得读到 usg_a 的
    assert records[0].input_tokens == 100
    assert records[1].input_tokens == 5


def test_usage_response_skips_records_without_created_at():
    text = 'id:"usg_a",model:"m1",inputTokens:1'  # 无 timeCreated: 整条丢弃
    assert parse_usage_response(text) == []
