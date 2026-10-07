"""ForecastEngine 纯函数单测 — 与 Android ForecastEngineTest 同口径 (四组用例对齐)."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.forecast import forecast

NOW_MS = 1_759_000_000_000


def _days(*costs: float) -> list[dict]:
    return [{"date": f"2026-09-{i + 1:02d}", "cost_usd": c} for i, c in enumerate(costs)]


def _opencode_input(**kw):
    base = {
        "daily_costs": _days(5.0, 0.0, 10.0, 3.0, 2.0, 0.0, 10.0),
        "period_start_ms": NOW_MS - 15 * 86_400_000,
        "period_end_ms": NOW_MS + 15 * 86_400_000,
        "month_used_percent": 50.0,
        "month_remaining_percent": 50.0,
        "month_remaining_amount": None,  # opencode: 无金额口径
        "five_hour_cap_amount": None,
        "week_cap_amount": None,
        "five_hour_used_percent": 20.0,
        "week_used_percent": 30.0,
        "period_cost_usd": 20.0,
        "recent_2h_cost": 4.0,
    }
    base.update(kw)
    return base


def _goat_input(**kw):
    base = _opencode_input()
    base.update(
        month_remaining_amount=35.0,  # GOAT: 直读月池 × 剩余%
        five_hour_cap_amount=14.0,
        week_cap_amount=35.0,
    )
    base.update(kw)
    return base


def test_opencode_percent_conversion():
    f = forecast(_opencode_input(), NOW_MS)
    # usdPerPercent = 20/50 = 0.4 → 月剩余 = 0.4 × 50 = $20
    assert abs(f["month_remaining_usd"] - 20.0) < 0.01
    # 日均 = 30/7 ≈ 4.286 → 20/4.286 ≈ 4.67 天
    assert abs(f["month_days_left"] - 4.67) < 0.1
    # 今日预算 = 20 / 15 天 ≈ 1.33
    assert abs(f["daily_budget_usd"] - 1.33) < 0.01
    assert not f["degraded"]


def test_goat_reads_remaining_amount_directly():
    f = forecast(_goat_input(), NOW_MS)
    assert abs(f["month_remaining_usd"] - 35.0) < 0.01
    # 5h: cap $14 × 80% = $11.2; 速率 $2/h → 5.6h → 336 分钟
    assert f["five_hour_exhaust_in_min"] == 336
    # 周: 35 × 70% = $24.5 → 24.5/4.286 ≈ 5.72 天
    assert abs(f["week_days_left"] - 5.72) < 0.1


def test_insufficient_data_degrades():
    f1 = forecast(_opencode_input(daily_costs=_days(0.0, 0.0, 0.0)), NOW_MS)
    assert f1["degraded"]
    assert f1["month_days_left"] is None
    assert f1["projected_period_cost_usd"] is None
    # GOAT 直读金额不受历史影响, 预算仍可算
    f2 = forecast(_goat_input(daily_costs=_days(0.0, 0.0, 0.0)), NOW_MS)
    assert f2["degraded"]
    assert f2["daily_budget_usd"] is not None
    assert abs(f2["month_remaining_usd"] - 35.0) < 0.01
    # 只有 1 个非零日 (<2): 同样退化
    f3 = forecast(_opencode_input(daily_costs=_days(5.0, 0.0, 0.0)), NOW_MS)
    assert f3["degraded"]


def test_skips_conversion_when_usage_below_1_percent():
    f = forecast(_opencode_input(month_used_percent=0.5, month_remaining_percent=99.5), NOW_MS)
    assert f["month_remaining_usd"] is None
    assert f["month_days_left"] is None


def test_no_conversion_without_period_cost():
    f = forecast(_opencode_input(period_cost_usd=0.0), NOW_MS)
    assert f["month_remaining_usd"] is None


def test_five_hour_exhaust_and_guards():
    # opencode: usdPerPercent=0.4, 5h 剩余 = 0.4 × 80 = $32 → 32/2 = 16h = 960 分钟
    f = forecast(_opencode_input(), NOW_MS)
    assert f["five_hour_exhaust_in_min"] == 960
    # 近 2h 无消耗: 不外推
    f2 = forecast(_opencode_input(recent_2h_cost=0.0), NOW_MS)
    assert f2["five_hour_exhaust_in_min"] is None
    # 周期终末半天内不输出预算
    f3 = forecast(_goat_input(period_end_ms=NOW_MS + 6 * 3600_000), NOW_MS)
    assert f3["daily_budget_usd"] is None
