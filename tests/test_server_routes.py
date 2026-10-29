"""server.py 本地 HTTP 路由冒烟测试 (127.0.0.1 起真实服务, 只测无外网依赖的路由)."""
from __future__ import annotations

import gzip
import http.client
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

from app import backup, db, server, updater


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """独立临时库: 重定向 data_dir (同 test_db_multiuser)."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


def _drain_server_background(timeout: float = 20.0) -> None:
    """等待前序用例遗留的后台同步/配额线程退出 (测试隔离; 见 conftest 集成备注).

    其它测试文件可能真实触发 sync_all_async, 残留线程会让 /api/sync 与聚合
    缓存断言假红. 按线程名做有界等待并兜底复位同步状态.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        with server._sync_lock:
            running = bool(server._sync_state.get("running"))
        stray = [
            t for t in threading.enumerate()
            if t.name in ("gousage-sync", "gousage-quota") and t.is_alive()
        ]
        if not running and not stray:
            break
        time.sleep(0.05)
    with server._sync_lock:
        server._sync_state.update(
            running=False, mode="", page=0, inserted=0, phase="idle", message="", account="")


@pytest.fixture()
def http(tmp_db):
    server.set_auth_token(None)
    _drain_server_background()
    with server._update_check_lock:
        server._update_check.update(state="idle", result=None, error="")
    host, port = server.start_server("127.0.0.1", 0)
    yield f"http://{host}:{port}"
    server.stop_server()
    with server._sync_lock:
        server._sync_state["running"] = False


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status


def _post_raw(url: str, raw: bytes):
    req = urllib.request.Request(url, data=raw, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8")), exc.code


def _request(url: str, method: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8")), exc.code


def test_version_route(http):
    data, status = _get(f"{http}/api/version")
    assert status == 200
    assert isinstance(data.get("version"), str) and data["version"]


def test_state_fresh_install(http):
    data, status = _get(f"{http}/api/state")
    assert status == 200
    assert data["logged_in"] is False
    assert data["accounts_total"] == 1  # 种子行


def test_settings_roundtrip(http):
    saved, status = _request(
        f"{http}/api/settings", "PUT", {"window_days": 90, "sync_interval_sec": 900})
    assert status == 200
    assert saved["window_days"] == 90
    assert saved["sync_interval_sec"] == 900
    again, status = _get(f"{http}/api/settings")
    assert status == 200
    assert again["window_days"] == 90


def test_settings_rejects_invalid_body(http):
    _, status = _request(f"{http}/api/settings", "PUT", None)
    assert status == 400


def test_sync_requires_login(http):
    _, status = _request(f"{http}/api/sync?mode=incremental", "POST")
    assert status == 401


def test_accounts_list(http):
    data, status = _get(f"{http}/api/accounts")
    assert status == 200
    assert data["ok"] is True
    assert len(data["accounts"]) == 1


def test_static_index_served(http):
    with urllib.request.urlopen(f"{http}/", timeout=5) as resp:
        body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "GoGauge" in body


def test_path_traversal_rejected(http):
    # Windows 盘符绝对路径与 .. 穿越都必须被 realpath 包含校验拦下
    for path in ("/..%2F..%2Fetc/passwd", "/..%5C..%5Cgousage.db"):
        try:
            _, status = _get(f"{http}{path}")
        except urllib.error.HTTPError as exc:
            status = exc.code
        assert status in (403, 404), path


# ---------------------------------------------------------------------------
# _record_cycle_bounds: 配额响应 → 周期边界落库 (「本周期」筛选起点的数据源)
# ---------------------------------------------------------------------------


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_record_cycle_bounds_prefers_real_period(tmp_db):
    """响应带真实周期 (Go access.startsAt/endsAt) 时落库并优先于「重置 - 30 天」
    回推 —— 31 天自然月下回推会得到未来起点, 「本周期」筛选恒为空."""
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=12)
    end = start + timedelta(days=31)
    server._record_cycle_bounds(1, {
        "period_start": _iso(start),
        "period_end": _iso(end),
        "windows": [{"label": "Monthly", "reset_at": _iso(end)}],
    })
    assert db.period_bounds(1) == (
        start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"),
    )
    assert db.monthly_cycle_start(1) == start.strftime("%Y-%m-%d %H:%M:%S")


def test_record_cycle_bounds_without_period_keeps_reset(tmp_db):
    """老响应无真实周期: 仍只记「下次重置」, 回推兜底路径可用."""
    from datetime import timedelta

    reset = datetime.now(timezone.utc) + timedelta(days=20)
    server._record_cycle_bounds(1, {
        "windows": [{"label": "Monthly", "reset_at": _iso(reset)}],
    })
    assert db.period_bounds(1) == (None, None)
    assert db.monthly_cycle_start(1) is not None


def test_record_cycle_bounds_garbage_never_raises(tmp_db):
    """异常数据/空响应不得抛出 (配额返回不能被落库失败拖垮)."""
    server._record_cycle_bounds(1, {})
    server._record_cycle_bounds(1, {
        "period_start": "x", "period_end": "y",
        "windows": [{"label": "Monthly", "reset_at": "bad"}],
    })
    assert db.period_bounds(1) == (None, None)


def test_attach_forecast_annotates_windows_without_mutating_cache():
    """dashboard 的 quota 窗口带打满预测字段, 且缓存对象 (接口原始形状) 不被污染."""
    quota = {
        "success": True,
        "period_start": "2026-10-08T00:00:00Z",
        "period_end": "2026-11-08T00:00:00Z",
        "windows": [
            {"label": "5h Rolling", "used": 42.0, "reset_at": "2026-10-08T05:00:00Z", "reset_in_sec": 12000},
            {"label": "Weekly", "used": 20.0, "reset_at": "2026-10-15T00:00:00Z", "reset_in_sec": 518400},
            {"label": "Monthly", "used": 3.0, "reset_at": "2026-11-08T00:00:00Z", "reset_in_sec": 2592000},
        ],
    }
    out = server._attach_forecast(quota)
    assert out["windows"][0]["forecast"] == {"state": "fill", "sec": 8286}
    assert out["windows"][1]["forecast"] == {"state": "fill", "sec": 4 * 86400}
    assert out["windows"][2]["forecast"] == {"state": "no_fill", "pct": 93}
    assert out is not quota
    assert all("forecast" not in w for w in quota["windows"])


def test_attach_forecast_skips_window_without_reset():
    """无重置时间 = 窗口未开始 (5h 窗口空闲): reset_in_sec 为 0 会让整窗被当成
    已过样本、算出「不会打满」—— 没有窗口在跑就别说预测, forecast 留 null."""
    quota = {
        "success": True,
        "period_start": "2026-10-08T00:00:00Z",
        "period_end": "2026-11-08T00:00:00Z",
        "windows": [
            {"label": "5h Rolling", "used": 0.0, "reset_at": "", "reset_in_sec": 0},
            {"label": "Monthly", "used": 3.0, "reset_at": "2026-11-08T00:00:00Z", "reset_in_sec": 2592000},
        ],
    }
    out = server._attach_forecast(quota)
    assert out["windows"][0]["forecast"] is None
    assert out["windows"][1]["forecast"] == {"state": "no_fill", "pct": 93}


def test_attach_forecast_passthrough_when_unavailable():
    """失败/空窗口的配额原样返回, 不给前端制造半截字段."""
    assert server._attach_forecast(None) is None
    failed = {"success": False, "error": "x", "windows": []}
    assert server._attach_forecast(failed) is failed
    no_windows = {"success": True}
    assert server._attach_forecast(no_windows) is no_windows


# ---------------------------------------------------------------------------
# 「按同步范围清理」: 同步范围是取数范围, 本地数据只能由按钮显式删除
# ---------------------------------------------------------------------------


def _stamp(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _rec(usg_id: str, created_at: str) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": created_at,
        "model": "test-model",
        "provider": "opencode",
        "input_tokens": 1,
        "output_tokens": 1,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": 0.0,
    }


def _count_records() -> int:
    return db.get_db().execute(
        "SELECT COUNT(*) AS c FROM usage_records").fetchone()["c"]


def _count_charts() -> int:
    return db.get_db().execute(
        "SELECT COUNT(*) AS c FROM usage_charts").fetchone()["c"]


def _chart(time_bucket: str, model: str = "goat-model") -> dict:
    return {
        "model": model,
        "provider": db.PROVIDER_COMMANDCODE,
        "time_bucket": time_bucket,
        "requests": 3,
        "tokens_in": 30,
        "tokens_out": 15,
        "tokens_total": 45,
    }


def test_prune_preview_then_execute(http, tmp_db):
    """预演只算数不写库; POST 才真删, 且只删边界之前的行."""
    db.insert_usage_records(
        [_rec("old-1", _stamp(100)), _rec("old-2", _stamp(100)), _rec("new-1", _stamp(0))],
        1,
    )
    _request(f"{http}/api/settings", "PUT", {"window_days": 30})

    preview, status = _get(f"{http}/api/usage/prune")
    assert status == 200
    assert preview["window_days"] == 30
    assert preview["count"] == 2
    assert preview["charts_count"] == 0  # I3: charts 也参与预演 (口径对称)
    assert _count_records() == 3, "预演不能删数据"

    done, status = _request(f"{http}/api/usage/prune", "POST")
    assert status == 200
    assert done["deleted"] == 2
    assert done["deleted_charts"] == 0
    assert done["count"] == 2 and done["charts_count"] == 0  # 删除前口径
    assert _count_records() == 1
    assert db.get_db().execute(
        "SELECT usg_id FROM usage_records").fetchone()["usg_id"] == "new-1"


def test_prune_covers_usage_charts(http, tmp_db):
    """P2-7/I3: GOAT 统计主口径是 charts, 清理必须同时删过期 charts.

    此前 prune 只删 usage_records: 提示"已清理 N 条"后 totals("all") 仍含历史,
    charts 跨计费周期无限累积.
    """
    old_day = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
    new_day = datetime.now().strftime("%Y-%m-%d")
    db.insert_usage_charts([_chart(f"{old_day} 10:00:00"), _chart(f"{new_day} 10:00:00")], 1)
    _request(f"{http}/api/settings", "PUT", {"window_days": 30})

    preview, status = _get(f"{http}/api/usage/prune")
    assert status == 200
    assert preview["charts_count"] == 1

    done, status = _request(f"{http}/api/usage/prune", "POST")
    assert status == 200
    assert done["deleted_charts"] == 1
    assert _count_charts() == 1
    assert db.get_db().execute(
        "SELECT local_date FROM usage_charts").fetchone()["local_date"] == new_day


def test_prune_is_noop_when_range_is_all(http, tmp_db):
    """同步范围「所有」= 不设上限, 清理按钮什么都不该删."""
    db.insert_usage_records([_rec("ancient", _stamp(400))], 1)
    db.insert_usage_charts([_chart("2020-01-01 10:00:00")], 1)
    _request(f"{http}/api/settings", "PUT", {"window_days": None})

    preview, _ = _get(f"{http}/api/usage/prune")
    assert preview["window_days"] is None
    assert preview["count"] == 0
    assert preview["charts_count"] == 0

    done, status = _request(f"{http}/api/usage/prune", "POST")
    assert status == 200
    assert done["deleted"] == 0 and done["deleted_charts"] == 0
    assert _count_records() == 1
    assert _count_charts() == 1


class _FakePage:
    """fetch_usage_page 的替身: 一页到底, 不产生网络请求."""

    def __init__(self, records):
        self.records = records
        self.next_cursor = None
        self.retention_days = 30


class _FakeRecord:
    def __init__(self, usg_id: str, created_at: str):
        self.usg_id = usg_id
        self.created_at = created_at

    def to_db_dict(self) -> dict:
        return _rec(self.usg_id, self.created_at)


def test_sync_never_deletes_local_records(tmp_db, monkeypatch):
    """回归: 同步结束不得裁剪窗口外的本地存量.

    window_days 只是取数范围 (调用它的全量同步据此决定翻页深度), 绝不能顺手
    删掉更早的记录 —— 早期实现每次同步都 prune, 把「改小同步范围」变成一次
    静默的不可恢复删除.
    """
    aid = db.add_account("tok", "wrk_test", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_rec("keep-old", _stamp(100))], aid)

    monkeypatch.setattr(
        server, "fetch_usage_page",
        lambda *a, **k: _FakePage([_FakeRecord("fresh", _stamp(0))]),
    )
    monkeypatch.setattr(server, "fetch_key_names", lambda *a, **k: {})

    result = server._sync_one_account(aid, "acc", "full", 30)
    assert result["ok"] is True

    ids = {
        r["usg_id"]
        for r in db.get_db().execute(
            "SELECT usg_id FROM usage_records WHERE account_id = ?", (aid,)).fetchall()
    }
    assert "keep-old" in ids, "同步把窗口外的本地记录删掉了"
    assert "fresh" in ids


# ---------------------------------------------------------------------------
# P3-5: /api/sync 进行中再点"全量同步" -> 409 (不得静默丢弃)
# ---------------------------------------------------------------------------


def test_sync_returns_409_while_running(http, tmp_db):
    db.add_account("tok-sync", "wrk_sync", switch=True, provider=db.PROVIDER_OPENCODE)
    with server._sync_lock:
        server._sync_state["running"] = True
    try:
        body, status = _request(f"{http}/api/sync?mode=full", "POST")
        assert status == 409, body
        assert body["ok"] is False
        assert body["error"] == "同步进行中"
    finally:
        with server._sync_lock:
            server._sync_state["running"] = False


def test_sync_starts_when_idle(http, tmp_db, monkeypatch):
    db.add_account("tok-sync", "wrk_sync", switch=True, provider=db.PROVIDER_OPENCODE)
    started: dict = {}
    monkeypatch.setattr(
        server, "sync_all_async", lambda mode: started.setdefault("mode", mode))
    body, status = _request(f"{http}/api/sync?mode=full", "POST")
    assert status == 200 and body == {"ok": True}
    assert started["mode"] == "full"


# ---------------------------------------------------------------------------
# P3-6: 错误处理契约 (JSON 404 / 400 / 不泄漏绝对路径 / ok 字段一致)
# ---------------------------------------------------------------------------


def test_unknown_api_route_returns_json_404(http):
    body, status = _request(f"{http}/api/does-not-exist", "GET")
    assert status == 404
    assert body == {"ok": False, "error": "not found"}


def test_nul_byte_static_path_returns_400(http):
    """GET /%00 曾让 os.path.realpath 抛 ValueError -> 空响应 + traceback."""
    from http.client import HTTPConnection

    port = int(http.rsplit(":", 1)[1])
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", "/%00")
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 400
    finally:
        conn.close()


def test_export_failure_does_not_leak_absolute_path(http, tmp_db):
    """OS 错误文案含绝对路径, 不能回显给客户端 (P3-6)."""
    directory = str(tmp_db)
    server.approve_path(directory, server.APPROVAL_SAVE)
    body, status = _request(f"{http}/api/backup/export", "POST", {"path": directory})
    assert status == 500
    assert body["ok"] is False
    assert directory not in body["error"]
    assert "/" not in body["error"]


def test_malformed_json_body_is_400_not_403(http):
    """非法 JSON body 曾被并进"路径未授权"的 403, 语义误导; 应为 400."""
    body, status = _post_raw(f"{http}/api/export/csv", b"{not-json")
    assert status == 400
    assert body["ok"] is False


def test_success_responses_have_ok_field(http):
    """契约统一: 成功响应都带 ok=true (此前 dashboard/heatmap/records 无 ok)."""
    for url in (
        f"{http}/api/version",
        f"{http}/api/state",
        f"{http}/api/dashboard?range=today",
        f"{http}/api/heatmap?days=7",
        f"{http}/api/model_trend?days=7",
        f"{http}/api/usage/records?page=1",
        f"{http}/api/usage/sessions?page=1",
        f"{http}/api/settings",
        f"{http}/api/usage/prune",
    ):
        body, status = _get(url)
        assert status == 200, url
        assert body.get("ok") is True, url


def test_state_exposes_token_storage_mode(http):
    """I11: 只读展示凭证存储形态, 不改变存储行为."""
    body, status = _get(f"{http}/api/state")
    assert status == 200
    assert body["token_storage"] in ("keychain", "dpapi", "plain")


# ---------------------------------------------------------------------------
# I5: 更新检查 async + status (保留原同步端点)
# ---------------------------------------------------------------------------


_UPDATE_RESULT = {
    "has_update": False,
    "current": "2.2.2",
    "latest": "v2.2.2",
    "release_url": "https://github.com/x/y/releases/tag/v2.2.2",
    "notes": "",
}


def _wait_update_check(timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        state, _ = _get(f"{_wait_update_check.base}/api/update/check/status")
        if state["state"] != "checking":
            return state
        time.sleep(0.02)
    raise AssertionError("检查更新状态一直停在 checking")


def test_update_check_sync_route_kept(http, monkeypatch):
    """I5 additive: 原同步 GET 语义/结构不变 (测试与旧前端依赖).

    N3: 成功响应统一带 ok=true (结果字段结构不变, 前端按 has_update 读).
    """
    monkeypatch.setattr(server, "check_update", lambda: dict(_UPDATE_RESULT))
    body, status = _get(f"{http}/api/update/check")
    assert status == 200
    assert body == {"ok": True, **_UPDATE_RESULT}


def test_update_check_sync_route_error_502(http, monkeypatch):
    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(server, "check_update", boom)
    try:
        _get(f"{http}/api/update/check")
        raise AssertionError("502 应当抛 HTTPError")
    except urllib.error.HTTPError as exc:
        assert exc.code == 502
        body = json.loads(exc.read().decode("utf-8"))
    assert body["ok"] is False and "network down" in body["error"]


def test_update_check_async_and_status(http, monkeypatch):
    monkeypatch.setattr(server, "check_update", lambda: dict(_UPDATE_RESULT))
    body, status = _request(f"{http}/api/update/check/async", "POST", {})
    assert status == 200
    assert body["ok"] is True and body["state"] == "checking"
    assert "already" not in body

    _wait_update_check.base = http
    final = _wait_update_check()
    assert final == {"ok": True, "state": "done", "result": _UPDATE_RESULT, "error": ""}


def test_update_check_async_already_running(http, monkeypatch):
    from threading import Event

    gate = Event()
    monkeypatch.setattr(
        server, "check_update", lambda: (gate.wait(5), dict(_UPDATE_RESULT))[1])

    first, status = _request(f"{http}/api/update/check/async", "POST", {})
    assert status == 200 and first["ok"] is True and "already" not in first
    second, status = _request(f"{http}/api/update/check/async", "POST", {})
    assert status == 200 and second["already"] is True and second["state"] == "checking"

    gate.set()
    _wait_update_check.base = http
    assert _wait_update_check()["state"] == "done"


def test_update_check_async_error_status(http, monkeypatch):
    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(server, "check_update", boom)
    _request(f"{http}/api/update/check/async", "POST", {})
    _wait_update_check.base = http
    final = _wait_update_check()
    assert final["state"] == "error"
    assert final["result"] is None
    assert "network down" in final["error"]


# ---------------------------------------------------------------------------
# I8: /api/update/open 默认列表页 + 传入 URL 白名单校验
# ---------------------------------------------------------------------------


def test_update_open_defaults_to_releases_list(http, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    body, status = _request(f"{http}/api/update/open", "POST")
    assert status == 200 and body == {"ok": True}
    assert opened == [f"https://github.com/{updater.REPO}/releases"]


def test_update_open_accepts_release_url(http, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    url = f"https://github.com/{updater.REPO}/releases/tag/v2.2.2"
    body, status = _request(f"{http}/api/update/open", "POST", {"url": url})
    assert status == 200 and body == {"ok": True}
    assert opened == [url]


def test_update_open_rejects_foreign_urls(http, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    bad_urls = [
        "https://evil.example/releases",
        "https://github.com/other/repo/releases",
        "http://github.com/whatever/releases",
        f"https://github.com/{updater.REPO}/releases@evil.example/",
        f"https://github.com/{updater.REPO}/issues",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ]
    for bad in bad_urls:
        body, status = _request(f"{http}/api/update/open", "POST", {"url": bad})
        assert status == 400, bad
        assert body["ok"] is False
    assert opened == []  # 一律不得真的打开


def test_update_open_rejects_invalid_json_body(http, monkeypatch):
    monkeypatch.setattr("webbrowser.open", lambda url: True)
    body, status = _post_raw(f"{http}/api/update/open", b"{broken")
    assert status == 400 and body["ok"] is False


def test_record_cycle_bounds_uses_stable_window_kind(tmp_db):
    """P3-19: 窗口身份用 API 客户端的稳定 kind, 不再依赖展示文案 "Monthly".

    文案会本地化/改名; 若协议仍按 "Monthly" 判断, 改名会静默破坏周期落库.
    """
    reset = (datetime.now(timezone.utc) + timedelta(days=20)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    # 非 monthly 的 kind: 即使 label 恰好叫 "Monthly" 也不得落 monthly_reset
    server._record_cycle_bounds(1, {
        "windows": [{"label": "Monthly", "kind": "rolling", "reset_at": reset}]})
    assert db.monthly_cycle_start(1) is None
    # 本地化 label + kind=monthly: 正常落库
    server._record_cycle_bounds(1, {
        "windows": [{"label": "月度", "kind": "monthly", "reset_at": reset}]})
    assert db.monthly_cycle_start(1) is not None


# ---------------------------------------------------------------------------
# N4: 备份导入长写锁与同步的互斥 (维护态, 而非 database is locked)
# ---------------------------------------------------------------------------


def _write_gz(path, body: dict):
    path.write_bytes(gzip.compress(json.dumps(body).encode("utf-8")))
    return path


def _empty_backup(tmp_db):
    return _write_gz(
        tmp_db / "empty-backup.json.gz",
        {"app": "GoGauge", "version": 1, "accounts": [], "records": []},
    )


def _seed_export_backup(tmp_db) -> str:
    """造一个含 1 条记录的真实备份文件 (用于慢导入/并发用例)."""
    aid = db.add_account(
        "tok-import-n4", "wrk_import_n4", switch=True, provider=db.PROVIDER_OPENCODE)
    db.insert_usage_records([_rec("imported-n4-1", _stamp(0))], aid)
    path = tmp_db / "import-n4.json.gz"
    backup.export_backup(str(path))
    server.approve_path(str(path), server.APPROVAL_OPEN)
    return str(path)


def test_import_route_rejected_while_sync_running(http, tmp_db):
    """N4: 同步进行中导入 -> 409, 不排队等锁 (避免 database is locked)."""
    path = _empty_backup(tmp_db)
    server.approve_path(str(path), server.APPROVAL_OPEN)
    with server._sync_lock:
        server._sync_state["running"] = True
    try:
        body, status = _request(
            f"{http}/api/backup/import", "POST", {"path": str(path)})
    finally:
        with server._sync_lock:
            server._sync_state["running"] = False
    assert status == 409, body
    assert body["ok"] is False and "同步" in body["error"]
    assert backup.is_importing() is False  # 被拒的请求不得留下维护态


def test_sync_route_rejected_while_importing(http, tmp_db, monkeypatch):
    """N4: 导入维护态中新同步 -> 409; 清理后立刻可用."""
    db.add_account("tok-sync-imp", "wrk_sync_imp", switch=True,
                   provider=db.PROVIDER_OPENCODE)
    backup._importing.set()
    try:
        body, status = _request(f"{http}/api/sync?mode=incremental", "POST", {})
        assert status == 409, body
        assert body["ok"] is False and "导入进行中" in body["error"]
    finally:
        backup._importing.clear()

    started: dict = {}
    monkeypatch.setattr(
        server, "sync_all_async", lambda mode: started.setdefault("mode", mode))
    body, status = _request(f"{http}/api/sync?mode=incremental", "POST", {})
    assert status == 200 and body["ok"] is True
    assert started["mode"] == "incremental"


def test_sync_usage_refused_directly_while_importing(http, tmp_db):
    """维护态对直达调用 (自动定时器/后台线程) 也生效: 返回可读错误而非抛锁异常."""
    db.add_account("tok-direct", "wrk_direct", switch=True,
                   provider=db.PROVIDER_OPENCODE)
    backup._importing.set()
    try:
        result = server.sync_usage("incremental")
    finally:
        backup._importing.clear()
    assert result["ok"] is False and result["error"] == "导入进行中"


def test_slow_import_blocks_sync_without_db_locked(http, tmp_db, monkeypatch):
    """N4 核心: 模拟慢导入 (写事务内挂起) 并发 POST /api/sync -> 409 维护态.

    若没有维护态互斥, 同步会尝试读 settings/写库并排队等导入的写锁, 15s
    busy_timeout 用尽后报 "database is locked" (同步失败/partial).
    """
    path = _seed_export_backup(tmp_db)
    started = threading.Event()
    release = threading.Event()
    real_insert = db.insert_usage_records

    def slow_insert(*args, **kwargs):
        started.set()
        assert release.wait(10), "测试没有放行慢导入"
        return real_insert(*args, **kwargs)

    monkeypatch.setattr(db, "insert_usage_records", slow_insert)
    holder: dict = {}

    def run_import() -> None:
        holder["result"] = _request(
            f"{http}/api/backup/import", "POST", {"path": path})

    thread = threading.Thread(target=run_import, daemon=True)
    thread.start()
    try:
        assert started.wait(10), "导入没有进入写事务"
        # 导入持写锁期间: 新同步请求明确 409, 不进 DB 排队
        body, status = _request(f"{http}/api/sync?mode=incremental", "POST", {})
        assert status == 409, body
        assert body["ok"] is False and "导入进行中" in body["error"]
        # 直达调用同样被维护态拦下 (不是 database is locked)
        direct = server.sync_usage("incremental")
        assert direct["ok"] is False and direct["error"] == "导入进行中"
        # 并发第二个导入同样 409
        body2, status2 = _request(
            f"{http}/api/backup/import", "POST", {"path": path})
        assert status2 == 409 and "导入" in body2["error"]
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive(), "导入线程未结束"
    body, status = holder["result"]
    assert status == 200 and body["ok"] is True
    assert backup.is_importing() is False
    # 导入结束后同步立刻可用 (打桩避免真网络)
    called: dict = {}
    monkeypatch.setattr(
        server, "sync_all_async", lambda mode: called.setdefault("mode", mode))
    body, status = _request(f"{http}/api/sync?mode=incremental", "POST", {})
    assert status == 200 and body["ok"] is True and called["mode"] == "incremental"


def test_failed_import_clears_maintenance_and_does_not_bump(http, tmp_db, monkeypatch):
    """N4: 导入失败也要清理维护态; 校验失败零写入 -> 不 bump 聚合代数."""
    path = _write_gz(tmp_db / "foreign-n4.json.gz", {"app": "Other"})
    server.approve_path(str(path), server.APPROVAL_OPEN)
    before_gen = server._agg_generation(None)
    body, status = _request(
        f"{http}/api/backup/import", "POST", {"path": str(path)})
    assert status == 400 and body["ok"] is False
    assert backup.is_importing() is False
    # 校验失败 (零写入) 不需要失效缓存; 成功路径才 bump (见 perf_server_cache 用例)
    assert server._agg_generation(None) == before_gen


def test_import_write_failure_clears_maintenance(http, tmp_db, monkeypatch):
    """N4: 写事务中途异常 -> rollback + 维护态清理, 同步入口立刻恢复."""
    path = _seed_export_backup(tmp_db)
    monkeypatch.setattr(
        db, "insert_usage_records",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    body, status = _request(
        f"{http}/api/backup/import", "POST", {"path": path})
    assert status == 500 and body["ok"] is False
    assert backup.is_importing() is False
    # 维护态已清理: 同步路由不再 409 (这里打桩避免真网络)
    monkeypatch.setattr(server, "sync_all_async", lambda mode: None)
    body, status = _request(f"{http}/api/sync?mode=incremental", "POST", {})
    assert status == 200 and body["ok"] is True


def test_update_download_status_has_ok_field(http):
    """N3: 下载状态机成功响应也带 ok=true (state/path/... 结构不变)."""
    with server._update_lock:
        server._update_download.update(
            {"state": "idle", "path": "", "error": "", "latest": ""})
    body, status = _get(f"{http}/api/update/download/status")
    assert status == 200
    assert body["ok"] is True
    assert body["state"] == "idle"
