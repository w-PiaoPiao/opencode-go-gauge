"""按 DeepSeek 峰谷口径切分本地用量 (只读, 不改库).

DeepSeek-V4.1-Flash (模型名 deepseek-flash) 自 2026-09-10 起实行两档计价:
  * 高峰: 北京时间 (UTC+8) 周一至周五 09:00-12:00、14:00-18:00, 且非法定节假日
  * 空闲: 其余全部时段 (含周末与法定节假日全天), 单价恰为高峰的一半
区间左闭右开 —— 实测本地账单在 11:59:59 仍为高峰价, 12:00:07 已切空闲价,
14:00/18:00 同理. 调休补班的周六 (如 2026-10-10) 实测仍按空闲价计费,
因此判定只看「周一到周五 + 非法定节假日」, 不看调休上班日.

官方单价 (USD / 1M tokens, 空闲档):
    输入-缓存未命中 0.15   输入-缓存命中 0.003   输出 0.60
高峰档为上述两倍.

库内 token 口径: input_tokens 是未命中部分, cache_read_tokens 是命中部分,
两者相加才是总输入; output_tokens 为输出. cost_usd 为上游实付金额,
已含峰谷差价 (实测与官方两档价逐条吻合, 单条比值精确 1.00).

用法:
    python scripts/peak_split.py                         # 自动找最新的库
    python scripts/peak_split.py --model deepseek-v4-flash
    python scripts/peak_split.py --db "C:/path/gousage.db" --by-day
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3
import sys
from collections import defaultdict

UTC8 = dt.timezone(dt.timedelta(hours=8))

# 国务院办公厅《关于2026年部分节假日安排的通知》: 法定节假日放假日
# (调休上班的 9-20、10-10 不在其中 —— 周末仍算空闲)
HOLIDAYS_2026 = {
    *[dt.date(2026, 1, d) for d in (1, 2, 3)],
    *[dt.date(2026, 2, d) for d in range(15, 24)],
    *[dt.date(2026, 4, d) for d in (4, 5, 6)],
    *[dt.date(2026, 5, d) for d in range(1, 6)],
    *[dt.date(2026, 6, d) for d in (19, 20, 21)],
    *[dt.date(2026, 9, d) for d in (25, 26, 27)],
    *[dt.date(2026, 10, d) for d in range(1, 8)],
}
# 旧年份 (库里可能有 2025 存量) 只补常见节日, 缺的年份按「仅周末」处理
HOLIDAYS = HOLIDAYS_2026

PEAK_WINDOWS = ((9 * 60, 12 * 60), (14 * 60, 18 * 60))
# 官方单价 USD/1M: 空闲 = (未命中, 命中, 输出); 高峰 = 空闲 × 2
RATE_OFF = (0.15, 0.003, 0.60)


def pick_db(explicit: str | None) -> str:
    if explicit:
        return explicit
    cands = []
    env = os.environ.get("GOUSAGE_DATA")
    if env:
        cands.append(os.path.join(env, "gousage.db"))
    home = os.path.expanduser("~")
    cands += [
        os.path.join(home, "Desktop", "data", "gousage.db"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "GoGauge", "data", "gousage.db"),
        os.path.join(os.path.dirname(__file__), "..", "data", "gousage.db"),
        os.path.join(os.path.dirname(__file__), "..", "dist", "data", "gousage.db"),
    ]
    best, best_score = None, -1
    for p in cands:
        if not p or not os.path.exists(p):
            continue
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            n = con.execute("SELECT COUNT(*) FROM usage_records").fetchone()[0]
            con.close()
        except sqlite3.Error:
            continue
        # 行数是主要依据, 同分看修改时间
        score = n * 1e12 + os.path.getmtime(p)
        if n > 0 and score > best_score:
            best, best_score = p, score
    if not best:
        sys.exit("找不到含数据的 gousage.db, 请用 --db 指定")
    return os.path.abspath(best)


def to_bj(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC8)


def is_peak(moment: dt.datetime) -> bool:
    if moment.weekday() >= 5 or moment.date() in HOLIDAYS:
        return False
    minute = moment.hour * 60 + moment.minute
    return any(lo <= minute < hi for lo, hi in PEAK_WINDOWS)


def theo_cost(rec: sqlite3.Row, peak: bool) -> float:
    mult = 2.0 if peak else 1.0
    miss, hit, out = (v * mult for v in RATE_OFF)
    return (rec["input_tokens"] * miss + rec["cache_read_tokens"] * hit
            + rec["output_tokens"] * out) / 1e6


def main() -> None:
    ap = argparse.ArgumentParser(description="按 DeepSeek 峰谷口径切分本地用量")
    ap.add_argument("--db", help="gousage.db 路径 (默认自动探测数据最多的库)")
    ap.add_argument("--model", default="deepseek-v4.1-flash",
                    help="模型名 (精确匹配, 默认 deepseek-v4.1-flash)")
    ap.add_argument("--by-day", action="store_true", help="额外输出逐日峰谷明细")
    args = ap.parse_args()

    path = pick_db(args.db)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT created_at, provider, input_tokens, output_tokens, cache_read_tokens, cost_usd
           FROM usage_records WHERE model = ? ORDER BY created_at""", (args.model,)).fetchall()
    if not rows:
        sys.exit(f"库 {path} 里没有 model={args.model!r} 的记录")

    span = f"{to_bj(rows[0]['created_at']):%Y-%m-%d} ~ {to_bj(rows[-1]['created_at']):%Y-%m-%d}"
    print(f"库: {path}")
    print(f"模型: {args.model}    记录: {len(rows):,}    区间: {span}\n")

    agg = {k: dict(n=0, miss=0, hit=0, out=0, cost=0.0, theo=0.0) for k in ("peak", "off")}
    by_day: dict[dt.date, dict[str, float]] = defaultdict(
        lambda: {"pn": 0, "pc": 0.0, "on": 0, "oc": 0.0})
    for r in rows:
        moment = to_bj(r["created_at"])
        key = "peak" if is_peak(moment) else "off"
        a = agg[key]
        a["n"] += 1
        a["miss"] += r["input_tokens"]
        a["hit"] += r["cache_read_tokens"]
        a["out"] += r["output_tokens"]
        a["cost"] += r["cost_usd"] or 0.0
        a["theo"] += theo_cost(r, key == "peak")
        d = by_day[moment.date()]
        d["pn" if key == "peak" else "on"] += 1
        d["pc" if key == "peak" else "oc"] += r["cost_usd"] or 0.0

    print(f"{'档位':<6}{'请求':>7}{'输入未命中':>14}{'输入命中':>16}{'输出':>13}"
          f"{'实付USD':>11}{'官方理论':>11}{'实付/理论':>10}")
    tot = dict(n=0, miss=0, hit=0, out=0, cost=0.0, theo=0.0)
    for key, label in (("peak", "高峰"), ("off", "空闲")):
        a = agg[key]
        ratio = a["cost"] / a["theo"] if a["theo"] else 0
        print(f"{label:<6}{a['n']:>7}{a['miss']:>14,}{a['hit']:>16,}{a['out']:>13,}"
              f"{a['cost']:>11.4f}{a['theo']:>11.4f}{ratio:>10.4f}")
        for f in tot:
            tot[f] += a[f]
    print(f"{'合计':<6}{tot['n']:>7}{tot['miss']:>14,}{tot['hit']:>16,}{tot['out']:>13,}"
          f"{tot['cost']:>11.4f}{tot['theo']:>11.4f}"
          f"{(tot['cost'] / tot['theo'] if tot['theo'] else 0):>10.4f}")

    peak, off = agg["peak"], agg["off"]
    tok = lambda a: a["miss"] + a["hit"] + a["out"]  # noqa: E731
    all_tok = tok(peak) + tok(off)
    print(f"\n高峰占比: 请求 {peak['n'] / tot['n'] * 100:.1f}%   "
          f"token {tok(peak) / all_tok * 100 if all_tok else 0:.1f}%   "
          f"金额 {peak['cost'] / tot['cost'] * 100 if tot['cost'] else 0:.1f}%")
    print(f"高峰 token 单价是空闲的 2 倍; 若高峰用量整体挪到空闲档, "
          f"账单 ${tot['cost']:.4f} -> ${tot['cost'] - peak['cost'] / 2:.4f} "
          f"(省 ${peak['cost'] / 2:.4f}, {peak['cost'] / 2 / tot['cost'] * 100 if tot['cost'] else 0:.1f}%)")

    if args.by_day:
        print(f"\n{'日期':<12}{'周':<3}{'高峰请求':>9}{'高峰USD':>10}{'空闲请求':>9}{'空闲USD':>10}")
        for d in sorted(by_day):
            v = by_day[d]
            wd = "一二三四五六日"[d.weekday()]
            flag = " 假" if d in HOLIDAYS else ""
            print(f"{d!s:<12}{wd}{flag:<2}{int(v['pn']):>9}{v['pc']:>10.4f}"
                  f"{int(v['on']):>9}{v['oc']:>10.4f}")
    con.close()


if __name__ == "__main__":
    main()
