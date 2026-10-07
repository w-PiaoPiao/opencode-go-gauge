"""导出/导入 (v2.2.0b) — CSV 写出行与 gzip JSON 备份写读往返 (真实 SQLite)."""
from __future__ import annotations

import gzip
import json
import sys

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
    # 改造备份: 账号 id 换成不存在的, workspace 改名 → 导入时重建空 token 账号
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
