"""开机自启 (macOS LaunchAgent) 回归测试.

覆盖 P2-4: 自启启动时本进程就是 LaunchAgent 的 job, 关闭自启时若仍
`launchctl unload` 会给当前进程发 SIGTERM —— 表现为"一点关闭自启, app 直接退出".
修复后该场景只删除 plist (下次登录不再拉起), 不调用 unload.

约束: 不执行真实 launchctl / 不写真实 ~/Library/LaunchAgents (plist 路径与
subprocess 全部替身).
"""
from __future__ import annotations

import plistlib
from types import SimpleNamespace

import pytest

from app import autostart


@pytest.fixture()
def mac_agent(tmp_path, monkeypatch):
    """把自启模块钳到"macOS 打包版"并重定向 plist/launchctl 到替身."""
    plist_path = tmp_path / "LaunchAgents" / f"{autostart.PLIST_ID}.plist"
    calls: list[list[str]] = []
    state = {"running_as_agent": False, "job_loaded": False}

    monkeypatch.setattr(autostart.sys, "platform", "darwin")
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(autostart, "_plist_path", lambda: str(plist_path))
    monkeypatch.setattr(autostart, "_launchctl", lambda args: calls.append(list(args)))
    monkeypatch.setattr(
        autostart, "_running_as_launch_agent", lambda: state["running_as_agent"]
    )
    monkeypatch.setattr(autostart, "_job_loaded", lambda: state["job_loaded"])
    return SimpleNamespace(
        plist_path=plist_path, calls=calls, state=state, tmp_path=tmp_path
    )


def _write_plist(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"stale")


# ---------------------------------------------------------------------------
# enable
# ---------------------------------------------------------------------------


def test_enable_writes_plist_and_loads_job(mac_agent):
    assert autostart.enable() is True
    raw = mac_agent.plist_path.read_bytes()
    plist = plistlib.loads(raw)
    assert plist["Label"] == autostart.PLIST_ID
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] is False
    assert plist["ProgramArguments"] == [autostart.os.path.abspath(autostart.sys.executable)]
    assert mac_agent.calls == [["load", str(mac_agent.plist_path)]]


def test_enable_skips_load_when_job_already_loaded(mac_agent):
    """已加载的 job 再 load 会因 RunAtLoad 起第二个实例 (弹窗副作用), 只刷新 plist."""
    mac_agent.state["job_loaded"] = True
    assert autostart.enable() is True
    assert mac_agent.plist_path.is_file(), "plist 必须被刷新, 下次登录才生效"
    assert mac_agent.calls == [], "已加载时不得再 launchctl load"


def test_enable_returns_false_when_unsupported(monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "win32")
    assert autostart.supported() is False
    assert autostart.enable() is False


def test_enable_unsupported_leaves_no_plist(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "darwin")
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    monkeypatch.setattr(autostart, "_plist_path", lambda: str(tmp_path / "x.plist"))
    assert autostart.enable() is False
    assert not (tmp_path / "x.plist").exists()


# ---------------------------------------------------------------------------
# disable —— P2-4 的核心
# ---------------------------------------------------------------------------


def test_disable_skips_unload_when_running_as_the_agent(mac_agent):
    """自启启动的进程关闭自启: 只删 plist, 绝不 unload (否则 SIGTERM 自己)."""
    _write_plist(mac_agent.plist_path)
    mac_agent.state["running_as_agent"] = True

    assert autostart.disable() is True

    assert mac_agent.calls == [], "自启运行中调用 unload 会杀掉当前进程"
    assert not mac_agent.plist_path.exists(), "plist 必须删除, 下次登录不再自启"


def test_disable_unloads_when_not_the_agent(mac_agent):
    """非自启启动 (手动打开 app): 维持原有 unload + 删 plist 行为."""
    _write_plist(mac_agent.plist_path)
    mac_agent.state["running_as_agent"] = False

    assert autostart.disable() is True

    assert mac_agent.calls == [["unload", str(mac_agent.plist_path)]]
    assert not mac_agent.plist_path.exists()


def test_disable_noop_when_plist_missing(mac_agent):
    assert autostart.disable() is True
    assert mac_agent.calls == []


def test_disable_returns_false_when_remove_fails(mac_agent, monkeypatch):
    _write_plist(mac_agent.plist_path)
    mac_agent.state["running_as_agent"] = True
    monkeypatch.setattr(
        autostart.os, "remove", lambda _p: (_ for _ in ()).throw(OSError("denied"))
    )
    assert autostart.disable() is False


# ---------------------------------------------------------------------------
# launchctl 输出解析 (判断"当前进程是否就是 job")
# ---------------------------------------------------------------------------


def _run_stub(stdout: str, returncode: int = 0):
    return SimpleNamespace(stdout=stdout, returncode=returncode, stderr=b"")


def test_running_as_launch_agent_true_when_pid_matches(monkeypatch):
    output = (
        '{\n\t"Label" = "com.opencode.gogauge";\n'
        '\t"LastExitStatus" = 0;\n\t"PID" = %d;\n}\n' % autostart.os.getpid()
    )
    monkeypatch.setattr(
        autostart.subprocess, "run", lambda *a, **k: _run_stub(output)
    )
    assert autostart._running_as_launch_agent() is True


def test_running_as_launch_agent_false_when_pid_differs(monkeypatch):
    output = '{\n\t"PID" = %d;\n}\n' % (autostart.os.getpid() + 1)
    monkeypatch.setattr(
        autostart.subprocess, "run", lambda *a, **k: _run_stub(output)
    )
    assert autostart._running_as_launch_agent() is False


def test_running_as_launch_agent_false_when_not_loaded(monkeypatch):
    """launchctl list 非零 (未加载) / 无 PID 行 / 异常一律按"不是 job"处理."""
    monkeypatch.setattr(
        autostart.subprocess,
        "run",
        lambda *a, **k: _run_stub("Could not find service", returncode=113),
    )
    assert autostart._running_as_launch_agent() is False

    monkeypatch.setattr(
        autostart.subprocess, "run", lambda *a, **k: _run_stub("{\n}\n")
    )
    assert autostart._running_as_launch_agent() is False

    def boom(*_a, **_k):
        raise OSError("launchctl missing")

    monkeypatch.setattr(autostart.subprocess, "run", boom)
    assert autostart._running_as_launch_agent() is False


def test_job_loaded_uses_launchctl_exit_code(monkeypatch):
    monkeypatch.setattr(
        autostart.subprocess, "run", lambda *a, **k: _run_stub("", returncode=0)
    )
    assert autostart._job_loaded() is True
    monkeypatch.setattr(
        autostart.subprocess, "run", lambda *a, **k: _run_stub("", returncode=113)
    )
    assert autostart._job_loaded() is False
