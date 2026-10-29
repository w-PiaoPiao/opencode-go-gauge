"""同步引擎测试: 多账号遍历、分页、失败隔离、增量停止条件 (假 fetcher, 无网络).

覆盖此前会静默丢数据的回归:
- incremental 模式下首个账号失败曾直接 return, 导致其后所有账号永久无法自动同步;
- _sync_one_account 的内部流程 (游标翻页/单页重试/窗口边界/增量停止) 过去被整
  体 mock, 从未真正执行 (P2-13: 游标/页失败/增量停止回归会"同步成功但静默少数据").
CC (commandcode) 分支的用例在 tests/test_sync_engine_cc.py.
"""
from __future__ import annotations

import threading
import time

import pytest

from datetime import datetime, timezone

from app import backup, db, server


def _drain_server_background(timeout: float = 20.0) -> None:
    """等待前序用例遗留的后台同步/配额线程退出 (测试隔离).

    其它测试文件 (main() 冒烟等) 可能真实触发 sync_all_async; 残留线程会占住
    同步单飞闸门, 让本文件断言假红. 按线程名做有界等待并兜底复位同步状态.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        with server._sync_lock:
            running = bool(server._sync_state.get("running"))
        stray = [
            t for t in threading.enumerate()
            if t.name in ("gousage-sync", "gousage-quota") and t.is_alive()
        ]
        if not running and not stray:
            break
        time.sleep(0.05)
    with server._sync_lock:
        server._sync_state.update(
            running=False, mode="", page=0, inserted=0, phase="idle", message="", account="")




@pytest.fixture()
def two_accounts(tmp_path):
    """两个已登录账号 (id 2 为活跃); 隔离数据目录."""
    _drain_server_background()
    db.set_data_dir(str(tmp_path))
    server._key_names_fetched_at.clear()
    yield
    db.close_db()
    db.set_data_dir(None)


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


def _account(provider: str = db.PROVIDER_OPENCODE, workspace: str = "wrk_sync") -> int:
    return db.add_account("tok-" + workspace, workspace, switch=True, provider=provider)


# ---------------------------------------------------------------------------
# 多账号轮询 / 失败隔离 (既有回归)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 页数上限 / 窗口边界 / 增量停止判定 (纯函数)
# ---------------------------------------------------------------------------


def test_max_pages_for_modes():
    assert server._max_pages_for("full") == server.MAX_FULL_PAGES
    assert server._max_pages_for("incremental") == server.INCREMENTAL_PAGES
    # 未知 mode 按增量处理 (保守: 不会一次翻 1000 页)
    assert server._max_pages_for("whatever") == server.INCREMENTAL_PAGES


class _FakeRec:
    def __init__(self, created_at: str):
        self.created_at = created_at


def test_window_boundary_hit_only_for_full_with_window():
    from datetime import timedelta

    old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = [_FakeRec(fresh), _FakeRec(old)]
    assert server._window_boundary_hit(records, "full", 30) is True
    assert server._window_boundary_hit(records, "full", None) is False
    assert server._window_boundary_hit(records, "incremental", 30) is False
    assert server._window_boundary_hit([_FakeRec(fresh)], "full", 30) is False
    assert server._window_boundary_hit([], "full", 30) is False
    # 时间戳不可解析: 不判边界 (不误停)
    assert server._window_boundary_hit([_FakeRec("not-a-date")], "full", 30) is False


def test_incremental_done_requires_two_empty_batches():
    assert server._incremental_done(0, 0, "incremental") == (False, 1)
    assert server._incremental_done(0, 1, "incremental") == (True, 2)
    assert server._incremental_done(3, 1, "incremental") == (False, 0)  # 有新增即清零
    assert server._incremental_done(0, 1, "full") == (False, 0)  # full 不按空批停止


# ---------------------------------------------------------------------------
# _sync_one_account: 游标翻页 / 重试 / 失败语义 (假 fetcher)
# ---------------------------------------------------------------------------


class _FakePage:
    def __init__(self, records, cursor=None, retention_days=30):
        self.records = records
        self.next_cursor = cursor
        self.retention_days = retention_days


class _FakeUsageRecord:
    def __init__(self, usg_id: str, created_at: str = ""):
        self.usg_id = usg_id
        self.created_at = created_at or _TODAY_10AM

    def to_db_dict(self) -> dict:
        return _record(self.usg_id, self.created_at)


@pytest.fixture()
def opencode_ready(two_accounts, monkeypatch):
    """单账号 + 已解析 workspace (跳过 resolve_workspace_id 网络) + key 名称打桩."""
    aid = _account(workspace="wrk_abc")
    monkeypatch.setattr(server, "fetch_key_names", lambda *a, **k: {})
    monkeypatch.setattr(server.time, "sleep", lambda *_: None)  # 重试退避不真等
    return aid


def test_sync_one_account_paginates_via_cursor(opencode_ready, monkeypatch):
    """游标翻页: 两页数据 + next_cursor 到底, 记录全部落库."""
    aid = opencode_ready
    pages = {
        None: _FakePage([_FakeUsageRecord("p1")], cursor="c1"),
        "c1": _FakePage([_FakeUsageRecord("p2")], cursor=None),
    }
    cursors: list = []

    def fake_fetch(*_a, **kwargs):
        cursors.append(kwargs.get("cursor"))
        return pages[kwargs.get("cursor")]

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "full", None)

    assert result["ok"] is True and result["inserted"] == 2 and result["pages"] == 2
    assert cursors == [None, "c1"]
    ids = {
        r["usg_id"] for r in db.get_db().execute(
            "SELECT usg_id FROM usage_records WHERE account_id = ?", (aid,)).fetchall()
    }
    assert ids == {"p1", "p2"}


def test_sync_one_account_retries_page_then_succeeds(opencode_ready, monkeypatch):
    """翻页中途失败: 同一游标重试 (PAGE_RETRIES 次) 后成功, 不判 partial."""
    aid = opencode_ready
    calls = {"n": 0}

    def fake_fetch(*_a, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakePage([_FakeUsageRecord("p1")], cursor="c1")
        if calls["n"] == 2:
            raise server.OpenCodeAPIError("boom")
        return _FakePage([_FakeUsageRecord("p2")], cursor=None)

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "full", None)

    assert result["ok"] is True and result.get("partial") is not True
    assert result["inserted"] == 2 and result["pages"] == 2
    assert calls["n"] == 3


def test_sync_one_account_marks_partial_when_page_keeps_failing(opencode_ready, monkeypatch):
    """重试用尽仍失败: 保留已入库数据, 返回 partial + failed_pages."""
    aid = opencode_ready
    calls = {"n": 0}

    def fake_fetch(*_a, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakePage([_FakeUsageRecord("p1")], cursor="c1")
        raise server.OpenCodeAPIError("boom")

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "full", None)

    assert result["ok"] is True and result["partial"] is True
    assert result["failed_pages"] == 1
    assert result["inserted"] == 1
    assert calls["n"] == 1 + 1 + server.PAGE_RETRIES
    # 同步状态写 partial (前端可提示"数据不完整")
    assert db.get_sync_state(aid)["last_sync_status"] == "partial"


def test_sync_one_account_first_page_api_error_is_failure(opencode_ready, monkeypatch):
    """首页即失败 = 整体失败 (不能伪装成 partial/成功)."""
    aid = opencode_ready

    def fake_fetch(*_a, **kwargs):
        raise server.OpenCodeAPIError("boom")

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "incremental", None)

    assert result["ok"] is False and "boom" in result["error"]
    assert db.get_sync_state(aid)["last_sync_status"] == "error"


def test_sync_one_account_auth_error_aborts(opencode_ready, monkeypatch):
    """认证失败直接放弃 (重试无意义), 状态记 error."""
    aid = opencode_ready

    def fake_fetch(*_a, **kwargs):
        raise server.AuthError("unauthorized")

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "incremental", None)

    assert result["ok"] is False and "unauthorized" in result["error"]


def test_sync_one_account_incremental_stops_after_two_duplicate_batches(
        opencode_ready, monkeypatch):
    """增量追平: 连续两批新增 0 (全是已存在记录) 即停止, 不再翻页."""
    aid = opencode_ready
    db.insert_usage_records([_record("dup")], aid)
    calls = {"n": 0}

    def fake_fetch(*_a, **kwargs):
        calls["n"] += 1
        return _FakePage([_FakeUsageRecord("dup")], cursor=f"c{calls['n']}")

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "incremental", None)

    assert result["ok"] is True and result["inserted"] == 0
    assert result["pages"] == 2  # 第一批空, 第二批空 -> 停
    assert calls["n"] == 2


def test_sync_one_account_full_window_boundary_stops_pagination(opencode_ready, monkeypatch):
    """全量同步: 本页最早记录早于窗口边界 -> 保留该页后停止, 不再向更早翻页."""
    aid = opencode_ready
    from datetime import timedelta

    old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    calls = {"n": 0}

    def fake_fetch(*_a, **kwargs):
        calls["n"] += 1
        return _FakePage([_FakeUsageRecord("ancient", old)], cursor="older")

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "full", 30)

    assert result["ok"] is True and result["inserted"] == 1
    assert calls["n"] == 1  # 边界页保留后立即停
    assert db.count_records(aid) == 1


def test_sync_one_account_incremental_uses_overlap_since(opencode_ready, monkeypatch):
    """增量同步带 since_ms (最新记录 - 1h 重叠), 全量不带."""
    aid = opencode_ready
    db.insert_usage_records([_record("latest", _TODAY_10AM)], aid)
    # 增量起点来自 sync_state.newest_record_at: 该列由收尾/清理路径回填
    db.update_sync_state("ok", None, 1, aid)
    captured: dict = {}

    def fake_fetch(*_a, **kwargs):
        captured.update(kwargs)
        return _FakePage([], cursor=None)

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    server._sync_one_account(aid, "acc", "incremental", None)
    assert captured.get("since_ms") is not None
    assert captured["since_ms"] < server.iso_to_ms(_TODAY_10AM)

    captured.clear()
    server._sync_one_account(aid, "acc", "full", None)
    assert captured.get("since_ms") is None


def test_sync_one_account_key_names_refreshed_once_per_day(opencode_ready, monkeypatch):
    """key 名称缓存 24h 内不重复拉取 (整页网络请求 + settings 读写)."""
    aid = opencode_ready
    calls = {"n": 0}

    def fake_keys(*a, **k):
        calls["n"] += 1
        return {"k1": "Key One"}

    monkeypatch.setattr(server, "fetch_key_names", fake_keys)
    monkeypatch.setattr(
        server, "fetch_usage_page", lambda *a, **k: _FakePage([], cursor=None))

    server._sync_one_account(aid, "acc", "incremental", None)
    server._sync_one_account(aid, "acc", "incremental", None)
    assert calls["n"] == 1  # 第二轮命中 24h 时间戳
    assert db.get_key_names().get("k1") == "Key One"


# ---------------------------------------------------------------------------
# 数据写入/统计口径 (既有用例)
# ---------------------------------------------------------------------------


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


def test_insert_usage_records_scopes_identity_to_account(two_accounts):
    """同号 usg_id 在不同账号下各存一行, 不再互相夺走归属.

    历史: 主键曾是 usg_id 全局唯一, upsert 写作
    ON CONFLICT(usg_id) DO UPDATE ... account_id = excluded.account_id, 于是后同步
    的账号会把先同步账号的行改归自己 —— 前者用量凭空减少, 后者摊上不属于自己的
    记录. 曾假定 usg_id 由服务端全局生成、不会跨账号撞号, 该假定不成立
    (不同账号的 provider id 空间可重叠, 备份导入也会重放他人 id).
    唯一键现为 (account_id, usg_id); 数据搬运与迁移见 test_usage_record_identity.py.
    """
    a1 = db.add_account("tok1", "ws1", switch=True, provider=db.PROVIDER_OPENCODE)
    a2 = db.add_account("tok2", "ws2", switch=False, provider=db.PROVIDER_OPENCODE)

    db.insert_usage_records([_record("shared")], a1)
    assert db.insert_usage_records([_record("shared")], a2) == 1  # 对 a2 算新增

    owners = [
        r["account_id"]
        for r in db.get_db().execute(
            "SELECT account_id FROM usage_records WHERE usg_id = 'shared'"
        ).fetchall()
    ]
    assert sorted(owners) == sorted([a1, a2])

    # 同一账号内重复写仍是幂等更新, 不会多出一行
    assert db.insert_usage_records([_record("shared")], a1) == 0
    assert db.get_db().execute(
        "SELECT COUNT(*) AS c FROM usage_records"
        " WHERE account_id = ? AND usg_id = 'shared'",
        (a1,),
    ).fetchone()["c"] == 1


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
    """无记录的天补 0, 保证趋势图不缺天 (三端一致口径).

    I10: 返回**恰好** days 个点 (今天-days+1 … 今天), 与前端「N 日」文案一致.
    """
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_record("u1")], aid)

    rows = db.daily_stats(7, aid)
    assert len(rows) == 7  # 恰好 7 天, 不再多算一天
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


# ---------------------------------------------------------------------------
# N4: 备份导入维护态期间, 同步入口直接拒绝而不是排队等锁
# ---------------------------------------------------------------------------


def test_sync_usage_refused_while_importing(two_accounts, monkeypatch):
    """导入持写锁期间 sync_usage 直达调用立即返回"导入进行中" (不碰 DB 等锁)."""
    db.add_account("tok-n4", "wrk_n4", switch=True, provider=db.PROVIDER_OPENCODE)
    backup._importing.set()
    try:
        result = server.sync_usage("incremental")
    finally:
        backup._importing.clear()
    assert result["ok"] is False
    assert result["error"] == "导入进行中"
    # 维护态清理后同步立即可用 (假 _sync_one_account, 无网络)
    monkeypatch.setattr(
        server, "_sync_one_account",
        lambda aid, name, mode, wd: {"ok": True, "inserted": 0, "pages": 1})
    result = server.sync_usage("incremental")
    assert result["ok"] is True


def test_sync_all_async_skips_while_importing(two_accounts, monkeypatch):
    """后台 worker (自动同步定时器路径) 在维护态期间不启动同步."""
    db.add_account("tok-n4b", "wrk_n4b", switch=True, provider=db.PROVIDER_OPENCODE)
    called = {"sync": 0}
    real_sync_usage = server.sync_usage

    def counting(*a, **k):
        called["sync"] += 1
        return real_sync_usage(*a, **k)

    monkeypatch.setattr(server, "sync_usage", counting)
    backup._importing.set()
    try:
        server.sync_all_async("incremental")
        for _ in range(100):  # worker 是 daemon 线程: 有界等它跑完
            if called["sync"]:
                break
            time.sleep(0.01)
    finally:
        backup._importing.clear()
    assert called["sync"] == 0, "维护态期间不应启动同步"
    assert backup.is_importing() is False
