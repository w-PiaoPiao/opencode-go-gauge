"""updater 统一 release 选择测试 (无网络).

覆盖「一个 release 内含全平台资产」与旧式按平台 tag 并存的场景:
- 列表按版本号取最大 (创建时间顺序 ≠ 版本顺序)
- 统一 tag 必须真的带本平台资产才可用 (只发 Android 的 release 不能让桌面端误报)
- 资产按平台/架构挑选 (macOS arm64 / x86_64, Windows exe)
"""
from __future__ import annotations

import pytest

from app import updater


def _asset(name: str) -> dict:
    return {
        "name": name,
        "browser_download_url": f"https://example.test/{name}",
        "digest": "sha256:" + "a" * 64,
    }


def _rel(tag: str, *asset_names: str) -> dict:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/o/r/releases/tag/{tag}",
        "body": f"notes-{tag}",
        "assets": [_asset(n) for n in asset_names],
    }


def _unified(tag: str = "v2.2.1d") -> dict:
    return _rel(
        tag,
        f"GoGauge-{tag}-windows.exe",
        f"GoGauge-{tag}-macos-arm64.zip",
        f"GoGauge-{tag}-macos-x86_64.zip",
        f"GoGauge-{tag}-android.apk",
    )


def _as_platform(monkeypatch, *, win: bool, machine: str = "arm64") -> None:
    """把 updater 切到指定运行平台 (CI 三平台都跑, 不能依赖当前 sys.platform)."""
    monkeypatch.setattr(updater, "_IS_WIN", win)
    monkeypatch.setattr(updater, "_PLATFORM_SUFFIX", "-windows" if win else "-macos")
    monkeypatch.setattr(updater, "_PLATFORM_NAME", "Windows" if win else "macOS")
    monkeypatch.setattr(updater, "_ASSET_EXT", ".exe" if win else ".zip")
    monkeypatch.setattr(updater.platform, "machine", lambda: machine)


@pytest.fixture(params=["mac-arm64", "mac-x86_64", "win"])
def platform_case(request, monkeypatch):
    """三个运行平台组合 (对应 CI 上会被验证的三条路径)."""
    if request.param == "win":
        _as_platform(monkeypatch, win=True, machine="x86_64")
    elif request.param == "mac-x86_64":
        _as_platform(monkeypatch, win=False, machine="x86_64")
    else:
        _as_platform(monkeypatch, win=False, machine="arm64")
    return request.param


def test_unified_release_picked_as_latest(platform_case, monkeypatch):
    """统一 release (v2.2.1d) 版本高于旧式平台 tag 时应被选中, 与列表顺序无关."""
    data = [
        _rel("v2.2.1c-macos", "GoGauge-v2.2.1c-macos.zip"),
        _unified("v2.2.1d"),
        _rel("v2.2.1c-windows", "GoGauge-v2.2.1c-windows.exe"),
    ]
    monkeypatch.setattr(updater, "_fetch_json", lambda url: data)
    info = updater._fetch_latest_platform_release()
    assert info["tag"] == "v2.2.1d"
    assert info["release_url"].endswith("/releases/tag/v2.2.1d")
    assert info["notes"] == "notes-v2.2.1d"


def test_higher_version_wins_even_if_listed_later(platform_case, monkeypatch):
    """旧式平台 tag 出现在前面、版本更低时, 不能直接取首条."""
    data = [
        _rel("v2.2.1c-macos", "GoGauge-v2.2.1c-macos.zip"),
        _rel("v2.2.1c-windows", "GoGauge-v2.2.1c-windows.exe"),
        _unified("v2.2.1d"),
    ]
    monkeypatch.setattr(updater, "_fetch_json", lambda url: data)
    assert updater._fetch_latest_platform_release()["tag"] == "v2.2.1d"


def test_unified_release_without_platform_asset_is_skipped(platform_case, monkeypatch):
    """统一 tag 但资产里没有本平台包 (如只发了 Android) → 不选它."""
    data = [
        _rel("v2.2.1e", "GoGauge-v2.2.1e-android.apk"),
        _rel("v2.2.1c-macos", "GoGauge-v2.2.1c-macos.zip"),
        _rel("v2.2.1c-windows", "GoGauge-v2.2.1c-windows.exe"),
    ]
    monkeypatch.setattr(updater, "_fetch_json", lambda url: data)
    tag = updater._fetch_latest_platform_release()["tag"]
    assert tag == ("v2.2.1c-windows" if platform_case == "win" else "v2.2.1c-macos")


def test_legacy_platform_tags_still_supported(platform_case, monkeypatch):
    """没有统一 release 时, 旧式 -macos / -windows tag 仍然可用."""
    data = [
        _rel("v2.2.1a-macos", "GoGauge-v2.2.1a-macos.zip"),
        _rel("v2.2.1b-macos", "GoGauge-v2.2.1b-macos.zip"),
        _rel("v2.2.1b-windows", "GoGauge-v2.2.1b-windows.exe"),
    ]
    monkeypatch.setattr(updater, "_fetch_json", lambda url: data)
    want = "v2.2.1b-windows" if platform_case == "win" else "v2.2.1b-macos"
    assert updater._fetch_latest_platform_release()["tag"] == want


def test_no_compatible_release_raises(platform_case, monkeypatch):
    monkeypatch.setattr(
        updater, "_fetch_json",
        lambda url: [_rel("v2.2.1e", "GoGauge-v2.2.1e-android.apk")],
    )
    with pytest.raises(RuntimeError, match="暂无"):
        updater._fetch_latest_platform_release()


def test_fetch_asset_info_prefers_matching_arch(monkeypatch):
    monkeypatch.setattr(updater, "_fetch_json", lambda url: _unified("v2.2.1d"))
    _as_platform(monkeypatch, win=False, machine="arm64")
    url, digest = updater.fetch_asset_info("v2.2.1d")
    assert url.endswith("-macos-arm64.zip")
    assert digest.startswith("sha256:")

    _as_platform(monkeypatch, win=False, machine="x86_64")
    url, _ = updater.fetch_asset_info("v2.2.1d")
    assert url.endswith("-macos-x86_64.zip")


def test_fetch_asset_info_windows_exe(monkeypatch):
    monkeypatch.setattr(updater, "_fetch_json", lambda url: _unified("v2.2.1d"))
    _as_platform(monkeypatch, win=True)
    url, _ = updater.fetch_asset_info("v2.2.1d")
    assert url.endswith("-windows.exe")


_ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:github.com,2008:Repository/1/v2.2.1f-android</id>
    <link rel="alternate" type="text/html" href="https://github.com/o/r/releases/tag/v2.2.1f-android"/>
    <content type="html">android only, must be ignored</content>
  </entry>
  <entry>
    <id>tag:github.com,2008:Repository/1/v2.2.1d</id>
    <link rel="alternate" type="text/html" href="https://github.com/o/r/releases/tag/v2.2.1d"/>
    <content type="html">unified</content>
  </entry>
  <entry>
    <id>tag:github.com,2008:Repository/1/v2.2.1c-macos</id>
    <link rel="alternate" type="text/html" href="https://github.com/o/r/releases/tag/v2.2.1c-macos"/>
    <content type="html">legacy</content>
  </entry>
</feed>
"""


def test_atom_fallback_accepts_unified_and_picks_max(platform_case, monkeypatch):
    """Atom 兜底: 统一 tag 可用; 其它平台后缀 tag 即使版本更高也要跳过."""
    monkeypatch.setattr(updater, "_fetch_text", lambda url: _ATOM)
    info = updater._fetch_latest_atom()
    assert info["tag"] == "v2.2.1d"
    assert info["release_url"].endswith("/releases/tag/v2.2.1d")
    assert info["notes"] == "unified"


def test_asset_name_platform_matching(monkeypatch):
    _as_platform(monkeypatch, win=False)
    assert updater._asset_name_matches_platform("GoGauge-v2.2.1a-macos.zip")
    assert updater._asset_name_matches_platform("GoGauge-v2.2.1d-macos-arm64.zip")
    assert not updater._asset_name_matches_platform("GoGauge-v2.2.1d-windows.exe")
    assert not updater._asset_name_matches_platform("GoGauge-v2.2.1d-android.apk")
    assert not updater._asset_name_matches_platform("")

    _as_platform(monkeypatch, win=True)
    assert updater._asset_name_matches_platform("GoGauge-v2.2.1d-windows.exe")
    assert not updater._asset_name_matches_platform("GoGauge-v2.2.1d-macos-arm64.zip")


def test_pick_platform_asset_tolerates_malformed_entries(monkeypatch):
    _as_platform(monkeypatch, win=False)
    assets = [
        "not-a-dict",
        {"name": "GoGauge-v2.2.1d-macos-arm64.zip", "browser_download_url": ""},
        {"name": "GoGauge-v2.2.1d-windows.exe", "browser_download_url": "https://x/w.exe"},
    ]
    assert updater._pick_platform_asset(assets) is None


def test_check_update_reports_unified_version(monkeypatch):
    _as_platform(monkeypatch, win=False, machine="arm64")
    monkeypatch.setattr(updater, "_fetch_json", lambda url: [_unified("v9.9.9")])
    monkeypatch.setattr(updater, "__version__", "2.2.1c")
    info = updater.check_update()
    assert info["has_update"] is True
    assert info["latest"] == "v9.9.9"


# ---------------------------------------------------------------------------
# P3-4 / I6: 严格版本解析、预发布过滤、check_update 带出资产信息、I8 页面 helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("2.2.2", (2, 2, 2, 0)),
        ("v2.2.2", (2, 2, 2, 0)),
        ("V2.2.2", (2, 2, 2, 0)),
        ("v2.2.1d", (2, 2, 1, 4)),
        ("v2.2.1d-macos", (2, 2, 1, 4)),          # 平台 tag 仍可解析 (语义不变)
        ("v2.2.1d-macos-arm64", (2, 2, 1, 4)),    # 平台+架构组合后缀
        ("v2.2.1d-windows", (2, 2, 1, 4)),
        ("v2.2.3-rc1", None),                     # 预发布不参与版本比较
        ("v2.2.3-beta", None),
        ("v2.2.2+build.7", None),                 # 构建元数据不是稳定发布
        ("v2.2", None),
        ("not-a-version", None),
        ("", None),
    ],
)
def test_parse_version_strict_and_platform_suffixes(tag, expected):
    assert updater._parse_version(tag) == expected


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v2.2.3-rc1", True),
        ("v2.2.3-beta.2", True),
        ("v2.2.3-alpha", True),
        ("v2.2.3-pre", True),
        ("v2.2.3-dev", True),
        ("v2.2.2+build.7", True),
        ("v2.2.3-rc1-macos", True),
        ("v2.2.1d-macos", False),
        ("v2.2.1d-macos-arm64", False),
        ("v2.2.2", False),
        ("", False),
    ],
)
def test_is_prerelease_tag(tag, expected):
    assert updater._is_prerelease_tag(tag) is expected


def test_platform_and_unified_tag_predicates(monkeypatch):
    _as_platform(monkeypatch, win=False, machine="arm64")
    assert updater._is_platform_tag("v2.2.1d-macos")
    assert not updater._is_platform_tag("v2.2.1d")
    assert not updater._is_platform_tag("v2.2.3-rc1-macos")
    assert updater._is_unified_tag("v2.2.1d")
    assert not updater._is_unified_tag("v2.2.1d-macos")
    assert not updater._is_unified_tag("v2.2.3-rc1")


def test_fetch_latest_platform_release_skips_prerelease_and_draft(monkeypatch):
    """GitHub 标记的 prerelease/draft 即使版本更高也不能推给稳定版用户."""
    _as_platform(monkeypatch, win=False, machine="arm64")
    pre = _unified("v9.9.9-rc1")
    pre["prerelease"] = True
    draft = _unified("v9.9.8")
    draft["draft"] = True
    monkeypatch.setattr(updater, "_fetch_json", lambda url: [pre, draft, _unified("v2.2.1d")])
    info = updater._fetch_latest_platform_release()
    assert info["tag"] == "v2.2.1d"
    assert info["asset_url"].endswith("-macos-arm64.zip")
    assert info["asset_digest"].startswith("sha256:")


def test_fetch_latest_atom_skips_prerelease_tags(monkeypatch):
    """Atom 没有 prerelease 布尔字段, 只能靠 tag 语义过滤 -rc/-beta/+build."""
    atom = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>tag:github.com,2008:Repository/1/v9.9.9-rc1</id>
    <content type="html">rc</content></entry>
  <entry><id>tag:github.com,2008:Repository/1/v9.9.8+build.7</id>
    <content type="html">build meta</content></entry>
  <entry><id>tag:github.com,2008:Repository/1/v2.2.1d</id>
    <content type="html">stable</content></entry>
</feed>"""
    monkeypatch.setattr(updater, "_fetch_text", lambda url: atom)
    info = updater._fetch_latest_atom()
    assert info["tag"] == "v2.2.1d"
    assert info["asset_url"] == "" and info["asset_digest"] == ""


def test_check_update_exposes_asset_url_and_digest(monkeypatch):
    """I6: 列表路径把匹配资产的 url/digest 一并返回, download 不再二次打 API."""
    _as_platform(monkeypatch, win=False, machine="arm64")
    monkeypatch.setattr(updater, "_fetch_json", lambda url: [_unified("v9.9.9")])
    monkeypatch.setattr(updater, "__version__", "2.2.1c")
    info = updater.check_update()
    assert info["has_update"] is True
    assert info["latest"] == "v9.9.9"
    assert info["asset_url"].endswith("-macos-arm64.zip")
    assert info["asset_digest"].startswith("sha256:")


def test_check_update_atom_fallback_has_empty_asset_fields(platform_case, monkeypatch):
    """Atom 路径拿不到资产列表: asset_url/asset_digest 必须为空 (交给 SHA256SUMS 兜底)."""
    monkeypatch.setattr(
        updater, "_fetch_json",
        lambda url: (_ for _ in ()).throw(OSError("HTTP 403 rate limit")))
    monkeypatch.setattr(updater, "_fetch_text", lambda url: _ATOM)
    monkeypatch.setattr(updater, "__version__", "2.2.1c")
    info = updater.check_update()
    assert info["has_update"] is True
    assert info["asset_url"] == ""
    assert info["asset_digest"] == ""


def test_release_page_helpers(monkeypatch):
    """I8: 默认打开列表页, 且 POST url 只允许本仓库 releases 前缀."""
    assert updater.RELEASES_PAGE_URL.endswith("/releases")
    assert updater.RELEASE_PAGE_URL == updater.RELEASES_PAGE_URL
    tag_url = updater.release_url_for_tag("v2.2.1d")
    assert tag_url == f"https://github.com/{updater.REPO}/releases/tag/v2.2.1d"
    assert updater.is_allowed_release_url(updater.RELEASES_PAGE_URL)
    assert updater.is_allowed_release_url(tag_url)
    assert not updater.is_allowed_release_url("https://github.com/other/repo/releases")
    assert not updater.is_allowed_release_url("http://github.com/x/releases")
    assert not updater.is_allowed_release_url(
        f"https://user:pass@github.com/{updater.REPO}/releases")
    assert not updater.is_allowed_release_url("")
