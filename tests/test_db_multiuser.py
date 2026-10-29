"""db.py 多账号数据层测试: 存量迁移 / 账号 CRUD / 隔离查询 / 级联删除."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """独立临时库: 重定向 data_dir 并重置模块级连接."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    # 真实复位: 不存在 db._DB (历史误写的死属性); 换库要重新走建表/迁移 + 清缓存
    db._schema_init_path = None
    db._invalidate_payload_cache()
    db._invalidate_cred_cache()  # 进程级凭证缓存跨测试共享, 换库必须清
    yield tmp_path
    db.close_db()
    db._schema_init_path = None


def _rec(usg_id, created="2026-01-01T00:00:00Z", model="m", inp=10, outp=20, cost_usd=0.5):
    return {
        "usg_id": usg_id, "created_at": created, "model": model, "provider": None,
        "input_tokens": inp, "output_tokens": outp, "reasoning_tokens": 0,
        "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
        "cost_raw": 0, "cost_usd": cost_usd, "key_id": None, "session_id": None, "plan": None,
    }


LEGACY_DDL = """
CREATE TABLE account (
  id INTEGER PRIMARY KEY CHECK (id = 1),
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
  synced_at TEXT NOT NULL
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
"""


def _make_legacy_db(path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(LEGACY_DDL)
    now = "2024-01-01T00:00:00Z"
    conn.execute(
        "INSERT INTO account VALUES (1,'Old','wrk_old',NULL,'tok-legacy',?,?)", (now, now)
    )
    conn.execute(
        "INSERT INTO usage_records VALUES"
        " ('usg_a','2024-01-02T10:00:00Z','m1',NULL,10,20,0,0,0,0,0,0.5,'k','s','plan','2024-01-02T11:00:00Z')"
    )
    conn.execute(
        "INSERT INTO usage_records VALUES"
        " ('usg_b','2024-01-03T10:00:00Z','m2',NULL,30,40,0,0,0,0,0,0.7,NULL,NULL,NULL,'2024-01-03T11:00:00Z')"
    )
    conn.execute(
        "INSERT INTO usage_sync_state VALUES"
        " (1,'2024-01-03T11:00:00Z','ok',NULL,2,7,2,'2024-01-02T10:00:00Z','2024-01-03T10:00:00Z')"
    )
    conn.execute("INSERT INTO settings VALUES (1,'{\"window_days\": 30}',?)", (now,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# 全新安装
# ---------------------------------------------------------------------------


def test_fresh_seed(tmp_db):
    assert db.count_accounts() == 1
    assert db.get_active_account_id() == 1
    acc = db.get_account()
    assert acc["name"] == "Default" and not acc["has_token"]
    assert db.get_token() == ""


# ---------------------------------------------------------------------------
# 存量迁移
# ---------------------------------------------------------------------------


def test_legacy_migration_full(tmp_db):
    _make_legacy_db(tmp_db / "gousage.db")
    db.get_db()  # 首次连接触发迁移
    # 断言结果
    accs = db.list_accounts()
    assert len(accs) == 1 and accs[0]["id"] == 1
    assert accs[0]["name"] == "Old" and accs[0]["workspace_id"] == "wrk_old"
    assert accs[0]["has_token"] and db.get_token() == "tok-legacy"
    # 旧表已删除
    conn = db.get_db()
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "account" not in names and "usage_sync_state_legacy" not in names
    assert "accounts" in names
    # 用量记录自动归属 id=1 且可查
    records, total = db.usage_records_page(page=1, page_size=10)
    assert total == 2 and all(r["usg_id"] in ("usg_a", "usg_b") for r in records)
    # 同步状态无损搬运
    st = db.get_sync_state()
    assert st["deepest_page_fetched"] == 7 and st["total_records"] == 2
    # settings 白名单键保留
    assert db.get_settings()["window_days"] == 30


def test_legacy_migration_idempotent_reopen(tmp_db):
    _make_legacy_db(tmp_db / "gousage.db")
    db.get_db()
    db.close_db()
    db.get_db()  # 二次打开不应重复迁移/报错
    assert db.count_accounts() == 1 and db.get_token() == "tok-legacy"


# ---------------------------------------------------------------------------
# 账号 CRUD
# ---------------------------------------------------------------------------


def test_add_and_dedup_by_token(tmp_db):
    a = db.add_account("tA", "ws-a")            # 种子行是空 token, tA 是新行
    b_same = db.add_account("tA", "ws-b")       # 相同 token -> 去重为同一账号
    assert a == b_same
    assert db.count_accounts() == 2             # 种子 + 1 新增
    row = next(x for x in db.list_accounts() if x["id"] == a)
    assert row["workspace_id"] == "ws-b"


def test_switch_persists_across_reopen(tmp_db):
    aid = db.add_account("tX", "ws-x")
    assert db.set_active_account(aid) is True
    assert db.set_active_account(9999) is False
    db.close_db()
    assert db.get_active_account_id() == aid


def test_active_prefers_logged_in(tmp_db):
    """存储的活跃账号若未登录, 应自动让位给最小的已登录账号 (启动默认落在可用账号)."""
    a = db.add_account("tA", "ws-a")            # id2, 激活
    db.add_account("tB", "ws-b")                # id3
    assert db.set_active_account(1) is True     # 手动指向无 token 的种子行
    assert db.get_active_account_id() == a      # 让位给最小的已登录账号


def test_rename_clamp_strip(tmp_db):
    aid = db.add_account("tR", "ws-r")
    assert db.rename_account(aid, "  张三  ") is True
    assert next(x for x in db.list_accounts() if x["id"] == aid)["name"] == "张三"
    long_name = "x" * 80
    assert db.rename_account(aid, long_name) is True
    assert len(next(x for x in db.list_accounts() if x["id"] == aid)["name"]) == 50
    assert db.rename_account(aid, "   ") is False


def test_save_token_targets_active_only(tmp_db):
    a = db.add_account("tA", "ws-a")
    b = db.add_account("tB", "ws-b")            # add 默认 switch -> 活跃=b
    conn = db.get_db()
    conn.execute("UPDATE usage_sync_state SET deepest_page_fetched = 9 WHERE account_id = ?", (a,))
    conn.commit()
    db.save_token("tB-new", "ws-b2")            # 只应作用于活跃账号 b
    assert db.get_token() == "tB-new"
    rows = {r["id"]: r["token"] for r in conn.execute("SELECT id, token FROM accounts")}
    assert rows[a] == "tA" and rows[b] == "tB-new"
    sa = db.get_sync_state(a)
    assert sa["deepest_page_fetched"] == 9      # a 的游标不受影响
    assert db.get_sync_state(b)["deepest_page_fetched"] == -1  # b 游标被重置


# ---------------------------------------------------------------------------
# 数据隔离与级联删除
# ---------------------------------------------------------------------------


def test_query_isolation_between_accounts(tmp_db):
    a = db.add_account("tA", "ws-a")
    b = db.add_account("tB", "ws-b")
    db.insert_usage_records([_rec("a1", inp=100)], account_id=a)
    db.insert_usage_records([_rec("b1", inp=200), _rec("b2", inp=300)], account_id=b)
    ta = db.totals(period="all", account_id=a)
    tb = db.totals(period="all", account_id=b)
    assert ta["request_count"] == 1 and tb["request_count"] == 2
    assert ta["total_input_tokens"] == 100 and tb["total_input_tokens"] == 500  # 含缓存口径
    db.set_active_account(b)
    assert db.totals(period="all")["request_count"] == 2        # 默认走活跃账号
    assert db.list_models(account_id=a) == ["m"]


def test_delete_cascades_and_fallback(tmp_db):
    a = db.add_account("tA", "ws-a")
    b = db.add_account("tB", "ws-b")                            # 活跃=b
    db.insert_usage_records([_rec(f"a{i}") for i in range(3)], account_id=a)
    db.insert_usage_records([_rec(f"b{i}") for i in range(2)], account_id=b)
    remaining = db.delete_account(b)
    assert remaining == 2                       # 剩余: 种子行 + a
    assert db.totals(period="all", account_id=b)["request_count"] == 0
    assert db.totals(period="all", account_id=a)["request_count"] == 3
    assert db.get_active_account_id() == a      # 活跃让位给已登录账号 (而非无 token 的种子行)
    st = db.get_sync_state(b)
    assert st == {}


def test_delete_last_account_safe(tmp_db):
    seed = db.get_active_account_id()
    db.delete_account(seed)
    assert db.count_accounts() == 0
    assert db.get_active_account_id() == 0
    assert db.get_token() == ""
    assert db.totals(period="all")["request_count"] == 0         # 空集不崩溃
    assert db.count_logged_in_accounts() == 0


def test_clear_account_scoped_to_active(tmp_db):
    a = db.add_account("tA", "ws-a")
    b = db.add_account("tB", "ws-b")
    db.insert_usage_records([_rec("a1")], account_id=a)
    db.insert_usage_records([_rec("b1")], account_id=b)
    db.clear_account()                                           # 清活跃账号 b
    assert db.totals(period="all", account_id=b)["request_count"] == 0
    assert db.totals(period="all", account_id=a)["request_count"] == 1
    assert next(x for x in db.list_accounts() if x["id"] == b)["has_token"] is False
    assert next(x for x in db.list_accounts() if x["id"] == a)["has_token"] is True
    assert db.count_logged_in_accounts() == 1


def test_insert_dedup_counts(tmp_db):
    batch = [_rec("u1"), _rec("u2")]
    first = db.insert_usage_records(batch)
    second = db.insert_usage_records(batch)
    assert first == 2 and second == 0
    assert db.totals(period="all")["request_count"] == 2


# ---------------------------------------------------------------------------
# settings payload 共存 (key_names / active_account_id 不被覆盖)
# ---------------------------------------------------------------------------


def test_settings_roundtrip_preserves_extras(tmp_db):
    aid = db.add_account("tS", "ws-s")
    db.save_key_names({"k1": "名字"})
    db.save_settings({"sync_interval_sec": 60})
    # 回归守卫: save_settings 不得清掉同 payload 里的 key_names / active_account_id
    assert db.get_key_names() == {"k1": "名字"}
    assert db.get_settings()["sync_interval_sec"] == 60
    assert db.get_active_account_id() == aid
    # chart_animation 默认关闭 (弱机优先), bool 值可持久化
    assert db.get_settings()["chart_animation"] is False
    db.save_settings({"chart_animation": True})
    assert db.get_settings()["chart_animation"] is True


def test_settings_window_days_all(tmp_db):
    # 回归: 前端选 "全部" 发 window_days=null, 外层 "None=未提供" 守卫曾把它拦下,
    # 导致范围永远停在旧值 (UI 上按钮不移动)
    assert db.save_settings({"window_days": 90})["window_days"] == 90
    assert db.save_settings({"window_days": None})["window_days"] is None
    assert db.get_settings()["window_days"] is None
    # 数字范围与越界钳制不受影响
    assert db.save_settings({"window_days": 99999})["window_days"] == 3650


def test_payload_cache_read_write_consistency(tmp_db):
    """payload 读缓存: 常规读写路径 (_write_payload) 必须立即互见;
    绕开它的直改库只有显式失效后才可见 (直改库是测试/外部工具的越界行为)."""
    db.save_key_names({"k1": "n1"})
    assert db.get_key_names() == {"k1": "n1"}
    conn = db.get_db()
    conn.execute(
        "UPDATE settings SET payload = ? WHERE id = 1",
        ('{"key_names": {"k2": "n2"}}',),
    )
    conn.commit()
    assert db.get_key_names() == {"k1": "n1"}  # 缓存命中 (直改库对读侧不可见)
    db._invalidate_payload_cache()
    assert db.get_key_names() == {"k2": "n2"}  # 失效后重读拿到库内新值
    db.save_key_names({"k3": "n3"})            # 写路径继续正常工作
    assert db.get_key_names() == {"k3": "n3"}


# ---------------------------------------------------------------------------
# 「本月」= 当前月度重置周期 (最近激活的 $10 付费期间) 筛选
# ---------------------------------------------------------------------------


def _iso_utc(days_offset: int) -> str:
    """相对当前 UTC 时间偏移 N 天的时间; 正=过去, 负=未来."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_offset)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _assert_cycle_start(start: str, expect_days_ago: int) -> None:
    dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    delta = abs((datetime.now(timezone.utc) - dt).total_seconds() - expect_days_ago * 86400)
    assert delta < 3600  # 容差 1 小时, 吸收执行耗时


def test_month_range_future_reset(tmp_db):
    """reset 在未来: 周期起点 = 下次重置 - 30 天, 只统计周期内记录."""
    db.insert_usage_records([_rec("u-in", created=_iso_utc(2)), _rec("u-out", created=_iso_utc(10))])
    db.record_monthly_reset(None, _iso_utc(-25))  # 下次重置在 25 天后
    assert db.totals("month")["request_count"] == 1
    _assert_cycle_start(db.monthly_cycle_start(), 5)


def test_month_range_past_reset(tmp_db):
    """reset 已过去 (重置发生而配额未刷新): 周期起点 = 该重置时刻."""
    db.insert_usage_records([_rec("u-in", created=_iso_utc(5)), _rec("u-out", created=_iso_utc(12))])
    db.record_monthly_reset(None, _iso_utc(10))  # 重置发生在 10 天前
    assert db.totals("month")["request_count"] == 1
    _assert_cycle_start(db.monthly_cycle_start(), 10)


def test_month_range_fallback_30d(tmp_db):
    """无月度重置记录 (配额从未拉到): 回退为滚动 30 天, 与 30d 口径一致."""
    db.insert_usage_records([_rec("u-in", created=_iso_utc(20)), _rec("u-out", created=_iso_utc(40))])
    assert db.totals("month")["request_count"] == db.totals("30d")["request_count"] == 1


def test_month_range_real_period_not_empty(tmp_db):
    """真实周期 (Go access.startsAt/endsAt, 31 天自然月) 下「本周期」筛选必须非空.

    回归: 只靠「下次重置 - 30 天」推算时, 起点落在未来 (今晨 01:01 → 明天 01:01),
    local_date >= 未来日期 把当天全部记录滤掉, 页面筛出 0 条.
    """
    import json as _json

    db.insert_usage_records([_rec("u-today", created=_iso_utc(0)), _rec("u-out", created=_iso_utc(40))])
    # 直改库注入真实周期: 起点 12 小时前 (今晨), 终点 31 天后
    conn = db.get_db()
    payload = _json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()["payload"])
    payload["period_start:1"] = (datetime.now(timezone.utc) - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    payload["period_end:1"] = (datetime.now(timezone.utc) + timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
    payload["monthly_reset:1"] = _iso_utc(-31)  # 存量旧值: 单靠它回推给不出起点
    conn.execute("UPDATE settings SET payload=? WHERE id=1", (_json.dumps(payload),))
    conn.commit()
    db._invalidate_payload_cache()
    assert db.monthly_cycle_start() is not None
    assert db.totals("month")["request_count"] == 1


def test_month_range_reset_beyond_30d_not_empty(tmp_db):
    """无真实周期且重置在 31 天后: 回退滚动 30 天, 而非未来起点导致的空集."""
    db.insert_usage_records([_rec("u-today", created=_iso_utc(0)), _rec("u-out", created=_iso_utc(40))])
    db.record_monthly_reset(None, _iso_utc(-31))  # 下次重置在 31 天后 (自然月)
    assert db.monthly_cycle_start() is None
    assert db.totals("month")["request_count"] == 1


def test_month_range_period_without_end_falls_back(tmp_db):
    """有周期起点但终点缺失/非法 (手改库等异常数据): 无法顺延过期周期,
    回退 None 走 30 天滚动口径, 避免把上个周期拉进「本月」窗口."""
    import json as _json

    db.insert_usage_records([_rec("u-old", created=_iso_utc(40)), _rec("u-new", created=_iso_utc(5))])
    # record_period_bounds 要求起止同时有效; 这里直改库构造 "只有 start" 的状态
    conn = db.get_db()
    payload = _json.loads(conn.execute("SELECT payload FROM settings WHERE id=1").fetchone()["payload"])
    payload["period_start:1"] = _iso_utc(40)
    payload.pop("period_end:1", None)
    conn.execute("UPDATE settings SET payload=? WHERE id=1", (_json.dumps(payload),))
    conn.commit()
    db._invalidate_payload_cache()  # 绕开 _write_payload 的直改库必须手动失效缓存
    assert db.monthly_cycle_start() is None
    assert db.totals("month")["request_count"] == db.totals("30d")["request_count"] == 1


def test_monthly_reset_per_account(tmp_db):
    """重置时间按账号隔离存储, 周期起点跟随活跃账号."""
    db.record_monthly_reset(None, _iso_utc(-25))  # 种子账号 (id=1)
    other = db.add_account("tM", "ws-m")          # add 默认 switch -> 活跃为 other
    assert db.monthly_cycle_start() is None       # 新账号尚无配额记录
    db.record_monthly_reset(other, _iso_utc(-25))
    _assert_cycle_start(db.monthly_cycle_start(), 5)
    db.set_active_account(1)
    _assert_cycle_start(db.monthly_cycle_start(), 5)


# ---------------------------------------------------------------------------
# 每日聚合: 无记录的天补 0 (折线图数据源不得缺天跳线)
# ---------------------------------------------------------------------------


def _iso_utc_noon(days_offset: int) -> str:
    """本地「今天 - N 天」中午 12 点的 UTC ISO 串.

    用本地时区中午构造, 避免 UTC/本地日期边界翻转干扰 daily_stats 的
    按本地日期分组断言.
    """
    local = (datetime.now().astimezone() - timedelta(days=days_offset)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_daily_stats_fills_zero_days(tmp_db):
    """有记录的日子取真实聚合值, 无记录的日子全部补 0, 日期严格连续."""
    today = datetime.now().astimezone().date()
    db.insert_usage_records(
        [
            _rec("u-today", created=_iso_utc_noon(0), inp=100, outp=50, cost_usd=1.5),
            _rec("u-3d", created=_iso_utc_noon(3), inp=10, outp=20, cost_usd=0.5),
        ]
    )
    stats = db.daily_stats(7)
    # 恰好 7 个点 = [今天-6, 今天] (I10: 与前端「7 日」文案/totals("7d") 同源)
    assert len(stats) == 7
    dates = [s["date"] for s in stats]
    assert dates[0] == (today - timedelta(days=6)).isoformat()
    assert dates[-1] == today.isoformat()
    # 日期严格连续无重复
    assert dates == sorted(set(dates))
    assert all(
        datetime.strptime(a, "%Y-%m-%d").date() + timedelta(days=1)
        == datetime.strptime(b, "%Y-%m-%d").date()
        for a, b in zip(dates, dates[1:])
    )
    by_date = {s["date"]: s for s in stats}
    # 有记录的两天: 数值正确 (u-today 落在今天, u-3d 落在今天-3)
    assert by_date[today.isoformat()]["request_count"] == 1
    assert by_date[today.isoformat()]["total_input_tokens"] == 100
    assert by_date[today.isoformat()]["total_output_tokens"] == 50
    assert by_date[today.isoformat()]["total_cost_usd"] == 1.5
    assert by_date[(today - timedelta(days=3)).isoformat()]["request_count"] == 1
    # 无记录的天: 全字段为 0
    for d in set(dates) - {today.isoformat(), (today - timedelta(days=3)).isoformat()}:
        s = by_date[d]
        assert s["request_count"] == 0
        assert s["total_input_tokens"] == 0
        assert s["uncached_input_tokens"] == 0
        assert s["total_output_tokens"] == 0
        assert s["total_reasoning_tokens"] == 0
        assert s["cache_hit_tokens"] == 0
        assert s["cache_write_tokens"] == 0
        assert s["total_cost_usd"] == 0.0
        assert s["hit_rate"] == 0.0


def test_daily_stats_empty_returns_zero_series(tmp_db):
    """窗口内完全没有记录时返回全 0 的连续日期序列 (而非空列表)."""
    stats = db.daily_stats(30)
    assert len(stats) == 30  # 恰好 N 个点 (I10)
    assert all(s["request_count"] == 0 and s["total_cost_usd"] == 0.0 for s in stats)


# ---------------------------------------------------------------------------
# I1: 重登录目标账号固化 (save_token account_id)
# ---------------------------------------------------------------------------


def test_save_token_targets_explicit_account(tmp_db):
    """登录发起时固化的目标账号: 即使活跃账号已被切走, 也只写目标账号 (P1-1 db 侧)."""
    a = db.add_account("tA", "ws-a")
    b = db.add_account("tB", "ws-b")  # 活跃 = b
    conn = db.get_db()
    conn.execute("UPDATE usage_sync_state SET deepest_page_fetched = 9 WHERE account_id = ?", (a,))
    conn.commit()
    # 登录途中切号, 回调时带发起时的目标 a
    assert db.set_active_account(b) is True
    assert db.save_token("tA-new", "ws-a2", account_id=a) is True
    tokens = {r["id"]: r["token"] for r in conn.execute("SELECT id, token FROM accounts")}
    assert tokens[a] == "tA-new" and tokens[b] == "tB"  # b 的原凭证分毫不动
    assert db.get_active_account_id() == b               # 活跃账号不被写回操作改掉
    sa, sb = db.get_sync_state(a), db.get_sync_state(b)
    assert sa["deepest_page_fetched"] == -1  # 目标账号游标被重置
    assert sb["deepest_page_fetched"] == -1


def test_save_token_missing_target_returns_false(tmp_db):
    """目标账号已被删: 明确返回 False (调用方回退新增), 不误写活跃账号."""
    db.add_account("tA", "ws-a")
    before = db.count_accounts()
    assert db.save_token("tok-x", "ws", account_id=9999) is False
    assert db.count_accounts() == before
    assert db.get_token() == "tA"  # 活跃账号未被写入 tok-x


# ---------------------------------------------------------------------------
# I2: insert_usage_records / add_account 的 commit=False 事务参与
# ---------------------------------------------------------------------------


def test_commit_false_participates_in_caller_transaction(tmp_db):
    """备份导入场景: 账号创建 + 记录写入并入外层事务, 回滚后库内无半截数据."""
    conn = db.get_db()
    before_accounts = db.count_accounts()
    conn.execute("BEGIN")
    aid = db.add_account("tok-tx", "ws-tx", switch=False, commit=False)
    db.insert_usage_records([_rec("tx-1")], aid, commit=False)
    db.rename_account(aid, "TX", commit=False)
    assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == before_accounts + 1
    conn.rollback()
    assert db.count_accounts() == before_accounts
    assert db.count_records() == 0
    assert not [x for x in db.list_accounts() if x["name"] == "TX"]


def test_commit_false_committed_by_caller_persists(tmp_db):
    conn = db.get_db()
    conn.execute("BEGIN")
    aid = db.add_account("tok-tx", "ws-tx", switch=False, commit=False)
    assert db.insert_usage_records([_rec("tx-1")], aid, commit=False) == 1
    conn.commit()
    assert db.count_records() == 1
    assert next(x for x in db.list_accounts() if x["id"] == aid)["has_token"] is True


# ---------------------------------------------------------------------------
# P2-2: 空 token 占位行按 (provider, workspace_id, name) 去重 (导入幂等)
# ---------------------------------------------------------------------------


def test_add_account_dedupes_placeholder_identity(tmp_db):
    a1 = db.add_account("", "ws-ph", switch=False, name="Backup A")
    a2 = db.add_account("", "ws-ph", switch=False, name="Backup A")
    assert a1 == a2
    assert db.count_accounts() == 2  # 种子 + 1 个占位行
    # 同 workspace 不同名字: 不同备份账号, 不能合并
    a3 = db.add_account("", "ws-ph", switch=False, name="Backup B")
    assert a3 != a1
    # 有 token 的账号不会被占位行去重命中
    tok = db.add_account("tok-x", "ws-ph", switch=False)
    assert tok not in (a1, a3)


# ---------------------------------------------------------------------------
# I3: prune 覆盖 charts (P2-7) / 脏 window_days 防御 (P3-9)
# ---------------------------------------------------------------------------


def _old_created(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def test_prune_preview_and_expired_cover_charts(tmp_db):
    aid = db.get_active_account_id()
    db.insert_usage_records(
        [_rec("old-rec", created=_old_created(400)), _rec("new-rec", created=_old_created(1))]
    )
    db.insert_usage_charts(
        [
            {"model": "goat", "time_bucket": (datetime.now(timezone.utc) - timedelta(days=400))
             .strftime("%Y-%m-%d %H:%M:%S"), "requests": 3},
            {"model": "goat", "time_bucket": datetime.now(timezone.utc)
             .strftime("%Y-%m-%d %H:%M:%S"), "requests": 1},
        ],
        aid,
    )
    preview = db.prune_preview(30)
    assert preview["count"] == 1 and preview["charts_count"] == 1

    result = db.prune_expired(30)
    assert result == {"records": 1, "charts": 1}
    assert db.count_records() == 1
    assert db.get_db().execute("SELECT COUNT(*) FROM usage_charts").fetchone()[0] == 1
    # 再清理一次不出错且无可删
    assert db.prune_expired(30) == {"records": 0, "charts": 0}


def test_prune_all_and_invalid_window_are_noops(tmp_db):
    db.insert_usage_records([_rec("u-old", created="2020-01-01T00:00:00Z")])
    assert db.prune_preview(None) == {
        "window_days": None, "cutoff": None, "count": 0, "charts_count": 0,
    }
    assert db.prune_expired(None) == {"records": 0, "charts": 0}
    # 脏值 (字符串/None 以外) 不得抛异常让接口 500
    assert db._prune_window("oops") is None
    assert db.prune_expired("oops") == {"records": 0, "charts": 0}
    assert db._prune_window(0) == 1
    assert db._prune_window(99999) == 3650


# ---------------------------------------------------------------------------
# I13: set_data_dir(None) 复位
# ---------------------------------------------------------------------------


def test_set_data_dir_none_resets_process_state(tmp_path, monkeypatch):
    """切库状态复位: override / schema 标记 / payload/凭证缓存全清, 并关当前连接."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    db.set_data_dir(str(tmp_path))
    db.get_db()
    assert db._data_dir_override == str(tmp_path)
    assert db._schema_init_path == str(tmp_path / "gousage.db")  # 以库文件路径为键
    db._cred_cache[1] = (0.0, ("t", "w", "opencode"))

    db.set_data_dir(None)
    assert db._data_dir_override is None
    assert db._schema_init_path is None
    assert db._payload_cache is None and db._payload_cache_path is None
    assert db._cred_cache == {}
    assert getattr(db._db_local, "conn", None) is None  # 当前线程连接已关


# ---------------------------------------------------------------------------
# I15/P3-9: 设置读取/写入的类型规整
# ---------------------------------------------------------------------------


def _write_raw_payload(payload: dict) -> None:
    import json as _json

    conn = db.get_db()
    conn.execute(
        "UPDATE settings SET payload = ? WHERE id = 1",
        (_json.dumps(payload),),
    )
    conn.commit()
    db._invalidate_payload_cache()


def test_get_settings_coerces_dirty_values(tmp_db):
    _write_raw_payload(
        {
            "sync_interval_sec": "oops",
            "auto_sync": "false",
            "window_days": "abc",
            "chart_animation": "true",
            "key_names": {"k": "v"},
        }
    )
    settings = db.get_settings()
    assert settings["sync_interval_sec"] == 300     # 非法 -> 默认
    assert settings["auto_sync"] is False           # 字符串 "false" 不能变 True
    assert settings["window_days"] == 60            # 非法 -> 默认
    assert settings["chart_animation"] is True
    # 正常数值仍照常钳制
    _write_raw_payload({"sync_interval_sec": 5})
    assert db.get_settings()["sync_interval_sec"] == 30


def test_save_settings_parses_string_booleans(tmp_db):
    out = db.save_settings({"auto_sync": "false", "autostart": "true", "ds_peak_split": 0})
    assert out["auto_sync"] is False
    assert out["autostart"] is True
    assert out["ds_peak_split"] is False
    assert db.get_settings()["auto_sync"] is False
    # 非白名单键 (key_names) 不会被整体覆盖丢失
    db.save_key_names({"k1": "名字"})
    db.save_settings({"auto_sync": True})
    assert db.get_key_names() == {"k1": "名字"}


# ---------------------------------------------------------------------------
# P3-8: payload 缓存回写持锁 (旧值不能覆盖新写入)
# ---------------------------------------------------------------------------


def test_payload_cache_fill_holds_lock(tmp_db, monkeypatch):
    import threading
    import time as _time

    db.save_settings({"sync_interval_sec": 300})
    db._invalidate_payload_cache()
    started = threading.Event()
    release = threading.Event()
    real_read = db._read_payload_row

    def slow_read(conn):
        started.set()
        release.wait(3)
        return real_read(conn)

    monkeypatch.setattr(db, "_read_payload_row", slow_read)
    result: dict = {}

    def reader():
        result["payload"] = db._raw_payload(db.get_db())

    reader_thread = threading.Thread(target=reader)
    reader_thread.start()
    assert started.wait(3)

    def writer():
        db.save_settings({"sync_interval_sec": 123})

    writer_thread = threading.Thread(target=writer)
    writer_thread.start()
    _time.sleep(0.2)  # 写线程此时应被 _payload_lock 挡在锁外
    release.set()
    reader_thread.join(5)
    writer_thread.join(5)

    assert not reader_thread.is_alive() and not writer_thread.is_alive()
    assert result["payload"]["sync_interval_sec"] == 300  # 读线程拿到的是旧值
    # 最终缓存必须是新写入的值 (旧读不能把 300 回写进缓存)
    assert db.get_settings()["sync_interval_sec"] == 123
    assert db._payload_cache["sync_interval_sec"] == 123


# ---------------------------------------------------------------------------
# P3-11: last_inserted_count 语义 / clear_account 重置 last_sync_at
# ---------------------------------------------------------------------------


def test_last_inserted_count_is_per_update(tmp_db):
    """last_inserted_count 记"本次更新写入条数"而非历史累加 (旧实现只增不减)."""
    db.update_sync_state("ok", None, inserted=5)
    assert db.get_sync_state()["last_inserted_count"] == 5
    db.update_sync_state("ok", None, inserted=3)
    assert db.get_sync_state()["last_inserted_count"] == 3  # 不是 8


def test_clear_account_resets_last_sync_at(tmp_db):
    aid = db.add_account("tA", "ws-a")
    db.update_sync_state("ok", None, inserted=2, account_id=aid)
    assert db.get_sync_state(aid)["last_sync_at"] is not None
    db.clear_account()
    st = db.get_sync_state(aid)
    assert st["last_sync_at"] is None  # 登出后不再显示旧的"上次同步"
    assert st["last_inserted_count"] == 0
