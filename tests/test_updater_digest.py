"""updater 下载摘要校验测试 (SHA-256 比对逻辑, 无网络)."""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from app import updater


def _write_file(tmp_path, data: bytes):
    path = tmp_path / "pkg.zip"
    path.write_bytes(data)
    return str(path)


def _stub_payload(ext: str) -> bytes:
    """按资产类型造一份能过结构自检的载荷 (exe 走 PE 头, zip 走 CRC).

    下载收尾的结构自检是平台分支的 (updater._ASSET_EXT: win32 = .exe, 其余 .zip),
    载荷写死一种就只在那一半平台上成立.
    """
    if ext == ".zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("GoGauge.txt", "stub")
        return buf.getvalue()
    return b"MZ" + b"\x00" * 32


def test_verify_digest_accepts_matching_sha256(tmp_path):
    data = b"package-bytes"
    path = _write_file(tmp_path, data)
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    # 真断言 (此前零 assert, 校验逻辑退化成 no-op 也照样绿)
    assert updater._verify_digest(path, digest) is None


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
    assert updater._verify_digest(path, "") is None
    assert updater._verify_digest(path, "md5:unsupported") is None


def test_verify_digest_rejects_malformed_hex(tmp_path, monkeypatch):
    """摘要长度/字符非法时拒绝 (防止 "sha256:" 后接空串或截断值直接比对成功)."""
    monkeypatch.delenv("GOGauge_ALLOW_UNVERIFIED_UPDATE", raising=False)
    path = _write_file(tmp_path, b"anything")
    for bad in ("sha256:", "sha256:abc", "sha256:" + "z" * 64):
        with pytest.raises(RuntimeError, match="摘要格式非法"):
            updater._verify_digest(path, bad)


@pytest.mark.parametrize("ext", [".exe", ".zip"])
def test_download_filename_tag_is_sanitized(tmp_path, monkeypatch, ext):
    """远端 tag 含路径分隔符/上跳时, 下载路径不得逃出 dest_dir.

    过去这个用例只断言 state == "error": 摘要缺失本就会 fail-closed, 与文件名
    无关; 即使把消毒整段删掉, 中间目录不存在导致 open() 抛 FileNotFoundError,
    断言照样成立. 这里给一份**合法**摘要让写入真正走完, 再断言落点.

    两种资产类型都要跑: 载荷写死 PE 头只在 Windows 成立, Linux/macOS 上
    _ASSET_EXT 是 .zip, 会在结构自检处撞 "File is not a zip file" (CI 上就是这么红的).
    """
    monkeypatch.setattr(updater, "_ASSET_EXT", ext)
    payload = _stub_payload(ext)
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()

    monkeypatch.setattr(
        updater, "check_update",
        lambda use_cache=False: {
            "has_update": True,
            "latest": "v1.0.2/../../evil",
            "asset_url": "https://x/y.zip",
            "asset_digest": digest,
        },
    )

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
    assert written.name == (
        f"GoGauge-v1.0.2_.._.._evil{updater._PLATFORM_SUFFIX}"
        f"{updater._asset_arch_suffix()}{ext}")
    assert "/" not in written.name and "\\" not in written.name
    # 没有逃逸到 dest_dir 之外 (消毒失效时落点会是 ../evil<suffix><ext>)
    assert not (tmp_path.parent / f"evil{updater._PLATFORM_SUFFIX}{ext}").exists()
    # .part 中间态不应残留
    assert not list(tmp_path.glob("*.part"))


def test_failed_download_leaves_no_partial_file(tmp_path, monkeypatch):
    """下载/校验失败不留 .part 残骸 (下载目录会堆一串用户没要过的文件)."""
    monkeypatch.setattr(
        updater, "check_update",
        lambda use_cache=False: {
            "has_update": True,
            "latest": "v9.9.9",
            "asset_url": "https://x/y.zip",
            "asset_digest": "sha256:" + "0" * 64,
        },
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


def test_download_filename_legacy_platform_tag_not_doubled(monkeypatch):
    """P3-24: 旧式平台 tag 不能拼成 -macos-macos.zip; macOS 还要带架构后缀."""
    monkeypatch.setattr(updater, "_IS_WIN", False)
    monkeypatch.setattr(updater, "_PLATFORM_SUFFIX", "-macos")
    monkeypatch.setattr(updater, "_ASSET_EXT", ".zip")
    monkeypatch.setattr(updater.platform, "machine", lambda: "arm64")
    assert updater._download_filename("v2.2.1d-macos") == "GoGauge-v2.2.1d-macos-arm64.zip"
    # 统一 tag 的命名与旧式 tag 剥后缀后一致
    assert updater._download_filename("v2.2.1d") == "GoGauge-v2.2.1d-macos-arm64.zip"
    # Intel 机器下载的包名同样能分辨
    monkeypatch.setattr(updater.platform, "machine", lambda: "x86_64")
    assert updater._download_filename("v2.2.1d-macos") == (
        "GoGauge-v2.2.1d-macos-x86_64.zip")


def test_download_filename_windows_legacy_platform_tag_not_doubled(monkeypatch):
    """Windows 旧式 -windows tag 同样不得双后缀 (且不追加架构)."""
    monkeypatch.setattr(updater, "_IS_WIN", True)
    monkeypatch.setattr(updater, "_PLATFORM_SUFFIX", "-windows")
    monkeypatch.setattr(updater, "_ASSET_EXT", ".exe")
    assert updater._download_filename("v2.2.1b-windows") == "GoGauge-v2.2.1b-windows.exe"
    assert updater._download_filename("v2.2.2") == "GoGauge-v2.2.2-windows.exe"


def test_sanitized_name_contains_no_separators():
    """直接验证消毒逻辑: 过滤后只保留白名单字符 (调用生产代码, 非抄一遍正则)."""
    for raw in ("v1.0.2/../../evil-macos", "v1.0.2", "v2.1.0c-macos", "..", "a/b\\c"):
        safe = updater._safe_tag(raw)
        assert "/" not in safe and "\\" not in safe
        assert not safe.startswith("..")
    assert updater._safe_tag("..") == "update"
    assert updater._safe_tag("v2.1.0c-macos") == "v2.1.0c-macos"


# ---------------------------------------------------------------------------
# I6/I7: 下载资产来源 = check_update 结果 / SHA256SUMS.txt (不再无条件打 tags API)
# ---------------------------------------------------------------------------


def _mock_urlopen(payload: bytes, seen: list[str]):
    """返回一个 urlopen 替身: 每次请求记录 URL, 首次 read 给出完整 payload, 之后 EOF."""

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
            return payload

    def _open(req, **_kwargs):
        seen.append(req.full_url)
        return _Resp()

    return _open


def _macos_arm_platform(monkeypatch) -> None:
    monkeypatch.setattr(updater, "_IS_WIN", False)
    monkeypatch.setattr(updater, "_PLATFORM_SUFFIX", "-macos")
    monkeypatch.setattr(updater, "_ASSET_EXT", ".zip")
    monkeypatch.setattr(updater.platform, "machine", lambda: "arm64")


def test_parse_sha256sums_ignores_malformed_lines():
    """摘要清单解析: 兼容 sha256sum 的 '*资产名' 形式, 非法行忽略."""
    good_arm = "a" * 64
    good_win = "B" * 64
    text = (
        f"{good_arm}  GoGauge-v9.9.9-macos-arm64.zip\n"
        f"{good_win} *GoGauge-v9.9.9-windows.exe\n"
        "not-a-line\n"
        "sha256:xyz  bad\n"
    )
    sums = updater._parse_sha256sums(text)
    assert sums["GoGauge-v9.9.9-macos-arm64.zip"] == "sha256:" + good_arm
    assert sums["GoGauge-v9.9.9-windows.exe"] == "sha256:" + good_win.lower()
    assert len(sums) == 2


def test_download_reuses_asset_from_check_without_api(tmp_path, monkeypatch):
    """列表路径已带 asset_url/digest 时, 下载不得再打 tags API / SHA256SUMS.

    这正是 P1-4: API 被限流时 Atom 只能发现版本; 列表路径成功时必须复用资产
    信息, 否则下载会二次撞同一个 API。
    """
    _macos_arm_platform(monkeypatch)
    payload = _stub_payload(".zip")
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        updater, "check_update",
        lambda use_cache=False: {
            "has_update": True, "latest": "v9.9.9",
            "asset_url": "https://example.test/GoGauge-v9.9.9-macos-arm64.zip",
            "asset_digest": digest,
        },
    )

    def _must_not_call(*_a, **_k):
        raise AssertionError("已带资产信息时不应再请求 API/SHA256SUMS")

    monkeypatch.setattr(updater, "fetch_asset_info", _must_not_call)
    monkeypatch.setattr(updater, "_fetch_text", _must_not_call)
    seen: list = []
    monkeypatch.setattr(updater.urllib.request, "urlopen", _mock_urlopen(payload, seen))

    res = updater.download_update(str(tmp_path))

    assert res["state"] == "done", res
    assert seen and seen[0] == "https://example.test/GoGauge-v9.9.9-macos-arm64.zip"


def test_download_atom_path_uses_sha256sums(tmp_path, monkeypatch):
    """Atom 兜底 (asset_url 为空) 时, 从 release 的 SHA256SUMS.txt 挑资产+摘要."""
    _macos_arm_platform(monkeypatch)
    payload = _stub_payload(".zip")
    digest = hashlib.sha256(payload).hexdigest()
    asset = "GoGauge-v9.9.9-macos-arm64.zip"
    monkeypatch.setattr(
        updater, "check_update",
        lambda use_cache=False: {
            "has_update": True, "latest": "v9.9.9",
            "asset_url": "", "asset_digest": "",
        },
    )

    fetched: list[str] = []

    def _fetch_text(url: str) -> str:
        fetched.append(url)
        assert url.endswith("/SHA256SUMS.txt"), url
        return f"{digest}  {asset}\n"

    monkeypatch.setattr(updater, "_fetch_text", _fetch_text)
    seen: list = []
    monkeypatch.setattr(updater.urllib.request, "urlopen", _mock_urlopen(payload, seen))

    res = updater.download_update(str(tmp_path))

    assert res["state"] == "done", res
    assert fetched and fetched[0].endswith("/releases/download/v9.9.9/SHA256SUMS.txt")
    assert seen and seen[0].endswith("/" + asset)


def test_download_missing_digest_fails_closed_end_to_end(tmp_path, monkeypatch):
    """下载路径同样 fail-closed: 无摘要时不安装, 且不留下 .part 残骸."""
    monkeypatch.delenv("GOGauge_ALLOW_UNVERIFIED_UPDATE", raising=False)
    _macos_arm_platform(monkeypatch)
    payload = _stub_payload(".zip")
    monkeypatch.setattr(
        updater, "check_update",
        lambda use_cache=False: {
            "has_update": True, "latest": "v9.9.9",
            "asset_url": "https://example.test/GoGauge-v9.9.9-macos-arm64.zip",
            "asset_digest": "",
        },
    )
    # 旧式 release 无 SHA256SUMS.txt
    monkeypatch.setattr(
        updater, "_fetch_text",
        lambda url: (_ for _ in ()).throw(OSError("404 Not Found")))
    seen: list = []
    monkeypatch.setattr(updater.urllib.request, "urlopen", _mock_urlopen(payload, seen))

    res = updater.download_update(str(tmp_path))

    assert res["state"] == "error"
    assert "SHA-256" in res["error"]
    assert list(tmp_path.glob("*")) == []


def test_download_missing_digest_allowed_with_explicit_opt_out(tmp_path, monkeypatch):
    """显式 GOGauge_ALLOW_UNVERIFIED_UPDATE=1 时, 无摘要仍可完成 (自建 release 逃生口)."""
    monkeypatch.setenv("GOGauge_ALLOW_UNVERIFIED_UPDATE", "1")
    _macos_arm_platform(monkeypatch)
    payload = _stub_payload(".zip")
    monkeypatch.setattr(
        updater, "check_update",
        lambda use_cache=False: {
            "has_update": True, "latest": "v9.9.9",
            "asset_url": "https://example.test/GoGauge-v9.9.9-macos-arm64.zip",
            "asset_digest": "",
        },
    )
    monkeypatch.setattr(
        updater, "_fetch_text",
        lambda url: (_ for _ in ()).throw(OSError("404 Not Found")))
    seen: list = []
    monkeypatch.setattr(updater.urllib.request, "urlopen", _mock_urlopen(payload, seen))

    res = updater.download_update(str(tmp_path))

    assert res["state"] == "done", res


def test_download_update_accepts_prechecked_info(tmp_path, monkeypatch):
    """download_update(info=...) 可直接复用 server 侧检查结果, 不再自己联网检查."""
    _macos_arm_platform(monkeypatch)
    payload = _stub_payload(".zip")
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()

    def _must_not_check(*_a, **_k):
        raise AssertionError("传入 info 时不应再调用 check_update")

    monkeypatch.setattr(updater, "check_update", _must_not_check)
    seen: list = []
    monkeypatch.setattr(updater.urllib.request, "urlopen", _mock_urlopen(payload, seen))
    res = updater.download_update(
        str(tmp_path),
        info={
            "has_update": True, "latest": "v9.9.9",
            "asset_url": "https://example.test/pkg.zip",
            "asset_digest": digest,
        },
    )
    assert res["state"] == "done", res
