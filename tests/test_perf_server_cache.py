"""server.py usage 聚合缓存 (性能优化 B2) 的边界测试.

只有「由 usage 数据聚合出来的部分」可以缓存:
  · totals/today/daily/trend/today_trend/models (dashboard)
  · heatmap / model_trend / list_models
quota / progress / sync / account / logged_in / exchange_rate / server_time
必须每次请求实时计算 —— 整包缓存会让配额条卡死、同步进度不动 (本组测试专门盯着
这一点). 失效机制是「数据代数」: 任何写 usage 数据的路径 bump 一次.

覆盖:
  ① 同口径第二次请求命中缓存 (聚合没重跑)
  ② bump 后代数变化、缓存失效并返回新数据
  ③ 易变字段 (quota/progress) 不被缓存
  ④ range / exclude_models 不同不互相串味
  ⑤ 缓存容量上限 + 并发安全
  ⑥ 同步收尾 / 同步出错收尾 / 账号写路径 / 备份导入 / 同步窗口变更 的失效点
  ⑦ 同步进行中不吃缓存 (聚合在滚动变化)
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from app import db, server


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """独立临时库 + 干净缓存: 不打网络, 不受其它测试残留影响."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(server, "_fetch_usd_cny", lambda: 7.2)  # 汇率不走网络
    with server._agg_lock:
        server._agg_cache.clear()
        server._agg_gen.clear()
    yield tmp_path
    db.close_db()


@pytest.fixture()
def http(tmp_db):
    host, port = server.start_server("127.0.0.1", 0)
    yield f"http://{host}:{port}"
    server.stop_server()
    with server._sync_lock:
        server._sync_state["running"] = False


def _get(url: str):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status


def _request(url: str, method: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8")), exc.code


def _today_at(hour: int) -> str:
    """今天本地 hour 点的 UTC ISO (构造记录用, local_date 必为今天)."""
    local = datetime.now().astimezone().replace(hour=hour, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _rec(usg_id: str, *, model: str = "m1", hour: int = 10) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": _today_at(hour),
        "model": model,
        "input_tokens": 100,
        "output_tokens": 10,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": 0.01,
        "session_id": "s1",
    }


# ---------------------------------------------------------------------------
# ① 命中缓存: 第二次不再重跑聚合
# ---------------------------------------------------------------------------


def test_second_identical_request_hits_cache(http, monkeypatch):
    calls = {"n": 0}
    real_totals = db.totals

    def counting_totals(*args, **kwargs):
        calls["n"] += 1
        return real_totals(*args, **kwargs)

    monkeypatch.setattr(db, "totals", counting_totals)
    first, st1 = _get(f"{http}/api/dashboard?range=today")
    assert st1 == 200
    after_first = calls["n"]
    assert after_first >= 1  # 首次一定真跑了聚合

    second, st2 = _get(f"{http}/api/dashboard?range=today")
    assert st2 == 200
    assert calls["n"] == after_first  # 第二次命中缓存, 聚合一次都没多跑
    assert second["totals"] == first["totals"]
    assert second["range"] == "today"


def test_heatmap_model_trend_and_models_are_cached(http, monkeypatch):
    calls = {"daily": 0, "trend": 0, "models": 0}
    real_daily, real_trend, real_models = db.daily_stats, db.model_daily_stats, db.list_models
    monkeypatch.setattr(db, "daily_stats", lambda *a, **k: (calls.__setitem__("daily", calls["daily"] + 1), real_daily(*a, **k))[1])
    monkeypatch.setattr(db, "model_daily_stats", lambda *a, **k: (calls.__setitem__("trend", calls["trend"] + 1), real_trend(*a, **k))[1])
    monkeypatch.setattr(db, "list_models", lambda *a, **k: (calls.__setitem__("models", calls["models"] + 1), real_models(*a, **k))[1])

    for url in (f"{http}/api/heatmap?days=126", f"{http}/api/model_trend?days=30",
                f"{http}/api/usage/records?page=1"):
        assert _get(url)[1] == 200
    first = dict(calls)
    assert first == {"daily": 1, "trend": 1, "models": 1}

    for url in (f"{http}/api/heatmap?days=126", f"{http}/api/model_trend?days=30",
                f"{http}/api/usage/records?page=1", f"{http}/api/usage/records?page=2"):
        assert _get(url)[1] == 200
    assert calls == first  # 翻页/重复拉取不再重算 (list_models 键不含 page)


# ---------------------------------------------------------------------------
# ② bump 后代数变化: 缓存失效并返回新数据
# ---------------------------------------------------------------------------


def test_bump_invalidates_cache_and_returns_new_data(http):
    aid = db.get_active_account_id()
    _get(f"{http}/api/dashboard?range=today")  # 预热 (空库 -> 0 条)
    db.insert_usage_records([_rec("u-bump")], aid)

    stale, _ = _get(f"{http}/api/dashboard?range=today")
    assert stale["totals"]["request_count"] == 0  # 未 bump: 仍是同步前的旧聚合

    gen_before = server._agg_generation(aid)
    server.bump_data_generation()  # 同步落库收尾会做的事
    assert server._agg_generation(aid) > gen_before

    fresh, _ = _get(f"{http}/api/dashboard?range=today")
    assert fresh["totals"]["request_count"] == 1
    assert fresh["today"]["request_count"] == 1


def test_cached_entry_holds_only_aggregates(tmp_db):
    """缓存对象只能是聚合子字典 —— 有人往里塞易变字段时这里立刻失败."""
    agg = server._dashboard_aggregates(None, "today", [])
    assert set(agg) == {"totals", "today", "daily", "trend", "today_trend", "models"}
    for volatile in ("quota", "progress", "sync", "account", "logged_in",
                     "exchange_rate", "server_time", "range", "excluded_models"):
        assert volatile not in agg


# ---------------------------------------------------------------------------
# ③ 易变字段不被缓存: quota / progress 每次实时算
# ---------------------------------------------------------------------------


def test_volatile_quota_and_progress_not_cached(http):
    aid = db.add_account("tok-cache-test", "ws")  # 有 token 时 dashboard 才回 quota
    server._quota_cache[aid] = {
        "at": time.time(), "data": {"success": True, "used": 10, "windows": []},
    }
    with server._sync_lock:
        server._sync_state.update(page=1, message="A")
    before, _ = _get(f"{http}/api/dashboard?range=today")

    # 两个易变源同时变化: 配额缓存被后台刷新、同步进度前进
    server._quota_cache[aid] = {
        "at": time.time(), "data": {"success": True, "used": 99, "windows": []},
    }
    with server._sync_lock:
        server._sync_state.update(page=7, message="B")
    after, _ = _get(f"{http}/api/dashboard?range=today")

    assert before["quota"]["used"] == 10 and after["quota"]["used"] == 99
    assert before["progress"]["page"] == 1 and after["progress"]["page"] == 7
    assert before["progress"]["message"] == "A" and after["progress"]["message"] == "B"
    assert before["sync"] is not None and after["sync"] is not None
    assert before["server_time"] and after["server_time"]


# ---------------------------------------------------------------------------
# ④ range / exclude_models 不互相串味
# ---------------------------------------------------------------------------


def test_range_and_exclude_do_not_cross_contaminate(http):
    aid = db.get_active_account_id()
    db.insert_usage_records([_rec("u-a", model="alpha"), _rec("u-b", model="beta")], aid)
    server.bump_data_generation(aid)

    all_today, _ = _get(f"{http}/api/dashboard?range=today")
    assert all_today["totals"]["request_count"] == 2
    excl, _ = _get(f"{http}/api/dashboard?range=today&exclude_models=alpha")
    assert excl["totals"]["request_count"] == 1
    assert excl["excluded_models"] == ["alpha"]
    # models 始终全量 (图例要能点击加回), 排除只作用于 totals
    assert {m["model"] for m in excl["models"]} == {"alpha", "beta"}

    # 再拉全量: 不能命中排除后的缓存
    again, _ = _get(f"{http}/api/dashboard?range=today")
    assert again["totals"]["request_count"] == 2
    assert again["excluded_models"] == []

    # 换 range 也不能串味 (7d 与 today 是不同键)
    week, _ = _get(f"{http}/api/dashboard?range=7d")
    assert week["range"] == "7d"

    # 同一排除集第二次: 命中缓存, 仍返回排除后的口径
    excl2, _ = _get(f"{http}/api/dashboard?range=today&exclude_models=alpha")
    assert excl2["totals"]["request_count"] == 1


# ---------------------------------------------------------------------------
# ⑤ 容量上限 + 并发安全
# ---------------------------------------------------------------------------


def test_cache_capacity_is_bounded(tmp_db):
    for i in range(server._AGG_CACHE_MAX + 20):
        assert server._agg_cached((1, "fill", i), lambda i=i: {"i": i}) == {"i": i}
    assert len(server._agg_cache) <= server._AGG_CACHE_MAX
    # 最新写入的还在 (FIFO 淘汰最旧)
    assert (1, "fill", server._AGG_CACHE_MAX + 19) in server._agg_cache
    assert (1, "fill", 0) not in server._agg_cache


def test_concurrent_cache_access_is_safe(tmp_db):
    errors: list[Exception] = []

    def worker(seed: int) -> None:
        try:
            for i in range(200):
                value = server._agg_cached((1, "concurrent", i % 7), lambda i=i: {"v": i})
                assert isinstance(value, dict)
                if i % 3 == 0:
                    server.bump_data_generation(1)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(server._agg_cache) <= server._AGG_CACHE_MAX


def test_producer_result_not_cached_when_data_changed_meanwhile(tmp_db):
    """生成期间数据变了 (代数前移): 旧值不得被写成新代."""
    server.bump_data_generation(1)
    gen_before = server._agg_generation(1)

    def producer() -> dict:
        server.bump_data_generation(1)  # 聚合跑到一半, 同步落库了
        return {"v": 1}

    assert server._agg_cached((1, "race"), producer) == {"v": 1}
    assert server._agg_generation(1) > gen_before
    assert (1, "race") not in server._agg_cache  # 没有写回, 下次会重算


# ---------------------------------------------------------------------------
# ⑥ 失效点: 同步收尾 / 同步出错 / 账号写路径 / 备份导入 / 同步窗口
# ---------------------------------------------------------------------------


def test_sync_running_bypasses_cache(http):
    """同步进行中聚合在滚动变化: 不吃缓存 (改动前就是实时语义)."""
    aid = db.get_active_account_id()
    _get(f"{http}/api/dashboard?range=today")  # 填缓存 (0 条)
    with server._sync_lock:
        server._sync_state["running"] = True
    try:
        db.insert_usage_records([_rec("u-syncing")], aid)
        live, _ = _get(f"{http}/api/dashboard?range=today")
        assert live["totals"]["request_count"] == 1  # 同步中拿到的是实时结果
    finally:
        with server._sync_lock:
            server._sync_state["running"] = False


def test_finish_sync_bumps_generation(tmp_db):
    gen = server._agg_generation(1)
    server._finish_sync(1, 5, 2)
    assert server._agg_generation(1) > gen


def test_sync_error_finish_bumps_generation(tmp_db, monkeypatch):
    monkeypatch.setattr(
        db, "list_accounts", lambda: [{"id": 1, "name": "Default", "has_token": True}]
    )
    monkeypatch.setattr(server, "_sync_one_account", lambda *a, **k: {"ok": False, "error": "boom"})
    gen = server._agg_generation(1)
    result = server.sync_usage("incremental")
    assert result["ok"] is False and "boom" in result["error"]
    assert server._agg_generation(1) > gen  # 同步出错收尾同样要失效
    with server._sync_lock:
        assert server._sync_state["running"] is False  # 闸门必须放开


def test_cycle_bounds_bump_only_when_cycle_start_changes(tmp_db):
    """计费周期起点是「本周期」聚合口径的一部分: 变了必须失效, 没变不要抖动."""
    gen = server._agg_generation(1)
    server._record_cycle_bounds(1, {})  # 没有周期信息
    assert server._agg_generation(1) == gen

    start = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (datetime.now(timezone.utc) + timedelta(days=27)).strftime("%Y-%m-%dT%H:%M:%SZ")
    server._record_cycle_bounds(1, {"period_start": start, "period_end": end})
    assert server._agg_generation(1) > gen  # 首次拿到真实周期 -> 失效

    settled = server._agg_generation(1)
    server._record_cycle_bounds(1, {"period_start": start, "period_end": end})
    assert server._agg_generation(1) == settled  # 同周期重复落库不失效 (缓存继续命中)


def test_settings_route_bumps_only_on_window_change(http):
    gen = server._agg_generation(None)
    _, status = _request(f"{http}/api/settings", "PUT", {"sync_interval_sec": 900})
    assert status == 200
    assert server._agg_generation(None) == gen  # 不影响聚合口径, 不失效

    _, status = _request(f"{http}/api/settings", "PUT", {"window_days": 90})
    assert status == 200
    assert server._agg_generation(None) > gen  # 窗口变更 -> 失效


def test_account_and_backup_routes_bump_generation(http, tmp_db, monkeypatch):
    # /api/logout: 退出登录会清空该账号明细
    aid = db.get_active_account_id()
    gen = server._agg_generation(aid)
    assert _request(f"{http}/api/logout", "POST", {})[1] == 200
    assert server._agg_generation(aid) > gen

    # /api/relogin: 凭证变更 (登录窗回调)
    aid = db.get_active_account_id()
    gen = server._agg_generation(aid)
    assert _request(f"{http}/api/relogin", "POST", {})[1] == 200
    assert server._agg_generation(aid) > gen

    # /api/accounts/add-token: 配额校验打桩 (不打网络), 新增账号并切过去
    class _Ok:
        success = True
        error = None

    monkeypatch.setattr(server, "fetch_quota", lambda token, ws: _Ok())
    body, status = _request(
        f"{http}/api/accounts/add-token", "POST", {"token": "tok-x", "provider": "opencode"}
    )
    assert status == 200 and body["id"]
    new_aid = body["id"]
    gen = server._agg_generation(new_aid)
    assert _request(f"{http}/api/accounts/switch", "POST", {"id": new_aid})[1] == 200
    assert server._agg_generation(new_aid) > gen

    # /api/accounts/delete: 删号会删掉该账号明细
    gen = server._agg_generation(new_aid)
    assert _request(f"{http}/api/accounts/delete", "POST", {"id": new_aid})[1] == 200
    assert server._agg_generation(new_aid) > gen

    # /api/backup/import: 备份解析打桩, 只验路由接线 (导入可能跨账号写)
    monkeypatch.setattr(server.backup, "import_backup", lambda path: {"records_added": 0})
    backup_path = str(tmp_db / "fake-backup.json.gz")
    server.approve_path(backup_path, server.APPROVAL_OPEN)
    gen = server._agg_generation(None)
    body, status = _request(f"{http}/api/backup/import", "POST", {"path": backup_path})
    assert status == 200 and body["ok"] is True
    assert server._agg_generation(None) > gen
