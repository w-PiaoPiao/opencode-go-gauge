"""usage_records 的记录身份: (account_id, usg_id) 账号内唯一.

回归背景: 主键曾是 usg_id 全局唯一, 而 usg_id 只是 provider 侧记录 id. 两个账号的
id 空间一旦重叠, upsert 的 ON CONFLICT(usg_id) DO UPDATE ... account_id=excluded
会把先同步账号的行改归后同步者 —— 前者用量凭空减少, 后者摊上不属于自己的记录.
"""
import sqlite3

import pytest

from app import db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    db._DB = None
    db._invalidate_cred_cache()
    yield tmp_path
    db.close_db()


def _rec(usg_id, model="m", cost_usd=0.5):
    return {
        "usg_id": usg_id, "created_at": "2026-01-01T00:00:00Z", "model": model, "provider": None,
        "input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 0,
        "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
        "cost_raw": 0, "cost_usd": cost_usd, "key_id": None, "session_id": None, "plan": None,
    }


def _mk_account(name):
    return db.add_account(name, "ws-" + name)


def _owner(usg_id):
    rows = db.get_db().execute(
        "SELECT account_id, model FROM usage_records WHERE usg_id = ?", (usg_id,)
    ).fetchall()
    return sorted((r["account_id"], r["model"]) for r in rows)


def test_same_usg_id_coexists_across_accounts(tmp_db):
    """两个账号拿到同号 usg_id 时各存一行, 互不夺走."""
    a = _mk_account("A")
    b = _mk_account("B")

    assert db.insert_usage_records([_rec("req_XYZ", model="from-A")], a) == 1
    assert db.insert_usage_records([_rec("req_XYZ", model="from-B")], b) == 1

    # 两行都在, 且各自归属正确
    assert _owner("req_XYZ") == sorted([(a, "from-A"), (b, "from-B")])


def test_cross_account_duplicate_does_not_flip_ownership(tmp_db):
    """重复同步同一账号时仍是幂等更新, 且不会把行改归别的账号."""
    a = _mk_account("A")
    b = _mk_account("B")

    db.insert_usage_records([_rec("req_XYZ", model="from-A")], a)
    # 同账号再同步一次: 更新而非新增
    assert db.insert_usage_records([_rec("req_XYZ", model="from-A-v2")], a) == 0
    assert _owner("req_XYZ") == [(a, "from-A-v2")]

    # 另一账号随后同步同号: 新增自己的行, A 的行分毫不动
    assert db.insert_usage_records([_rec("req_XYZ", model="from-B")], b) == 1
    assert _owner("req_XYZ") == sorted([(a, "from-A-v2"), (b, "from-B")])


def test_inserted_count_scoped_per_account(tmp_db):
    """新增数按账号判重: B 侧同号 id 在 B 账号里仍算新增."""
    a = _mk_account("A")
    b = _mk_account("B")

    db.insert_usage_records([_rec("req_1"), _rec("req_2")], a)
    assert db.insert_usage_records([_rec("req_1"), _rec("req_2")], b) == 2


def test_migration_rebuilds_legacy_global_pk(tmp_db):
    """旧库 (usg_id 全局主键) 启动后重建为账号内唯一, 数据无损搬运."""
    path = str(tmp_db / "gousage.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          resolved_workspace_id TEXT,
          token TEXT NOT NULL DEFAULT '',
          provider TEXT NOT NULL DEFAULT 'opencode',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE usage_records (
          usg_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          model TEXT NOT NULL,
          provider TEXT,
          input_tokens INTEGER NOT NULL,
          output_tokens INTEGER NOT NULL,
          reasoning_tokens INTEGER NOT NULL DEFAULT 0,
          cache_read_tokens INTEGER NOT NULL DEFAULT 0,
          cache_write_5m_tokens INTEGER NOT NULL DEFAULT 0,
          cache_write_1h_tokens INTEGER NOT NULL DEFAULT 0,
          cost_raw INTEGER NOT NULL,
          cost_usd REAL NOT NULL,
          key_id TEXT,
          session_id TEXT,
          plan TEXT,
          synced_at TEXT NOT NULL,
          account_id INTEGER NOT NULL DEFAULT 1,
          local_date TEXT
        );
        -- 夹具必须带上真实旧库的索引: 重建表时它们会随旧表一起消失,
        -- 不写在这里就永远测不出"迁移把索引弄丢"这一路 (见下方索引断言)
        CREATE INDEX idx_usage_time ON usage_records(created_at DESC);
        CREATE INDEX idx_usage_account_time ON usage_records(account_id, created_at DESC);
        CREATE INDEX idx_usage_account_localdate ON usage_records(account_id, local_date);
        CREATE INDEX idx_usage_account_model ON usage_records(account_id, model);
        INSERT INTO accounts (id, name, workspace_id, token, created_at, updated_at)
          VALUES (1, 'A', 'ws-A', 'enc:v2:x', '2026-01-01', '2026-01-01'),
                 (2, 'B', 'ws-B', 'enc:v2:y', '2026-01-01', '2026-01-01');
        INSERT INTO usage_records
          (usg_id, created_at, model, input_tokens, output_tokens, cost_raw, cost_usd,
           synced_at, account_id, local_date)
          VALUES ('req_KEEP', '2026-01-01T00:00:00Z', 'legacy', 1, 2, 0, 0.25,
                  '2026-01-01T00:00:00Z', 2, '2026-01-01');
        """
    )
    conn.commit()
    conn.close()

    db._DB = None
    db._invalidate_cred_cache()

    # 旧行原样保留, 归属不变
    assert _owner("req_KEEP") == [(2, "legacy")]

    # 主键已变为账号内唯一: 同号 id 可在两个账号共存
    assert db.insert_usage_records([_rec("req_KEEP", model="A-side")], 1) == 1
    assert _owner("req_KEEP") == sorted([(1, "A-side"), (2, "legacy")])

    # 凭证未被迁移里的 token 清理误伤 (enc:v2 前缀是修复版)
    tokens = {
        r["id"]: r["token"]
        for r in db.get_db().execute("SELECT id, token FROM accounts").fetchall()
    }
    assert tokens == {1: "enc:v2:x", 2: "enc:v2:y"}

    # 重建表不得弄丢旧库的索引: 索引跟随 RENAME 挂在旧表上, 又随 DROP TABLE
    # 一起消失; 迁移 2/6 的补建要到下次启动才生效, 所以必须在迁移里就地重建
    # —— 否则升级后的首个进程一直跑全表扫描.
    indexes = {
        r["name"]
        for r in db.get_db().execute(
            "SELECT name FROM sqlite_master"
            " WHERE type='index' AND tbl_name='usage_records'"
        ).fetchall()
    }
    assert {
        "idx_usage_account_usgid",
        "idx_usage_time",
        "idx_usage_account_time",
        "idx_usage_account_localdate",
        "idx_usage_account_model",
    } <= indexes, f"迁移后缺少索引: {indexes}"
