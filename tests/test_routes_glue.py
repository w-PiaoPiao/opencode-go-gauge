"""此前 0 测试引用的 HTTP 端点 glue 测试（起真实服务, 只 mock 网络侧）.

覆盖端点:
- `GET  /api/version`
- `GET  /api/update/check`（同步版, 保留旧语义）+ 错误映射 502
- `POST /api/update/check/async` + `GET /api/update/check/status`（I5 异步版,
  server-fixer 已确认契约: status 严格 `{state, result, error}`）
- `POST /api/update/open`（仅放行本仓库 releases 地址, 否则 400）
- `POST /api/update/download` + `GET /api/update/download/status`（状态机/错误映射）
- `GET  /api/accounts/overview`
- `GET  /api/usage/sessions`
- 未知 `/api/*` 路由: JSON 404（不是 HTML send_error）

这些端点此前只被前端调用, 没有任何 pytest 覆盖; 回归表现为 UI 卡住/弹错,
而不是后端异常。测试用 `monkeypatch.setattr(server, "check_update"/"download_update")`
注入网络结果 —— 后台线程必须调用 server 模块级符号才能被拦截（已与 server-fixer 对齐）。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

import app as app_pkg
from app import db, server


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    """真实服务 + 独立临时库; 屏蔽汇率/配额的后台网络线程."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    db._schema_init_path = None
    db.close_db()
    monkeypatch.setattr(server, "_fetch_usd_cny", lambda: 7.2)
    # 账户总览会为每个已登录账号触发后台配额刷新: 本文件只测 glue, 不打网络
    monkeypatch.setattr(server, "_ensure_quota_async", lambda *a, **k: None)
    host, port = server.start_server("127.0.0.1", 0)
    try:
        yield f"http://{host}:{port}"
    finally:
        server.stop_server()
        db.close_db()
        db._schema_init_path = None
        # 下载状态机是进程级全局: 收尾复位, 避免污染后续测试
        with server._update_lock:
            server._update_download.update(
                {"state": "idle", "path": "", "error": "", "latest": ""}
            )


def _request(base: str, method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw}


def _get(base: str, path: str):
    return _request(base, "GET", path)


def _post(base: str, path: str, body: dict | None = None):
    return _request(base, "POST", path, body)


def _wait_update_check_state(base: str, timeout: float = 3.0) -> dict:
    """轮询 I5 异步检查状态, 返回首次进入终态的 body."""
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        status, last = _get(base, "/api/update/check/status")
        assert status == 200, last
        if last.get("state") in ("done", "error", "idle"):
            return last
        time.sleep(0.02)
    pytest.fail(f"异步更新检查未在 {timeout}s 内进入终态: {last}")


def _wait_download_state(base: str, timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        status, last = _get(base, "/api/update/download/status")
        assert status == 200, last
        if last.get("state") != "checking":
            return last
        time.sleep(0.02)
    pytest.fail(f"更新下载状态机未在 {timeout}s 内离开 checking: {last}")


# ---------------------------------------------------------------------------
# /api/version
# ---------------------------------------------------------------------------


def test_version_route(srv):
    status, body = _get(srv, "/api/version")
    assert status == 200
    assert body["version"] == app_pkg.__version__


# ---------------------------------------------------------------------------
# /api/update/check（同步, 旧语义保留）
# ---------------------------------------------------------------------------


def test_update_check_happy(srv, monkeypatch):
    payload = {
        "has_update": True,
        "current": app_pkg.__version__,
        "latest": "v9.9.9",
        "release_url": "https://github.com/o/r/releases/tag/v9.9.9",
        "notes": "notes",
    }
    monkeypatch.setattr(server, "check_update", lambda: dict(payload))
    status, body = _get(srv, "/api/update/check")
    assert status == 200
    for key, value in payload.items():
        assert body[key] == value


def test_update_check_error_maps_to_502(srv, monkeypatch):
    monkeypatch.setattr(
        server, "check_update",
        lambda: (_ for _ in ()).throw(RuntimeError("github unreachable")),
    )
    status, body = _get(srv, "/api/update/check")
    assert status == 502
    assert "github unreachable" in body["error"]


# ---------------------------------------------------------------------------
# I5: 异步检查 + 状态轮询
# ---------------------------------------------------------------------------


def test_update_check_async_happy(srv, monkeypatch):
    payload = {
        "has_update": True,
        "current": app_pkg.__version__,
        "latest": "v9.9.9",
        "release_url": "https://github.com/o/r/releases/tag/v9.9.9",
        "notes": "async notes",
    }
    monkeypatch.setattr(server, "check_update", lambda: dict(payload))

    status, body = _post(srv, "/api/update/check/async")
    assert status == 200, body
    assert body["ok"] is True
    assert body["state"] == "checking"

    final = _wait_update_check_state(srv)
    assert final["state"] == "done", final
    assert final["result"]["latest"] == "v9.9.9"
    assert final["error"] == ""


def test_update_check_async_error_maps_to_state_error(srv, monkeypatch):
    monkeypatch.setattr(
        server, "check_update",
        lambda: (_ for _ in ()).throw(RuntimeError("network down")),
    )
    # 等上一轮状态回到非 checking（同进程内状态机是全局的）
    _wait_update_check_state(srv)
    status, body = _post(srv, "/api/update/check/async")
    assert status == 200, body
    final = _wait_update_check_state(srv)
    assert final["state"] == "error", final
    assert final["result"] is None
    assert "network down" in final["error"]


# ---------------------------------------------------------------------------
# /api/update/open（URL 白名单）
# ---------------------------------------------------------------------------


def test_update_open_rejects_external_url(srv, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, *a, **k: opened.append(url))
    status, body = _post(srv, "/api/update/open", {"url": "https://evil.example/x"})
    assert status == 400, body
    assert body["ok"] is False
    assert opened == [], "非法 URL 不得交给 webbrowser"


def test_update_open_defaults_to_releases_page(srv, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, *a, **k: opened.append(url))
    status, body = _post(srv, "/api/update/open")
    assert status == 200, body
    assert opened and "/releases" in opened[0]


# ---------------------------------------------------------------------------
# /api/update/download + status（状态机）
# ---------------------------------------------------------------------------


def test_update_download_state_machine_error(srv, monkeypatch):
    monkeypatch.setattr(
        server, "download_update",
        lambda dest: {"state": "error", "path": "", "latest": "v9.9.9", "error": "boom"},
    )
    status, body = _post(srv, "/api/update/download")
    assert status == 200 and body["ok"] is True
    final = _wait_download_state(srv)
    assert final["state"] == "error"
    assert "boom" in final["error"]


def test_update_download_busy_returns_409(srv):
    with server._update_lock:
        server._update_download.update({"state": "downloading", "path": "", "error": "", "latest": ""})
    try:
        status, body = _post(srv, "/api/update/download")
        assert status == 409
        assert body["ok"] is False
    finally:
        with server._update_lock:
            server._update_download.update(
                {"state": "idle", "path": "", "error": "", "latest": ""}
            )


def test_update_download_done_reveals_file(srv, monkeypatch):
    revealed: list[list[str]] = []
    monkeypatch.setattr("subprocess.Popen", lambda args, *a, **k: revealed.append(list(args)))
    monkeypatch.setattr(
        server, "download_update",
        lambda dest: {"state": "done", "path": "/tmp/GoGauge-fake.zip", "latest": "v9.9.9", "error": ""},
    )
    status, body = _post(srv, "/api/update/download")
    assert status == 200 and body["ok"] is True
    final = _wait_download_state(srv)
    assert final["state"] == "done"
    assert final["path"].endswith("GoGauge-fake.zip")
    # 非 Windows 走 `open -R <path>`; Windows 走 explorer /select,
    assert revealed, "下载完成后应在文件管理器中定位"


# ---------------------------------------------------------------------------
# /api/accounts/overview
# ---------------------------------------------------------------------------


def test_accounts_overview_lists_logged_in_accounts(srv):
    aid = db.add_account("tok-overview", "wsA", provider=db.PROVIDER_OPENCODE)
    status, body = _get(srv, "/api/accounts/overview")
    assert status == 200
    assert body["ok"] is True
    assert body["active_id"] == aid
    assert len(body["accounts"]) == 1, "只返回已登录账号（种子 Default 无 token, 不应出现）"
    acc = body["accounts"][0]
    assert acc["id"] == aid
    assert acc["logged_in"] is True
    assert acc["active"] is True
    assert acc["provider"] == db.PROVIDER_OPENCODE
    assert "today" in acc and "daily7" in acc and "today_trend" in acc
    assert body["exchange_rate"]["usd_cny"] == 7.2
    assert isinstance(body["server_time"], str) and body["server_time"]


# ---------------------------------------------------------------------------
# /api/usage/sessions
# ---------------------------------------------------------------------------


def _rec(usg_id: str, session_id: str, *, model: str = "m1") -> dict:
    return {
        "usg_id": usg_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": model,
        "provider": "opencode",
        "input_tokens": 10,
        "output_tokens": 5,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": 0.01,
        "session_id": session_id,
        "key_id": "key-1",
    }


def test_usage_sessions_lists_grouped_rows(srv):
    aid = db.get_active_account_id()
    db.insert_usage_records(
        [_rec("s-1", "ses-alpha"), _rec("s-2", "ses-alpha"), _rec("s-3", "ses-beta")],
        aid,
    )
    status, body = _get(srv, "/api/usage/sessions?page=1&page_size=10")
    assert status == 200
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["filter"]["days"] is None
    sessions = {r["session_id"] for r in body["records"]}
    assert "ses-alpha" in sessions
    assert body["total"] == 2, f"按 session 分组应得到 2 条, 实际: {body['total']}"


def test_usage_sessions_clamps_params(srv):
    aid = db.get_active_account_id()
    db.insert_usage_records([_rec("s-4", "ses-gamma")], aid)
    status, body = _get(srv, "/api/usage/sessions?page=1&page_size=999&days=abc")
    assert status == 200
    assert body["page_size"] == 50, "page_size 上限 50"
    assert body["filter"]["days"] is None, "非法 days 按未指定处理, 不报错"


# ---------------------------------------------------------------------------
# 未知路由 / 安全响应头（server-fixer P2-9 契约）
# ---------------------------------------------------------------------------


def test_unknown_api_route_returns_json_404(srv):
    status, body = _get(srv, "/api/does-not-exist")
    assert status == 404
    assert body["ok"] is False
    assert body["error"] == "not found"


def test_security_headers_on_json_and_errors(srv):
    for path, expected_status in (("/api/version", 200), ("/api/does-not-exist", 404)):
        req = urllib.request.Request(srv + path)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                headers = {k.lower(): v for k, v in resp.getheaders()}
        except urllib.error.HTTPError as exc:
            headers = {k.lower(): v for k, v in exc.headers.items()}
        assert headers.get("x-content-type-options") == "nosniff", path
        assert headers.get("x-frame-options") == "DENY", path
        assert "frame-ancestors 'none'" in headers.get("content-security-policy", ""), path
        assert headers.get("referrer-policy") == "no-referrer", path
