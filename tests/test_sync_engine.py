"""同步引擎测试: 多账号遍历、失败隔离、增量停止条件 (假 fetcher, 无网络).

覆盖此前会静默丢数据的回归: incremental 模式下首个账号失败曾直接 return,
导致其后所有账号永久无法自动同步.
"""
from __future__ import annotations

import pytest

from datetime import datetime

from app import db, server


@pytest.fixture()
def two_accounts(tmp_path, monkeypatch):
    """两个已登录账号 (id 2 为活跃); 隔离数据目录."""
    monkeypatch.setenv("GOUSAGE_DATA", str(tmp_path))
    db.set_data_dir(str(tmp_path))
    # 重置连接与建表标记, 让新目录生效
    db.close_db()
    db._schema_init_path = None
    yield
    db.close_db()
    db._schema_init_path = None


# 默认落在今天: 日期写死会随时间推移落出 7 天统计窗口 (曾因此假日失败)
_TODAY_10AM = datetime.now().strftime("%Y-%m-%d") + " 10:00:00"


def _record(usg_id: str, created_at: str = "") -> dict:
    return {
        "usg_id": usg_id,
        "created_at": created_at or _TODAY_10AM,
        "model": "test-model",
        "input_tokens": 10,
        "output_tokens": 5,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": 0.01,
    }


def test_incremental_continues_after_account_failure(two_accounts, monkeypatch):
    """首个账号失败时, 后续账号仍必须被同步 (P1 回归)."""
    db.add_account("token-a", "wsA", switch=True, provider=db.PROVIDER_OPENCODE)
    db.add_account("token-b", "wsB", switch=False, provider=db.PROVIDER_OPENCODE)
    accounts = [a for a in db.list_accounts() if a["has_token"]]
    assert len(accounts) == 2
    failing_id = accounts[0]["id"]

    attempted: list[int] = []

    def fake_sync_one(account_id, name, mode, window_days):
        attempted.append(account_id)
        if account_id == failing_id:
            return {"ok": False, "error": "认证失败 (HTTP 401)"}
        inserted = db.insert_usage_records([_record(f"u{account_id}")], account_id)
        return {"ok": True, "inserted": inserted, "pages": 1}

    monkeypatch.setattr(server, "_sync_one_account", fake_sync_one)
    result = server.sync_usage("incremental")

    assert attempted == [a["id"] for a in accounts], "失败账号之后的账号被跳过"
    assert result["ok"] is True
    assert result["partial"] is True
    assert result["inserted"] == 1
    assert len(result["errors"]) == 1


def test_incremental_all_accounts_failing_reports_error(two_accounts, monkeypatch):
    """所有账号都失败 -> 整轮报错 (前端展示错误而不是虚假成功)."""
    db.add_account("token-a", "wsA", switch=True, provider=db.PROVIDER_OPENCODE)
    db.add_account("token-b", "wsB", switch=False, provider=db.PROVIDER_OPENCODE)

    monkeypatch.setattr(
        server, "_sync_one_account",
        lambda aid, name, mode, wd: {"ok": False, "error": "认证失败 (HTTP 401)"},
    )
    result = server.sync_usage("incremental")

    assert result["ok"] is False
    assert "401" in result["error"]


def test_full_mode_targets_only_active_account(two_accounts, monkeypatch):
    """full 模式只同步活跃账号."""
    db.add_account("token-a", "wsA", switch=True, provider=db.PROVIDER_OPENCODE)
    db.add_account("token-b", "wsB", switch=False, provider=db.PROVIDER_OPENCODE)
    active = db.get_active_account_id()

    attempted: list[int] = []

    def fake_sync_one(account_id, name, mode, window_days):
        attempted.append(account_id)
        return {"ok": True, "inserted": 0, "pages": 1}

    monkeypatch.setattr(server, "_sync_one_account", fake_sync_one)
    server.sync_usage("full")

    assert attempted == [active]


def test_insert_usage_records_counts_only_new_ids(two_accounts):
    """重复写入同一批只计一次新增; 二次写入计 0."""
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)

    first = db.insert_usage_records([_record("u1"), _record("u2")], aid)
    assert first == 2

    # 同 id 再写 (内容更新) 不算新增
    again = db.insert_usage_records([_record("u1"), _record("u2"), _record("u3")], aid)
    assert again == 1

    # 批内重复 id 只计一次
    dup = db.insert_usage_records([_record("u4"), _record("u4")], aid)
    assert dup == 1


def test_insert_usage_records_reassigns_owner_on_conflict(two_accounts):
    """桌面端 UPSERT 语义: 冲突时 account_id 取 excluded (后写覆盖归属).

    注意与 Android 的差异: Android 的 insertUsageRecords 刻意保留原归属
    (existingOwnership)。两边都在各自平台自洽 —— usg_id 是服务端按请求生成的
    全局唯一值, 正常数据流下同一 id 不会落进两个账号, 因此该分支只在异常数据
    下触发. 此用例锁定桌面端行为, 防止今后无意改动.
    """
    a1 = db.add_account("tok1", "ws1", switch=True, provider=db.PROVIDER_OPENCODE)
    a2 = db.add_account("tok2", "ws2", switch=False, provider=db.PROVIDER_OPENCODE)

    db.insert_usage_records([_record("shared")], a1)
    db.insert_usage_records([_record("shared")], a2)

    row = db.get_db().execute(
        "SELECT account_id FROM usage_records WHERE usg_id = 'shared'"
    ).fetchone()
    assert row["account_id"] == a2


def test_period_filter_uses_local_date(two_accounts):
    """local_date 落库正确, 且 'today' 过滤走索引列 (功能等价性)."""
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_record("u1")], aid)

    row = db.get_db().execute(
        "SELECT local_date FROM usage_records WHERE usg_id = 'u1'"
    ).fetchone()
    assert row["local_date"] is not None and len(row["local_date"]) == 10

    # 查询计划必须命中 local_date 索引而不是全表扫
    plan = db.get_db().execute(
        "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM usage_records"
        " WHERE account_id = ? AND local_date = date('now','localtime')",
        (aid,),
    ).fetchall()
    detail = " ".join(str(r["detail"]) for r in plan)
    assert "idx_usage_account_localdate" in detail


def test_daily_stats_zero_fills_missing_days(two_accounts):
    """无记录的天补 0, 保证趋势图不缺天 (三端一致口径)."""
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_record("u1")], aid)

    rows = db.daily_stats(7, aid)
    assert len(rows) == 8  # 含今天, 共 days+1 天
    assert all("date" in r and "request_count" in r for r in rows)
    assert sum(r["request_count"] for r in rows) >= 1


def test_insert_usage_charts_persists_local_date(two_accounts):
    """charts 行写入: local_date 由 time_bucket 派生 (占位符与绑定数必须一致).

    回归: insert_usage_charts 曾漏掉 date() 的绑定值, executemany 抛
    ProgrammingError, 而同步路径的 broad except 把它报成"聚合数据拉取失败",
    静默丢掉了 GOAT 全周期统计.
    """
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_COMMANDCODE)
    rows = [
        {"model": "m1", "provider": "cc", "time_bucket": "2026-09-10 02:30:00",
         "requests": 7, "tokens_in": 100, "tokens_out": 50, "tokens_total": 150},
        {"model": "m2", "provider": "cc", "time_bucket": "2026-09-09 23:30:00",
         "requests": 3, "tokens_in": 10, "tokens_out": 5, "tokens_total": 15},
    ]
    assert db.insert_usage_charts(rows, aid) == 2

    got = {
        r["model"]: r["local_date"]
        for r in db.get_db().execute(
            "SELECT model, local_date FROM usage_charts WHERE account_id = ?", (aid,)
        )
    }
    # 本地日必须与 SQLite 自身口径一致
    expected = db.get_db().execute(
        "SELECT date('2026-09-10 02:30:00','localtime') AS a, date('2026-09-09 23:30:00','localtime') AS b"
    ).fetchone()
    assert got["m1"] == expected["a"]
    assert got["m2"] == expected["b"]

    # 重复写入同一键应 UPSERT 覆盖而非报错 (主键 account_id+model+time_bucket)
    rows[0]["requests"] = 99
    assert db.insert_usage_charts(rows, aid) == 2
    cnt = db.get_db().execute(
        "SELECT COUNT(*) AS c FROM usage_charts WHERE account_id = ?", (aid,)
    ).fetchone()["c"]
    assert cnt == 2
    assert db.get_db().execute(
        "SELECT requests FROM usage_charts WHERE account_id=? AND model='m1'", (aid,)
    ).fetchone()["requests"] == 99
