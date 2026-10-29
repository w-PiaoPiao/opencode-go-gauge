#!/usr/bin/env python3
"""版本一致性校验（CI release preflight 用，只读、不改任何版本号）.

背景: 版本号散落在三个平台（桌面 `app/__init__.py`、Android
`android/app/build.gradle.kts`、HarmonyOS `harmonyos/AppScope/app.json5`），
此前唯一的一致性校验放在统一发布 workflow 的 `publish` job —— 即三个平台
各跑完约 45 分钟构建之后才发现 tag 与代码版本不匹配；单平台 hotfix workflow
则完全没有校验，可能发出 `__version__` 仍是旧值的包（已安装客户端会陷入
"永远有新版本"的循环提示）。本脚本把校验前移到 preflight，并允许 Android
暂时落后于桌面（当前仓库 desktop=2.2.2 / android=2.2.1d 是合法状态：
Android 未适配时统一 release 只跳过 Android 构建，不算失败）。

用法（在仓库根或任意目录均可，默认以脚本所在仓库为根）::

    python scripts/check_versions.py
    python scripts/check_versions.py --tag v2.2.2 --platform all
    python scripts/check_versions.py --tag v2.2.1d-android --platform android

退出码: 0 = 通过；1 = 校验失败（格式/不一致/文件缺失）。失败时向 stderr 打印
GitHub Actions 注解 `::error::...`，preflight 可直接据此中止构建。

GitHub 输出: `--github-output "$GITHUB_OUTPUT"` 会追加
`android_ready=<true|false>` 与各平台版本，供 release.yml 的
`build-android` 条件执行使用。

校验规则:
1. 三个平台的版本号格式均为 `\\d+\\.\\d+\\.\\d+[a-z]?`（字母后缀 = 预发布序号，
   与 app/updater.py 的排序口径一致: 无后缀=0, a=1, b=2 ...）；
2. Android 版本 **不得高于** 桌面版本（Android 依赖桌面已发布的行为）；
   HarmonyOS 目前独立版本（1.0.0）只校验格式，不参与跨端比较；
3. 给定 `--tag` 时:
   - `--platform desktop`: tag 去掉 `-macos/-windows/-android/-harmony` 后缀后
     必须等于桌面版本（release-windows / release-macos 用）；
   - `--platform android`: 必须等于 Android 版本（release-android 用）；
   - `--platform all`: tag 必须等于桌面版本；Android 等于 tag 时
     `android_ready=true`，否则 `android_ready=false`（统一发布跳过 Android）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+[a-z]?$")
# tag 允许: v2.2.2 / 2.2.2 / v2.2.1d / v2.2.1d-macos / v2.2.1d-windows /
#          v2.2.1d-android / v2.2.1d-harmony
_TAG_RE = re.compile(
    r"^v?(?P<version>\d+\.\d+\.\d+[a-z]?)(?:-(?P<platform>macos|windows|android|harmony))?$"
)


class VersionError(Exception):
    """校验失败（消息直接进 ::error:: 注解与 stderr）."""


def parse_version(text: str) -> Optional[tuple[int, int, int, int]]:
    """版本字符串 -> 可比较四元组；非法返回 None.

    字母后缀按 a=1, b=2 ... 计入第四位（与 app/updater.py 的 `_parse_version`
    同一口径，保证 "2.2.1d > 2.2.1"）。
    """
    text = (text or "").strip()
    if not _VERSION_RE.match(text):
        return None
    base = text.rstrip("abcdefghijklmnopqrstuvwxyz")
    suffix = text[len(base):]
    major_s, minor_s, patch_s = base.split(".")
    letter_rank = (ord(suffix) - ord("a") + 1) if suffix else 0
    return int(major_s), int(minor_s), int(patch_s), letter_rank


def parse_tag(tag: str) -> tuple[str, Optional[str]]:
    """tag -> (版本号, 平台后缀或 None)；非法 tag 抛 VersionError."""
    m = _TAG_RE.match((tag or "").strip())
    if not m:
        raise VersionError(
            f"tag 格式非法: {tag!r}（应形如 v2.2.2 / v2.2.1d / v2.2.1d-macos）"
        )
    return m.group("version"), m.group("platform")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VersionError(f"读取版本文件失败: {path} ({exc})") from exc


def _first_match(pattern: str, text: str, what: str, path: Path) -> str:
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        raise VersionError(f"无法从 {path} 解析出 {what}")
    return m.group(1)


def read_desktop_version(root: Path) -> str:
    path = root / "app" / "__init__.py"
    text = _read_text(path)
    version = _first_match(r'^__version__\s*=\s*"([^"]+)"', text, "桌面 __version__", path)
    return version


def read_android_versions(root: Path) -> tuple[str, int]:
    """返回 (versionName, versionCode)."""
    path = root / "android" / "app" / "build.gradle.kts"
    text = _read_text(path)
    version_name = _first_match(r'versionName\s*=\s*"([^"]+)"', text, "Android versionName", path)
    code_text = _first_match(r"versionCode\s*=\s*(\d+)", text, "Android versionCode", path)
    return version_name, int(code_text)


def read_harmony_version(root: Path) -> str:
    path = root / "harmonyos" / "AppScope" / "app.json5"
    text = _read_text(path)
    return _first_match(r'"versionName"\s*:\s*"([^"]+)"', text, "HarmonyOS versionName", path)


def _require_valid(platform: str, version: str) -> tuple[int, int, int, int]:
    parsed = parse_version(version)
    if parsed is None:
        raise VersionError(
            f"{platform} 版本号格式非法: {version!r}（要求 \\d+\\d+\\d+[a-z]?，如 2.2.2 / 2.2.1d）"
        )
    return parsed


def check_versions(root: Path, tag: Optional[str], platform: str) -> dict[str, str]:
    """执行全部校验，返回将要写入 GitHub Output 的键值；失败抛 VersionError."""
    desktop = read_desktop_version(root)
    android, android_code = read_android_versions(root)
    harmony = read_harmony_version(root)

    desktop_parsed = _require_valid("desktop", desktop)
    android_parsed = _require_valid("android", android)
    _require_valid("harmony", harmony)
    if android_code <= 0:
        raise VersionError(f"Android versionCode 非法: {android_code}")

    # Android 不得高于桌面：桌面发布代表已具备该版本能力，Android 侧适配可以滞后
    if android_parsed > desktop_parsed:
        raise VersionError(
            f"Android 版本 {android} 高于桌面版本 {desktop}；"
            "请先升桌面版本或降回 Android 版本（Android 适配依赖桌面已发布行为）"
        )

    result: dict[str, str] = {
        "desktop_version": desktop,
        "android_version": android,
        "android_version_code": str(android_code),
        "harmony_version": harmony,
        "android_ready": "false",
    }

    if tag:
        tag_version, _tag_platform = parse_tag(tag)
        _require_valid("tag", tag_version)
        result["tag_version"] = tag_version

        if platform == "desktop":
            if tag_version != desktop:
                raise VersionError(
                    f"tag {tag} 指向版本 {tag_version}，但桌面 __version__={desktop} 不一致；"
                    "请先升版本号再打 tag"
                )
        elif platform == "android":
            if tag_version != android:
                raise VersionError(
                    f"tag {tag} 指向版本 {tag_version}，但 Android versionName={android} 不一致；"
                    "请先升 Android 版本号再打 tag"
                )
        elif platform == "all":
            if tag_version != desktop:
                raise VersionError(
                    f"tag {tag} 指向版本 {tag_version}，但桌面 __version__={desktop} 不一致；"
                    "请先升版本号再打 tag"
                )
            result["android_ready"] = "true" if tag_version == android else "false"
        else:  # pragma: no cover - argparse choices 已限制
            raise VersionError(f"未知 platform: {platform!r}")
    else:
        # 无 tag 只做仓库内不变量；android_ready 以"是否与桌面同版本"给出参考值
        result["android_ready"] = "true" if android_parsed == desktop_parsed else "false"

    return result


def _emit(lines: list[str], stream) -> None:  # type: ignore[no-untyped-def]
    for line in lines:
        print(line, file=stream)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="GoGauge 三平台版本一致性校验（preflight 用，只读）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/check_versions.py\n"
            "  python scripts/check_versions.py --tag v2.2.2 --platform all\n"
            "  python scripts/check_versions.py --tag v2.2.1d-android --platform android\n"
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        help="仓库根目录（默认取脚本所在仓库；测试用临时目录时指定）",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="要发布的 git tag（如 v2.2.2 / v2.2.1d-macos）；不传则只做仓库内不变量校验",
    )
    parser.add_argument(
        "--platform",
        choices=("desktop", "android", "all"),
        default="all",
        help="校验口径: desktop=tag 必须等于桌面版本; android=tag 必须等于 Android; "
        "all=tag 等于桌面, Android 可用则输出 android_ready",
    )
    parser.add_argument(
        "--github-output",
        default=None,
        help="GitHub Actions 的 $GITHUB_OUTPUT 文件路径（追加 android_ready/版本键）",
    )
    args = parser.parse_args(argv)
    if args.tag is not None and not args.tag.strip():
        print("::error::--tag 不能为空字符串", file=sys.stderr)
        return 1

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    try:
        result = check_versions(root, args.tag, args.platform)
    except VersionError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    lines = [
        f"desktop={result['desktop_version']}",
        f"android={result['android_version']} (versionCode {result['android_version_code']})",
        f"harmony={result['harmony_version']}",
    ]
    if "tag_version" in result:
        lines.append(f"tag={result['tag_version']} platform={args.platform}")
    lines.append(f"android_ready={result['android_ready']}")
    lines.append("OK: 版本一致性校验通过")
    _emit(lines, sys.stdout)

    if args.github_output:
        try:
            with open(args.github_output, "a", encoding="utf-8") as fh:
                for key in (
                    "android_ready",
                    "desktop_version",
                    "android_version",
                    "android_version_code",
                    "harmony_version",
                ):
                    fh.write(f"{key}={result[key]}\n")
        except OSError as exc:
            print(f"::error::写入 GITHUB_OUTPUT 失败: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
