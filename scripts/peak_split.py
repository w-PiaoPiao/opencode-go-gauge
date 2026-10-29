"""按 DeepSeek 峰谷口径切分本地用量 (只读, 不改库).

DeepSeek-V4.1-Flash 自北京 2026-09-10 00:00 起实行两档计价:
  * 高峰: 北京时间 (UTC+8) 周一至周五 09:00-12:00、14:00-18:00, 且非法定节假日
  * 空闲: 其余全部时段 (含周末与法定节假日全天), 单价恰为高峰的一半
区间左闭右开 —— 实测本地账单在 11:59:59 仍为高峰价, 12:00:07 已切空闲价,
14:00/18:00 同理. 调休补班的周六 (如 2026-10-10) 实测仍按空闲价计费,
因此判定只看「周一到周五 + 非法定节假日」, 不看调休上班日.

计价起始门按模型区分 (与 app/db.py 的 _PRICING_GATES 同一口径, I9):
  * deepseek-v4.1-flash: 北京 2026-09-10 00:00 (UTC 2026-09-09 16:00)
  * deepseek-v4-flash:   北京 2026-08-17 00:00 (UTC 2026-08-16 16:00)
    —— 真实账单反证: 该模型 2026-08-17 起空闲/高峰单价约 0.22/0.445 USD/1M,
       08-14 之前各时段同价; 起始门之前的记录为「未分档」, 不参与峰谷统计.

官方单价 (USD / 1M tokens, 空闲档, 仅 V4.1-Flash 已核对):
    输入-缓存未命中 0.15   输入-缓存命中 0.003   输出 0.60
高峰档为上述两倍. V4-Flash 历史价目不同且未完整核对, 本脚本不给它算「官方理论」列.

库内 token 口径: input_tokens 是未命中部分, cache_read_tokens 是命中部分,
两者相加才是总输入; output_tokens 为输出. cost_usd 为上游实付金额,
已含峰谷差价 (实测与官方两档价逐条吻合, 单条比值精确 1.00).

模型名匹配与 App 统计页同口径: 精确名或 ``provider/<模型名>`` 前缀形式都算同一模型.

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
from pathlib import Path


def _force_utf8_stdio() -> None:
    """stdout/stderr 强制 UTF-8 (Windows 控制台 cp1252 打印中文会抛 UnicodeEncodeError)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


# 允许从任意 cwd 运行: 规则/节假日/起始门以 app/db.py 为唯一事实来源 (I9);
# 导入失败 (脚本被单独拷走) 时退回本文件内的等价常量, parity 测试会校验两者一致.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
try:  # pragma: no cover - 取决于运行位置
    from app.db import (  # type: ignore[attr-defined]
        _CN_HOLIDAYS as DB_HOLIDAYS,
        _DS_FLASH_MODELS as DB_FLASH_MODELS,
        _PRICING_GATES as DB_PRICING_GATES,
    )
except (ImportError, AttributeError):  # pragma: no cover - 兜底分支由 parity 测试覆盖
    DB_HOLIDAYS = None
    DB_FLASH_MODELS = None
    DB_PRICING_GATES = None

UTC = dt.timezone.utc
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

# 节假日表: 优先用 db 的按年 dict (db 为准); 兜底为本文件的 2026 集合
CN_HOLIDAYS: dict[int, set[str]] = (
    {int(year): set(days) for year, days in DB_HOLIDAYS.items()}
    if DB_HOLIDAYS
    else {2026: {d.isoformat() for d in HOLIDAYS_2026}}
)
HOLIDAYS = {
    dt.date.fromisoformat(day) for days in CN_HOLIDAYS.values() for day in days
}

# 旧年份 (库里可能有 2025 存量) 缺表时按「仅周末」处理
PEAK_WINDOWS = ((9 * 60, 12 * 60), (14 * 60, 18 * 60))
# 官方单价 USD/1M: 空闲 = (未命中, 命中, 输出); 高峰 = 空闲 × 2
RATE_OFF = (0.15, 0.003, 0.60)
# 已核对过官方两档价目表的模型; 其余模型只统计实测金额, 不给「官方理论」列
RATE_TABLES = {"deepseek-v4.1-flash": RATE_OFF}


def _is_retail_provider(provider: str) -> bool:
    """该行成本是否适用 DeepSeek 零售价目表.

    opencode / inf-go.* 是 Go 订阅的直连上游, 实测与官方单价逐条吻合;
    commandcode 是 GOAT 套餐的积分币种成本 (约为零售价的 5%), 不能拿来和
    零售价目比, 只计入实付/峰谷占比, 不参与「官方理论/可省」列。
    """
    name = str(provider or "").strip().lower()
    return name == "opencode" or name.startswith("inf-go")

# 分档模型白名单 (与 db._DS_FLASH_MODELS 一致; 精确名, 也匹配 provider/ 前缀)
FLASH_MODELS: tuple[str, ...] = tuple(
    DB_FLASH_MODELS or ("deepseek-v4.1-flash", "deepseek-v4-flash")
)

# 计价起始门 (UTC): 值形如 (日期 "YYYY-MM-DD", 时刻 "HH:MM")
_FALLBACK_PRICING_GATES: dict[str, tuple[str, str]] = {
    "deepseek-v4.1-flash": ("2026-09-09", "16:00"),  # 北京 2026-09-10 00:00
    "deepseek-v4-flash": ("2026-08-16", "16:00"),    # 北京 2026-08-17 00:00
}
PRICING_GATES: dict[str, tuple[str, str]] = dict(
    DB_PRICING_GATES or _FALLBACK_PRICING_GATES
)


def _parse_gate(value: tuple[str, str]) -> dt.datetime:
    return dt.datetime.strptime(
        f"{value[0]} {value[1]}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=UTC)


_GATE_DATETIMES = {model: _parse_gate(value) for model, value in PRICING_GATES.items()}


# ---------------------------------------------------------------------------
# 时间 / 模型 / 档位判定 (parity 测试的脚本侧入口)
# ---------------------------------------------------------------------------


def to_utc(ts: str) -> dt.datetime:
    """ISO 时间串 -> UTC datetime (无时区按 UTC; 非法串抛 ValueError)."""
    parsed = dt.datetime.fromisoformat(str(ts).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def to_bj(ts: str) -> dt.datetime:
    """ISO 时间串 -> 北京时间 (与 db 的 UTC+8 峰窗口径一致)."""
    return to_utc(ts).astimezone(UTC8)


def base_model(model: str) -> str:
    """模型名 -> 基础名: 去空白/转小写/剥 ``provider/`` 前缀 (与 db 的 LIKE 同口径)."""
    return str(model or "").strip().lower().rsplit("/", 1)[-1]


def pricing_gate_for(model: str) -> dt.datetime | None:
    """该模型的计价起始时刻 (UTC); 不在分档白名单或未配门返回 None."""
    base = base_model(model)
    if base not in FLASH_MODELS:
        return None
    return _GATE_DATETIMES.get(base)


def is_peak(moment: dt.datetime) -> bool:
    """时刻是否落在高峰窗口 (只看北京时间周几/节假日/时段, **不含计价起始门**)."""
    bj = moment.astimezone(UTC8)
    if bj.weekday() >= 5 or bj.date() in HOLIDAYS:
        return False
    minute = bj.hour * 60 + bj.minute
    return any(lo <= minute < hi for lo, hi in PEAK_WINDOWS)


def tier_for(model: str, created_at_utc: str) -> str:
    """返回档位: ``"peak"`` / ``"off"`` / ``""`` (= 不分档: 计价门之前/非白名单/时间非法).

    与 ``app/db.py::_peak_tier_sql`` 的判定一一对应.
    """
    gate = pricing_gate_for(model)
    if gate is None:
        return ""
    try:
        moment = to_utc(created_at_utc)
    except (TypeError, ValueError):
        return ""
    if moment < gate:
        return ""  # 单一价时期 / 计价门之前: 拆峰谷会误导
    return "peak" if is_peak(moment) else "off"


def theo_cost(
    rec: sqlite3.Row, peak: bool, rate: tuple[float, float, float] = RATE_OFF
) -> float:
    mult = 2.0 if peak else 1.0
    miss, hit, out = (v * mult for v in rate)
    return (rec["input_tokens"] * miss + rec["cache_read_tokens"] * hit
            + rec["output_tokens"] * out) / 1e6


# ---------------------------------------------------------------------------
# 库定位
# ---------------------------------------------------------------------------


def pick_db(explicit: str | None) -> str:
    if explicit:
        return explicit
    cands = []
    env = os.environ.get("GOUSAGE_DATA")
    if env:
        cands.append(os.path.join(env, "gousage.db"))
    home = os.path.expanduser("~")
    # macOS 打包/源码运行的默认数据目录 (app/db.py::_default_data_dir)
    cands.append(os.path.join(
        home, "Library", "Application Support", "GoGauge", "data", "gousage.db"))
    cands.append(os.path.join(home, "Desktop", "data", "gousage.db"))
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        # Windows 打包版默认数据目录 (exe 同目录不可写时的回退)
        cands.append(os.path.join(localappdata, "GoGauge", "data", "gousage.db"))
    cands += [
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


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def _model_where(target: str) -> tuple[str, list[str]]:
    """``--model`` 的 SQL 条件: 精确名或 provider/ 前缀形式 (与 App 统计口径一致)."""
    base = base_model(target)
    return "(lower(model) = ? OR lower(model) LIKE ?)", [base, f"%/{base}"]


def _fmt_ratio(cost: float, theo: float) -> str:
    return f"{cost / theo:.4f}" if theo > 0 else "-"


def main() -> None:
    _force_utf8_stdio()
    ap = argparse.ArgumentParser(description="按 DeepSeek 峰谷口径切分本地用量")
    ap.add_argument("--db", help="gousage.db 路径 (默认自动探测数据最多的库)")
    ap.add_argument("--model", default="deepseek-v4.1-flash",
                    help="模型名, 支持 provider/ 前缀形式 (默认 deepseek-v4.1-flash)")
    ap.add_argument("--by-day", action="store_true", help="额外输出逐日峰谷明细")
    args = ap.parse_args()

    path = pick_db(args.db)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    where, params = _model_where(args.model)
    rows = con.execute(
        f"""SELECT created_at, provider, input_tokens, output_tokens, cache_read_tokens,
                  cost_usd
           FROM usage_records WHERE {where} ORDER BY created_at""", params).fetchall()
    if not rows:
        sys.exit(f"库 {path} 里没有 model={args.model!r} 的记录")

    base = base_model(args.model)
    gate = pricing_gate_for(base)
    rate = RATE_TABLES.get(base)
    span = f"{to_bj(rows[0]['created_at']):%Y-%m-%d} ~ {to_bj(rows[-1]['created_at']):%Y-%m-%d}"
    print(f"库: {path}")
    print(f"模型: {args.model}    记录: {len(rows):,}    区间: {span}")
    if gate is not None:
        print(f"计价起始门: UTC {gate:%Y-%m-%d %H:%M} "
              f"(北京 {gate.astimezone(UTC8):%Y-%m-%d %H:%M}), 此前的记录计为「未分档」")
    else:
        print("该模型不在峰谷分档白名单内, 全部记录按未分档统计")
    print()

    agg = {k: dict(n=0, miss=0, hit=0, out=0, cost=0.0, theo=0.0, retail_cost=0.0)
           for k in ("peak", "off", "na")}
    retail = dict(n=0, cost=0.0)  # 零售价目口径 (可算理论/可省) 的子集
    by_day: dict[dt.date, dict[str, float]] = defaultdict(
        lambda: {"pn": 0, "pc": 0.0, "on": 0, "oc": 0.0, "nn": 0, "nc": 0.0})
    retail_rows = 0
    for r in rows:
        key = tier_for(args.model, r["created_at"]) or "na"
        a = agg[key]
        a["n"] += 1
        a["miss"] += r["input_tokens"]
        a["hit"] += r["cache_read_tokens"]
        a["out"] += r["output_tokens"]
        a["cost"] += r["cost_usd"] or 0.0
        if _is_retail_provider(r["provider"]):
            retail_rows += 1
            retail["n"] += 1
            retail["cost"] += r["cost_usd"] or 0.0
            if rate is not None and key in ("peak", "off"):
                a["retail_cost"] += r["cost_usd"] or 0.0
                a["theo"] += theo_cost(r, key == "peak", rate)
        try:
            day = to_bj(r["created_at"]).date()
        except (TypeError, ValueError):
            continue  # 非法时间已计入未分档, 不参与逐日
        d = by_day[day]
        if key == "peak":
            d["pn"] += 1
            d["pc"] += r["cost_usd"] or 0.0
        elif key == "off":
            d["on"] += 1
            d["oc"] += r["cost_usd"] or 0.0
        else:
            d["nn"] += 1
            d["nc"] += r["cost_usd"] or 0.0

    print(f"{'档位':<6}{'请求':>7}{'输入未命中':>14}{'输入命中':>16}{'输出':>13}"
          f"{'实付USD':>11}{'官方理论':>11}{'实付/理论':>10}")
    tot = dict(n=0, miss=0, hit=0, out=0, cost=0.0, theo=0.0)
    for key, label in (("peak", "高峰"), ("off", "空闲"), ("na", "未分档")):
        a = agg[key]
        print(f"{label:<6}{a['n']:>7}{a['miss']:>14,}{a['hit']:>16,}{a['out']:>13,}"
              f"{a['cost']:>11.4f}{a['theo']:>11.4f}{_fmt_ratio(a['retail_cost'], a['theo']):>10}")
        for f in tot:
            tot[f] += a[f]
    peak, off = agg["peak"], agg["off"]
    total_retail_cost = peak["retail_cost"] + off["retail_cost"]
    print(f"{'合计':<6}{tot['n']:>7}{tot['miss']:>14,}{tot['hit']:>16,}{tot['out']:>13,}"
          f"{tot['cost']:>11.4f}{tot['theo']:>11.4f}"
          f"{_fmt_ratio(total_retail_cost, tot['theo']):>10}")
    if retail_rows != len(rows):
        print(f"注: {len(rows) - retail_rows:,} 条为 Command Code 积分计费 (成本约零售价 5%),"
              f" 计入实付/峰谷占比, 但不参与「官方理论/实付理论比/可省」列")
    judged = peak["n"] + off["n"]
    if judged == 0:
        print("\n没有需要分档的记录 (全部在计价起始门之前或模型未参与分档).")
        con.close()
        return
    tok = lambda a: a["miss"] + a["hit"] + a["out"]  # noqa: E731
    all_tok = tok(peak) + tok(off)
    judged_cost = peak["cost"] + off["cost"]
    print(f"\n高峰占比 (已分档 {judged:,} 条): 请求 {peak['n'] / judged * 100:.1f}%   "
          f"token {tok(peak) / all_tok * 100 if all_tok else 0:.1f}%   "
          f"金额 {peak['cost'] / judged_cost * 100 if judged_cost else 0:.1f}%")
    if rate is not None and total_retail_cost:
        print(f"高峰 token 单价是空闲的 2 倍; 若高峰用量整体挪到空闲档, "
              f"零售口径账单 ${total_retail_cost:.4f} -> "
              f"${total_retail_cost - peak['retail_cost'] / 2:.4f} "
              f"(省 ${peak['retail_cost'] / 2:.4f}, "
              f"{peak['retail_cost'] / 2 / total_retail_cost * 100:.1f}%)")
    elif rate is None:
        print("V4-Flash 历史价目与 V4.1 不同, 本脚本不给它算「官方理论/可省」列.")

    if args.by_day:
        print(f"\n{'日期':<12}{'周':<4}{'高峰请求':>9}{'高峰USD':>10}{'空闲请求':>9}"
              f"{'空闲USD':>10}{'未分档请求':>11}{'未分档USD':>11}")
        for d in sorted(by_day):
            v = by_day[d]
            wd = "一二三四五六日"[d.weekday()]
            flag = " 假" if d in HOLIDAYS else ""
            print(f"{d!s:<12}{wd}{flag:<3}{int(v['pn']):>9}{v['pc']:>10.4f}"
                  f"{int(v['on']):>9}{v['oc']:>10.4f}{int(v['nn']):>11}{v['nc']:>11.4f}")
    con.close()


if __name__ == "__main__":
    main()
