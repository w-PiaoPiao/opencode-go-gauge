"""本地 HTTP 服务: 静态资源 + JSON API + 后台同步."""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

from . import __version__, db
from .autostart import disable as _autostart_disable, enable as _autostart_enable
from .updater import RELEASE_PAGE_URL, check_update, download_update
from .opencode_api import (
    AuthError,
    OpenCodeAPIError,
    fetch_key_names,
    fetch_quota,
    fetch_usage_page,
    resolve_workspace_id,
)

PAGE_SIZE = 50
QUOTA_CACHE_TTL = 30.0
INCREMENTAL_PAGES = 5  # 增量同步最多拉取的页数 (5*50=250 条)
MAX_FULL_PAGES = 2000  # 全量同步上限, 防失控
FETCH_BATCH = 5  # 并发拉取页数 (服务端响应慢, 并发提速)


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
_exchange_cache: dict[str, Any] = {"at": 0.0, "usd_cny": 7.2}
_EXCHANGE_TTL = 6 * 3600  # 汇率缓存 6 小时
_DEFAULT_USD_CNY = 7.2


def _fetch_usd_cny() -> float:
    """从 open.er-api.com 获取 USD→CNY 汇率, 失败时返回上次缓存/默认值."""
    now = time.time()
    if now - _exchange_cache["at"] < _EXCHANGE_TTL:
        return _exchange_cache["usd_cny"]
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
            _exchange_cache.update(at=now, usd_cny=rate)
    except Exception:  # noqa: BLE001 网络失败时保留旧值
        _exchange_cache["at"] = now
    return _exchange_cache["usd_cny"]


def _sync_progress_snapshot() -> dict[str, Any]:
    with _sync_lock:
        return dict(_sync_state)


def _set_phase(phase: str, message: str = "") -> None:
    with _sync_lock:
        _sync_state["phase"] = phase
        _sync_state["message"] = message
        _sync_state["running"] = phase in ("quota", "usage")


# ---------------------------------------------------------------------------
# 同步执行
# ---------------------------------------------------------------------------


def _record_monthly_reset(account_id: int, quota: dict[str, Any]) -> None:
    """配额拉取成功后持久化月度窗口的重置时间 (供「本月」筛选推算周期起点)."""
    try:
        for window in quota.get("windows") or []:
            if window.get("label") == "Monthly" and window.get("reset_at"):
                db.record_monthly_reset(account_id, window["reset_at"])
                break
    except Exception:  # noqa: BLE001 持久化失败不影响配额返回
        pass


def _fetch_quota_with_cache(account_id: int, token: str, workspace_hint: str) -> dict[str, Any]:
    slot = _quota_cache.setdefault(account_id, {"at": 0.0, "data": None})
    now = time.time()
    if slot["data"] and now - slot["at"] < QUOTA_CACHE_TTL:
        return slot["data"]
    result = fetch_quota(token, workspace_hint)
    slot["at"] = now
    slot["data"] = result.to_dict()
    _record_monthly_reset(account_id, slot["data"])
    return slot["data"]


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
    if aid in _quota_refreshing:
        return  # 该账号已有刷新线程在跑
    token, workspace_hint = db.get_account_credentials(aid)
    if not token:
        return
    _quota_refreshing.add(aid)

    def worker() -> None:
        try:
            # 失败也写入缓存 (None), TTL 内不再重试, 避免前端无限刷新
            _fetch_quota_with_cache(aid, token, workspace_hint)
        except Exception:  # noqa: BLE001
            _quota_cache.setdefault(aid, {"at": 0.0, "data": None})
            _quota_cache[aid]["at"] = time.time()
            _quota_cache[aid]["data"] = None
        finally:
            _quota_refreshing.discard(aid)

    threading.Thread(target=worker, daemon=True, name="gousage-quota").start()


def _fetch_usage_batch(
    token: str, workspace_id: str, pages: list[int]
) -> dict[int, Any]:
    """并发拉取多页, 返回 {page: records | Exception}."""
    results: dict[int, Any] = {}
    with ThreadPoolExecutor(max_workers=FETCH_BATCH) as executor:
        futures = {
            executor.submit(fetch_usage_page, token, workspace_id, p): p
            for p in pages
        }
        for future in as_completed(futures):
            page = futures[future]
            try:
                results[page] = future.result()
            except Exception as exc:  # noqa: BLE001
                results[page] = exc
    return results


def _sync_one_account(
    account_id: int, name: str, mode: str, window_days: Optional[int]
) -> dict[str, Any]:
    """同步单个账号的用量记录 (原单账号逻辑, 显式传入账号上下文)."""
    token = db.get_db().execute(
        "SELECT token, workspace_id, resolved_workspace_id FROM accounts WHERE id = ?",
        (account_id,),
    ).fetchone()
    if token is None or not token["token"].strip():
        return {"ok": False, "error": "未登录"}
    token_str = token["token"].strip()
    workspace_id = token["resolved_workspace_id"] or token["workspace_id"] or "Default"

    with _sync_lock:
        _sync_state.update(account=name)

    try:
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
        max_pages = MAX_FULL_PAGES if mode == "full" else INCREMENTAL_PAGES
        page = 0
        empty_batches = 0
        failed_pages = 0
        window_boundary_reached = False

        while page < max_pages:
            batch_pages = list(range(page, min(page + FETCH_BATCH, max_pages)))
            with _sync_lock:
                _sync_state["page"] = page
            results = _fetch_usage_batch(token_str, workspace_id, batch_pages)

            batch_inserted = 0
            batch_full_pages = 0
            batch_failed = 0
            for p in sorted(results):
                result = results[p]
                if isinstance(result, Exception):
                    batch_failed += 1
                    continue
                if not result:
                    continue  # 空页: 数据到底
                # 同步范围: 全量拉取时, 若本页最早记录早于窗口边界 → 该页整页保留后停止
                if mode == "full" and window_days is not None:
                    earliest = min((r.created_at for r in result), default="")
                    if earliest:
                        try:
                            from datetime import datetime, timedelta, timezone
                            et = datetime.fromisoformat(earliest.replace("Z", "+00:00"))
                            boundary = datetime.now(timezone.utc) - timedelta(days=window_days)
                            if et < boundary:
                                window_boundary_reached = True
                        except (ValueError, TypeError):
                            pass
                inserted = db.insert_usage_records(
                    [r.to_db_dict() for r in result], account_id
                )
                total_inserted += inserted
                batch_inserted += inserted
                if len(result) >= PAGE_SIZE:
                    batch_full_pages += 1
                with _sync_lock:
                    _sync_state["inserted"] = total_inserted

            page += FETCH_BATCH

            if window_boundary_reached:
                break
            if batch_failed:
                failed_pages += batch_failed
                if mode == "incremental":
                    msg = "网络请求失败 (IncompleteRead/超时)"
                    _set_phase("error", f"[{name}] 第 {page - FETCH_BATCH + 1} 页拉取失败: {msg}")
                    db.update_sync_state("error", msg, total_inserted, account_id)
                    return {"ok": False, "error": msg, "partial_inserted": total_inserted}

            # 本批没有任何满页 → 到底了
            if batch_full_pages == 0:
                break
            # 增量模式: 连续两批全部是旧数据 (插入 0 条) → 停止
            if mode == "incremental" and batch_inserted == 0:
                empty_batches += 1
                if empty_batches >= 2:
                    break
            else:
                empty_batches = 0

        # 按同步范围裁剪窗口外记录 (与本次新增数独立)
        if window_days is not None:
            db.prune_old_records(window_days, account_id)

        # 顺带刷新该账号的 key 显示名称缓存 (合并写入: key_id 全局唯一,
        # 多账号各补各的条目; 单账号失败不影响已有缓存)
        try:
            fresh_keys = fetch_key_names(token_str, workspace_id)
            merged = dict(db.get_key_names())
            merged.update(fresh_keys)
            db.save_key_names(merged)
        except Exception:  # noqa: BLE001
            pass

        if failed_pages:
            msg = f"完成, 但 {failed_pages} 页拉取失败 (数据不完整, 可再次全量同步补全)"
            db.update_sync_state("partial", msg, total_inserted, account_id)
            return {"ok": True, "partial": True, "failed_pages": failed_pages,
                    "inserted": total_inserted, "pages": page}
        db.update_sync_state("ok", None, total_inserted, account_id)
        return {"ok": True, "inserted": total_inserted, "pages": page}
    except Exception as exc:  # noqa: BLE001
        db.update_sync_state("error", str(exc), 0, account_id)
        return {"ok": False, "error": str(exc)}


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
        any_error = ""
        partial = False
        pages = 0
        for aid, name in targets:
            result = _sync_one_account(aid, name, mode, window_days)
            total_inserted += int(result.get("inserted") or 0)
            pages += int(result.get("pages") or 0)
            if not result.get("ok"):
                any_error = result.get("error") or "同步失败"
                if mode == "incremental":
                    _set_phase("error", f"[{name}] {any_error}")
                    return {"ok": False, "error": any_error, "partial_inserted": total_inserted}
            if result.get("partial"):
                partial = True

        if partial or (mode != "incremental" and any_error):
            msg = "部分账号同步异常" if any_error else "完成, 但部分页面拉取失败"
            _set_phase("done", msg)
            return {"ok": True, "partial": True, "inserted": total_inserted, "pages": pages}
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

_on_open_login: Optional[Callable[[str], None]] = None
_server: Optional[ThreadingHTTPServer] = None

# 半自动更新下载状态机: idle -> checking -> downloading -> done/no_update/no_asset/error
_update_download: dict[str, Any] = {"state": "idle", "path": "", "error": "", "latest": ""}


def _update_download_worker() -> None:
    """后台下载新版本 zip 到 ~/Downloads, 完成后在 Finder 中定位."""
    try:
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        result = download_update(downloads)
        _update_download.update(result)
        if result.get("state") == "done" and result.get("path"):
            import subprocess

            subprocess.Popen(["open", "-R", result["path"]])
    except Exception as exc:  # noqa: BLE001
        _update_download.update({"state": "error", "error": str(exc)[:300]})


def set_login_callback(callback: Callable[[str], None]) -> None:
    """由 main.py 注册: 前端请求登录时触发窗口跳转.

    回调契约: callback(mode), mode 为 "add" (添加新用户) 或 "relogin" (重新登录当前用户).
    """
    global _on_open_login
    _on_open_login = callback


def _read_json_body(handler: BaseHTTPRequestHandler) -> Any:
    """读取并解析 JSON 请求体, 失败抛 ValueError."""
    length = int(handler.headers.get("Content-Length") or 0)
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
    # 防目录穿越
    rel = rel.lstrip("/")
    if ".." in rel.replace("\\", "/").split("/"):
        handler.send_error(403)
        return
    path = _resource_path(rel)
    if not os.path.isfile(path):
        handler.send_error(404)
        return
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    try:
        with open(path, "rb") as fh:
            body = fh.read()
    except OSError:
        handler.send_error(500)
        return
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def _handle_api(handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]]) -> None:
    method = handler.command
    route = path

    if route == "/api/version" and method == "GET":
        _json_response(handler, {"version": __version__})

    if route == "/api/update/check" and method == "GET":
        try:
            _json_response(handler, check_update())
        except Exception as exc:  # noqa: BLE001 网络/解析失败 -> 前端提示
            _json_response(handler, {"error": str(exc)}, status=502)

    if route == "/api/update/open" and method == "POST":
        # 用系统默认浏览器打开 GitHub Releases 页 (WebView 内 window.open 不可靠)
        import webbrowser

        webbrowser.open(RELEASE_PAGE_URL)
        _json_response(handler, {"ok": True})

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
        # quota 使用缓存 (按账号分槽), 过期时后台刷新, 不阻塞 dashboard 响应
        active_id = db.get_active_account_id()
        _ensure_quota_async(active_id)
        slot = _quota_cache.get(active_id) or {}
        quota = slot.get("data") if token else None
        account = db.get_account()
        _json_response(
            handler,
            {
                "logged_in": bool(token),
                "account": account,
                "account_name": account.get("name", ""),
                "accounts_total": db.count_accounts(),
                "accounts_logged_in": db.count_logged_in_accounts(),
                "quota": quota,
                "totals": db.totals(period),
                "today": db.totals("today"),
                "daily": db.daily_stats(7),  # 每日趋势固定显示近 7 天
                "trend": db.daily_stats(30),  # 用量趋势 (费用/请求双轴)
                "today_trend": db.today_trend(),  # 今日 24 小时趋势
                "models": db.model_stats(period),
                "sync": db.get_sync_state(),
                "progress": _sync_progress_snapshot(),
                "range": range_param,
                "exchange_rate": {"usd_cny": _fetch_usd_cny(), "currency": "CNY"},
                "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        return

    if route == "/api/logout" and method == "POST":
        # 退出前记录账号 id, 退出后清理其配额缓存槽 (防止残留旧配额)
        aid = db.get_active_account_id()
        db.clear_account()
        if aid:
            _quota_cache.pop(aid, None)
        _json_response(handler, {"ok": True})
        return

    if route == "/api/relogin" and method == "POST":
        if _on_open_login:
            _on_open_login("relogin")
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
            _json_response(handler, {"ok": True, "remaining": remaining})
            return

        if action == "add":
            # 触发登录窗口 (add 模式); 无窗口环境 (纯浏览器/冒烟) 时返回未打开状态
            opened = bool(_on_open_login)
            if opened:
                _on_open_login("add")
            _json_response(handler, {"ok": True, "opened": opened})
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
            # 无 session 的行分组键为 key_id, 前端据此显示"未归属"
            if rec["session_id"] and rec["session_id"].startswith("key_"):
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

    if route == "/api/settings" and method == "GET":
        _json_response(handler, db.get_settings())
        return

    if route == "/api/settings" and method == "PUT":
        try:
            length = int(handler.headers.get("Content-Length") or 0)
            body = json.loads(handler.rfile.read(length).decode("utf-8", errors="replace"))
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

    def log_message(self, fmt: str, *args: Any) -> None:  # 静默日志
        pass

    def do_GET(self) -> None:  # noqa: N802
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
