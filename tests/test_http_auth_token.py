"""I4 本地 API token 鉴权 + P2-9 安全响应头 + P3-1 显式 MIME 表 (真实 HTTP).

威胁模型: loopback 是主机级共享资源, 同机其他 OS 用户/进程用 netstat 就能找到
ephemeral 端口. token 未配置时 (测试/开发) 不校验; main.py 启动时必设随机 token,
前端从 URL fragment 取到后每个 /api/* 请求带 X-GoGauge-Token.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from app import db, server

_SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


@pytest.fixture()
def http(tmp_db):
    server.set_auth_token(None)
    host, port = server.start_server("127.0.0.1", 0)
    yield f"http://{host}:{port}"
    server.stop_server()
    server.set_auth_token(None)


def _request(url: str, token: str | None = None):
    req = urllib.request.Request(url)
    if token is not None:
        req.add_header("X-GoGauge-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read(), resp.status, dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.read(), exc.code, dict(exc.headers)


def test_token_disabled_by_default(http):
    body, status, _ = _request(f"{http}/api/version")
    assert status == 200
    assert json.loads(body)["version"]


def test_token_required_for_api(http):
    server.set_auth_token("s3cret-token")
    body, status, _ = _request(f"{http}/api/version")
    assert status == 401
    payload = json.loads(body)
    assert payload == {"ok": False, "error": "unauthorized"}

    body, status, _ = _request(f"{http}/api/version", token="wrong-token")
    assert status == 401
    assert json.loads(body)["error"] == "unauthorized"

    body, status, _ = _request(f"{http}/api/version", token="s3cret-token")
    assert status == 200
    assert json.loads(body)["version"]


def test_token_blocks_mutating_routes_too(http):
    """危险写路由与读路由同一道门禁 (缺失 token 一律 401, 不区分方法)."""
    server.set_auth_token("tok")
    req = urllib.request.Request(f"{http}/api/logout", data=b"", method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
        status = 200
    except urllib.error.HTTPError as exc:
        status = exc.code
    assert status == 401


def test_static_resources_not_token_guarded(http):
    """静态资源不校验: token 经 URL fragment 交付, 首屏 HTML/JS 加载不能要 header."""
    server.set_auth_token("tok")
    body, status, headers = _request(f"{http}/")
    assert status == 200
    assert b"GoGauge" in body
    js, status, headers = _request(f"{http}/app.js")
    assert status == 200
    assert "javascript" in headers.get("Content-Type", "").lower()


def test_set_auth_token_none_restores_open_access(http):
    server.set_auth_token("tok")
    assert _request(f"{http}/api/version")[1] == 401
    server.set_auth_token(None)
    assert _request(f"{http}/api/version")[1] == 200
    # 空串等价于不鉴权
    server.set_auth_token("")
    assert server.auth_token() is None


def test_security_headers_on_static_json_and_error_responses(http):
    for url in (f"{http}/", f"{http}/api/version", f"{http}/api/does-not-exist"):
        _, _, headers = _request(url)
        for name, value in _SECURITY_HEADERS.items():
            assert headers.get(name) == value, f"{url} 缺 {name}"

    # 401 (鉴权失败) 与 304 (缓存命中) 同样要带安全头
    server.set_auth_token("tok")
    _, status, headers = _request(f"{http}/api/version")
    assert status == 401
    for name, value in _SECURITY_HEADERS.items():
        assert headers.get(name) == value
    server.set_auth_token(None)

    _, status, headers = _request(f"{http}/")
    etag = headers["ETag"]
    req = urllib.request.Request(f"{http}/")
    req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, headers = resp.status, dict(resp.headers)
    except urllib.error.HTTPError as exc:  # 304 不会被 urlopen 当错误
        status, headers = exc.code, dict(exc.headers)
    assert status == 304
    for name, value in _SECURITY_HEADERS.items():
        assert headers.get(name) == value


def test_explicit_mime_table_used_for_static(http):
    """P3-1: 不依赖 mimetypes/系统注册表, 显式表保证 .js 不会被误判 text/plain."""
    _, status, headers = _request(f"{http}/app.js")
    assert status == 200
    assert headers["Content-Type"].startswith("text/javascript")
    _, status, headers = _request(f"{http}/style.css")
    assert status == 200
    assert headers["Content-Type"].startswith("text/css")
    _, status, headers = _request(f"{http}/")
    assert headers["Content-Type"].startswith("text/html")


def test_content_type_fallback_is_octet_stream():
    assert server._content_type_for("/x/unknown.weird") == "application/octet-stream"
    assert server._content_type_for("/x/app.js").startswith("text/javascript")


def test_security_headers_apply_to_rejected_host(tmp_db):
    """Host 校验失败走 send_error(403): 错误页也必须带安全头 (防绕过加固)."""
    server.set_auth_token(None)
    host, port = server.start_server("127.0.0.1", 0)
    try:
        import http.client

        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.putrequest("GET", "/api/version", skip_host=True)
        conn.putheader("Host", "evil.example")
        conn.endheaders()
        resp = conn.getresponse()
        resp.read()
        try:
            assert resp.status == 403
            for name, value in _SECURITY_HEADERS.items():
                assert resp.getheader(name) == value
        finally:
            conn.close()
    finally:
        server.stop_server()
