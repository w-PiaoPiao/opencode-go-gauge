"""打包版的 HTTPS 根证书兜底.

PyInstaller 冻结后, OpenSSL 找默认 CA 用的仍是**构建机**的编译期路径: CI 用
python.org 的 Python 3.12 构建 macOS 包时, 路径被写成
``/Library/Frameworks/Python.framework/Versions/3.12/etc/openssl/cert.pem`` ——
用户机没装对应 python.org Python 时该文件不存在, ``load_default_certs`` 对缺失
的默认路径**静默失败**, 于是所有 https 请求在握手阶段报
``CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate``
(2026-10-08 实测: 配额拉取与同步全挂). 本地构建的包因"构建机就是运行机"而
从未暴露该问题.

策略: 包装 ``ssl._create_default_https_context``(urllib 的默认工厂), 只在默认
上下文**一个 CA 都没加载到**时回退加载系统 CA bundle. 缺 CA 才介入 ——
Windows 走系统证书存储、正常环境自带 CA, 均不受影响.
"""
from __future__ import annotations

import os
import ssl
from typing import Any, Optional

# 系统 CA bundle 候选 (按优先级): macOS 的系统根证书在 /etc/ssl/cert.pem
# (/private/etc/ssl 为其真实路径), 其后是各发行版与 Homebrew 的常见位置.
_CA_CANDIDATES = (
    "/etc/ssl/cert.pem",
    "/private/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
)

_installed = False


def system_ca_file() -> Optional[str]:
    """本机第一个存在的系统 CA bundle; 都不存在返回 None."""
    for path in _CA_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def ensure_ca(ctx: ssl.SSLContext) -> bool:
    """上下文没有任何 CA 时补齐系统 bundle; 返回是否补齐.

    用 ``cert_store_stats`` 探测而非试请求: 冻结包的故障是静默的 (OpenSSL 对
    缺失的默认路径不报错, 只在握手时拒绝), 只能靠"有没有装到 CA"判断.
    """
    try:
        if int(ctx.cert_store_stats().get("x509_ca") or 0) > 0:
            return False
    except Exception:  # noqa: BLE001 探测异常按未知处理, 尝试补齐更安全
        pass
    cafile = system_ca_file()
    if not cafile:
        return False
    try:
        ctx.load_verify_locations(cafile=cafile)
        return True
    except Exception:  # noqa: BLE001 补齐失败保持原行为, 不把网络功能拖垮
        return False


def install() -> None:
    """幂等: 默认上下文缺 CA 时用系统 bundle 兜底, 正常环境不动任何全局状态.

    双保险: ① 设 ``SSL_CERT_FILE`` —— OpenSSL 每次建默认上下文都会读, 覆盖所有
    走标准库的网络调用; ② 包装 urllib/http.client 的默认工厂, 兜住 ① 未生效的
    路径 (例如变量已被外部占用).
    """
    global _installed
    if _installed:
        return
    _installed = True

    try:
        if int(ssl.create_default_context().cert_store_stats().get("x509_ca") or 0) > 0:
            return  # 正常环境 (含 Windows 证书存储): 零侵入
    except Exception:  # noqa: BLE001 探测失败按"缺 CA"处理, 继续兜底
        pass

    cafile = system_ca_file()
    if not cafile:
        return

    # 环境变量只在缺席或指向不存在的文件时接管: 指向有效文件的变量是用户的
    # 显式配置 (自建 CA 等), 必须尊重; 指向不存在路径的显然是坏值, 一并修正.
    env_file = os.environ.get("SSL_CERT_FILE")
    if not env_file or not os.path.isfile(env_file):
        os.environ["SSL_CERT_FILE"] = cafile

    current = ssl._create_default_https_context
    if getattr(current, "_gousage_ca_fallback", False):
        return

    def _factory(*args: Any, **kwargs: Any) -> ssl.SSLContext:
        ctx = current(*args, **kwargs)
        ensure_ca(ctx)
        return ctx

    _factory._gousage_ca_fallback = True  # type: ignore[attr-defined]
    ssl._create_default_https_context = _factory
