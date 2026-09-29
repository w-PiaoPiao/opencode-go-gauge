"""凭证静态加密管道测试: token_fp 去重 / 迁移回填 / 加密形态读写 / payload 残留清理.

加密基元 (DPAPI/钥匙串) 依赖真实系统环境, 这里用替身验证 db 层的存储与解密管线;
明文路径 (非 frozen) 直接覆盖真实行为.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys

import pytest

from app import db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """独立临时库: 重定向 data_dir (同 test_db_multiuser)."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------


def test_token_fp_stable_and_trimmed():
    assert db._token_fp(" abc ") == hashlib.sha256(b"abc").hexdigest()
    assert db._token_fp("") == ""
    assert db._token_fp("   ") == ""


def test_storage_decode_plaintext_passthrough():
    # 非 frozen (源码运行/测试): 明文原样返回
    assert db._storage_decode(1, "auth=abc") == "auth=abc"
    assert db._storage_decode(1, "") == ""


def test_storage_encode_plaintext_when_not_frozen():
    if db._frozen():
        pytest.skip("打包环境不适用明文回退断言")
    assert db._storage_encode(1, "auth=abc") == "auth=abc"
    assert db._storage_encode(1, "  ") == ""


# ---------------------------------------------------------------------------
# db 层读写
# ---------------------------------------------------------------------------


def test_add_account_sets_fp(tmp_db):
    aid = db.add_account("tok-a", "", switch=True)
    row = db.get_db().execute(
        "SELECT token, token_fp FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == "tok-a"  # 非 frozen: 明文直存
    assert row["token_fp"] == db._token_fp("tok-a")


def test_dedup_by_fp(tmp_db):
    a1 = db.add_account("tok-a", "wrk_1")
    a2 = db.add_account("tok-a", "wrk_2")
    assert a1 == a2


def test_dedup_matches_legacy_row_after_backfill(tmp_db):
    """旧库 (无 token_fp 列) 被新版本进程打开时迁移回填, 新增同 token 账号应命中旧行."""
    aid = db.add_account("tok-legacy", "", switch=False)
    # 模拟旧版本写入的行: 指纹为 NULL (新加列的初始态, 迁移回填的目标)
    db.get_db().execute("UPDATE accounts SET token_fp = NULL WHERE id = ?", (aid,))
    db.get_db().commit()
    db.close_db()
    # 重新打开 = 新进程启动: 重置 schema 就绪标记, 让 _init_schema 重跑回填
    db._schema_init_path = None
    aid2 = db.add_account("tok-legacy", "", switch=True)
    assert aid2 == aid


def test_get_token_decodes(tmp_db):
    aid = db.add_account("tok-a")
    db.set_active_account(aid)
    assert db.get_token() == "tok-a"


def test_keychain_roundtrip(tmp_db, monkeypatch):
    """mac 钥匙串形态: 库内只存 kc: 引用, 读侧经 _keychain_get 解出."""
    if sys.platform != "darwin":
        pytest.skip("钥匙串路径仅 darwin 存在")
    store: dict[int, str] = {}
    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(
        db, "_keychain_set", lambda aid, secret: (store.__setitem__(aid, secret) or True))
    monkeypatch.setattr(db, "_keychain_get", lambda aid: store.get(aid, ""))
    monkeypatch.setattr(db, "_keychain_delete", lambda aid: store.pop(aid, None))

    aid = db.add_account("tok-secret")
    db.set_active_account(aid)
    row = db.get_db().execute(
        "SELECT token, token_fp FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == db._KC_PREFIX  # 库内不含明文
    assert db.get_token() == "tok-secret"  # 读侧从钥匙串解出
    assert row["token_fp"] == db._token_fp("tok-secret")

    db.clear_account()
    assert aid not in store  # 登出清理钥匙串条目
    assert db.get_token() == ""


def test_keychain_failure_falls_back_to_plaintext(tmp_db, monkeypatch):
    """钥匙串写入失败必须回退明文, 不能弄丢凭证."""
    if sys.platform != "darwin":
        pytest.skip("钥匙串路径仅 darwin 存在")
    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(db, "_keychain_set", lambda aid, secret: False)
    aid = db.add_account("tok-plain")
    db.set_active_account(aid)
    row = db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == "tok-plain"
    assert db.get_token() == "tok-plain"


def _win_frozen_dpapi(monkeypatch):
    """模拟 Windows frozen DPAPI 环境 (加解密基元用可逆替身)."""
    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(db, "_dpapi_protect", lambda data: b"blob-" + data)
    monkeypatch.setattr(
        db, "_dpapi_unprotect", lambda blob: blob[len(b"blob-"):])


def _restart_app(tmp_db):
    """模拟进程重启: 关闭连接并重置 schema 就绪标记, 下次访问重跑迁移."""
    db.close_db()
    db._schema_init_path = None


def test_dpapi_v2_token_survives_restart_migration(tmp_db, monkeypatch):
    """Windows frozen: 新凭证存 enc:v2:, 模拟重启 (重跑迁移 7) 后仍解得回.

    回归: DPAPI 修复 (687f204) 换了实现但没换前缀, 修复版新凭证仍写 enc:v1:,
    与旧版垃圾同前缀 —— 迁移 7 每次启动都清 enc:v1:, 结果修复版用户一重启
    所有 DPAPI 凭证被清空 (两账号同时掉登录).
    """
    _win_frozen_dpapi(monkeypatch)
    aid = db.add_account("tok-secret", switch=True)
    row = db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"].startswith("enc:v2:")

    _restart_app(tmp_db)
    assert db.get_token() == "tok-secret"


def test_legacy_dpapi_v1_token_still_purged(tmp_db, monkeypatch):
    """旧版写入的 enc:v1: 垃圾凭证仍在启动迁移中被清空 (迁移 7 原语义)."""
    _win_frozen_dpapi(monkeypatch)
    aid = db.add_account("tok-x", switch=True)
    db.get_db().execute(
        "UPDATE accounts SET token = 'enc:v1:Z2FyYmFnZQ==' WHERE id = ?", (aid,))
    db.get_db().commit()

    _restart_app(tmp_db)
    db.get_db().execute("SELECT 1").fetchone()  # 触发 _init_schema
    row = db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == ""


# ---------------------------------------------------------------------------
# 账号删除的 payload 残留清理
# ---------------------------------------------------------------------------


def test_delete_account_cleans_period_keys(tmp_db):
    aid = db.add_account("tok-x")
    db.record_monthly_reset(aid, "2026-01-01T00:00:00Z")
    db.record_period_bounds(aid, "2026-01-01T00:00:00Z", "2026-01-31T00:00:00Z")
    payload = db._raw_payload(db.get_db())
    assert f"monthly_reset:{aid}" in payload
    assert f"period_start:{aid}" in payload

    db.delete_account(aid)

    payload = db._raw_payload(db.get_db())
    assert f"monthly_reset:{aid}" not in payload
    assert f"period_start:{aid}" not in payload
    assert f"period_end:{aid}" not in payload


def test_migration_backfills_fp_from_legacy_schema(tmp_path, monkeypatch):
    """v2.1.0c 形态旧库 (accounts 无 token_fp 列) 打开时补列并回填指纹."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    conn = sqlite3.connect(str(tmp_path / "gousage.db"))
    conn.executescript(
        """
        CREATE TABLE accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL DEFAULT 'Default',
          workspace_id TEXT NOT NULL DEFAULT 'Default',
          resolved_workspace_id TEXT,
          token TEXT NOT NULL DEFAULT '',
          provider TEXT NOT NULL DEFAULT 'opencode',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        INSERT INTO accounts (name, token, provider, created_at, updated_at)
        VALUES ('L', 'tok-legacy', 'opencode', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z');
        """
    )
    conn.commit()
    conn.close()

    # 打开即触发迁移
    assert db.get_active_account_id() == 1
    row = db.get_db().execute(
        "SELECT token_fp FROM accounts WHERE id = 1").fetchone()
    assert row["token_fp"] == db._token_fp("tok-legacy")
    db.close_db()
