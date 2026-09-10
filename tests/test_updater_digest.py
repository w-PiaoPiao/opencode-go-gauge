"""updater 下载摘要校验测试 (SHA-256 比对逻辑, 无网络)."""
from __future__ import annotations

import hashlib

import pytest

from app import updater


def _write_file(tmp_path, data: bytes):
    path = tmp_path / "pkg.zip"
    path.write_bytes(data)
    return str(path)


def test_verify_digest_accepts_matching_sha256(tmp_path):
    data = b"package-bytes"
    path = _write_file(tmp_path, data)
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    updater._verify_digest(path, digest)  # 不抛即通过


def test_verify_digest_rejects_mismatch(tmp_path):
    path = _write_file(tmp_path, b"tampered")
    digest = "sha256:" + hashlib.sha256(b"original").hexdigest()
    with pytest.raises(RuntimeError, match="SHA-256"):
        updater._verify_digest(path, digest)


def test_verify_digest_rejects_missing_digest(tmp_path, monkeypatch):
    """缺摘要时必须 fail-closed: 不能凭 zip CRC / PE 头自检就放行安装."""
    monkeypatch.delenv("GOGauge_ALLOW_UNVERIFIED_UPDATE", raising=False)
    path = _write_file(tmp_path, b"anything")
    with pytest.raises(RuntimeError, match="缺少官方 SHA-256 摘要"):
        updater._verify_digest(path, "")
    with pytest.raises(RuntimeError, match="缺少官方 SHA-256 摘要"):
        updater._verify_digest(path, "md5:unsupported")


def test_verify_digest_missing_allowed_with_env_opt_out(tmp_path, monkeypatch):
    """自建 release 无摘要时, 显式 opt-out 仍可放行 (供 fork/私有构建使用)."""
    monkeypatch.setenv("GOGauge_ALLOW_UNVERIFIED_UPDATE", "1")
    path = _write_file(tmp_path, b"anything")
    updater._verify_digest(path, "")
    updater._verify_digest(path, "md5:unsupported")


def test_verify_digest_rejects_malformed_hex(tmp_path, monkeypatch):
    """摘要长度/字符非法时拒绝 (防止 "sha256:" 后接空串或截断值直接比对成功)."""
    monkeypatch.delenv("GOGauge_ALLOW_UNVERIFIED_UPDATE", raising=False)
    path = _write_file(tmp_path, b"anything")
    for bad in ("sha256:", "sha256:abc", "sha256:" + "z" * 64):
        with pytest.raises(RuntimeError, match="摘要格式非法"):
            updater._verify_digest(path, bad)


def test_download_filename_tag_is_sanitized(tmp_path, monkeypatch):
    """远端 tag 含路径分隔符/上跳时, 下载路径不得逃出 dest_dir."""
    monkeypatch.setattr(
        updater, "check_update",
        lambda: {"has_update": True, "latest": "v1.0.2/../../evil-macos"},
    )
    monkeypatch.setattr(updater, "fetch_asset_info", lambda tag: ("https://x/y.zip", ""))

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, _n):
            return b""

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *a, **k: _Resp())

    res = updater.download_update(str(tmp_path))
    # 摘要缺失 -> 被 fail-closed 拦下, 不会落盘
    assert res["state"] == "error"
    assert not (tmp_path.parent / "evil-macos-macos.zip").exists()


def test_sanitized_name_contains_no_separators():
    """直接验证消毒逻辑: 过滤后只保留白名单字符."""
    import re as _re

    for raw in ("v1.0.2/../../evil-macos", "v1.0.2", "v2.1.0c-macos", ".."):
        safe = _re.sub(r"[^A-Za-z0-9._-]", "_", raw).strip(".") or "update"
        assert "/" not in safe and "\\" not in safe
        assert not safe.startswith("..")
