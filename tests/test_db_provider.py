"""db.py provider 维度测试: schema 迁移 / 账号 CRUD 按 provider 隔离 / 周期记录."""
from __future__ import annotations

import sqlite3

import pytest

from app import db
from app.db import PROVIDER_COMMANDCODE, PROVIDER_OPENCODE


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    db._DB = None
    yield tmp_path
    db.close_db()


def _make_legacy_db(path) -> None:
    """构造旧版 schema (accounts 无 provider 列)."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL DEFAULT 'Default',
          workspace_id TEXT NOT NULL DEFAULT 'Default',
          resolved_workspace_id TEXT,
          token TEXT NOT NULL DEFAULT '',
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
          account_id INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE usage_sync_state (
          account_id INTEGER PRIMARY KEY,
          deepest_page_fetched INTEGER NOT NULL DEFAULT -1
        );
        CREATE TABLE settings (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          payload TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )
    now = "2024-01-01T00:00:00Z"
    conn.execute(
        "INSERT INTO accounts (id, name, workspace_id, token, created_at, updated_at)"
        " VALUES (1, 'legacy-user', 'wrk_abc123', 'auth=secret', ?, ?)",
        (now, now),
    )
    conn.execute("INSERT INTO settings (id, payload, updated_at) VALUES (1, '{}', ?)", (now,))
    conn.commit()
    conn.close()


class TestSchemaMigration:
    def test_legacy_db_gets_provider_column(self, tmp_db):
        # 先写旧库再让 db 连接初始化 (模拟用户升级)
        _make_legacy_db(tmp_db / "gousage.db")
        conn = db.get_db()
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()}
        assert "provider" in cols
        row = conn.execute("SELECT provider FROM accounts WHERE id = 1").fetchone()
        assert row["provider"] == PROVIDER_OPENCODE  # 存量回填 opencode
        rec_cols = {r["name"] for r in conn.execute("PRAGMA table_info(usage_records)").fetchall()}
        assert "provider" in rec_cols

    def test_fresh_db_default_provider(self, tmp_db):
        conn = db.get_db()
        row = conn.execute("SELECT provider FROM accounts WHERE id = 1").fetchone()
        assert row["provider"] == PROVIDER_OPENCODE


class TestAccountCRUD:
    def test_add_and_dedup_by_provider(self, tmp_db):
        a1 = db.add_account("__Secure-commandcode_prod_.session_token=cc1", provider=PROVIDER_COMMANDCODE)
        # 同 provider 同 token 去重
        a2 = db.add_account("__Secure-commandcode_prod_.session_token=cc1", provider=PROVIDER_COMMANDCODE)
        assert a1 == a2
        # 不同 provider 即使 token 相似也各自独立
        o1 = db.add_account("auth=oc1", provider=PROVIDER_OPENCODE)
        assert o1 != a1
        accounts = db.list_accounts()
        assert len(accounts) == 3  # 种子 + cc + oc

    def test_account_dict_has_provider(self, tmp_db):
        db.add_account("__Secure-commandcode_prod_.session_token=cc1", provider=PROVIDER_COMMANDCODE)
        acc = next(a for a in db.list_accounts() if a["provider"] == PROVIDER_COMMANDCODE)
        assert acc["provider"] == PROVIDER_COMMANDCODE

    def test_credentials_return_provider(self, tmp_db):
        aid = db.add_account("__Secure-commandcode_prod_.session_token=cc1", provider=PROVIDER_COMMANDCODE)
        token, hint, provider = db.get_account_credentials(aid)
        assert token == "__Secure-commandcode_prod_.session_token=cc1"
        assert provider == PROVIDER_COMMANDCODE

    def test_credentials_missing_account(self, tmp_db):
        token, hint, provider = db.get_account_credentials(99999)
        assert token == ""
        assert provider == PROVIDER_OPENCODE

    def test_save_token_updates_provider(self, tmp_db):
        aid = db.get_active_account_id()
        db.save_token("newtoken", provider=PROVIDER_COMMANDCODE)
        row = db.get_db().execute(
            "SELECT token, provider FROM accounts WHERE id = ?", (aid,)
        ).fetchone()
        assert row["token"] == "newtoken"
        assert row["provider"] == PROVIDER_COMMANDCODE

    def test_list_by_provider(self, tmp_db):
        db.add_account("__Secure-commandcode_prod_.session_token=cc1", provider=PROVIDER_COMMANDCODE)
        db.add_account("__Secure-commandcode_prod_.session_token=cc2", provider=PROVIDER_COMMANDCODE)
        db.add_account("auth=oc1", provider=PROVIDER_OPENCODE)
        assert len(db.list_accounts_by_provider(PROVIDER_COMMANDCODE)) == 2
        assert len(db.list_accounts_by_provider(PROVIDER_OPENCODE)) == 2  # 种子 + oc1


class TestPeriodBounds:
    def test_record_and_read_period(self, tmp_db):
        db.record_period_bounds(None, "2026-09-02T01:03:43.000Z", "2026-10-02T01:03:43.000Z")
        start = db.monthly_cycle_start()
        assert start == "2026-09-02 01:03:43"

    def test_period_from_ms(self, tmp_db):
        db.record_period_bounds(None, 1788366123616, 1788952323616)
        start = db.monthly_cycle_start()
        assert start is not None

    def test_monthly_reset_fallback_when_no_period(self, tmp_db):
        # 无真实周期时, opencode 的 monthly_reset 回推仍生效
        db.record_monthly_reset(None, "2099-01-01T00:00:00Z")
        start = db.monthly_cycle_start()
        assert start is not None
