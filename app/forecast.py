"""配额窗口打满预测 (纯函数) — 首页三窗口的「预计耗尽于 X / 预计不会打满（X%）」.

口径: 按窗口内自身的平均消耗速率外推 (已用 % ÷ 已过时间). used 与 reset_in_sec
取自同一份配额快照, 因此预测与界面上「重置于 X」始终同源可比; 不依赖历史账单
或金额换算 —— 各窗口独立自洽, 缺周期边界时宁可不显示.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from .opencode_api import LABEL_MONTHLY, LABEL_ROLLING, LABEL_WEEKLY, iso_to_ms

FIVE_HOUR_SEC = 5 * 3600
WEEK_SEC = 7 * 86400
# 已过时间不足窗口长度的 1% 时不预测: 窗口刚重置的突发用量会放大噪声
MIN_SAMPLE_RATIO = 0.01
# 「不会打满」时展示的预测用量上限: 预测值本身 <= 100, 而 100% 与「不会打满」
# 自相矛盾 (边界上耗尽时刻恰等于重置时刻), 显示层封顶 99.
MAX_PROJECTED_PCT = 99


def _projected_pct(used: float, elapsed: float, window_len: float) -> int:
    """按窗口内平均速率外推到重置时的用量百分比 (四舍五入取整, 封顶 99).

    与打满判定同源: exhaust < reset ⇔ used × window_len ÷ elapsed > 100, 所以
    no_fill 分支里本函数的结果天然 <= 100; 取整/封顶保证「不会打满」不会配上
    「（100%）」这种自相矛盾的文案.
    """
    projected = used * window_len / elapsed
    return max(0, min(MAX_PROJECTED_PCT, int(math.floor(projected + 0.5))))


def window_len_sec(
    label: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Optional[float]:
    """窗口总时长 (秒). 5h/周为固定长度; 月窗口取订阅周期起止, 缺边界则 None."""
    if label == LABEL_ROLLING:
        return float(FIVE_HOUR_SEC)
    if label == LABEL_WEEKLY:
        return float(WEEK_SEC)
    if label == LABEL_MONTHLY:
        start, end = iso_to_ms(period_start or ""), iso_to_ms(period_end or "")
        if start and end and end > start:
            return (end - start) / 1000.0
    return None


def window_forecast(
    used: Any,
    reset_in_sec: Any,
    window_len: Optional[float],
) -> Optional[dict[str, Any]]:
    """按窗口内平均速率判断能否在重置前打满.

    返回 {"state": "fill", "sec": N}    — 预计 N 秒后耗尽, 早于重置;
        {"state": "no_fill", "pct": P}  — 不会打满, 按当前速率到重置时预计用掉 P%;
        None                            — 无法预测 (样本不足 / 已打满 / 缺窗口长度).
    """
    if not window_len or window_len <= 0:
        return None
    try:
        u = float(used or 0)
        reset_raw = float(reset_in_sec or 0)
        window_len = float(window_len)
    except (TypeError, ValueError):
        # 字符串/None 之外的脏值: 不预测比 500 好
        return None
    # NaN/Inf 防护: 上游 JSON 允许 NaN 字面量; math.floor(nan + 0.5) 会抛
    # ValueError → /api/dashboard 500 (F17). 非有限值一律当作"无法预测".
    # 注意要在 max(0.0, reset) 之前判: max 对 NaN 的返回值是实现相关的.
    if not (math.isfinite(u) and math.isfinite(reset_raw) and math.isfinite(window_len)):
        return None
    reset = max(0.0, reset_raw)
    if u >= 100.0:  # 已打满, 无预测可言
        return None
    elapsed = window_len - reset
    if elapsed < window_len * MIN_SAMPLE_RATIO:  # 样本不足 (含 reset 越过窗口长度的脏数据)
        return None
    if u <= 0.0:  # 零消耗: 重置前用不完
        return {"state": "no_fill", "pct": 0}
    exhaust = (100.0 - u) * elapsed / u
    if exhaust < reset:
        return {"state": "fill", "sec": int(math.ceil(exhaust))}
    return {"state": "no_fill", "pct": _projected_pct(u, elapsed, window_len)}
