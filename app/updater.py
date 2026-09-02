"""检查 GitHub Releases 是否有新版本 (轻量更新提示, 不自动下载替换).

流程: 优先请求 GitHub API 最新 release -> 解析 tag -> 与本地 __version__ 比较;
API 受未认证限流(403)/502/超时影响时, 自动降级到 Releases Atom 流(不受 API 限流).
发现新版本后由用户点击按钮用系统浏览器打开 Releases 页自行下载.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Optional

from . import __version__

# 源码/开发态默认上游仓库; 打包产物由 build_macos.sh 生成的 _build_info 覆盖,
# 使"更新检查源"与实际分发源一致 (fork 发布的版本检查 fork 的 releases).
_DEFAULT_REPO = "yphyphyph/opencode-go-gauge"


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
# android/windows 版发布后占据 Latest 会把 mac 更新判断带偏 (tag 后缀被
# 剥掉后 0.1.0-android < 当前版本 → 误判"已是最新"). 这里只认 -macos 条目.
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
ATOM_URL = f"https://github.com/{REPO}/releases.atom"
RELEASE_PAGE_URL = f"https://github.com/{REPO}/releases/latest"
# 平台后缀/资产扩展名: 更新检查与下载按运行平台分流 (-macos .zip / -windows .exe)
_IS_WIN = sys.platform == "win32"
_PLATFORM_SUFFIX = "-windows" if _IS_WIN else "-macos"
_ASSET_EXT = ".exe" if _IS_WIN else ".zip"
_ASSET_NAME = f"gogauge{_PLATFORM_SUFFIX}{_ASSET_EXT}"  # release 资产的标准文件名 (小写比较)
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
_TIMEOUT = 8  # 秒; GitHub 直连可能超时, 快速失败避免卡住 UI
_MAX_ATTEMPTS = 3  # 境内直连 GitHub 间歇性 502/超时/重置, 自动重试提高成功率
_RETRY_SLEEP = 0.8  # 每次重试间隔(秒)

# 版本号支持三段数字 + 可选字母预发布后缀 (如 2.1.0b, 排序上 2.1.0b > 2.1.0),
# 以及 -/+ 起尾缀 (如 2.1.0-macos / 2.1.0b-android, 尾缀不参与版本比较)
_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)([a-z])?(?:[-+].*)?$")
_HTML_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")


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


def _fetch_json(url: str) -> dict[str, Any]:
    """请求 GitHub API 并解析 JSON 对象.

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


def _fetch_latest_atom() -> dict[str, str]:
    """从 Releases Atom 流解析最新 release (不受 GitHub API 限流).

    只认本平台 (-macos) 条目: 流内混排各平台 release, 逐条过滤.

    Returns:
        {"tag": str, "release_url": str, "notes": str}

    Raises:
        RuntimeError: 流为空/解析失败/无平台条目
    """
    root = ET.fromstring(_fetch_text(ATOM_URL))
    entries = root.findall("a:entry", _ATOM_NS)
    if not entries:
        raise RuntimeError("GitHub Releases 订阅流为空，未获取到版本信息")

    for entry in entries:
        tag = ""
        id_el = entry.find("a:id", _ATOM_NS)
        if id_el is not None and id_el.text:
            tag = id_el.text.rsplit("/", 1)[-1].strip()
        if not _is_platform_tag(tag):
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

        return {"tag": tag, "release_url": release_url, "notes": notes}

    raise RuntimeError(f"Releases 订阅流中暂无 {_PLATFORM_SUFFIX} 版本")


def _parse_version(text: str) -> Optional[tuple[int, int, int, int]]:
    """解析版本为可比较的四元组; 字母后缀按 a=1,b=2... 计入第四位 (无后缀=0)."""
    m = _TAG_RE.match((text or "").strip())
    if not m:
        return None
    suffix = m.group(4) or ""
    letter_rank = (ord(suffix) - ord("a") + 1) if suffix else 0
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), letter_rank


def _is_platform_tag(tag: str) -> bool:
    """tag 是否为本平台 release (如 v1.0.2-macos): 版本前缀合法且带 -macos 后缀."""
    t = (tag or "").strip().lower()
    return t.endswith(_PLATFORM_SUFFIX) and _parse_version(t) is not None


def _fetch_latest_platform_release() -> dict[str, str]:
    """从 Releases 列表取最新的本平台 (-macos) release.

    API 按创建时间倒序返回, 首个匹配即最新; 各平台 tag 互不干扰.

    Returns:
        {"tag": str, "release_url": str, "notes": str}

    Raises:
        RuntimeError: 列表为空或无平台条目
    """
    data = _fetch_json(RELEASES_URL)
    if isinstance(data, list):
        for rel in data:
            tag = str(rel.get("tag_name") or "").strip()
            if not _is_platform_tag(tag):
                continue
            return {
                "tag": tag,
                "release_url": rel.get("html_url")
                or f"https://github.com/{REPO}/releases/tag/{tag}",
                "notes": str(rel.get("body") or "").strip(),
            }
    raise RuntimeError(f"Releases 中暂无 {_PLATFORM_SUFFIX} 版本")


def check_update() -> dict[str, Any]:
    """请求 GitHub 最新本平台 release 并与本地版本比较.

    列表 API 首优(可按平台过滤); 受未认证限流(403)/502/超时影响时降级
    Atom 流(约等于无限额), 两者均失败才抛错, 并把具体原因带给前端展示.

    Returns:
        {"has_update": bool, "current": str, "latest": str,
         "release_url": str, "notes": str}

    Raises:
        RuntimeError: 两种来源均失败时的可读提示
    """
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
            )

    tag = info["tag"]
    latest = _parse_version(tag)
    current = _parse_version(__version__)
    has_update = bool(latest and current and latest > current)
    return {
        "has_update": has_update,
        "current": __version__,
        "latest": tag,
        "release_url": info["release_url"],
        "notes": info["notes"][:600],
    }


_ASSET_NAME = "gogauge-macos.zip"  # release 资产的标准文件名 (小写比较)


def fetch_asset_url(tag: str) -> str:
    """取指定 release 中本平台分发包的下载直链.

    优先精确匹配标准资产名, 否则回退任一本平台扩展名的资产.

    Returns:
        browser_download_url; 找不到返回空串
    """
    try:
        data = _fetch_json(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
    except Exception:  # noqa: BLE001
        return ""
    fallback = ""
    for asset in data.get("assets") or []:
        name = str(asset.get("name") or "").strip().lower()
        url = str(asset.get("browser_download_url") or "")
        if not url:
            continue
        if name == _ASSET_NAME:
            return url
        if not fallback and (
            name.endswith(_PLATFORM_SUFFIX + _ASSET_EXT)
            or (not _IS_WIN and name.endswith(".zip"))
        ):
            fallback = url
    return fallback


def download_update(dest_dir: str) -> dict[str, Any]:
    """检查更新并下载新版本 zip 到 dest_dir (调用方放后台线程执行).

    Returns:
        {"state": "done|no_update|no_asset|error",
         "path": str, "latest": str, "error": str}
    """
    result: dict[str, Any] = {"state": "error", "path": "", "latest": "", "error": ""}
    try:
        info = check_update()
        result["latest"] = str(info.get("latest") or "")
        if not info.get("has_update"):
            result["state"] = "no_update"
            return result
        url = fetch_asset_url(result["latest"])
        if not url:
            result["state"] = "no_asset"
            result["error"] = f"release {result['latest']} 中未找到 {_ASSET_NAME}"
            return result
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"GoGauge-{result['latest']}{_PLATFORM_SUFFIX}{_ASSET_EXT}")
        req = urllib.request.Request(
            url, headers={"User-Agent": f"GoGauge/{__version__}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(dest + ".part", "wb") as fh:
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
        # 完整性自检 (HTTPS 之外的第二道防线): zip 验 CRC, exe 至少验 PE 头,
        # 防半截/损坏/被替换的文件在 os.replace 后被用户直接安装
        if _ASSET_EXT == ".zip":
            import zipfile
            with zipfile.ZipFile(dest + ".part") as zf:
                bad = zf.testzip()
                if bad is not None:
                    raise RuntimeError(f"下载包损坏 (CRC 校验失败): {bad}")
        else:
            with open(dest + ".part", "rb") as fh:
                if fh.read(2) != b"MZ":
                    raise RuntimeError("下载包损坏 (非有效的 Windows 可执行文件)")
        os.replace(dest + ".part", dest)  # .part 中间态防半截文件
        result["state"] = "done"
        result["path"] = dest
        return result
    except Exception as exc:  # noqa: BLE001
        result["state"] = "error"
        result["error"] = str(exc)[:300]
        return result