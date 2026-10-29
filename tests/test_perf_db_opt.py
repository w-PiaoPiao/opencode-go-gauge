"""数据层性能优化回归守卫 (性能审计集群 A / task-7, D / task-11).

覆盖五类"静默退化" —— 它们都不会报错, 只会让性能或数据悄悄变坏:

1. 新索引缺失/列不全: 漏建 (升级首启走迁移 8 重建分支时最易漏) 或把 11 列
   覆盖索引写成 10 列 (缺 session_id) 都会让 dashboard 查询退回全表扫描;
2. 导出 keyset 分页: 与 offset 分页结果必须逐行一致 (含时间戳并列/末页/空集),
   否则备份静默丢行或重行;
3. 守卫 upsert: 值未变不写 (省 WAL), 但**任一值列真变时必须落库** —— WHERE 漏
   一列就是"该列静默不更新"; charts 的 SET 还必须保留 synced_at;
4. session_stats_page 单遍聚合: total 语义与旧 COUNT(DISTINCT) 完全一致,
   尤其是超出末页导致结果集为空时必须回退一次 COUNT.
5. export_backup 流式写出: 输出必须与旧物化实现逐字段/逐字节一致 (Android 导入
   parity), 峰值内存必须只与 EXPORT_PAGE 有关, 不随全库行数增长.
"""
from __future__ import annotations

import csv
import gc
import gzip
import json
import os
import re
import sqlite3
import time
import tracemalloc
from datetime import datetime, timedelta, timezone

import pytest

from app import backup, db

COVER_INDEX_COLS = [
    "account_id", "local_date", "model",
    "input_tokens", "output_tokens", "reasoning_tokens",
    "cache_read_tokens", "cache_write_5m_tokens", "cache_write_1h_tokens",
    "cost_usd", "session_id",
]

ADMIN_INDEX_COLS = ["account_id", "created_at", "usg_id"]

# usage_charts 的全部值列 (主键 account_id/model/time_bucket 与 synced_at 除外)
CHART_VALUE_COLS = [
    "provider", "requests", "input_cost", "output_cost", "cache_cost", "total_cost",
    "credits_total", "tokens_in", "tokens_out", "tokens_total",
    "cache_read_tokens", "cache_creation_tokens", "local_date",
]

# usage_records 的全部值列 (冲突键 account_id/usg_id 与无读取方的 synced_at 除外)
RECORD_VALUE_COLS = [
    "created_at", "model", "provider", "input_tokens", "output_tokens",
    "reasoning_tokens", "cache_read_tokens", "cache_write_5m_tokens",
    "cache_write_1h_tokens", "cost_raw", "cost_usd", "key_id", "session_id",
    "plan", "local_date",
]

# 逐列改写用的新值 (local_date 由时间列派生, 另有专门用例覆盖)
_CHART_NEW = {
    "provider": "provider-new", "requests": 999, "input_cost": 9.1,
    "output_cost": 9.2, "cache_cost": 9.3, "total_cost": 9.4,
    "credits_total": 9.5, "tokens_in": 991, "tokens_out": 992,
    "tokens_total": 993, "cache_read_tokens": 994, "cache_creation_tokens": 995,
    "local_date": "2030-12-31",
}
_RECORD_NEW = {
    "created_at": "2026-02-02T03:04:05Z", "model": "m-new", "provider": "provider-new",
    "input_tokens": 999, "output_tokens": 998, "reasoning_tokens": 997,
    "cache_read_tokens": 996, "cache_write_5m_tokens": 995, "cache_write_1h_tokens": 994,
    "cost_raw": 993, "cost_usd": 9.75, "key_id": "k-new", "session_id": "s-new",
    "plan": "plan-new", "local_date": "2030-12-31",
}


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


def _account(name="bench", ws=None):
    return db.add_account(f"tok-{name}", ws or f"ws-{name}", provider=db.PROVIDER_OPENCODE)


def _rec(usg_id: str, **over) -> dict:
    rec = {
        "usg_id": usg_id,
        "created_at": "2026-01-01T00:00:00Z",
        "model": "m1",
        "provider": db.PROVIDER_OPENCODE,
        "input_tokens": 10,
        "output_tokens": 5,
        "reasoning_tokens": 1,
        "cache_read_tokens": 2,
        "cache_write_5m_tokens": 3,
        "cache_write_1h_tokens": 4,
        "cost_raw": 100,
        "cost_usd": 0.25,
        "key_id": "k1",
        "session_id": "s1",
        "plan": "pro",
    }
    rec.update(over)
    return rec


def _chart(model="m1", bucket="2026-01-01 10:00:00", **over) -> dict:
    row = {
        "model": model,
        "provider": db.PROVIDER_OPENCODE,
        "time_bucket": bucket,
        "requests": 3,
        "input_cost": 0.1,
        "output_cost": 0.2,
        "cache_cost": 0.05,
        "total_cost": 0.35,
        "credits_total": 1.5,
        "tokens_in": 100,
        "tokens_out": 50,
        "tokens_total": 150,
        "cache_read_tokens": 20,
        "cache_creation_tokens": 10,
    }
    row.update(over)
    return row


def _index_cols(name: str) -> list[str]:
    return [r["name"] for r in db.get_db().execute(f"PRAGMA index_info({name})").fetchall()]


def _all_cols(table: str, where: str, params: tuple) -> dict:
    row = db.get_db().execute(f"SELECT * FROM {table} WHERE {where}", params).fetchone()
    return dict(row) if row is not None else {}


# ---------------------------------------------------------------------------
# 1) 索引: 存在性 + 精确列序 (新库与旧库升级两条路径都要走到)
# ---------------------------------------------------------------------------


def test_new_indexes_present_with_exact_columns(tmp_db):
    """新库首启即建好两个索引, 且覆盖索引必须含 session_id (11 列版)."""
    db.get_db()  # 触发建表/迁移
    assert _index_cols("idx_usage_account_time_usgid") == ADMIN_INDEX_COLS
    # 缺 session_id 的 10 列版本会让 totals_today / today_trend 反而变慢
    assert _index_cols("idx_usage_cover_dash") == COVER_INDEX_COLS


def test_migration_rebuild_recreates_new_indexes(tmp_db):
    """迁移 8 重建表分支必须顺手补建两个新索引.

    索引随 RENAME 挂在旧表上、又随 DROP TABLE 一起消失; 迁移 6 的补建要等下次
    启动才跑, 所以不在重建脚本里补, 升级后的**首个进程**全程全表扫描.
    """
    path = str(tmp_db / "gousage.db")
    conn = sqlite3.connect(path)
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
        CREATE INDEX idx_usage_time ON usage_records(created_at DESC);
        CREATE INDEX idx_usage_account_time ON usage_records(account_id, created_at DESC);
        CREATE INDEX idx_usage_account_localdate ON usage_records(account_id, local_date);
        CREATE INDEX idx_usage_account_model ON usage_records(account_id, model);
        INSERT INTO accounts (id, name, workspace_id, token, created_at, updated_at)
          VALUES (1, 'A', 'ws-A', 'enc:v2:x', '2026-01-01', '2026-01-01');
        INSERT INTO usage_records
          (usg_id, created_at, model, input_tokens, output_tokens, cost_raw, cost_usd,
           synced_at, account_id, local_date)
          VALUES ('keep-1', '2026-01-01T00:00:00Z', 'legacy', 1, 2, 0, 0.25,
                  '2026-01-01T00:00:00Z', 1, '2026-01-01');
        """
    )
    conn.commit()
    conn.close()

    # 首次打开 → 迁移 8 重建表
    pinned = {r["name"] for r in db.get_db().execute(
        "PRAGMA table_info(usage_records)").fetchall()}
    assert "local_date" in pinned
    assert _index_cols("idx_usage_account_time_usgid") == ADMIN_INDEX_COLS
    assert _index_cols("idx_usage_cover_dash") == COVER_INDEX_COLS
    # 重建分支原有的索引也没丢
    names = {
        r["name"]
        for r in db.get_db().execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='usage_records'"
        ).fetchall()
    }
    assert {"idx_usage_time", "idx_usage_account_time",
            "idx_usage_account_localdate", "idx_usage_account_model"} <= names
    # 数据无损
    assert _all_cols("usage_records", "usg_id = 'keep-1'", ())["model"] == "legacy"


# ---------------------------------------------------------------------------
# 2) 导出: keyset 与 offset 逐行一致
# ---------------------------------------------------------------------------


def _seed_tied_records(aid: int, n: int = 250) -> None:
    """大量 created_at 并列的行 —— keyset 游标必须靠 usg_id 打破平局."""
    recs = [
        _rec(
            f"rec-{i:05d}",
            created_at=f"2026-01-0{1 + i // 100}T00:00:{i % 60:02d}Z",
            model=f"m{i % 5}",
            session_id=None if i % 9 == 0 else f"s{i % 40}",
            key_id=f"k{i % 7}",
        )
        for i in range(n)
    ]
    db.insert_usage_records(recs, aid)


def _offset_walk(aid: int, page_size: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = db.export_page(page_size, offset, aid)
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        if len(page) < page_size:
            break
    return rows


def _keyset_walk(aid: int, page_size: int) -> list[dict]:
    rows: list[dict] = []
    after = None
    while True:
        page = db.export_page(page_size, account_id=aid, after=after)
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        after = (page[-1]["created_at"], page[-1]["usg_id"])
    return rows


def test_export_page_keyset_matches_offset(tmp_db):
    aid = _account()
    _seed_tied_records(aid)
    off_rows = _offset_walk(aid, 40)
    ks_rows = _keyset_walk(aid, 40)
    assert len(off_rows) == 250
    assert [r["usg_id"] for r in ks_rows] == [r["usg_id"] for r in off_rows]
    assert ks_rows == off_rows  # 逐字段一致
    # 时间戳严格递增 (usg_id 打破平局): 漏行/重行会直接破坏该性质
    keys = [(r["created_at"], r["usg_id"]) for r in ks_rows]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)


def test_export_page_keyset_boundaries(tmp_db):
    aid = _account()
    _seed_tied_records(aid, n=25)
    rows = _keyset_walk(aid, 10)
    assert len(rows) == 25
    last = (rows[-1]["created_at"], rows[-1]["usg_id"])
    # 游标停在最后一行 → 空集 (page_size 整除 25 时不会自然走到这里)
    assert db.export_page(10, 0, aid, after=last) == []
    # offset 超界 → 空集
    assert db.export_page(10, 10_000, aid) == []
    # 空账号两条路径都返回空集
    empty = _account("empty", "ws-empty")
    assert db.export_page(10, 0, empty) == []
    assert db.export_page(10, 0, empty, after=("2026-01-01T00:00:00Z", "zzz")) == []
    # 每页不足 page_size 时以 len(page) < limit 收尾, 游标推进不再查询
    assert len(db.export_page(10, 0, aid)) == 10
    assert len(db.export_page(1000, 0, aid)) == 25


def test_backup_export_multipage_uses_keyset_without_loss(tmp_db, monkeypatch):
    """缩小页大小强制多页, 验证 backup 导出的行集合与 offset 参考实现一致."""
    monkeypatch.setattr(backup, "EXPORT_PAGE", 7)
    aid = _account()
    _seed_tied_records(aid)
    ref = _offset_walk(aid, 7)
    assert len(ref) == 250

    json_path = tmp_db / "backup.json.gz"
    assert backup.export_backup(str(json_path)) == 250
    body = json.loads(gzip.open(str(json_path), "rb").read())
    assert [r["usgId"] for r in body["records"]] == [r["usg_id"] for r in ref]
    # 记录内容也要一致 (抽样比对整行)
    by_id = {r["usg_id"]: r for r in ref}
    for got in body["records"]:
        want = by_id[got["usgId"]]
        assert got["createdAt"] == want["created_at"]
        assert got["model"] == want["model"]
        assert got["costUsd"] == want["cost_usd"]
        assert got["accountId"] == want["account_id"]

    csv_path = tmp_db / "export.csv"
    assert backup.export_csv(str(csv_path)) == 250
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        got_rows = list(csv.DictReader(fh))
    assert [r["created_at"] for r in got_rows] == [r["created_at"] for r in ref]
    assert [r["model"] for r in got_rows] == [r["model"] for r in ref]


# ---------------------------------------------------------------------------
# 3) usage_records 守卫 upsert
# ---------------------------------------------------------------------------


def test_records_guarded_rewrite_is_field_identical(tmp_db):
    """同值重同步: 行内容 (含 synced_at) 分毫不动, 且不新增."""
    aid = _account()
    rec = _rec("rec-1")
    assert db.insert_usage_records([rec], aid) == 1
    before = _all_cols("usage_records", "usg_id = ?", ("rec-1",))
    assert db.insert_usage_records([rec], aid) == 0
    assert _all_cols("usage_records", "usg_id = ?", ("rec-1",)) == before


def test_records_guarded_rewrite_writes_when_value_changes(tmp_db):
    """值真变时必须落库, 且 synced_at 同步刷新 (SET 不能丢 synced_at)."""
    aid = _account()
    db.insert_usage_records([_rec("rec-1")], aid)
    db.get_db().execute(
        "UPDATE usage_records SET synced_at = '2000-01-01T00:00:00Z' WHERE usg_id = 'rec-1'"
    )
    db.get_db().commit()
    assert db.insert_usage_records([_rec("rec-1", model="m2")], aid) == 0
    after = _all_cols("usage_records", "usg_id = ?", ("rec-1",))
    assert after["model"] == "m2"
    assert after["synced_at"] != "2000-01-01T00:00:00Z"


@pytest.mark.parametrize("col", [c for c in RECORD_VALUE_COLS if c != "local_date"])
def test_records_guard_covers_every_value_column(tmp_db, col):
    """WHERE 漏掉任一值列 → 该列的更新被静默吞掉 (本用例逐个列守住).

    列名来自 RECORD_VALUE_COLS: 新加值列却忘了补新值/补 WHERE, 这里会直接报错.
    """
    new = _RECORD_NEW[col]
    aid = _account(col)
    db.insert_usage_records([_rec("rec-1")], aid)
    db.insert_usage_records([_rec("rec-1", **{col: new})], aid)
    stored = _all_cols("usage_records", "usg_id = ?", ("rec-1",))[col]
    assert stored == new


def test_records_guard_repairs_stale_local_date(tmp_db):
    """local_date 也在守卫比较范围内: 存量行 local_date 为空时同值重同步要补回.

    local_date 由 created_at 派生, 正常同步不会变; 但迁移回填失败的历史行会是
    NULL —— WHERE 漏掉 local_date 的话这类行永远不会被修好 (且完全静默).
    """
    aid = _account()
    db.insert_usage_records([_rec("rec-1")], aid)
    db.get_db().execute("UPDATE usage_records SET local_date = NULL WHERE usg_id = 'rec-1'")
    db.get_db().commit()
    expected = db.get_db().execute(
        "SELECT date(substr(?, 1, 19), 'localtime') AS d", ("2026-01-01T12:00:00Z",)
    ).fetchone()["d"]
    db.insert_usage_records([_rec("rec-1", created_at="2026-01-01T12:00:00Z")], aid)
    stored = _all_cols("usage_records", "usg_id = ?", ("rec-1",))
    assert stored["local_date"] == expected


# ---------------------------------------------------------------------------
# 4) usage_charts 守卫 upsert (含 synced_at 行为)
# ---------------------------------------------------------------------------


def test_charts_guarded_rewrite_keeps_synced_at_and_values(tmp_db):
    """同值重同步: 不写行 → 值列与 synced_at 都保持原样."""
    aid = _account()
    db.insert_usage_charts([_chart()], aid)
    db.get_db().execute("UPDATE usage_charts SET synced_at = '2000-01-01T00:00:00Z'")
    db.get_db().commit()
    before = _all_cols("usage_charts", "model = 'm1'", ())
    db.insert_usage_charts([_chart()], aid)
    assert _all_cols("usage_charts", "model = 'm1'", ()) == before
    assert before["synced_at"] == "2000-01-01T00:00:00Z"


def test_charts_guarded_rewrite_refreshes_synced_at_on_change(tmp_db):
    """任一值列真变时必须写入, 且 synced_at = excluded.synced_at 生效."""
    aid = _account()
    db.insert_usage_charts([_chart()], aid)
    db.get_db().execute("UPDATE usage_charts SET synced_at = '2000-01-01T00:00:00Z'")
    db.get_db().commit()
    db.insert_usage_charts([_chart(tokens_in=777)], aid)
    after = _all_cols("usage_charts", "model = 'm1'", ())
    assert after["tokens_in"] == 777
    # SET 里删掉 synced_at 会让同步时间永久冻结在 2000 年
    assert after["synced_at"] != "2000-01-01T00:00:00Z"


@pytest.mark.parametrize("col", [c for c in CHART_VALUE_COLS if c != "local_date"])
def test_charts_guard_covers_every_value_column(tmp_db, col):
    """13 个值列里任一变化都必须落库 (WHERE 只盖 3 列的陷阱由此挡住).

    列名来自 CHART_VALUE_COLS: 新加值列却忘了补新值/补 WHERE, 这里会直接报错.
    """
    new = _CHART_NEW[col]
    aid = _account(col)
    db.insert_usage_charts([_chart()], aid)
    db.insert_usage_charts([_chart(**{col: new})], aid)
    stored = _all_cols("usage_charts", "model = 'm1'", ())[col]
    assert stored == new


def test_charts_guard_repairs_stale_local_date(tmp_db):
    """local_date 也在守卫比较范围内 (同值重同步要把 NULL 的派生列补回)."""
    aid = _account()
    db.insert_usage_charts([_chart(bucket="2026-01-01 12:00:00")], aid)
    db.get_db().execute("UPDATE usage_charts SET local_date = NULL")
    db.get_db().commit()
    expected = db.get_db().execute(
        "SELECT date(substr(?, 1, 19), 'localtime') AS d", ("2026-01-01 12:00:00",)
    ).fetchone()["d"]
    db.insert_usage_charts([_chart(bucket="2026-01-01 12:00:00")], aid)
    stored = _all_cols("usage_charts", "model = 'm1'", ())
    assert stored["local_date"] == expected


def test_charts_guarded_upsert_keeps_row_identity(tmp_db):
    """守卫不影响 (账号, 模型, 时间桶) 主键语义: 不同桶各成一行."""
    aid = _account()
    db.insert_usage_charts(
        [_chart(bucket="2026-01-01 10:00:00"), _chart(bucket="2026-01-01 11:00:00")], aid
    )
    db.insert_usage_charts([_chart(bucket="2026-01-01 10:00:00", requests=7)], aid)
    rows = db.get_db().execute(
        "SELECT time_bucket, requests FROM usage_charts ORDER BY time_bucket"
    ).fetchall()
    assert [(r["time_bucket"], r["requests"]) for r in rows] == [
        ("2026-01-01 10:00:00", 7), ("2026-01-01 11:00:00", 3)
    ]


# ---------------------------------------------------------------------------
# 5) session_stats_page 单遍聚合 vs 旧 COUNT(DISTINCT)
# ---------------------------------------------------------------------------

_SESSION_KEY = (
    "CASE WHEN session_id IS NOT NULL AND session_id != '' THEN session_id "
    "WHEN key_id IS NOT NULL AND key_id != '' THEN key_id ELSE '' END"
)


def _legacy_total(days, aid) -> int:
    where, params = [], []
    if days:
        where.append("local_date >= date('now', 'localtime', ?)")
        params.append(f"-{days} days")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    where_sql, params = db._account_filter(where_sql, params, aid)
    row = db.get_db().execute(
        f"SELECT COUNT(DISTINCT {_SESSION_KEY}) AS c FROM usage_records {where_sql}", params
    ).fetchone()
    return int(row["c"])


def _legacy_page(page, page_size, days, aid) -> list[dict]:
    where, params = [], []
    if days:
        where.append("local_date >= date('now', 'localtime', ?)")
        params.append(f"-{days} days")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    where_sql, params = db._account_filter(where_sql, params, aid)
    rows = db.get_db().execute(
        f"""SELECT {_SESSION_KEY} AS session_id,
               MAX(key_id) AS key_id,
               COUNT(*) AS request_count,
               SUM(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens) AS total_input_tokens,
               SUM(input_tokens) AS uncached_input_tokens,
               SUM(output_tokens) AS total_output_tokens,
               SUM(reasoning_tokens) AS total_reasoning_tokens,
               SUM(cost_usd) AS total_cost_usd,
               MAX(created_at) AS last_at
        FROM usage_records {where_sql}
        GROUP BY {_SESSION_KEY}
        ORDER BY last_at DESC
        LIMIT ? OFFSET ?""",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return [
        {
            "session_id": r["session_id"],
            "key_id": r["key_id"],
            "request_count": int(r["request_count"]),
            "total_input_tokens": int(r["total_input_tokens"] or 0),
            "uncached_input_tokens": int(r["uncached_input_tokens"] or 0),
            "total_output_tokens": int(r["total_output_tokens"] or 0),
            "total_reasoning_tokens": int(r["total_reasoning_tokens"] or 0),
            "total_cost_usd": round(float(r["total_cost_usd"] or 0), 6),
            "last_at": r["last_at"],
        }
        for r in rows
    ]


def _seed_sessions(aid: int) -> None:
    # 每条记录时间戳递减 1s: 各分组的 MAX(created_at) 互不相同 → ORDER BY last_at
    # DESC 是全序, 两个实现的输出顺序才可比对 (并列时 SQLite 不保证次序).
    now = datetime.now(timezone.utc)
    recs = []
    for i in range(60):
        created = (now - timedelta(seconds=i)).isoformat().replace("+00:00", "Z")
        # 30 个具名会话 + 无 session_id 时按 key_id 拆分 + 两者皆空兜底一行
        if i % 10 == 0:
            recs.append(_rec(f"r-{i:03d}", created_at=created, session_id=None, key_id="", model="m1"))
        elif i % 3 == 0:
            recs.append(_rec(f"r-{i:03d}", created_at=created, session_id=None,
                             key_id=f"k{i % 4}", model=f"m{i % 3}"))
        else:
            recs.append(_rec(f"r-{i:03d}", created_at=created, session_id=f"s{i % 30}",
                             key_id=f"k{i % 4}", model=f"m{i % 3}"))
    # 10 条 2020 年的记录: days 窗口必须真的把老数据排除掉, 两个 total 才不等价
    for i in range(10):
        recs.append(_rec(f"old-{i:03d}", created_at=f"2020-01-01T00:00:{i:02d}Z",
                         session_id=f"old-s{i}", key_id=f"old-k{i}", model="m-old"))
    db.insert_usage_records(recs, aid)


@pytest.mark.parametrize("days", [None, 30])
@pytest.mark.parametrize("page", [1, 2, 3])
def test_session_stats_total_matches_legacy(tmp_db, days, page):
    aid = _account()
    _seed_sessions(aid)
    records, total = db.session_stats_page(page, 10, days, aid)
    assert total == _legacy_total(days, aid)
    assert records == _legacy_page(page, 10, days, aid)


@pytest.mark.parametrize("days", [None, 30])
def test_session_stats_beyond_last_page_total_fallback(tmp_db, days):
    """超出末页 → 单遍聚合拿不到 total, 必须回退 COUNT(DISTINCT).

    回退缺失时前端会把翻页上限算成 0 (或 1), 直接看不到"上一页".
    """
    aid = _account()
    _seed_sessions(aid)
    records, total = db.session_stats_page(9_999, 10, days, aid)
    assert records == []
    assert total == _legacy_total(days, aid)
    assert total > 0


def test_session_stats_empty_db(tmp_db):
    aid = _account()
    assert db.session_stats_page(1, 10, None, aid) == ([], 0)
    assert db.session_stats_page(1, 10, 30, aid) == ([], 0)
    assert db.session_stats_page(5, 10, None, aid) == ([], 0)


def _tied_sessions(aid: int, n: int = 250, per_stamp: int = 50) -> None:
    """n 个会话, 每 per_stamp 个共享同一 MAX(created_at) → 大量并列 last_at.

    批量同步一次写入多条记录时 created_at 会同秒甚至同毫秒, 并列是常态而非边角.
    """
    recs = []
    for i in range(n):
        ts = f"2026-03-{(i // per_stamp) + 1:02d}T10:00:00Z"
        recs.append(_rec(f"tie-{i:04d}", created_at=ts, session_id=f"tie-s{i:05d}",
                         key_id=f"k{i % 9}", model=f"m{i % 4}"))
    db.insert_usage_records(recs, aid)


def _walk_session_pages(aid: int, page_size: int) -> list[str]:
    seen: list[str] = []
    for page in range(1, 500):
        rows, _ = db.session_stats_page(page, page_size, None, aid)
        if not rows:
            break
        seen.extend(r["session_id"] for r in rows)
    return seen


@pytest.mark.parametrize("page_size", [1, 7, 13, 50])
def test_session_stats_tied_last_at_paging_is_exact(tmp_db, page_size):
    """并列 last_at 下的分页: 逐页拼接无重复、无遗漏, 且并列项按次序键确定排序.

    这是单遍化最需要钉住的点 —— 只按 last_at 排序时并列项次序由计划/排序器决定,
    页边界上可能重复或跳过会话 (静默丢会话).
    """
    aid = _account()
    _tied_sessions(aid)
    seen = _walk_session_pages(aid, page_size)
    assert len(seen) == 250
    assert len(set(seen)) == 250  # 无重复
    # 同一页两次调用逐字段一致 (次序确定, 不随排序器漂移)
    for page in (1, 2, 3, 30):
        assert db.session_stats_page(page, page_size, None, aid)[0] == \
            db.session_stats_page(page, page_size, None, aid)[0]
    # 并列 last_at 的组内次序 = ORDER BY 的次序键 session_id ASC
    rows = [
        r for p in range(1, 500)
        for r in db.session_stats_page(p, page_size, None, aid)[0]
    ]
    by_stamp: dict[str, list[str]] = {}
    for r in rows:
        by_stamp.setdefault(r["last_at"], []).append(r["session_id"])
    for stamp, sids in by_stamp.items():
        assert sids == sorted(sids), f"{stamp} 的并列项次序不是 session_id ASC"
    # 并列组之外的 last_at 必须严格递减
    stamps = [r["last_at"] for r in rows]
    assert stamps == sorted(stamps, reverse=True)
    # 不同页大小得到同一绝对序列 (页边界不影响结果)
    assert seen == _walk_session_pages(aid, 7 if page_size != 7 else 5)


def test_session_stats_tied_last_at_total_stable(tmp_db):
    """并列 last_at 下 total 仍等于会话数 (不因并列被重复计数)."""
    aid = _account()
    _tied_sessions(aid)
    for page_size in (7, 50):
        _, total = db.session_stats_page(1, page_size, None, aid)
        assert total == 250
        _, total = db.session_stats_page(9_999, page_size, None, aid)
        assert total == 250


def test_session_stats_paged_sql_orders_by_tiebreak(tmp_db):
    """SQL 层面必须带次序键 session_id: 这是"分页确定序"的唯一硬保证.

    仅靠行为断言不够 —— 排序器恰好稳定时, 去掉 tiebreak 行为断言仍会全绿
    (已用变异测试验证); 而"页边界重复/跳过"的窗口正是无次序键的排序打开的.
    """
    aid = _account()
    _tied_sessions(aid, n=30, per_stamp=30)
    seen_sql: list[str] = []
    conn = db.get_db()
    conn.set_trace_callback(seen_sql.append)
    try:
        db.session_stats_page(1, 10, None, aid)
    finally:
        conn.set_trace_callback(None)
    paged = [
        " ".join(sql.split()) for sql in seen_sql
        if "GROUP BY" in sql and "LIMIT" in sql
    ]
    assert paged, seen_sql
    assert "ORDER BY last_at DESC, session_id ASC" in paged[-1]


def test_session_stats_aggregates_unchanged(tmp_db):
    """聚合口径不变: 会话合计 = 明细合计 (含缓存写入口径)."""
    aid = _account()
    _seed_sessions(aid)
    records, _ = db.session_stats_page(1, 50, None, aid)
    row = db.get_db().execute(
        "SELECT COUNT(*) AS n, SUM(cost_usd) AS cost,"
        " SUM(input_tokens) AS i, SUM(output_tokens) AS o,"
        " SUM(reasoning_tokens) AS r FROM usage_records WHERE account_id = ?",
        (aid,),
    ).fetchone()
    assert sum(r["request_count"] for r in records) == int(row["n"])
    assert abs(sum(r["total_cost_usd"] for r in records) - round(float(row["cost"]), 6)) < 1e-6
    assert sum(r["uncached_input_tokens"] for r in records) == int(row["i"])
    assert sum(r["total_output_tokens"] for r in records) == int(row["o"])
    assert sum(r["total_reasoning_tokens"] for r in records) == int(row["r"])


# ---------------------------------------------------------------------------
# 6) export_backup 流式写出 (与物化实现等价 + 峰值内存不随行数增长)
# ---------------------------------------------------------------------------


def _legacy_export_backup(path: str) -> int:
    """task-11 之前的物化实现 (逐字复制), 作为流式版本的对拍参照.

    参照实现刻意**不复用** backup._record_payload: 复用会让"字段名/顺序被改错"
    这类回归在两边同时发生, 对拍就失去意义.
    """
    # 与 app/backup.py 现行导出形态保持逐字节一致 (P2-2): **全部账号** (含无
    # token 占位行, 它们在导入后可能带着记录且下一次导出不能丢) + accountKey.
    accounts = [
        {
            "id": a["id"],
            "name": a.get("name") or "",
            "workspaceId": a.get("workspace_id") or "",
            "provider": a.get("provider") or db.PROVIDER_OPENCODE,
            "hasToken": bool(a.get("has_token")),
            "accountKey": (
                f"{a.get('provider') or db.PROVIDER_OPENCODE}:"
                f"{a.get('workspace_id') or ''}:{a.get('name') or ''}"
            ),
        }
        for a in db.list_accounts()
    ]
    records: list[dict] = []
    for acc in accounts:
        after: tuple[str, str] | None = None
        while True:
            page = db.export_page(backup.EXPORT_PAGE, account_id=acc["id"], after=after)
            if not page:
                break
            for r in page:
                records.append(
                    {
                        "usgId": r["usg_id"],
                        "createdAt": r["created_at"],
                        "model": r["model"],
                        "provider": r.get("provider"),
                        "inputTokens": r.get("input_tokens", 0),
                        "outputTokens": r.get("output_tokens", 0),
                        "reasoningTokens": r.get("reasoning_tokens", 0),
                        "cacheReadTokens": r.get("cache_read_tokens", 0),
                        "cacheWrite5mTokens": r.get("cache_write_5m_tokens", 0) or 0,
                        "cacheWrite1hTokens": r.get("cache_write_1h_tokens", 0) or 0,
                        "costUsd": r.get("cost_usd", 0.0),
                        "costRaw": r.get("cost_raw", 0) or 0,
                        "keyId": r.get("key_id"),
                        "sessionId": r.get("session_id"),
                        "plan": r.get("plan"),
                        "localDate": r.get("local_date"),
                        "accountId": r.get("account_id", acc["id"]),
                    }
                )
            if len(page) < backup.EXPORT_PAGE:
                break
            after = (page[-1]["created_at"], page[-1]["usg_id"])
    body = {
        "app": "GoGauge",
        "version": 1,
        "exportedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "accounts": accounts,
        "records": records,
    }
    with gzip.open(path, "wb", compresslevel=6) as fh:
        fh.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    return len(records)


_EXPORTED_AT_RE = re.compile(rb'"exportedAt": "[^"]*"')
_EXPORTED_AT_STUB = b'"exportedAt": "T"'


def _read_backup(path) -> bytes:
    with gzip.open(str(path), "rb") as fh:
        return fh.read()


def _assert_same_backup(old_path, new_path) -> None:
    """新旧备份: 标准库可解析 + 深度相等 + 键顺序一致 + 正文逐字节相同."""
    raw_old, raw_new = _read_backup(old_path), _read_backup(new_path)
    old_doc, new_doc = json.loads(raw_old), json.loads(raw_new)
    assert list(new_doc) == list(old_doc) == ["app", "version", "exportedAt", "accounts", "records"]
    assert new_doc["app"] == "GoGauge" and new_doc["version"] == 1
    assert new_doc["exportedAt"] and old_doc["exportedAt"]
    # 每条记录的字段名与顺序 (Android 端按字段名导入; 顺序参与对拍)
    assert len(new_doc["records"]) == len(old_doc["records"])
    for got, want in zip(new_doc["records"], old_doc["records"]):
        assert list(got) == list(want)
    # 除 exportedAt 外深度相等
    old_doc.pop("exportedAt")
    new_doc.pop("exportedAt")
    assert new_doc == old_doc
    # 更强: 解压正文在归一化时间戳后逐字节相同 → 流式拼接与整体 dumps 文本等价
    assert _EXPORTED_AT_RE.sub(_EXPORTED_AT_STUB, raw_new) == _EXPORTED_AT_RE.sub(
        _EXPORTED_AT_STUB, raw_old
    )


def test_export_backup_streaming_matches_materialized(tmp_db, monkeypatch):
    """同一份数据: 流式实现与旧物化实现输出等价 (强制多页 + 时间戳并列)."""
    monkeypatch.setattr(backup, "EXPORT_PAGE", 7)  # 强制多页, 覆盖页间连接符
    aid = _account()
    _seed_tied_records(aid)  # 250 行, 大量并列 created_at
    old_path, new_path = tmp_db / "old.json.gz", tmp_db / "new.json.gz"
    assert _legacy_export_backup(str(old_path)) == 250
    assert backup.export_backup(str(new_path)) == 250
    _assert_same_backup(old_path, new_path)
    assert not (tmp_db / "new.json.gz.tmp").exists()  # 临时文件已原子替换


def test_export_backup_streaming_empty_db(tmp_db):
    """无已登录账号: 骨架与旧实现一致 (records 空数组, 不产生多余逗号)."""
    old_path, new_path = tmp_db / "old.json.gz", tmp_db / "new.json.gz"
    assert _legacy_export_backup(str(old_path)) == 0
    assert backup.export_backup(str(new_path)) == 0
    _assert_same_backup(old_path, new_path)
    assert json.loads(_read_backup(new_path))["records"] == []


def _seed_bulk(aid: int, tag: str, n: int) -> None:
    rows = [
        _rec(
            f"{tag}-{i:06d}",
            created_at=f"2026-04-{(i % 28) + 1:02d}T10:{i % 60:02d}:{(i // 60) % 60:02d}Z",
            model=f"m{i % 12}",
            session_id=f"s{i % 300}",
            key_id=f"k{i % 20}",
        )
        for i in range(n)
    ]
    for start in range(0, n, 2_000):
        db.insert_usage_records(rows[start:start + 2_000], aid)


def _export_peak(path) -> tuple[int, int]:
    """在干净的 tracemalloc 窗口里导出一次, 返回 (记录数, 峰值字节)."""
    db.checkpoint_wal()
    gc.collect()
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        count = backup.export_backup(str(path))
        _cur, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return count, peak


def test_export_backup_memory_does_not_scale_with_rows(tmp_db, monkeypatch):
    """峰值内存由 EXPORT_PAGE 决定, 不随全库行数线性增长.

    物化实现约 1.8KB/行 (2 万行 ~40MB, 20 万行 340MB, window_days=None 的
    100 万行 ~1.8GB); 流式实现峰值只有常数级. 这条用例防止改回"先堆 list
    再整串 dumps".
    """
    monkeypatch.setattr(backup, "EXPORT_PAGE", 500)
    aid = _account()
    _seed_bulk(aid, "a", 2_000)
    n1, peak1 = _export_peak(tmp_db / "small.json.gz")
    _seed_bulk(aid, "b", 20_000)
    n2, peak2 = _export_peak(tmp_db / "big.json.gz")
    assert (n1, n2) == (2_000, 22_000)
    # 11× 数据, 峰值不得随之线性增长 (物化实现这里会到 ~11×)
    assert peak2 < peak1 * 4, f"峰值随行数增长: 2k={peak1}B 22k={peak2}B"
    # 绝对上限: 物化实现在 22k 行约 40MB
    assert peak2 < 16 * 1024 * 1024, f"22k 行峰值 {peak2 / 1048576:.1f}MB 过大"


def test_export_backup_failure_keeps_previous_file_and_no_partial(tmp_db, monkeypatch):
    """中途失败: 不留半截文件, 已存在的旧备份原样保留 (旧实现的失败语义)."""
    monkeypatch.setattr(backup, "EXPORT_PAGE", 7)
    aid = _account()
    _seed_tied_records(aid, n=60)
    path = tmp_db / "backup.json.gz"
    assert backup.export_backup(str(path)) == 60
    good = path.read_bytes()

    real = db.export_page
    state = {"calls": 0}

    def flaky(*args, **kwargs):
        state["calls"] += 1
        if state["calls"] > 1:
            raise RuntimeError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(db, "export_page", flaky)
    with pytest.raises(RuntimeError):
        backup.export_backup(str(path))
    assert state["calls"] >= 2  # 确认是"写到一半才炸"
    assert path.read_bytes() == good  # 旧备份未被破坏
    assert not (tmp_db / "backup.json.gz.tmp").exists()


def test_export_backup_tmp_is_replaced_atomically(tmp_db, monkeypatch):
    """成功路径不留 .tmp, 且覆盖导出得到完整新文件 (返回记录数随之变化)."""
    monkeypatch.setattr(backup, "EXPORT_PAGE", 7)
    aid = _account()
    _seed_tied_records(aid, n=30)
    path = tmp_db / "b.json.gz"
    assert backup.export_backup(str(path)) == 30
    db.insert_usage_records([_rec("extra-1")], aid)
    assert backup.export_backup(str(path)) == 31
    assert not (tmp_db / "b.json.gz.tmp").exists()
    assert len(json.loads(_read_backup(path))["records"]) == 31


def test_export_backup_preserves_existing_file_mode(tmp_db, monkeypatch):
    """覆盖导出沿用既有备份的权限位 (os.replace 按 umask 新建, 无守卫会把 0600 放宽成 0644).

    POSIX 专属: Windows 上 os.chmod 只切只读位, 权限位是合成的 (文件固定报
    0666/0444), 0600 根本无法表达 —— 守约 (app/backup.py 里抄 S_IMODE) 也只会
    抄到合成的 0666, 该断言在 Windows 上不可满足, 不能当成产品缺陷.
    """
    import os
    import stat
    import sys

    if sys.platform == "win32":
        pytest.skip("Windows 无 POSIX 权限位 (os.chmod 只切只读位, stat 报合成 0666/0444), 0600 不可表达")
    monkeypatch.setattr(backup, "EXPORT_PAGE", 7)
    aid = _account()
    _seed_tied_records(aid, n=30)
    path = tmp_db / "b.json.gz"
    assert backup.export_backup(str(path)) == 30
    os.chmod(path, 0o600)
    assert backup.export_backup(str(path)) == 30          # 覆盖导出
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600   # 权限沿用
    assert not (tmp_db / "b.json.gz.tmp").exists()


def test_export_backup_survives_chmod_failure(tmp_db, monkeypatch):
    """权限沿用失败 (PermissionError) 不得影响备份内容 —— 守住 except OSError 分支."""
    import os

    aid = _account()
    _seed_tied_records(aid, n=30)
    path = tmp_db / "b.json.gz"
    with open(path, "wb") as fh:
        fh.write(b"OLD")

    def boom(*a, **k):
        raise PermissionError("injected")

    monkeypatch.setattr(os, "chmod", boom)
    assert backup.export_backup(str(path)) == 30   # 权限沿用失败不影响备份
    monkeypatch.undo()
    assert len(json.loads(_read_backup(path))["records"]) == 30


# ---------------------------------------------------------------------------
# 7) P3-7: 明细页 days 过滤的排序修复 (加 local_date 首键, 免 TEMP B-TREE)
# ---------------------------------------------------------------------------


def test_records_page_days_order_matches_created_at_order(tmp_db):
    """days 过滤下逐页拼接 == 旧排序 (created_at DESC, usg_id DESC) 的行序.

    复用 local_date 索引后输出顺序不变; 若 local_date 与 created_at 派生不一致,
    这里会直接暴露页边界重/漏.
    """
    aid = _account()
    now = datetime.now(timezone.utc)
    recs = [
        _rec(
            f"d-{i:04d}",
            created_at=(now - timedelta(seconds=i * 600)).isoformat().replace("+00:00", "Z"),
            model=f"m{i % 3}",
        )
        for i in range(120)
    ]
    # created_at 大量并列 (批量同步一次插多条是常态): usg_id 是唯一次序键
    tied = (now - timedelta(days=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    recs += [_rec(f"t-{i:03d}", created_at=tied, model="m0") for i in range(30)]
    db.insert_usage_records(recs, aid)

    days = 30
    where = ["local_date >= date('now', 'localtime', ?)"]
    params: list = [f"-{days - 1} days"]
    where_sql, ref_params = db._account_filter("WHERE " + " AND ".join(where), params, aid)
    ref = [
        r["usg_id"]
        for r in db.get_db().execute(
            f"SELECT usg_id FROM usage_records {where_sql}"
            " ORDER BY created_at DESC, usg_id DESC",
            ref_params,
        ).fetchall()
    ]
    got: list[str] = []
    page = 1
    while True:
        rows, total = db.usage_records_page(page, 17, days=days, account_id=aid)
        if not rows:
            break
        got.extend(r["usg_id"] for r in rows)
        page += 1
    assert len(got) == len(set(got)) == len(ref) == total
    assert got == ref

    # SQL 层: 走 (account_id, local_date) 索引顺序, 不再对 8 万行做 TEMP B-TREE
    seen: list[str] = []
    conn = db.get_db()
    conn.set_trace_callback(seen.append)
    try:
        db.usage_records_page(1, 17, days=days, account_id=aid)
    finally:
        conn.set_trace_callback(None)
    sql = next(s for s in seen if "ORDER BY local_date DESC" in s and "LIMIT" in s)
    plan = " ".join(
        str(r["detail"]) for r in db.get_db().execute("EXPLAIN QUERY PLAN " + sql).fetchall()
    )
    assert "idx_usage_account_localdate" in plan, plan
    # 旧实现的 created_at 首键会让整个窗口 (8 万行) 进一个 TEMP B-TREE;
    # 新排序把排序范围收敛到单个 local_date 分组内 ("LAST 2 TERMS"), 代价 O(每天行数).
    assert "TEMP B-TREE FOR ORDER BY" not in plan, plan
    assert "TEMP B-TREE FOR LAST" in plan or "TEMP B-TREE" not in plan, plan


# ---------------------------------------------------------------------------
# 8) P2-8: data_dir() 进程内缓存 / 探针只跑一次 / 失败沿用上次可用路径
# ---------------------------------------------------------------------------


def _reset_data_dir_globals(monkeypatch, monkeypatch_none=True):
    """把 data_dir 的模块级缓存重置到"未解析"状态 (测试内自包含, 不影响其他用例)."""
    import sys

    if monkeypatch_none:
        monkeypatch.setattr(db, "_data_dir_cache", None)
        monkeypatch.setattr(db, "_data_dir_cache_env", None)
    monkeypatch.setattr(db, "_data_dir_override", None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")


def test_data_dir_resolution_is_cached(monkeypatch, tmp_path):
    """Windows frozen 分支的写删探针只在首次解析时跑 (旧实现每次 data_dir 都跑)."""
    import sys

    monkeypatch.delenv("GOUSAGE_DATA", raising=False)
    monkeypatch.setattr(db, "_last_good_data_dir", None)
    _reset_data_dir_globals(monkeypatch)
    exe_dir = tmp_path / "exe"
    exe_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(exe_dir / "GoGauge.exe"))
    calls: list[str] = []
    monkeypatch.setattr(db, "_probe_writable", lambda p: calls.append(p) or True)

    first = db.data_dir()
    second = db.data_dir()
    assert first == second == str(exe_dir / "data")
    assert len(calls) == 1  # 第二次命中进程内缓存, 不再做写删探针


def test_data_dir_probe_failure_keeps_last_good_path(monkeypatch, tmp_path):
    """探针瞬时失败 (磁盘满/杀软锁文件) 沿用上次成功路径, 不静默换到空库."""
    import sys

    monkeypatch.delenv("GOUSAGE_DATA", raising=False)
    good = tmp_path / "known-good" / "data"
    monkeypatch.setattr(db, "_last_good_data_dir", str(good))
    _reset_data_dir_globals(monkeypatch)
    exe_dir = tmp_path / "exe"
    exe_dir.mkdir()
    monkeypatch.setattr(sys, "executable", str(exe_dir / "GoGauge.exe"))

    def failing_probe(_path):
        raise OSError("disk full")

    monkeypatch.setattr(db, "_probe_writable", failing_probe)
    assert db.data_dir() == str(good)  # 不是 LOCALAPPDATA 的空库


def test_set_data_dir_invalidates_data_dir_cache(monkeypatch, tmp_path):
    """set_data_dir 切目录后必须重新解析 (缓存/探针结果不能沿用)."""
    import sys

    monkeypatch.delenv("GOUSAGE_DATA", raising=False)
    _reset_data_dir_globals(monkeypatch)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "GoGauge.exe"))
    monkeypatch.setattr(db, "_probe_writable", lambda p: True)
    default_path = db.data_dir()
    assert default_path == str(tmp_path / "data")

    db.set_data_dir(str(tmp_path / "other"))
    try:
        assert db.data_dir() == str(tmp_path / "other")
        db.set_data_dir(None)
        assert db.data_dir() == default_path
    finally:
        db.set_data_dir(None)


# ---------------------------------------------------------------------------
# 9) P2-5: 数据目录 0700 / DB 文件 0600
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="Windows 无 POSIX 权限位")
def test_data_dir_and_db_file_permissions(tmp_db, monkeypatch):
    """默认解析目录: DB 文件 0600 + 数据目录 0700."""
    import stat

    # data_dir 被 fixture monkeypatch 到 tmp_db, 这里模拟"默认解析目录"分支
    monkeypatch.delenv("GOUSAGE_DATA", raising=False)
    monkeypatch.setattr(db, "_data_dir_override", None)
    db.get_db()
    dir_mode = stat.S_IMODE(os.stat(tmp_db).st_mode)
    db_mode = stat.S_IMODE(os.stat(tmp_db / "gousage.db").st_mode)
    assert dir_mode == 0o700, oct(dir_mode)
    assert db_mode == 0o600, oct(db_mode)


@pytest.mark.skipif(os.name == "nt", reason="Windows 无 POSIX 权限位")
def test_override_data_dir_permissions_are_respected(tmp_path, monkeypatch):
    """N2b: set_data_dir 指定的既有目录不改权限 (DB 文件仍 0600)."""
    import stat

    shared = tmp_path / "shared"
    shared.mkdir()
    os.chmod(shared, 0o755)
    monkeypatch.setattr(db, "data_dir", lambda: str(shared))
    db.set_data_dir(str(shared))
    try:
        db.get_db()
        assert stat.S_IMODE(os.stat(shared).st_mode) == 0o755
        assert stat.S_IMODE(os.stat(shared / "gousage.db").st_mode) == 0o600
    finally:
        db.set_data_dir(None)


@pytest.mark.skipif(os.name == "nt", reason="Windows 无 POSIX 权限位")
def test_env_data_dir_permissions_are_respected(tmp_path, monkeypatch):
    """N2b: GOUSAGE_DATA 指定的既有目录同样不改权限."""
    import stat

    custom = tmp_path / "custom"
    custom.mkdir()
    os.chmod(custom, 0o755)
    monkeypatch.setenv("GOUSAGE_DATA", str(custom))
    monkeypatch.setattr(db, "data_dir", lambda: str(custom))
    monkeypatch.setattr(db, "_data_dir_override", None)
    db.get_db()
    assert stat.S_IMODE(os.stat(custom).st_mode) == 0o755
    assert stat.S_IMODE(os.stat(custom / "gousage.db").st_mode) == 0o600
