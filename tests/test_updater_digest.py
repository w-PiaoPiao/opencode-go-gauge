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


def test_verify_digest_skips_when_release_has_no_digest(tmp_path):
    """旧 release 无 digest 字段: 退回 zip CRC / PE 头自检, 不因缺摘要而失败."""
    path = _write_file(tmp_path, b"anything")
    updater._verify_digest(path, "")
    updater._verify_digest(path, "md5:unsupported")
