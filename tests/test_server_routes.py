"""server.py 本地 HTTP 路由冒烟测试 (127.0.0.1 起真实服务, 只测无外网依赖的路由)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from app import db, server


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """独立临时库: 重定向 data_dir (同 test_db_multiuser)."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


@pytest.fixture()
def http(tmp_db):
    host, port = server.start_server("127.0.0.1", 0)
    yield f"http://{host}:{port}"
    server.stop_server()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status


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
