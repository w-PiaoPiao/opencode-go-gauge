"""导出/导入路由的路径授权 (confused deputy 防护).

这些路由过去直接采用请求体里的绝对路径写文件, 而本地 HTTP 层没有鉴权
(只有 Host/Origin 回环校验). 同机任意进程因此能借本应用以登录用户身份覆写
任意可写文件. 现在真实路径只认用户在系统对话框里亲自选过的那些.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from app import db, server


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


@pytest.fixture()
def http(tmp_db):
    host, port = server.start_server("127.0.0.1", 0)
    yield f"http://{host}:{port}"
    server.stop_server()


def _post(url: str, body: dict):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8")), exc.code


@pytest.fixture(autouse=True)
def _clear_approved():
    with server._approved_lock:
        server._APPROVED_PATHS.clear()
    yield
    with server._approved_lock:
        server._APPROVED_PATHS.clear()


def test_export_csv_rejects_unapproved_path(http, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("ORIGINAL", encoding="utf-8")

    body, status = _post(f"{http}/api/export/csv", {"path": str(victim)})

    assert status == 403
    assert body["ok"] is False
    # 关键: 既有文件内容没被覆写
    assert victim.read_text(encoding="utf-8") == "ORIGINAL"


def test_backup_export_and_import_reject_unapproved_path(http, tmp_path):
    victim = tmp_path / "victim.json.gz"
    victim.write_text("ORIGINAL", encoding="utf-8")

    body, status = _post(f"{http}/api/backup/export", {"path": str(victim)})
    assert status == 403 and body["ok"] is False

    body, status = _post(f"{http}/api/backup/import", {"path": str(victim)})
    assert status == 403 and body["ok"] is False

    assert victim.read_text(encoding="utf-8") == "ORIGINAL"


def test_approved_path_is_accepted(http, tmp_path):
    """用户在对话框里选过之后, 同一条路由正常工作."""
    target = tmp_path / "out.csv"
    server.approve_path(str(target))

    body, status = _post(f"{http}/api/export/csv", {"path": str(target)})

    assert status == 200, body
    assert body["ok"] is True
    assert target.exists()


def test_approval_matches_normalized_path(http, tmp_path):
    """登记与请求可以写法不同 (分隔符/大小写/相对段), 归一化后视为同一条."""
    target = tmp_path / "sub" / "out.csv"
    target.parent.mkdir()
    target.write_text("x", encoding="utf-8")
    server.approve_path(str(target))

    messy = str(tmp_path / "sub" / "." / "out.csv")
    body, status = _post(f"{http}/api/export/csv", {"path": messy})

    assert status == 200, body
    assert body["ok"] is True


def test_empty_path_is_rejected(http):
    body, status = _post(f"{http}/api/export/csv", {"path": ""})
    assert status == 403 and body["ok"] is False


def test_resolve_approved_path_rejects_expired(http, tmp_path):
    import time as _time

    target = tmp_path / "out.csv"
    server.approve_path(str(target))
    assert server.resolve_approved_path(str(target)) is not None

    # 把登记的到期时间拨到过去, 模拟超过 TTL
    real = server._real_path(str(target))
    with server._approved_lock:
        server._APPROVED_PATHS[real] = _time.time() - 1
    assert server.resolve_approved_path(str(target)) is None


def test_read_json_body_rejects_negative_length():
    """负 Content-Length 必须被拒: rfile.read(-1) 语义是读到 EOF, 会阻塞到超时."""

    class _H:
        headers = {"Content-Length": "-1"}

        class rfile:
            @staticmethod
            def read(n):  # pragma: no cover - 不应被调用
                raise AssertionError("负长度不应触发 read()")

    with pytest.raises(ValueError):
        server._read_json_body(_H())


def test_read_json_body_rejects_oversized():
    class _H:
        headers = {"Content-Length": str(server._MAX_BODY_BYTES + 1)}

    with pytest.raises(ValueError):
        server._read_json_body(_H())


def test_negative_content_length_does_not_hang(http):
    """端到端: 畸形请求要立刻拿到 4xx, 而不是占住线程等 socket 超时."""
    import socket

    sock = socket.create_connection(("127.0.0.1", int(http.rsplit(":", 1)[1])), timeout=5)
    try:
        sock.sendall(
            b"POST /api/export/csv HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: -1\r\n\r\n"
        )
        resp = sock.recv(200).decode("utf-8", errors="replace")
    finally:
        sock.close()

    status_line = resp.split("\r\n")[0]
    assert status_line.split(" ")[1].startswith("4"), status_line