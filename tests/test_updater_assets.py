"""更新器资产选择测试 (无网络).

macOS 分发包按架构拆分发布 (``GoGauge-vX-macos-arm64.zip`` / ``-x86_64.zip``),
而更新器原先只有"精确名 gogauge-macos.zip"与"-macos.zip 后缀"两条规则, 两者
都不匹配实际资产名 → 回退到"取第一个 .zip" (上传顺序里 arm64 在前), Intel
机器因此会下载到跑不起来的包, 且 SHA-256 校验仍能通过, 故障完全静默.
"""
from __future__ import annotations

from app import updater


def _asset(name: str) -> dict[str, str]:
    return {
        "name": name,
        "browser_download_url": f"https://example.com/{name}",
        "digest": "sha256:" + "a" * 64,
    }


def _fake_macos(monkeypatch, arch: str, assets: list[dict[str, str]]) -> None:
    monkeypatch.setattr(updater, "_IS_WIN", False)
    monkeypatch.setattr(updater, "_PLATFORM_SUFFIX", "-macos")
    monkeypatch.setattr(updater, "_ASSET_EXT", ".zip")
    monkeypatch.setattr(updater, "_ASSET_NAME", "gogauge-macos.zip")
    monkeypatch.setattr(updater, "_ARCH", arch)
    monkeypatch.setattr(updater, "_fetch_json", lambda _url: {"assets": assets})


def test_macos_picks_matching_arch_over_first_zip(monkeypatch):
    """Intel 必须拿到 -x86_64 包, 而不是资产列表里的第一个 zip (arm64)."""
    _fake_macos(
        monkeypatch,
        "x86_64",
        [_asset("GoGauge-v2.2.0-macos-arm64.zip"), _asset("GoGauge-v2.2.0-macos-x86_64.zip")],
    )
    url, digest = updater.fetch_asset_info("v2.2.0-macos")
    assert url.endswith("-macos-x86_64.zip")
    assert digest.startswith("sha256:")


def test_macos_arm64_picks_arm64(monkeypatch):
    _fake_macos(
        monkeypatch,
        "arm64",
        [_asset("GoGauge-v2.2.0-macos-x86_64.zip"), _asset("GoGauge-v2.2.0-macos-arm64.zip")],
    )
    url, _digest = updater.fetch_asset_info("v2.2.0-macos")
    assert url.endswith("-macos-arm64.zip")


def test_macos_exact_name_still_wins(monkeypatch):
    """上游若改回标准资产名, 精确匹配优先于架构匹配."""
    _fake_macos(
        monkeypatch,
        "arm64",
        [_asset("GoGauge-v2.2.0-macos-arm64.zip"), _asset("gogauge-macos.zip")],
    )
    url, _digest = updater.fetch_asset_info("v2.2.0-macos")
    assert url.endswith("gogauge-macos.zip")


def test_macos_falls_back_without_arch_match(monkeypatch):
    """没有本机架构的包时仍回退到任一 zip (不能因为架构缺失就拒绝更新)."""
    _fake_macos(monkeypatch, "x86_64", [_asset("GoGauge-v2.2.0-macos-arm64.zip")])
    url, _digest = updater.fetch_asset_info("v2.2.0-macos")
    assert url.endswith("-macos-arm64.zip")


def test_windows_asset_name_unchanged(monkeypatch):
    monkeypatch.setattr(updater, "_IS_WIN", True)
    monkeypatch.setattr(updater, "_PLATFORM_SUFFIX", "-windows")
    monkeypatch.setattr(updater, "_ASSET_EXT", ".exe")
    monkeypatch.setattr(updater, "_ASSET_NAME", "gogauge-windows.exe")
    monkeypatch.setattr(updater, "_ARCH", "x86_64")
    monkeypatch.setattr(
        updater, "_fetch_json", lambda _url: {"assets": [_asset("GoGauge-v2.2.0-windows.exe")]}
    )
    url, _digest = updater.fetch_asset_info("v2.2.0-windows")
    assert url.endswith("-windows.exe")
