"""配额窗口打满预测 (app/forecast.py) 纯函数单测."""
from __future__ import annotations

from app.forecast import FIVE_HOUR_SEC, WEEK_SEC, window_forecast, window_len_sec


class TestWindowLenSec:
    def test_fixed_windows(self):
        assert window_len_sec("5h Rolling") == FIVE_HOUR_SEC
        assert window_len_sec("Weekly") == WEEK_SEC

    def test_monthly_from_period_bounds(self):
        # 自然月 10-08 → 11-08 (31 天)
        assert window_len_sec("Monthly", "2026-10-08T00:00:00Z", "2026-11-08T00:00:00Z") == 31 * 86400

    def test_monthly_missing_or_invalid_bounds(self):
        assert window_len_sec("Monthly") is None
        assert window_len_sec("Monthly", "2026-10-08T00:00:00Z", None) is None
        assert window_len_sec("Monthly", "garbage", "2026-11-08T00:00:00Z") is None
        # 起点晚于终点: 脏数据不产出窗口长度
        assert window_len_sec("Monthly", "2026-11-08T00:00:00Z", "2026-10-08T00:00:00Z") is None

    def test_unknown_label(self):
        assert window_len_sec("Something else") is None


class TestWindowForecast:
    def test_fill_before_reset(self):
        # 5h 窗口: 已过 6000s, 已用 42% → 剩余 58% 按同速率还需 ~8286s, 早于 12000s 重置
        fc = window_forecast(used=42, reset_in_sec=12000, window_len=FIVE_HOUR_SEC)
        assert fc == {"state": "fill", "sec": 8286}

    def test_no_fill_when_pace_too_slow(self):
        # 已过 6000s 仅用 10%: 按均值到重置只用到 30%, 不会打满
        fc = window_forecast(used=10, reset_in_sec=12000, window_len=FIVE_HOUR_SEC)
        assert fc == {"state": "no_fill", "pct": 30}

    def test_no_fill_on_zero_usage(self):
        fc = window_forecast(used=0, reset_in_sec=12000, window_len=FIVE_HOUR_SEC)
        assert fc == {"state": "no_fill", "pct": 0}

    def test_no_fill_projects_usage_at_reset(self):
        # 月窗口 31 天, 已过 13 天用 41%: 41 × 31 ÷ 13 ≈ 97.8% → 98 (重置前不会打满)
        month = 31 * 86400
        elapsed = 13 * 86400
        fc = window_forecast(used=41, reset_in_sec=month - elapsed, window_len=month)
        assert fc == {"state": "no_fill", "pct": 98}

    def test_no_fill_pct_rounds_half_up(self):
        # 32.4 × 18000 ÷ 6000 = 97.2% → 97; 32.5 × 18000 ÷ 6000 = 97.5% → 98
        # (四舍五入, 与 Android Forecast.kt 同口径)
        fc = window_forecast(used=32.4, reset_in_sec=12000, window_len=FIVE_HOUR_SEC)
        assert fc == {"state": "no_fill", "pct": 97}
        fc = window_forecast(used=32.5, reset_in_sec=12000, window_len=FIVE_HOUR_SEC)
        assert fc == {"state": "no_fill", "pct": 98}

    def test_none_when_sample_too_small(self):
        # 窗口刚重置 (elapsed=0) 或已过不足 1% 时间: 不给预测
        assert window_forecast(used=5, reset_in_sec=FIVE_HOUR_SEC, window_len=FIVE_HOUR_SEC) is None
        assert window_forecast(used=5, reset_in_sec=FIVE_HOUR_SEC - 60, window_len=FIVE_HOUR_SEC) is None

    def test_none_when_already_full(self):
        assert window_forecast(used=100, reset_in_sec=12000, window_len=FIVE_HOUR_SEC) is None
        assert window_forecast(used=120, reset_in_sec=12000, window_len=FIVE_HOUR_SEC) is None

    def test_none_without_window_len(self):
        assert window_forecast(used=42, reset_in_sec=12000, window_len=None) is None
        assert window_forecast(used=42, reset_in_sec=12000, window_len=0) is None

    def test_reset_too_large_is_dirty_data(self):
        # reset 越过窗口长度 → elapsed 为负, 视为脏数据不预测
        assert window_forecast(used=42, reset_in_sec=FIVE_HOUR_SEC + 60, window_len=FIVE_HOUR_SEC) is None

    def test_weekly_pace(self):
        # 周窗口已过 1 天用 20%: 剩余 80% 需 4 天, 早于 6 天重置 → fill
        elapsed = 86400
        fc = window_forecast(used=20, reset_in_sec=WEEK_SEC - elapsed, window_len=WEEK_SEC)
        assert fc == {"state": "fill", "sec": 4 * 86400}

    def test_boundary_exhaust_equals_reset(self):
        # 耗尽时刻恰好等于重置时刻: 不算打满 (需严格早于重置)
        # used=50, elapsed=1000 → exhaust=1000; reset=1000 → no_fill; 预测 100% 封顶为 99
        fc = window_forecast(used=50, reset_in_sec=1000, window_len=2000)
        assert fc == {"state": "no_fill", "pct": 99}

    def test_string_inputs_tolerated(self):
        fc = window_forecast(used="42", reset_in_sec="12000", window_len=FIVE_HOUR_SEC)
        assert fc == {"state": "fill", "sec": 8286}


class TestNonFiniteInputs:
    """NaN/Inf 输入防护 (F17): 上游 JSON 允许 NaN 字面量, math.floor(nan) 会抛异常."""

    def test_nan_used_returns_none(self):
        from app.forecast import window_forecast

        assert window_forecast(used=float("nan"), reset_in_sec=12000, window_len=FIVE_HOUR_SEC) is None

    def test_nan_reset_returns_none(self):
        from app.forecast import window_forecast

        assert window_forecast(used=42, reset_in_sec=float("nan"), window_len=FIVE_HOUR_SEC) is None

    def test_inf_inputs_return_none(self):
        from app.forecast import window_forecast

        assert window_forecast(used=float("inf"), reset_in_sec=12000, window_len=FIVE_HOUR_SEC) is None
        assert window_forecast(used=42, reset_in_sec=float("inf"), window_len=FIVE_HOUR_SEC) is None
        assert window_forecast(used=42, reset_in_sec=12000, window_len=float("nan")) is None

    def test_unparseable_strings_return_none(self):
        from app.forecast import window_forecast

        assert window_forecast(used="oops", reset_in_sec=12000, window_len=FIVE_HOUR_SEC) is None
