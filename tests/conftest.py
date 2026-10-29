"""pytest 全局配置 / 安全沙箱: 导入路径 / 时区 / GUI 依赖替身 / 真实数据目录隔离.

集中放在这里的原因（重要性依次递减）:

0. **绝不允许测试碰到用户真实数据目录**（最高优先级）。此前有测试在
   `db.set_data_dir(None)` 之后调用 `app.open_login()`，数据目录解析回落到源码
   运行的默认值 = 用户真实库 `~/Library/Application Support/GoGauge/data`，触发
   了一次在途迁移（数据无损，但属于必须堵死的类事故）。本文件在 import 阶段
   （早于任何测试模块）强制：

       os.environ["GOUSAGE_DATA"] = <本 session 的临时沙箱>

   因为 `db._default_data_dir()` 的优先级是 `_data_dir_override` > 环境变量
   `GOUSAGE_DATA` > 平台默认目录，所以 **`db.set_data_dir(None)` 现在回落到
   sandbox，而不是真实目录**（这一语义在 pytest 下成立，生产不受影响）。
   另加 autouse guard 在每个用例收尾断言解析结果仍在临时目录内，指向真实目录
   直接 fail；并顺带把 `_data_dir_override` 复位到 sandbox，防止泄漏给下一个用例。

1. **收集顺序不能成为隐式依赖**。CI 只装 requirements-dev.txt（不含 pywebview），
   而 app/auth.py、app/main.py 顶层 `import webview`。此前占位模块只写在
   test_auth_login.py / test_perf_runtime_opt.py 的模块顶层 —— 全套按字母序先
   import 到它们才侥幸能跑；单跑 test_login_session.py / test_windows_login.py
   或换随机顺序会直接 ImportError。放在 conftest 后，任何收集顺序/单文件运行都成立。

2. **固定时区**。local_date / localtime 相关断言在多处是"与同进程 SQLite 的
   localtime 自比"，CI runner 默认 UTC 时该断言退化成恒等变换（把本地日误写成
   UTC 也照样绿）。固定成 Asia/Shanghai 让本地与 CI 口径一致，也真正覆盖偏移
   路径。需要其它时区的测试请自行 monkeypatch TZ + tzset 并在 finally 恢复。

3. 提供统一的 `tmp_db` fixture，避免每个测试文件重复写 data_dir monkeypatch
   与 teardown（已有的本地同名 fixture 会覆盖本 fixture，不受影响）。
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ---------------------------------------------------------------------------
# 0) 真实数据目录沙箱（必须在任何 app/db 导入之前完成）
# ---------------------------------------------------------------------------
# 强制覆盖（不是 setdefault）: 即使外部环境误设 GOUSAGE_DATA 指向真实目录,
# 测试进程也一律落到本 session 的临时目录.
_SANDBOX_DIR = os.path.realpath(tempfile.mkdtemp(prefix="gousage-test-sandbox-"))
os.environ["GOUSAGE_DATA"] = _SANDBOX_DIR


def _allowed_test_roots(extra_roots: tuple[str, ...] = ()) -> list[str]:
    """凡落在这些根下的数据目录都视为"测试临时目录"（guard 放行）."""
    roots = [_SANDBOX_DIR]
    try:
        roots.append(os.path.realpath(tempfile.gettempdir()))
    except OSError:  # pragma: no cover - 极端环境
        pass
    # macOS 上 tempfile.gettempdir() 是 /var/folders/...; 测试里硬编码 /tmp 的
    # 临时目录也应放行（/tmp -> /private/tmp）
    try:
        roots.append(os.path.realpath("/tmp"))
    except OSError:  # pragma: no cover
        pass
    # pytest 的 basetemp 可被 --basetemp 指到系统临时目录之外, 由调用方补充
    for extra in extra_roots:
        if extra:
            roots.append(os.path.realpath(extra))
    return roots


def _is_sandboxed(path: str, extra_roots: tuple[str, ...] = ()) -> bool:
    real = os.path.realpath(path)
    for root in _allowed_test_roots(extra_roots):
        if real == root or real.startswith(root + os.sep):
            return True
    return False


def _real_data_dir_candidates() -> list[str]:
    """用户真实数据目录候选（命中即重点报错, 便于事故定位）."""
    home = os.path.realpath(os.path.expanduser("~"))
    return [
        os.path.join(home, "Library", "Application Support", "GoGauge"),
        os.path.join(home, "AppData", "Roaming", "GoGauge"),
        os.path.join(home, "AppData", "Local", "GoGauge"),
        os.path.join(home, ".local", "share", "GoGauge"),
        os.path.join(REPO_ROOT, "data"),
    ]


# ---------------------------------------------------------------------------
# 1) 固定时区: 影响 Python 的 time.localtime / SQLite 的 'localtime' 修饰符
# (SQLite 走 C localtime, 认 TZ 环境变量; tzset 让它立即生效)
#
# 约定: 本文件把全仓测试的基准时区固定为 Asia/Shanghai。**依赖其它时区的
# 测试必须自行切换并恢复**（例如自测 DST / 负偏移）:
#     old = os.environ.get("TZ")
#     os.environ["TZ"] = "America/New_York"
#     if hasattr(time, "tzset"): time.tzset()
#     try: ...                      # 断言
#     finally:
#         os.environ["TZ"] = old or "Asia/Shanghai"
#         if hasattr(time, "tzset"): time.tzset()
# 不建议放在 fixture 里跨测试生效（会影响同进程后续用例）。
# ---------------------------------------------------------------------------
os.environ["TZ"] = "Asia/Shanghai"
# Windows 没有 time.tzset: 保留 env（子进程会继承），不因缺函数而崩
if hasattr(time, "tzset"):
    time.tzset()  # noqa: SIM105 - POSIX 路径

# ---------------------------------------------------------------------------
# 2) pywebview 占位: 仅在真实包不可用时注入 (本地开发装了真包就用真包)
# ---------------------------------------------------------------------------
try:  # 需要区分"装没装", 不用 contextlib.suppress
    import webview  # noqa: F401
except Exception:  # noqa: BLE001  导入失败的情况不止 ImportError (缺 GUI 后端时也会炸)
    _webview_stub = types.ModuleType("webview")
    # 提供测试会 monkeypatch 到的最小 API 面（monkeypatch.setattr 默认要求属性
    # 已存在）: 窗口存活性判断用 windows; test_perf_runtime_opt 的 main() 假跑
    # 会替换 create_window/start; 文件对话框走 SAVE_DIALOG/OPEN_DIALOG 常量.
    # 这些值只在"未替换"时被调用, 真值无意义.
    _webview_stub.windows = []
    _webview_stub.create_window = lambda *a, **k: None
    _webview_stub.start = lambda *a, **k: None
    _webview_stub.SAVE_DIALOG = 1
    _webview_stub.OPEN_DIALOG = 2
    sys.modules["webview"] = _webview_stub


import pytest  # noqa: E402 - 必须放在上面几个"需在 app 导入前完成"的块之后


# ---------------------------------------------------------------------------
# 3) 进程级全局状态隔离
# ---------------------------------------------------------------------------

# server/main 会起的后台 daemon 线程名（见 app/server.py / app/main.py）:
# 同步、配额刷新、更新检查。它们带进程级副作用（running 标记 / 聚合代数 bump /
# 缓存写），用例结束时若仍在跑会污染后续用例。
_BACKGROUND_THREAD_NAMES = frozenset(
    {"gousage-sync", "gousage-quota", "gousage-update-check", "gousage-update-dl"}
)


def _wait_background_threads_gone(timeout: float = 3.0) -> None:
    """有界等待已知后台 daemon 线程退出（不 kill, 超时即返回）.

    正常情况没有线程存活, 循环立即返回（对整套耗时可忽略）。只有像"真跑了一遍
    main()"这类用例才会真的等到超时上限, 换来后续用例的确定性。
    """
    deadline = time.monotonic() + timeout
    current = threading.current_thread()
    while time.monotonic() < deadline:
        alive = [
            t for t in threading.enumerate()
            if t is not current and t.name in _BACKGROUND_THREAD_NAMES and t.is_alive()
        ]
        if not alive:
            return
        time.sleep(0.02)



@pytest.fixture(autouse=True)
def _no_real_data_dir_guard(tmp_path_factory):
    """每个用例收尾: 断言数据目录仍在临时沙箱内, 并把 override 复位.

    - 指向真实数据目录（macOS Application Support / Windows AppData /
      Linux .local/share / 仓库根 data/）或任何非临时路径 → 直接 fail，
      消息里带上具体路径与命中的真实目录候选；
    - 无论断言结果如何，先把 `_data_dir_override` 复位（`set_data_dir(None)`
      在本沙箱下回落到 `GOUSAGE_DATA` 的临时目录），避免泄漏给下一个用例。
    """
    # pytest 的 basetemp 可能被 --basetemp 指到系统临时目录外, 作为额外白名单根
    try:
        extra_roots: tuple[str, ...] = (str(tmp_path_factory.getbasetemp()),)
    except Exception:  # noqa: BLE001 - 非预期上下文时退回系统临时目录白名单
        extra_roots = ()

    yield

    try:
        from app import db  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - 缺运行依赖的收集环境不阻塞
        return

    try:
        resolved = os.path.realpath(db.data_dir())
    except Exception:  # noqa: BLE001 - 解析失败不阻塞收尾
        return

    # 先复位: 即使下面断言失败, 下一个用例也不会继承脏 override
    try:
        db.set_data_dir(None)
    except Exception:  # noqa: BLE001 - 复位失败不应掩盖真正的问题
        pass

    if _is_sandboxed(resolved, extra_roots):
        return

    hit = next(
        (candidate for candidate in _real_data_dir_candidates()
         if resolved == os.path.realpath(candidate)
         or resolved.startswith(os.path.realpath(candidate) + os.sep)),
        None,
    )
    detail = f"命中真实数据目录候选: {hit}" if hit else "路径不在任何测试临时目录内"
    pytest.fail(
        "测试污染真实数据目录: "
        f"{resolved}（{detail}）。"
        "测试请用 tmp_path / db.set_data_dir(str(tmp_path)) 并在 teardown 复位；"
        "conftest 的 GOUSAGE_DATA 沙箱只兜底默认解析，不替代显式隔离。",
        pytrace=False,
    )


@pytest.fixture(autouse=True)
def _reset_server_global_state():
    """每个用例收尾: 有界等待已知后台线程退出 + 复位 server 进程级状态.

    背景（都是集成时实际发生过的连锁红）:
    - `server.set_auth_token(...)` 是模块级全局。某测试设置 token 后忘记复位,
      后续所有走 HTTP 的用例被 401 拦截;
    - `server._update_check` / `_update_download` 状态机同理;
    - `tests/test_perf_runtime_opt.py` 真跑了一遍 main(), 它会启动
      `gousage-sync` / `gousage-quota` daemon 线程。线程在后续用例里继续
      `running`/`bump_data_generation`, 导致 `test_perf_server_cache.py` 的
      缓存命中用例随机变红。这里**只做有界等待 + 复位状态机**, 不强制 kill
      daemon 线程（正常情况线程已退出, 循环立即返回）; 源头修法是用例侧
      monkeypatch `sync_all_async`（已通知 runtime-auth）。
    """
    _wait_background_threads_gone(timeout=3.0)

    yield

    _wait_background_threads_gone(timeout=3.0)
    try:
        from app import server  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return

    setter = getattr(server, "set_auth_token", None)
    if setter is not None:
        try:
            setter(None)
        except Exception:  # noqa: BLE001
            pass

    lock = getattr(server, "_update_check_lock", None)
    state = getattr(server, "_update_check", None)
    if lock is not None and isinstance(state, dict):
        try:
            with lock:
                state.update(state="idle", result=None, error="")
        except Exception:  # noqa: BLE001
            pass

    lock = getattr(server, "_update_lock", None)
    state = getattr(server, "_update_download", None)
    if lock is not None and isinstance(state, dict):
        try:
            with lock:
                state.update(state="idle", path="", error="", latest="")
        except Exception:  # noqa: BLE001
            pass

    sync_lock = getattr(server, "_sync_lock", None)
    sync_state = getattr(server, "_sync_state", None)
    if sync_lock is not None and isinstance(sync_state, dict):
        try:
            with sync_lock:
                sync_state.update(
                    running=False, mode="", page=0, inserted=0,
                    phase="idle", message="", account="",
                )
        except Exception:  # noqa: BLE001
            pass
        # 同步中禁止并发双开的集合/节流缓存同样是进程级全局
        try:
            refreshing = getattr(server, "_quota_refreshing", None)
            if isinstance(refreshing, set):
                refreshing.clear()
        except Exception:  # noqa: BLE001
            pass

    try:
        key_names_fetched = getattr(server, "_key_names_fetched_at", None)
        if isinstance(key_names_fetched, dict):
            key_names_fetched.clear()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# 4) 统一 fixture (可选使用): 重定向 data_dir 到 tmp_path 并在收尾关闭连接
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """独立临时库: 重定向 db.data_dir 并重置 schema 就绪标记.

    用法: `def test_x(tmp_db): ...`（tmp_db 即 tmp_path）。
    收尾只关连接 + 清标记; 不改全局 _data_dir_override（由各测试自行 set_data_dir）。
    """
    from app import db  # noqa: PLC0415 - fixture 内导入, 兼容运行依赖不全的收集环境

    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    db._schema_init_path = None
    try:
        yield tmp_path
    finally:
        db.close_db()
        db._schema_init_path = None
