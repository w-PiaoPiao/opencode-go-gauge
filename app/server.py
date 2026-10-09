"""本地 HTTP 服务: 静态资源 + JSON API + 后台同步."""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from email import utils as email_utils
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__, backup, db
from .autostart import disable as _autostart_disable, enable as _autostart_enable
from .updater import RELEASE_PAGE_URL, check_update, download_update
from .commandcode_api import (
    AuthError as CCAuthError,
    CommandCodeAPIError,
    fetch_quota as cc_fetch_quota,
    fetch_usage_charts as cc_fetch_usage_charts,
    fetch_usage_page as cc_fetch_usage_page,
)
from .db import PROVIDER_COMMANDCODE, PROVIDER_OPENCODE
from .opencode_api import (
    AuthError,
    OpenCodeAPIError,
    fetch_key_names,
    fetch_quota,
    fetch_usage_page,
    iso_to_ms,
    resolve_workspace_id,
)

PAGE_SIZE = 50  # commandcode 明细单页条数
QUOTA_CACHE_TTL = 30.0
PAGE_LIMIT = 100  # opencode /request-logs 单页条数上限
INCREMENTAL_PAGES = 10  # 增量同步最多翻页数 (10*100=1000 条)
MAX_FULL_PAGES = 1000  # 全量同步翻页上限, 防失控 (服务端仅保留 30 天明细)
PAGE_RETRIES = 2  # 单页失败重试次数 (深页偶尔慢/连接被重置)
INCREMENTAL_OVERLAP_MS = 3600_000  # 增量同步回溯 1 小时, 防边界漏记
KEY_NAMES_REFRESH_SEC = 24 * 3600  # key 名称缓存刷新周期 (变化极少, 无需每轮同步都拉)
_key_names_fetched_at: dict[int, float] = {}  # {account_id: 上次成功拉取时刻}


def _resource_path(rel: str) -> str:
    """定位资源文件 (开发/打包后通用)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "app", "web", rel)
    return os.path.join(os.path.dirname(__file__), "web", rel)


# ---------------------------------------------------------------------------
# 同步状态 (跨线程)
# ---------------------------------------------------------------------------

_sync_lock = threading.Lock()
_sync_state: dict[str, Any] = {
    "running": False,
    "mode": "",
    "page": 0,
    "inserted": 0,
    "phase": "idle",  # idle | quota | usage | done | error
    "message": "",
    "account": "",  # 当前正在同步的账号名 (多账号顺序轮询)
}
_quota_cache: dict[int, dict[str, Any]] = {}  # {account_id: {"at": float, "data": ...}}
_quota_refreshing: set[int] = set()  # 防重入: 同一账号同一时刻只允许一个 quota 刷新线程
_quota_gate = threading.Lock()  # check-then-add 原子化 (并发 dashboard 请求)
_exchange_cache: dict[str, Any] = {"at": 0.0, "usd_cny": 7.2}
_EXCHANGE_TTL = 6 * 3600  # 汇率缓存 6 小时
_exchange_refreshing = threading.Event()  # 防重入: 汇率后台刷新单线程
_DEFAULT_USD_CNY = 7.2


def _fetch_usd_cny() -> float:
    """返回 USD→CNY 汇率 (缓存值即时返回, 过期由后台线程刷新, 不阻塞请求)."""
    now = time.time()
    if now - _exchange_cache["at"] >= _EXCHANGE_TTL and not _exchange_refreshing.is_set():
        _exchange_refreshing.set()
        threading.Thread(target=_refresh_exchange_async, daemon=True,
                         name="gousage-fx").start()
    return _exchange_cache["usd_cny"]


def _refresh_exchange_async() -> None:
    """后台刷新汇率: 成功按 TTL 缓存, 失败短重试 (5 分钟), 不阻塞调用方."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://open.er-api.com/v6/latest/USD",
            headers={"User-Agent": "GoGauge/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        rate = float(data.get("rates", {}).get("CNY") or 0)
        if rate > 0:
            _exchange_cache.update(at=time.time(), usd_cny=rate)
        else:
            _exchange_cache["at"] = time.time() - _EXCHANGE_TTL + 300
    except Exception:  # noqa: BLE001 网络失败: 短 TTL 重试, 保留旧值
        _exchange_cache["at"] = time.time() - _EXCHANGE_TTL + 300
    finally:
        _exchange_refreshing.clear()


def _sync_progress_snapshot() -> dict[str, Any]:
    with _sync_lock:
        return dict(_sync_state)


def _set_phase(phase: str, message: str = "") -> None:
    # 只更新 phase/message, 刻意**不**碰 running.
    #
    # running 是同步的单飞闸门, 只能由 sync_usage 的进入/退出来置位与清零.
    # 过去这里写 running = (phase == "usage"), 而 _sync_one_account 在账号失败时
    # 会从 sync_usage 的账号循环内部回调 _set_phase("error") —— 闸门于是被中途
    # 放开, 第二个 POST /api/sync 会被放行并另起一个线程, 两个线程并发写同一批
    # 记录: 新增计数重复累加、增量判定失效, 并发写还可能撞 "database is locked".
    #
    # 配额刷新 (见 _ensure_quota_async) 是独立的非阻塞后台线程, 同样不该改这里.
    with _sync_lock:
        _sync_state["phase"] = phase
        _sync_state["message"] = message


# ---------------------------------------------------------------------------
# 导出/导入路径授权 (confused deputy 防护)
# ---------------------------------------------------------------------------
#
# /api/export/csv、/api/backup/* 过去直接采用请求里的绝对路径写文件, 而本地 HTTP
# 层没有任何鉴权 (只有 Host/Origin 回环校验). 于是同机任意进程可以 POST 一个路径,
# 让本应用以**登录用户**的权限覆写任意可写文件 (已实测覆盖未选中的既有文件).
#
# 真实路径只来自用户在系统对话框里的选择 —— pywebview 的 pick_save_path /
# pick_open_path 与 HTTP 服务同进程, 对话框选中时把路径登记进来, HTTP 侧只认
# 登记过的路径. 前端契约不变 (仍回传路径字符串), 差别只在于路径必须经用户点头.

_APPROVED_PATHS: dict[str, float] = {}
_APPROVED_TTL_SEC = 300.0
_approved_lock = threading.Lock()


def _real_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(str(path))))


def approve_path(path: str) -> None:
    """登记用户在系统对话框中亲自选定的路径 (由 js_api 调用)."""
    real = _real_path(path)
    now = time.time()
    with _approved_lock:
        for key, exp in list(_APPROVED_PATHS.items()):
            if exp < now:
                del _APPROVED_PATHS[key]
        _APPROVED_PATHS[real] = now + _APPROVED_TTL_SEC


def resolve_approved_path(raw: Any) -> Optional[str]:
    """把请求里的路径解析为已登记路径; 未登记 / 已过期返回 None."""
    if not raw:
        return None
    try:
        real = _real_path(raw)
    except (TypeError, ValueError):
        return None
    now = time.time()
    with _approved_lock:
        exp = _APPROVED_PATHS.get(real)
        if exp is None or exp < now:
            _APPROVED_PATHS.pop(real, None)
            return None
        return real


# ---------------------------------------------------------------------------
# 同步执行
# ---------------------------------------------------------------------------


def invalidate_quota_cache(account_id: Optional[int] = None) -> None:
    """凭证变更 (登录/重新登录/新增账号) 后丢弃配额缓存, 让面板按新凭证立即重拉.

    否则在 QUOTA_CACHE_TTL 内仍会读到旧凭证的结果 (通常是 401 失败值), 界面
    表现为"重新登录成功但配额依旧是空的". 在途刷新线程的写回由
    _fetch_quota_with_cache 的缓存槽 identity 校验拦下, 不会把旧凭证结果塞回.
    """
    with _quota_gate:
        if account_id is None:
            _quota_cache.clear()
        else:
            _quota_cache.pop(int(account_id), None)
            # 放行后续刷新: 不清则 _ensure_quota_async 会认为"已有线程在跑"而不重拉
            _quota_refreshing.discard(int(account_id))


def _fetch_quota_with_cache(account_id: int, token: str, workspace_hint: str, provider: str = PROVIDER_OPENCODE) -> dict[str, Any]:
    slot = _quota_cache.setdefault(account_id, {"at": 0.0, "data": None})
    now = time.time()
    if slot["data"] and now - slot["at"] < QUOTA_CACHE_TTL:
        return slot["data"]
    if provider == PROVIDER_COMMANDCODE:
        result = cc_fetch_quota(token)
    else:
        result = fetch_quota(token, workspace_hint)
    data = result.to_dict()
    # 缓存槽已被凭证变更清掉 (relogin): 丢弃本次结果, 否则旧 token 的结果会落进
    # 新槽并在 TTL 内被当成新凭证的配额返回
    if _quota_cache.get(account_id) is not slot:
        return data
    # 取**请求前**的 now 会让实际有效期变成 TTL + 本次网络耗时, 慢网下配额
    # 比声明的 30s 更久不刷新; 取请求后的时刻才是"多久之后可再拉"的真实起点
    slot["at"] = time.time()
    slot["data"] = data
    _record_cycle_bounds(account_id, data)
    return data


def _record_cycle_bounds(account_id: int, quota: dict[str, Any]) -> None:
    """配额拉取成功后持久化计费周期边界 (供「本周期」筛选取起点).

    真实周期 (GOAT subscriptions / Go 的 access.startsAt·endsAt) 一律落库 —— 只有
    「下次重置」的旧口径要靠回推推算, 而 Go 月度周期实测按自然月 (31 天), 回推
    30 天会得到未来起点、「本周期」筛出 0 条. 两者都记录: 真实周期缺位时
    (老接口/异常响应) 回推路径仍有新鲜的「下次重置」兜底.
    """
    try:
        if quota.get("period_start") and quota.get("period_end"):
            db.record_period_bounds(account_id, quota["period_start"], quota["period_end"])
        for window in quota.get("windows") or []:
            if window.get("label") == "Monthly" and window.get("reset_at"):
                db.record_monthly_reset(account_id, window["reset_at"])
                break
    except Exception:  # noqa: BLE001 持久化失败不影响配额返回
        pass


def _ensure_quota_async(account_id: Optional[int] = None) -> None:
    """若该账号配额缓存过期, 在后台线程刷新 (不阻塞 dashboard 响应, 防重入).

    支持任意账号 (非活跃账号凭证从 accounts 表直接读取, 供账户总览面板使用).
    """
    aid = account_id or db.get_active_account_id()
    if not aid:
        return
    slot = _quota_cache.get(aid)
    now = time.time()
    if slot and slot["data"] and now - slot["at"] < QUOTA_CACHE_TTL:
        return
    token, workspace_hint, provider = db.get_account_credentials(aid)
    if not token:
        return
    # check-then-add 原子化: 并发 dashboard 请求只放一个刷新线程过去
    with _quota_gate:
        if aid in _quota_refreshing:
            return  # 该账号已有刷新线程在跑
        _quota_refreshing.add(aid)

    def worker() -> None:
        try:
            # 失败也写入缓存 (None), TTL 内不再重试, 避免前端无限刷新
            _fetch_quota_with_cache(aid, token, workspace_hint, provider)
        except Exception:  # noqa: BLE001
            # 缓存槽已被凭证变更清掉时不再回写 (也不重建): 让下次请求按新凭证重拉
            slot = _quota_cache.get(aid)
            if slot is None:
                return
            if slot.get("data"):
                # 保留上次成功的配额 (界面不闪空), 仅把时间戳拨到短退避点:
                # 30s 后才允许后台再试, 不随每个请求都触发刷新线程
                slot["at"] = time.time() - QUOTA_CACHE_TTL + 30.0
            else:
                slot["at"] = time.time()
                slot["data"] = None
        finally:
            _quota_refreshing.discard(aid)

    threading.Thread(target=worker, daemon=True, name="gousage-quota").start()


def _max_pages_for(mode: str) -> int:
    """全量/增量的页数上限 (两种 provider 共用, 避免各自定义漂移)."""
    return MAX_FULL_PAGES if mode == "full" else INCREMENTAL_PAGES


def _window_boundary_hit(records: Any, mode: str, window_days: Optional[int]) -> bool:
    """全量同步时判断本页是否已越过同步范围边界 (最早记录早于 今天-window_days).

    该页整页保留后再停止: 保证边界附近不丢数据, 又不继续向更早翻页.
    """
    if mode != "full" or window_days is None:
        return False
    earliest = min((r.created_at for r in records), default="")
    if not earliest:
        return False
    try:
        et = datetime.fromisoformat(earliest.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    return et < datetime.now(timezone.utc) - timedelta(days=window_days)


def _incremental_done(inserted: int, empty_batches: int, mode: str) -> tuple[bool, int]:
    """增量模式的停止判定: 连续两批 0 新增 (全是旧数据) 即认为已追平.

    Returns: (是否停止, 更新后的 empty_batches 计数)
    """
    if mode == "incremental" and inserted == 0:
        empty_batches += 1
        return empty_batches >= 2, empty_batches
    return False, 0


def _finish_sync(
    account_id: int,
    total_inserted: int,
    pages: int,
    *,
    failed_pages: int = 0,
    charts_ok: bool = True,
    retention_days: Optional[int] = None,
) -> dict[str, Any]:
    """两种 provider 共用的收尾: 按失败维度写状态并构造返回体.

    统一 partial 语义 (此前 opencode 报 partial, commandcode 分支另有措辞,
    且失败信息不一致), 保证前端看到同一种状态形状. retention_days 是
    opencode 控制台接口上报的明细保留天数 (commandcode 无此概念, 传 None).
    """
    if failed_pages:
        msg = "完成, 但翻页中断 (数据不完整, 可再次全量同步补全)"
        db.update_sync_state("partial", msg, total_inserted, account_id)
        return {"ok": True, "partial": True, "failed_pages": failed_pages,
                "inserted": total_inserted, "pages": pages}
    if not charts_ok:
        msg = "完成, 但聚合数据拉取失败 (统计暂缺全周期数据, 下次同步自动重试)"
        db.update_sync_state("partial", msg, total_inserted, account_id)
        return {"ok": True, "partial": True, "inserted": total_inserted, "pages": pages}
    db.update_sync_state("ok", None, total_inserted, account_id)
    return {"ok": True, "inserted": total_inserted, "pages": pages,
            "retention_days": retention_days}


def _sync_one_account(
    account_id: int, name: str, mode: str, window_days: Optional[int]
) -> dict[str, Any]:
    """同步单个账号的用量记录 (显式传入账号上下文, 按 provider 分流)."""
    # 凭证经 _storage_decode 解出 (frozen 下库内为加密形态)
    token_str, workspace_hint, provider = db.get_account_credentials(account_id)
    if not token_str:
        return {"ok": False, "error": "未登录"}
    workspace_id = workspace_hint

    with _sync_lock:
        _sync_state.update(account=name)

    try:
        # commandcode: 无 workspace 概念, 游标翻页; opencode: 页式 + workspace 解析
        if provider == PROVIDER_COMMANDCODE:
            return _sync_one_cc_account(account_id, name, token_str, mode, window_days)

        # ---------- opencode: /console/api 游标分页 (按时间倒序, 无法并发跳页) ----------
        # 确保工作区 ID 已解析
        try:
            resolved = resolve_workspace_id(workspace_id, token_str)
            if not workspace_id.startswith("wrk_"):
                workspace_id = resolved
                db.save_resolved_workspace(resolved, account_id)
        except (AuthError, OpenCodeAPIError) as exc:
            _set_phase("error", f"[{name}] 工作区解析失败: {exc}")
            db.update_sync_state("error", str(exc), 0, account_id)
            return {"ok": False, "error": str(exc)}

        total_inserted = 0
        max_pages = _max_pages_for(mode)
        page = 0
        cursor: Optional[str] = None
        empty_pages = 0
        failed_pages = 0
        page_retries = 0
        window_boundary_reached = False
        retention_days: Optional[int] = None

        # 增量同步: 只取最新记录之后的一段时间 (重叠 1 小时防边界漏记),
        # 命中不到旧数据就不会去翻历史页, 既快又少请求
        since_ms: Optional[int] = None
        if mode != "full":
            newest_local = (db.get_sync_state(account_id) or {}).get("newest_record_at")
            if newest_local:
                stamp = iso_to_ms(newest_local) - INCREMENTAL_OVERLAP_MS
                since_ms = stamp if stamp > 0 else None

        while page < max_pages:
            with _sync_lock:
                _sync_state["page"] = page
            try:
                usage_page = fetch_usage_page(
                    token_str, workspace_id, cursor=cursor, limit=PAGE_LIMIT,
                    since_ms=since_ms,
                )
            except AuthError as exc:
                _set_phase("error", f"[{name}] {exc}")
                db.update_sync_state("error", str(exc), total_inserted, account_id)
                return {"ok": False, "error": str(exc), "partial_inserted": total_inserted}
            except OpenCodeAPIError as exc:
                # 首页即失败 -> 整体报错; 翻页中途失败 -> 同一游标重试, 仍失败则保留已入库数据
                if page == 0:
                    _set_phase("error", f"[{name}] {exc}")
                    db.update_sync_state("error", str(exc), 0, account_id)
                    return {"ok": False, "error": str(exc)}
                if page_retries < PAGE_RETRIES:
                    page_retries += 1
                    time.sleep(1.5 * page_retries)
                    continue
                failed_pages += 1
                break

            page += 1
            page_retries = 0
            if usage_page.retention_days:
                retention_days = usage_page.retention_days
            records = usage_page.records

            inserted = 0
            if records:
                # 同步范围: 全量拉取时, 若本页最早记录早于窗口边界 -> 该页保留后停止
                # (与 commandcode 分支共用同一判定, 此前这里内联了一份等价逻辑)
                if _window_boundary_hit(records, mode, window_days):
                    window_boundary_reached = True
                inserted = db.insert_usage_records(
                    [r.to_db_dict() for r in records], account_id
                )
                total_inserted += inserted
                with _sync_lock:
                    _sync_state["inserted"] = total_inserted
            # 增量停止判定与 commandcode 同一实现: 连续两批 0 新增 (空页同计) 即追平
            stop, empty_pages = _incremental_done(inserted, empty_pages, mode)

            cursor = usage_page.next_cursor
            if not cursor:
                break  # 已到最早一条
            if window_boundary_reached:
                break
            if stop:
                break

        # 按同步范围裁剪窗口外记录 (与本次新增数独立)
        if window_days is not None:
            db.prune_old_records(window_days, account_id)

        # 顺带刷新该账号的 key 显示名称缓存 (合并写入: key_id 全局唯一,
        # 多账号各补各的条目; 单账号失败不影响已有缓存).
        # 24h 内不重复拉取: keys 页面是一个完整网络请求 + settings 整包读改写,
        # 而名称变化极少, 没必要每轮增量同步都跑一遍.
        now = time.time()
        if now - _key_names_fetched_at.get(account_id, 0.0) > KEY_NAMES_REFRESH_SEC:
            try:
                fresh_keys = fetch_key_names(token_str, workspace_id)
                merged = dict(db.get_key_names())
                merged.update(fresh_keys)
                db.save_key_names(merged)
                _key_names_fetched_at[account_id] = now
            except Exception:  # noqa: BLE001
                pass

        return _finish_sync(account_id, total_inserted, page,
                            failed_pages=failed_pages, retention_days=retention_days)
    except Exception as exc:  # noqa: BLE001
        db.update_sync_state("error", str(exc), 0, account_id)
        return {"ok": False, "error": str(exc)}


def _sync_one_cc_account(
    account_id: int, name: str, token: str, mode: str, window_days: Optional[int]
) -> dict[str, Any]:
    """同步单个 Command Code 账号: 明细游标翻页 + charts 全周期聚合落库."""
    total_inserted = 0
    pages = 0
    cursor: Optional[str] = None
    empty_batches = 0
    failed_pages = 0
    window_boundary_reached = False

    max_pages = _max_pages_for(mode)
    try:
        while pages < max_pages:
            with _sync_lock:
                _sync_state["page"] = pages
            try:
                records, next_cursor = cc_fetch_usage_page(token, cursor, PAGE_SIZE)
            except (CCAuthError, CommandCodeAPIError) as exc:
                if mode == "incremental":
                    _set_phase("error", f"[{name}] 第 {pages + 1} 页拉取失败: {exc}")
                    db.update_sync_state("error", str(exc), total_inserted, account_id)
                    return {"ok": False, "error": str(exc), "partial_inserted": total_inserted}
                failed_pages += 1
                break
            if not records:
                break  # 没有更多数据

            if _window_boundary_hit(records, mode, window_days):
                window_boundary_reached = True

            inserted = db.insert_usage_records(
                [r.to_db_dict() for r in records], account_id
            )
            total_inserted += inserted
            pages += 1
            with _sync_lock:
                _sync_state["inserted"] = total_inserted

            if window_boundary_reached:
                break
            # 游标翻页: 无 next_cursor 即到底
            if not next_cursor:
                break
            stop, empty_batches = _incremental_done(inserted, empty_batches, mode)
            if stop:
                break
            cursor = next_cursor

        # 按同步范围裁剪窗口外记录
        if window_days is not None:
            db.prune_old_records(window_days, account_id)

        # commandcode 无 key 名称概念, 不需要 fetch_key_names

        # charts 聚合 (全计费周期, 模型×5min 桶): 补全明细接口 24h/100 条之外的
        # 历史统计 (统计面板的 totals/趋势/模型占比以聚合表为准). 独立容错:
        # 失败仅标记 partial, 不影响已落库明细, 下次同步自动重试.
        charts_ok = True
        try:
            chart_rows = cc_fetch_usage_charts(token)
            db.insert_usage_charts([r.to_db_dict() for r in chart_rows], account_id)
        except Exception:  # noqa: BLE001
            charts_ok = False

        return _finish_sync(
            account_id, total_inserted, pages,
            failed_pages=failed_pages, charts_ok=charts_ok,
        )
    except Exception as exc:  # noqa: BLE001
        db.update_sync_state("error", str(exc), total_inserted, account_id)
        return {"ok": False, "error": str(exc), "partial_inserted": total_inserted}


def sync_usage(mode: str = "incremental") -> dict[str, Any]:
    """同步用量记录.

    - incremental: 顺序轮询所有已登录账号 (各账号独立游标/状态)
    - full: 仅对当前活跃账号全量拉取
    进度快照在原有字段上追加 account (当前正在同步的账号名), 前端兼容旧字段.
    """
    window_days = db.get_settings().get("window_days")

    if mode == "full":
        aid = db.get_active_account_id()
        targets = [(aid, db.get_account().get("name") or f"#{aid}")] if aid and db.get_token() else []
    else:
        targets = [
            (a["id"], a["name"]) for a in db.list_accounts() if a["has_token"]
        ]
    if not targets:
        return {"ok": False, "error": "未登录"}

    with _sync_lock:
        if _sync_state["running"]:
            return {"ok": False, "error": "已有同步任务进行中"}
        _sync_state.update(running=True, mode=mode, page=0, inserted=0, phase="usage", message="")

    try:
        total_inserted = 0
        errors: list[str] = []
        partial = False
        pages = 0
        # 单账号失败不中断整轮同步: 此前 incremental 直接 return, 导致首个
        # token 过期的账号会永久阻塞其后所有账号的自动同步 (定时器每轮撞同一处).
        for aid, name in targets:
            result = _sync_one_account(aid, name, mode, window_days)
            total_inserted += int(result.get("inserted") or 0)
            pages += int(result.get("pages") or 0)
            if not result.get("ok"):
                errors.append(f"[{name}] {result.get('error') or '同步失败'}")
            if result.get("partial"):
                partial = True

        any_error = "; ".join(errors)
        # 全部账号都失败才算整轮失败; 任一成功即为 partial (前端展示警告但不报错)
        if errors and len(errors) == len(targets):
            _set_phase("error", any_error)
            return {"ok": False, "error": any_error, "partial_inserted": total_inserted}
        if partial or errors:
            msg = "部分账号同步异常" if errors else "完成, 但部分页面拉取失败"
            _set_phase("done", msg)
            return {
                "ok": True, "partial": True, "inserted": total_inserted,
                "pages": pages, "errors": errors,
            }
        _set_phase("done", f"同步完成, 新增 {total_inserted} 条")
        return {"ok": True, "inserted": total_inserted, "pages": pages}
    except Exception as exc:  # noqa: BLE001
        _set_phase("error", str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        with _sync_lock:
            _sync_state["running"] = False


def sync_all_async(mode: str) -> None:
    """后台线程执行 用量同步 (配额由独立后台线程刷新, 不阻塞用量)."""
    def worker() -> None:
        try:
            _ensure_quota_async()  # 触发配额后台刷新 (独立线程, 防重入)
            sync_usage(mode)
        except Exception:  # noqa: BLE001
            _set_phase("error", "同步失败")

    thread = threading.Thread(target=worker, daemon=True, name="gousage-sync")
    thread.start()


# ---------------------------------------------------------------------------
# HTTP 服务
# ---------------------------------------------------------------------------

_on_open_login: Optional[Callable[[str, str], None]] = None
_server: Optional[ThreadingHTTPServer] = None

# 半自动更新下载状态机: idle -> checking -> downloading -> done/no_update/no_asset/error
_update_download: dict[str, Any] = {"state": "idle", "path": "", "error": "", "latest": ""}
_update_lock = threading.Lock()  # 下载状态机原子占位: 防并发双开写坏同一 .part


def _update_download_worker() -> None:
    """后台下载新版本 zip 到 ~/Downloads, 完成后在 Finder 中定位."""
    try:
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        result = download_update(downloads)
        _update_download.update(result)
        if result.get("state") == "done" and result.get("path"):
            import subprocess

            if sys.platform == "win32":
                # Windows: 资源管理器定位文件 (open -R 仅 macOS)
                subprocess.Popen(["explorer", "/select,", os.path.normpath(result["path"])])
            else:
                subprocess.Popen(["open", "-R", result["path"]])
    except Exception as exc:  # noqa: BLE001
        _update_download.update({"state": "error", "error": str(exc)[:300]})


def set_login_callback(callback: Callable[[str, str], None]) -> None:
    """由 main.py 注册: 前端请求登录时触发窗口跳转.

    回调契约: callback(mode, provider), mode 为 "add" (添加新用户) 或
    "relogin" (重新登录当前用户), provider 为 "opencode" / "commandcode".
    """
    global _on_open_login
    _on_open_login = callback


_MAX_BODY_BYTES = 1 << 20  # 1 MiB: 本地接口请求体上限 (防异常声明挂死线程)


def _read_json_body(handler: BaseHTTPRequestHandler) -> Any:
    """读取并解析 JSON 请求体, 失败抛 ValueError."""
    length = int(handler.headers.get("Content-Length") or 0)
    # 必须一并挡掉负数: rfile.read(-1) 语义是"读到 EOF", 会一直阻塞到
    # Handler.timeout (15s). ThreadingHTTPServer 下每个畸形请求白占一个线程.
    if length < 0 or length > _MAX_BODY_BYTES:
        raise ValueError("请求体大小非法")
    return json.loads(handler.rfile.read(length).decode("utf-8", errors="replace"))


def _json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _static_response(handler: BaseHTTPRequestHandler, rel: str) -> None:
    # 防目录穿越: 单纯过滤 '..' 不够 —— Windows 下 os.path.join 遇到盘符绝对
    # 组件会丢弃前缀 (GET /C:/Users/.../gousage.db 可读任意文件). 解码后做
    # realpath 包含校验, 双平台都强制落在资源目录内.
    rel = unquote(rel or "").lstrip("/")
    if ".." in rel.replace("\\", "/").split("/"):
        handler.send_error(403)
        return
    path = _resource_path(rel)
    root = os.path.normcase(os.path.dirname(os.path.realpath(_resource_path("index.html"))))
    real = os.path.normcase(os.path.realpath(path))
    if real != root and not real.startswith(root + os.sep):
        handler.send_error(403)
        return
    if not os.path.isfile(path):
        handler.send_error(404)
        return
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    try:
        st = os.stat(path)
    except OSError:
        handler.send_error(404)
        return
    # 弱校验: 大小 + mtime 纳秒 (文件极小概率同刻变更, 对本地静态资源足够).
    # 原先恒定 no-cache 且无校验器, 每次窗口刷新都要重下 app.js/图表库.
    etag = f'W/"{st.st_size:x}-{st.st_mtime_ns:x}"'
    last_modified = email_utils.formatdate(st.st_mtime, usegmt=True)
    if handler.headers.get("If-None-Match") == etag:
        handler.send_response(304)
        handler.send_header("ETag", etag)
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        return
    ims = handler.headers.get("If-Modified-Since")
    if ims and not handler.headers.get("If-None-Match"):
        try:
            if email_utils.parsedate_to_datetime(ims).timestamp() >= int(st.st_mtime):
                handler.send_response(304)
                handler.send_header("ETag", etag)
                handler.send_header("Cache-Control", "no-cache")
                handler.end_headers()
                return
        except (TypeError, ValueError):
            pass  # 非法日期头: 按普通 GET 处理
    try:
        with open(path, "rb") as fh:
            body = fh.read()
    except OSError:
        handler.send_error(500)
        return
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    # no-cache = 允许缓存但每次需校验 (304 时无 body, 省下重复传输)
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("ETag", etag)
    handler.send_header("Last-Modified", last_modified)
    handler.end_headers()
    handler.wfile.write(body)


def _handle_api(handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]]) -> None:
    method = handler.command
    route = path

    if route == "/api/version" and method == "GET":
        _json_response(handler, {"version": __version__})
        return

    if route == "/api/update/check" and method == "GET":
        try:
            _json_response(handler, check_update())
        except Exception as exc:  # noqa: BLE001 网络/解析失败 -> 前端提示
            _json_response(handler, {"error": str(exc)}, status=502)
        return

    if route == "/api/update/open" and method == "POST":
        # 用系统默认浏览器打开 GitHub Releases 页 (WebView 内 window.open 不可靠)
        import webbrowser

        webbrowser.open(RELEASE_PAGE_URL)
        _json_response(handler, {"ok": True})
        return

    if route == "/api/state" and method == "GET":
        account = db.get_account()
        sync = db.get_sync_state()
        _json_response(
            handler,
            {
                "logged_in": bool(db.count_logged_in_accounts()),
                "account": account,
                "accounts": db.list_accounts(),
                "accounts_total": db.count_accounts(),
                "accounts_logged_in": db.count_logged_in_accounts(),
                "sync": sync,
                "progress": _sync_progress_snapshot(),
                "datadir": db.data_dir(),
            },
        )
        return

    if route == "/api/sync" and method == "POST":
        mode = (query.get("mode") or ["incremental"])[0]
        if mode not in ("incremental", "full"):
            _json_response(handler, {"ok": False, "error": "invalid mode"}, 400)
            return
        # incremental 轮询所有已登录账号; full 仅作用于活跃账号 (需其 token)
        if mode == "incremental":
            if not db.count_logged_in_accounts():
                _json_response(handler, {"ok": False, "error": "未登录"}, 401)
                return
        elif not db.get_token():
            _json_response(handler, {"ok": False, "error": "未登录"}, 401)
            return
        sync_all_async(mode)
        _json_response(handler, {"ok": True})
        return

    if route == "/api/dashboard" and method == "GET":
        # 时间范围: today / 7d / 30d / month / all
        range_param = query.get("range", ["today"])[0]
        if range_param == "today":
            period, days = "today", 1
        elif range_param == "7d":
            period, days = "7d", 7
        elif range_param == "month":
            period, days = "month", 31
        elif range_param == "all":
            period, days = "all", 365
        else:
            period, days = "30d", 30
        token = db.get_token()
        # 统计页「排除模型」筛选 (模型用量环形图图例点击): 可重复查询参数,
        # 逐项清洗 — 去空白/去重/长度与数量上限, 防止超长 WHERE 拖慢聚合
        exclude_models: list[str] = []
        for raw in query.get("exclude_models", []):
            name = (raw or "").strip()
            if name and len(name) <= 200 and name not in exclude_models:
                exclude_models.append(name)
            if len(exclude_models) >= 50:
                break
        # quota 使用缓存 (按账号分槽), 过期时后台刷新, 不阻塞 dashboard 响应
        active_id = db.get_active_account_id()
        _ensure_quota_async(active_id)
        slot = _quota_cache.get(active_id) or {}
        quota = slot.get("data") if token else None
        account = db.get_account()
        # 显式透传 active_id: 各聚合内部若收到 None 会各自重跑
        # get_active_account_id() (settings 读取 + JSON 解析 + MIN(id) 查询),
        # 一次 dashboard 会重复 7 次.
        totals_period = db.totals(period, active_id, exclude_models)
        # 首页默认 range 即 today: 此时 totals(period) 与 totals("today") 是
        # 同一个查询, 复用结果省一次聚合 (弱机上聚合是 dashboard 的 CPU 大头)
        totals_today = (
            totals_period if period == "today" else db.totals("today", active_id, exclude_models)
        )
        # 近 7 天趋势是 30 天序列的后缀子集: 一次聚合切片复用, 省一条按天 GROUP BY
        daily30 = db.daily_stats(30, active_id, exclude_models)
        _json_response(
            handler,
            {
                "logged_in": bool(token),
                "account": account,
                "account_name": account.get("name", ""),
                "accounts_total": db.count_accounts(),
                "accounts_logged_in": db.count_logged_in_accounts(),
                "quota": quota,
                "totals": totals_period,
                "today": totals_today,
                "daily": daily30[-7:],  # 每日趋势固定显示近 7 天
                "trend": daily30,  # 用量趋势 (费用/请求双轴)
                "today_trend": db.today_trend(active_id),  # 今日 24 小时趋势
                # models 始终全量: 环形图需保留被排除模型 (图例删除线 + 点击即加回),
                # 排行由前端按 excluded_models 过滤; 排除只作用于 totals/trend 聚合
                "models": db.model_stats(period, active_id),
                "excluded_models": exclude_models,  # 回显生效的排除项
                "sync": db.get_sync_state(active_id),
                "progress": _sync_progress_snapshot(),
                "range": range_param,
                "exchange_rate": {"usd_cny": _fetch_usd_cny(), "currency": "CNY"},
                "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        return

    if route == "/api/logout" and method == "POST":
        # 退出前记录账号 id, 退出后清理其配额缓存槽 (防止残留旧配额);
        # 同步丢弃在途刷新防重启标记, 避免进行中的 worker 把弹出的槽位塞回去
        aid = db.get_active_account_id()
        db.clear_account()
        if aid:
            _quota_cache.pop(aid, None)
            _quota_refreshing.discard(aid)
        _json_response(handler, {"ok": True})
        return

    if route == "/api/relogin" and method == "POST":
        provider = (query.get("provider") or ["opencode"])[0]
        if provider not in (PROVIDER_OPENCODE, PROVIDER_COMMANDCODE):
            provider = PROVIDER_OPENCODE
        if _on_open_login:
            _on_open_login("relogin", provider)
        _json_response(handler, {"ok": True})
        return

    # ---------------- 多账号管理 ----------------

    if route == "/api/accounts" and method == "GET":
        _json_response(
            handler,
            {
                "ok": True,
                "accounts": db.list_accounts(),
                "active_id": db.get_active_account_id(),
            },
        )
        return

    if route == "/api/accounts/overview" and method == "GET":
        # 账户总览面板: 仅返回已登录账号 (退出登录即移除本地数据, 未登录账号无展示意义)
        active_id = db.get_active_account_id()
        accounts: list[dict[str, Any]] = []
        for acc in db.list_accounts():
            if not acc["has_token"]:
                continue
            aid = acc["id"]
            # 过期配额后台刷新 (不阻塞响应), 本次先返回缓存值
            _ensure_quota_async(aid)
            slot = _quota_cache.get(aid)
            quota = slot.get("data") if slot else None
            sync_state = db.get_sync_state(aid)
            accounts.append(
                {
                    "id": aid,
                    "name": acc["name"],
                    "logged_in": True,
                    "active": aid == active_id,
                    "provider": acc.get("provider") or PROVIDER_OPENCODE,
                    "quota": quota,
                    "today": db.totals("today", aid),
                    "today_trend": db.today_trend(aid),
                    "daily7": db.daily_stats(7, aid),
                    "last_sync_at": sync_state.get("last_sync_at"),
                    "last_sync_status": sync_state.get("last_sync_status"),
                }
            )
        _json_response(
            handler,
            {
                "ok": True,
                "accounts": accounts,
                "active_id": active_id,
                "exchange_rate": {"usd_cny": _fetch_usd_cny(), "currency": "CNY"},
                "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        return

    if route.startswith("/api/accounts/") and method == "POST":
        try:
            body = _read_json_body(handler)
            if not isinstance(body, dict):
                raise ValueError
        except Exception:  # noqa: BLE001
            _json_response(handler, {"ok": False, "error": "无效请求体"}, 400)
            return
        action = route[len("/api/accounts/"):]

        if action == "switch":
            try:
                aid = int(body.get("id"))
            except (TypeError, ValueError):
                aid = 0
            row = db.get_db().execute(
                "SELECT TRIM(token) AS t FROM accounts WHERE id = ?", (aid,)
            ).fetchone() if aid else None
            if row is None:
                _json_response(handler, {"ok": False, "error": "账号不存在"}, 404)
                return
            if not row["t"]:
                _json_response(handler, {"ok": False, "error": "该账号未登录"}, 400)
                return
            db.set_active_account(aid)
            _json_response(handler, {"ok": True, "active_id": aid})
            return

        if action == "rename":
            try:
                aid = int(body.get("id"))
            except (TypeError, ValueError):
                aid = 0
            if not db.rename_account(aid, str(body.get("name") or "")):
                _json_response(handler, {"ok": False, "error": "重命名失败 (账号不存在或名称为空)"}, 400)
                return
            _json_response(handler, {"ok": True})
            return

        if action == "delete":
            try:
                aid = int(body.get("id"))
            except (TypeError, ValueError):
                aid = 0
            remaining = db.delete_account(aid) if aid else -1
            if remaining < 0:
                _json_response(handler, {"ok": False, "error": "无效账号 id"}, 400)
                return
            _quota_cache.pop(aid, None)  # 清理该账号的配额缓存槽
            _key_names_fetched_at.pop(aid, None)  # key 名称刷新时间戳一并回收
            _json_response(handler, {"ok": True, "remaining": remaining})
            return

        if action == "add":
            # 触发登录窗口 (add 模式, 带 provider); 无窗口环境 (纯浏览器/冒烟) 时返回未打开状态
            provider = str(body.get("provider") or PROVIDER_OPENCODE)
            if provider not in (PROVIDER_OPENCODE, PROVIDER_COMMANDCODE):
                provider = PROVIDER_OPENCODE
            opened = bool(_on_open_login)
            if opened:
                _on_open_login("add", provider)
            _json_response(handler, {"ok": True, "opened": opened})
            return

        if action == "add-token":
            # 手动粘贴 token/cookie 登录 (commandcode 内嵌登录窗不可用时的兜底,
            # opencode 也可用). 先校验有效性再落库.
            provider = str(body.get("provider") or PROVIDER_OPENCODE)
            if provider not in (PROVIDER_OPENCODE, PROVIDER_COMMANDCODE):
                provider = PROVIDER_OPENCODE
            token = str(body.get("token") or "").strip()
            if not token:
                _json_response(handler, {"ok": False, "error": "token 为空"}, 400)
                return
            try:
                # 校验: 拉一次配额确认凭证可用
                if provider == PROVIDER_COMMANDCODE:
                    result = cc_fetch_quota(token)
                else:
                    result = fetch_quota(token, "Default")
                if not result.success:
                    _json_response(handler, {"ok": False, "error": result.error or "凭证无效"}, 400)
                    return
            except Exception as exc:  # noqa: BLE001
                _json_response(handler, {"ok": False, "error": str(exc)}, 400)
                return
            try:
                aid = db.add_account(token, "", switch=True, provider=provider)
            except Exception as exc:  # noqa: BLE001
                _json_response(handler, {"ok": False, "error": str(exc)}, 500)
                return
            _json_response(handler, {"ok": True, "id": aid, "provider": provider})
            return

        _json_response(handler, {"ok": False, "error": "未知操作"}, 404)
        return

    if route == "/api/usage/records" and method == "GET":
        try:
            page = max(1, int(query.get("page", ["1"])[0]))
        except ValueError:
            page = 1
        try:
            page_size = max(1, min(int(query.get("page_size", ["50"])[0]), 100))
        except ValueError:
            page_size = 50
        model = query.get("model", [""])[0] or None
        days_raw = query.get("days", [""])[0]
        try:
            days = max(1, min(int(days_raw), 365)) if days_raw else None
        except ValueError:
            days = None
        records, total = db.usage_records_page(page, page_size, model, days)
        key_names = db.get_key_names()
        for rec in records:
            rec["key_name"] = key_names.get(rec.get("key_id") or "", "")
        _json_response(
            handler,
            {
                "records": records,
                "total": total,
                "page": page,
                "page_size": page_size,
                "models": db.list_models(),
                "filter": {"model": model, "days": days},
            },
        )
        return

    if route == "/api/usage/sessions" and method == "GET":
        try:
            page = max(1, int(query.get("page", ["1"])[0]))
        except ValueError:
            page = 1
        try:
            page_size = max(1, min(int(query.get("page_size", ["10"])[0]), 50))
        except ValueError:
            page_size = 10
        days_raw = query.get("days", [""])[0]
        try:
            days = max(1, min(int(days_raw), 365)) if days_raw else None
        except ValueError:
            days = None
        records, total = db.session_stats_page(page, page_size, days)
        key_names = db.get_key_names()
        for rec in records:
            rec["key_name"] = key_names.get(rec.get("key_id") or "", "")
            # 无 session 的行分组键为 key_id (key_/sk_ 前缀), 前端据此显示"未归属"
            if rec["session_id"] and rec["session_id"].startswith(("key_", "sk_")):
                rec["session_id"] = ""
        _json_response(
            handler,
            {
                "records": records,
                "total": total,
                "page": page,
                "page_size": page_size,
                "filter": {"days": days},
            },
        )
        return

    if route == "/api/heatmap" and method == "GET":
        # 日历热力图 (v2.2.0b): 近 N 天逐日聚合 (默认 18 周), 统计页独立拉取
        try:
            days = max(7, min(int(query.get("days", ["126"])[0]), 365))
        except ValueError:
            days = 126
        active_id = db.get_active_account_id()
        _json_response(handler, {"days": db.daily_stats(days, active_id)})
        return

    if route == "/api/export/csv" and method == "POST":
        try:
            body = _read_json_body(handler)
            path = resolve_approved_path((body or {}).get("path"))
        except Exception:  # noqa: BLE001
            path = None
        if not path:
            _json_response(handler, {"ok": False, "error": "导出路径未授权, 请重新选择保存位置"}, 403)
            return
        try:
            rows = backup.export_csv(path)
            _json_response(handler, {"ok": True, "path": path, "rows": rows})
        except Exception as exc:  # noqa: BLE001
            _json_response(handler, {"ok": False, "error": str(exc)}, 500)
        return

    if route == "/api/backup/export" and method == "POST":
        try:
            body = _read_json_body(handler)
            path = resolve_approved_path((body or {}).get("path"))
        except Exception:  # noqa: BLE001
            path = None
        if not path:
            _json_response(handler, {"ok": False, "error": "导出路径未授权, 请重新选择保存位置"}, 403)
            return
        try:
            n = backup.export_backup(path)
            _json_response(handler, {"ok": True, "path": path, "records": n})
        except Exception as exc:  # noqa: BLE001
            _json_response(handler, {"ok": False, "error": str(exc)}, 500)
        return

    if route == "/api/backup/import" and method == "POST":
        try:
            body = _read_json_body(handler)
            path = resolve_approved_path((body or {}).get("path"))
        except Exception:  # noqa: BLE001
            path = None
        if not path:
            _json_response(handler, {"ok": False, "error": "备份路径未授权, 请重新选择文件"}, 403)
            return
        try:
            result = backup.import_backup(path)
            _json_response(handler, {"ok": True, **result})
        except Exception as exc:  # noqa: BLE001
            _json_response(handler, {"ok": False, "error": str(exc)}, 500)
        return

    if route == "/api/settings" and method == "GET":
        _json_response(handler, db.get_settings())
        return

    if route == "/api/settings" and method == "PUT":
        try:
            body = _read_json_body(handler)
            if not isinstance(body, dict):
                raise ValueError
        except Exception:  # noqa: BLE001
            _json_response(handler, {"ok": False, "error": "无效请求体"}, 400)
            return
        old_autostart = bool(db.get_settings().get("autostart"))
        saved = db.save_settings(body)
        new_autostart = bool(saved.get("autostart"))
        # 开机自启副作用: 设置变化时注册/注销 LaunchAgent (仅 mac 打包版实际生效)
        if new_autostart != old_autostart:
            try:
                ok = _autostart_enable() if new_autostart else _autostart_disable()
            except Exception:  # noqa: BLE001
                ok = False
            if not ok:
                saved["autostart_applied"] = False
            else:
                saved["autostart_applied"] = True
        else:
            saved["autostart_applied"] = True
        _json_response(handler, saved)
        return

    if route == "/api/update/download" and method == "POST":
        with _update_lock:
            if _update_download["state"] in ("checking", "downloading"):
                _json_response(handler, {"ok": False, "error": "下载进行中"}, 409)
                return
            _update_download.update({"state": "checking", "path": "", "error": "", "latest": ""})
        threading.Thread(target=_update_download_worker, daemon=True,
                         name="gousage-update-dl").start()
        _json_response(handler, {"ok": True})
        return

    if route == "/api/update/download/status" and method == "GET":
        _json_response(handler, dict(_update_download))
        return

    handler.send_error(404)


class _Handler(BaseHTTPRequestHandler):
    server_version = "GoGauge/1.0"
    timeout = 15  # socket 读超时: 防异常客户端声明超大 Content-Length 挂死线程

    def log_message(self, fmt: str, *args: Any) -> None:  # 静默日志
        pass

    def _reject_non_local(self) -> bool:
        """请求来自本机才处理. Host 必须为本机 (防 DNS rebinding 把外部域名
        解析到 127.0.0.1); 浏览器跨站请求必带 Origin (CSRF), 只允许本机来源.
        无 Origin 的请求 (本机进程/脚本) 放行 —— 本机可信边界即安全边界."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip().lower()
        if host and host not in ("127.0.0.1", "localhost", "::1", "[::1]"):
            self.send_error(403)
            return True
        origin = (self.headers.get("Origin") or "").strip()
        if origin:
            try:
                o = urlparse(origin)
            except ValueError:
                self.send_error(403)
                return True
            if (o.hostname or "").lower() not in ("127.0.0.1", "localhost", "::1"):
                self.send_error(403)
                return True
        return False

    def do_GET(self) -> None:  # noqa: N802
        if self._reject_non_local():
            return
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path.startswith("/api/"):
            try:
                _handle_api(self, path, query)
            except Exception as exc:  # noqa: BLE001
                _json_response(self, {"ok": False, "error": str(exc)}, 500)
            return
        if path == "/" or path == "":
            _static_response(self, "index.html")
        else:
            _static_response(self, path)

    def do_POST(self) -> None:  # noqa: N802
        self._handle_api_request()

    def do_PUT(self) -> None:  # noqa: N802
        self._handle_api_request()

    def _handle_api_request(self) -> None:
        if self._reject_non_local():
            return
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path.startswith("/api/"):
            try:
                _handle_api(self, path, query)
            except Exception as exc:  # noqa: BLE001
                _json_response(self, {"ok": False, "error": str(exc)}, 500)
            return
        self.send_error(404)


def start_server(host: str = "127.0.0.1", port: int = 0) -> tuple[str, int]:
    """启动 HTTP 服务, 返回 (host, port)."""
    global _server
    _server = ThreadingHTTPServer((host, port), _Handler)
    thread = threading.Thread(target=_server.serve_forever, daemon=True, name="gousage-http")
    thread.start()
    return _server.server_address[0], _server.server_address[1]


def stop_server() -> None:
    global _server
    if _server:
        _server.shutdown()
        _server.server_close()
        _server = None
