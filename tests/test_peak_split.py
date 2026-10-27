"""DeepSeek 峰谷分档 (设置 ds_peak_split): 判定口径 / 拆分守恒 / 关闭时行为不变.

分档是纯展示层口径 —— 断言重点是「拆出来的两条加起来 == 原来一条」,
以及 totals / 明细 / 同步数据一概不受影响.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from app import db, server

BJ = timezone(timedelta(hours=8))


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


def _tier_of(created_at_utc: str, model: str = "deepseek-v4.1-flash") -> str:
    """直接把时间戳喂给 tier 表达式 (绕开周期过滤, 便于测历史日期/节假日)."""
    expr, params = db._peak_tier_sql("created_at")
    row = db.get_db().execute(
        f"SELECT {expr} AS tier FROM (SELECT ? AS created_at, ? AS model)",
        [*params, created_at_utc, model],
    ).fetchone()
    return row["tier"]


def _utc(day: str, hhmmss: str) -> str:
    """北京时间 -> 库内 UTC ISO 串."""
    naive = datetime.strptime(f"{day} {hhmmss}", "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=BJ).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _rec(usg_id: str, model: str, created_at: str, *, inp=100, out=10, cache_read=0, cost=0.01) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": created_at,
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


def _recent_weekday_hour(hour: int, weekday: int = 0) -> str:
    """最近一个指定星期几 (0=周一) 的北京时间 hour 点, 保证落在统计窗口内."""
    now = datetime.now(BJ)
    delta = (now.weekday() - weekday) % 7
    day = (now - timedelta(days=delta)).replace(hour=hour, minute=0, second=0, microsecond=0)
    if day > now:  # 该时刻还没到 -> 往前推一周
        day -= timedelta(days=7)
    return day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ---------------------------------------------------------------------------
# 判定口径: 左闭右开 + 周末 + 法定节假日 + 调休补班日
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("beijing_time", "expect"),
    [
        ("2026-10-12 08:59:59", "off"),   # 周一, 高峰前
        ("2026-10-12 09:00:00", "peak"),  # 左闭: 起点算高峰
        ("2026-10-12 11:59:59", "peak"),
        ("2026-10-12 12:00:00", "off"),   # 右开: 12:00 已切空闲
        ("2026-10-12 13:59:59", "off"),
        ("2026-10-12 14:00:00", "peak"),
        ("2026-10-12 17:59:59", "peak"),
        ("2026-10-12 18:00:00", "off"),
        ("2026-10-17 10:00:00", "off"),   # 周六全天空闲
        ("2026-10-18 10:00:00", "off"),   # 周日全天空闲
        ("2026-10-01 10:00:00", "off"),   # 国庆 (周四) 全天空闲
        ("2026-10-10 10:00:00", "off"),   # 调休上班的周六仍按空闲 (实测口径)
        ("2026-09-25 10:00:00", "off"),   # 中秋 (周五) 全天空闲
        ("2026-09-30 10:00:00", "peak"),  # 节前普通工作日
    ],
)
def test_peak_window_boundaries(tmp_db, beijing_time, expect):
    day, clock = beijing_time.split()
    assert _tier_of(_utc(day, clock)) == expect


def test_only_deepseek_flash_is_split(tmp_db):
    ts = _utc("2026-10-12", "10:00:00")
    assert _tier_of(ts, "deepseek-v4.1-flash") == "peak"
    assert _tier_of(ts, "deepseek/deepseek-v4.1-flash") == "peak"
    assert _tier_of(ts, "deepseek-v4-flash") == "peak"
    assert _tier_of(ts, "glm-5.3-flash") == ""          # 非 deepseek
    assert _tier_of(ts, "deepseek-v4.1-flash-free") == ""  # 白嫖款不分档
    assert _tier_of(ts, "deepseek-v4-pro") == ""        # 非 flash


# ---------------------------------------------------------------------------
# 拆分与守恒
# ---------------------------------------------------------------------------


def test_split_off_keeps_single_row(tmp_db):
    db.insert_usage_records([
        _rec("u1", "deepseek-v4.1-flash", _recent_weekday_hour(11), cost=0.5),
        _rec("u2", "deepseek-v4.1-flash", _recent_weekday_hour(11, weekday=6), cost=0.25),
    ])
    rows = db.model_stats("30d")
    flash = [r for r in rows if r["base_model"] == "deepseek-v4.1-flash"]
    assert len(flash) == 1
    assert flash[0]["model"] == "deepseek-v4.1-flash"
    assert flash[0]["request_count"] == 2


def test_split_on_splits_peak_and_off(tmp_db):
    db.insert_usage_records([
        _rec("u1", "deepseek-v4.1-flash", _recent_weekday_hour(11), inp=100, out=10, cost=0.5),
        _rec("u2", "deepseek-v4.1-flash", _recent_weekday_hour(11, weekday=6), inp=200, out=20, cost=0.25),
    ])
    db.save_settings({"ds_peak_split": True})
    rows = db.model_stats("30d")
    by_label = {r["model"]: r for r in rows}
    assert "deepseek-v4.1-flash 峰" in by_label
    assert "deepseek-v4.1-flash 谷" in by_label
    assert by_label["deepseek-v4.1-flash 峰"]["base_model"] == "deepseek-v4.1-flash"
    peak, off = by_label["deepseek-v4.1-flash 峰"], by_label["deepseek-v4.1-flash 谷"]
    assert peak["request_count"] == 1 and off["request_count"] == 1
    assert peak["total_input_tokens"] == 100 and off["total_input_tokens"] == 200
    # 守恒: 两条相加 = 关闭时的单条
    db.save_settings({"ds_peak_split": False})
    whole = [r for r in db.model_stats("30d") if r["model"] == "deepseek-v4.1-flash"][0]
    assert peak["total_cost_usd"] + off["total_cost_usd"] == pytest.approx(whole["total_cost_usd"])
    assert peak["request_count"] + off["request_count"] == whole["request_count"]


def test_totals_untouched_by_split(tmp_db):
    db.insert_usage_records([
        _rec("u1", "deepseek-v4.1-flash", _recent_weekday_hour(11), inp=100, out=10, cost=0.5),
        _rec("u2", "deepseek-v4.1-flash", _recent_weekday_hour(11, weekday=6), inp=200, out=20, cost=0.25),
        _rec("u3", "glm-5.3-flash", _recent_weekday_hour(11), inp=50, out=5, cost=0.1),
    ])
    db.save_settings({"ds_peak_split": False})
    before = db.totals("30d")
    daily_before = db.daily_stats(30)
    db.save_settings({"ds_peak_split": True})
    assert db.totals("30d") == before
    assert db.daily_stats(30) == daily_before


def test_free_and_other_models_not_split(tmp_db):
    db.insert_usage_records([
        _rec("u1", "deepseek-v4.1-flash-free", _recent_weekday_hour(11)),
        _rec("u2", "glm-5.3-flash", _recent_weekday_hour(11)),
    ])
    db.save_settings({"ds_peak_split": True})
    names = {r["model"] for r in db.model_stats("30d")}
    assert names == {"deepseek-v4.1-flash-free", "glm-5.3-flash"}


def test_model_daily_stats_split_series(tmp_db):
    db.insert_usage_records([
        _rec("u1", "deepseek-v4.1-flash", _recent_weekday_hour(11), inp=100, cost=0.5),
        _rec("u2", "deepseek-v4.1-flash", _recent_weekday_hour(11, weekday=6), inp=200, cost=0.25),
    ])
    db.save_settings({"ds_peak_split": True})
    out = db.model_daily_stats(days=7)
    by_label = {s["model"]: s for s in out["series"]}
    assert set(by_label) == {"deepseek-v4.1-flash 峰", "deepseek-v4.1-flash 谷"}
    assert by_label["deepseek-v4.1-flash 峰"]["base_model"] == "deepseek-v4.1-flash"
    assert sum(sum(s["input"]) for s in by_label.values()) == 300
    db.save_settings({"ds_peak_split": False})
    out2 = db.model_daily_stats(days=7)
    assert [s["model"] for s in out2["series"]] == ["deepseek-v4.1-flash"]


# ---------------------------------------------------------------------------
# 排除: 带后缀的名称要剥回真实模型 (排除是模型级动作)
# ---------------------------------------------------------------------------


def test_exclude_strips_tier_suffix(tmp_db):
    assert db._exclude_clause(["deepseek-v4.1-flash 峰"]) == ("model NOT IN (?)", ["deepseek-v4.1-flash"])
    assert db._exclude_clause(["deepseek-v4.1-flash 谷", "glm-5.3-flash"]) == (
        "model NOT IN (?, ?)", ["deepseek-v4.1-flash", "glm-5.3-flash"]
    )


def test_exclude_by_tier_label_removes_whole_model(tmp_db):
    db.insert_usage_records([
        _rec("u1", "deepseek-v4.1-flash", _recent_weekday_hour(11), inp=100, cost=0.5),
        _rec("u2", "glm-5.3-flash", _recent_weekday_hour(11), inp=50, cost=0.1),
    ])
    db.save_settings({"ds_peak_split": True})
    full = db.totals("30d")
    excluded = db.totals("30d", None, ["deepseek-v4.1-flash 峰"])
    assert excluded["request_count"] == full["request_count"] - 1
    assert excluded["total_cost_usd"] == pytest.approx(full["total_cost_usd"] - 0.5)


def test_setting_defaults_off_and_persists(tmp_db):
    assert db.get_settings()["ds_peak_split"] is False
    db.save_settings({"ds_peak_split": True})
    assert db.get_settings()["ds_peak_split"] is True
    db.save_settings({"ds_peak_split": False})


# ---------------------------------------------------------------------------
# 计价起始门 / 模型白名单
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("beijing_time", "expect"),
    [
        ("2026-09-09 10:00:00", ""),      # 起始门之前: 即使落在高峰窗也不拆
        ("2026-09-09 23:59:59", ""),
        ("2026-09-10 00:00:00", "off"),   # 起始门之后, 非高峰窗算谷
        ("2026-09-10 08:00:00", "off"),
        ("2026-09-10 09:00:00", "peak"),
        ("2026-09-14 20:00:00", "off"),
    ],
)
def test_pricing_start_cutoff(tmp_db, beijing_time, expect):
    day, clock = beijing_time.split()
    assert _tier_of(_utc(day, clock)) == expect


def test_pre_cutoff_records_stay_whole(tmp_db):
    """起始门之前 (单一价时期) 的 flash 记录不能拆成峰/谷."""
    db.insert_usage_records([
        _rec("u1", "deepseek-v4.1-flash", _utc("2026-09-09", "10:00:00"), cost=0.1),
        _rec("u2", "deepseek-v4.1-flash", _utc("2026-09-10", "10:00:00"), cost=0.2),
    ])
    db.save_settings({"ds_peak_split": True})
    rows = db.model_stats("all")
    by_label = {r["model"]: r for r in rows}
    assert by_label["deepseek-v4.1-flash"]["request_count"] == 1  # 起始门之前整条
    assert by_label["deepseek-v4.1-flash 峰"]["request_count"] == 1
    assert "deepseek-v4.1-flash 谷" not in by_label


def test_experimental_flash_variants_not_split(tmp_db):
    """集费规则未经验证的实验变体不参与分档 (精确白名单)."""
    ts = _utc("2026-10-12", "10:00:00")
    assert _tier_of(ts, "deepseek-v4-flash-vision-exp") == ""
    assert _tier_of(ts, "deepseek/deepseek-v4-flash-vision-exp") == ""
    assert _tier_of(ts, "deepseek-v4.1-flash-thinking") == ""
    assert _tier_of(ts, "deepseek-v4-flash") == "peak"  # 白名单里的另一条主线
    assert _tier_of(ts, "deepseek/deepseek-v4.1-flash") == "peak"


# ---------------------------------------------------------------------------
# charts 数据源: 15 分钟桶起点判档, 结果必须与明细路径一致
# ---------------------------------------------------------------------------


def _chart(aid: int, model: str, created_at_utc: str, *, cost=0.01, requests=1) -> dict:
    bj = datetime.fromisoformat(created_at_utc.replace("Z", "+00:00")).astimezone(BJ)
    return {
        "account_id": aid,
        "model": model,
        "provider": "commandcode",
        "time_bucket": created_at_utc.replace("T", " ")[:16] + ":00",
        "requests": requests,
        "total_cost": cost,
        "tokens_in": 100 * requests,
        "tokens_out": 10 * requests,
        "tokens_total": 110 * requests,
        "local_date": bj.strftime("%Y-%m-%d"),
        "synced_at": "2026-10-27T00:00:00Z",
    }


def _insert_charts(rows: list[dict]) -> None:
    con = db.get_db()
    con.executemany(
        """INSERT INTO usage_charts
           (account_id, model, provider, time_bucket, requests, total_cost,
            tokens_in, tokens_out, tokens_total, local_date, synced_at)
           VALUES (:account_id, :model, :provider, :time_bucket, :requests,
                   :total_cost, :tokens_in, :tokens_out, :tokens_total,
                   :local_date, :synced_at)""",
        rows,
    )
    con.commit()


def test_charts_path_split(tmp_db, monkeypatch):
    aid = db.get_active_account_id()
    _insert_charts([
        _chart(aid, "deepseek-v4.1-flash", _recent_weekday_hour(11), cost=0.30),
        _chart(aid, "deepseek-v4.1-flash", _recent_weekday_hour(11, weekday=6), cost=0.15),
    ])
    monkeypatch.setattr(db, "_use_charts_stats", lambda _aid: True)
    db.save_settings({"ds_peak_split": True})

    rows = db.model_stats("7d")
    by_label = {r["model"]: r for r in rows}
    assert by_label["deepseek-v4.1-flash 峰"]["request_count"] == 1
    assert by_label["deepseek-v4.1-flash 谷"]["request_count"] == 1
    assert by_label["deepseek-v4.1-flash 峰"]["total_cost_usd"] == pytest.approx(0.30)
    assert by_label["deepseek-v4.1-flash 谷"]["total_cost_usd"] == pytest.approx(0.15)

    daily = db.model_daily_stats(7)
    by_series = {s["model"]: s for s in daily["series"]}
    assert set(by_series) == {"deepseek-v4.1-flash 峰", "deepseek-v4.1-flash 谷"}
    assert sum(by_series["deepseek-v4.1-flash 峰"]["cost"]) == pytest.approx(0.30)
    assert sum(by_series["deepseek-v4.1-flash 谷"]["cost"]) == pytest.approx(0.15)

    db.save_settings({"ds_peak_split": False})
    assert [r["model"] for r in db.model_stats("7d")] == ["deepseek-v4.1-flash"]


# ---------------------------------------------------------------------------
# 首页/统计页隔离: 只有统计页请求 (peak_split=1) 拆, 且设置是最终闸门
# ---------------------------------------------------------------------------


def _http_json(url: str, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _with_server(fn) -> None:
    server.bump_data_generation()
    host, port = server.start_server("127.0.0.1", 0)
    try:
        fn(f"http://{host}:{port}")
    finally:
        server.stop_server()


def _seed_split_records() -> None:
    db.insert_usage_records([
        _rec("u1", "deepseek-v4.1-flash", _recent_weekday_hour(11), cost=0.5),
        _rec("u2", "deepseek-v4.1-flash", _recent_weekday_hour(11, weekday=6), cost=0.25),
    ])


def test_dashboard_split_only_on_stats_page(tmp_db):
    _seed_split_records()
    db.save_settings({"ds_peak_split": True})

    def run(base: str) -> None:
        home = _http_json(f"{base}/api/dashboard?range=7d")
        stats = _http_json(f"{base}/api/dashboard?range=7d&peak_split=1")
        trend = _http_json(f"{base}/api/model_trend?days=7")

        home_labels = [m["model"] for m in home["models"]]
        stats_labels = [m["model"] for m in stats["models"]]
        assert "deepseek-v4.1-flash" in home_labels
        assert not any(label.endswith((" 峰", " 谷")) for label in home_labels)
        assert "deepseek-v4.1-flash 峰" in stats_labels
        assert "deepseek-v4.1-flash 谷" in stats_labels
        assert home["totals"] == stats["totals"]
        assert {"deepseek-v4.1-flash 峰", "deepseek-v4.1-flash 谷"} <= {
            s["model"] for s in trend["series"]
        }

    _with_server(run)


def test_dashboard_split_gated_by_setting(tmp_db):
    _seed_split_records()
    db.save_settings({"ds_peak_split": False})

    def run(base: str) -> None:
        data = _http_json(f"{base}/api/dashboard?range=7d&peak_split=1")
        labels = [m["model"] for m in data["models"]]
        assert "deepseek-v4.1-flash" in labels
        assert not any(label.endswith((" 峰", " 谷")) for label in labels)

    _with_server(run)
    assert db.get_settings()["ds_peak_split"] is False
