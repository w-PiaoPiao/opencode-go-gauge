"""登录目标账号固化 (P1-1) 与登录成功流程 (P2-10) 的回归测试.

背景: 登录窗是非模态独立窗口, OAuth 期间用户可以在主窗口切换活跃账号.
旧实现 `on_login_success -> db.save_token()` 在**回调时刻**解析活跃账号, 会把
A 的新凭证写进 B 并销毁 B 的原凭证. 修复后目标账号在 `open_login` 发起时
固化 (`pending_mode["account_id"]`), 回调只按该 id 写入.

同时锁定:
- `_complete_login` 的副作用顺序: 保存 -> 缓存失效 -> **首次全量同步** -> UI;
  保存失败时不跑任何副作用 (不假装成功);
- 重打包/重启不丢登录: 同一 DB 重新走一遍 `_init_schema` 后, 凭证仍可解码,
  `count_logged_in_accounts()` 不变.
"""
from __future__ import annotations

import base64
import inspect
import uuid
from datetime import datetime, timezone

import pytest

from app import db, main


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """临时数据目录 (绝不碰用户真实库/钥匙串).

    set_data_dir + GOUSAGE_DATA 双保险: 任何绕过 override 的路径也都落 tmp.
    """
    monkeypatch.setenv("GOUSAGE_DATA", str(tmp_path))
    db.close_db()
    db.set_data_dir(str(tmp_path))
    yield tmp_path
    db.close_db()
    db.set_data_dir(None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _simulate_process_restart():
    """模拟"重新打包后新进程": 关连接 -> 清进程内缓存 -> 重新建连接并跑迁移."""
    db.close_db()
    for attr in ("_schema_init_path", "_payload_cache", "_payload_cache_path", "_data_dir_cache"):
        if hasattr(db, attr):
            try:
                setattr(db, attr, None)
            except Exception:  # pragma: no cover - 只读属性等极端情况
                pass
    for invalidate in ("_invalidate_payload_cache", "_invalidate_cred_cache"):
        if hasattr(db, invalidate):
            try:
                getattr(db, invalidate)()
            except Exception:  # pragma: no cover
                pass
    conn = db.get_db()
    # 即便路径缓存未失效, 也显式再跑一遍启动迁移 (等价于新进程启动)
    if hasattr(db, "_init_schema"):
        db._init_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# P1-1: relogin 目标账号固化
# ---------------------------------------------------------------------------


def _add(token: str, provider: str = "opencode", ws: str = "ws") -> int:
    return db.add_account(token, ws, switch=True, provider=provider)


def test_relogin_writes_to_target_account_not_active(tmp_db):
    """登录期间切到 B, A 的新凭证也必须写回 A (核心回归)."""
    aid_a = _add("__Host-console_session=OLD_A")
    aid_b = _add("__Host-console_session=B")
    db.set_active_account(aid_a)  # open_login 发起时: A 是活跃账号
    captured_target = db.get_active_account_id()
    db.set_active_account(aid_b)  # OAuth 期间用户在主窗口切到 B

    ok = main._persist_login_credential(
        "__Host-console_session=NEW_A",
        "ws",
        "opencode",
        mode="relogin",
        target_account_id=captured_target,
    )

    assert ok is True
    assert db.get_account_credentials(aid_a)[0] == "__Host-console_session=NEW_A"
    assert db.get_account_credentials(aid_b)[0] == "__Host-console_session=B", (
        "B 的原凭证被登录流程覆盖 (P1-1 复发)"
    )
    assert db.get_active_account_id() == aid_b, "登录流程不应把活跃账号切回 A"


def test_relogin_target_deleted_falls_back_to_add(tmp_db):
    """目标账号在登录期间被删除: 回退为新增账号, 凭证不静默丢弃."""
    aid = _add("__Host-console_session=OLD")
    db.set_active_account(aid)
    old_active = db.get_active_account_id()
    db.delete_account(old_active)
    assert db.count_logged_in_accounts() == 0

    ok = main._persist_login_credential(
        "__Host-console_session=FRESH",
        "ws",
        "opencode",
        mode="relogin",
        target_account_id=old_active,
    )

    assert ok is True
    assert db.count_logged_in_accounts() == 1
    assert db.get_token() == "__Host-console_session=FRESH"


def test_add_mode_creates_and_switches_account(tmp_db):
    """add 模式语义保持不变: 新增账号并切换为活跃."""
    _add("__Host-console_session=FIRST")
    before_ids = {a["id"] for a in db.list_accounts()}
    before_logged_in = db.count_logged_in_accounts()

    ok = main._persist_login_credential(
        "__Host-console_session=SECOND",
        "ws2",
        "opencode",
        mode="add",
        target_account_id=None,
    )

    assert ok is True
    accounts = db.list_accounts()
    new_ids = {a["id"] for a in accounts} - before_ids
    assert len(new_ids) == 1, "add 模式必须新增恰好一个账号行"
    assert db.count_logged_in_accounts() == before_logged_in + 1
    assert db.get_active_account_id() == new_ids.pop()


def test_relogin_without_target_keeps_legacy_semantics(tmp_db):
    """没拿到目标快照 (旧调用/DB 异常) 时保持旧语义: 更新活跃账号."""
    aid = _add("__Host-console_session=OLD")

    ok = main._persist_login_credential(
        "__Host-console_session=NEW",
        "ws",
        "opencode",
        mode="relogin",
        target_account_id=None,
    )

    assert ok is True
    assert db.get_account_credentials(aid)[0] == "__Host-console_session=NEW"


def test_db_save_token_supports_account_id_contract():
    """I1 契约: db.save_token 必须接受 account_id (main 侧直接按 id 写入)."""
    parameters = inspect.signature(db.save_token).parameters
    assert "account_id" in parameters
    assert parameters["account_id"].default is None


def test_relogin_passes_account_id(tmp_db, monkeypatch):
    """必须把固化后的目标 id 传给 db.save_token (而不是让 db 取活跃账号)."""
    calls: list[tuple[str, object]] = []

    def fake_save(token, workspace_id="Default", provider="opencode", account_id=None):
        calls.append((token, account_id))
        return True

    monkeypatch.setattr(db, "save_token", fake_save)
    ok = main._persist_login_credential(
        "tok", "ws", "opencode", mode="relogin", target_account_id=7
    )

    assert ok is True
    assert calls == [("tok", 7)]


def test_relogin_falls_back_to_add_when_target_missing_from_save(monkeypatch):
    """I1 返回 False (账号不存在) -> 回退 add_account, 不写错账号."""
    added: list[tuple] = []

    def fake_save(token, workspace_id="Default", provider="opencode", account_id=None):
        return False

    monkeypatch.setattr(db, "save_token", fake_save)
    monkeypatch.setattr(
        db, "add_account", lambda token, ws="", switch=True, provider="opencode": added.append(token) or 1
    )

    assert main._persist_login_credential(
        "tok", "ws", "opencode", mode="relogin", target_account_id=9
    ) is True
    assert added == ["tok"]


def test_window_api_exposes_auth_token_readonly(monkeypatch):
    """I4 双保险: 主窗口前端可在 fragment 丢失时经 js_api 只读兜底取 token."""
    api = main.WindowApi()
    monkeypatch.setitem(main._auth_token_ref, "token", "")
    assert api.get_auth_token() == ""

    monkeypatch.setitem(main._auth_token_ref, "token", "tok-readonly-123")
    assert api.get_auth_token() == "tok-readonly-123"
    # 只读方法: 除 self 外不接受参数 (前端无法传参改 token)
    params = inspect.signature(main.WindowApi.get_auth_token).parameters
    assert list(params) == ["self"]


# ---------------------------------------------------------------------------
# P2-10: 登录成功后的副作用顺序 / 失败不假装成功
# ---------------------------------------------------------------------------


def _complete(monkeypatch, persist_result, events, *, raise_exc=None):
    def fake_persist(*_a, **_k):
        if raise_exc is not None:
            raise raise_exc
        return persist_result

    monkeypatch.setattr(main, "_persist_login_credential", fake_persist)
    return main._complete_login(
        "tok",
        "ws",
        "opencode",
        mode="relogin",
        target_account_id=1,
        after_save=lambda: events.append("after_save"),
        sync=lambda mode: events.append(("sync", mode)),
        on_ui=lambda: events.append("ui"),
        log=lambda message: events.append(("log", message)),
    )


def test_complete_login_syncs_before_ui(monkeypatch):
    events: list = []
    ok = _complete(monkeypatch, True, events)

    assert ok is True
    # 首次全量同步必须先于任何 UI 收尾 (UI 线程忙时排在后面的同步会永远丢失);
    # 过滤掉纯日志事件, 只比较副作用顺序.
    actions = [e for e in events if not (isinstance(e, tuple) and e[0] == "log")]
    assert actions == ["after_save", ("sync", "full"), "ui"]


def test_complete_login_skips_all_side_effects_on_save_failure(monkeypatch):
    events: list = []
    ok = _complete(monkeypatch, False, events)

    assert ok is False
    assert "after_save" not in events
    assert not any(isinstance(e, tuple) and e[0] == "sync" for e in events)
    assert "ui" not in events
    assert any("NOT saved" in e[1] for e in events if isinstance(e, tuple) and e[0] == "log")


def test_complete_login_skips_side_effects_when_save_raises(monkeypatch):
    events: list = []
    ok = _complete(monkeypatch, False, events, raise_exc=RuntimeError("database is locked"))

    assert ok is False
    assert events and events[0][0] == "log"
    assert ("sync", "full") not in events
    assert "ui" not in events


# ---------------------------------------------------------------------------
# 重新打包/重启不丢登录 (同一 DB + 凭证形态重新初始化后仍可解码)
# ---------------------------------------------------------------------------


def test_credentials_survive_process_restart(tmp_db):
    """明文凭证: 新进程重新走 _init_schema 后 token 仍可解出、登录数不变."""
    token = "__Host-console_session=ALIVE_ACROSS_RESTART"
    aid = _add(token)

    _simulate_process_restart()

    assert db.count_logged_in_accounts() == 1
    stored = db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)
    ).fetchone()["token"]
    assert db._storage_decode(aid, stored) == token
    assert db.get_token() == token


def test_keychain_and_dpapi_forms_survive_schema_reinit(tmp_db, monkeypatch):
    """钥匙串 `kc:` / DPAPI `enc:v2:` 形态不得被启动迁移清掉 (重新打包不丢登录).

    安全: 只 monkeypatch `_KC_SERVICE` 为随机临时名并直接替换读写函数 ——
    绝不触碰真实 `GoGauge` service 与用户真实库.
    """
    service = f"GoGauge-review-{uuid.uuid4().hex}"
    monkeypatch.setattr(db, "_KC_SERVICE", service)
    monkeypatch.setattr(db, "_keychain_get", lambda _aid: "SECRET_FROM_KEYCHAIN")
    monkeypatch.setattr(db, "_dpapi_unprotect", lambda _blob: b"SECRET_FROM_DPAPI")
    plain = "__Secure-commandcode_prod_.session_token=PLAIN"
    v2 = "enc:v2:" + base64.b64encode(b"ciphertext").decode("ascii")
    conn = db.get_db()
    now = _now()
    try:
        ids = {}
        for name, token in (("kc-user", "kc:"), ("dpapi-user", v2), ("plain-user", plain)):
            cur = conn.execute(
                "INSERT INTO accounts (name, workspace_id, token, token_fp, provider,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, "Default", token, db._token_fp(token), "commandcode", now, now),
            )
            ids[name] = int(cur.lastrowid)
        conn.commit()

        _simulate_process_restart()

        assert db.count_logged_in_accounts() == 3
        assert db._storage_decode(ids["kc-user"], "kc:") == "SECRET_FROM_KEYCHAIN"
        assert db._storage_decode(ids["dpapi-user"], v2) == "SECRET_FROM_DPAPI"
        assert db._storage_decode(ids["plain-user"], plain) == plain
    finally:
        assert db._KC_SERVICE == service, "测试不得使用真实钥匙串 service"


# ---------------------------------------------------------------------------
# P3-18: macOS Cmd+Q 退出也武装 os._exit 兜底
# ---------------------------------------------------------------------------


def test_mac_terminate_arms_quit_fallback(monkeypatch):
    armed: list[int] = []
    monkeypatch.setattr(main, "_arm_quit_fallback", lambda *a, **k: armed.append(1))
    monkeypatch.setattr(main, "_quitting", False)

    main._prepare_mac_terminate()

    assert main._quitting is True, "Cmd+Q 后 on_closing 必须放行"
    assert armed == [1], "Cmd+Q 路径必须武装强制退出兜底 (P3-18)"
