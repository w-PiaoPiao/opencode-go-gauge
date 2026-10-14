"""today_trend (首页 24 小时趋势数据源): 五字段口径 / 小时补 0 / 明细与 charts 双路径.

2026-10-14: 图从「未缓存输入+输出」扩为可选「含缓存总 TOKEN」单列, 后端补齐
cache_read/cache_write 字段, 且 charts 路径的 input 需从含缓存的 tokens_in 中减出
cache_read_tokens, 与明细路径对齐 (此前 charts 路径的 input 是含缓存口径, 两路径不一致).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import db
from app.db import PROVIDER_COMMANDCODE


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


def _today_at(hour: int, *, minute: int = 0) -> str:
    """今天本地 hour 点的 UTC ISO —— 用本地时钟构造, 保证 local_date 恰好是今天 (任意时区)."""
    local = datetime.now().astimezone().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _rec(
    usg_id: str,
    *,
    created_at: str,
    model: str = "m",
    inp=100,
    out=10,
    rsn=0,
    cache_read=0,
    cw5=0,
    cw1=0,
) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": created_at,
        "model": model,
        "input_tokens": inp,
        "output_tokens": out,
        "reasoning_tokens": rsn,
        "cache_read_tokens": cache_read,
        "cache_write_5m_tokens": cw5,
        "cache_write_1h_tokens": cw1,
        "cost_raw": 0,
        "cost_usd": 0.01,
        "session_id": "s1",
    }


def test_hourly_fields_and_zero_fill(tmp_db):
    db.insert_usage_records([
        _rec("u1", created_at=_today_at(10), inp=100, out=10, rsn=5, cache_read=1000, cw5=20, cw1=30),
        _rec("u2", created_at=_today_at(10, minute=30), inp=200, out=20, cache_read=500),
        _rec("u3", created_at=_today_at(15), inp=7, out=3, rsn=1),
    ])
    trend = db.today_trend()
    assert len(trend) == 24 and trend[0]["hour"] == "00:00" and trend[23]["hour"] == "23:00"
    assert trend[10] == {
        "hour": "10:00", "input": 300, "cache_read": 1500,
        "cache_write": 50, "output": 30, "reasoning": 5,
    }
    h15 = trend[15]
    assert (h15["input"], h15["output"], h15["reasoning"], h15["cache_read"]) == (7, 3, 1, 0)
    for h in (0, 9, 23):
        assert trend[h]["input"] == 0 and trend[h]["cache_read"] == 0 and trend[h]["output"] == 0


def test_total_matches_totals_today(tmp_db):
    """含缓存柱 (五项求和) 与 totals('today') 的「总 TOKEN 消耗」卡口径对账."""
    db.insert_usage_records([
        _rec("u1", created_at=_today_at(9), inp=100, out=10, rsn=5, cache_read=1000, cw5=20, cw1=30),
        _rec("u2", created_at=_today_at(18), inp=200, out=20, cache_read=500),
    ])
    five = sum(
        t["input"] + t["cache_read"] + t["cache_write"] + t["output"] + t["reasoning"]
        for t in db.today_trend()
    )
    tt = db.totals("today")
    assert five == tt["total_input_tokens"] + tt["total_output_tokens"] + tt["total_reasoning_tokens"]


def test_charts_path_reports_uncached_input(tmp_db):
    """commandcode charts 路径: tokens_in 含缓存读, input 报未缓存部分 (与明细对齐)."""
    conn = db.get_db()
    conn.execute("UPDATE accounts SET provider = ? WHERE id = 1", (PROVIDER_COMMANDCODE,))
    conn.commit()
    db.insert_usage_charts([
        {"model": "goat", "provider": PROVIDER_COMMANDCODE, "time_bucket": _today_at(12),
         "requests": 1, "tokens_in": 1000, "tokens_out": 100, "cache_read_tokens": 400,
         "cache_creation_tokens": 50, "total_cost": 0.5},
    ])
    assert db.today_trend()[12] == {
        "hour": "12:00", "input": 600, "cache_read": 400,
        "cache_write": 50, "output": 100, "reasoning": 0,
    }
