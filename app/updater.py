"""检查 GitHub Releases 是否有新版本 (轻量更新提示, 不自动下载替换).

流程: 优先请求 GitHub API 最新 release -> 解析 tag -> 与本地 __version__ 比较;
API 受未认证限流(403)/502/超时影响时, 自动降级到 Releases Atom 流(不受 API 限流).
发现新版本后由用户点击按钮下载到本地 (半自动) 或打开 Releases 页自行下载.

资产信息与摘要来源 (I6/I7):
- 列表 API 路径: ``check_update()`` 直接带出匹配资产的 ``asset_url``/``asset_digest``,
  ``download_update()`` 复用, 不再二次请求 ``/releases/tags/{tag}``;
- Atom 兜底路径: 拿 release 里附带的 ``SHA256SUMS.txt`` 按摘要清单挑本平台资产
  (统一发布每次都会生成该文件), 无摘要时保持 fail-closed;
- API 仍可用的旧式 release (无 SHA256SUMS.txt) 回退到 tags 接口取资产。
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Optional

from . import __version__

# 源码/开发态默认仓库与**实际分发 fork**一致; 打包产物由 scripts/build.py 生成的
# app/_build_info.py 覆盖 (CI 里由 workflow 写入 github.repository)。此前源码态
# 回落到另一个（上游）仓库, 本地 build.bat 出的 exe 会去错的仓库查更新。
_DEFAULT_REPO = "w-PiaoPiao/opencode-go-gauge"


def _resolve_repo() -> str:
    env = (os.environ.get("GOUSAGE_UPDATE_REPO") or "").strip()
    if env:
        return env
    if getattr(sys, "frozen", False):
        try:
            from ._build_info import UPDATE_REPO  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001  文件不存在(源码运行/旧包)则回退默认
            pass
        else:
            repo = str(UPDATE_REPO or "").strip()
            if repo:
                return repo
    return _DEFAULT_REPO


REPO = _resolve_repo()
# 列表接口而非 /releases/latest: 仓库 Latest 是全平台共享的一个标记,
# 其它平台发布后占据 Latest 会把本平台判断带偏. 现在统一发布 (同一 release
# 内含全平台资产) 与旧式平台 tag 并存: 遍历列表, 用「旧式平台 tag 或统一
# release 且内含本平台资产」过滤, 再按版本号取最大.
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
ATOM_URL = f"https://github.com/{REPO}/releases.atom"
# 更新失败兜底打开的页面: **列表页**而非 /latest —— Latest 可能属于别的平台
# (仓库里有 v*-android / v*-harmony / v*-windows / v*-macos 单平台 release)。
RELEASES_PAGE_URL = f"https://github.com/{REPO}/releases"
# 旧名兼容: 语义已改成列表页 (server 侧 I8 默认打开它); 新代码请用 RELEASES_PAGE_URL
RELEASE_PAGE_URL = RELEASES_PAGE_URL
# 平台后缀/资产扩展名: 更新检查与下载按运行平台分流 (-macos .zip / -windows .exe)
_IS_WIN = sys.platform == "win32"
_PLATFORM_SUFFIX = "-windows" if _IS_WIN else "-macos"
_PLATFORM_NAME = "Windows" if _IS_WIN else "macOS"
_ASSET_EXT = ".exe" if _IS_WIN else ".zip"
# 已知平台后缀: 统一发布用不带后缀的版本 tag (如 v2.2.1d), 旧式按平台发布的
# tag (v2.2.1d-macos / -windows / -android / -harmony) 继续兼容.
_KNOWN_SUFFIXES = ("-windows", "-macos", "-android", "-harmony")
# tag 上可能出现的平台+架构组合后缀 (资产名形态, 防御性剥离; 见 _parse_version_core)
_PLATFORM_SUFFIX_COMBOS = (
    "-macos-arm64", "-macos-x86_64", "-macos-universal2", "-windows-x64",
)
# 预发布标记: 收紧后的版本正则不再吞任意尾缀, 这里显式识别并跳过 (Atom 路径没有
# GitHub 的 prerelease 布尔字段, 只能靠 tag 语义兜住)。
_PRERELEASE_MARKERS = ("-rc", "-beta", "-alpha", "-pre", "-dev")
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
_TIMEOUT = 8  # 秒; GitHub 直连可能超时, 快速失败避免卡住 UI
_MAX_ATTEMPTS = 3  # 境内直连 GitHub 间歇性 502/超时/重置, 自动重试提高成功率
_RETRY_SLEEP = 0.8  # 每次重试间隔(秒)

# 版本号: 先剥平台后缀, 再只接受「三段数字 + 可选单字母」的稳定版本 (如 2.1.0b,
# 排序上 2.1.0b > 2.1.0)。-rc/-beta/-alpha/-pre/-dev 与 +build 一律视为非稳定
# 版本 (_is_prerelease_tag), 不进更新候选。
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)([a-z])?$")
_HTML_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")
_SHA256SUMS_RE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")

# check_update() 的结果缓存: 「检查更新」-> 点下载 的流程里, 下载 worker 不再做
# 第二遍完整联网检查 (最坏 51.2s); 120s 内复用同一结果, 资产仍会重新校验摘要。
_CHECK_CACHE_TTL_SEC = 120.0
_check_cache: dict[str, Any] = {"at": 0.0, "data": None}


def _cached_check() -> Optional[dict[str, Any]]:
    """TTL 内最近一次成功的检查结果副本; 过期/未检查返回 None."""
    data = _check_cache.get("data")
    if data and (time.monotonic() - float(_check_cache.get("at") or 0.0)) < _CHECK_CACHE_TTL_SEC:
        return dict(data)
    return None


def _fetch_text(url: str) -> str:
    """请求指定 URL 并返回文本, 失败自动重试.

    重试耗尽后抛出最后一次底层异常, 由调用方决定降级或转为友好提示.

    Args:
        url: 完整请求地址

    Returns:
        响应文本

    Raises:
        urllib.error.HTTPError / URLError / TimeoutError / OSError: 重试仍失败
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"GoGauge/{__version__}", "Accept": "application/vnd.github+json"},
    )
    last: Optional[BaseException] = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return resp.read().decode("utf-8", "replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_SLEEP)
                continue
    if last:
        raise last  # type: ignore[misc]
    raise RuntimeError("unknown network error")


def _fetch_json(url: str) -> Any:
    """请求 GitHub API 并解析 JSON.

    Args:
        url: 完整请求地址

    Returns:
        解析后的 JSON 对象

    Raises:
        见 _fetch_text: 重试仍失败时抛出底层异常
    """
    return json.loads(_fetch_text(url))


def _strip_html(text: str) -> str:
    """去除 HTML 标签并压缩空白, 供 Atom content 转纯文本展示."""
    text = _html.unescape(text or "")
    text = _HTML_TAG_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()


def _strip_platform_suffix(text: str) -> str:
    """剥掉 tag 末尾的已知平台/架构后缀 (不存在则原样返回)."""
    t = (text or "").strip().lower()
    for combo in _PLATFORM_SUFFIX_COMBOS:
        if t.endswith(combo):
            return t[: -len(combo)]
    for suffix in _KNOWN_SUFFIXES:
        if t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def _parse_version_core(text: str) -> Optional[tuple[int, int, int, int]]:
    """严格版本解析: 剥平台后缀后只接受稳定版本串.

    字母后缀按 a=1,b=2... 计入第四位 (无后缀=0); ``-rc/-beta/+build`` 等一律
    None (由 _is_prerelease_tag 负责显式识别/跳过)。
    """
    m = _VERSION_RE.match(_strip_platform_suffix(text))
    if not m:
        return None
    suffix = m.group(4) or ""
    letter_rank = (ord(suffix) - ord("a") + 1) if suffix else 0
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), letter_rank


def _parse_version(text: str) -> Optional[tuple[int, int, int, int]]:
    """解析版本为可比较的四元组 (平台 tag 如 v2.2.1d-macos 仍可解析, 语义不变)."""
    return _parse_version_core(text)


def _is_prerelease_tag(tag: str) -> bool:
    """tag 是否预发布 (剥平台后缀后仍含 -rc/-beta/-alpha/-pre/-dev 或 +构建元数据)."""
    base = _strip_platform_suffix(tag)
    if "+" in base:
        return True
    return any(marker in base for marker in _PRERELEASE_MARKERS)


def _is_platform_tag(tag: str) -> bool:
    """旧式平台 tag (如 v1.0.2-macos): 版本前缀合法且带本平台后缀."""
    t = (tag or "").strip().lower()
    return t.endswith(_PLATFORM_SUFFIX) and _parse_version(t) is not None


def _is_unified_tag(tag: str) -> bool:
    """统一发布 tag (如 v2.2.1d): 版本前缀合法且不带任何已知平台后缀.

    统一 release 约定内含 Windows / macOS / Android 全部资产, 所以 Atom 兜底
    (看不到资产列表) 只能信任该约定; API 列表路径会再校验资产是否真的存在.
    """
    t = (tag or "").strip().lower()
    return not t.endswith(_KNOWN_SUFFIXES) and _parse_version(t) is not None


def _asset_arch_suffix() -> str:
    """macOS 分发包的架构后缀 ("-arm64" / "-x86_64"); Windows 无.

    与 CI 产物命名 (GoGauge-v<ver>-macos-{arm64,x86_64}.zip) 以及
    _pick_platform_asset 的架构优先规则保持一致。
    """
    if _IS_WIN:
        return ""
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "-arm64"
    return "-x86_64"


def _asset_name_matches_platform(name: str) -> bool:
    """资产名是否属于运行平台 (统一发布 / 旧式发布命名都兼容).

    旧式: GoGauge-v2.2.1a-macos.zip / GoGauge-v2.1.0b-windows.exe
    统一: GoGauge-v2.2.1d-macos-arm64.zip / GoGauge-v2.2.1d-windows.exe
    """
    n = (name or "").strip().lower()
    if _IS_WIN:
        return n.endswith(".exe") and "windows" in n
    return n.endswith(".zip") and "macos" in n


def _pick_platform_asset(assets: Any) -> Optional[dict[str, Any]]:
    """从 release 资产列表挑运行平台安装包; macOS 按 CPU 架构优先.

    Args:
        assets: GitHub API 的 assets 数组 (容错非 dict / 空下载地址)

    Returns:
        匹配的资产对象; 没有时返回 None
    """
    candidates = [
        a for a in (assets or [])
        if isinstance(a, dict)
        and _asset_name_matches_platform(str(a.get("name") or ""))
        and str(a.get("browser_download_url") or "")
    ]
    if not candidates:
        return None
    if not _IS_WIN:
        machine = platform.machine().lower()
        prefer = (
            ("arm64", "aarch64")
            if machine in ("arm64", "aarch64")
            else ("x86_64", "x64", "amd64", "intel")
        )
        for asset in candidates:
            name = str(asset.get("name") or "").lower()
            if any(token in name for token in prefer):
                return asset
    return candidates[0]


def _release_applies(rel: dict[str, Any]) -> bool:
    """release 是否提供运行平台的安装包.

    - 旧式平台 tag: 直接认 (兼容历史上只发单平台的 release);
    - 统一 tag: 必须能在资产里找到本平台安装包, 否则跳过 —— 例如只含 Android
      APK 的 release 不能让桌面端误报有更新.
    """
    tag = str(rel.get("tag_name") or "").strip()
    if _is_platform_tag(tag):
        return True
    return _is_unified_tag(tag) and _pick_platform_asset(rel.get("assets")) is not None


def _release_asset_fields(rel: dict[str, Any]) -> tuple[str, str]:
    """release 里本平台资产的 (browser_download_url, digest); 没有则空串."""
    asset = _pick_platform_asset(rel.get("assets"))
    if asset is None:
        return "", ""
    return (
        str(asset.get("browser_download_url") or ""),
        str(asset.get("digest") or "").strip().lower(),
    )


def _fetch_latest_atom() -> dict[str, str]:
    """从 Releases Atom 流解析最新可用 release (不受 GitHub API 限流).

    Atom 条目不含资产列表, 只能按 tag 判定: 本平台旧式后缀, 或统一发布
    (无平台后缀; 约定统一 release 必带全平台资产). 多个候选取版本最大 ——
    Atom 按发布时间倒序, 但混排各平台 tag 时不能直接取首条.
    预发布 tag (-rc/-beta/…) 与非法 tag 一律跳过。

    Returns:
        {"tag", "release_url", "notes", "asset_url", "asset_digest"}
        (Atom 路径拿不到资产信息, 后两项恒为空串; download_update 会按
        SHA256SUMS.txt 兜底)

    Raises:
        RuntimeError: 流为空/解析失败/无平台条目
    """
    root = ET.fromstring(_fetch_text(ATOM_URL))
    entries = root.findall("a:entry", _ATOM_NS)
    if not entries:
        raise RuntimeError("GitHub Releases 订阅流为空，未获取到版本信息")

    best_ver: Optional[tuple[int, int, int, int]] = None
    best: Optional[dict[str, str]] = None
    for entry in entries:
        tag = ""
        id_el = entry.find("a:id", _ATOM_NS)
        if id_el is not None and id_el.text:
            tag = id_el.text.rsplit("/", 1)[-1].strip()
        if _is_prerelease_tag(tag):
            continue
        ver = _parse_version(tag)
        if ver is None or not (_is_platform_tag(tag) or _is_unified_tag(tag)):
            continue
        if best_ver is not None and ver <= best_ver:
            continue

        release_url = f"https://github.com/{REPO}/releases/tag/{tag}"
        for link in entry.findall("a:link", _ATOM_NS):
            href = link.get("href") or ""
            if link.get("rel") == "alternate" and "/releases/tag/" in href:
                release_url = href
                break

        notes = ""
        content = entry.find("a:content", _ATOM_NS)
        if content is not None and content.text:
            notes = _strip_html(content.text)

        best_ver = ver
        best = {
            "tag": tag,
            "release_url": release_url,
            "notes": notes,
            "asset_url": "",
            "asset_digest": "",
        }

    if best is not None:
        return best
    raise RuntimeError(f"Releases 订阅流中暂无 {_PLATFORM_NAME} 版本")


def _fetch_latest_platform_release() -> dict[str, str]:
    """从 Releases 列表取最新的可用 release (兼容统一发布与旧式平台 tag).

    遍历全部条目按版本号取最大 (而不是取首条): 统一 release 与旧式平台 tag
    混排在同一列表里, 创建时间顺序不等于版本顺序。跳过 GitHub 标记的
    prerelease/draft (草稿通常只有认证请求可见, 一并挡掉防意外)。

    Returns:
        {"tag", "release_url", "notes", "asset_url", "asset_digest"}

    Raises:
        RuntimeError: 列表为空或无可用条目
    """
    data = _fetch_json(RELEASES_URL)
    if not isinstance(data, list):
        raise RuntimeError("GitHub Releases 响应格式异常")
    best_ver: Optional[tuple[int, int, int, int]] = None
    best: Optional[dict[str, str]] = None
    for rel in data:
        if not isinstance(rel, dict):
            continue
        if rel.get("prerelease") or rel.get("draft"):
            continue  # 预发布/草稿不能推给稳定版用户
        tag = str(rel.get("tag_name") or "").strip()
        if _is_prerelease_tag(tag):
            continue
        ver = _parse_version(tag)
        if ver is None or not _release_applies(rel):
            continue
        if best_ver is not None and ver <= best_ver:
            continue
        best_ver = ver
        asset_url, asset_digest = _release_asset_fields(rel)
        best = {
            "tag": tag,
            "release_url": rel.get("html_url")
            or f"https://github.com/{REPO}/releases/tag/{tag}",
            "notes": str(rel.get("body") or "").strip(),
            "asset_url": asset_url,
            "asset_digest": asset_digest,
        }
    if best is not None:
        return best
    raise RuntimeError(f"Releases 中暂无 {_PLATFORM_NAME} 版本")


def check_update(use_cache: bool = False) -> dict[str, Any]:
    """请求 GitHub 最新本平台 release 并与本地版本比较.

    列表 API 首优(可按平台过滤); 受未认证限流(403)/502/超时影响时降级
    Atom 流(约等于无限额), 两者均失败才抛错, 并把具体原因带给前端展示.

    Args:
        use_cache: True 时优先返回 120s 内最近一次成功检查结果 —— 供
            download_update() 复用「检查更新」的结果, 避免同一流程联网两遍。
            默认 False 保持「每次调用都真实联网」的对外语义。

    Returns:
        {"has_update": bool, "current": str, "latest": str,
         "release_url": str, "notes": str,
         "asset_url": str, "asset_digest": str}
        asset_url/asset_digest 只有列表 API 路径能给出真实值; Atom 路径为空串
        (download_update 会按 SHA256SUMS.txt 兜底)。

    Raises:
        RuntimeError: 两种来源均失败时的可读提示
    """
    if use_cache:
        cached = _cached_check()
        if cached is not None:
            return cached

    errors: list[str] = []
    info: Optional[dict[str, str]] = None
    try:
        info = _fetch_latest_platform_release()
    except Exception as exc:  # noqa: BLE001 首次失败仅记录, 交由 Atom 兜底
        errors.append(str(exc))

    if info is None:
        try:
            info = _fetch_latest_atom()
        except Exception as exc:  # noqa: BLE001 双来源都失败 -> 友好提示
            errors.append(str(exc))
            raise RuntimeError(
                f"无法连接 GitHub，无法检查更新（{'；'.join(errors)}）。\n"
                "通常是境内直连 GitHub 暂时不可用：请稍后重试，"
                "或开启系统代理 / VPN 后再次「检查更新」。"
            ) from exc

    tag = info["tag"]
    latest = _parse_version(tag)
    current = _parse_version(__version__)
    has_update = bool(latest and current and latest > current)
    result = {
        "has_update": has_update,
        "current": __version__,
        "latest": tag,
        "release_url": info["release_url"],
        "notes": info["notes"][:600],
        "asset_url": str(info.get("asset_url") or ""),
        "asset_digest": str(info.get("asset_digest") or ""),
    }
    _check_cache["at"] = time.monotonic()
    _check_cache["data"] = dict(result)
    return result


def release_url_for_tag(tag: str) -> str:
    """平台 release 页 URL (供 server /api/update/open 兜底用; tag 做 URL 转义)."""
    safe = urllib.parse.quote(str(tag or "").strip(), safe="-._+")
    return f"https://github.com/{REPO}/releases/tag/{safe}"


def is_allowed_release_url(url: str) -> bool:
    """URL 是否落在本仓库的 GitHub Releases 页面内 (server 校验 POST url 用)."""
    try:
        parsed = urllib.parse.urlsplit(str(url or "").strip())
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        return False
    if parsed.username or parsed.password:
        return False
    prefix = f"/{REPO}/releases"
    return parsed.path == prefix or parsed.path.startswith(prefix + "/")


def fetch_asset_info(tag: str) -> tuple[str, str]:
    """取指定 release 中本平台分发包的下载直链与官方摘要.

    按资产名识别平台 (旧式 -macos/-windows 命名与统一发布命名都兼容),
    macOS 优先匹配当前 CPU 架构; GitHub API 的 assets[].digest 形如
    "sha256:<hex>" (无摘要时为空串).

    这是 API 兜底路径: 列表路径已在 check_update() 里带出资产信息, 只有
    Atom 兜底 (且 release 没带 SHA256SUMS.txt) 时才会再用到本函数。

    Returns:
        (browser_download_url, digest); 找不到资产时 url 为空串

    Raises:
        RuntimeError: API 不可达/响应异常 —— 与「资产不存在」区分开, 避免更新
            失败被误报为 "release 中未找到资产" 而掩盖真实原因.
    """
    try:
        data = _fetch_json(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"无法获取 release {tag} 的资产信息: {exc}") from exc
    asset = _pick_platform_asset(data.get("assets") if isinstance(data, dict) else None)
    if asset is None:
        return "", ""
    url = str(asset.get("browser_download_url") or "")
    digest = str(asset.get("digest") or "").strip().lower()
    return url, digest


def _asset_download_url(tag: str, name: str) -> str:
    """构造 release 资产的下载直链 (/releases/download/<tag>/<asset>)."""
    safe_tag = urllib.parse.quote(str(tag or "").strip(), safe="-._+")
    safe_name = urllib.parse.quote(str(name or "").strip(), safe="-._+")
    return f"https://github.com/{REPO}/releases/download/{safe_tag}/{safe_name}"


def _sha256sums_url(tag: str) -> str:
    return _asset_download_url(tag, "SHA256SUMS.txt")


def _parse_sha256sums(text: str) -> dict[str, str]:
    """解析 ``sha256sum`` 格式清单 -> {资产名: "sha256:<hex>"} (非法行忽略)."""
    sums: dict[str, str] = {}
    for line in (text or "").splitlines():
        m = _SHA256SUMS_RE.match(line.strip())
        if not m:
            continue
        sums[m.group(2)] = "sha256:" + m.group(1).lower()
    return sums


def _asset_from_sha256sums(tag: str) -> tuple[str, str]:
    """从 release 附带 SHA256SUMS.txt 挑本平台资产 -> (url, digest).

    统一发布 (release.yml) 每次都会生成该清单; 旧式单平台 release 没有时会
    HTTP 404, 由调用方回退 API。清单同时给出资产名与摘要, 因此不依赖发行
    工作流对资产命名的约定, 也避免为了拿 URL 再打被限流的 API。
    """
    sums = _parse_sha256sums(_fetch_text(_sha256sums_url(tag)))
    candidates = [
        {
            "name": name,
            "browser_download_url": _asset_download_url(tag, name),
            "digest": digest,
        }
        for name, digest in sums.items()
    ]
    asset = _pick_platform_asset(candidates)
    if asset is None:
        return "", ""
    return str(asset["browser_download_url"]), str(asset["digest"])


def _guess_asset_url(tag: str) -> str:
    """按发行工作流的资产命名约定猜下载直链 (只在显式跳过摘要校验时使用).

    仅作为 ``GOGauge_ALLOW_UNVERIFIED_UPDATE=1`` 的自建 release 逃生口:
    - 旧式平台 tag (v2.2.1b-macos): GoGauge-<tag>[-arch].zip / GoGauge-<tag>.exe
    - 统一 tag (v2.2.1d): GoGauge-<tag>-macos-<arch>.zip / -windows.exe
    """
    t = str(tag or "").strip().lower()
    arch = _asset_arch_suffix()
    if _IS_WIN:
        name = f"GoGauge-{tag}.exe" if t.endswith(_PLATFORM_SUFFIX) else (
            f"GoGauge-{tag}-windows.exe")
    elif t.endswith(_PLATFORM_SUFFIX):
        name = f"GoGauge-{tag}{arch}.zip"
    else:
        name = f"GoGauge-{tag}-macos{arch}.zip"
    return _asset_download_url(tag, name)


def _resolve_download_asset(tag: str, info: dict[str, Any]) -> tuple[str, str]:
    """解析待下载资产的 (url, digest).

    优先级: check_update 带出的资产 -> SHA256SUMS.txt -> tags API -> (显式
    跳过校验时) 命名约定。返回 ("","") 表示 release 里确实没有本平台资产;
    API 不可达等真实错误抛 RuntimeError (与「资产不存在」区分)。
    """
    url = str(info.get("asset_url") or "").strip()
    digest = str(info.get("asset_digest") or "").strip().lower()
    if url and digest:
        return url, digest

    sums_error: Optional[BaseException] = None
    if not url or not digest:
        try:
            sums_url, sums_digest = _asset_from_sha256sums(tag)
        except Exception as exc:  # noqa: BLE001 旧式 release 可能没有清单
            sums_url, sums_digest, sums_error = "", "", exc
        if not url and sums_url:
            url, digest = sums_url, sums_digest
        elif url and not digest:
            digest = sums_digest
    if url:
        return url, digest

    api_error: Optional[BaseException] = None
    try:
        api_url, api_digest = fetch_asset_info(tag)
    except Exception as exc:  # noqa: BLE001
        api_url, api_digest, api_error = "", "", exc
    if api_url:
        return api_url, api_digest or digest
    if api_error is not None and sums_error is not None:
        raise RuntimeError(
            f"无法获取 release {tag} 的安装包信息: {api_error}")
    if os.environ.get("GOGauge_ALLOW_UNVERIFIED_UPDATE") == "1":
        return _guess_asset_url(tag), digest
    return "", ""


def _verify_digest(path: str, digest: str) -> None:
    """对下载文件校验 GitHub 官方 SHA-256 摘要 (digest 形如 "sha256:<hex>").

    fail-closed: 摘要缺失或算法不受支持时直接拒绝. 先前的实现遇到空摘要会
    ``return`` 跳过校验, 只剩 zip CRC / 2 字节 PE 头自检 —— 那样一个被篡改或
    拼错的资产仍能通过并进入安装流程. GitHub 对本仓库全部资产都返回
    "sha256:<hex>", 故严格要求不会影响正常更新.
    确需跳过 (自建 release 无摘要) 时显式设置 GOGauge_ALLOW_UNVERIFIED_UPDATE=1.
    """
    if not digest.startswith("sha256:"):
        if os.environ.get("GOGauge_ALLOW_UNVERIFIED_UPDATE") == "1":
            return
        raise RuntimeError(
            "下载包缺少官方 SHA-256 摘要, 已阻止安装 (如为自建 release 可设 "
            "GOGauge_ALLOW_UNVERIFIED_UPDATE=1 跳过此检查)"
        )
    expected = digest.split(":", 1)[1].strip().lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise RuntimeError("下载包摘要格式非法, 已阻止安装")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != expected:
        raise RuntimeError(f"下载包校验失败 (SHA-256 不匹配): {actual[:16]}…")


def _safe_tag(tag: str) -> str:
    """远端 tag → 可安全拼进文件名的片段.

    tag 来自远端 API, 仅做白名单字符过滤后再拼路径: 过去版本正则的尾部
    ``(?:[-+].*)?`` 允许 "/" 与 "..", 直接拼接可写到 dest_dir 之外。即使现在
    版本解析更严格, 这里仍保留消毒作为纵深防御 (并供测试直接断言)。
    """
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(tag)).strip(".") or "update"


def _download_filename(tag: str) -> str:
    """下载落盘文件名: 与 CI 资产命名一致 (平台后缀去重 + macOS 带架构).

    旧式平台 tag (v2.2.1d-macos) 若直接拼 ``_PLATFORM_SUFFIX`` 会产出
    ``GoGauge-v2.2.1d-macos-macos.zip``; 这里先剥掉 tag 上的已知平台后缀, 再按
    ``GoGauge-<版本>-<平台>[-<架构>].<ext>`` 拼。macOS 带 arm64/x86_64 后缀,
    用户在下载目录里能直接分辨拿到的包 (与 _pick_platform_asset 的选择一致)。
    """
    safe = _safe_tag(tag)
    lower = safe.lower()
    for suffix in _KNOWN_SUFFIXES:
        if lower.endswith(suffix):
            safe = safe[: -len(suffix)]
            break
    return f"GoGauge-{safe}{_PLATFORM_SUFFIX}{_asset_arch_suffix()}{_ASSET_EXT}"


def download_update(
    dest_dir: str, info: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """检查更新并下载新版本安装包到 dest_dir (调用方放后台线程执行).

    Args:
        dest_dir: 保存目录 (通常 ~/Downloads)
        info: 可选的 check_update() 结果 (server 已检查过时可传入, 省一次联网);
            默认内部用 check_update(use_cache=True), 120s 内复用检查结果。

    Returns:
        {"state": "done|no_update|no_asset|error",
         "path": str, "latest": str, "error": str}
    """
    result: dict[str, Any] = {"state": "error", "path": "", "latest": "", "error": ""}
    try:
        check = info if isinstance(info, dict) else check_update(use_cache=True)
        result["latest"] = str(check.get("latest") or "")
        if not check.get("has_update"):
            result["state"] = "no_update"
            return result
        url, digest = _resolve_download_asset(result["latest"], check)
        if not url:
            result["state"] = "no_asset"
            result["error"] = f"release {result['latest']} 中未找到本平台安装包"
            return result
        os.makedirs(dest_dir, exist_ok=True)
        # 文件名走 _download_filename: tag 做白名单消毒 (纵深防御), 平台后缀去重,
        # macOS 带架构后缀 (旧式平台 tag 不再出现 -macos-macos.zip)
        dest = os.path.join(dest_dir, _download_filename(result["latest"]))
        part = dest + ".part"
        req = urllib.request.Request(
            url, headers={"User-Agent": f"GoGauge/{__version__}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(part, "wb") as fh:
                    while True:
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        fh.write(chunk)
            # 完整性校验: 优先比对 GitHub 官方 SHA-256 摘要 (HTTPS 之外的供应链防线),
            # release 未提供摘要时退回 zip CRC / exe PE 头自检, 防半截/损坏文件被直接安装
            _verify_digest(part, digest)
            if _ASSET_EXT == ".zip":
                import zipfile
                with zipfile.ZipFile(part) as zf:
                    bad = zf.testzip()
                    if bad is not None:
                        raise RuntimeError(f"下载包损坏 (CRC 校验失败): {bad}")
            else:
                with open(part, "rb") as fh:
                    if fh.read(2) != b"MZ":
                        raise RuntimeError("下载包损坏 (非有效的 Windows 可执行文件)")
            os.replace(part, dest)  # .part 中间态防半截文件
        except Exception:
            # 失败不留残骸: 否则校验不通过/网络中断会在下载目录堆一串
            # GoGauge-<tag>-*.zip.part, 用户没要过也再没人会用
            try:
                os.unlink(part)
            except OSError:
                pass
            raise
        result["state"] = "done"
        result["path"] = dest
        return result
    except Exception as exc:  # noqa: BLE001
        result["state"] = "error"
        result["error"] = str(exc)[:300]
        return result
