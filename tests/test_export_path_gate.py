"""导出/导入路由的路径授权 (confused deputy 防护).

这些路由过去直接采用请求体里的绝对路径写文件, 而本地 HTTP 层没有鉴权
(只有 Host/Origin 回环校验). 同机任意进程因此能借本应用以登录用户身份覆写
任意可写文件. 现在真实路径只认用户在系统对话框里亲自选过的那些.
"""
from __future__ import annotations

import gzip
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
    server.approve_path(str(target), server.APPROVAL_SAVE)

    body, status = _post(f"{http}/api/export/csv", {"path": str(target)})

    assert status == 200, body
    assert body["ok"] is True
    assert target.exists()

    # 同为保存授权: 备份导出也放行 (用途相同即互相可用, 与前端一致)
    pack = tmp_path / "out.json.gz"
    server.approve_path(str(pack), server.APPROVAL_SAVE)
    body, status = _post(f"{http}/api/backup/export", {"path": str(pack)})
    assert status == 200, body
    assert body["ok"] is True


def test_open_approval_imports(http, tmp_path):
    """打开对话框登记过的路径能正常导入 —— 用途绑定不得误伤正常流程."""
    src = tmp_path / "backup.json.gz"
    with gzip.open(src, "wb") as fh:
        fh.write(json.dumps({"app": "GoGauge", "accounts": [], "records": []}).encode("utf-8"))
    server.approve_path(str(src), server.APPROVAL_OPEN)

    body, status = _post(f"{http}/api/backup/import", {"path": str(src)})

    assert status == 200, body
    assert body["ok"] is True


def test_approval_is_bound_to_purpose(http, tmp_path):
    """授权按用途分开: 为导入 (打开对话框) 点过的文件不得被导出覆写.

    用户点头的是"读这个文件", 不是"覆盖它"; 两种对话框的用途不能互相顶替.
    """
    picked = tmp_path / "picked.json.gz"
    picked.write_text("IMPORT-SOURCE", encoding="utf-8")
    server.approve_path(str(picked), server.APPROVAL_OPEN)

    # 开放来源的授权: 导入放行, 导出 (csv / backup) 一律拒绝且不动文件
    body, status = _post(f"{http}/api/backup/export", {"path": str(picked)})
    assert status == 403 and body["ok"] is False
    body, status = _post(f"{http}/api/export/csv", {"path": str(picked)})
    assert status == 403 and body["ok"] is False
    assert picked.read_text(encoding="utf-8") == "IMPORT-SOURCE"

    # 反向: 保存对话框的授权不得被当成导入来源
    target = tmp_path / "out.csv"
    server.approve_path(str(target), server.APPROVAL_SAVE)
    body, status = _post(f"{http}/api/backup/import", {"path": str(target)})
    assert status == 403 and body["ok"] is False


def test_approval_matches_normalized_path(http, tmp_path):
    """登记与请求可以写法不同 (分隔符/大小写/相对段), 归一化后视为同一条."""
    target = tmp_path / "sub" / "out.csv"
    target.parent.mkdir()
    target.write_text("x", encoding="utf-8")
    server.approve_path(str(target), server.APPROVAL_SAVE)

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
    server.approve_path(str(target), server.APPROVAL_SAVE)
    assert server.resolve_approved_path(str(target), server.APPROVAL_SAVE) is not None

    # 把登记的到期时间拨到过去, 模拟超过 TTL
    real = server._real_path(str(target))
    with server._approved_lock:
        server._APPROVED_PATHS[(server.APPROVAL_SAVE, real)] = _time.time() - 1
    assert server.resolve_approved_path(str(target), server.APPROVAL_SAVE) is None


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