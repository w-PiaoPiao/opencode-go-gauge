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
