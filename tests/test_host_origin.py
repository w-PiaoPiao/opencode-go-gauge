"""本地 HTTP 服务的 Host/Origin 回环校验 + I4 token 鉴权测试.

背景: 这个服务没有任何账户体系, 唯一的边界就是:
- `_reject_non_local`: Host 必须是回环地址（防 DNS rebinding 把外部域名解析到
  127.0.0.1）, 浏览器跨站请求必带 Origin（防 CSRF）;
- I4 `set_auth_token`: 设置后所有 `/api/*` 必须带 `X-GoGauge-Token`
  （静态资源不校验）。
一旦这两道门回归, 同机/任意网页都能 POST 导出、导入、删除、触发同步。此前
两个函数都没有测试（只测了 URL 路径穿越与导出路径授权）。

实现方式: 起真实 `ThreadingHTTPServer`, 用 **raw socket** 发请求 —— 只有这样才能
精确控制 Host/Origin 头（urllib 会按 URL 覆写 Host, 也发不出 `Origin: null`）。
"""
from __future__ import annotations

import json
import socket

import pytest

from app import db, server

API_VERSION_PATH = "/api/version"


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    """真实服务 + 独立临时库; 停掉汇率网络请求, 避免测试打外网."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    db._schema_init_path = None
    db.close_db()
    monkeypatch.setattr(server, "_fetch_usd_cny", lambda: 7.2)
    host, port = server.start_server("127.0.0.1", 0)
    try:
        yield host, port
    finally:
        server.stop_server()
        db.close_db()
        db._schema_init_path = None
        # 鉴权 token 是进程级状态: 若某用例没走到 finally 的复位, 这里再兜一次底
        if hasattr(server, "set_auth_token"):
            server.set_auth_token(None)


# ---------------------------------------------------------------------------
# raw socket helpers
# ---------------------------------------------------------------------------


def _raw_request(host: str, port: int, request: bytes, timeout: float = 5.0) -> tuple[int, bytes]:
    """发送原始 HTTP 请求, 返回 (状态码, 完整响应字节)."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(request)
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    data = b"".join(chunks)
    assert data, "服务端未返回任何响应"
    status_line = data.split(b"\r\n", 1)[0]
    return int(status_line.split(b" ")[1]), data


def _request_bytes(
    method: str,
    path: str,
    host_header: str,
    extra_headers: tuple[str, ...] = (),
) -> bytes:
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host_header}", "Connection: close"]
    lines.extend(extra_headers)
    return ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")


def _json_body(data: bytes) -> dict:
    head, _, body = data.partition(b"\r\n\r\n")
    return json.loads(body.decode("utf-8"))


def _loopback_host(port: int) -> str:
    return f"127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Host 校验 (DNS rebinding)
# ---------------------------------------------------------------------------


def test_host_loopback_allowed(srv):
    host, port = srv
    status, data = _raw_request(
        host, port, _request_bytes("GET", API_VERSION_PATH, _loopback_host(port))
    )
    assert status == 200
    assert "version" in _json_body(data)


def test_host_localhost_allowed(srv):
    host, port = srv
    status, _ = _raw_request(
        host, port,
        _request_bytes("GET", API_VERSION_PATH, f"localhost:{port}"),
    )
    assert status == 200


def test_host_ipv6_loopback_allowed(srv):
    """`[::1]` 也是合法回环 Host（服务本身绑 127.0.0.1, 但 Host 头允许）."""
    host, port = srv
    status, _ = _raw_request(
        host, port,
        _request_bytes("GET", API_VERSION_PATH, f"[::1]:{port}"),
    )
    assert status == 200


def test_host_non_loopback_rejected(srv):
    host, port = srv
    for bad_host in ("evil.example", "evil.example:80", "127.0.0.1.evil.example", "attacker"):
        status, _ = _raw_request(
            host, port,
            _request_bytes("GET", API_VERSION_PATH, bad_host),
        )
        assert status == 403, f"Host={bad_host!r} 应被拒绝"


def test_host_guard_applies_to_static_too(srv):
    host, port = srv
    status, _ = _raw_request(
        host, port,
        _request_bytes("GET", "/", "evil.example"),
    )
    assert status == 403


# ---------------------------------------------------------------------------
# Origin 校验 (CSRF)
# ---------------------------------------------------------------------------


def test_origin_non_loopback_rejected(srv):
    host, port = srv
    status, _ = _raw_request(
        host, port,
        _request_bytes(
            "GET", API_VERSION_PATH, _loopback_host(port),
            ("Origin: http://evil.example",),
        ),
    )
    assert status == 403


def test_origin_null_rejected(srv):
    """`Origin: null`（sandboxed iframe / 本地 file:// 页面）必须拒绝."""
    host, port = srv
    status, _ = _raw_request(
        host, port,
        _request_bytes(
            "GET", API_VERSION_PATH, _loopback_host(port), ("Origin: null",)
        ),
    )
    assert status == 403


def test_origin_loopback_allowed(srv):
    host, port = srv
    status, _ = _raw_request(
        host, port,
        _request_bytes(
            "GET", API_VERSION_PATH, _loopback_host(port),
            (f"Origin: http://127.0.0.1:{port}",),
        ),
    )
    assert status == 200


def test_no_origin_allowed_for_local_processes(srv):
    """无 Origin 的请求（curl / 本机脚本）放行: 本机进程在安全边界内."""
    host, port = srv
    status, _ = _raw_request(
        host, port, _request_bytes("GET", API_VERSION_PATH, _loopback_host(port))
    )
    assert status == 200


def test_post_with_cross_site_origin_rejected(srv):
    """写接口（POST）同样受 Origin 校验保护, 且不产生副作用."""
    host, port = srv
    status, _ = _raw_request(
        host, port,
        _request_bytes(
            "POST", "/api/logout", _loopback_host(port),
            ("Origin: https://evil.example",),
        ),
    )
    assert status == 403


# ---------------------------------------------------------------------------
# I4: 本地 HTTP token（契约见实施计划 §2 I4, server-fixer 已确认）
# ---------------------------------------------------------------------------


def test_api_requires_token_when_set(srv):
    host, port = srv
    token = "unit-test-token-0123456789"
    server.set_auth_token(token)
    try:
        assert server.auth_token() == token

        # 1) 无 header -> 401 JSON
        status, data = _raw_request(
            host, port, _request_bytes("GET", API_VERSION_PATH, _loopback_host(port))
        )
        assert status == 401
        body = _json_body(data)
        assert body["ok"] is False
        assert body["error"] == "unauthorized"

        # 2) 正确 header -> 200
        status, data = _raw_request(
            host, port,
            _request_bytes(
                "GET", API_VERSION_PATH, _loopback_host(port),
                (f"X-GoGauge-Token: {token}",),
            ),
        )
        assert status == 200
        assert "version" in _json_body(data)

        # 3) 错误 token -> 401
        status, _ = _raw_request(
            host, port,
            _request_bytes(
                "GET", API_VERSION_PATH, _loopback_host(port),
                ("X-GoGauge-Token: wrong-token",),
            ),
        )
        assert status == 401

        # 4) 静态资源不校验（否则页面本身都加载不出来）
        status, _ = _raw_request(
            host, port, _request_bytes("GET", "/", _loopback_host(port))
        )
        assert status == 200
    finally:
        server.set_auth_token(None)

    # 5) 复位后恢复零鉴权（现有测试/开发模式依赖这一语义）
    status, _ = _raw_request(
        host, port, _request_bytes("GET", API_VERSION_PATH, _loopback_host(port))
    )
    assert status == 200


# ---------------------------------------------------------------------------
# SEC-3: 无 Origin 的跨站 GET 不得驱动带用户凭证的出站请求
# ---------------------------------------------------------------------------
#
# 浏览器对跨站 GET (<img>/<script>/fetch(mode:"no-cors")) 不发 Origin, 因此只靠
# Origin 的 CSRF 防线挡不住它们; 这类请求能打到 /api/dashboard、
# /api/accounts/overview 等端点, 触发用**用户凭证**的上游配额/汇率/更新检查.
# Sec-Fetch-Site 是浏览器在 GET 上也会带的元数据, 只拦明确声明 cross-site 的.


def test_cross_site_fetch_metadata_rejected_on_get(srv):
    """Sec-Fetch-Site: cross-site + 无 Origin -> 403 (GET 只读端点也要挡)."""
    host, port = srv
    for path in ("/api/dashboard", "/api/accounts/overview"):
        status, _ = _raw_request(
            host, port,
            _request_bytes(
                "GET", path, _loopback_host(port),
                ("Sec-Fetch-Site: cross-site",),  # 刻意不带 Origin: 跨站 GET 本来就没有
            ),
        )
        assert status == 403, f"{path} 应被 cross-site 拦截"


def test_cross_site_fetch_metadata_rejected_on_post(srv):
    """写端点同样: cross-site 元数据一律 403, 且不产生副作用."""
    host, port = srv
    status, _ = _raw_request(
        host, port,
        _request_bytes(
            "POST", "/api/logout", _loopback_host(port),
            ("Sec-Fetch-Site: cross-site",),
        ),
    )
    assert status == 403


def test_same_origin_and_missing_fetch_metadata_allowed(srv):
    """只拦 cross-site: same-origin/same-site/none/缺省 (老 WebKit/本机脚本) 放行."""
    host, port = srv
    for extra in (
        ("Sec-Fetch-Site: same-origin",),
        ("Sec-Fetch-Site: same-site",),
        ("Sec-Fetch-Site: none",),
        ("Sec-Fetch-Site: SAME-ORIGIN",),  # 大小写不敏感
        (),
    ):
        status, data = _raw_request(
            host, port,
            _request_bytes("GET", API_VERSION_PATH, _loopback_host(port), extra),
        )
        assert status == 200, f"extra={extra!r} 不应被误伤"
        assert "version" in _json_body(data)
