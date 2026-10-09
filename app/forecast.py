"""配额窗口打满预测 (纯函数) — 首页三窗口的「预计耗尽于 X / 预计不会打满」.

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

    返回 {"state": "fill", "sec": N} — 预计 N 秒后耗尽, 早于重置;
        {"state": "no_fill"}        — 按当前速率重置前用不完;
        None                        — 无法预测 (样本不足 / 已打满 / 缺窗口长度).
    """
    if not window_len or window_len <= 0:
        return None
    u = float(used or 0)
    if u >= 100.0:  # 已打满, 无预测可言
        return None
    reset = max(0.0, float(reset_in_sec or 0))
    elapsed = window_len - reset
    if elapsed < window_len * MIN_SAMPLE_RATIO:  # 样本不足 (含 reset 越过窗口长度的脏数据)
        return None
    if u <= 0.0:  # 零消耗: 重置前用不完
        return {"state": "no_fill"}
    exhaust = (100.0 - u) * elapsed / u
    if exhaust < reset:
        return {"state": "fill", "sec": int(math.ceil(exhaust))}
    return {"state": "no_fill"}
