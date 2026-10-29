"""created_at 时区归一化 / local_date 派生 / 系统时区变更重算 (P2-3, F4/F5).

回归背景:
- `local_date` / 峰谷档位都按"前 19 字符是 UTC"派生, 而 commandcode 曾原样保留
  tz-aware ISO 串 (`...+08:00`) → 再 +8h, 跨零点时 local_date 错一天、峰/谷误判;
- 不可解析的 created_at 会产出 `local_date=NULL` 的僵尸行 (所有窗口不可见且
  prune 永不清理);
- 系统时区变更后旧行 local_date 不重算 → "今日"统计偏一天.

测试环境 TZ 由 tests/conftest.py 固定为 Asia/Shanghai, 但断言尽量用 SQLite 自身
的 date(...,'localtime') 推期望值, 不写死时区.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from app import db

BJ = timezone(timedelta(hours=8))


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
    db.close_db()
    db._schema_init_path = None
    db._invalidate_payload_cache()


def _rec(usg_id: str, created_at: str, model: str = "m", cost: float = 0.01) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": created_at,
        "model": model,
        "input_tokens": 10,
        "output_tokens": 5,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": cost,
        "session_id": "s1",
    }


def _stored(usg_id: str) -> dict:
    row = db.get_db().execute(
        "SELECT created_at, local_date FROM usage_records WHERE usg_id = ?", (usg_id,)
    ).fetchone()
    return dict(row) if row else {}


def _local_date_of(created_at: str) -> str:
    """期望的 local_date: 与写入 SQL 同一口径 (SQLite localtime)."""
    return db.get_db().execute(
        "SELECT date(substr(?, 1, 19), 'localtime') AS d", (created_at,)
    ).fetchone()["d"]


# ---------------------------------------------------------------------------
# 纯函数: _normalize_created_at / _normalize_time_bucket
# ---------------------------------------------------------------------------


class TestNormalizeCreatedAt:
    @pytest.mark.parametrize(
        ("raw", "expect"),
        [
            # 带偏移 -> 转 UTC-Z
            ("2026-10-12T10:00:00+08:00", "2026-10-12T02:00:00Z"),
            ("2026-10-12T10:00:00.123+08:00", "2026-10-12T02:00:00.123000Z"),
            ("2026-10-11T20:30:00-05:00", "2026-10-12T01:30:00Z"),
            # 已是 UTC: 原文保持不变 (避免存量格式/keyset 排序无谓漂移)
            ("2026-10-12T10:00:00Z", "2026-10-12T10:00:00Z"),
            ("2026-10-12T10:00:00+00:00", "2026-10-12T10:00:00+00:00"),
            ("2026-10-12T10:00:00+0000", "2026-10-12T10:00:00+0000"),
            ("2026-10-12T10:00:00.123456Z", "2026-10-12T10:00:00.123456Z"),
            # 无时区 = 既定 UTC 口径; 空格分隔/纯日期也保持
            ("2026-10-12 10:00:00", "2026-10-12 10:00:00"),
            ("2026-01-02", "2026-01-02"),
            # 非 ISO 但可解析的旧格式 -> 归一化
            ("2026/01/02 03:04:05", "2026-01-02T03:04:05Z"),
            # 非法 -> None (入口丢弃)
            ("yesterday", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalize(self, raw, expect):
        assert db._normalize_created_at(raw) == expect

    def test_datetime_input(self):
        aware = datetime(2026, 10, 12, 10, 0, tzinfo=BJ)
        assert db._normalize_created_at(aware) == "2026-10-12T02:00:00Z"
        naive = datetime(2026, 10, 12, 10, 0)
        assert db._normalize_created_at(naive) == "2026-10-12T10:00:00Z"


class TestNormalizeTimeBucket:
    def test_bucket_forms(self):
        assert db._normalize_time_bucket("2026-10-12 10:00:00") == "2026-10-12 10:00:00"
        assert db._normalize_time_bucket("2026-10-12T10:00:00+08:00") == "2026-10-12 02:00:00"
        assert db._normalize_time_bucket("2026-10-12T10:00:00Z") == "2026-10-12 10:00:00"
        assert db._normalize_time_bucket("garbage") is None
        assert db._normalize_time_bucket("") is None


# ---------------------------------------------------------------------------
# 入库归一化: 偏移时间戳 -> created_at UTC / local_date / 峰谷档位
# ---------------------------------------------------------------------------


def test_offset_timestamp_is_normalized(tmp_db):
    db.insert_usage_records([_rec("u-offset", "2026-10-12T10:00:00+08:00")])
    stored = _stored("u-offset")
    assert stored["created_at"] == "2026-10-12T02:00:00Z"
    assert stored["local_date"] == _local_date_of("2026-10-12T02:00:00Z")


def test_offset_timestamp_local_date_does_not_shift_day(tmp_db):
    """-05:00 的 12:00 实例: 上海已是次日凌晨 —— 旧实现会把它记成当天."""
    db.insert_usage_records([_rec("u-cross", "2026-10-12T12:00:00-05:00")])
    stored = _stored("u-cross")
    assert stored["created_at"] == "2026-10-12T17:00:00Z"
    expected = _local_date_of("2026-10-12T17:00:00Z")
    assert stored["local_date"] == expected
    # 直接验证与"错误口径"不同 (证明本用例能抓住回归): 旧实现是把前 19 字符当 UTC
    buggy = _local_date_of("2026-10-12T12:00:00Z")
    assert stored["local_date"] == expected
    if expected != buggy:
        assert stored["local_date"] != buggy


def test_offset_timestamp_peak_tier_matches_utc_instant(tmp_db):
    """北京 10-12(周一) 10:00 = UTC 02:00 属高峰; 偏移串若未归一化会被误判成谷."""
    db.insert_usage_records(
        [_rec("u-peak", "2026-10-12T10:00:00+08:00", model="deepseek-v4.1-flash")]
    )
    rows = db.model_stats("all", peak_split=True)
    by_label = {r["model"]: r for r in rows}
    assert by_label["deepseek-v4.1-flash 峰"]["request_count"] == 1
    assert "deepseek-v4.1-flash 谷" not in by_label


def test_invalid_created_at_rows_are_dropped(tmp_db):
    """不可解析时间戳在入口丢弃: 不产生 local_date=NULL 的僵尸行 (F5)."""
    inserted = db.insert_usage_records(
        [
            _rec("u-ok", "2026-10-12T10:00:00Z"),
            _rec("u-bad", "yesterday"),
            _rec("u-bad2", ""),
        ]
    )
    assert inserted == 1
    assert db.count_records() == 1
    leftovers = db.get_db().execute(
        "SELECT COUNT(*) FROM usage_records WHERE local_date IS NULL"
    ).fetchone()[0]
    assert leftovers == 0
    # 时间戳合法的行仍可被窗口统计到
    assert db.totals("all")["request_count"] == 1


def test_invalid_chart_bucket_dropped(tmp_db):
    assert db.insert_usage_charts(
        [
            {"model": "goat", "time_bucket": "2026-10-12 10:00:00", "requests": 1},
            {"model": "goat", "time_bucket": "not-a-time", "requests": 1},
        ],
        db.get_active_account_id(),
    ) == 1
    rows = db.get_db().execute("SELECT time_bucket FROM usage_charts").fetchall()
    assert [r["time_bucket"] for r in rows] == ["2026-10-12 10:00:00"]


def test_chart_offset_bucket_normalized(tmp_db):
    aid = db.get_active_account_id()
    db.insert_usage_charts(
        [{"model": "goat", "time_bucket": "2026-10-12T10:00:00+08:00", "requests": 3}], aid
    )
    row = db.get_db().execute(
        "SELECT time_bucket, local_date FROM usage_charts"
    ).fetchone()
    assert row["time_bucket"] == "2026-10-12 02:00:00"
    assert row["local_date"] == _local_date_of("2026-10-12 02:00:00")


# ---------------------------------------------------------------------------
# 迁移 6 回填条件放宽: 10 字符短格式也要自愈 (F5)
# ---------------------------------------------------------------------------


def test_backfill_repairs_short_format_rows(tmp_db):
    db.get_db()  # 建库
    conn = db.get_db()
    conn.execute(
        "INSERT INTO usage_records (usg_id, created_at, model, provider, input_tokens,"
        " output_tokens, reasoning_tokens, cache_read_tokens, cache_write_5m_tokens,"
        " cache_write_1h_tokens, cost_raw, cost_usd, key_id, session_id, plan, synced_at,"
        " account_id, local_date) VALUES ('short', '2026-01-02', 'm', 'opencode', 1, 1, 0,"
        " 0, 0, 0, 0, 0.0, NULL, NULL, NULL, '2026-01-02T00:00:00Z', ?, NULL)",
        (db.get_active_account_id(),),
    )
    conn.commit()
    _restart()  # 重跑迁移 (仅回填 local_date IS NULL 的行)
    db.get_db()
    row = db.get_db().execute(
        "SELECT local_date FROM usage_records WHERE usg_id = 'short'"
    ).fetchone()
    assert row["local_date"] == _local_date_of("2026-01-02")


# ---------------------------------------------------------------------------
# 系统时区变更检测与重算
# ---------------------------------------------------------------------------


def test_tz_change_triggers_local_date_recompute(tmp_db):
    """注入"时区标识已变化"状态: 同步模式重算两表 local_date, 并更新标识."""
    db.insert_usage_records([_rec("u1", "2026-10-12T02:00:00Z")])
    aid = db.get_active_account_id()
    db.insert_usage_charts(
        [{"model": "goat", "time_bucket": "2026-10-12 02:00:00", "requests": 1}], aid
    )
    conn = db.get_db()
    # 人为制造"旧时区派生"的 local_date + 旧时区标识
    conn.execute("UPDATE usage_records SET local_date = '1999-01-01'")
    conn.execute("UPDATE usage_charts SET local_date = '1999-01-01'")
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    payload["local_date_tz"] = "INVALID-OFFSET"
    conn.execute("UPDATE settings SET payload = ? WHERE id = 1", (json.dumps(payload),))
    conn.commit()
    db._invalidate_payload_cache()

    changed = db._check_local_date_tz(conn, background=False)
    assert changed is True
    assert conn.execute("SELECT local_date FROM usage_records").fetchone()[0] == _local_date_of(
        "2026-10-12T02:00:00Z"
    )
    assert conn.execute("SELECT local_date FROM usage_charts").fetchone()[0] == _local_date_of(
        "2026-10-12 02:00:00"
    )
    # 标识已更新为当前偏移; 再次检查不再重算 (幂等)
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == db._local_date_tz_id()
    db._invalidate_payload_cache()
    assert db._check_local_date_tz(conn, background=False) is False


def test_tz_marker_missing_but_rows_consistent_only_marks(tmp_db):
    """老库升级 (marker 缺失) 且 local_date 已与当前时区一致: 只补 marker, 0 写 (N2)."""
    db.insert_usage_records([_rec("u1", "2026-10-12T02:00:00Z")])
    conn = db.get_db()
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    payload.pop("local_date_tz", None)
    conn.execute("UPDATE settings SET payload = ? WHERE id = 1", (json.dumps(payload),))
    conn.commit()
    db._invalidate_payload_cache()

    before = conn.execute("SELECT total_changes()").fetchone()[0]
    assert db._check_local_date_tz(conn, background=False) is False
    after = conn.execute("SELECT total_changes()").fetchone()[0]
    assert after - before <= 1  # 最多只写 settings 里的 marker, 不重写数据行
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == db._local_date_tz_id()


def test_tz_marker_missing_with_stale_rows_recomputes(tmp_db):
    """老库升级 (marker 缺失) 但旧行是别的时区派生的: 必须重算并补 marker.

    旧实现把"marker 缺失"一律当成"首次运行, 无需重算", 跨时区迁移的存量库会
    永久错位; 新逻辑先 COUNT 再决定 (N1/N3).
    """
    db.insert_usage_records([_rec("u1", "2026-10-12T02:00:00Z")])
    conn = db.get_db()
    conn.execute("UPDATE usage_records SET local_date = '1999-01-01'")
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    payload.pop("local_date_tz", None)
    conn.execute("UPDATE settings SET payload = ? WHERE id = 1", (json.dumps(payload),))
    conn.commit()
    db._invalidate_payload_cache()

    assert db._check_local_date_tz(conn, background=False) is True
    assert db._count_local_date_mismatch(conn) == 0
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == db._local_date_tz_id()


# ---------------------------------------------------------------------------
# N1/N3: marker 语义 = 最后一次**成功完成**重算的时区; 中途中断下次启动必须重试
# ---------------------------------------------------------------------------


def _set_tz_marker(marker: str, drop: bool = False) -> None:
    import json as _json

    conn = db.get_db()
    payload = _json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    if drop:
        payload.pop("local_date_tz", None)
    else:
        payload["local_date_tz"] = marker
    conn.execute("UPDATE settings SET payload = ? WHERE id = 1", (_json.dumps(payload),))
    conn.commit()
    db._invalidate_payload_cache()


def test_interrupted_recompute_is_retried_after_restart(tmp_db):
    """模拟"重算改完一批就被 os._exit 强杀": marker 仍旧值 → 重启后继续收敛 (N1).

    复现路径: 时区变更 → 后台重算开始 → 进程被杀. 旧实现重算前就写了 marker,
    重启后误以为已完成, 剩余旧行永久错一天. 新实现 marker 只在全部收敛后写,
    所以重启看到 marker != 当前时区, 自动重试.
    """
    # 6000 行 > 默认批大小 2000, 保证多批; 先制造"旧时区派生"的 local_date
    records = [
        _rec(f"u-{i}", (datetime(2026, 9, 1) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        for i in range(6000)
    ]
    db.insert_usage_records(records)
    conn = db.get_db()
    conn.execute("UPDATE usage_records SET local_date = '1999-01-01'")
    conn.commit()
    # 模拟被强杀前：第一批 2000 行已被重算修正, marker 仍是旧时区 (NOT 当前偏移)
    good = _local_date_of("2026-09-01T00:00:00Z")
    rows = conn.execute("SELECT rowid FROM usage_records ORDER BY rowid LIMIT 2000").fetchall()
    conn.executemany(
        "UPDATE usage_records SET local_date = ? WHERE rowid = ?",
        [(good, r["rowid"]) for r in rows],
    )
    conn.commit()
    _set_tz_marker("OLDTZ")
    assert db._count_local_date_mismatch(conn) > 0  # 仍有未重算完的行
    db.close_db()
    db._schema_init_path = None
    db._invalidate_payload_cache()

    # 重启 (等价 _init_schema 里的检查): marker != 当前时区 → 同步重算到收敛
    conn = db.get_db()
    assert db._check_local_date_tz(conn, background=False) is True
    assert db._count_local_date_mismatch(conn) == 0
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == db._local_date_tz_id()
    # 收敛后再检查是快路径
    assert db._check_local_date_tz(conn, background=False) is False


def test_marker_old_but_rows_current_recompute_is_noop(tmp_db):
    """反向场景: marker 是旧时区但数据其实已经是当前时区 → 重算 0 写并更新 marker."""
    db.insert_usage_records([_rec("u1", "2026-10-12T02:00:00Z")])
    conn = db.get_db()
    _set_tz_marker("OLDTZ")
    assert db._count_local_date_mismatch(conn) == 0
    before = conn.execute("SELECT total_changes()").fetchone()[0]
    assert db._check_local_date_tz(conn, background=False) is True
    # 守卫 UPDATE 不写任何数据行 (N2: 不因时区切换就全表重写); 仅 settings marker 1 行
    assert conn.execute("SELECT total_changes()").fetchone()[0] - before == 1
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == db._local_date_tz_id()


def test_recompute_guard_only_touches_mismatched_rows(tmp_db):
    """N2: 重算只更新 local_date 不一致的行; 全一致时 0 写 (无 WAL 放大)."""
    db.insert_usage_records(
        [_rec(f"u-{i}", f"2026-10-{10 + i:02d}T02:00:00Z") for i in range(5)]
    )
    conn = db.get_db()
    assert db._count_local_date_mismatch(conn) == 0
    before = conn.execute("SELECT total_changes()").fetchone()[0]
    assert db._recompute_local_dates(conn) == 0
    assert conn.execute("SELECT total_changes()").fetchone()[0] == before

    conn.execute("UPDATE usage_records SET local_date = '1999-01-01' WHERE usg_id IN ('u-0','u-1')")
    conn.commit()
    assert db._count_local_date_mismatch(conn) == 2
    updated = db._recompute_local_dates(conn)
    assert updated == 2
    assert db._count_local_date_mismatch(conn) == 0


def test_recompute_with_unparseable_timestamp_converges_to_null(tmp_db):
    """无法解析 created_at 的行: 重算后 local_date 收敛为 NULL, 不会无限重试."""
    db.get_db()
    conn = db.get_db()
    conn.execute(
        "INSERT INTO usage_records (usg_id, created_at, model, provider, input_tokens,"
        " output_tokens, reasoning_tokens, cache_read_tokens, cache_write_5m_tokens,"
        " cache_write_1h_tokens, cost_raw, cost_usd, key_id, session_id, plan, synced_at,"
        " account_id, local_date) VALUES ('bad', 'garbage', 'm', 'opencode', 1, 1, 0,"
        " 0, 0, 0, 0, 0.0, NULL, NULL, NULL, '2026-01-01T00:00:00Z', ?, '1999-01-01')",
        (db.get_active_account_id(),),
    )
    conn.commit()
    assert db._recompute_local_dates(conn) == 1
    assert db._count_local_date_mismatch(conn) == 0
    assert conn.execute(
        "SELECT local_date FROM usage_records WHERE usg_id = 'bad'"
    ).fetchone()[0] is None


# ---------------------------------------------------------------------------
# N5: 不可解析时间戳不再静默丢弃 (每次调用汇总一条 WARNING)
# ---------------------------------------------------------------------------


def test_invalid_created_at_emits_single_warning(tmp_db, caplog):
    """跳过非法行时汇总一条 WARNING: 同步链路"ok 但少数据"可被发现, 不逐行刷屏."""
    with caplog.at_level("WARNING", logger="app.db"):
        inserted = db.insert_usage_records(
            [
                _rec("ok-1", "2026-10-12T10:00:00Z"),
                _rec("bad-1", "yesterday"),
                _rec("bad-2", ""),
            ]
        )
    assert inserted == 1
    warnings = [
        r for r in caplog.records if "created_at 无法解析" in r.getMessage()
    ]
    assert len(warnings) == 1  # 汇总一条, 不是每行一条
    message = warnings[0].getMessage()
    assert "2 条" in message
    assert "yesterday" in message  # 带样例
    assert "格式可能已变化" not in message  # 本批有成功新增, 不误导


def test_all_invalid_batch_warns_upstream_format_hint(tmp_db, caplog):
    """整批 0 新增且全是非法时间戳: warning 明示"上游时间戳格式可能变化"."""
    with caplog.at_level("WARNING", logger="app.db"):
        assert db.insert_usage_records([_rec("bad", "x" * 200)]) == 0
    messages = [
        r.getMessage() for r in caplog.records if "created_at 无法解析" in r.getMessage()
    ]
    assert len(messages) == 1
    message = messages[0]
    assert "1 条" in message and "0 新增" in message and "格式可能已变化" in message
    # 样例截断到 40 字符, 避免日志里出现整串异常数据
    assert "x" * 40 in message and "x" * 41 not in message


def test_background_worker_marks_only_after_convergence(tmp_db):
    """后台线程路径: 重算收敛后自己写 marker (用独立连接) (N1)."""
    db.insert_usage_records([_rec("u1", "2026-10-12T02:00:00Z")])
    conn = db.get_db()
    conn.execute("UPDATE usage_records SET local_date = '1999-01-01'")
    conn.commit()
    _set_tz_marker("OLDTZ")
    db._recompute_local_dates_worker()  # 同步执行后台线程入口
    conn = db.get_db()
    assert db._count_local_date_mismatch(conn) == 0
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == db._local_date_tz_id()


def test_marker_not_updated_when_recompute_not_converged(tmp_db, monkeypatch):
    """未收敛时**不得**更新 marker, 否则重启会误判"已重算"而不再重试 (N1/N3 核心)."""
    db.insert_usage_records([_rec("u1", "2026-10-12T02:00:00Z")])
    conn = db.get_db()
    conn.execute("UPDATE usage_records SET local_date = '1999-01-01'")
    conn.commit()
    _set_tz_marker("OLDTZ")
    monkeypatch.setattr(db, "_count_local_date_mismatch", lambda _conn: 5)
    assert db._recompute_and_mark(conn) is False
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == "OLDTZ"  # 保留旧 marker, 下次启动会重试


def test_os_exit_mid_recompute_is_retried_and_converges(tmp_db):
    """真·崩溃收敛证据 (N1/N3): 重算改完一批即被 os._exit 强杀 → 重启继续并收敛.

    子进程模拟真实被杀路径 (SIGKILL/os._exit 不会执行任何 finally/提交 marker),
    父进程等价"下次启动": 看到 marker 仍是旧时区 → 继续重算到 0 mismatch → 才写
    marker; 再下一次启动走快路径不再重算.
    """
    import subprocess
    import sys
    import textwrap

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    records = [
        _rec(f"u-{i}", (datetime(2026, 9, 1) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        for i in range(6000)
    ]
    db.insert_usage_records(records)
    conn = db.get_db()
    conn.execute("UPDATE usage_records SET local_date = '1999-01-01'")
    conn.commit()
    _set_tz_marker("OLDTZ")
    db.close_db()
    db._schema_init_path = None

    script = textwrap.dedent(
        f"""
        import os, sys
        sys.path.insert(0, {root!r})
        from app import db
        db.set_data_dir({str(tmp_db)!r})
        # 阻止 _init_schema 的自动重算, 让本脚本自己控制"被杀时刻"
        real_check = db._check_local_date_tz
        db._check_local_date_tz = lambda conn, background=True: False
        conn = db.get_db()

        def interrupted(conn, batch_size=2000):
            conn.execute(
                "UPDATE usage_records SET local_date = date(substr(created_at,1,19),'localtime')"
                " WHERE rowid <= 2000"
                " AND local_date IS NOT date(substr(created_at,1,19),'localtime')"
            )
            conn.commit()
            os._exit(9)  # 重算中途被强杀: marker 还没来得及更新

        db._recompute_local_dates = interrupted
        db._check_local_date_tz = real_check
        db._check_local_date_tz(conn, background=False)
        os._exit(0)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=root, capture_output=True, timeout=60
    )
    assert proc.returncode == 9, proc.stderr.decode("utf-8", "replace")[-800:]

    db._schema_init_path = None
    db._invalidate_payload_cache()
    conn = db.get_db()
    # 被杀后: 只改了一部分, marker 仍是旧值 (旧实现在重算前就写 marker, 这里会误判完成)
    assert db._count_local_date_mismatch(conn) > 0
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == "OLDTZ"

    # 下次启动: marker != 当前时区 → 继续重算, 全收敛后才写 marker
    assert db._check_local_date_tz(conn, background=False) is True
    assert db._count_local_date_mismatch(conn) == 0
    payload = json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])
    assert payload["local_date_tz"] == db._local_date_tz_id()

    # 再下一次启动: 快路径, 不再重算
    db.close_db()
    db._schema_init_path = None
    db._invalidate_payload_cache()
    conn = db.get_db()
    assert db._check_local_date_tz(conn, background=False) is False
