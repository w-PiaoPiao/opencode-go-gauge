# GoGauge 桌面版性能审查报告

> **审查对象**：桌面版（Windows / macOS）—— `app/*.py` + `app/web/*`，**不含** `android/` 与 `harmonyos/`
> **代码版本**：`90c4415`（GoGauge 2.2.1b）｜**审查日期**：2026-10-17
> **审查方式**：4 路并行审查（数据层 / HTTP·API 层 / 运行时与登录 / 前端）+ 1 路独立复核（逐条证伪与优先级校准）
> **结论可信度**：30 条裁决 = **确认 20 / 降级 8 / 证伪 2**；四组跨报告冲突全部给出唯一定论。所有数字均为可复跑实测；审查期间**仓库源码零改动**（`git status --porcelain` 为空）。

---

## 一、先回答你的问题

**有，但不在你现在能感觉到的地方。**

以本机真实库的只读快照（约 2.4 万条记录 / 13.8 MB）对照实测缩放曲线：

| 场景 | 你当前的实际耗时 | 判断 |
|---|---|---|
| 首页 dashboard 刷新 | 约 20–30 ms | 不卡 |
| 使用记录页（会话表） | 约 25 ms | 不卡 |
| 热力图 / 模型趋势 | 约 17 ms / 13 ms | 不卡 |

所以**现在没有需要救火的性能问题**。审查的价值在于两类问题：

### 1️⃣ 会随数据量线性劣化的结构性问题（真正的隐患）

所有统计接口**每次请求都从原始行重算聚合，零缓存**。实测拟合成一条直线：

```
单次聚合耗时 ≈ 10–14 ms + (1.0–1.4 µs × 窗口内行数)
```

关键结论（复核已证实）：**决定快慢的是「所选时间窗口内的行数」，不是库总行数**。同一份 20 万行的库：

| 窗口内行数 | 20 万 | 10.3 万 | 5.1 万 | 2.6 万 |
|---|---|---|---|---|
| `totals(30d)` | 207 ms | 126 ms | 69 ms | 39 ms |

按此推算：单账号窗口内行数到 **5 万**时 dashboard ≈ 60–80 ms；到 **20 万**时，HTTP 实测 `dashboard?today` = 274 ms、`30d` = 614 ms、统计页一次切换 ≈ 481 ms（三个串行请求）。

### 2️⃣ 与数据量无关的确定性浪费与缺陷（现在就存在）

- **导出是 O(N²)**：10 万行导出 6.9–7.4 s，20 万行 **34.8 s**（每页都做一次全表排序）。
- **每 5 分钟把整张 charts 表重写一遍**：43 万行时 430 ms + 9.8 MB WAL/次，其中 99% 是重复数据。
- **备份导出把全库堆进内存**：20 万行峰值 365 MB，`window_days=全部` 的用户有 OOM 风险。
- **macOS 登录轮询**：每秒 2.4 次无超时的跨线程主线程往返，超时线程不回收；点登录后最多 **20 秒**无反应（期间静默吞掉点击）。
- **托盘「今日用量」永远停在启动那一刻**（功能缺陷，不是性能）：菜单文本是常量，pystray 永不刷新。
- **退出被拖 3 秒**：`main.py:1151` 的 `threading.Timer` 没设 daemon，一个字的修复。
- **点「检查更新」最坏卡 51.2 秒**（两个来源 × 3 次重试 × 8 s 超时串行叠加）。

**如果只做三件事**：① `export_page` 加索引 + keyset 分页 ② dashboard 聚合加 11 列覆盖索引 ③ charts / records 的守卫 upsert。

---

## 二、优先级总表

| # | 优化项 | 实测收益 | 改动面 |
|:--:|---|---|---|
| 1 | `export_page` 加复合索引 + 改 keyset 分页 | 200k 行导出 **34.8 s → 0.69 s（50×）** | `db.py` + `backup.py` |
| 2 | dashboard 聚合加 **11 列覆盖索引** | today 274→65 ms、30d 614→230 ms、heatmap 228→45 ms、model_trend 222→26 ms；顺带修掉 `range=today` 规划器坏计划 | `db.py` 一处迁移 |
| 3 | `insert_usage_charts` 变更守卫 upsert | 每 5 分钟一次的全量重写 **430→188 ms**，未变行零页写（WAL 9.8 MB→0） | `db.py` 一条 SQL |
| 4 | `auth.py` macOS 分支补 `_bounded_call` + 复用本轮 URL | 主线程往返 2.4→1.2 次/秒；消除「点登录 ≤20 s 无反应」与线程泄漏 | `auth.py` |
| 5 | `session_stats_page` 单遍化（`COUNT(*) OVER ()`） | 每次翻页 233→171 ms（−27%）；带 days 时 415→250 ms（−40%） | `db.py` 一条 SQL |
| 6 | `insert_usage_records` 变更守卫 upsert | 1000 条已存在记录 52.5 ms/6.7 MB WAL → **8.1 ms/0 WAL**；每轮增量同步必命中 | `db.py` ~10 行 |
| 7 | 重复 dashboard 请求治理（前端防抖 + 服务端代数缓存） | 缓存命中 614 ms→**0.2 ms**；连点/快速切页服务端聚合 N→1 | `app.js` + `server.py` |
| 8 | `export_backup` 改流式写出 | 峰值内存 365 MB→O(页)；1M 行 ~1.8 GB→<10 MB | `backup.py` |

**次席（顺手做，未进 TOP 8）**

| 项 | 收益 |
|---|---|
| `main.py:1151` Timer 加 `daemon=True` | 退出延迟 **3027→28 ms**（一行） |
| `import_backup` 上限 512→128 MiB，少一份拷贝 | 峰值内存 ≈ 解压体积 4.43× |
| `/api/update/check` 异步化 | 最坏阻塞按钮 **51.2 s → ~0** |
| 托盘菜单文本改 callable | 修掉「数据永不刷新」的功能缺陷 |
| `list_models()` 并入数据代数缓存 | 记录页翻页 12.6→4.3 ms（−66%） |

---

## 三、TOP 8 详情

### 1. `export_page`：每页一次全表排序，导出随数据量超线性劣化

**位置**：`app/db.py:2357-2372`（`export_page`）；调用方 `app/backup.py:36-55`（CSV）、`app/backup.py:76-107`（备份）

**现状**：`ORDER BY created_at ASC, usg_id ASC LIMIT ? OFFSET ?`，但索引 `idx_usage_account_time` 只覆盖 `(account_id, created_at DESC)`。`EXPLAIN` 显示 `USE TEMP B-TREE FOR LAST TERM OF ORDER BY` —— 每一页都要把 OFFSET 之前的行全部喂进临时 B 树。页数 = N/1000，总成本 ≈ **O(N²/页大小)**。

**实测**（单账号 100k / 200k 行）

| 场景 | 现状 | 加索引 | 索引 + keyset |
|---|---|---|---|
| 100k 行导出循环 | 6.9–7.4 s | 0.57 s | **0.34 s** |
| 200k 行导出循环 | **34.8 s** | 1.52 s | **0.69 s** |

**改法**：迁移 6 索引块（`db.py:592-605`）与迁移 8 重建表分支（`db.py:670-677`）各补一条：

```sql
CREATE INDEX IF NOT EXISTS idx_usage_account_time_usgid
  ON usage_records(account_id, created_at, usg_id);
```

再把两个导出循环改为游标分页（`after = (page[-1]["created_at"], page[-1]["usg_id"])`），`export_page` 增加可选 `after` 参数、保留 `offset` 兼容。

**代价**：索引约 50 B/行 ≈ 5 MB/100k 行；写入 <2%。**风险低**：只改执行计划不改语义；注意迁移 8 分支必须同步补建，否则升级首启会漏。

---

### 2. dashboard 聚合加 11 列覆盖索引（并顺带修掉规划器坏计划）

**位置**：`app/db.py:1966`（`model_stats`）、`2043`（`daily_stats`）、`2148`（`model_daily_stats`）、`2224`（`today_trend`）、`2284`（`totals`）；索引定义在 `db.py:592-605`

**现状**：聚合走 `idx_usage_account_localdate(account_id, local_date)`，但 SELECT 需要 tokens/cost/model/session_id 等列，**每个命中行都要回表**；同一次 dashboard 里 5 条查询各扫同一批行、各回表一遍。

**另一个独立问题**：库内从未 `ANALYZE`（`sqlite_stat1` 为空），默认视图 `range=today` 的 `local_date = ?` 是**等值**谓词，规划器为省掉 `GROUP BY` 临时 B 树选了 `idx_usage_account_model`，等于**全账号扫描**。20 万行实测 91 ms → 加提示后 10.5 ms。

**实测（11 列覆盖索引，端到端 HTTP）**

| 接口 | 现状 | 加索引 |
|---|---|---|
| `dashboard?range=today` | 274 ms | **65 ms** |
| `dashboard?range=30d` | 614 ms | **230 ms** |
| `heatmap` | 228 ms | **45 ms** |
| `model_trend` | 222 ms | **26 ms** |

**改法**（一条迁移，且它同时解决坏计划，无需 `INDEXED BY`）：

```sql
CREATE INDEX IF NOT EXISTS idx_usage_cover_dash ON usage_records(
  account_id, local_date, model,
  input_tokens, output_tokens, reasoning_tokens,
  cache_read_tokens, cache_write_5m_tokens, cache_write_1h_tokens,
  cost_usd, session_id);
```

> ⚠️ **必须带 `session_id`**。初审给出的 10 列清单会让 3/8 条查询不变甚至变慢（`totals_today` 8.8→16.0 ms、`today_trend` 11.2→21.1 ms），因为它对这几条查询不是覆盖索引。

**代价**：+66.7 B/行 ≈ 库体积 +21%（你当前 13.8 MB 的库约 +2.9 MB）；批量写 +24%（折算到同步批 +0.1 ms/批，可忽略）。

**风险中低**：建索引在升级首启一次性发生（百万行约 3 s）。**不要与第 7 项的汇总表方案同时上**，写放大与体积会叠加。

---

### 3. `insert_usage_charts` 每 5 分钟重写整张表

**位置**：`app/db.py:1222-1275`；调用 `app/server.py:588-589`（每次 commandcode 同步，与增量/全量无关）

**现状**：commandcode 返回整个计费周期的「模型 × 时间桶」聚合行，代码不做差异比较直接整批 UPSERT，且 `DO UPDATE` 更新全部列含 `synced_at` → **每行都算“有变化”**，SQLite 逐行写页并维护 PK + 3 个索引。

**实测**：43 万行时 **430 ms + 9.8 MB WAL/次**（每 5 分钟一次）；加变更守卫后 **188 ms，未变行零页写、WAL→0**。

**改法**：`DO UPDATE ... WHERE` 值列有变化才写。**这里有一个真实陷阱（复核发现初审改法有语义 bug）**：

```sql
ON CONFLICT(account_id, model, time_bucket) DO UPDATE SET
  provider=excluded.provider, requests=excluded.requests, ... ,  -- 全部值列
  synced_at=excluded.synced_at                                    -- 必须保留！
WHERE usage_charts.requests IS NOT excluded.requests
   OR usage_charts.total_cost IS NOT excluded.total_cost
   OR ...                                                          -- 必须覆盖全部 12 个值列
```

- SET 里**去掉 `synced_at`** → `_charts_last_synced()`（`db.py:1318` 读 `MAX(synced_at)`）会**永久冻结**，界面「聚合同步于 X」不再更新；
- WHERE 只盖 3 列 → **静默丢弃其余 9 个值列的更新**。

按正确写法无需改展示侧。

---

### 4. `auth.py` 登录轮询：macOS 缺超时保护 + 每轮重复取 URL + 线程泄漏

**位置**：`app/auth.py:1087-1095`（macOS 分支直接调 `self.win.get_current_url()`）；对照 `1077-1085`（Windows 分支已用 `_bounded_call`）；`1101-1104 → 1115-1126 → 313-340`（commandcode 每轮**再取一次** URL）；`929-949`（`_bounded_call` 每次新建线程）

**现状**：pywebview cocoa 后端的 `get_current_url`/`get_cookies` 是**无超时**信号量（`cocoa.py:869-877`、`839-867`）。主线程被页面加载/首帧/全量同步占住时，监听线程就永久挂在那次 `acquire()` 上；`_bounded_call` 超时后 worker 线程也不回收。

**实测**：commandcode 页停留 5 秒 → `get_current_url` 调用 **12 次（2.4 次/秒）**，其中一半是同一轮内的重复调用（相邻间隔中位 0.8 ms）；opencode 页为 6 次；超时场景线程数 1→2 且不回收。

**修正后的影响范围**（复核澄清）：不是「永久拦死登录」——`main.py:1204` 有 `seconds_since_tick() > 20` 的自愈分支，实际表现是**点登录后最多 20 秒静默无反应，然后强制销毁重建窗口**。

**改法**：① macOS 分支同样用 `_bounded_call(self.win.get_current_url, COOKIE_READ_TIMEOUT)`；② `login_entry_lost(win, provider, url=None)` 增加可选 `url`，`_check_entry_drift` 复用本轮已读到的 URL；③ `_bounded_call` 改为复用固定 worker（`ThreadPoolExecutor`），超时不再无界新建线程。

---

### 5. 会话表每次翻页跑两遍全量聚合

**位置**：`app/db.py:1468-1531`（`COUNT(DISTINCT ...)` 在 1495-1500，`GROUP BY` 在 1504-1513）；接口 `app/server.py:1135`；前端 `app/web/app.js:1743-1744`（每页 7 行，每次翻页触发）

**现状**：同一次调用对同一批行跑两条同窗口、同分组键的语句（一条只为拿 `total`），两个都 `USE TEMP B-TREE`。

**实测**：约 20 万行时该端点 **233 ms**（不带 days）；单遍合并后 **171 ms（−27%）**；带 `days=30` 时 415→250 ms（−40%）。复核已实测 `COUNT(*) OVER ()` 与 `COUNT(DISTINCT ...)` 在 6 种 LIMIT/OFFSET/days 组合下 total 完全等价。

**改法**：合并为一条，用窗口函数带回总数（取首行；空集 total=0）。

> 注意：初审曾建议「前端补 `days` 参数」，**实测被否决**——`days=30` 反而更慢（226 vs 171 ms），因为计划切到 `local_date` 索引后随机回表更多。

---

### 6. `insert_usage_records` 的 UPSERT 对未变行也写（每轮同步必命中）

**位置**：`app/db.py:1131-1215`（`DO UPDATE SET` 在 1147-1167）；调用 `app/server.py:485`（每页）

**现状**：增量同步每次回溯最近 **1 小时**（`INCREMENTAL_OVERLAP_MS`），上一轮已写入的记录会被重新 UPSERT；即使值完全没变也走完整 UPDATE 路径，产生页写与 WAL。

**实测**：1000 条已存在记录重复写入 = **52.5 ms + 6.7 MB WAL**；加「值有变化才写」守卫后 = **8.1 ms + 0 WAL**。因为每 5 分钟一次增量同步都会重拉最近 1 小时，**这是每轮必然命中的路径**（初审数据层报告曾判「不值得改」，复核实测后**证伪**该判断）。

**改法**：给 `DO UPDATE` 加 `WHERE` 值变化守卫（约 10 行）。`usage_records.synced_at` 全库无读取方，可安全排除在守卫外；**新增条数语义不变**。

---

### 7. 重复的 dashboard 请求：前端无防抖 + 服务端零缓存

**位置**：前端 `app/web/app.js:474-487`（切页）、`1676-1683`（range pill）、`726-740`（图例点击）、`512-527`（`loadDashboard`）；服务端 `app/server.py:859-917`

**现状**：`loadDashboard()` 只有 `loadSeq` 丢弃过期响应，**请求照发、服务端照算**。实测：连点 5 个 range pill → 服务端收到 **5 次** dashboard（每次 4–5 条聚合），客户端只渲染 1 次；`stats→home` 往返每轮 3 个请求。服务端侧则完全没有请求级缓存，**每次都是 200–330 ms 的重复计算**（20 万行档）。

**改法（两段，可分开做）**
- **前端（低风险）**：`loadDashboard` 加同口径 5 s 复用 + `AbortController` 取消在途；3 个 pill/图例调用点加 180 ms 防抖。
- **服务端（高收益）**：按「账号 + 数据代数」缓存已序列化的响应体，命中 614 ms → **0.2 ms**。必须覆盖 **8 个失效点**：同步完成 / 切账号 / 登出 / 重登录 / 加号 / 删号 / 导入 / 改设置；并加一条「同步后数字必须变化」的冒烟测试。

**风险**：缓存失效漏点会显示陈旧数据 —— 这是本条唯一的主要风险，务必配测试。

---

### 8. `export_backup` 全量物化进内存

**位置**：`app/backup.py:76-117`（`records.append` 84-104、`json.dumps(body)` 116）

**现状**：把全库明细先堆成一个 Python list（每条 16 键 dict ≈ 1.9 KB），再整串 `json.dumps` —— 两份完整副本，**无上限**。`export_csv` 已是流式，只有备份不是。

**实测**：90k 条 = 4.88 s / 峰值 173 MB 堆 / 343 MB RSS；20 万行峰值 **365 MB**（1,827 B/行）。`window_days=None`（所有）是合法配置 → 百万行级 = ~1.8 GB。

**改法**：改为 gzip 流式拼接写出（字段结构不变，Android parity 不受影响），峰值降到 O(EXPORT_PAGE)=1000 行。**风险中**：手写 JSON 拼接需保证转义正确 —— 建议加一条「流式导出可被 `json.loads` 且与旧实现逐字段相等」的单测。

---

## 四、明确不建议做（已实测否决，别白花力气）

这些看着该改、实测不值得，列出来避免重复投入：

| 项 | 否决依据 |
|---|---|
| **单独上 `ANALYZE`** | 对默认视图 today 有效（91→10.6 ms），但对 30d 的符号**随窗口密度翻转**（窗口占比 100%/51% → −113/−27 ms；26%/13% → **+28/+62 ms 回归**）。要用统计信息必须配合索引提示；最优解是第 2 项的覆盖索引。 |
| 前端给 `/api/usage/sessions` 补 `days` | 实测 `days=30` 反而更慢（226 vs 171 ms） |
| 图表 `destroy()+new Chart()` 改 `update()` | 4 张图合计 11.09 vs 10.51 ms（1.2×），改 5 处数据映射的回归风险远大于 ~1 ms 收益 |
| 205 KB `chart.umd.min.js` 加 `defer` / 按需加载 | V8 解析+编译+执行实测中位 **1.6 ms** |
| 静态资源 gzip | loopback 传 205 KB 仅 ~0.2 ms，压缩 app.js 要 2.5 ms，**每请求净亏** |
| HTTP/1.1 keep-alive / 线程池 / 连接池 | 每请求固定开销合计 0.4–0.5 ms；`db.get_db()` 新建连接实测 0.128–0.232 ms |
| `pollUntilIdle` 重入、`renderAll` 隐藏页、首屏 4 请求并行 | 收益 ≤1–2 ms，或触发条件实测不可达（`/api/state` 仅 0.79 ms） |
| 「quota=null 导致每 5 s 上游重试风暴」 | **证伪**：两个 provider 的 `fetch_quota` 都吞异常返回 `success=False`（真值 dict），TTL 正常拦截，实测 20 请求仅 3 次上游。保留为「守卫脆弱」的 P2 潜在项 |
| charts 请求数改增量维护列 | 收益 1.3 ms，换一致性维护成本 |
| 每请求重复的账号解析 SQL（dashboard 23–24 条） | 已确认但降级 P3：全是 PK/索引点查，合计 <0.1 ms |

---

## 五、这份结论是怎么保证可信的

初审四路报告之间存在直接矛盾，独立复核用受控实验逐条裁决：

| 冲突 | 裁决 |
|---|---|
| 规划器 / ANALYZE（两份报告结论相反） | server 的机制确认；db 的「ANALYZE 无正向证据」**证伪**（其对比受表增长污染）。推荐覆盖索引而非 ANALYZE。 |
| `session_stats_page` 是 P1 还是 P2 | 统一 **P1**；收益从宣称的 −50% 修正为实测 **−27%/−40%**。 |
| 聚合耗时四个数字互相对不上（242.9 / 614 / 63.7 / ~60 ms） | 差异主因是**窗口内行数**而非总行数；四份报告的数字在统一口径下全部回代一致。 |
| quota 5 s 重试风暴 | **证伪**并降级 P2；前端独立成本也不成立（null 窗口被上游 10 s 超时封顶）。 |

复核还查出初审的两处实质错误：**db 的 charts 守卫改法有语义 bug**（会冻结同步时间显示并漏更新 9 个值列）、**10 列覆盖索引清单不成立**（会让 3/8 条查询变慢）。此外证伪 2 条、降级 8 条 —— 上面「不建议做」一节即由此而来。

**复现**：测量基座在 `.tmp/perf-audit/harness/`，一条命令重跑全部基准：

```bash
bash .tmp/perf-audit/harness/run_all.sh          # ~100 秒，可调 RECORDS / REPEAT
```

---

## 六、实施结果（2026-10-17 完成）

TOP 8 已**全部落地**，并经独立验证（15 项检查点 + 备份等价性 7 项 + 权限矩阵 8 场景 + 变异测试，`pytest` **354 passed**）。

| # | 项目 | 实施前 | 实施后 | 独立验证 |
|:--:|---|---|---|---|
| 1 | 导出复合索引 + keyset 分页 | 200k 行导出 34.0 s | **1.65 s（20.6×）** | 逐行等价 4 种边界 |
| 2 | 11 列覆盖索引 | dashboard 冷启 today 274 / 30d 614 ms | **49.5 / 202.6 ms** | 计划切到 COVERING INDEX |
| 3 | charts 守卫 upsert | 430 ms + 9.8 MB WAL / 5 min | **188 ms + 0 WAL** | 12 值列逐列生效 |
| 4 | auth macOS 有界调用 + URL 复用 | 12 次 URL/5 s；僵尸 tick 持续增长 | **6 次；0.18 s** | 假窗口计数复现 |
| 5 | session 单遍聚合 + 次序键 | 233 ms（days=None） | **157 ms** | total 与旧实现全等价 |
| 6 | records 守卫 upsert | 2000 行全同写 471 KiB WAL | **0 B WAL** | 逐字段等价 + 计数不变 |
| 7 | 重复请求治理（前端防抖 + 服务端代数缓存） | 重复 dashboard 589.8 ms | **1.95 ms** | 易变字段实时性 + 8 类失效点动态触发 |
| 8 | 备份导出流式写出 | 峰值 **365 MB** | **3.1 MB（116×）** | 200k 行解压正文**逐字节相同**（sha256 一致） |
| + | 退出延迟（Timer daemon，一行） | 3019 ms | **72 ms** | 子进程实测 |
| + | 托盘「今日用量」永不刷新（功能缺陷） | 永远停在启动瞬间 | **每 30 s 真实刷新** | callable 求值零 DB 调用 |

**真实库验收**（本机 13.8 MB / 2.6 万行的只读快照）：迁移 **46 ms**、幂等重开 7 ms、体积 **13.8 → 14.8 MB（+1.0 MB，新索引优先复用了 700+ 个空闲页）**、`integrity_check` 通过、行数/账号数不变。真实数据上冷启 dashboard 12–33 ms、缓存命中 0.13 ms、导出 17,744 行 <10 ms；`EXPLAIN` 确认聚合走 `COVERING INDEX idx_usage_cover_dash`、导出走 `idx_usage_account_time_usgid`。

**已知行为变化（有意为之，均可回退）**

- **覆盖索引的写入代价**：新增行 +36 ms/千行（增量同步单轮新增 ≤100 行 → +3.6 ms），首次全量约 +37%（顺序到达）；真实增量画像净值是 **3.3× 更快、4.2× 更少写**（90% 命中原行时值全同 → 零写）。合成最坏情况库体积 +40%，本机真实库实测仅 +1.0 MB。
- **`usage_charts.synced_at`** 语义变为「最后变更时刻」（此前每次同步都推进）。已确认全仓无消费方、API 字段仍在。
- **会话列表并列 `last_at`** 时按 `session_id ASC` 稳定排序（分页确定性，良性）。
- **备份导出改原子替换**：目标为符号链接时会被替换成普通文件（旧实现透过链接写）；覆盖导出沿用原文件权限位。

**本轮未做（有意）**：`/api/accounts/overview` 缓存（真实库仅 3.4 ms）、`import_backup` 上限下调（512 MiB 上限对应峰值 ~2.2 GB，但下调会挡住合法的大备份导入）、以及第五节「明确不建议做」的全部条目。

**回退**：改动集中在 6 个文件且相互独立 —— `git checkout app/db.py app/backup.py app/server.py app/web/app.js app/main.py app/auth.py` 可整体回到本轮之前。无 schema 破坏性变更（只加索引），备份文件格式向后兼容。

---

## 附录：审查产出文件

| 文件 | 内容 |
|---|---|
| `.tmp/perf-audit/db.md` | 数据层审查（db.py / forecast.py / backup.py） |
| `.tmp/perf-audit/server.md` | HTTP·API 层审查（server.py / updater.py） |
| `.tmp/perf-audit/runtime.md` | 运行时与登录链路审查（main.py / auth.py / 打包） |
| `.tmp/perf-audit/web.md` | 前端审查（app/web） |
| `.tmp/perf-audit/verify.md` | 审查阶段独立复核：30 条裁决 + 4 组冲突 + TOP 8 |
| `.tmp/perf-audit/impl-{db,server,runtime}.md` | 三集群实施记录（改动 / 前后实测 / 风险与回退） |
| `.tmp/perf-audit/verify-impl.md` | 实施阶段独立验证：15 项检查点 + 3 处裁决（347 passed 时点） |
| `.tmp/perf-audit/impl-backup-stream.md` | 备份流式导出实施记录 |
| `.tmp/perf-audit/verify-backup-stream.md` | 备份等价性独立验证（逐字节 + 内存 + 边界） |
| `.tmp/perf-audit/harness/` | 可复跑测量基座（合成库 schema 由 `db._init_schema` 真实生成）+ 实施验证套件 |

> 审查与实施的全部过程记录。**最终代码状态**：6 个源文件改动 + 3 个新增测试文件（89 例），`pytest` **354 passed**；审查开始时基线为 265 passed。原始审查报告（第二～五节）保留实施前的判断与依据，实施结果见第六节。
