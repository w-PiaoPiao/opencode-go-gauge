"""静态资源缓存协商测试: ETag / 304 / If-Modified-Since.

背景: 早期实现对所有静态资源硬编码 `no-cache` 且没有校验器, 每次窗口刷新
都要重下 app.js / 图表库。现在 `_static_response` 用「大小 + mtime_ns」生成弱
ETag, 并支持 If-None-Match / If-Modified-Since 返回 304。

这里补的正是此前完全没测的部分: 一旦 304 逻辑写反（对已变更文件回 304, 或
对未变更文件回 200）, 用户升级后可能长时间看到旧前端配新后端 —— 界面静默错乱,
没有任何报错。本文件不修改 app/web 下任何文件（只读协商行为）。
"""
from __future__ import annotations

import http.client
from email import utils as email_utils

import pytest

from app import db, server


@pytest.fixture()
def srv(tmp_path, monkeypatch):
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


def _get(host: str, port: int, path: str, headers: dict[str, str] | None = None):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 基础校验器
# ---------------------------------------------------------------------------


def test_index_serves_etag_and_cache_headers(srv):
    host, port = srv
    status, headers, body = _get(host, port, "/")
    assert status == 200
    assert b"GoGauge" in body
    assert headers["content-type"].startswith("text/html")
    # 弱 ETag: W/"<size-hex>-<mtime_ns-hex>"
    assert headers["etag"].startswith('W/"') and headers["etag"].endswith('"')
    assert headers["cache-control"] == "no-cache"
    # Last-Modified 必须是合法 HTTP-date
    assert email_utils.parsedate_to_datetime(headers["last-modified"]) is not None


def test_etag_is_stable_between_requests(srv):
    host, port = srv
    _, first, _ = _get(host, port, "/")
    _, second, _ = _get(host, port, "/")
    assert first["etag"] == second["etag"]


def test_if_none_match_returns_304_without_body(srv):
    """协商命中: 304 且不重发资源正文（刷新窗口时省掉重复传输）."""
    host, port = srv
    _, headers, _ = _get(host, port, "/")
    status, second_headers, body = _get(
        host, port, "/", {"If-None-Match": headers["etag"]}
    )
    assert status == 304
    assert body == b""
    assert second_headers["etag"] == headers["etag"]


def test_if_none_match_mismatch_returns_200(srv):
    host, port = srv
    status, _, body = _get(host, port, "/", {"If-None-Match": 'W/"deadbeef-1"'})
    assert status == 200
    assert b"GoGauge" in body


def test_if_modified_since_future_date_returns_304(srv):
    """没有 If-None-Match 时按 If-Modified-Since 协商（浏览器降级路径）."""
    host, port = srv
    _, headers, _ = _get(host, port, "/")
    status, _, body = _get(
        host, port, "/", {"If-Modified-Since": headers["last-modified"]}
    )
    assert status == 304
    assert body == b""


def test_if_modified_since_invalid_date_falls_back_to_200(srv):
    host, port = srv
    status, _, body = _get(host, port, "/", {"If-Modified-Since": "not-a-date"})
    assert status == 200
    assert b"GoGauge" in body


# ---------------------------------------------------------------------------
# 静态资源内容类型与 404
# ---------------------------------------------------------------------------


def test_js_asset_has_javascript_content_type(srv):
    host, port = srv
    status, headers, body = _get(host, port, "/app.js")
    assert status == 200
    assert "javascript" in headers["content-type"]
    assert body


def test_unknown_static_path_404(srv):
    host, port = srv
    status, _, _ = _get(host, port, "/no-such-asset-xyz.js")
    assert status == 404
