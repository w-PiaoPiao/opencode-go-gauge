"""updater 下载摘要校验测试 (SHA-256 比对逻辑, 无网络)."""
from __future__ import annotations

import hashlib
from pathlib import Path

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
    """远端 tag 含路径分隔符/上跳时, 下载路径不得逃出 dest_dir.

    过去这个用例只断言 state == "error": 摘要缺失本就会 fail-closed, 与文件名
    无关; 即使把消毒整段删掉, 中间目录不存在导致 open() 抛 FileNotFoundError,
    断言照样成立. 这里给一份**合法**摘要让写入真正走完, 再断言落点.
    """
    payload = b"MZ" + b"\x00" * 32  # 模拟 exe, 走 PE 头自检分支
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()

    monkeypatch.setattr(
        updater, "check_update",
        lambda: {"has_update": True, "latest": "v1.0.2/../../evil"},
    )
    monkeypatch.setattr(updater, "fetch_asset_info", lambda tag: ("https://x/y.zip", digest))

    class _Resp:
        # 读一次给内容, 之后返回 EOF —— 必须如此: 下载循环靠 read() 返回空串收尾,
        # 每次都给内容会无限循环
        def __init__(self):
            self._sent = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, _n):
            if self._sent:
                return b""
            self._sent = True
            return payload

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *a, **k: _Resp())

    res = updater.download_update(str(tmp_path))

    assert res["state"] == "done", res
    # 落点必须在 dest_dir 内, 且不得出现任何分隔符残留
    written = tmp_path / Path(res["path"]).name
    assert Path(res["path"]).parent == tmp_path
    assert written.exists()
    assert "/" not in written.name and "\\" not in written.name
    # 没有逃逸到 dest_dir 之外
    assert not (tmp_path.parent / "evil-macos-macos.exe").exists()
    # .part 中间态不应残留
    assert not list(tmp_path.glob("*.part"))


def test_failed_download_leaves_no_partial_file(tmp_path, monkeypatch):
    """下载/校验失败不留 .part 残骸 (下载目录会堆一串用户没要过的文件)."""
    monkeypatch.setattr(
        updater, "check_update",
        lambda: {"has_update": True, "latest": "v9.9.9"},
    )
    # 摘要合法但内容不是 PE —— 会在结构自检处失败
    monkeypatch.setattr(
        updater, "fetch_asset_info",
        lambda tag: ("https://x/y.zip", "sha256:" + "0" * 64),
    )

    class _Resp:
        def __init__(self):
            self._sent = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, _n):
            if self._sent:
                return b""
            self._sent = True
            return b"not-an-exe"

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *a, **k: _Resp())

    res = updater.download_update(str(tmp_path))

    assert res["state"] == "error"
    assert list(tmp_path.glob("*")) == [], f"残留文件: {list(tmp_path.glob('*'))}"


def test_sanitized_name_contains_no_separators():
    """直接验证消毒逻辑: 过滤后只保留白名单字符 (调用生产代码, 非抄一遍正则)."""
    for raw in ("v1.0.2/../../evil-macos", "v1.0.2", "v2.1.0c-macos", "..", "a/b\\c"):
        safe = updater._safe_tag(raw)
        assert "/" not in safe and "\\" not in safe
        assert not safe.startswith("..")
    assert updater._safe_tag("..") == "update"
    assert updater._safe_tag("v2.1.0c-macos") == "v2.1.0c-macos"
