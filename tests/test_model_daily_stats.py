"""model_daily_stats (统计页模型堆叠趋势图数据源): 连续日期 / 缺日补 0 / 多模型 / 排除过滤."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


def _iso_days_ago(n: int) -> str:
    """n 天前的 UTC ISO —— 用本地时钟回推, 保证 local_date 恰好是 n 天前 (任意时区)."""
    return (datetime.now().astimezone() - timedelta(days=n)).astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )


def _rec(usg_id: str, model: str, *, inp=100, out=10, cache_read=0, cost=0.01, days_ago=0) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": _iso_days_ago(days_ago),
        "model": model,
        "input_tokens": inp,
        "output_tokens": out,
        "reasoning_tokens": 0,
        "cache_read_tokens": cache_read,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": cost,
        "session_id": "s1",
    }


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def test_continuous_days_with_zero_fill(tmp_db):
    db.insert_usage_records([
        _rec("u1", "alpha", inp=100, out=10, cost=1.5),
        _rec("u2", "alpha", inp=100, out=10, cost=0.5),
        _rec("u3", "beta", inp=20, out=2, cost=0.2, days_ago=2),
    ])
    out = db.model_daily_stats(days=3)
    assert len(out["days"]) == 4  # [今天-3, 今天]
    assert out["days"][-1] == _today()
    by_model = {s["model"]: s for s in out["series"]}
    assert set(by_model) == {"alpha", "beta"}
    alpha = by_model["alpha"]
    assert len(alpha["input"]) == 4
    assert alpha["input"][-1] == 200 and alpha["input"][-2] == 0  # 同日两条累加, 其余补 0
    assert alpha["output"][-1] == 20
    assert alpha["cost"][-1] == pytest.approx(2.0)
    beta = by_model["beta"]
    assert beta["input"][-3] == 20 and beta["input"][-1] == 0  # 两天前的值落在对应天


def test_cache_tokens_counted_as_input(tmp_db):
    db.insert_usage_records([_rec("u1", "alpha", inp=100, cache_read=900)])
    out = db.model_daily_stats(days=1)
    alpha = out["series"][0]
    assert alpha["input"][-1] == 1000  # 与 model_stats 的「含缓存输入」同口径


def test_exclude_models_filters_series(tmp_db):
    db.insert_usage_records([
        _rec("u1", "alpha", cost=1.0),
        _rec("u2", "beta", cost=2.0),
    ])
    out = db.model_daily_stats(days=1, exclude_models=["beta"])
    assert [s["model"] for s in out["series"]] == ["alpha"]


def test_empty_db_returns_continuous_days(tmp_db):
    out = db.model_daily_stats(days=7)
    assert len(out["days"]) == 8
    assert out["series"] == []
