"""HTTPS 根证书兜底 (app/https_ca.py) —— 复现并验证冻结包的 SSL 故障修复.

背景: CI 用 python.org Python 构建的 macOS 包里, OpenSSL 的默认 CA 是构建机的
编译期路径, 用户机缺该路径时 https 全挂 (CERTIFICATE_VERIFY_FAILED). 这里用
SSL_CERT_FILE/SSL_CERT_DIR 指向不存在的位置来等价复现"编译期路径失效".
"""
from __future__ import annotations

import os
import ssl

import pytest

from app import https_ca


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
    """等价复现 CI 冻结包: 编译期 CA 路径缺失 -> 默认上下文零 CA."""
    _break_default_ca(monkeypatch)
    ctx = ssl.create_default_context()
    assert ctx.cert_store_stats()["x509_ca"] == 0


def test_ensure_ca_recovers_empty_context(monkeypatch):
    """零 CA 上下文补齐系统 bundle —— 冻结包恢复 https 的关键一步."""
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
    """macOS/Linux 必带系统根证书 —— 兜底依赖它存在."""
    path = https_ca.system_ca_file()
    assert path is not None and os.path.isfile(path)
