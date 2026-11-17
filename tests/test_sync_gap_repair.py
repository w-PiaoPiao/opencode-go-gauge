"""同步缺口自愈回归用例：截断检测 / 游标安全 / 自动全量校准.

背景（用户实测 bug）：应用休眠几天后重开，增量同步的 `since` 会回溯到几天前，
而旧实现一轮最多翻 10 页 (1000 条) 且把"页数耗尽"当成功收尾 —— 收尾又会用
`MAX(created_at)` 前移增量游标，于是缺口旧端永远不再被增量请求，只能手动全量
同步补回。表现：趋势图某 1~2 天为 0，全量同步后数据才出现。

本文件锁定四件事：
1. since 已知时必须连续翻到 since 边界，中间命中已入库数据（0 新增）也不能早停；
2. 页数预算耗尽 → partial（而不是 ok），且不推进游标；
3. 游标只在完整收尾（ok）时前移；
4. 每账号超过 AUTO_FULL_SYNC_DAYS 未成功全量 → 增量轮询自动改跑 full 校准。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import db, server


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _record(usg_id: str, created_at: str) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": created_at,
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


class _FakeRec:
    def __init__(self, usg_id: str, created_at: str):
        self.usg_id = usg_id
        self.created_at = created_at

    def to_db_dict(self) -> dict:
        return _record(self.usg_id, self.created_at)


class _FakePage:
    def __init__(self, records, cursor=None, retention_days=30):
        self.records = records
        self.next_cursor = cursor
        self.retention_days = retention_days


@pytest.fixture()
def engine(tmp_db, monkeypatch):
    """单账号 + 已解析 workspace（wrk_ 前缀快速路径，零网络）+ 干净的同步状态。"""
    aid = db.add_account("tok", "wrk_gap", switch=True, provider=db.PROVIDER_OPENCODE)
    monkeypatch.setattr(server, "fetch_key_names", lambda *a, **k: {})
    monkeypatch.setattr(server.time, "sleep", lambda *_: None)
    with server._sync_lock:
        server._sync_state.update(
            running=False, mode="", page=0, inserted=0,
            phase="idle", message="", account="",
        )
    yield aid
    with server._sync_lock:
        server._sync_state.update(running=False, phase="idle", message="", account="")


# ---------------------------------------------------------------------------
# 1) since 边界停止：中间命中已知数据（0 新增）也不能提前结束
# ---------------------------------------------------------------------------

def test_incremental_pages_past_known_records_to_since_boundary(engine, monkeypatch):
    """连续两批 0 新增不得早停：必须翻到 since 边界，否则缺口补不上。"""
    aid = engine
    now = datetime.now(timezone.utc)
    known_at = _iso(now - timedelta(minutes=30))
    db.insert_usage_records([_record("known", known_at)], aid)
    db.update_sync_state("ok", None, 1, aid)  # 游标 = known_at → since = known_at - 1h

    fresh_at = _iso(now - timedelta(minutes=10))
    ancient_at = _iso(now - timedelta(hours=3))
    pages = {
        None: _FakePage([_FakeRec("fresh", fresh_at)], cursor="c1"),
        "c1": _FakePage([_FakeRec("known", known_at)], cursor="c2"),      # 0 新增
        "c2": _FakePage([_FakeRec("known", known_at)], cursor="c3"),      # 仍然 0 新增
        "c3": _FakePage([_FakeRec("ancient", ancient_at)], cursor="c4"),  # 越过 since
    }
    fetched: list = []

    def fake_fetch(*_a, **kwargs):
        fetched.append(kwargs.get("cursor"))
        return pages[kwargs.get("cursor")]

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "incremental", None)

    assert result["ok"] is True
    assert not result.get("partial")
    assert fetched == [None, "c1", "c2", "c3"], "在已知数据段提前停止了 (缺口会被永远的跳过)"
    assert result["inserted"] == 2  # fresh + ancient


def test_incremental_stops_when_page_crosses_since(engine, monkeypatch):
    """同一页最早记录已早于 since → 该页照常落库后停止。"""
    aid = engine
    now = datetime.now(timezone.utc)
    known_at = _iso(now - timedelta(minutes=30))
    db.insert_usage_records([_record("known", known_at)], aid)
    db.update_sync_state("ok", None, 1, aid)

    old_at = _iso(now - timedelta(hours=2))
    calls = {"n": 0}

    def fake_fetch(*_a, **kwargs):
        calls["n"] += 1
        return _FakePage([_FakeRec("older", old_at)], cursor="never")

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "incremental", None)

    assert calls["n"] == 1
    assert result["ok"] is True and result["pages"] == 1
    assert db.count_records(aid) == 2  # 越界的旧记录也照常落库


# ---------------------------------------------------------------------------
# 2) 页数预算耗尽 = 数据不完整：partial + 不推进游标
# ---------------------------------------------------------------------------

def test_incremental_truncation_marks_partial_and_keeps_cursor(engine, monkeypatch):
    """页数耗尽且未到 since 边界：必须 partial，且 newest 游标保持旧值。"""
    aid = engine
    now = datetime.now(timezone.utc)
    oldest_at = _iso(now - timedelta(hours=3))
    db.insert_usage_records([_record("oldest", oldest_at)], aid)
    db.update_sync_state("ok", None, 1, aid)
    cursor_before = db.get_sync_state(aid)["newest_record_at"]
    assert cursor_before

    monkeypatch.setattr(server, "INCREMENTAL_PAGES", 3)
    fresh_at = _iso(now - timedelta(minutes=10))
    calls = {"n": 0}

    def fake_fetch(*_a, **kwargs):
        calls["n"] += 1
        return _FakePage([_FakeRec(f"r{calls['n']}", fresh_at)], cursor=f"c{calls['n']}")

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "incremental", None)

    assert calls["n"] == 3
    assert result["ok"] is True and result.get("partial") is True
    assert result.get("truncated") is True
    state = db.get_sync_state(aid)
    assert state["last_sync_status"] == "partial"
    assert "翻页上限" in (state["last_sync_error"] or "")
    assert state["newest_record_at"] == cursor_before, "截断时游标前移 → 缺口将永远补不上"


def test_full_truncation_marks_partial(engine, monkeypatch):
    """全量模式同样不能把"页数耗尽"静默当成功。"""
    aid = engine
    monkeypatch.setattr(server, "MAX_FULL_PAGES", 2)
    now = datetime.now(timezone.utc)
    calls = {"n": 0}

    def fake_fetch(*_a, **kwargs):
        calls["n"] += 1
        at = _iso(now - timedelta(minutes=calls["n"]))
        return _FakePage([_FakeRec(f"r{calls['n']}", at)], cursor=f"c{calls['n']}")

    monkeypatch.setattr(server, "fetch_usage_page", fake_fetch)
    result = server._sync_one_account(aid, "acc", "full", None)

    assert calls["n"] == 2
    assert result.get("partial") is True and result.get("truncated") is True
    assert db.get_sync_state(aid)["last_sync_status"] == "partial"


# ---------------------------------------------------------------------------
# 3) 游标只在完整收尾时前移（db 层语义）
# ---------------------------------------------------------------------------

def test_cursor_only_advances_on_complete_sync(tmp_db):
    aid = db.add_account("tok", "wrk_cursor", switch=True, provider=db.PROVIDER_OPENCODE)
    now = datetime.now(timezone.utc)
    t1 = _iso(now - timedelta(hours=2))
    t2 = _iso(now - timedelta(minutes=5))

    db.insert_usage_records([_record("a", t1)], aid)
    db.update_sync_state("ok", None, 1, aid)
    first = db.get_sync_state(aid)["newest_record_at"]
    assert first

    db.insert_usage_records([_record("b", t2)], aid)
    # 不完整的一轮：total 刷新，但游标必须原地不动
    db.update_sync_state("partial", "截断", 1, aid, advance_cursor=False)
    state = db.get_sync_state(aid)
    assert state["total_records"] == 2
    assert state["newest_record_at"] == first

    db.update_sync_state("ok", None, 1, aid)
    assert db.get_sync_state(aid)["newest_record_at"] != first


def test_cursor_seeded_even_when_first_sync_incomplete(tmp_db):
    """新账号首轮就失败时也要写入游标，否则会一直退回"无游标=类全量"慢路径。"""
    aid = db.add_account("tok", "wrk_cursor2", switch=True, provider=db.PROVIDER_OPENCODE)
    at = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    db.insert_usage_records([_record("a", at)], aid)
    db.update_sync_state("error", "boom", 1, aid, advance_cursor=False)
    assert db.get_sync_state(aid)["newest_record_at"]


# ---------------------------------------------------------------------------
# 4) 自动全量校准：last_full_sync_at 与 due 判定
# ---------------------------------------------------------------------------

def _rewrite_full_sync_key(aid: int, value: str) -> None:
    conn = db.get_db()
    with db._payload_lock:
        data = db._raw_payload(conn)
        data[f"last_full_sync_at:{aid}"] = value
        db._write_payload(conn, data)


def test_full_sync_due_and_mark(tmp_db):
    aid = db.add_account("tok", "wrk_full", switch=True, provider=db.PROVIDER_OPENCODE)
    assert db.get_last_full_sync_at(aid) is None
    assert db.full_sync_due(aid) is True, "从未全量 → 需要一次校准"

    db.mark_full_sync_done(aid)
    assert db.get_last_full_sync_at(aid)
    assert db.full_sync_due(aid) is False

    old = (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _rewrite_full_sync_key(aid, old)
    assert db.full_sync_due(aid) is True
    assert db.full_sync_due(aid, max_age_days=30) is False

    _rewrite_full_sync_key(aid, "not-a-timestamp")
    assert db.full_sync_due(aid) is True, "坏时间戳按需要校准处理"


def test_finish_sync_marks_full_sync_done_only_on_ok(tmp_db):
    aid = db.add_account("tok", "wrk_full2", switch=True, provider=db.PROVIDER_OPENCODE)
    # 截断（partial）不算一次成功的校准
    server._finish_sync(aid, 0, 1, truncated=True, full_mode=True)
    assert db.get_last_full_sync_at(aid) is None
    server._finish_sync(aid, 0, 1, full_mode=True)
    assert db.get_last_full_sync_at(aid) is not None


def test_sync_usage_auto_calibrates_due_account(tmp_db, monkeypatch):
    """增量轮询里：due 的账号自动改跑 full，未 due 的账号保持 incremental。"""
    a_due = db.add_account("tok-a", "wrk_a", switch=True, provider=db.PROVIDER_OPENCODE)
    b_fresh = db.add_account("tok-b", "wrk_b", switch=False, provider=db.PROVIDER_OPENCODE)
    db.mark_full_sync_done(b_fresh)
    modes: list[tuple[int, str]] = []

    def fake_sync_one(account_id, name, mode, window_days):
        modes.append((account_id, mode))
        return {"ok": True, "inserted": 0, "pages": 1}

    monkeypatch.setattr(server, "_sync_one_account", fake_sync_one)
    with server._sync_lock:
        server._sync_state.update(running=False)
    result = server.sync_usage("incremental")

    assert result["ok"] is True
    assert (a_due, "full") in modes
    assert (b_fresh, "incremental") in modes


# ---------------------------------------------------------------------------
# 5) 启动补同步判定
# ---------------------------------------------------------------------------

def test_startup_sync_needed(tmp_db):
    aid = db.add_account("tok", "wrk_start", switch=True, provider=db.PROVIDER_OPENCODE)
    assert db.get_token()
    assert server.startup_sync_needed() is True, "从未同步 → 启动补一轮"

    db.update_sync_state("ok", None, 0, aid)
    assert server.startup_sync_needed() is False, "刚同步完 → 不重复打请求"

    conn = db.get_db()
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "UPDATE usage_sync_state SET last_sync_at = ? WHERE account_id = ?", (old, aid)
    )
    conn.commit()
    assert server.startup_sync_needed() is True, "上次同步已过期 → 启动补一轮"

    db.save_settings({"auto_sync": False})
    assert server.startup_sync_needed() is False, "关闭自动同步后不自动补"


# ---------------------------------------------------------------------------
# 6) 纯函数：本页最早时间 / since 边界判定
# ---------------------------------------------------------------------------

def test_oldest_record_ms_and_reached_since_boundary():
    now = datetime.now(timezone.utc)
    a = _iso(now - timedelta(minutes=50))
    b = _iso(now - timedelta(minutes=10))
    recs = [_FakeRec("a", a), _FakeRec("b", b)]

    oldest = server._oldest_record_ms(recs)
    assert oldest is not None and oldest == server.iso_to_ms(a)
    assert server._oldest_record_ms([]) is None

    # since 晚于本页最早记录 → 已越过边界
    assert server._reached_since_boundary(recs, server.iso_to_ms(b) + 1000) is True
    # since 早于本页最早记录 → 还没翻到
    assert server._reached_since_boundary(recs, server.iso_to_ms(a) - 1000) is False
    # 无 since（账号还没有游标）→ 不看边界
    assert server._reached_since_boundary(recs, None) is False


def test_page_budget_parity_between_modes():
    """增量必须能追平多天缺口：翻页预算与全量同量级（旧值 10 会静默截断）。"""
    assert server.INCREMENTAL_PAGES >= 100
    assert server._max_pages_for("incremental") == server.INCREMENTAL_PAGES
    assert server._max_pages_for("full") == server.MAX_FULL_PAGES
