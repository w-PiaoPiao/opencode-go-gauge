"""凭证静态加密管道测试: token_fp 去重 / 迁移回填 / 加密形态读写 / payload 残留清理.

加密基元 (DPAPI/钥匙串) 依赖真实系统环境, 这里用替身验证 db 层的存储与解密管线;
明文路径 (非 frozen) 直接覆盖真实行为.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys

import pytest

from app import db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """独立临时库: 重定向 data_dir (同 test_db_multiuser)."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------


def test_token_fp_stable_and_trimmed():
    assert db._token_fp(" abc ") == hashlib.sha256(b"abc").hexdigest()
    assert db._token_fp("") == ""
    assert db._token_fp("   ") == ""


def test_storage_decode_plaintext_passthrough():
    # 非 frozen (源码运行/测试): 明文原样返回
    assert db._storage_decode(1, "auth=abc") == "auth=abc"
    assert db._storage_decode(1, "") == ""


def test_storage_encode_plaintext_when_not_frozen():
    if db._frozen():
        pytest.skip("打包环境不适用明文回退断言")
    assert db._storage_encode(1, "auth=abc") == "auth=abc"
    assert db._storage_encode(1, "  ") == ""


# ---------------------------------------------------------------------------
# db 层读写
# ---------------------------------------------------------------------------


def test_add_account_sets_fp(tmp_db):
    aid = db.add_account("tok-a", "", switch=True)
    row = db.get_db().execute(
        "SELECT token, token_fp FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == "tok-a"  # 非 frozen: 明文直存
    assert row["token_fp"] == db._token_fp("tok-a")


def test_dedup_by_fp(tmp_db):
    a1 = db.add_account("tok-a", "wrk_1")
    a2 = db.add_account("tok-a", "wrk_2")
    assert a1 == a2


def test_dedup_matches_legacy_row_after_backfill(tmp_db):
    """旧库 (无 token_fp 列) 被新版本进程打开时迁移回填, 新增同 token 账号应命中旧行."""
    aid = db.add_account("tok-legacy", "", switch=False)
    # 模拟旧版本写入的行: 指纹为 NULL (新加列的初始态, 迁移回填的目标)
    db.get_db().execute("UPDATE accounts SET token_fp = NULL WHERE id = ?", (aid,))
    db.get_db().commit()
    db.close_db()
    # 重新打开 = 新进程启动: 重置 schema 就绪标记, 让 _init_schema 重跑回填
    db._schema_init_path = None
    aid2 = db.add_account("tok-legacy", "", switch=True)
    assert aid2 == aid


def test_dedup_repairs_token_wiped_by_migration(tmp_db):
    """指纹命中但凭证已被迁移清空时, 同 token 重登必须把凭证补写回去.

    回归: 迁移 4/7 只置空 token 而留着 token_fp, add_account 靠
    (provider, token_fp) 去重并提前返回, 凭证于是永远写不回库 —— 接口返回成功
    (前端弹"已切换账号"), 但 count_logged_in_accounts() 恒为 0, /api/state 的
    logged_in 一直 false, 欢迎页的登录轮询不触发, 界面永久卡在欢迎页.
    """
    aid = db.add_account("tok-cc", "", switch=True, provider=db.PROVIDER_COMMANDCODE)
    # 迁移现场: 只清 token 一列, 指纹留下
    db.get_db().execute("UPDATE accounts SET token = '' WHERE id = ?", (aid,))
    db.get_db().commit()
    assert db.count_logged_in_accounts() == 0

    before = db.count_accounts()  # 新库自带播种的 Default 行, 基数不是 0
    aid2 = db.add_account("tok-cc", "", switch=True, provider=db.PROVIDER_COMMANDCODE)
    assert aid2 == aid           # 仍命中同一行, 不新建同名账号
    assert db.count_accounts() == before
    assert db.count_logged_in_accounts() == 1

    db.set_active_account(aid)
    assert db.get_token() == "tok-cc"


def test_get_token_decodes(tmp_db):
    aid = db.add_account("tok-a")
    db.set_active_account(aid)
    assert db.get_token() == "tok-a"


def test_keychain_roundtrip(tmp_db, monkeypatch):
    """mac 钥匙串形态: 库内只存 kc: 引用, 读侧经 _keychain_get 解出."""
    if sys.platform != "darwin":
        pytest.skip("钥匙串路径仅 darwin 存在")
    store: dict[int, str] = {}
    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(
        db, "_keychain_set", lambda aid, secret: (store.__setitem__(aid, secret) or True))
    monkeypatch.setattr(db, "_keychain_get", lambda aid: store.get(aid, ""))
    monkeypatch.setattr(db, "_keychain_delete", lambda aid: store.pop(aid, None))

    aid = db.add_account("tok-secret")
    db.set_active_account(aid)
    row = db.get_db().execute(
        "SELECT token, token_fp FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == db._KC_PREFIX  # 库内不含明文
    assert db.get_token() == "tok-secret"  # 读侧从钥匙串解出
    assert row["token_fp"] == db._token_fp("tok-secret")

    db.clear_account()
    assert aid not in store  # 登出清理钥匙串条目
    assert db.get_token() == ""


def test_keychain_failure_falls_back_to_plaintext(tmp_db, monkeypatch):
    """钥匙串写入失败必须回退明文, 不能弄丢凭证."""
    if sys.platform != "darwin":
        pytest.skip("钥匙串路径仅 darwin 存在")
    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(db, "_keychain_set", lambda aid, secret: False)
    aid = db.add_account("tok-plain")
    db.set_active_account(aid)
    row = db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == "tok-plain"
    assert db.get_token() == "tok-plain"


def _win_frozen_dpapi(monkeypatch):
    """模拟 Windows frozen DPAPI 环境 (加解密基元用可逆替身)."""
    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(db, "_dpapi_protect", lambda data: b"blob-" + data)
    monkeypatch.setattr(
        db, "_dpapi_unprotect", lambda blob: blob[len(b"blob-"):])


def _restart_app(tmp_db):
    """模拟进程重启: 关闭连接并重置 schema 就绪标记, 下次访问重跑迁移."""
    db.close_db()
    db._schema_init_path = None


def test_dpapi_v2_token_survives_restart_migration(tmp_db, monkeypatch):
    """Windows frozen: 新凭证存 enc:v2:, 模拟重启 (重跑迁移 7) 后仍解得回.

    回归: DPAPI 修复 (687f204) 换了实现但没换前缀, 修复版新凭证仍写 enc:v1:,
    与旧版垃圾同前缀 —— 迁移 7 每次启动都清 enc:v1:, 结果修复版用户一重启
    所有 DPAPI 凭证被清空 (两账号同时掉登录).
    """
    _win_frozen_dpapi(monkeypatch)
    aid = db.add_account("tok-secret", switch=True)
    row = db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"].startswith("enc:v2:")

    _restart_app(tmp_db)
    assert db.get_token() == "tok-secret"


def _mark_old_version() -> None:
    """把库标成"上一版本" (user_version=0 且无一次性清理 marker): 模拟老用户升级.

    真实老库由旧版本创建, 既没有 marker (旧代码没有这个概念), user_version 也是
    0/缺省; 两个状态都要还原, 否则新代码首启时写的 marker 会让清理被跳过.
    """
    import json as _json

    conn = db.get_db()
    conn.execute("PRAGMA user_version = 0")
    row = conn.execute("SELECT payload FROM settings WHERE id = 1").fetchone()
    data = _json.loads(row["payload"]) if row else {}
    if isinstance(data, dict):
        data.pop(db._ONE_TIME_CLEANUP_MARKER, None)
        conn.execute(
            "UPDATE settings SET payload = ? WHERE id = 1",
            (_json.dumps(data, ensure_ascii=False),),
        )
    conn.commit()
    db._invalidate_payload_cache()


def test_legacy_dpapi_v1_token_still_purged(tmp_db, monkeypatch):
    """旧库 (user_version=0) 升级时, enc:v1: 垃圾凭证被一次性清理 (迁移 7 语义)."""
    _win_frozen_dpapi(monkeypatch)
    aid = db.add_account("tok-x", switch=True)
    db.get_db().execute(
        "UPDATE accounts SET token = 'enc:v1:Z2FyYmFnZQ==' WHERE id = ?", (aid,))
    db.get_db().commit()
    _mark_old_version()  # 旧版本库: 一次性门控应当放行

    _restart_app(tmp_db)
    db.get_db().execute("SELECT 1").fetchone()  # 触发 _init_schema
    row = db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == ""


def test_dedup_rewrites_undecryptable_token(tmp_db, monkeypatch):
    """指纹命中但密文解不回来时 (换 Windows 用户 / DPAPI 凭据损坏) 也要重写凭证.

    注意 count_logged_in_accounts 只看 token 列非空, 这种行会被算作"已登录":
    界面不显示欢迎页, 但配额/同步全拉不到 —— 靠同 token 重登自愈.
    """
    state = {"broken": False, "protect_calls": 0}

    def fake_protect(data: bytes) -> bytes:
        # 每次加密产出不同密文, 使"凭证被重写"可观测 (真 DPAPI 也有随机盐)
        state["protect_calls"] += 1
        return b"blob%d-" % state["protect_calls"] + data

    def fake_unprotect(blob: bytes):
        if state["broken"]:
            return None
        return blob[blob.index(b"-") + 1:]

    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(db, "_dpapi_protect", fake_protect)
    monkeypatch.setattr(db, "_dpapi_unprotect", fake_unprotect)

    def read_back(aid: int) -> str:
        row = db.get_db().execute(
            "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
        return db._storage_decode(aid, row["token"] or "")

    aid = db.add_account("tok-secret", switch=True)
    assert read_back(aid) == "tok-secret"

    state["broken"] = True
    assert read_back(aid) == ""                  # 密文再也解不回来
    assert db.count_logged_in_accounts() == 1    # 但仍被计为已登录

    calls_before = state["protect_calls"]
    aid2 = db.add_account("tok-secret", "", switch=True)
    assert aid2 == aid
    assert state["protect_calls"] > calls_before  # 凭证被重新加密写回

    state["broken"] = False                      # 环境恢复后按新密文可解
    assert read_back(aid) == "tok-secret"


# ---------------------------------------------------------------------------
# 账号删除的 payload 残留清理
# ---------------------------------------------------------------------------


def test_delete_account_cleans_period_keys(tmp_db):
    aid = db.add_account("tok-x")
    db.record_monthly_reset(aid, "2026-01-01T00:00:00Z")
    db.record_period_bounds(aid, "2026-01-01T00:00:00Z", "2026-01-31T00:00:00Z")
    payload = db._raw_payload(db.get_db())
    assert f"monthly_reset:{aid}" in payload
    assert f"period_start:{aid}" in payload

    db.delete_account(aid)

    payload = db._raw_payload(db.get_db())
    assert f"monthly_reset:{aid}" not in payload
    assert f"period_start:{aid}" not in payload
    assert f"period_end:{aid}" not in payload


def test_migration_backfills_fp_from_legacy_schema(tmp_path, monkeypatch):
    """v2.1.0c 形态旧库 (accounts 无 token_fp 列) 打开时补列并回填指纹."""
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    conn = sqlite3.connect(str(tmp_path / "gousage.db"))
    conn.executescript(
        """
        CREATE TABLE accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL DEFAULT 'Default',
          workspace_id TEXT NOT NULL DEFAULT 'Default',
          resolved_workspace_id TEXT,
          token TEXT NOT NULL DEFAULT '',
          provider TEXT NOT NULL DEFAULT 'opencode',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        INSERT INTO accounts (name, token, provider, created_at, updated_at)
        VALUES ('L', 'tok-legacy', 'opencode', '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z');
        """
    )
    conn.commit()
    conn.close()

    # 打开即触发迁移
    assert db.get_active_account_id() == 1
    row = db.get_db().execute(
        "SELECT token_fp FROM accounts WHERE id = 1").fetchone()
    assert row["token_fp"] == db._token_fp("tok-legacy")
    db.close_db()

# ---------------------------------------------------------------------------
# 一次性旧凭证清理的门控 (P2-6): 只对"还没升级到本版本"的库跑一次
# ---------------------------------------------------------------------------


def _stored_tokens() -> dict[int, str]:
    rows = db.get_db().execute("SELECT id, token FROM accounts").fetchall()
    return {int(r["id"]): r["token"] for r in rows}


def test_cleanup_is_one_shot_and_keeps_new_credentials(tmp_db, monkeypatch):
    """升级后新写入的 auth= 明文 / enc:v2: / kc: 跨重启不再被清空.

    回归 (F3): 旧实现每次启动都执行 `token LIKE 'auth=%'` 清空 —— auth.py 的
    legacy 捕获路径仍可能生成 auth= 形态凭证, 用户"重登成功、重启又掉登录".
    一次性门控后: 清理只发生在 user_version 落后时, 之后所有形态原样保留.
    """
    _win_frozen_dpapi(monkeypatch)
    aid_v2 = db.add_account("tok-v2", "", switch=False)  # frozen win -> enc:v2:
    aid_plain = db.add_account("tok-plain", "", switch=False)
    conn = db.get_db()
    # 新版本写入的 auth= 明文 (源码运行/明文回退路径) 与 kc: 引用
    conn.execute("UPDATE accounts SET token = ? WHERE id = ?", ("auth=Fe26-new", aid_plain))
    aid_kc = db.add_account("", "", switch=False)
    conn.execute("UPDATE accounts SET token = ? WHERE id = ?", (db._KC_PREFIX, aid_kc))
    conn.commit()
    before = _stored_tokens()
    assert before[aid_v2].startswith("enc:v2:")

    for _ in range(2):  # 多次重启 (曾经每次启动都会清)
        _restart_app(tmp_db)
        db.get_db()
        assert _stored_tokens() == before
    # enc:v2 仍解得回, 登录不丢
    assert db._storage_decode(aid_v2, _stored_tokens()[aid_v2]) == "tok-v2"


def test_cleanup_gate_clears_old_db_once_then_stops(tmp_db, monkeypatch):
    """旧库升级: 首次启动清一次旧垃圾; 之后再写入的 auth= 不再被清."""
    _win_frozen_dpapi(monkeypatch)
    aid = db.add_account("tok-old", "", switch=False)
    conn = db.get_db()
    conn.execute("UPDATE accounts SET token = 'enc:v1:Z2FyYmFnZQ==' WHERE id = ?", (aid,))
    conn.execute(
        "INSERT INTO accounts (name, workspace_id, token, provider, created_at, updated_at)"
        " VALUES ('legacy-auth', 'Default', 'auth=old-session', 'opencode', '2026-01-01', '2026-01-01')"
    )
    conn.commit()
    _mark_old_version()

    _restart_app(tmp_db)
    tokens = _stored_tokens()
    assert tokens[aid] == ""                   # enc:v1 垃圾被清
    assert "auth=old-session" not in tokens.values()  # 旧会话 auth= 被清

    # 升级完成后新登录写回 auth= 形态: 重启必须保留 (旧实现会再次清空)
    conn = db.get_db()
    conn.execute("UPDATE accounts SET token = 'auth=Fe26-fresh' WHERE id = ?", (aid,))
    conn.commit()
    _restart_app(tmp_db)
    assert _stored_tokens()[aid] == "auth=Fe26-fresh"


# ---------------------------------------------------------------------------
# P2-5: 钥匙串 secret 走 stdin (不进 argv) + 回读校验 + 明文回退日志 + 存储模式
# ---------------------------------------------------------------------------


def test_keychain_set_uses_stdin_and_never_argv(monkeypatch):
    """secret 走 `security -i` 的 stdin; argv 里只有 `security -i` (ps 看不到 token)."""
    import subprocess
    import types

    # 不含双引号 (值内转义由 _security_quote 负责)
    secret = "tok with spaces=+/&"
    seen: list[tuple[list[str], dict]] = []

    def fake_run(args, **kwargs):
        seen.append((list(args), kwargs))
        if list(args) == ["/usr/bin/security", "-i"]:
            return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        # find-generic-password -w 回读: 返回刚"写入"的 secret
        return types.SimpleNamespace(returncode=0, stdout=secret.encode(), stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(db, "_KC_SERVICE", "GoGaugeTest-unit")  # 绝不碰真实服务名

    assert db._keychain_set(424242, secret) is True
    add_call = seen[0]
    assert add_call[0] == ["/usr/bin/security", "-i"]
    command = add_call[1]["input"].decode("utf-8")
    assert secret in command                               # secret 只在 stdin
    assert secret not in " ".join(add_call[0])             # 不在 argv
    # 值一律双引号包裹, 特殊字符 (空格 = + / &) 原样保留
    assert '-w "' + secret + '"' in command


def test_keychain_set_verifies_readback(monkeypatch):
    """`security -i` 解析异常时返回码可能是 0: 回读不一致必须判失败 (回退明文)."""
    import subprocess
    import types

    def fake_run(args, **kwargs):
        if list(args) == ["/usr/bin/security", "-i"]:
            return types.SimpleNamespace(returncode=0, stdout=b"ehh", stderr=b"")
        return types.SimpleNamespace(returncode=0, stdout=b"wrong-value", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(db, "_KC_SERVICE", "GoGaugeTest-unit")
    assert db._keychain_set(424242, "expected-value") is False


def test_storage_encode_fallback_logs_without_secret(tmp_db, monkeypatch, caplog):
    """加密不可用回退明文时必须写日志 (不含 token), 便于排查"为什么库内是明文"."""
    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(db, "_keychain_set", lambda aid, secret: False)
    with caplog.at_level("WARNING", logger="app.db"):
        stored = db._storage_encode(1, "super-secret-token")
    assert stored == "super-secret-token"  # 登录可用优先
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "钥匙串写入失败" in messages
    assert "super-secret-token" not in messages  # 日志绝不泄漏 token


def test_token_storage_mode(monkeypatch):
    monkeypatch.setattr(db, "_frozen", lambda: False)
    assert db.token_storage_mode() == "plain"
    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(sys, "platform", "win32")
    assert db.token_storage_mode() == "dpapi"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert db.token_storage_mode() == "keychain"


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI 仅 Windows")
def test_dpapi_real_roundtrip() -> None:
    """真实 DPAPI 加解密 roundtrip (Windows CI 上真跑, 其他平台 skip).

    回归背景: 旧实现的 DATA_BLOB.pbData 误用 c_char_p, 存进库的密文被 NUL 截断
    (并附赠野指针 free), 表现为"重启即掉登录/随机闪退"。这类 ctypes 结构体错误
    用替身(stub)永远测不出来, 必须真调 CryptProtectData/CryptUnprotectData。
    """
    plain = b"tok-real-dpapi-roundtrip-0123456789abcdef"
    blob = db._dpapi_protect(plain)
    assert blob is not None, "CryptProtectData 失败 (CI 环境异常)"
    assert blob != plain
    assert db._dpapi_unprotect(blob) == plain
    # 截断的密文必须安全失败 (返回 None), 不能抛异常/返回垃圾
    assert db._dpapi_unprotect(blob[:-4]) in (None, b"")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS 钥匙串专用")
def test_keychain_stdin_roundtrip_real_temp_service(monkeypatch):
    """真实 `security -i` stdin 写入/读回 (临时 service 名, 完成后删除).

    安全红线: 绝不能碰 `GoGauge` 服务名下用户的真实登录 token; 这里用随机
    service + 随机 account id, finally 清理.
    """
    import random
    import uuid

    service = f"GoGaugeTest-{uuid.uuid4().hex}"
    aid = 90_000_000 + random.randint(0, 9_000_000)
    monkeypatch.setattr(db, "_KC_SERVICE", service)
    secret = 'tok with spaces=+/&"quoted string"'
    try:
        if not db._keychain_set(aid, secret):
            pytest.skip("钥匙串不可用/被锁 (CI 环境), 跳过真实 CLI 集成断言")
        assert db._keychain_get(aid) == secret
    finally:
        db._keychain_delete(aid)


def test_token_storage_fallback_counter(tmp_db, monkeypatch):
    """N8: token_storage_mode() 是"预期保护方式"; 实际回退明文另有计数可查."""
    import sys as _sys

    monkeypatch.setattr(db, "_frozen", lambda: True)
    monkeypatch.setattr(_sys, "platform", "win32")
    monkeypatch.setattr(db, "_dpapi_protect", lambda data: None)  # 模拟加密失败
    before = db.token_storage_fallback_count()
    aid = db.add_account("tok-fallback", switch=False)
    assert db.token_storage_fallback_count() == before + 1
    row = db.get_db().execute(
        "SELECT token FROM accounts WHERE id = ?", (aid,)).fetchone()
    assert row["token"] == "tok-fallback"  # 回退明文, 登录可用
    assert db.token_storage_mode() == "dpapi"  # mode 仍报"预期保护方式"

    # 加密成功路径不增加计数
    monkeypatch.setattr(db, "_dpapi_protect", lambda data: b"blob-" + data)
    monkeypatch.setattr(db, "_dpapi_unprotect", lambda blob: blob[len(b"blob-"):])
    db.add_account("tok-ok", switch=False)
    assert db.token_storage_fallback_count() == before + 1
