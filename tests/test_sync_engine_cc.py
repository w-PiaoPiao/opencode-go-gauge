"""commandcode (GOAT) 同步分支测试: _sync_one_cc_account 的游标翻页/失败/停止语义.

P2-13: `_sync_one_cc_account` 此前在 tests 中 0 引用 (真实内部从未执行), 而它
与 opencode 分支的失败语义不同 —— CC incremental 首页失败即放弃, opencode 会
重试; 这里把现状固化成契约, 防止回归成"同步成功但静默少数据".

全部使用假 fetcher, 无网络.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app import db, server


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
def cc_env(tmp_path):
    _drain_server_background()
    db.set_data_dir(str(tmp_path))
    yield
    db.close_db()
    db.set_data_dir(None)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _record(usg_id: str) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": _today(),
        "model": "cc-model",
        "provider": db.PROVIDER_COMMANDCODE,
        "input_tokens": 10,
        "output_tokens": 5,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": 0.01,
    }


class _Rec:
    def __init__(self, usg_id: str, created_at: str | None = None):
        self.usg_id = usg_id
        self.created_at = created_at or _today()

    def to_db_dict(self) -> dict:
        return _record(self.usg_id)


class _Chart:
    def __init__(self, model: str = "cc-model"):
        self._model = model

    def to_db_dict(self) -> dict:
        return {
            "model": self._model,
            "provider": "commandcode",
            "time_bucket": _today().replace("T", " ").replace("Z", ""),
            "requests": 3,
            "tokens_in": 30,
            "tokens_out": 15,
            "tokens_total": 45,
        }


@pytest.fixture()
def cc_account(cc_env):
    aid = db.add_account(
        "cc-token", "Default", switch=True, provider=db.PROVIDER_COMMANDCODE)
    return aid


def _patch_charts(monkeypatch, rows=None, error: Exception | None = None) -> dict:
    calls = {"n": 0}

    def fake_charts(token):
        calls["n"] += 1
        if error is not None:
            raise error
        return rows if rows is not None else []

    monkeypatch.setattr(server, "cc_fetch_usage_charts", fake_charts)
    return calls


def test_cc_full_paginates_with_cursor(cc_account, monkeypatch):
    """游标翻页: next_cursor 驱动下一页, 两页记录全部落库, charts 一并写入."""
    aid = cc_account
    pages = {
        None: ([_Rec("cc1")], "cursor-2"),
        "cursor-2": ([_Rec("cc2")], None),
    }
    cursors: list = []

    def fake_page(token, cursor, size):
        cursors.append(cursor)
        return pages[cursor]

    monkeypatch.setattr(server, "cc_fetch_usage_page", fake_page)
    charts = _patch_charts(monkeypatch, [_Chart()])

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "full", None)

    assert result["ok"] is True
    assert result["inserted"] == 2 and result["pages"] == 2
    assert cursors == [None, "cursor-2"]
    assert charts["n"] == 1
    ids = {
        r["usg_id"] for r in db.get_db().execute(
            "SELECT usg_id FROM usage_records WHERE account_id = ?", (aid,)).fetchall()
    }
    assert ids == {"cc1", "cc2"}
    chart_count = db.get_db().execute(
        "SELECT COUNT(*) AS c FROM usage_charts WHERE account_id = ?", (aid,)
    ).fetchone()["c"]
    assert chart_count == 1


def test_cc_full_page_error_marks_partial_and_keeps_rows(cc_account, monkeypatch):
    """全量翻页失败: 保留已入库数据 + partial (charts 仍尝试补全)."""
    aid = cc_account
    calls = {"n": 0}

    def fake_page(token, cursor, size):
        calls["n"] += 1
        if calls["n"] == 1:
            return [_Rec("cc1")], "cursor-2"
        raise server.CommandCodeAPIError("boom")

    monkeypatch.setattr(server, "cc_fetch_usage_page", fake_page)
    _patch_charts(monkeypatch, [])

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "full", None)

    assert result["ok"] is True and result["partial"] is True
    assert result["failed_pages"] == 1
    assert result["inserted"] == 1
    assert db.count_records(aid) == 1
    assert db.get_sync_state(aid)["last_sync_status"] == "partial"


def test_cc_incremental_first_page_error_aborts(cc_account, monkeypatch):
    """CC incremental 首页失败即放弃 (与 opencode 重试语义不同, 现状契约)."""
    aid = cc_account

    def fake_page(token, cursor, size):
        raise server.CommandCodeAPIError("boom")

    monkeypatch.setattr(server, "cc_fetch_usage_page", fake_page)
    charts = _patch_charts(monkeypatch, [_Chart()])

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "incremental", None)

    assert result["ok"] is False and "boom" in result["error"]
    assert result["partial_inserted"] == 0
    assert charts["n"] == 0  # 明细整体失败: 不再拉 charts
    assert db.get_sync_state(aid)["last_sync_status"] == "error"


def test_cc_incremental_auth_error_aborts(cc_account, monkeypatch):
    aid = cc_account

    def fake_page(token, cursor, size):
        raise server.CCAuthError("unauthorized")

    monkeypatch.setattr(server, "cc_fetch_usage_page", fake_page)
    _patch_charts(monkeypatch, [])

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "incremental", None)
    assert result["ok"] is False and "unauthorized" in result["error"]


def test_cc_incremental_stops_after_two_duplicate_batches(cc_account, monkeypatch):
    """增量追平: 连续两批新增 0 即停 (不再翻页)."""
    aid = cc_account
    db.insert_usage_records([_record("dup")], aid)
    calls = {"n": 0}

    def fake_page(token, cursor, size):
        calls["n"] += 1
        return [_Rec("dup")], f"c{calls['n']}"

    monkeypatch.setattr(server, "cc_fetch_usage_page", fake_page)
    _patch_charts(monkeypatch, [])

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "incremental", None)

    assert result["ok"] is True and result["inserted"] == 0
    assert result["pages"] == 2
    assert calls["n"] == 2


def test_cc_full_window_boundary_stops_pagination(cc_account, monkeypatch):
    """全量同步越过同步范围边界: 保留边界页后停止."""
    aid = cc_account
    old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    calls = {"n": 0}

    def fake_page(token, cursor, size):
        calls["n"] += 1
        return [_Rec("ancient", old)], "older-cursor"

    monkeypatch.setattr(server, "cc_fetch_usage_page", fake_page)
    _patch_charts(monkeypatch, [])

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "full", 30)

    assert result["ok"] is True and result["inserted"] == 1
    assert calls["n"] == 1
    assert db.count_records(aid) == 1


def test_cc_empty_first_page_stops(cc_account, monkeypatch):
    """空页即到底: 不拉 charts 之外的额外翻页, 仍补全 charts."""
    aid = cc_account
    calls = {"n": 0}

    def fake_page(token, cursor, size):
        calls["n"] += 1
        return [], None

    monkeypatch.setattr(server, "cc_fetch_usage_page", fake_page)
    charts = _patch_charts(monkeypatch, [_Chart()])

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "full", None)

    assert result["ok"] is True and result["pages"] == 0
    assert calls["n"] == 1
    assert charts["n"] == 1  # 明细为空也要 charts (GOAT 统计主口径)


def test_cc_charts_failure_marks_partial(cc_account, monkeypatch):
    """charts 拉取失败: 明细已落库 -> partial, 不报整轮失败 (下次同步重试)."""
    aid = cc_account

    monkeypatch.setattr(
        server, "cc_fetch_usage_page",
        lambda token, cursor, size: ([_Rec("cc1")], None),
    )
    _patch_charts(monkeypatch, error=RuntimeError("charts down"))

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "full", None)

    assert result["ok"] is True and result["partial"] is True
    assert result["inserted"] == 1
    assert db.count_records(aid) == 1


def test_cc_max_pages_cap(cc_account, monkeypatch):
    """翻页上限: incremental 最多 INCREMENTAL_PAGES 页 (每页都有新数据也不失控)."""
    aid = cc_account
    counter = {"n": 0}

    def fake_page(token, cursor, size):
        counter["n"] += 1
        return [_Rec(f"cc{counter['n']}")], f"cursor-{counter['n']}"

    monkeypatch.setattr(server, "cc_fetch_usage_page", fake_page)
    _patch_charts(monkeypatch, [])

    result = server._sync_one_cc_account(aid, "goat", "cc-token", "incremental", None)

    assert result["ok"] is True
    assert result["pages"] == server.INCREMENTAL_PAGES
    assert counter["n"] == server.INCREMENTAL_PAGES
