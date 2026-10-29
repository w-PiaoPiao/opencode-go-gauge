"""CSV / JSON 备份导出导入 (v2.2.0b) — Android 端 BackupManager.kt 的桌面 parity.

备份文件格式与 Android 端完全一致 (字段名对齐): 两端导出的 .json.gz 可互相导入。
凭证不可迁移 (桌面端 DPAPI/钥匙串加密, Android 端 Keystore 加密, 均无法跨设备
解密): 导入只重建空账号行, 用户重新登录后历史记录即可复用。

2.2.2 数据完整性修复 (审查报告 BK-1~BK-4 / P2-2):
- 导出账号集合 = **全部账号** (含无 token 占位行): 占位行可能有导入恢复的记录,
  只导出已登录账号会让这些数据在下次导出时静默消失; 每个账号附稳定
  ``accountKey = provider:workspaceId:name`` (格式 version 仍为 1, 旧备份无该
  字段也兼容), 供导入端跨机精确匹配。
- 导入: 先**全量校验** (结构/类型/时间戳/账号数上限) 再单事务写入; 失败抛
  ``ValueError`` 且不写任何东西。账号匹配保证"每个本地账号在一次导入中最多被
  匹配一次", 未匹配的按 2/3 的字段规范化重建占位行 —— 重复导入同一文件幂等。
- 导出走同目录 ``mkstemp``(0600) + ``os.replace`` 原子替换 + ``BEGIN`` 只读快照;
  CSV 做 OWASP 公式注入转义并同样原子写。
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import sqlite3
import stat
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Iterator

from . import db

EXPORT_PAGE = 1000

# 导入上限 (报告 BK-2): 账号数无上限时一个构造文件能一次建出几百个占位行;
# records 上限在解压体积上限 (512 MiB) 之外再给条数约束, 防深嵌套/超长数组.
MAX_IMPORT_ACCOUNTS = 200
MAX_IMPORT_RECORDS = 1_000_000
_SQLITE_INT_MAX = 2**63 - 1

# N4: 导入持写锁的时间与行数成正比 (200k 行 ≈ 4s, 上限 1M 行 ≈ 20s), 而其它
# SQLite 连接 (同步/后台配额) 的 busy_timeout 只有 15s —— 导入期间后台同步写会
# "database is locked" (表现为同步失败/partial). 三重防护:
#   (a) 导入连接的 busy_timeout 提到 60s: 导入自己等别人可以久一点;
#   (b) `_importing` 维护态标志: server 的同步入口 (路由 + 后台 worker) 见到它
#       直接拒绝/跳过, 不去排队等锁;
#   (c) `_import_gate` 非阻塞互斥: 禁止两个导入同时持锁 (否则互相等 60s).
# 标志必须在 finally 清理 (含异常/rollback 路径), 否则同步会永久被拒.
_importing = threading.Event()
_import_gate = threading.Lock()

# 导入连接等待写锁的上限 (ms); 其它连接保持默认 15s 不动
_IMPORT_BUSY_TIMEOUT_MS = 60_000


def is_importing() -> bool:
    """是否有备份导入正持有/即将持有写锁 (server 同步入口据此拒绝新同步)."""
    return _importing.is_set()

CSV_HEADER = [
    "created_at", "model", "provider", "input_tokens", "output_tokens",
    "reasoning_tokens", "cache_read_tokens", "cache_write_5m_tokens",
    "cache_write_1h_tokens", "cost_usd", "session_id", "key_id", "plan", "account_id",
]

# OWASP CSV Injection: Excel/LibreOffice 会把以这些字符开头的单元格当公式执行.
# 数据可来自"导入的备份" (model/session_id/key_id/plan 完全由文件内容决定),
# 形成 "导入恶意备份 → 导出 CSV → Excel 打开" 的注入链.
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


# ---------------------------------------------------------------------------
# 账号序列化 / 匹配键
# ---------------------------------------------------------------------------


def _account_key(acc: dict[str, Any]) -> str:
    """账号的稳定匹配键: provider:workspaceId:name (I12).

    导出端写进备份的 ``accountKey``, 导入端用同样公式计算本地账号的键做精确
    匹配 —— 两端算法必须一致, 否则跨机恢复会退化成按名字/顺序猜。
    """
    provider = acc.get("provider") or db.PROVIDER_OPENCODE
    return f"{provider}:{acc.get('workspace_id') or ''}:{acc.get('name') or ''}"


def _account_export_entry(acc: dict[str, Any]) -> dict[str, Any]:
    """单个账号的备份序列化形态 (Android parity; 新增字段只可追加)."""
    return {
        "id": acc["id"],
        "name": acc.get("name") or "",
        "workspaceId": acc.get("workspace_id") or "",
        "provider": acc.get("provider") or db.PROVIDER_OPENCODE,
        "hasToken": bool(acc.get("has_token")),
        # 稳定键: 供导入端精确匹配 (旧备份无此字段 → 回退 (provider, ws, name))
        "accountKey": _account_key(acc),
    }


def _all_accounts() -> list[dict[str, Any]]:
    """导出/导入使用的账号集合: **全部账号** (含无 token 占位行).

    此前只用 has_token 的账号: 导入恢复出来的占位行 (无 token) 记录既进不了
    界面, 也不会被下一次备份导出 —— 每次导出/导入循环都静默丢数据 (BK-1C).
    """
    return db.list_accounts()


# ---------------------------------------------------------------------------
# 原子落盘 / 只读快照
# ---------------------------------------------------------------------------


@contextmanager
def _read_snapshot() -> Iterator[None]:
    """导出期间的只读事务快照 (WAL 下不阻塞写).

    keyset 分页由多条独立 SELECT 组成; 没有跨页快照时, 导出期间的并发回填
    (登录后的全量同步、另一进程的导入) 会落在已越过的游标之后, 备份静默少行
    (审查实测 DB 3001 行 / 备份 3000 行). 只对**当前线程**连接生效, 而导出本来
    就在请求线程内完成, 所以 export_page 的 get_db() 命中的是同一个快照.
    """
    conn = db.get_db()
    started = False
    try:
        conn.execute("BEGIN")
        started = True
    except sqlite3.OperationalError:
        # 已有外层事务: 复用 (不重复 BEGIN, 也不替调用方提交/回滚)
        pass
    try:
        yield
    finally:
        if started:
            try:
                conn.execute("ROLLBACK")  # 只读快照: 回滚即释放, 无副作用
            except sqlite3.Error:
                pass


def _replace_atomically(
    path: str,
    writer: Callable[[Any], None],
    mode: str = "wb",
    encoding: str | None = None,
    newline: str | None = None,
) -> None:
    """在目标同目录写临时文件, 成功后 ``os.replace`` 原子顶上目标.

    旧实现 ``export_backup`` 用可预测的 ``<path>.tmp`` 且 ``gzip.open`` 跟随
    软链接 (可被预置软链把内容写进受害者文件); 新文件按 umask 建成 0644 而 DB
    是 0600. ``mkstemp`` 自带 ``O_CREAT|O_EXCL`` 且初始 0600, 软链/同名文件
    覆盖与权限外泄一并消失; 失败时目标路径保持原样 (旧备份不被半截文件毁掉).
    """
    target_dir = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".gogauge-", suffix=".tmp")
    try:
        kwargs: dict[str, Any] = {} if encoding is None else {"encoding": encoding}
        if newline is not None:
            kwargs["newline"] = newline
        with os.fdopen(fd, mode, **kwargs) as fh:
            writer(fh)
        # 覆盖导出沿用目标文件原有权限位 (旧实现就地截断写会保留 inode/权限,
        # 不沿用会把用户手工收紧过的 0600 备份放宽成 0644); 新文件保持 mkstemp
        # 的 0600. 只处理常规文件 (符号链接会被 replace 替换掉, 不额外分支).
        try:
            if os.path.exists(path) and not os.path.islink(path):
                os.chmod(tmp_path, stat.S_IMODE(os.stat(path).st_mode))
            else:
                os.chmod(tmp_path, 0o600)
        except OSError:
            pass  # 权限设置失败不影响备份内容 (Windows 无 POSIX 权限位)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)  # 清掉半截临时文件; 目标路径不动
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CSV 导出
# ---------------------------------------------------------------------------


def _csv_cell(value: Any) -> Any:
    """OWASP 公式注入转义: 文本首字符为 = + - @ TAB CR 时前缀单引号."""
    if isinstance(value, str) and value[:1] in _CSV_FORMULA_PREFIXES:
        return "'" + value
    return value


def export_csv(path: str) -> int:
    """导出全部账号的用量明细为 CSV, 返回写出行数.

    - 账号集合是**全部账号** (占位行也可能有导入恢复的记录, 只导已登录会丢);
    - 单元格做公式注入转义 (OWASP; 数据可来自导入的备份);
    - 写入走临时文件 + 原子替换, 失败时上一份导出原样保留.
    """
    rows_written = 0

    def _write(fh: Any) -> None:
        nonlocal rows_written
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        with _read_snapshot():
            for acc in _all_accounts():
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
                            _csv_cell(r.get("created_at", "")),
                            _csv_cell(r.get("model", "")),
                            _csv_cell(r.get("provider") or ""),
                            r.get("input_tokens", 0), r.get("output_tokens", 0),
                            r.get("reasoning_tokens", 0), r.get("cache_read_tokens", 0),
                            r.get("cache_write_5m_tokens", 0) or 0,
                            r.get("cache_write_1h_tokens", 0) or 0,
                            r.get("cost_usd", 0.0),
                            _csv_cell(r.get("session_id") or ""),
                            _csv_cell(r.get("key_id") or ""),
                            _csv_cell(r.get("plan") or ""),
                            r.get("account_id", acc["id"]),
                        ])
                    rows_written += len(page)
                    if len(page) < EXPORT_PAGE:
                        break
                    after = (page[-1]["created_at"], page[-1]["usg_id"])

    # newline="": csv 模块自己写行终止符; 不设的话 Windows 文本模式会把 "\n"
    # 再翻译成 "\r\n", 得到 "...\r\r\n" 的坏行
    _replace_atomically(path, _write, mode="w", encoding="utf-8-sig", newline="")
    return rows_written


# ---------------------------------------------------------------------------
# JSON 备份导出
# ---------------------------------------------------------------------------


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

    账号集合是**全部账号** (含无 token 占位行): 占位行可能持有导入恢复的记录,
    只导已登录账号会让它们在下一次导出时静默消失; 每个账号额外写
    ``accountKey`` 供跨机精确匹配 (格式 version 仍为 1).

    **流式写出**: 逐账号、逐页 (keyset 游标) 取数, 每页序列化后立即写盘, 峰值
    内存只与 EXPORT_PAGE 有关, 不随全库行数增长. 输出与旧实现**逐字节一致**
    (同一份数据 + 同一 exportedAt 时刻): 头部由 json.dumps 生成后截掉收尾 '}'
    再续写 records 数组, 页间用 ", " 连接, 因此键顺序/分隔符/ensure_ascii=False
    全部继承 json.dumps 的默认行为, 不存在"手写 JSON 文本与 dumps 漂移"的风险.
    落盘走同目录 mkstemp + 原子替换, 失败时目标路径保持原样.
    """
    written = 0
    exported_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _write(fh: Any) -> None:
        nonlocal written
        # 读快照必须在写文件前开启, 并覆盖全部 export_page 调用 (跨页一致)
        accounts = [_account_export_entry(a) for a in _all_accounts()]
        # head[:-1] 去掉 json.dumps 收尾的 '}': 紧随其后补 ", \"records\": [" 即与
        # dumps 整个 body 的文本完全相同 (accounts 是最后一个键)
        head = json.dumps(
            {"app": "GoGauge", "version": 1, "exportedAt": exported_at, "accounts": accounts},
            ensure_ascii=False,
        )
        with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=6) as gz:
            gz.write(head[:-1].encode("utf-8"))
            gz.write(b', "records": [')
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
                    gz.write(((", " if written else "") + page_json[1:-1]).encode("utf-8"))
                    written += len(page)
                    if len(page) < EXPORT_PAGE:
                        break
                    after = (page[-1]["created_at"], page[-1]["usg_id"])
            gz.write(b"]}")

    def _write_in_snapshot(fh: Any) -> None:
        # 快照只对当前线程连接有效, 所以必须在写盘线程/上下文里开启 (导出本来
        # 就在请求线程内同步完成)
        with _read_snapshot():
            _write(fh)

    _replace_atomically(path, _write_in_snapshot, mode="wb")
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


# ---------------------------------------------------------------------------
# 导入: 预校验 (纯函数, 不写库)
# ---------------------------------------------------------------------------


def _as_dict_list(value: Any, field: str) -> list[dict[str, Any]]:
    """校验 JSON 数组且元素为对象 (此前非 list 会裸抛 AttributeError/TypeError)."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"备份文件字段损坏: {field} 必须是数组")
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"备份文件字段损坏: {field} 的数组元素必须是对象")
        out.append(item)
    return out


def _as_int(
    value: Any,
    field: str,
    *,
    minimum: int = 0,
    maximum: int = _SQLITE_INT_MAX,
) -> int:
    """严格整数校验: 拒绝 bool/字符串/非整浮点/超 SQLite 64 位范围.

    此前 ``int(r.get("accountId"))`` 对字符串抛 ValueError、超大整数在 sqlite3
    绑定时抛 OverflowError, 且都发生在部分 chunk 已 commit 之后 (BK-2).
    """
    if isinstance(value, bool):
        raise ValueError(f"备份文件字段损坏: {field} 必须是整数")
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    else:
        raise ValueError(f"备份文件字段损坏: {field} 必须是整数")
    if number < minimum or number > maximum:
        raise ValueError(f"备份文件字段损坏: {field} 超出允许范围")
    return number


def _as_number(value: Any, field: str) -> float:
    """严格非负数校验: 拒绝 bool/字符串/NaN/Infinity/负数/超大数.

    N1: JSON 可解析出任意精度的整数 (如 ``10**400``), ``float()`` 对它抛
    OverflowError 而不是 ValueError —— 若不在这里归一成 ValueError, 路由会把
    用户输入错误映射成 500 (虽然仍零写入). 校验阶段必须全 ValueError.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"备份文件字段损坏: {field} 必须是数字")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"备份文件字段损坏: {field} 超出允许范围") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"备份文件字段损坏: {field} 超出允许范围")
    return number


def _as_optional_text(value: Any, field: str, max_len: int = 500) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"备份文件字段损坏: {field} 必须是字符串")
    if len(value) > max_len:
        raise ValueError(f"备份文件字段损坏: {field} 过长")
    return value


def _parse_created_at(value: Any, field: str) -> str:
    """校验 createdAt 可解析 (保留原字符串入库).

    不可解析的时间戳会让 local_date 为 NULL: 明细窗口/趋势/prune 都看不到该行,
    但 totals("all") 仍计入 → 同一份数据两套口径 (review 实测 3 vs 2).
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"备份文件字段损坏: {field} 缺失或非法")
    raw = value.strip()
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"备份文件字段损坏: {field} 不是可解析的时间") from exc
    return raw


def _normalize_backup_account(acc: dict[str, Any], index: int) -> dict[str, Any]:
    """备份账号字段规范化 (provider/workspace/name 与本地 add_account 口径一致)."""
    raw_id = acc.get("id")
    if raw_id is None:
        raise ValueError(f"备份文件字段损坏: accounts[{index}].id 缺失")
    backup_id = _as_int(raw_id, f"accounts[{index}].id", minimum=1)

    provider_raw = acc.get("provider")
    if provider_raw is None:
        provider = db.PROVIDER_OPENCODE
    elif isinstance(provider_raw, str):
        provider = provider_raw.strip().lower() or db.PROVIDER_OPENCODE
    else:
        raise ValueError(f"备份文件字段损坏: accounts[{index}].provider 必须是字符串")
    if provider not in db.ALL_PROVIDERS:
        # 旧备份/手写文件里的未知来源: 归一到默认 provider (不丢账号数据)
        provider = db.PROVIDER_OPENCODE

    workspace_raw = acc.get("workspaceId")
    if workspace_raw is None:
        workspace = ""
    elif isinstance(workspace_raw, str):
        workspace = workspace_raw.strip()
    else:
        raise ValueError(f"备份文件字段损坏: accounts[{index}].workspaceId 必须是字符串")

    name_raw = acc.get("name")
    if name_raw is None:
        name = ""
    elif isinstance(name_raw, str):
        name = name_raw.strip()[:50]  # db.rename_account/add_account 名称上限 50
    else:
        raise ValueError(f"备份文件字段损坏: accounts[{index}].name 必须是字符串")

    key_raw = acc.get("accountKey")
    if key_raw is None:
        account_key = ""
    elif isinstance(key_raw, str):
        account_key = key_raw.strip()
    else:
        raise ValueError(f"备份文件字段损坏: accounts[{index}].accountKey 必须是字符串")

    return {
        "id": backup_id,
        "provider": provider,
        "workspace": workspace,
        "name": name,
        "accountKey": account_key,
    }


def _local_account_key(acc: dict[str, Any]) -> str:
    """与导出端同公式的本地账号键 (用于 accountKey 精确匹配)."""
    return f"{acc.get('provider') or db.PROVIDER_OPENCODE}:{acc.get('workspace_id') or ''}:{acc.get('name') or ''}"


def _plan_account_mapping(
    file_accounts: list[dict[str, Any]],
    local_accounts: list[dict[str, Any]],
) -> tuple[dict[int, int], list[dict[str, Any]], int]:
    """I12 账号匹配计划: 返回 (备份 id → 本地 id, 待创建账号, 已匹配数).

    匹配顺序 (每个本地账号在一次导入中最多被匹配一次):
      1. ``accountKey`` 精确 (导出的稳定键);
      2. ``(provider, workspaceId, name)`` 精确;
      3. 唯一一个同 ``(provider, workspaceId)`` 且本文件尚未匹配过的账号;
      4. 否则创建占位行 (字段按 2/3 规范化, 保证重复导入幂等).
    """
    remap: dict[int, int] = {}
    matched_ids: set[int] = set()
    to_create: list[dict[str, Any]] = []
    matched = 0

    def _find(predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any] | None:
        for local in local_accounts:
            if local["id"] in matched_ids:
                continue
            if predicate(local):
                return local
        return None

    for acc in file_accounts:
        target: dict[str, Any] | None = None
        if acc["accountKey"]:
            target = _find(lambda local: _local_account_key(local) == acc["accountKey"])
        if target is None and acc["name"]:
            target = _find(
                lambda local: (
                    (local.get("provider") or db.PROVIDER_OPENCODE) == acc["provider"]
                    and (local.get("workspace_id") or "") == acc["workspace"]
                    and (local.get("name") or "") == acc["name"]
                )
            )
        if target is None:
            candidates = [
                local
                for local in local_accounts
                if local["id"] not in matched_ids
                and (local.get("provider") or db.PROVIDER_OPENCODE) == acc["provider"]
                and (local.get("workspace_id") or "") == acc["workspace"]
            ]
            if len(candidates) == 1:
                target = candidates[0]
        if target is not None:
            remap[acc["id"]] = int(target["id"])
            matched_ids.add(int(target["id"]))
            matched += 1
        else:
            to_create.append(acc)
    return remap, to_create, matched


def _record_entity(
    rec: dict[str, Any],
    index: int,
    remap: dict[int, int],
    pending_ids: set[int],
) -> dict[str, Any] | None:
    """校验并规范化单条记录; 指向备份中不存在账号的记录返回 None (跳过).

    ``pending_ids`` 是待创建占位行的备份 id 集合: 预校验时允许它们暂时没有
    本地 id, 真正写库前 remap 已补齐. 指向未知账号的记录沿用旧语义跳过 (不再
    回退写入账号 1 —— 那可能是不相干账号, 造成记录错归).
    """
    prefix = f"records[{index}]"
    usg_id = rec.get("usgId")
    if not isinstance(usg_id, str) or not usg_id.strip():
        raise ValueError(f"备份文件字段损坏: {prefix}.usgId 缺失或非法")
    usg_id = usg_id.strip()
    if len(usg_id) > 500:
        raise ValueError(f"备份文件字段损坏: {prefix}.usgId 过长")
    created_at = _parse_created_at(rec.get("createdAt"), f"{prefix}.createdAt")

    raw_aid = rec.get("accountId")
    if raw_aid is None:
        return None
    aid = _as_int(raw_aid, f"{prefix}.accountId", minimum=1)
    if aid in remap:
        mapped = remap[aid]
    elif aid in pending_ids:
        mapped = -aid  # 占位行待创建 (负哨兵, 写库前替换)
    else:
        return None

    model = rec.get("model")
    if model is None:
        model = ""
    elif not isinstance(model, str):
        raise ValueError(f"备份文件字段损坏: {prefix}.model 必须是字符串")

    provider = rec.get("provider")
    if provider is not None and not isinstance(provider, str):
        raise ValueError(f"备份文件字段损坏: {prefix}.provider 必须是字符串")

    def _int_field(key: str, default: int = 0) -> int:
        value = rec.get(key)
        if value is None:
            return default
        return _as_int(value, f"{prefix}.{key}")

    cost_usd_raw = rec.get("costUsd")
    cost_usd = 0.0 if cost_usd_raw is None else _as_number(cost_usd_raw, f"{prefix}.costUsd")
    cost_raw = _int_field("costRaw")

    return {
        "usg_id": usg_id,
        "created_at": created_at,
        "model": model,
        "provider": provider,
        "input_tokens": _int_field("inputTokens"),
        "output_tokens": _int_field("outputTokens"),
        "reasoning_tokens": _int_field("reasoningTokens"),
        "cache_read_tokens": _int_field("cacheReadTokens"),
        "cache_write_5m_tokens": _int_field("cacheWrite5mTokens"),
        "cache_write_1h_tokens": _int_field("cacheWrite1hTokens"),
        "cost_usd": cost_usd,
        "cost_raw": cost_raw,
        "key_id": _as_optional_text(rec.get("keyId"), f"{prefix}.keyId"),
        "session_id": _as_optional_text(rec.get("sessionId"), f"{prefix}.sessionId"),
        "plan": _as_optional_text(rec.get("plan"), f"{prefix}.plan"),
        "account_id": mapped,
    }


def import_backup(path: str) -> dict[str, Any]:
    """导入 gzip JSON 备份并合并 (先全量校验、再单事务写入).

    - 记录按 (account_id, usg_id) 幂等 upsert;
    - 账号按 I12 顺序匹配, 每个本地账号本次最多匹配一次, 未匹配的建空 token
      占位行 (凭证不可迁移, 需重新登录) 并按备份字段规范化;
    - 重复导入同一文件 → 账号数/记录数不变 (幂等);
    - 任何校验失败 → ``ValueError`` (路由映射 400) 且**不写任何东西**;
      写入阶段失败 → rollback (账号创建与记录写入在同一事务内).
    """
    try:
        raw = _read_gzip_capped(path)
    except ValueError:
        raise  # 解压体积超限等已带可读文案
    except (OSError, EOFError) as exc:
        # 非 gzip / 读取失败属于"用户选错文件"一类: 400 具体原因, 不是 500 内部错误
        raise ValueError("备份文件无法读取, 不是有效的 .json.gz 备份") from exc
    try:
        body = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("备份文件不是有效的 JSON") from exc

    if not isinstance(body, dict) or body.get("app") != "GoGauge":
        raise ValueError("不是有效的 GoGauge 备份文件")
    version = body.get("version")
    if version is not None and version != 1:
        raise ValueError("备份文件版本不受支持")

    raw_accounts = _as_dict_list(body.get("accounts"), "accounts")
    raw_records = _as_dict_list(body.get("records"), "records")
    if len(raw_accounts) > MAX_IMPORT_ACCOUNTS:
        raise ValueError(f"备份账号数超过上限 ({MAX_IMPORT_ACCOUNTS})")
    if len(raw_records) > MAX_IMPORT_RECORDS:
        raise ValueError(f"备份记录数超过上限 ({MAX_IMPORT_RECORDS})")

    file_accounts = [
        _normalize_backup_account(acc, i) for i, acc in enumerate(raw_accounts)
    ]
    seen_ids: set[int] = set()
    for acc in file_accounts:
        if acc["id"] in seen_ids:
            raise ValueError(f"备份文件字段损坏: accounts 中 id {acc['id']} 重复")
        seen_ids.add(acc["id"])

    local_accounts = _all_accounts()
    remap, to_create, matched = _plan_account_mapping(file_accounts, local_accounts)
    if len(local_accounts) + len(to_create) > MAX_IMPORT_ACCOUNTS:
        raise ValueError(f"导入后账号数会超过上限 ({MAX_IMPORT_ACCOUNTS})")

    # ---- 全量校验: 逐条记录检查类型/时间戳/账号可映射 (纯计算, 不写库) ----
    pending_ids = {acc["id"] for acc in to_create}
    for index, rec in enumerate(raw_records):
        _record_entity(rec, index, remap, pending_ids)

    # ---- 单事务写入: 账号创建 + 记录写入 必须一起提交/一起回滚 ----
    # N4: 导入持写锁的时间与记录数成正比 (200k 行 ≈ 4s, 上限 1M 行 ≈ 20s), 超过
    # 其它连接 15s 的 busy_timeout. 因此进入写事务前: 非阻塞互斥禁止并发导入 +
    # 打开维护态标志 (server 的同步入口据此拒绝/跳过, 见 app/server.py 的
    # backup.is_importing() 检查) + 抬高本连接 busy_timeout. finally 兜底清理,
    # 异常/rollback 路径不得残留维护态 (否则同步会一直被拒).
    if not _import_gate.acquire(blocking=False):
        raise ValueError("已有导入任务进行中, 请稍后重试")
    _importing.set()
    conn: sqlite3.Connection | None = None
    prev_busy_timeout: int | None = None
    try:
        conn = db.get_db()
        try:
            prev_busy_timeout = int(
                conn.execute("PRAGMA busy_timeout").fetchone()[0]
            )
            conn.execute(f"PRAGMA busy_timeout = {_IMPORT_BUSY_TIMEOUT_MS}")
        except sqlite3.Error:
            prev_busy_timeout = None  # PRAGMA 失败不阻塞导入 (默认 15s 仍可用)

        started = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            started = True
        except sqlite3.OperationalError:
            pass  # 调用方已开事务: 复用之, 不越权提交
        try:
            accounts_added = 0
            accounts_skipped = matched
            existing_ids = {int(a["id"]) for a in local_accounts}
            for acc in to_create:
                local_id = db.add_account(
                    "",
                    acc["workspace"],
                    switch=False,
                    provider=acc["provider"],
                    name=(acc["name"] or None),
                    commit=False,
                )
                remap[acc["id"]] = int(local_id)
                if int(local_id) in existing_ids:
                    # DB 层 (provider, workspace, name) 去重命中了既有占位行: 不算新增
                    accounts_skipped += 1
                else:
                    accounts_added += 1
                    existing_ids.add(int(local_id))

            records_added = 0
            batch: list[dict[str, Any]] = []
            for index, rec in enumerate(raw_records):
                entity = _record_entity(rec, index, remap, set())
                if entity is None:
                    continue
                if entity["account_id"] < 0:  # 理论上 remap 已补齐, 兜底防御
                    entity["account_id"] = remap[-entity["account_id"]]
                batch.append(entity)
                if len(batch) >= EXPORT_PAGE:
                    records_added += db.insert_usage_records(
                        batch, int(batch[0]["account_id"]), commit=False
                    )
                    batch = []
            if batch:
                records_added += db.insert_usage_records(
                    batch, int(batch[0]["account_id"]), commit=False
                )
            if started:
                conn.commit()
            # started=False 说明调用方已开事务: 不越权提交别人的事务, 由调用方提交
        except Exception:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise
    finally:
        if conn is not None and prev_busy_timeout is not None:
            try:
                conn.execute(f"PRAGMA busy_timeout = {int(prev_busy_timeout)}")
            except sqlite3.Error:
                pass
        _importing.clear()
        _import_gate.release()

    return {
        "accounts_added": accounts_added,
        "records_added": records_added,
        "accounts_skipped": accounts_skipped,
    }
