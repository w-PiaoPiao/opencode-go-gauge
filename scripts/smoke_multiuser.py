"""多用户功能端到端冒烟测试 (无 GUI).

起真实 HTTP 服务 (随机端口), 用临时数据目录, 通过 API 断言多账号全流程:
账号列表/重命名/切换/删除(级联)/退出登录(移除行)/活跃偏好已登录/dashboard
按活跃账号过滤/守卫响应码. 配额接口打桩, 不触网.

运行: python scripts/smoke_multiuser.py   (退出码 0 = 全部通过)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmpdir = tempfile.mkdtemp(prefix="gousage-smoke-")
os.environ["GOUSAGE_DATA"] = _tmpdir  # 必须在 app.db 首次连接前生效

from app import db, server  # noqa: E402


class _FakeQuota:  # 配额打桩: 避免冒烟测试访问外网
    def to_dict(self):
        return {"success": True, "windows": []}


server.fetch_quota = lambda token, hint: _FakeQuota()


def call(method: str, path: str, body: dict | None = None):
    """请求本地服务, 返回 (status, json)."""
    url = f"http://{_host}:{_port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode())
        except Exception:  # noqa: BLE001
            payload = {}
        return exc.code, payload


PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def _rec(usg_id, inp=10):
    return {
        "usg_id": usg_id, "created_at": "2026-08-01T00:00:00Z", "model": "m1",
        "provider": None, "input_tokens": inp, "output_tokens": 5, "reasoning_tokens": 0,
        "cache_read_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
        "cost_raw": 0, "cost_usd": 0.1, "key_id": None, "session_id": None, "plan": None,
    }


def main() -> int:
    global _host, _port
    _host, _port = server.start_server(port=0)
    print(f"server at {_host}:{_port}, data={_tmpdir}")

    # 1. 全新库初始态
    st, st_body = call("GET", "/api/state")
    check("state 200", st == 200)
    check("fresh logged_in=False", st_body.get("logged_in") is False)
    check("fresh accounts_total==1", st_body.get("accounts_total") == 1)
    check("state has accounts list", isinstance(st_body.get("accounts"), list))
    st, acc = call("GET", "/api/accounts")
    check("accounts list ok", st == 200 and acc.get("ok") is True and acc.get("active_id") == 1)
    st, r = call("POST", "/api/sync?mode=incremental")
    check("sync guard 401 when none logged in", st == 401)

    # 2. 重命名种子账号 + 守卫
    st, r = call("POST", "/api/accounts/rename", {"id": 1, "name": "  主号 "})
    check("rename ok+stripped", st == 200 and r.get("ok") is True)
    st, r = call("POST", "/api/accounts/rename", {"id": 9999, "name": "x"})
    check("rename bogus id -> 400", st == 400)

    # 3. 添加账号 / 去重 / 切换守卫
    a2 = db.add_account("tok-b", "ws-b", switch=True)
    a3 = db.add_account("tok-c", "ws-c", switch=True)
    db.insert_usage_records([_rec("b1"), _rec("b2")], account_id=a2)
    db.insert_usage_records([_rec("c1", inp=99)], account_id=a3)
    dup = db.add_account("tok-b", "ws-b2", switch=True)
    check("add dedup reactivates existing", dup == a2 and db.get_active_account_id() == a2)
    db.set_active_account(a3)
    st, r = call("POST", "/api/accounts/switch", {"id": 1})
    check("switch tokenless -> 400", st == 400, str(r))
    st, r = call("POST", "/api/accounts/switch", {"id": 424242})
    check("switch bogus id -> 404", st == 404)

    # 4. dashboard 反映活跃账号 ws-c
    st, dash = call("GET", "/api/dashboard?range=all")
    check("dashboard 200", st == 200)
    check("dashboard active filter (ws-c)", dash["totals"]["request_count"] == 1, str(dash["totals"]))
    check("dashboard account_name==ws-c", dash.get("account_name") == "ws-c")
    check("dashboard counts 2/3", dash.get("accounts_logged_in") == 2 and dash.get("accounts_total") == 3)
    check("quota stubbed ok when logged in", bool(dash.get("quota")) and dash["quota"].get("success") is True)

    # 5. 切到 ws-b
    st, r = call("POST", "/api/accounts/switch", {"id": a2})
    check("switch ok", st == 200 and r.get("ok") is True)
    st, dash = call("GET", "/api/dashboard?range=all")
    check("dashboard follows switch (ws-b)", dash["totals"]["request_count"] == 2 and dash.get("account_name") == "ws-b")

    # 6. 删除 ws-b (级联): 活跃自动回落到已登录的 ws-c
    st, r = call("POST", "/api/accounts/delete", {"id": a2})
    check("delete ok remaining==2", st == 200 and r.get("remaining") == 2, str(r))
    st, dash = call("GET", "/api/dashboard?range=all")
    check("active falls back to logged-in ws-c", dash["totals"]["request_count"] == 1 and dash.get("account_name") == "ws-c")

    # 7. 退出登录当前账号 (=移除行): 全部退完 -> logged_in False / 回欢迎页条件成立
    st, r = call("POST", "/api/logout")
    check("logout ok", st == 200 and r.get("ok") is True)
    st, st2 = call("GET", "/api/state")
    check("all logged out state", st2.get("logged_in") is False and st2.get("accounts_logged_in") == 0)
    st, dash = call("GET", "/api/dashboard?range=all")
    check("dashboard empty after logout-all", dash["totals"]["request_count"] == 0)
    check("quota None after logout-all", dash.get("quota") is None)
    st, r = call("POST", "/api/sync?mode=full")
    check("full sync guard 401 when none logged in", st == 401)

    # 8. add 路由在无窗口环境返回 opened=False 且不崩溃
    st, r = call("POST", "/api/accounts/add", {})
    check("accounts/add no-window ok", st == 200 and r.get("opened") is False)

    # 9. settings PUT 不破坏 active_account_id / key_names
    db.save_key_names({"k9": "九"})
    st, r = call("PUT", "/api/settings", {"sync_interval_sec": 60})
    check("settings put ok", st == 200 and r.get("sync_interval_sec") == 60)
    check("key_names preserved", db.get_key_names() == {"k9": "九"})

    print(f"\nresult: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        code = main()
    finally:
        server.stop_server()
        db.close_db()
    sys.exit(code)
