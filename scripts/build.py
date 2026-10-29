"""PyInstaller 统一打包入口 (Windows 单文件 exe / macOS .app).

修掉的历史问题 (P2-14): 打包参数此前手抄在 5 处 (release.yml ×2、release-windows.yml、
build.bat、build_macos.sh + 自动生成的 GoGauge.spec), 已经出现漂移 (有的带
--noconfirm --clean, 有的不带; macOS 忘了生成 _build_info.py 就会去 upstream 查更新)。
现在 workflow 与本地脚本都只调本文件:

    python scripts/build.py --platform macos   [--repo owner/name]
    python scripts/build.py --platform windows [--repo owner/name]

职责:
1. 校验运行平台与 --platform 一致 (跨平台构建只会产出坏包, 直接报错);
2. 生成 app/_build_info.py (UPDATE_REPO, 默认本 fork; 可被 --repo / GOUSAGE_UPDATE_REPO 覆盖);
3. macOS: 生成 icns/png 图标 -> PyInstaller --windowed -> 写 Info.plist 版本 -> ad-hoc 重签;
   Windows: PyInstaller --onefile --noconsole;
4. 校验产物存在/可执行, 打印版本、仓库、产物路径与大小。

依赖由调用方安装 (workflow 用对应 lock; build.bat/build_macos.sh 是先装 lock 的薄包装),
本脚本不联网、不 pip install。
"""
from __future__ import annotations

import argparse
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "entry.py"
APP_INIT = ROOT / "app" / "__init__.py"
BUILD_INFO = ROOT / "app" / "_build_info.py"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_DIR = BUILD_DIR / "spec"
WORK_DIR = BUILD_DIR / "pyinstaller"

DEFAULT_UPDATE_REPO = "w-PiaoPiao/opencode-go-gauge"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_VERSION_RE = re.compile(r"""__version__\s*=\s*["']([^"']+)["']""")

HIDDEN_IMPORTS = ["pystray"]
EXCLUDES = ["numpy", "cryptography", "PIL._avif"]
ADD_DATA_DIRS = ("app/web", "assets")

PLATFORM_ALIASES = {"windows": "windows", "win": "windows", "macos": "macos", "darwin": "macos"}


def _force_utf8_stdio() -> None:
    """把 stdout/stderr 强制成 UTF-8, 避免中文日志在非 UTF-8 控制台上崩掉构建。

    Windows runner 的控制台编码是 cp1252 (中文系统为 cp936), ``print`` 中文会抛
    UnicodeEncodeError —— v2.2.2b 首次 Windows CI 实证: ``GoGauge.exe`` 已构建成功,
    却在最后一行「完成」上 exit 1, 整条发布链因此失败。``errors='replace'`` 保证极端
    情况 (输出被重定向到非 UTF-8 图形界面) 也只损失字形, 不改变退出码与产物。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # 已关闭/不可重配置的流: 保持原样
            pass


_force_utf8_stdio()


class BuildError(RuntimeError):
    """构建前置条件/后处理失败 (打印可读原因并以非 0 退出)。"""


def _host_platform() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return sys.platform


def _read_version() -> str:
    """从源码文本读版本号 (不 import: 旧 pyc 在 mtime+size 恰好未变时会读到旧版本)."""
    match = _VERSION_RE.search(APP_INIT.read_text(encoding="utf-8"))
    if not match:
        raise BuildError(f"无法从 {APP_INIT.relative_to(ROOT)} 解析 __version__")
    return match.group(1)


def _resolve_update_repo(explicit: Optional[str]) -> str:
    repo = (explicit or os.environ.get("GOUSAGE_UPDATE_REPO") or DEFAULT_UPDATE_REPO).strip()
    if not _REPO_RE.match(repo):
        raise BuildError(f"UPDATE_REPO 形态非法 (应为 owner/name): {repo!r}")
    return repo


def _write_build_info(repo: str) -> None:
    """生成 app/_build_info.py (gitignore): 冻结包的更新检查仓库 = 实际分发 fork."""
    BUILD_INFO.write_text(
        '"""构建时自动生成 (gitignored): 打包产物元信息, 供更新检查使用."""\n'
        f'UPDATE_REPO = "{repo}"\n',
        encoding="utf-8",
    )
    print(f"[build] app/_build_info.py: UPDATE_REPO={repo}")


def _run(cmd: list[str]) -> None:
    print("[build] $ " + " ".join(str(c) for c in cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise BuildError(f"命令失败 (exit {result.returncode}): {cmd[0]}")


def _check_pyinstaller() -> None:
    """依赖/解释器前置检查: 失败给出可操作提示 (而非 PyInstaller 的 import traceback)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            cwd=ROOT, capture_output=True, text=True, check=False)
    except OSError as exc:  # 解释器本身异常
        raise BuildError(f"无法执行 {sys.executable}: {exc}") from exc
    if result.returncode != 0:
        lock = "requirements-windows.lock.txt" if _host_platform() == "windows" else (
            "requirements-macos.lock.txt")
        raise BuildError(
            "PyInstaller 不可用 (或安装损坏), 请先安装锁定依赖再构建:\n"
            f"    {Path(sys.executable).name} -m pip install -r {lock}\n"
            f"stderr: {(result.stderr or '').strip()[:300]}")
    print(f"[build] python={sys.version.split()[0]} pyinstaller={result.stdout.strip()}")


def _add_data_arg(rel: str) -> str:
    # PyInstaller CLI 的 --add-data 用 os.pathsep 分隔 src/dest (Windows 为 ';').
    # 源路径必须是绝对路径: PyInstaller 6 会把相对源路径按 --specpath 解析,
    # 否则会去 build/spec/app/web 找文件 (实测 ERROR: Unable to find ...)。
    return f"{(ROOT / rel).as_posix()}{os.pathsep}{rel}"


def _pyinstaller_args(platform: str) -> list[str]:
    args = [
        "--noconfirm", "--clean", "--name", "GoGauge",
        "--specpath", str(SPEC_DIR), "--workpath", str(WORK_DIR), "--distpath", str(DIST_DIR),
    ]
    if platform == "windows":
        args += ["--onefile", "--noconsole", "--icon",
                 str(ROOT / "assets" / "GoGauge.ico")]
        args += ["--hidden-import", "clr", "--hidden-import", "pythonnet"]
    else:
        args += ["--windowed", "--icon", str(ROOT / "assets" / "GoGauge.icns"),
                 "--osx-bundle-identifier", "com.opencode.gogauge"]
    for hidden in HIDDEN_IMPORTS:
        args += ["--hidden-import", hidden]
    for data in ADD_DATA_DIRS:
        args += ["--add-data", _add_data_arg(data)]
    args += ["--collect-submodules", "webview"]
    for module in EXCLUDES:
        args += ["--exclude-module", module]
    args += [str(ENTRY)]
    return args


def _generate_icons(platform: str) -> None:
    if platform == "macos":
        # 图标源在 assets/ 已被跟踪; 每次构建重新生成 (输出确定性, 与旧 build_macos.sh 一致)
        _run([sys.executable, str(ROOT / "scripts" / "build_macos_icon.py")])
        return
    ico = ROOT / "assets" / "GoGauge.ico"
    if not ico.is_file():
        raise BuildError(f"缺少 Windows 图标: {ico.relative_to(ROOT)}")


def _macos_finalize(version: str) -> Path:
    """写 Info.plist 版本 + ad-hoc 重签 (改 plist 会使 PyInstaller 的签名失效)."""
    app = DIST_DIR / "GoGauge.app"
    exe = app / "Contents" / "MacOS" / "GoGauge"
    plist = app / "Contents" / "Info.plist"
    if not exe.is_file():
        raise BuildError(f"PyInstaller 产物缺少可执行文件: {exe}")
    if not plist.is_file():
        raise BuildError(f"PyInstaller 产物缺少 Info.plist: {plist}")

    plist_buddy = "/usr/libexec/PlistBuddy"
    if not Path(plist_buddy).is_file():
        raise BuildError(f"缺少 {plist_buddy}, 无法写入 Info.plist 版本号")
    for key, value in (
        (":CFBundleShortVersionString", version),
        (":CFBundleVersion", version),
    ):
        # PyInstaller 模板可能缺键: Set 失败时 Add 创建
        set_result = subprocess.run(
            [plist_buddy, "-c", f"Set {key} {value}", str(plist)],
            capture_output=True, text=True, check=False)
        if set_result.returncode != 0:
            _run([plist_buddy, "-c", f"Add {key} string {value}", str(plist)])

    codesign = shutil.which("codesign")
    if not codesign:
        raise BuildError("缺少 codesign, 无法重签 .app (需要 Xcode Command Line Tools)")
    _run([codesign, "--force", "--deep", "--sign", "-", str(app)])
    # 验证签名/结构; 失败即视为构建失败 (旧脚本无此校验, 坏包会到用户手里)
    _run([codesign, "--verify", "--deep", "--strict", str(app)])
    return app


def _print_macos_artifact(app: Path) -> None:
    plist = app / "Contents" / "Info.plist"
    with open(plist, "rb") as fh:
        info = plistlib.load(fh)
    size = sum(p.stat().st_size for p in app.rglob("*") if p.is_file())
    print(f"[build] artifact: {app} ({size / (1 << 20):.1f} MiB)")
    print(f"[build] Info.plist: CFBundleShortVersionString="
          f"{info.get('CFBundleShortVersionString')!r} "
          f"CFBundleVersion={info.get('CFBundleVersion')!r} "
          f"CFBundleIdentifier={info.get('CFBundleIdentifier')!r}")


def _print_windows_artifact(exe: Path) -> None:
    if not exe.is_file() or exe.stat().st_size <= 0:
        raise BuildError(f"PyInstaller 未产出有效 exe: {exe}")
    print(f"[build] artifact: {exe} ({exe.stat().st_size / (1 << 20):.1f} MiB)")


def build(platform: str, repo: Optional[str] = None) -> int:
    host = _host_platform()
    if platform != host:
        raise BuildError(f"--platform {platform} 只能在 {platform} 上构建 (当前: {host})")
    if platform not in ("windows", "macos"):
        raise BuildError(f"不支持的 --platform: {platform!r}")
    if not ENTRY.is_file():
        raise BuildError(f"缺少打包入口: {ENTRY}")

    version = _read_version()
    update_repo = _resolve_update_repo(repo)
    print(f"[build] platform={platform} version={version} update_repo={update_repo}")
    _check_pyinstaller()
    _write_build_info(update_repo)
    _generate_icons(platform)

    for directory in (SPEC_DIR, WORK_DIR, DIST_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    # PyInstaller 缓存落在项目内, 便于离线/受限环境与 CI 复用 (旧 macOS 脚本同款)
    os.environ.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / ".pyicache"))

    _run([sys.executable, "-m", "PyInstaller", *_pyinstaller_args(platform)])

    if platform == "macos":
        app = _macos_finalize(version)
        _print_macos_artifact(app)
        print("[build] 完成: dist/GoGauge.app")
        return 0
    exe = DIST_DIR / "GoGauge.exe"
    _print_windows_artifact(exe)
    print("[build] 完成: dist/GoGauge.exe")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GoGauge PyInstaller 统一打包入口")
    parser.add_argument("--platform", required=True, choices=("windows", "macos", "win", "darwin"),
                        help="目标平台 (必须与当前运行平台一致)")
    parser.add_argument("--repo", default=None,
                        help="写入 _build_info.py 的更新仓库 (owner/name); "
                             "默认 GOUSAGE_UPDATE_REPO 或本 fork")
    args = parser.parse_args(argv)
    platform = PLATFORM_ALIASES[args.platform]
    try:
        return build(platform, args.repo)
    except BuildError as exc:
        print(f"[build] 失败: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[build] 已取消", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
