"""server.py 本地 HTTP 路由冒烟测试 (127.0.0.1 起真实服务, 只测无外网依赖的路由)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from app import db, server


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """独立临时库: 重定向 data_dir (同 test_db_multiuser)."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


@pytest.fixture()
def http(tmp_db):
    host, port = server.start_server("127.0.0.1", 0)
    yield f"http://{host}:{port}"
    server.stop_server()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status


def _request(url: str, method: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8")), exc.code


def test_version_route(http):
    data, status = _get(f"{http}/api/version")
    assert status == 200
    assert isinstance(data.get("version"), str) and data["version"]


def test_state_fresh_install(http):
    data, status = _get(f"{http}/api/state")
    assert status == 200
    assert data["logged_in"] is False
    assert data["accounts_total"] == 1  # 种子行


def test_settings_roundtrip(http):
    saved, status = _request(
        f"{http}/api/settings", "PUT", {"window_days": 90, "sync_interval_sec": 900})
    assert status == 200
    assert saved["window_days"] == 90
    assert saved["sync_interval_sec"] == 900
    again, status = _get(f"{http}/api/settings")
    assert status == 200
    assert again["window_days"] == 90


def test_settings_rejects_invalid_body(http):
    _, status = _request(f"{http}/api/settings", "PUT", None)
    assert status == 400


def test_sync_requires_login(http):
    _, status = _request(f"{http}/api/sync?mode=incremental", "POST")
    assert status == 401


def test_accounts_list(http):
    data, status = _get(f"{http}/api/accounts")
    assert status == 200
    assert data["ok"] is True
    assert len(data["accounts"]) == 1


def test_static_index_served(http):
    with urllib.request.urlopen(f"{http}/", timeout=5) as resp:
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "GoGauge" in body


def test_path_traversal_rejected(http):
    # Windows 盘符绝对路径与 .. 穿越都必须被 realpath 包含校验拦下
    for path in ("/..%2F..%2Fetc/passwd", "/..%5C..%5Cgousage.db"):
        try:
            _, status = _get(f"{http}{path}")
        except urllib.error.HTTPError as exc:
            status = exc.code
        assert status in (403, 404), path


# ---------------------------------------------------------------------------
# _record_cycle_bounds: 配额响应 → 周期边界落库 (「本周期」筛选起点的数据源)
# ---------------------------------------------------------------------------


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_record_cycle_bounds_prefers_real_period(tmp_db):
    """响应带真实周期 (Go access.startsAt/endsAt) 时落库并优先于「重置 - 30 天」
    回推 —— 31 天自然月下回推会得到未来起点, 「本周期」筛选恒为空."""
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=12)
    end = start + timedelta(days=31)
    server._record_cycle_bounds(1, {
        "period_start": _iso(start),
        "period_end": _iso(end),
        "windows": [{"label": "Monthly", "reset_at": _iso(end)}],
    })
    assert db.period_bounds(1) == (
        start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"),
    )
    assert db.monthly_cycle_start(1) == start.strftime("%Y-%m-%d %H:%M:%S")


def test_record_cycle_bounds_without_period_keeps_reset(tmp_db):
    """老响应无真实周期: 仍只记「下次重置」, 回推兜底路径可用."""
    from datetime import timedelta

    reset = datetime.now(timezone.utc) + timedelta(days=20)
    server._record_cycle_bounds(1, {
        "windows": [{"label": "Monthly", "reset_at": _iso(reset)}],
    })
    assert db.period_bounds(1) == (None, None)
    assert db.monthly_cycle_start(1) is not None


def test_record_cycle_bounds_garbage_never_raises(tmp_db):
    """异常数据/空响应不得抛出 (配额返回不能被落库失败拖垮)."""
    server._record_cycle_bounds(1, {})
    server._record_cycle_bounds(1, {
        "period_start": "x", "period_end": "y",
        "windows": [{"label": "Monthly", "reset_at": "bad"}],
    })
    assert db.period_bounds(1) == (None, None)


def test_attach_forecast_annotates_windows_without_mutating_cache():
    """dashboard 的 quota 窗口带打满预测字段, 且缓存对象 (接口原始形状) 不被污染."""
    quota = {
        "success": True,
        "period_start": "2026-10-08T00:00:00Z",
        "period_end": "2026-11-08T00:00:00Z",
        "windows": [
            {"label": "5h Rolling", "used": 42.0, "reset_at": "2026-10-08T05:00:00Z", "reset_in_sec": 12000},
            {"label": "Weekly", "used": 20.0, "reset_at": "2026-10-15T00:00:00Z", "reset_in_sec": 518400},
            {"label": "Monthly", "used": 3.0, "reset_at": "2026-11-08T00:00:00Z", "reset_in_sec": 2592000},
        ],
    }
    out = server._attach_forecast(quota)
    assert out["windows"][0]["forecast"] == {"state": "fill", "sec": 8286}
    assert out["windows"][1]["forecast"] == {"state": "fill", "sec": 4 * 86400}
    assert out["windows"][2]["forecast"] == {"state": "no_fill", "pct": 93}
    assert out is not quota
    assert all("forecast" not in w for w in quota["windows"])


def test_attach_forecast_skips_window_without_reset():
    """无重置时间 = 窗口未开始 (5h 窗口空闲): reset_in_sec 为 0 会让整窗被当成
    已过样本、算出「不会打满」—— 没有窗口在跑就别说预测, forecast 留 null."""
    quota = {
        "success": True,
        "period_start": "2026-10-08T00:00:00Z",
        "period_end": "2026-11-08T00:00:00Z",
        "windows": [
            {"label": "5h Rolling", "used": 0.0, "reset_at": "", "reset_in_sec": 0},
            {"label": "Monthly", "used": 3.0, "reset_at": "2026-11-08T00:00:00Z", "reset_in_sec": 2592000},
        ],
    }
    out = server._attach_forecast(quota)
    assert out["windows"][0]["forecast"] is None
    assert out["windows"][1]["forecast"] == {"state": "no_fill", "pct": 93}


def test_attach_forecast_passthrough_when_unavailable():
    """失败/空窗口的配额原样返回, 不给前端制造半截字段."""
    assert server._attach_forecast(None) is None
    failed = {"success": False, "error": "x", "windows": []}
    assert server._attach_forecast(failed) is failed
    no_windows = {"success": True}
    assert server._attach_forecast(no_windows) is no_windows


# ---------------------------------------------------------------------------
# 「按同步范围清理」: 同步范围是取数范围, 本地数据只能由按钮显式删除
# ---------------------------------------------------------------------------


def _stamp(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _rec(usg_id: str, created_at: str) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": created_at,
        "model": "test-model",
        "provider": "opencode",
        "input_tokens": 1,
        "output_tokens": 1,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": 0.0,
    }


def _count_records() -> int:
    return db.get_db().execute(
        "SELECT COUNT(*) AS c FROM usage_records").fetchone()["c"]


def test_prune_preview_then_execute(http, tmp_db):
    """预演只算数不写库; POST 才真删, 且只删边界之前的行."""
    db.insert_usage_records(
        [_rec("old-1", _stamp(100)), _rec("old-2", _stamp(100)), _rec("new-1", _stamp(0))],
        1,
    )
    _request(f"{http}/api/settings", "PUT", {"window_days": 30})

    preview, status = _get(f"{http}/api/usage/prune")
    assert status == 200
    assert preview["window_days"] == 30
    assert preview["count"] == 2
    assert _count_records() == 3, "预演不能删数据"

    done, status = _request(f"{http}/api/usage/prune", "POST")
    assert status == 200
    assert done["deleted"] == 2
    assert _count_records() == 1
    assert db.get_db().execute(
        "SELECT usg_id FROM usage_records").fetchone()["usg_id"] == "new-1"


def test_prune_is_noop_when_range_is_all(http, tmp_db):
    """同步范围「所有」= 不设上限, 清理按钮什么都不该删."""
    db.insert_usage_records([_rec("ancient", _stamp(400))], 1)
    _request(f"{http}/api/settings", "PUT", {"window_days": None})

    preview, _ = _get(f"{http}/api/usage/prune")
    assert preview["window_days"] is None
    assert preview["count"] == 0

    done, status = _request(f"{http}/api/usage/prune", "POST")
    assert status == 200
    assert done["deleted"] == 0
    assert _count_records() == 1


class _FakePage:
    """fetch_usage_page 的替身: 一页到底, 不产生网络请求."""

    def __init__(self, records):
        self.records = records
        self.next_cursor = None
        self.retention_days = 30


class _FakeRecord:
    def __init__(self, usg_id: str, created_at: str):
        self.usg_id = usg_id
        self.created_at = created_at

    def to_db_dict(self) -> dict:
        return _rec(self.usg_id, self.created_at)


def test_sync_never_deletes_local_records(tmp_db, monkeypatch):
    """回归: 同步结束不得裁剪窗口外的本地存量.

    window_days 只是取数范围 (调用它的全量同步据此决定翻页深度), 绝不能顺手
    删掉更早的记录 —— 早期实现每次同步都 prune, 把「改小同步范围」变成一次
    静默的不可恢复删除.
    """
    aid = db.add_account("tok", "wrk_test", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_rec("keep-old", _stamp(100))], aid)

    monkeypatch.setattr(
        server, "fetch_usage_page",
        lambda *a, **k: _FakePage([_FakeRecord("fresh", _stamp(0))]),
    )
    monkeypatch.setattr(server, "fetch_key_names", lambda *a, **k: {})

    result = server._sync_one_account(aid, "acc", "full", 30)
    assert result["ok"] is True

    ids = {
        r["usg_id"]
        for r in db.get_db().execute(
            "SELECT usg_id FROM usage_records WHERE account_id = ?", (aid,)).fetchall()
    }
    assert "keep-old" in ids, "同步把窗口外的本地记录删掉了"
    assert "fresh" in ids
