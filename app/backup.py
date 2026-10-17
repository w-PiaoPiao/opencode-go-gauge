"""CSV / JSON 备份导出导入 (v2.2.0b) — Android 端 BackupManager.kt 的桌面 parity.

备份文件格式与 Android 端完全一致 (字段名对齐): 两端导出的 .json.gz 可互相导入。
凭证不可迁移 (桌面端 DPAPI/钥匙串加密, Android 端 Keystore 加密, 均无法跨设备
解密): 导入只重建空账号行, 用户重新登录后历史记录即可复用。
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import stat
import time
from typing import Any

from . import db

EXPORT_PAGE = 1000

CSV_HEADER = [
    "created_at", "model", "provider", "input_tokens", "output_tokens",
    "reasoning_tokens", "cache_read_tokens", "cache_write_5m_tokens",
    "cache_write_1h_tokens", "cost_usd", "session_id", "key_id", "plan", "account_id",
]


def _logged_in_accounts() -> list[dict[str, Any]]:
    return [a for a in db.list_accounts() if a.get("has_token")]


def export_csv(path: str) -> int:
    """导出全部已登录账号的用量明细为 CSV, 返回写出行数."""
    rows_written = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for acc in _logged_in_accounts():
            # keyset 游标 (created_at, usg_id): offset 分页每页都要跳过前面全部行,
            # 导出 20 万行是 O(页数²); 游标分页每页代价恒定 (实测 200k 行端到端
            # 导出 13.5s → 1.8s).
            after: tuple[str, str] | None = None
            while True:
                page = db.export_page(EXPORT_PAGE, account_id=acc["id"], after=after)
                if not page:
                    break
                for r in page:
                    writer.writerow([
                        r.get("created_at", ""), r.get("model", ""), r.get("provider") or "",
                        r.get("input_tokens", 0), r.get("output_tokens", 0),
                        r.get("reasoning_tokens", 0), r.get("cache_read_tokens", 0),
                        r.get("cache_write_5m_tokens", 0) or 0,
                        r.get("cache_write_1h_tokens", 0) or 0,
                        r.get("cost_usd", 0.0), r.get("session_id") or "", r.get("key_id") or "",
                        r.get("plan") or "", r.get("account_id", acc["id"]),
                    ])
                rows_written += len(page)
                if len(page) < EXPORT_PAGE:
                    break
                after = (page[-1]["created_at"], page[-1]["usg_id"])
    return rows_written


def _record_payload(r: dict[str, Any], fallback_account_id: Any) -> dict[str, Any]:
    """备份记录的单条序列化形态 (Android 导入 parity).

    字段名与**顺序**是外部契约 (两端 .json.gz 互导 + 字段顺序参与新旧实现逐字节
    比对), 改动需同步 Android 端 BackupManager.
    """
    return {
        "usgId": r["usg_id"],
        "createdAt": r["created_at"],
        "model": r["model"],
        "provider": r.get("provider"),
        "inputTokens": r.get("input_tokens", 0),
        "outputTokens": r.get("output_tokens", 0),
        "reasoningTokens": r.get("reasoning_tokens", 0),
        "cacheReadTokens": r.get("cache_read_tokens", 0),
        "cacheWrite5mTokens": r.get("cache_write_5m_tokens", 0) or 0,
        "cacheWrite1hTokens": r.get("cache_write_1h_tokens", 0) or 0,
        "costUsd": r.get("cost_usd", 0.0),
        "costRaw": r.get("cost_raw", 0) or 0,
        "keyId": r.get("key_id"),
        "sessionId": r.get("session_id"),
        "plan": r.get("plan"),
        "localDate": r.get("local_date"),
        "accountId": r.get("account_id", fallback_account_id),
    }


def export_backup(path: str) -> int:
    """导出 gzip JSON 备份 (账号不含凭证 + 全部用量记录), 返回记录条数.

    只导出已登录账号: 未登录占位行 (如种子 Default) 没有数据也没有可迁移
    的凭证, 且其 workspace 常与真实账号相同, 会被导入端的 (provider,
    workspace_id) 去重抢先匹配导致记录错归账号。

    **流式写出**: 逐账号、逐页 (keyset 游标) 取数, 每页序列化后立即写盘, 峰值
    内存只与 EXPORT_PAGE 有关, 不随全库行数增长. 旧实现先把 16 键 dict 全堆进
    list 再整串 json.dumps (两份完整副本), 20 万行实测峰值 340MB; 而
    window_days=None 是合法配置, 100 万行会到 ~1.8GB —— 备份导出这台机器上
    最可能 OOM 的路径.

    输出与旧实现**逐字节一致** (同一份数据 + 同一 exportedAt 时刻): 头部由
    json.dumps 生成后截掉收尾 '}' 再续写 records 数组, 页间用 ", " 连接,
    因此键顺序/分隔符/ensure_ascii=False 全部继承 json.dumps 的默认行为,
    不存在"手写 JSON 文本与 dumps 漂移"的风险. 落盘走同目录 .tmp + 原子替换,
    失败时目标路径保持原样 (与旧的"最后一次性落盘"语义一致).
    """
    accounts = [
        {
            "id": a["id"],
            "name": a.get("name") or "",
            "workspaceId": a.get("workspace_id") or "",
            "provider": a.get("provider") or db.PROVIDER_OPENCODE,
            "hasToken": bool(a.get("has_token")),
        }
        for a in _logged_in_accounts()
    ]
    exported_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # head[:-1] 去掉 json.dumps 收尾的 '}': 紧随其后补 ", \"records\": [" 即与
    # 旧实现 dumps 整个 body 的文本完全相同 (accounts 是最后一个键)
    head = json.dumps(
        {"app": "GoGauge", "version": 1, "exportedAt": exported_at, "accounts": accounts},
        ensure_ascii=False,
    )
    written = 0
    # 先写同目录临时文件, 成功后 os.replace 原子顶上目标路径. 旧实现是"先全部
    # 物化、最后一次性 open(path)" —— 中途失败时目标文件根本没被碰过 (覆盖导出时
    # 上一份好备份原样保留). 流式必须提前开文件, 若直接写 path, 中途失败会留下
    # 半截 .gz 并顶掉旧备份; 用临时文件 + 原子替换可以完全复现旧实现的失败语义
    # (目标路径要么是完整的新备份, 要么保持原样), 代价只是同目录多一个 .tmp 名字
    # (进程被 SIGKILL 时可能残留, 不影响导入).
    tmp_path = f"{path}.tmp"
    try:
        with gzip.open(tmp_path, "wb", compresslevel=6) as fh:
            fh.write(head[:-1].encode("utf-8"))
            fh.write(b', "records": [')
            for acc in accounts:
                after: tuple[str, str] | None = None
                while True:
                    page = db.export_page(EXPORT_PAGE, account_id=acc["id"], after=after)
                    if not page:
                        break
                    # 一页一次 dumps (走 C 序列化器, 逐条 dumps 会慢 20%+), 内存
                    # O(EXPORT_PAGE); 去掉外层方括号后与整体 dumps 的 records
                    # 数组文本完全一致, 页间用 ", " 连接
                    page_json = json.dumps(
                        [_record_payload(r, acc["id"]) for r in page], ensure_ascii=False
                    )
                    fh.write(((", " if written else "") + page_json[1:-1]).encode("utf-8"))
                    written += len(page)
                    if len(page) < EXPORT_PAGE:
                        break
                    after = (page[-1]["created_at"], page[-1]["usg_id"])
            fh.write(b"]}")
        # 覆盖导出时沿用目标文件原有权限位: 旧实现就地截断写会保留 inode 与权限,
        # 而 os.replace 是"按 umask 新建后替换", 会把用户手工收紧过的 0600 备份
        # 放宽成 0644. 只处理常规文件 (符号链接会被 replace 替换掉, 不额外分支).
        try:
            if os.path.exists(path) and not os.path.islink(path):
                os.chmod(tmp_path, stat.S_IMODE(os.stat(path).st_mode))
        except OSError:
            pass  # 权限沿用失败不影响备份内容
        os.replace(tmp_path, path)
    except Exception:
        # 失败时清掉半截临时文件 (目标路径不动, 与旧实现一致)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    return written


MAX_IMPORT_BYTES = 512 * 1024 * 1024  # 解压后 512 MiB 上限 (见 _read_gzip_capped)


def _read_gzip_capped(path: str, limit: int = MAX_IMPORT_BYTES) -> bytes:
    """读取 gzip 内容并对**解压后**体积设上限.

    gzip.open().read() 是无界的: 归档声明的压缩体积只有几 MB, 展开可达数 GB,
    直接把进程 OOM 掉 (MemoryError 还没被捕获). 这里分块读, 越限即中止.
    """
    with gzip.open(path, "rb") as fh:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise ValueError(
                    f"备份文件解压后超过 {limit // (1024 * 1024)} MiB, 已中止导入"
                )
            chunks.append(chunk)
    return b"".join(chunks)


def import_backup(path: str) -> dict[str, Any]:
    """导入 gzip JSON 备份并合并.

    - 记录按 (account_id, usg_id) 幂等 upsert (insert_usage_records 内部已处理);
    - 账号按 (provider, workspace_id) 去重, 已存在则记录映射到现有账号,
      否则重建空 token 占位行 (凭证不可迁移, 需重新登录) 并恢复备份中的名称.
    """
    body = json.loads(_read_gzip_capped(path).decode("utf-8"))
    if not isinstance(body, dict) or body.get("app") != "GoGauge":
        raise ValueError("不是有效的 GoGauge 备份文件")
    accounts = body.get("accounts") or []
    records = body.get("records") or []

    accounts_added = 0
    accounts_skipped = 0
    id_remap: dict[int, int] = {}
    # 去重仅在已登录账号间匹配: 未登录占位行 (种子 Default) 没有数据可映射,
    # 与真实账号同 workspace 时会抢走映射 (见 export_backup 说明)
    logged_in = _logged_in_accounts()
    for acc in accounts:
        provider = acc.get("provider") or db.PROVIDER_OPENCODE
        workspace = acc.get("workspaceId") or ""
        existing = next(
            (
                a
                for a in logged_in
                if a.get("provider") == provider and a.get("workspace_id") == workspace
            ),
            None,
        )
        if existing is not None:
            id_remap[int(acc.get("id") or 0)] = int(existing["id"])
            accounts_skipped += 1
        else:
            new_id = db.add_account("", workspace, switch=False, provider=provider)
            if acc.get("name"):
                db.rename_account(new_id, str(acc["name"]))
            id_remap[int(acc.get("id") or 0)] = new_id
            accounts_added += 1

    records_added = 0
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Android 备份无 synced_at 字段: 桌面 insert_usage_records 接受 db dict 形态
    for i in range(0, len(records), EXPORT_PAGE):
        chunk = records[i : i + EXPORT_PAGE]
        entities = []
        default_aid = 1
        for r in chunk:
            usg_id = r.get("usgId")
            created_at = r.get("createdAt") or ""
            # 缺主键/时间的记录无法入库 (local_date 由 created_at 派生), 跳过防脏行
            if not usg_id or not created_at:
                continue
            # accountId 无法映射 (指向备份中不存在的账号, 手改/损坏文件): 跳过,
            # 不再回退写入账号 1 —— 那可能是不相干账号, 造成记录错归
            mapped = id_remap.get(int(r.get("accountId") or 0))
            if mapped is None:
                continue
            entities.append(
                {
                    "usg_id": usg_id,
                    "created_at": created_at,
                    "model": r.get("model") or "",
                    "provider": r.get("provider"),
                    "input_tokens": r.get("inputTokens", 0),
                    "output_tokens": r.get("outputTokens", 0),
                    "reasoning_tokens": r.get("reasoningTokens", 0),
                    "cache_read_tokens": r.get("cacheReadTokens", 0),
                    "cache_write_5m_tokens": r.get("cacheWrite5mTokens", 0) or 0,
                    "cache_write_1h_tokens": r.get("cacheWrite1hTokens", 0) or 0,
                    "cost_usd": r.get("costUsd", 0.0),
                    "cost_raw": r.get("costRaw", 0) or 0,
                    "key_id": r.get("keyId"),
                    "session_id": r.get("sessionId"),
                    "plan": r.get("plan"),
                    "synced_at": now_iso,
                    "account_id": mapped,
                }
            )
            default_aid = mapped
        records_added += db.insert_usage_records(entities, default_aid)
    return {"accounts_added": accounts_added, "records_added": records_added, "accounts_skipped": accounts_skipped}
