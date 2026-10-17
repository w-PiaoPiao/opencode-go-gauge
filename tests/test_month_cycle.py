"""「本周期」筛选口径测试.

覆盖三条曾经出过问题的链路:
1. 周期起点推算 —— 真实周期顺延 (自然月按日历月推进) 与未来起点护栏;
2. 明细 / charts 两条聚合路径的窗口必须同源 (日历日口径), 否则同一张表上并存两套
   窗口, 统计页总卡比趋势图少掉最早半天的数据;
3. local_date 的派生不依赖 SQLite ≥3.38 的 'Z' 后缀解析 —— 解析失败会让该行
   local_date 为 NULL, 静默地不被任何周期过滤命中.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.db import PROVIDER_COMMANDCODE


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    db._DB = None
    db._invalidate_cred_cache()  # 进程级凭证缓存跨测试共享, 换库必须清
    yield tmp_path
    db.close_db()


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _rec(usg_id, created, model="m", inp=10, outp=20, cost_usd=0.5):
    return {
        "usg_id": usg_id, "created_at": created, "model": model, "provider": None,
        "input_tokens": inp, "output_tokens": outp, "reasoning_tokens": 0,
        "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
        "cost_raw": 0, "cost_usd": cost_usd, "key_id": None, "session_id": None, "plan": None,
    }


def _chart(time_bucket: str, requests: int = 1, model: str = "goat-a") -> dict:
    return {
        "model": model, "provider": PROVIDER_COMMANDCODE, "time_bucket": time_bucket,
        "requests": requests, "tokens_in": requests * 100, "tokens_out": requests * 10,
        "cache_read_tokens": 0, "cache_creation_tokens": 0, "total_cost": 0.1,
    }


def _use_commandcode() -> int:
    """把活跃账号切成 commandcode 并返回其 id (统计改走 usage_charts 数据源)."""
    aid = db.get_active_account_id()
    conn = db.get_db()
    conn.execute("UPDATE accounts SET provider = ? WHERE id = ?", (PROVIDER_COMMANDCODE, aid))
    conn.commit()
    return aid


def _local_to_utc(local_dt: str) -> str:
    """本地时刻 -> UTC 存储串 (charts 的 time_bucket 形态)."""
    return db.get_db().execute(
        "SELECT strftime('%Y-%m-%d %H:%M:%S', ?, 'utc') AS u", (local_dt,)
    ).fetchone()["u"]


# ---------------------------------------------------------------------------
# 1. 周期起点推算
# ---------------------------------------------------------------------------


class TestCycleStartGuard:
    def test_future_period_start_never_returned(self, tmp_db):
        """接口给出尚未开始的周期 (或本机时钟落后于服务端) 时绝不返回未来起点.

        未来起点会让「本周期」窗口恒为空 —— local_date >= 未来日期 筛出 0 条,
        正是 monthly_cycle_start 注释声称要避免的失效模式 (曾经只在 30 天回推的
        兜底路径上有这道护栏, 真实周期路径没有).
        """
        now = _now_naive()
        db.record_period_bounds(None, _fmt(now + timedelta(days=5)), _fmt(now + timedelta(days=35)))
        assert db.monthly_cycle_start() is None
        # 回退滚动 30 天口径: 今天的记录必须仍被「本周期」筛到
        db.insert_usage_records([_rec("u-today", now.strftime("%Y-%m-%dT%H:%M:%SZ"))])
        assert db.totals("month")["request_count"] == 1

    def test_invalid_bounds_fall_back(self, tmp_db):
        """end <= start 的脏数据回退 None (走滚动 30 天), 不返回未来起点也不死循环."""
        now = _now_naive()
        db.record_period_bounds(None, _fmt(now - timedelta(days=10)), _fmt(now - timedelta(days=40)))
        assert db.monthly_cycle_start() is None

    def test_real_period_in_progress_untouched(self, tmp_db):
        """周期尚未结束: 直接返回记录的真实起点, 不做任何顺延."""
        now = _now_naive()
        start = now - timedelta(days=10)
        db.record_period_bounds(None, _fmt(start), _fmt(start + timedelta(days=31)))
        assert db.monthly_cycle_start() == _fmt(start)


class TestCalendarMonthRoll:
    def test_add_calendar_months_keeps_anchor(self):
        """以锚点一次算出: 01-31 加 2 个月 = 03-31.

        逐月累加会丢锚点 (01-31 → 02-28 → 03-28), 此后永久停在 28 号 —— 顺延必须
        以原始起点为基准.
        """
        anchor = datetime(2026, 1, 31, 0, 0, 0)
        assert db._add_calendar_months(anchor, 1) == datetime(2026, 2, 28)
        assert db._add_calendar_months(anchor, 2) == datetime(2026, 3, 31)
        assert db._add_calendar_months(anchor, 3) == datetime(2026, 4, 30)
        assert db._add_calendar_months(anchor, 12) == datetime(2027, 1, 31)
        assert db._add_calendar_months(anchor, 14) == datetime(2027, 3, 31)

    def test_natural_month_cycle_rolls_by_calendar_month(self, tmp_db):
        """自然月周期按日历月推进, 日号随锚点保持.

        用记录的固定跨度反复顺延会累积漂移: 31 天自然月按 30 天跨度顺延, 每跨一个
        周期偏 1 天, 长期未打开可偏出一周 (实测 01-31→03-02 的 30 天跨度跨 8 个
        周期后偏到 09-28).
        """
        now = _now_naive()
        anchor = db._add_calendar_months(now, -9).replace(hour=1, minute=0, second=0, microsecond=0)
        db.record_period_bounds(None, _fmt(anchor), _fmt(db._add_calendar_months(anchor, 1)))
        got = datetime.strptime(db.monthly_cycle_start(), "%Y-%m-%d %H:%M:%S")
        assert got <= now < db._add_calendar_months(got, 1)  # 落在覆盖 now 的那个周期
        assert got.day == anchor.day                        # 日号不漂

    def test_weekly_span_keeps_fixed_roll(self, tmp_db):
        """跨度明显不是自然月 (如 7 天周套餐) 时保持固定跨度, 不被日历月改坏."""
        now = _now_naive()
        anchor = (now - timedelta(days=16)).replace(hour=0, minute=0, second=0, microsecond=0)
        db.record_period_bounds(None, _fmt(anchor), _fmt(anchor + timedelta(days=7)))
        got = datetime.strptime(db.monthly_cycle_start(), "%Y-%m-%d %H:%M:%S")
        assert got == anchor + timedelta(days=14)  # 每 7 天一个周期, 第 3 个覆盖 now


# ---------------------------------------------------------------------------
# 2. 明细 / charts 两条聚合路径的窗口一致性
# ---------------------------------------------------------------------------


class TestChartsRangeParity:
    """charts 聚合的 Nd 与 month 回退必须与明细同源 (日历日口径).

    回归: aa6cdbff 给 _charts_period_where 追加 local_date 索引收敛条件时, 明细分支
    是"替换"旧的 datetime() 精筛、charts 分支是"追加", 遗留成两套窗口 —— 同一张
    usage_charts 表上, 总卡 (精确 N×24h) 比趋势图 (日历日) 少掉最早那半天的数据.
    """

    def _seed_boundary_day(self, aid: int) -> int:
        """在窗口最早的本地日塞入"半天"数据, 返回该日两条桶的请求数之和."""
        earliest = db.get_db().execute(
            "SELECT date('now', 'localtime', '-30 days') AS d"
        ).fetchone()["d"]
        db.insert_usage_charts(
            [
                _chart(_local_to_utc(f"{earliest} 00:30:00"), requests=100),  # 精确口径会漏掉
                _chart(_local_to_utc(f"{earliest} 23:30:00"), requests=1),
            ],
            aid,
        )
        return 101

    def test_30d_matches_daily_stats(self, tmp_db):
        aid = _use_commandcode()
        total = self._seed_boundary_day(aid)
        assert db._use_charts_stats(aid)  # 确认统计走 charts 数据源
        assert db.totals("30d", aid)["request_count"] == total
        assert sum(d["request_count"] for d in db.daily_stats(30, aid)) == total

    def test_month_fallback_matches_30d(self, tmp_db):
        """无周期记录时 month 回退到滚动 30 天, 与 "30d" 必须完全同源."""
        aid = _use_commandcode()
        self._seed_boundary_day(aid)
        assert db.monthly_cycle_start(aid) is None  # 无周期记录 -> 走回退
        assert db.totals("month", aid) == db.totals("30d", aid)

    def test_month_with_real_cycle_keeps_exact_start(self, tmp_db):
        """有真实周期起点时仍精确到秒 (只砍掉周期开始之前的数据), 两路径同口径."""
        aid = _use_commandcode()
        start = _now_naive() - timedelta(hours=12)  # 已是 UTC
        db.record_period_bounds(aid, _fmt(start), _fmt(start + timedelta(days=31)))
        # time_bucket 本身就是 UTC 串, 不经本地时区转换
        inside = _fmt(start + timedelta(hours=1))
        outside = _fmt(start - timedelta(hours=1))
        db.insert_usage_charts([_chart(inside, requests=3), _chart(outside, requests=7)], aid)
        assert db._use_charts_stats(aid)
        assert db.totals("month", aid)["request_count"] == 3


# ---------------------------------------------------------------------------
# 3. local_date 派生不依赖 SQLite 的 'Z' / 偏移后缀解析
# ---------------------------------------------------------------------------


class TestLocalDateDerivation:
    """local_date 由 substr(created_at, 1, 19) 派生.

    created_at 是 isoformat 产物 ("...T..Z" 带微秒, 或 "+0000" 这类无冒号偏移) ——
    整串交给 SQLite 的 date() 只有 ≥3.38 且偏移带冒号时才认; 解析失败返回 NULL,
    该行便静默地不被任何周期过滤命中 (全表 NULL 时「本周期」筛出 0 条).
    """

    # 无冒号偏移: Python 的 fromisoformat 接受 (app 侧能解析入库), SQLite 的 date()
    # 整串解析返回 NULL —— 正是 substr 截断要挡住的形态.
    NO_COLON_OFFSET = "2026-01-02T03:04:05.678901+0000"

    def test_insert_derives_local_date(self, tmp_db):
        db.insert_usage_records([_rec("u1", self.NO_COLON_OFFSET)])
        row = db.get_db().execute(
            "SELECT local_date FROM usage_records WHERE usg_id = 'u1'"
        ).fetchone()
        assert row["local_date"] is not None

    def test_backfill_repairs_null_local_date(self, tmp_db):
        """迁移回填修复历史 NULL 行 (旧版 SQLite 写入的存量数据)."""
        conn = db.get_db()
        conn.execute(
            "INSERT INTO usage_records (usg_id, created_at, model, provider, input_tokens,"
            " output_tokens, reasoning_tokens, cache_read_tokens, cache_write_5m_tokens,"
            " cache_write_1h_tokens, cost_raw, cost_usd, key_id, session_id, plan, synced_at,"
            " account_id, local_date) VALUES ('legacy', ?, 'm', 'opencode', 1, 1, 0, 0, 0, 0,"
            " 0, 0.0, NULL, NULL, NULL, '2026-01-02T03:04:05Z', ?, NULL)",
            (self.NO_COLON_OFFSET, db.get_active_account_id()),
        )
        conn.commit()
        # 强制重跑迁移检查: _ensure_schema 只在连接建立时判路径, 需连连接一起换
        db._schema_init_path = None
        db.close_db()
        db.get_db()
        row = db.get_db().execute(
            "SELECT local_date FROM usage_records WHERE usg_id = 'legacy'"
        ).fetchone()
        assert row["local_date"] is not None
