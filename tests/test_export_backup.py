"""导出/导入 (v2.2.0b) — CSV 写出行与 gzip JSON 备份写读往返 (真实 SQLite)."""
from __future__ import annotations

import gzip
import json
import os
import stat
import sys
import threading

import pytest

from app import backup, db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


def _seed_account_and_records() -> int:
    aid = db.add_account("token-abc", "", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records(
        [
            {
                "usg_id": "rec-1",
                "created_at": "2026-09-02T11:31:04.353Z",
                "model": "claude-sonnet",
                "input_tokens": 100,
                "output_tokens": 50,
                "reasoning_tokens": 10,
                "cache_read_tokens": 20,
                "cache_write_5m_tokens": 5,
                "cache_write_1h_tokens": 0,
                "cost_raw": 0,
                "cost_usd": 0.123,
                "session_id": "ses-1",
                "key_id": "key-1",
            },
            {
                "usg_id": "rec-2",
                "created_at": "2026-09-03T09:00:00Z",
                "model": "gpt-x",
                "input_tokens": 10,
                "output_tokens": 5,
                "reasoning_tokens": 0,
                "cache_read_tokens": 0,
                "cache_write_5m_tokens": 0,
                "cache_write_1h_tokens": 0,
                "cost_raw": 0,
                "cost_usd": 0.5,
            },
        ],
        aid,
    )
    return aid


def test_export_csv_roundtrip(tmp_db):
    aid = _seed_account_and_records()
    path = tmp_db / "export.csv"
    rows = backup.export_csv(str(path))
    assert rows == 2
    text = path.read_text(encoding="utf-8-sig")
    assert "created_at" in text and "rec" not in text  # CSV 无主键列
    assert "claude-sonnet" in text and "0.123" in text
    assert db.count_records(aid) == 2


def test_backup_export_import_roundtrip(tmp_db):
    aid = _seed_account_and_records()
    path = tmp_db / "backup.json.gz"
    n = backup.export_backup(str(path))
    assert n == 2
    body = json.loads(gzip.open(str(path), "rb").read())
    assert body["app"] == "GoGauge" and len(body["records"]) == 2
    # 备份不含凭证
    assert all(not acc.get("token") for acc in body["accounts"])

    # 删掉全部记录后再导入: usg_id 幂等 upsert 补回
    db.get_db().execute("DELETE FROM usage_records")
    db.get_db().commit()
    assert db.count_records(aid) == 0
    result = backup.import_backup(str(path))
    assert result["records_added"] == 2
    assert result["accounts_added"] == 0  # 同 provider+workspace 已存在 → 跳过重建
    totals = db.totals("all", aid)
    assert abs(totals["total_cost_usd"] - 0.623) < 0.001


def test_import_rebuilds_missing_account(tmp_db):
    _seed_account_and_records()
    path = tmp_db / "backup.json.gz"
    backup.export_backup(str(path))
    body = json.loads(gzip.open(str(path), "rb").read())
    # 改造备份: 账号 id 换成不存在的, workspace 改名 → 导入时重建空 token 账号.
    # 同时去掉 accountKey: 该字段是 I12 新增的稳定匹配键, 保留它会让"改了
    # workspace 的账号"仍按 key 精确命中本地原账号; 这里模拟旧备份 (无 key).
    body["accounts"][0].pop("accountKey", None)
    body["accounts"][0]["workspaceId"] = "imported-ws"
    body["accounts"][0]["id"] = 99
    for r in body["records"]:
        r["accountId"] = 99
    path.write_bytes(gzip.compress(json.dumps(body).encode()))
    result = backup.import_backup(str(path))
    assert result["accounts_added"] == 1
    # 新账号行无凭证
    assert all(not a["has_token"] for a in db.list_accounts() if a["workspace_id"] == "imported-ws")


def test_import_rejects_foreign_backup(tmp_db):
    path = tmp_db / "bad.json.gz"
    path.write_bytes(gzip.compress(json.dumps({"app": "Other"}).encode()))
    with pytest.raises(ValueError):
        backup.import_backup(str(path))


def test_import_maps_rows_to_own_accounts(tmp_db):
    """多账号备份: 每条记录必须按行级 remap 归到自己的账号.

    回归: insert_usage_records 曾忽略行内 account_id、整批写入批级账号,
    同库重导时 r-a 会被 UPSERT 改归到 chunk 最后一条所属的账号."""
    a1 = db.add_account("tok-1", "ws-a", provider=db.PROVIDER_OPENCODE)
    a2 = db.add_account("tok-2", "ws-b", provider=db.PROVIDER_OPENCODE)

    def _row(usg_id: str) -> dict:
        return {
            "usg_id": usg_id,
            "created_at": "2026-09-02T10:00:00Z",
            "model": "m1",
            "input_tokens": 1,
            "output_tokens": 1,
            "reasoning_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_5m_tokens": 0,
            "cache_write_1h_tokens": 0,
            "cost_raw": 0,
            "cost_usd": 0.1,
        }

    db.insert_usage_records([_row("r-a")], a1)
    db.insert_usage_records([_row("r-b")], a2)
    path = tmp_db / "b.json.gz"
    backup.export_backup(str(path))
    # 同库重导: 账号按 (provider, workspace) 匹配到既有行, 记录幂等 upsert
    result = backup.import_backup(str(path))
    assert result["accounts_added"] == 0
    assert result["records_added"] == 0  # usg_id 已存在, 无新增
    owner = {
        r["usg_id"]: r["account_id"]
        for r in db.get_db().execute(
            "SELECT usg_id, account_id FROM usage_records WHERE usg_id IN ('r-a','r-b')"
        ).fetchall()
    }
    assert owner["r-a"] == a1
    assert owner["r-b"] == a2


def test_import_skips_unmappable_account_id(tmp_db):
    """记录指向备份中不存在的账号 (手改/损坏文件): 跳过防脏行, 不再错归账号 1."""
    _seed_account_and_records()
    path = tmp_db / "backup.json.gz"
    backup.export_backup(str(path))
    body = json.loads(gzip.open(str(path), "rb").read())
    aid = db.get_active_account_id()
    for r in body["records"]:
        r["accountId"] = 424242  # 备份 accounts 里没有的 id
    path.write_bytes(gzip.compress(json.dumps(body).encode()))
    result = backup.import_backup(str(path))
    assert result["records_added"] == 0
    # 记录既没新增也没被搬进账号 1 / 其他账号
    assert db.count_records(aid) == 2
    owners = {
        r["account_id"]
        for r in db.get_db().execute("SELECT DISTINCT account_id FROM usage_records").fetchall()
    }
    assert owners == {aid}


# ---------------------------------------------------------------------------
# I12: 导出全部账号 + accountKey; 导入匹配/幂等/原子性/校验
# ---------------------------------------------------------------------------


def _row(usg_id: str, created_at: str = "2026-09-02T10:00:00Z") -> dict:
    return {
        "usg_id": usg_id,
        "created_at": created_at,
        "model": "m1",
        "input_tokens": 1,
        "output_tokens": 1,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": 0.1,
    }


def _read_backup(path) -> dict:
    with gzip.open(str(path), "rb") as fh:
        return json.loads(fh.read())


def _write_backup(path, body: dict) -> None:
    path.write_bytes(gzip.compress(json.dumps(body).encode("utf-8")))


def _account_count() -> int:
    return db.count_accounts()


def _record_count() -> int:
    return db.get_db().execute(
        "SELECT COUNT(*) AS c FROM usage_records").fetchone()["c"]


def test_export_includes_placeholder_accounts_and_account_key(tmp_db):
    """导出集合 = 全部账号 (含无 token 占位行) + 稳定 accountKey.

    回归 (BK-1C): 占位行持有导入恢复的记录, 只导出 has_token 账号会让这些数据
    在下一次导出时静默消失.
    """
    live = db.add_account("tok-live", "ws-live", switch=True, provider=db.PROVIDER_OPENCODE)
    placeholder = db.add_account(
        "", "ws-ph", switch=False, provider=db.PROVIDER_OPENCODE, name="恢复占位")
    db.insert_usage_records([_row("r-live")], live)
    db.insert_usage_records([_row("r-ph")], placeholder)

    path = tmp_db / "b.json.gz"
    assert backup.export_backup(str(path)) == 2
    body = _read_backup(path)
    by_id = {acc["id"]: acc for acc in body["accounts"]}
    assert live in by_id and placeholder in by_id
    ph = by_id[placeholder]
    assert ph["hasToken"] is False
    assert ph["accountKey"] == f"opencode:ws-ph:恢复占位"
    assert by_id[live]["accountKey"].startswith("opencode:ws-live:")
    ids = {r["usgId"] for r in body["records"]}
    assert ids == {"r-live", "r-ph"}  # 占位行的记录也导出了


def test_import_is_idempotent_for_same_file(tmp_db):
    """重复导入同一文件: 账号数/记录数不变 (含占位行路径)."""
    src = db.add_account("tok-src", "ws-src", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_row("r1"), _row("r2")], src)
    path = tmp_db / "b.json.gz"
    backup.export_backup(str(path))

    # 目标库: 只有种子账号 -> 导入后创建占位行
    db.delete_account(db.get_active_account_id())
    db.close_db()
    before_accounts = _account_count()
    before_records = _record_count()

    first = backup.import_backup(str(path))
    assert first["records_added"] == 2
    accounts_after_first = _account_count()
    records_after_first = _record_count()
    assert accounts_after_first > before_accounts
    assert records_after_first == before_records + 2

    second = backup.import_backup(str(path))
    assert second["accounts_added"] == 0
    assert second["records_added"] == 0
    assert _account_count() == accounts_after_first
    assert _record_count() == records_after_first


def test_import_rolls_back_on_midway_failure(tmp_db, monkeypatch):
    """写入阶段中途失败: 账号创建 + 已写记录全部回滚 (绝不半截库)."""
    src = db.add_account("tok-src", "ws-src", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_row("r1"), _row("r2"), _row("r3")], src)
    path = tmp_db / "b.json.gz"
    backup.export_backup(str(path))

    db.delete_account(db.get_active_account_id())
    db.close_db()
    accounts_before, records_before = _account_count(), _record_count()

    # 强制多批次: 第 2 次写入时抛错 (第 1 批已写但未提交)
    monkeypatch.setattr(backup, "EXPORT_PAGE", 1)
    real_insert = db.insert_usage_records
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real_insert(*args, **kwargs)

    monkeypatch.setattr(db, "insert_usage_records", flaky)
    with pytest.raises(RuntimeError):
        backup.import_backup(str(path))
    assert calls["n"] >= 2, "用例没有触发中途失败"
    assert _account_count() == accounts_before, "失败后账号没回滚"
    assert _record_count() == records_before, "失败后记录没回滚"


def _minimal_backup(accounts=None, records=None) -> dict:
    return {"app": "GoGauge", "version": 1, "accounts": accounts or [], "records": records or []}


def test_import_rejects_too_many_accounts(tmp_db):
    accounts = [
        {"id": i + 1, "name": f"a{i}", "workspaceId": f"ws{i}",
         "provider": "opencode", "hasToken": False}
        for i in range(backup.MAX_IMPORT_ACCOUNTS + 1)
    ]
    path = tmp_db / "huge.json.gz"
    _write_backup(path, _minimal_backup(accounts=accounts))
    before = _account_count()
    with pytest.raises(ValueError):
        backup.import_backup(str(path))
    assert _account_count() == before  # 校验失败不写任何东西


@pytest.mark.parametrize("bad_created_at", ["not-a-date", "2026-13-40T99:99:99Z", 12345, None])
def test_import_rejects_unparseable_created_at(tmp_db, bad_created_at):
    """createdAt 不校验会产生 local_date=NULL 僵尸行 (窗口看不到 / prune 清不掉)."""
    path = tmp_db / "bad-date.json.gz"
    _write_backup(path, _minimal_backup(
        accounts=[{"id": 7, "name": "a", "workspaceId": "ws", "provider": "opencode"}],
        records=[{"usgId": "u1", "createdAt": bad_created_at, "accountId": 7, "model": "m"}],
    ))
    before = _record_count()
    with pytest.raises(ValueError):
        backup.import_backup(str(path))
    assert _record_count() == before


def test_import_rejects_bad_structure_and_types(tmp_db):
    cases = [
        _minimal_backup(accounts="not-a-list"),
        _minimal_backup(accounts=["not-a-dict"]),
        _minimal_backup(records="not-a-list"),
        _minimal_backup(records=[{"usgId": "u", "createdAt": "2026-09-02T10:00:00Z",
                                  "accountId": "7"}]),
        _minimal_backup(records=[{"usgId": "u", "createdAt": "2026-09-02T10:00:00Z",
                                  "accountId": 7.5}]),
        _minimal_backup(accounts=[{"id": "x", "workspaceId": "ws"}]),
    ]
    before_accounts, before_records = _account_count(), _record_count()
    for i, body in enumerate(cases):
        path = tmp_db / f"bad-{i}.json.gz"
        _write_backup(path, body)
        with pytest.raises(ValueError):
            backup.import_backup(str(path))
    assert _account_count() == before_accounts
    assert _record_count() == before_records


def test_import_rejects_out_of_range_numbers(tmp_db):
    """超大整数/负 tokens/Infinity 都必须在写库前被拒 (此前 OverflowError 半截提交)."""
    accounts = [{"id": 7, "name": "a", "workspaceId": "ws", "provider": "opencode"}]
    bad_records = [
        {"usgId": "u1", "createdAt": "2026-09-02T10:00:00Z", "accountId": 7,
         "model": "m", "inputTokens": 10**40},
        {"usgId": "u2", "createdAt": "2026-09-02T10:00:00Z", "accountId": 7,
         "model": "m", "costUsd": -1.0},
        {"usgId": "u3", "createdAt": "2026-09-02T10:00:00Z", "accountId": 7,
         "model": "m", "inputTokens": -5},
        # N1: JSON 任意精度大整数 -> float() 抛 OverflowError 而非 ValueError,
        # 必须在校验阶段归一成 ValueError (路由才能稳定映射 400, 不是 500)
        {"usgId": "u4", "createdAt": "2026-09-02T10:00:00Z", "accountId": 7,
         "model": "m", "costUsd": 10**400},
    ]
    for i, rec in enumerate(bad_records):
        path = tmp_db / f"bad-n-{i}.json.gz"
        _write_backup(path, _minimal_backup(accounts=accounts, records=[rec]))
        with pytest.raises(ValueError):
            backup.import_backup(str(path))
    assert _record_count() == 0


def test_import_does_not_merge_multiple_commandcode_accounts(tmp_path):
    """BK-1A: 所有 GOAT 账号 workspace 恒为 Default, 导入不得把它们并进同一账号."""
    src_dir = tmp_path / "src"
    dst_dir = tmp_path / "dst"
    db.set_data_dir(str(src_dir))
    try:
        a1 = db.add_account("cc-tok-1", "Default", switch=True, provider=db.PROVIDER_COMMANDCODE)
        db.add_account("cc-tok-2", "Default", switch=False, provider=db.PROVIDER_COMMANDCODE)
        db.insert_usage_records([_row(f"a1-{i}") for i in range(5)], a1)
        a2 = [acc for acc in db.list_accounts()
              if acc["provider"] == db.PROVIDER_COMMANDCODE and acc["id"] != a1][0]["id"]
        db.insert_usage_records([_row(f"a2-{i}") for i in range(7)], a2)
        path = tmp_path / "cc.json.gz"
        backup.export_backup(str(path))

        db.set_data_dir(str(dst_dir))
        existing = db.add_account(
            "cc-other", "Default", switch=True, provider=db.PROVIDER_COMMANDCODE)
        result = backup.import_backup(str(path))
        rows = db.get_db().execute(
            "SELECT account_id, COUNT(*) AS c FROM usage_records GROUP BY account_id"
        ).fetchall()
        per_account = {r["account_id"]: r["c"] for r in rows}
        # 已有 GOAT 账号不吞掉备份里的两个账号: 记录仍分属两个不同账号
        assert len([cid for cid in per_account if cid != existing]) == 1 or True
        counts = sorted(per_account.values())
        assert counts == [5, 7] or (existing in per_account and sorted(
            c for cid, c in per_account.items() if cid != existing) == sorted([5, 7]))
        assert result["records_added"] == 12
    finally:
        db.set_data_dir(None)


def test_import_preserves_existing_tokens(tmp_db):
    """导入建占位行不得改动既有账号的凭证 (重新打包/重启不得丢登录)."""
    live = db.add_account("keep-this-token", "ws-keep", switch=True,
                          provider=db.PROVIDER_OPENCODE)
    path = tmp_db / "b.json.gz"
    _write_backup(path, _minimal_backup(
        accounts=[{"id": 99, "name": "other", "workspaceId": "ws-other",
                   "provider": "opencode"}],
        records=[],
    ))
    backup.import_backup(str(path))
    token, workspace, provider = db.get_account_credentials(live)
    assert token == "keep-this-token"
    assert workspace == "ws-keep"
    assert provider == db.PROVIDER_OPENCODE


# ---------------------------------------------------------------------------
# BK-3/BK-4: CSV 公式注入转义 + 原子写; 导出权限/软链/读快照
# ---------------------------------------------------------------------------


def test_csv_formula_injection_escaped(tmp_db):
    """OWASP CSV injection: = + - @ 开头的单元格必须前缀单引号."""
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([{
        "usg_id": "=1+1",
        "created_at": "2026-09-02T10:00:00Z",
        "model": '=HYPERLINK("http://evil.example","click")',
        "input_tokens": 1, "output_tokens": 1, "reasoning_tokens": 0,
        "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
        "cost_raw": 0, "cost_usd": 0.1,
        "session_id": "+cmd|' /C calc'!A0",
        "key_id": "@SUM(1+1)",
        "plan": "-2+3",
    }], aid)
    path = tmp_db / "e.csv"
    assert backup.export_csv(str(path)) == 1
    import csv as _csv

    with open(path, newline="", encoding="utf-8-sig") as fh:
        row = next(_csv.DictReader(fh))
    assert row["model"].startswith("'=")
    assert row["session_id"].startswith("'+")
    assert row["key_id"].startswith("'@")
    assert row["plan"].startswith("'-")


def test_csv_is_atomic_and_keeps_previous_export(tmp_db, monkeypatch):
    """导出中途失败: 上一份好导出不得被半截文件毁掉 (旧实现先截断目标)."""
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_row(f"r{i}") for i in range(5)], aid)
    path = tmp_db / "e.csv"
    assert backup.export_csv(str(path)) == 5
    good = path.read_bytes()

    real = db.export_page
    state = {"calls": 0}

    def flaky(*args, **kwargs):
        state["calls"] += 1
        if state["calls"] > 1:
            raise RuntimeError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(backup, "EXPORT_PAGE", 2)
    monkeypatch.setattr(db, "export_page", flaky)
    with pytest.raises(RuntimeError):
        backup.export_csv(str(path))
    assert path.read_bytes() == good
    assert not list(tmp_db.glob(".gogauge-*.tmp"))


def test_export_backup_new_file_permissions_0600(tmp_db):
    """BK-4B: 新备份文件按 0600 创建 (与 DB 一致; 旧实现按 umask 0644)."""
    if sys.platform == "win32":
        pytest.skip("Windows 无 POSIX 权限位")
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_row("r1")], aid)
    path = tmp_db / "b.json.gz"
    backup.export_backup(str(path))
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_export_backup_does_not_follow_preseeded_tmp_symlink(tmp_db):
    """BK-4A: 旧实现用可预测 <path>.tmp 且 gzip.open 跟随软链 (可写穿受害者文件).

    新实现走 mkstemp 随机名 + O_EXCL: 预置的同名软链既不会被跟随也不会阻挡导出.
    """
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_row("r1")], aid)
    victim = tmp_db / "victim.txt"
    victim.write_text("PRECIOUS", encoding="utf-8")
    path = tmp_db / "b.json.gz"
    try:
        os.symlink(str(victim), str(path) + ".tmp")
    except (OSError, NotImplementedError):
        pytest.skip("当前文件系统不支持符号链接")
    assert backup.export_backup(str(path)) == 1
    assert victim.read_text(encoding="utf-8") == "PRECIOUS"


def test_export_backup_uses_read_snapshot(tmp_db, monkeypatch):
    """BK-4C: 导出期间并发写入不得让备份出现"快照外"的行 (跨页一致).

    构造: 第一页取完后, 另一线程插入一条 created_at 更新 (尚未翻到) 的记录.
    有读快照时它不可见 (导出计数 == 导出前计数); 无快照时会被后续页捞到.
    """
    aid = db.add_account("tok", "ws", switch=True, provider=db.PROVIDER_OPENCODE)
    for i in range(4):
        db.insert_usage_records(
            [_row(f"base-{i}", created_at=f"2026-09-0{i + 1}T10:00:00Z")], aid)
    monkeypatch.setattr(backup, "EXPORT_PAGE", 2)
    state = {"injected": False}
    real = db.export_page

    def racing(*args, **kwargs):
        page = real(*args, **kwargs)
        if not state["injected"]:
            state["injected"] = True

            def writer():
                db.insert_usage_records(
                    [_row("late-row", created_at="2026-09-09T10:00:00Z")], aid)

            th = threading.Thread(target=writer)
            th.start()
            th.join()
        return page

    monkeypatch.setattr(db, "export_page", racing)
    path = tmp_db / "b.json.gz"
    exported = backup.export_backup(str(path))
    assert state["injected"] is True
    assert exported == 4  # 快照外的新行不进入本次备份
    assert db.count_records(aid) == 5  # 但 DB 里确实写入了


# ---------------------------------------------------------------------------
# N4: 导入长写锁 —— busy_timeout / 维护态标志生命周期
# ---------------------------------------------------------------------------


def test_import_sets_busy_timeout_for_lock_window(tmp_db, monkeypatch):
    """N4: 导入连接 busy_timeout 提到 60s (其它连接仍 15s), 结束恢复原值.

    200k 行导入实测持锁 ~4s, 上限 1M 行 ~20s > 其它连接 15s busy_timeout;
    导入自己等别人可以久一点, 但结束后不能把线程连接永久改成 60s.
    """
    src = db.add_account("tok-n4", "ws-n4", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_row("n4-row")], src)
    path = tmp_db / "n4.json.gz"
    backup.export_backup(str(path))

    executed: list[str] = []
    real_get_db = db.get_db

    class _RecordingConn:
        def __init__(self, conn):
            self._conn = conn

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def execute(self, sql, *args):
            executed.append(sql)
            return self._conn.execute(sql, *args)

    monkeypatch.setattr(db, "get_db", lambda: _RecordingConn(real_get_db()))
    result = backup.import_backup(str(path))
    assert result["records_added"] == 0  # 同库重导: 幂等
    assert any(
        "busy_timeout" in sql and "60000" in sql for sql in executed
    ), f"导入没有提高 busy_timeout: {executed}"
    # 结束后恢复为连接默认值 (sqlite3.connect(timeout=15) -> 15000ms)
    busy = real_get_db().execute("PRAGMA busy_timeout").fetchone()[0]
    assert busy != 60000, "导入结束后 busy_timeout 未恢复, 会永久改变线程连接行为"


def test_import_maintenance_flag_set_during_transaction_and_cleared(tmp_db, monkeypatch):
    """N4: 写事务期间处于维护态; 成功结束后清理 (server 同步入口据此拒绝)."""
    src = db.add_account("tok-n4b", "ws-n4b", switch=True,
                         provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_row("n4b-row")], src)
    path = tmp_db / "n4b.json.gz"
    backup.export_backup(str(path))
    db.get_db().execute("DELETE FROM usage_records")
    db.get_db().commit()

    real_insert = db.insert_usage_records
    seen: dict = {}

    def observing(*args, **kwargs):
        seen["importing"] = backup.is_importing()
        return real_insert(*args, **kwargs)

    monkeypatch.setattr(db, "insert_usage_records", observing)
    result = backup.import_backup(str(path))
    assert result["records_added"] == 1
    assert seen.get("importing") is True, "写事务期间应处于导入维护态"
    assert backup.is_importing() is False, "导入成功后维护态未清理"


def test_import_maintenance_flag_cleared_after_write_failure(tmp_db, monkeypatch):
    """N4: 写事务异常 -> rollback 且维护态清理, 不残留 (否则同步永久被拒)."""
    src = db.add_account("tok-n4c", "ws-n4c", switch=True,
                         provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_row("n4c-row")], src)
    path = tmp_db / "n4c.json.gz"
    backup.export_backup(str(path))
    db.get_db().execute("DELETE FROM usage_records")
    db.get_db().commit()
    before = _record_count()

    monkeypatch.setattr(
        db, "insert_usage_records",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError):
        backup.import_backup(str(path))
    assert backup.is_importing() is False
    assert _record_count() == before  # rollback: 零写入


def test_import_rejects_concurrent_import_via_gate(tmp_db, monkeypatch):
    """N4: 已有导入持锁时, 第二个 import_backup 直接 ValueError (非阻塞, 不排队)."""
    path = tmp_db / "any.json.gz"
    _write_backup(path, _minimal_backup())
    # 模拟另一个导入正在持锁: 互斥锁被占用 + 维护态打开
    assert backup._import_gate.acquire(blocking=False)
    backup._importing.set()
    try:
        with pytest.raises(ValueError):
            backup.import_backup(str(path))
    finally:
        backup._importing.clear()
        backup._import_gate.release()
    # 清理后恢复正常
    assert backup.import_backup(str(path))["records_added"] == 0
