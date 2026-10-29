"""scripts/check_versions.py（release preflight 版本一致性校验）测试.

只读: 全部断言都用 subprocess 调脚本 + 临时目录夹具, **不修改仓库版本号**。
覆盖:
- 当前仓库的真实版本状态（desktop=2.2.2b / Android=2.2.2b 已对齐:
  Android 侧适配桌面最新改动后与桌面同版本, 统一 release 会构建 APK；
  "Android ≤ 桌面"的滞后状态同样合法, 那时统一 release 只是跳过 Android 构建）；
- tag 与平台版本的相等/不等语义（desktop / android / all 三种 --platform）；
- 格式校验（版本号、tag、字母后缀排序）；
- 文件缺失时的可读错误。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_versions.py"
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+[a-z]?$")


def _run(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _read_repo_versions() -> tuple[str, str, str]:
    desktop = re.search(
        r'^__version__\s*=\s*"([^"]+)"',
        (REPO_ROOT / "app" / "__init__.py").read_text(encoding="utf-8"),
        re.MULTILINE,
    ).group(1)
    android = re.search(
        r'versionName\s*=\s*"([^"]+)"',
        (REPO_ROOT / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8"),
    ).group(1)
    harmony = re.search(
        r'"versionName"\s*:\s*"([^"]+)"',
        (REPO_ROOT / "harmonyos" / "AppScope" / "app.json5").read_text(encoding="utf-8"),
    ).group(1)
    return desktop, android, harmony


def _make_root(root: Path, desktop: str, android: str, harmony: str = "1.0.0") -> Path:
    """造一个最小仓库树（只含脚本会读的三个版本文件）."""
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "android" / "app").mkdir(parents=True, exist_ok=True)
    (root / "harmonyos" / "AppScope").mkdir(parents=True, exist_ok=True)
    (root / "app" / "__init__.py").write_text(
        f'"""{desktop} fixture."""\n\n__version__ = "{desktop}"\n', encoding="utf-8"
    )
    (root / "android" / "app" / "build.gradle.kts").write_text(
        "android {\n"
        "    defaultConfig {\n"
        "        versionCode = 13\n"
        f'        versionName = "{android}"\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (root / "harmonyos" / "AppScope" / "app.json5").write_text(
        '{\n  "app": {\n'
        '    "versionCode": 1000000,\n'
        f'    "versionName": "{harmony}"\n'
        "  }\n}\n",
        encoding="utf-8",
    )
    return root


# ---------------------------------------------------------------------------
# 当前仓库真实状态
# ---------------------------------------------------------------------------


def test_current_repo_versions_have_valid_format():
    r"""三个平台的版本号都必须符合 `\d+.\d+.\d+[a-z]?` 格式."""
    desktop, android, harmony = _read_repo_versions()
    for platform, version in (("desktop", desktop), ("android", android), ("harmony", harmony)):
        assert _VERSION_RE.match(version), f"{platform} 版本格式非法: {version!r}"


def test_current_repo_passes_without_tag():
    proc = _run()
    assert proc.returncode == 0, proc.stderr
    assert "desktop=" in proc.stdout and "android=" in proc.stdout
    assert "OK" in proc.stdout


def test_current_repo_desktop_tag_matches_desktop_version():
    desktop, _android, _harmony = _read_repo_versions()
    proc = _run("--tag", f"v{desktop}", "--platform", "desktop")
    assert proc.returncode == 0, proc.stderr


def test_current_repo_desktop_tag_with_platform_suffix_is_stripped():
    """单平台 hotfix tag（v2.2.2-windows）去后缀后按桌面版本比较."""
    desktop, _android, _harmony = _read_repo_versions()
    proc = _run("--tag", f"v{desktop}-windows", "--platform", "desktop")
    assert proc.returncode == 0, proc.stderr


def test_current_repo_android_tag_matches_android_version():
    """release-android 口径: tag 必须等于 Android 版本."""
    _desktop, android, _harmony = _read_repo_versions()
    proc = _run("--tag", f"v{android}-android", "--platform", "android")
    assert proc.returncode == 0, proc.stderr


def test_current_repo_all_platform_emits_android_ready(tmp_path):
    """统一发布 preflight: tag=桌面版本时通过, android_ready 反映 Android 是否同版本."""
    desktop, android, _harmony = _read_repo_versions()
    out = tmp_path / "gh_output.txt"
    proc = _run(
        "--tag", f"v{desktop}", "--platform", "all", "--github-output", str(out)
    )
    assert proc.returncode == 0, proc.stderr
    expected = "true" if desktop == android else "false"
    assert f"android_ready={expected}" in out.read_text(encoding="utf-8")
    assert f"desktop_version={desktop}" in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 失败路径（tag / 格式 / 跨端不变量）
# ---------------------------------------------------------------------------


def test_tag_mismatch_with_desktop_version_fails():
    proc = _run("--tag", "v9.9.9", "--platform", "desktop")
    assert proc.returncode == 1
    assert "不一致" in proc.stderr


def test_tag_mismatch_with_android_version_fails(tmp_path):
    _make_root(tmp_path, desktop="2.2.2", android="2.2.1d")
    proc = _run(
        "--root", str(tmp_path), "--tag", "v2.2.2", "--platform", "android"
    )
    assert proc.returncode == 1
    assert "Android versionName" in proc.stderr


def test_invalid_tag_format_rejected():
    for bad in ("v2.2", "release-2.2.2", "v2.2.2-rc1", ""):
        proc = _run("--tag", bad, "--platform", "desktop")
        assert proc.returncode == 1, f"tag={bad!r} 应被拒绝"


def test_android_newer_than_desktop_rejected(tmp_path):
    """Android 不得高于桌面（当前 2.2.1d ≤ 2.2.2 是合法的, 反向不合法）."""
    _make_root(tmp_path, desktop="2.2.2", android="2.3.0")
    proc = _run("--root", str(tmp_path))
    assert proc.returncode == 1
    assert "高于桌面" in proc.stderr


def test_letter_suffix_ordering(tmp_path):
    """字母后缀参与比较: 2.2.1e > 2.2.1d（与 app/updater.py 排序口径一致）."""
    newer_root = _make_root(tmp_path / "newer", "2.2.1d", "2.2.1e")
    proc = _run("--root", str(newer_root))
    assert proc.returncode == 1, "2.2.1e 高于 2.2.1d 应报错"
    assert "高于桌面" in proc.stderr

    ok_root = _make_root(tmp_path / "ok", "2.2.1e", "2.2.1d")
    ok = _run("--root", str(ok_root))
    assert ok.returncode == 0, ok.stderr


def test_android_equal_desktop_sets_android_ready_true(tmp_path):
    _make_root(tmp_path, desktop="2.2.2", android="2.2.2")
    out = tmp_path / "gh_output.txt"
    proc = _run(
        "--root", str(tmp_path), "--tag", "v2.2.2", "--platform", "all",
        "--github-output", str(out),
    )
    assert proc.returncode == 0, proc.stderr
    assert "android_ready=true" in out.read_text(encoding="utf-8")


def test_bad_version_format_in_repo_rejected(tmp_path):
    _make_root(tmp_path, desktop="2.2", android="2.2.2")
    proc = _run("--root", str(tmp_path))
    assert proc.returncode == 1
    assert "格式非法" in proc.stderr


def test_missing_version_file_reports_clear_error(tmp_path):
    (tmp_path / "android" / "app").mkdir(parents=True)
    (tmp_path / "harmonyos" / "AppScope").mkdir(parents=True)
    proc = _run("--root", str(tmp_path))
    assert proc.returncode == 1
    assert "读取版本文件失败" in proc.stderr
