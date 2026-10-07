"""Burn-rate 用量预测引擎 (v2.2.0b) — 纯函数, 与 Android domain/ForecastEngine.kt 1:1 对齐.

两种月度口径的统一:
- GOAT (commandcode): 月剩余金额直读 (月池 × 剩余%), 5h/weekly 窗口带真实 cap ($);
- opencode: 窗口只有百分比 → 用「本周期已耗 $ ÷ 已用 %」换算每 1% 单价,
  再推出各窗口剩余金额。已用 <1% 时除数过小噪声放大, 该路径放弃 (结果置 None)。

输出各字段独立可空: 缺输入只影响对应项, 不拖垮整份预测。
"""
from __future__ import annotations

import math
from typing import Any, Optional

# 参与日均耗统计的天数窗口 (Android FORECAST_AVG_DAYS parity)
AVG_WINDOW_DAYS = 14
# % 换算的最小已用比例: 低于此值除数噪声放大, 放弃换算
MIN_USED_PERCENT_FOR_RATE = 1.0
# opencode 30 天滚动周期 (db._MONTHLY_PERIOD_DAYS parity)
DEFAULT_PERIOD_DAYS = 30


def forecast(inp: dict[str, Any], now_ms: Optional[int] = None) -> dict[str, Any]:
    """纯函数预测. 输入/输出字段与 Android ForecastEngine.kt 同名对齐 (snake_case).

    输入 (各可选字段缺省为 None/0):
      daily_costs: [{"date": "yyyy-MM-dd", "cost_usd": float}] (升序, 含补 0 天)
      period_start_ms / period_end_ms: 计费周期起止 epoch ms
      month_used_percent / month_remaining_percent: 月度窗口已用/剩余 %
      month_remaining_amount: GOAT 月剩余金额 ($)
      five_hour_cap_amount / week_cap_amount: GOAT 窗口 cap ($)
      five_hour_used_percent / week_used_percent: 窗口已用 %
      period_cost_usd: 本计费周期已耗 $
      recent_2h_cost: 近 2 小时已耗 $
    """
    import time

    if now_ms is None:
        now_ms = int(time.time() * 1000)

    daily = (inp.get("daily_costs") or [])[-AVG_WINDOW_DAYS:]
    costs = [float(d.get("cost_usd") or 0) for d in daily]
    non_zero = sum(1 for c in costs if c > 0)
    avg_daily = (sum(costs) / len(costs)) if costs else 0.0
    degraded = non_zero < 2

    month_used = inp.get("month_used_percent")
    month_used = float(month_used) if month_used is not None else None
    month_rem_pct = inp.get("month_remaining_percent")
    month_rem_pct = float(month_rem_pct) if month_rem_pct is not None else None
    period_cost = float(inp.get("period_cost_usd") or 0)
    recent_2h = float(inp.get("recent_2h_cost") or 0)

    # ---- 每 1% 窗口单价 (opencode 换算路径) ----
    usd_per_percent: Optional[float] = None
    if month_used is not None and month_used >= MIN_USED_PERCENT_FOR_RATE and period_cost > 0:
        usd_per_percent = period_cost / month_used

    # ---- 月度剩余 $: GOAT 直读, opencode 换算 ----
    month_remaining_usd = inp.get("month_remaining_amount")
    if month_remaining_usd is None and usd_per_percent is not None and month_rem_pct is not None:
        month_remaining_usd = usd_per_percent * month_rem_pct
    month_remaining_usd = float(month_remaining_usd) if month_remaining_usd is not None else None

    # ---- 月度还能用几天 ----
    month_days_left: Optional[float] = None
    if month_remaining_usd is not None and avg_daily > 0:
        month_days_left = month_remaining_usd / avg_daily

    # ---- 今日预算: 月剩余 ÷ 周期剩余天数 (终末半天内不输出, 避免除数虚高) ----
    daily_budget_usd: Optional[float] = None
    period_end_ms = inp.get("period_end_ms")
    if month_remaining_usd is not None and period_end_ms:
        days_left = (float(period_end_ms) - now_ms) / 86_400_000.0
        if days_left >= 0.5:
            daily_budget_usd = month_remaining_usd / days_left

    # ---- 预计整周期总耗 ----
    projected_period_cost: Optional[float] = None
    if avg_daily > 0:
        period_start_ms = inp.get("period_start_ms")
        if period_start_ms and period_end_ms and float(period_end_ms) > float(period_start_ms):
            span_days = (float(period_end_ms) - float(period_start_ms)) / 86_400_000.0
        else:
            span_days = float(DEFAULT_PERIOD_DAYS)
        projected_period_cost = avg_daily * span_days

    # ---- 5h 窗口打满预测: 剩余金额 ÷ 近 2h 速率 ----
    five_hour_cap = inp.get("five_hour_cap_amount")
    five_used = inp.get("five_hour_used_percent")
    five_hour_remaining: Optional[float] = None
    if five_hour_cap is not None:
        five_hour_remaining = float(five_hour_cap) * (100.0 - float(five_used or 0)) / 100.0
    elif usd_per_percent is not None and five_used is not None:
        five_hour_remaining = usd_per_percent * (100.0 - float(five_used))
    five_hour_exhaust_in_min: Optional[int] = None
    if five_hour_remaining is not None and five_hour_remaining > 0 and recent_2h > 0:
        hours = five_hour_remaining / (recent_2h / 2.0)
        five_hour_exhaust_in_min = int(math.ceil(hours * 60.0))

    # ---- 周窗口还能用几天 ----
    week_cap = inp.get("week_cap_amount")
    week_used = inp.get("week_used_percent")
    week_remaining: Optional[float] = None
    if week_cap is not None:
        week_remaining = float(week_cap) * (100.0 - float(week_used or 0)) / 100.0
    elif usd_per_percent is not None and week_used is not None:
        week_remaining = usd_per_percent * (100.0 - float(week_used))
    week_days_left: Optional[float] = None
    if week_remaining is not None and avg_daily > 0:
        week_days_left = week_remaining / avg_daily

    return {
        "month_remaining_usd": _round2(month_remaining_usd),
        "daily_budget_usd": _round2(daily_budget_usd),
        "month_days_left": _round2(month_days_left),
        "projected_period_cost_usd": _round2(projected_period_cost),
        "five_hour_exhaust_in_min": five_hour_exhaust_in_min,
        "week_days_left": _round2(week_days_left),
        "degraded": degraded,
    }


def _round2(v: Optional[float]) -> Optional[float]:
    return round(float(v), 2) if v is not None else None
