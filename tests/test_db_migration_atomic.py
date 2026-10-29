"""schema 迁移的原子性 / 崩溃恢复 / 迁移前备份 / 一次性门控 (P1-2, P2-6).

回归背景 (审查 P1-2):
- 迁移 8/3 用 `executescript` (不包事务) 重建表; 升级进程在 RENAME 之后、数据
  搬完之前被强杀, 下次启动会建出空表而把整份历史留在 `*_legacy` 孤儿表 ——
  应用正常启动、统计全 0、无任何报错.
- 修复: 脚本文本内自带 BEGIN/COMMIT (原子), 异常整体回滚后重抛; 启动时检测
  `*_legacy` 表回灌后 DROP; 迁移前自动备份库文件; 一次性清理用**具名 marker**
  门控 (不能只信 user_version —— 它可能被中间版本写成任意值).
"""
from __future__ import annotations

import glob
import gc
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import db

_NOW = "2026-01-01T00:00:00Z"


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    db._schema_init_path = None
    db._invalidate_payload_cache()
    db._invalidate_cred_cache()
    yield tmp_path
    db.close_db()
    db._schema_init_path = None


def _restart() -> None:
    """模拟进程重启: 关连接 + 清"本进程已初始化"标记, 下次访问重跑 _init_schema."""
    db.close_db()
    db._schema_init_path = None
    db._invalidate_payload_cache()


def _raw_connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def _pk_columns(conn: sqlite3.Connection) -> list[str]:
    return [
        row["name"]
        for row in sorted(
            conn.execute("PRAGMA table_info(usage_records)").fetchall(),
            key=lambda r: r["pk"],
        )
        if row["pk"]
    ]


def _usage_unique_index(conn: sqlite3.Connection) -> list[str]:
    """新形状的主键由唯一索引 idx_usage_account_usgid 表达 (表定义里没有 PK)."""
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_usage_account_usgid'"
    ).fetchone()
    return [sql[0]] if sql and sql[0] else []


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }


def _make_old_db(path) -> None:
    """v2.1 形态旧库: usage_records 主键是全局 usg_id / 无 local_date / 无 token_fp.

    这是真实用户升级前的形状 (迁移 8 会重建主键)。写入一条记录 + 同步状态.
    """
    conn = _raw_connect(path)
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
          id INTEGER PRIMARY KEY CHECK (id = 1),
          last_sync_at TEXT,
          last_sync_status TEXT,
          last_sync_error TEXT,
          last_inserted_count INTEGER NOT NULL DEFAULT 0,
          deepest_page_fetched INTEGER NOT NULL DEFAULT -1,
          total_records INTEGER NOT NULL DEFAULT 0,
          oldest_record_at TEXT,
          newest_record_at TEXT
        );
        CREATE TABLE settings (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          payload TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_usage_time ON usage_records(created_at DESC);
        """
    )
    conn.execute(
        "INSERT INTO accounts (id, name, workspace_id, token, provider, created_at, updated_at)"
        " VALUES (1, 'Old', 'Default', 'kc:', 'opencode', ?, ?)",
        (_NOW, _NOW),
    )
    conn.execute(
        "INSERT INTO usage_records VALUES"
        " ('keep-1', '2026-01-02T10:00:00Z', 'legacy-model', 'opencode', 10, 20, 0, 0, 0, 0,"
        " 0, 0.5, NULL, 's1', NULL, ?, 1)",
        (_NOW,),
    )
    conn.execute(
        "INSERT INTO usage_sync_state VALUES (1, ?, 'ok', NULL, 1, 7, 1, ?, ?)",
        (_NOW, "2026-01-02T10:00:00Z", "2026-01-02T10:00:00Z"),
    )
    conn.execute("INSERT INTO settings VALUES (1, '{\"window_days\": 30}', ?)", (_NOW,))
    conn.commit()
    conn.close()


def _make_orphan_legacy_db(path) -> None:
    """模拟"迁移 8 中途被强杀"的中间态: 新表已建好 (空), 数据全在 legacy 表里."""
    conn = _raw_connect(path)
    conn.executescript(
        """
        CREATE TABLE accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL DEFAULT 'Default',
          workspace_id TEXT NOT NULL DEFAULT 'Default',
          resolved_workspace_id TEXT,
          token TEXT NOT NULL DEFAULT '',
          token_fp TEXT,
          provider TEXT NOT NULL DEFAULT 'opencode',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        -- 新形状 usage_records (迁移已执行到 CREATE TABLE 之后, 数据还没搬)
        CREATE TABLE usage_records (
          usg_id TEXT NOT NULL,
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
        CREATE UNIQUE INDEX idx_usage_account_usgid
          ON usage_records(account_id, usg_id);
        -- 旧形状遗留在 legacy 表 (RENAME 的结果)
        CREATE TABLE usage_records_legacy (
          usg_id TEXT NOT NULL,
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
        CREATE TABLE usage_sync_state (
          account_id INTEGER PRIMARY KEY,
          last_sync_at TEXT,
          last_sync_status TEXT,
          last_sync_error TEXT,
          last_inserted_count INTEGER NOT NULL DEFAULT 0,
          deepest_page_fetched INTEGER NOT NULL DEFAULT -1,
          total_records INTEGER NOT NULL DEFAULT 0,
          oldest_record_at TEXT,
          newest_record_at TEXT
        );
        CREATE TABLE usage_sync_state_legacy (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          last_sync_at TEXT,
          last_sync_status TEXT,
          last_sync_error TEXT,
          last_inserted_count INTEGER NOT NULL DEFAULT 0,
          deepest_page_fetched INTEGER NOT NULL DEFAULT -1,
          total_records INTEGER NOT NULL DEFAULT 0,
          oldest_record_at TEXT,
          newest_record_at TEXT
        );
        CREATE TABLE settings (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          payload TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO accounts (id, name, workspace_id, token, provider, created_at, updated_at)"
        " VALUES (1, 'A', 'Default', 'kc:', 'opencode', ?, ?)",
        (_NOW, _NOW),
    )
    for i in range(3):
        day = i + 1
        conn.execute(
            "INSERT INTO usage_records_legacy VALUES"
            " (?, ? || 'T10:00:00Z', 'recovered-model', 'opencode', 10, 20, 0, 0, 0, 0,"
            " 0, 0.5, NULL, NULL, NULL, ?, 1, ?)",
            (f"recovered-{i}", f"2026-01-0{day}", _NOW, f"2026-01-0{day}"),
        )
    conn.execute(
        "INSERT INTO usage_sync_state_legacy VALUES (1, ?, 'ok', NULL, 3, 42, 3, ?, ?)",
        (_NOW, "2026-01-01T10:00:00Z", "2026-01-03T10:00:00Z"),
    )
    conn.execute("INSERT INTO settings VALUES (1, '{}', ?)", (_NOW,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# 崩溃恢复: legacy 孤儿表回灌后 DROP
# ---------------------------------------------------------------------------


def test_recovers_usage_records_legacy_orphans(tmp_db):
    _make_orphan_legacy_db(tmp_db / "gousage.db")
    conn = db.get_db()
    names = _table_names(conn)
    assert "usage_records_legacy" not in names and "usage_sync_state_legacy" not in names
    # 历史数据回灌后可查, 不再"应用正常启动但统计全 0"
    assert db.totals("all")["request_count"] == 3
    assert db.count_records() == 3
    # 同步状态 (游标) 也回灌: 不需要重新全量拉一遍
    assert db.get_sync_state()["deepest_page_fetched"] == 42
    # 主键已是新形状 (表定义无 PK, 由唯一索引表达)
    assert _pk_columns(conn) == []
    assert _usage_unique_index(conn)


def test_recovery_is_idempotent(tmp_db):
    """回灌 + DROP 后重复初始化不再报错/重复插入."""
    _make_orphan_legacy_db(tmp_db / "gousage.db")
    db.get_db()
    before = db.count_records()
    _restart()
    assert db.count_records() == before == 3
    assert _table_names(db.get_db()).isdisjoint(
        {"usage_records_legacy", "usage_sync_state_legacy"}
    )


# ---------------------------------------------------------------------------
# 迁移原子性: 失败整体回滚, 不留半完成状态
# ---------------------------------------------------------------------------


def _make_old_db_with_conflicting_object(path) -> None:
    """旧库 + 一个与迁移脚本要创建的索引同名的**表**.

    迁移 8 脚本在 RENAME 之后执行 `DROP INDEX IF EXISTS idx_usage_account_usgid`;
    同名对象是表时 DROP INDEX 会报错 —— 制造"RENAME 已发生、数据未搬完"的中途失败.
    """
    _make_old_db(path)
    conn = _raw_connect(path)
    conn.execute("CREATE TABLE idx_usage_account_usgid (x INTEGER)")
    conn.commit()
    conn.close()


def test_failed_migration_rolls_back_entirely(tmp_db):
    """迁移 8 中途失败 → 整体回滚: RENAME 撤销, 旧表结构/数据完好在位, 无 legacy."""
    _make_old_db_with_conflicting_object(tmp_db / "gousage.db")
    with pytest.raises(sqlite3.OperationalError):
        db.get_db()  # 迁移失败必须向上抛 (启动失败可见), 不能静默空库
    db.close_db()
    gc.collect()  # 释放异常回溯里残留的连接引用

    path = tmp_db / "gousage.db"
    conn = _raw_connect(path)
    try:
        # 迁移 8 的事务整体回滚: RENAME 已撤销, 仍是旧主键, 数据一行不少
        assert _pk_columns(conn) == ["usg_id"]
        assert "usage_records_legacy" not in _table_names(conn)
        rows = conn.execute("SELECT usg_id FROM usage_records").fetchall()
        assert {r["usg_id"] for r in rows} == {"keep-1"}
    finally:
        conn.close()

    # 清掉冲突对象后重开: 迁移成功, 数据无损搬运
    conn = _raw_connect(path)
    conn.execute("DROP TABLE idx_usage_account_usgid")
    conn.commit()
    conn.close()
    db._schema_init_path = None
    conn = db.get_db()
    assert _pk_columns(conn) == []
    assert _usage_unique_index(conn)
    assert db.count_records() == 1


# ---------------------------------------------------------------------------
# 迁移前自动备份
# ---------------------------------------------------------------------------


def _backups(tmp_path) -> list[str]:
    return sorted(glob.glob(str(tmp_path / "gousage.db.bak-*")))


def test_backup_is_created_before_migration_and_only_once(tmp_db):
    """旧库升级先备份一份 (可直接打开的完整库); 已迁移完成的库重开不再重复备份."""
    _make_old_db(tmp_db / "gousage.db")
    db.get_db()
    backups = _backups(tmp_db)
    assert len(backups) == 1, backups
    # 备份是迁移前的完整快照: 旧主键 + 旧数据都在
    conn = _raw_connect(backups[0])
    try:
        assert _pk_columns(conn) == ["usg_id"]
        assert conn.execute("SELECT COUNT(*) FROM usage_records").fetchone()[0] == 1
    finally:
        conn.close()

    _restart()
    db.get_db()
    assert len(_backups(tmp_db)) == 1  # 幂等重开不产生第二份


# ---------------------------------------------------------------------------
# 一次性动作的具名 marker 门控 (不依赖 user_version 阈值)
# ---------------------------------------------------------------------------


def _set_user_version(path, version: int) -> None:
    conn = _raw_connect(path)
    conn.execute(f"PRAGMA user_version = {int(version)}")
    conn.commit()
    conn.close()


def test_unknown_larger_user_version_is_not_downgraded(tmp_db):
    """user_version 只向上记录: 更大值 (未来版本/异常写入) 不被覆盖回 8."""
    db.get_db()
    db.close_db()
    gc.collect()
    _set_user_version(tmp_db / "gousage.db", 999)
    _restart()
    db.get_db()
    assert db._db_user_version(db.get_db()) == 999


def test_one_time_cleanup_marker_overrides_user_version(tmp_db):
    """user_version 被写成 8 但没有 marker: 仍需执行一次性清理 (安全方向的判断).

    反面同样成立: marker 已存在时, 即使 user_version=0 也**不**重复清理, 新写入的
    auth= 凭证不会被误清.
    """
    db.get_db()
    conn = db.get_db()
    aid = db.add_account("", "ws", switch=False)
    conn.execute("UPDATE accounts SET token = 'auth=old' WHERE id = ?", (aid,))
    conn.commit()
    db.close_db()
    gc.collect()

    # 1) user_version=8 但 marker 被移除: 视为"未完成一次性动作", 清理会跑
    conn = _raw_connect(tmp_db / "gousage.db")
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    payload.pop(db._ONE_TIME_CLEANUP_MARKER, None)
    conn.execute("UPDATE settings SET payload=? WHERE id=1", (json.dumps(payload),))
    conn.execute("PRAGMA user_version = 8")
    conn.commit()
    conn.close()
    _restart()
    db.get_db()
    assert db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()["token"] == ""

    # 2) 之后新写入的 auth= 形态: marker 已存在, user_version 再被改小也不清
    conn = db.get_db()
    conn.execute("UPDATE accounts SET token = 'auth=Fe26-fresh' WHERE id = ?", (aid,))
    conn.commit()
    db.close_db()
    gc.collect()
    _set_user_version(tmp_db / "gousage.db", 0)
    _restart()
    db.get_db()
    assert db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()["token"] == "auth=Fe26-fresh"


# ---------------------------------------------------------------------------
# 真实库快照 (Lead 提供的两份只读副本) 的兼容性验证
#
# 用最终代码打开**副本**, 断言数据/凭证零改动 + 幂等; 快照不存在时跳过.
# ---------------------------------------------------------------------------

_REAL_FIXTURES = "/tmp/real-fixtures"
_REAL_SNAPSHOTS = {
    "current_uv8": os.path.join(_REAL_FIXTURES, "current_uv8.db"),
    "premigration_uv0": os.path.join(_REAL_FIXTURES, "premigration_uv0.db"),
}


def _snapshot_state(path) -> dict:
    conn = _raw_connect(path)
    try:
        accounts = [
            dict(r)
            for r in conn.execute(
                "SELECT id, name, workspace_id, resolved_workspace_id, token, token_fp,"
                " provider, created_at, updated_at FROM accounts ORDER BY id"
            ).fetchall()
        ]
        settings_row = conn.execute("SELECT payload FROM settings WHERE id = 1").fetchone()
        return {
            "accounts": accounts,
            "records": conn.execute("SELECT COUNT(*) FROM usage_records").fetchone()[0],
            "charts": conn.execute("SELECT COUNT(*) FROM usage_charts").fetchone()[0],
            "settings": json.loads(settings_row[0]) if settings_row else {},
            "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
        }
    finally:
        conn.close()


@pytest.mark.parametrize("snapshot", sorted(_REAL_SNAPSHOTS))
def test_real_snapshot_compatibility(tmp_db, monkeypatch, snapshot):
    src = _REAL_SNAPSHOTS[snapshot]
    if not os.path.exists(src):
        pytest.skip(f"真实库快照不存在: {src}")
    import shutil

    copy_dir = tmp_db / snapshot
    copy_dir.mkdir()
    copy_path = copy_dir / "gousage.db"
    shutil.copy2(src, copy_path)
    # 绝不读真实钥匙串: kc: 形态只验证存储值未被清空, 解密路径用替身
    monkeypatch.setattr(db, "_keychain_get", lambda aid: "secret-from-keychain")
    monkeypatch.setattr(db, "_frozen", lambda: False)

    before = _snapshot_state(copy_path)
    assert before["integrity"] == "ok"

    monkeypatch.setattr(db, "data_dir", lambda: str(copy_dir))
    db._schema_init_path = None
    db._invalidate_payload_cache()
    db._invalidate_cred_cache()
    db.get_db()

    after = _snapshot_state(copy_path)
    assert after["integrity"] == "ok"
    # 账号 (含 token 原字符串 / token_fp / updated_at) 逐字段不变
    assert after["accounts"] == before["accounts"]
    assert after["records"] == before["records"]
    assert after["charts"] == before["charts"]
    # settings 原有键值不变 (一次性 marker 是新增键, 允许出现)
    for key, value in before["settings"].items():
        assert after["settings"][key] == value, key

    # kc: 账号的凭据读取路径不因迁移失败
    for acc in after["accounts"]:
        if acc["token"] == db._KC_PREFIX:
            token, _hint, _provider = db.get_account_credentials(acc["id"])
            assert token == "secret-from-keychain"

    # 幂等: 再初始化一次, 数据/账号/设置键值仍不变
    _restart()
    db.get_db()
    again = _snapshot_state(copy_path)
    assert again["accounts"] == before["accounts"]
    assert again["records"] == before["records"]
    assert again["charts"] == before["charts"]
    for key, value in before["settings"].items():
        assert again["settings"][key] == value, key
