"""HTTPS 根证书兜底 (app/https_ca.py) —— 复现并验证冻结包的 SSL 故障修复.

背景: CI 用 python.org Python 构建的 macOS 包里, OpenSSL 的默认 CA 是构建机的
编译期路径, 用户机缺该路径时 https 全挂 (CERTIFICATE_VERIFY_FAILED). 这里用
SSL_CERT_FILE/SSL_CERT_DIR 指向不存在的位置来等价复现"编译期路径失效".

平台差异 (断言不能跨平台照搬, 但每个平台都要断言自己那份真实契约):
- POSIX (macOS/Linux): 假定"系统必有 CA bundle". 注意这只是**测试机约定**,
  精简的 Linux 镜像仍可能没有, 所以缺少时是 skip 而不是 fail;
- Windows: OpenSSL 另外从系统证书存储 (CA 只读存储 / ROOT) 加载根证书, 与
  SSL_CERT_FILE 无关 —— "编译期路径失效 => 零 CA" 这个故障在 Windows 上不存在,
  也不可复现. 产品的对应契约是**零侵入**: install() 既不设 SSL_CERT_FILE, 也不
  包装 ssl._create_default_https_context (见 app/https_ca.py 模块文档).
"""
from __future__ import annotations

import os
import ssl
import sys

import pytest

from app import https_ca

# Windows: 走系统证书存储, "默认上下文零 CA" 不可构造 (见模块文档)
_WIN = sys.platform == "win32"


@pytest.fixture(autouse=True)
def _isolate_globals(monkeypatch):
    """install() 会改 ssl 全局与进程环境变量, 每个用例前后都要隔离."""
    saved_env = os.environ.get("SSL_CERT_FILE")
    saved_factory = ssl._create_default_https_context
    monkeypatch.setattr(https_ca, "_installed", False)
    yield
    ssl._create_default_https_context = saved_factory
    if saved_env is None:
        os.environ.pop("SSL_CERT_FILE", None)
    else:
        os.environ["SSL_CERT_FILE"] = saved_env


def _break_default_ca(monkeypatch) -> None:
    monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent/cert.pem")
    monkeypatch.setenv("SSL_CERT_DIR", "/nonexistent")


def _has_system_bundle() -> bool:
    return https_ca.system_ca_file() is not None


def test_frozen_bundle_failure_is_reproducible(monkeypatch):
    """等价复现 CI 冻结包: 编译期 CA 路径缺失 -> 默认上下文零 CA (仅 POSIX)."""
    if _WIN:
        # Windows 的 OpenSSL 除 SSL_CERT_FILE 外还从系统证书存储加载, 变量置空也
        # 仍有数百个 CA —— 本用例的前提在该平台不成立, Windows 契约见下面的
        # test_install_is_zero_touch_on_windows
        pytest.skip("Windows 走系统证书存储, 不存在'编译期 CA 路径失效 => 零 CA'的故障")
    _break_default_ca(monkeypatch)
    ctx = ssl.create_default_context()
    assert ctx.cert_store_stats()["x509_ca"] == 0


def test_ensure_ca_recovers_empty_context(monkeypatch):
    """零 CA 上下文补齐系统 bundle —— 冻结包恢复 https 的关键一步."""
    if _WIN:
        # 系统证书存储不可卸载, 构造不出零 CA 上下文 (植桩 load_verify_locations
        # 只能伪造补齐成功, 验不了真实 bundle 能装进上下文)
        pytest.skip("Windows 构造不出零 CA 上下文, 兜底路径走系统证书存储")
    if not _has_system_bundle():
        pytest.skip("本机没有已知系统 CA bundle")
    _break_default_ca(monkeypatch)
    ctx = ssl.create_default_context()
    assert ctx.cert_store_stats()["x509_ca"] == 0
    assert https_ca.ensure_ca(ctx) is True
    assert ctx.cert_store_stats()["x509_ca"] > 0


def test_ensure_ca_skips_context_with_ca():
    """已有 CA 的上下文不重复加载 (正常环境的 no-op 路径)."""
    ctx = ssl.create_default_context()
    before = ctx.cert_store_stats()["x509_ca"]
    if before == 0:
        pytest.skip("本机默认上下文无 CA, 无法验证 no-op 分支")
    assert https_ca.ensure_ca(ctx) is False
    assert ctx.cert_store_stats()["x509_ca"] == before


def test_ensure_ca_without_system_bundle(monkeypatch):
    """系统没有可用的 CA bundle 时安全返回 False, 不改动上下文."""
    monkeypatch.setattr(https_ca, "system_ca_file", lambda: None)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    assert ctx.cert_store_stats()["x509_ca"] == 0
    assert https_ca.ensure_ca(ctx) is False


def test_install_repairs_broken_default_context(monkeypatch):
    """install() 之后, 缺 CA 环境下任何默认上下文都能拿到系统 CA.

    两条路径都要成立: ① create_default_context() 直接创建 (靠 SSL_CERT_FILE);
    ② urllib/http.client 取用的 ssl._create_default_https_context (靠工厂包装).
    """
    if _WIN:
        # 前提"默认上下文零 CA"在 Windows 不可构造, 该平台的对应契约见
        # test_install_is_zero_touch_on_windows
        pytest.skip("Windows 走系统证书存储, 构造不出缺 CA 的默认上下文")
    if not _has_system_bundle():
        pytest.skip("本机没有已知系统 CA bundle")
    _break_default_ca(monkeypatch)
    assert ssl.create_default_context().cert_store_stats()["x509_ca"] == 0

    https_ca.install()

    assert os.environ.get("SSL_CERT_FILE") == https_ca.system_ca_file()
    assert ssl.create_default_context().cert_store_stats()["x509_ca"] > 0
    assert ssl._create_default_https_context().cert_store_stats()["x509_ca"] > 0


def test_install_noop_in_healthy_env(monkeypatch):
    """默认上下文本来就带 CA 时零侵入: 不改工厂、不设环境变量."""
    if ssl.create_default_context().cert_store_stats()["x509_ca"] == 0:
        pytest.skip("本机默认上下文无 CA, 无法验证零侵入分支")
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    original = ssl._create_default_https_context

    https_ca.install()

    assert ssl._create_default_https_context is original
    assert "SSL_CERT_FILE" not in os.environ


def test_install_is_idempotent(monkeypatch):
    if not _has_system_bundle():
        pytest.skip("本机没有已知系统 CA bundle")
    _break_default_ca(monkeypatch)
    https_ca.install()
    first = ssl._create_default_https_context
    https_ca.install()
    assert ssl._create_default_https_context is first


def test_install_without_system_bundle(monkeypatch):
    """没有任何系统 bundle 时不安装任何东西 (不制造半吊子状态)."""
    _break_default_ca(monkeypatch)
    monkeypatch.setattr(https_ca, "system_ca_file", lambda: None)
    original = ssl._create_default_https_context

    https_ca.install()

    assert ssl._create_default_https_context is original


def test_system_ca_file_exists_on_this_machine():
    """POSIX (macOS/Linux) 必带系统根证书 —— 兜底依赖它存在.

    Windows 的真契约在 test_install_is_zero_touch_on_windows (那里断言
    system_ca_file() 为 None 且 install() 零侵入); 本文用例的"机器带 POSIX
    bundle"断言只对 POSIX 成立.
    """
    if _WIN:
        pytest.skip("Windows 走系统证书存储, 无 POSIX CA bundle (契约见 test_install_is_zero_touch_on_windows)")
    path = https_ca.system_ca_file()
    assert path is not None and os.path.isfile(path)


def test_install_is_zero_touch_on_windows(monkeypatch):
    """Windows 的真契约: 根证书来自系统证书存储, 兜底必须完全零侵入.

    由 CPython 的 ``_ssl`` 构造保证 (非本仓库代码, 故用 sys.platform 守卫):
    Windows 上 ``ssl.create_default_context()`` 走 ``enum_certificates("ROOT")``
    把系统根证书灌进上下文, 与 SSL_CERT_FILE 无关; 因此这里的默认上下文必然
    带 CA. 与之配套的产品契约是 "系统自带 CA 就不该介入": system_ca_file() 返回
    None (候选表全是 POSIX 路径), install() 既不设 SSL_CERT_FILE 也不包装
    ssl._create_default_https_context, 尤其**不**去信一个失效的 SSL_CERT_FILE
    (否则会把本来靠证书存储能用的 https 换成加载失败).
    """
    if not _WIN:
        pytest.skip("Windows 专属契约 (系统证书存储), 其他平台见 test_system_ca_file_exists_on_this_machine")
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    original = ssl._create_default_https_context
    # 1) 系统证书存储提供 CA —— Windows 上由 CPython _ssl 构造保证
    assert ssl.create_default_context().cert_store_stats()["x509_ca"] > 0

    https_ca.install()

    # 2) 兜底不介入: 不改工厂、不设环境变量
    assert ssl._create_default_https_context is original
    assert "SSL_CERT_FILE" not in os.environ
    # 3) 产品有意不为 Windows 提供 POSIX bundle 路径 (模块文档: Windows 走系统证书存储)
    assert https_ca.system_ca_file() is None

    # 4) 失效的 SSL_CERT_FILE 也照旧零侵入: 证书存储已够用, 不该被"修"成别的值
    monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent/cert.pem")
    monkeypatch.setattr(https_ca, "_installed", False)
    https_ca.install()
    assert os.environ["SSL_CERT_FILE"] == "/nonexistent/cert.pem"
    assert ssl._create_default_https_context is original
