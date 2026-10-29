# GoGauge 代码审查报告（2026-10-27）

> **审查对象**：`main` @ `c6bb322`（v2.2.2）——桌面端 `app/*.py`（9,174 行）+ `app/web/*`（2,860 行）+ `tests/` + `.github/workflows/`。不含 Android / HarmonyOS 源码（仅在跨端口径处引用）。
> **方式**：6 路并行审查（数据层 / HTTP·备份 / 运行时·登录 / API·更新器·打包 / 前端 / 测试·CI）+ 独立复核；**只读**，除本报告外未改动任何仓库文件。
> **基线**：`.venv/bin/python -m pytest tests/ -q` → **416 passed, 1 skipped（~27s）**。
> **证据标签**：`[repro]` = 已用脚本/实测复现；`[trace]` = 调用链逐行确证；`[hypothesis]` = 合理推断未复现。
> **前置文档**：`docs/perf-review-desktop.md`（2026-10-17 性能审查）的 TOP 8 已全部落地且本次复核**仍然有效**（覆盖索引 / keyset 导出 / 守卫 upsert / 聚合缓存 / 流式备份 / 有界调用 / 托盘刷新 / Timer daemon 均在位）。本报告**不重复**该文档 §6（已完成）与 §4（已实测否决）的条目；只指出其中**未落地**的「次席」项（见 P2-11）。

---

## 一、先做什么（TL;DR）

**若只改三件事**：

1. **P1-1 重登录串号**（数据破坏，改动 0.5–1 天）——用户在登录途中切换账号，会把 A 的新凭证写进 B、并销毁 B 的原凭证。
2. **P1-2 迁移非原子**（静默丢全部历史，改动 0.5 天）——升级过程中崩溃/异常会把 `usage_records` 留在 `*_legacy` 表，应用正常启动但统计全 0，无任何报错与恢复。
3. **P1-3 发布闸门 + 版本漂移**（当前发不出 v2.2.2，改动 0.5–1 天）——`app/__init__.py` 已是 2.2.2，Android 仍是 2.2.1d，统一发布会在 3 个平台构建完（~45 min）后于 publish 阶段失败；且发布管线从不跑测试（历史实证：`v2.2.1a/-b` 从 `pytest(Windows)=failure` 的 commit 发布了三平台产物）。

其余 P1：更新器 Atom 兜底「能发现、不能下载」（P1-4）、GOAT 账号 dashboard 数字自相矛盾（P1-5）。

---

## 二、P1（建议本轮必修）

### P1-1【数据完整性】重新登录会把新凭证写进"切换后的"活跃账号 `[repro]`

- **位置**：`app/main.py:1093`（`pending_mode` 只记 mode/provider）、`main.py:1101-1109`（`on_login_success` 调 `db.save_token(...)`）、`app/db.py:904-936`（`save_token` 内部 `aid = get_active_account_id()`，L913）、`app/server.py:1146-1195`（`/api/accounts/switch` 无"登录进行中"守卫）。
- **症状**：对活跃账号 A 发起"重新登录"，OAuth 期间把活跃账号切到 B → 登录成功后 A 的新 session 写入 **B 行**；B 的原凭证被覆盖销毁，A 仍是失效旧凭证；界面按成功流程关窗/同步。次生影响：B 的 `token_fp` 被改成 A 的，残留凭证检测兜底弱化。
- **根因**：`relogin` 的目标账号在**发起时**未固化，到**回调时**才解析。
- **修法（0.5–1 天）**：`open_login()` 里 `pending_mode["account_id"] = db.get_active_account_id()`；`db.save_token()` 增加可选 `account_id` 参数（有值时 `UPDATE ... WHERE id=?`，并校验 `rowcount`）；目标账号已被删则回退 `add_account`。加一条"登录中途切号，凭证必须写回目标账号"的回归测试。
- **验证**：`/tmp/review-runtime/repro_wrong_account.py`（临时脚本，已跑通）。

### P1-2【数据丢失】迁移 8/3 非原子：升级中断会把全部历史留在孤儿表，应用静默变空库 `[repro]`

- **位置**：`app/db.py:622-713`（迁移 8，重建 `usage_records` 换主键；关键 `conn.executescript` 在 L637 附近）、`db.py:547-565`（迁移 3，重建 `usage_sync_state`）、`db.py:385-725`（`_init_schema`，无 `PRAGMA user_version`）。
- **症状**：在 `ALTER TABLE usage_records RENAME TO usage_records_legacy` 之后、`INSERT ... SELECT` 之前崩溃（断电/磁盘满/进程被杀）→ 下次启动 `CREATE TABLE IF NOT EXISTS usage_records` 建出空新表，迁移 8 因主键已是新形状走 else 分支，**永远不再碰 `usage_records_legacy`**。应用正常启动、`totals("all")` 返回 0、日志无异常。
- **根因**：Python `sqlite3.executescript()` 只做一次隐式 COMMIT，脚本内语句逐条自动提交，**天然不原子**；`_init_schema` 的幂等设计依赖"结构检测"而非版本号，识别不出"半完成"状态。
- **修法（0.5 天）**：① 迁移脚本文本内包 `BEGIN; ... COMMIT;`（`executescript` 允许携带事务控制；失败时 `rollback()` 再抛）；② 启动时若发现 `*_legacy` 表 → `INSERT OR IGNORE ... SELECT` 回灌后 DROP（并写日志）；③ 迁移前自动复制一份库（真实数据目录里已见到人工的 `backup-pre-migration-*`，说明需求真实存在）；④ 引入 `PRAGMA user_version` 做一次性门控（与 P2-6/P2-7 一起收益最大）。
- **备注**：重建分支本身已补齐全部索引，与 perf 文档的"重建表丢索引"陷阱无关；缺的是崩溃原子性与恢复。
- **验证**：`/tmp/review-db/migrations.py` §2/2b（模拟中间态后可复现"行数 0 + legacy 3 行 + totals=0"）。

### P1-3【发布】发布管线无测试闸门；当前版本号漂移使 v2.2.2 必然发布失败 `[repro]`

- **位置**：`.github/workflows/ci.yml:15-20`（只响应 push main / PR，不响应 tag）、`release.yml:128-157`（`publish.needs` 只有 3 个 build，版本一致性校验在 **3 个平台都构建完之后**才跑）、`release-*.yml`（全部无 pytest 步骤）、`app/__init__.py:3`（2.2.2）vs `android/app/build.gradle.kts:20-21`（`versionName "2.2.1d"` / `versionCode 13`）。
- **实证**：GitHub API 实查 —— tag `v2.2.1b-{windows,macos,android}` 都指向 commit `90c4415`，该 commit 的 `pytest (windows-latest) = failure`，而三个 `release` workflow 全部 `success`；`v2.2.1a-*`（commit `afd3249`）同样是 `pytest (windows-latest) = failure` + 三平台 `release = success`。（那两次 Windows 失败后来由 `a66e9ad` 修复，不影响结论：**发布流程从不等待测试结果**。）`main` 分支保护实测 `protected=false`、`rulesets=[]`，CI 对合并零约束力。
- **修法（0.5–1 天）**：① `release.yml` 增加 `preflight` job（pytest + 跨端版本一致性 + Android `versionCode` 单调性），三个 build 都 `needs: preflight`（在 build 之前失败，省 45 分钟）；② `ci.yml` 增加 `push: tags: ['v*']`；③ 打开分支保护，required check = 三平台 pytest；④ 单平台 hotfix workflow 同样加 preflight；⑤ CI 加一条 `test_versions_in_sync`（读 `app/__init__.py` / `build.gradle.kts` / HarmonyOS 版本文件断言一致）。

### P1-4【可用性/供应链】更新器 Atom 兜底只能"发现"，不能"下载" `[repro]`

- **位置**：`app/updater.py:343-366`（`fetch_asset_info(tag)` 硬请求 `api.github.com/releases/tags/{tag}`）、`updater.py:408-471`（`download_update` 在 L422 调它）、`app/server.py:947-952`。
- **症状**：GitHub API 被限流/被墙（Atom 兜底存在的**唯一理由**）时：检查更新走 Atom 成功显示"有新版本"，点下载 → `fetch_asset_info` 再撞同一个 API → **下载 100% 失败**；失败兜底又打开 `/releases/latest`（见 P3-3，可能根本不是桌面 release）。
- **修法（M）**：① `check_update()` 的列表路径本来就有完整 `assets[]`，直接返回匹配资产的 `browser_download_url + digest`，`download_update` 不再二次请求（顺带省一次最坏 25.6s 的调用，并缓解 P2-11）；② Atom 路径按资产命名约定构造 `releases/download/{tag}/{asset}`，用 release 里已附带的 `SHA256SUMS.txt`（`release.yml:194` 每次统一发布都会生成）做 sha256 校验，保留 fail-closed 语义；③ 兜底文案改为"API 不可用，请打开发布页手动下载"，并把 `release_url` 传下去。
- **验证**：`/tmp/review-api/repro_updater.py` B 段。

### P1-5【正确性】GOAT 账号同一 dashboard 内数字互相矛盾：`totals()` 的 charts→明细回退未与其它聚合对齐 `[repro]`

- **位置**：`app/db.py:2575-2640`（`totals()`；关键 L2582-2601）。
- **症状**：commandcode（GOAT）账号走 charts 口径。当某窗口 `usage_charts` 无行但明细表有行（典型：本地零点后 charts 尚未同步的 ≤5 分钟；charts 拉取失败但明细成功；新计费周期刚开始）时，`totals()` 的 charts SUM 返回 NULL → **继续回退到明细表**；而 `model_stats()` / `daily_stats()` / `today_trend()` 走 charts 直接返回空/0。用户看到"今日请求 1、费用 $0.5"，但模型环形图、每日趋势、24h 趋势全是 0；两套数据源 token 口径也不同。
- **修法（S）**：`_use_charts_stats()` 为真时把 NULL 视为 0 直接返回（不落明细），与其它三个函数统一；补一条"同一数据下 totals / Σmodel_stats / Σdaily_stats / today_trend 四路相等"的参数化测试（现有 `test_month_cycle.TestChartsRangeParity` 只覆盖 30d/month 且不含空窗口）。
- **验证**：`/tmp/review-db/probe2.py` §A（charts 只有昨天行 + 明细有今天行 → totals today=1 而三处为 0）。

---

## 三、P2（下一轮，按主题分组）

### P2-1 峰谷分档（2.2.2 新功能）：起始门口径错误 + 实测 2.6–12× 聚合回退

- **起始门**：`app/db.py:1971-1972` 用单一常量把两个白名单模型统一设门在"北京 2026-09-10"；但**真实账单反证** `deepseek-v4-flash` 自 2026-08-17 起已两档计价（空闲 ≈0.22 / 高峰 ≈0.445 USD/1M，同样是 09:00-12:00 / 14:00-18:00 北京窗口）。结果：2,384 条已按峰谷计费的 8 月记录在统计页被当成"单一价"不拆分；而 `scripts/peak_split.py:90-94` **没有门**，把 8 月上中旬真正单一价的记录也拆了，输出"省 $3.28"的错误结论。`tests/test_peak_split.py:222-236` 把错误口径固化成了契约。`deepseek-v4.1-flash` 的 15,450 条记录经同法验证：峰窗/节假日/左闭右开边界**全部吻合**，错的只是门。`[real-db 只读核对]`
- **性能（本次实测，20 万明细行 / 5 万 charts 行，中位数）**：

  | 调用 | 关闭分档 | 开启分档 | 倍数 |
  |---|---:|---:|---:|
  | `model_stats("30d")` | 53.9 ms | 195.2 ms | 3.6× |
  | `model_stats("all")` | 121.2 ms | 313.0 ms | 2.6× |
  | `model_daily_stats(30)` | 14.5 ms | 179.6 ms | **12.4×** |
  | `totals("30d")`（不分档） | 26.4 ms | 26.8 ms | — |

  根因：`_peak_tier_sql`（`db.py:1988-2017`）对每一行求 `lower(model)`×4 + `substr`×2 + `strftime('%w')`，且进入 `GROUP BY model, tier`，覆盖索引/分组顺序全部失效。实测等价表达式改写只回收 15–24%；**根治方案**：入库/迁移时预计算 `tier` 列（或 `peak_minute` 物化列）+ 索引，把开关变成纯查询列。
- **修法**：起始门按模型区分（v4-flash = 2026-08-17，v4.1-flash = 2026-09-10），脚本与 db 共享同一份规则/节假日表并加 parity 测试；性能按上面的预计算列方案。

### P2-2 备份导入/导出：账号合并、占位行重复、非原子、无校验 `[repro]`

- 位置：`app/backup.py:110-119`（账号映射只用 `(provider, workspace_id)`）、`backup.py:214-239`、`db.py:1011-1091`（`add_account` 对空 token 不去重，L1027-1031）、`backup.py:201-282`（`import_backup` 无事务/无校验/无账号上限）、`server.py:1386-1402`、`backup.py:32-61`（`export_csv`）、`backup.py:134-165`（`export_backup`）、`db.py:2648-2678`（`export_page`）。
- 已实测：
  1. **GOAT 账号合并**：所有 commandcode 账号 `workspace_id` 恒为 `"Default"` → 备份里多个 GOAT 账号在导入后合并进同一本地账号（5+7 条 → 12 条同账号）。
  2. **占位行重复**：未匹配账号被建为**无 token 占位行**（UI 不可见、无法切换）；同一备份导第二次会再建一批占位账号并把同 `usg_id` 记录再插一遍（与 docstring"幂等 upsert"矛盾）。
  3. **静默丢数据**：占位行不在 `_logged_in_accounts()` 里 → **下一次导出直接漏掉它们**（DB 有 1 行 → 导出 0 行）。
  4. **非原子**：坏字段（`accountId` 字符串、超大 int、`accounts` 非 list）抛错时前 1000 条已 commit、账号已建，HTTP 500 且聚合缓存不失效；300 账号的构造文件一次建 300 行。
  5. **createdAt 不校验** → `local_date=NULL` 的僵尸行（窗口不可见、prune 永不清理、`totals("all")` 仍计入）。
  6. **导出无读快照**：keyset 跨多条语句无事务，导出期间的并发回填会漏行（实测 3001 vs 3000）；新备份文件 0644（DB 已 0600）；`.tmp` 名字可预测且跟随软链。
- 修法：账号匹配改为"全账号去重 + 每个本地账号只匹配一次"+ 备份格式加稳定 accountKey；占位行按 `(provider, workspace_id)` 去重并参与下次匹配；导入做预校验 + 单事务 + 账号数上限 + 失败返回 400；`createdAt` 入口校验；导出加 `BEGIN` 读快照 + `mkstemp(0600)` + `os.replace`；CSV 做 OWASP 公式转义（`= + - @` 前缀）。

### P2-3 `local_date` 时区正确性：非 UTC 偏移时间戳 + 系统时区变更 `[repro]`

- 位置：`db.py:1193-1194`、`db.py:1251-1252`（`date(substr(?,1,19),'localtime')`）、`db.py:584-591`（迁移 6 回填）、`db.py:1988-2017`（峰谷 tier）、`commandcode_api.py:484`（`_normalize_created_at` 原样保留 tz-aware 串，与 opencode 侧归一化为 Z 的口径不一致）、`backup.py:250-252`。
- 症状：① 带偏移的时间戳（如 `2026-10-27T20:33:06+08:00`）会被当成 UTC 再 +8h → 跨零点时 `local_date` 错一天，索引预过滤与秒级精筛互相矛盾，峰谷"峰"被误判成"谷"；② 只存派生列不存时区 → 用户改系统时区/跨时区使用后旧行不重算，"今日"会统计到昨天的记录、prune 边界偏移一天；③ 不可解析的 `created_at` → `local_date=NULL` 僵尸行。
- 修法：写入边界统一归一化为 UTC-Z（非法时间戳拒收/跳过）；`settings` 记录派生时区标识，启动发现变化时后台分批重算 `local_date`；峰谷 tier 改用归一化后的值。

### P2-4 macOS 关闭"开机自启"会当场杀掉自己 `[repro + 系统实验]`

- 位置：`app/autostart.py:48-57`（L52 `_launchctl(["unload", plist])`）+ `app/server.py:1426-1437`（PUT 设置里调用）。
- 症状：自启启动的进程就是该 LaunchAgent 的 job → `launchctl unload` 对其发 SIGTERM：设置已落库但响应发不出，用户看到"一点就退出"。
- 修法（~1h）：只删 plist 不 unload；或检测"当前 pid 是否是该 job 的进程"后跳过 unload（`launchctl print` / 记录自启启动标记）。

### P2-5 凭证存储：token 明文进 argv + 静默明文回退 + 数据目录权限 `[repro]`

- 位置：`db.py:196-207`（L202-204 `security add-generic-password ... -w <token>`）、`db.py:237-249`（`_storage_encode` 加密失败静默 `return token`）、`db.py:119-134`（注释称"仅记录日志"但无日志）、`README.md:132`（宣称钥匙串）、`db.py:324-337`（数据目录未收窄 0700，仅 DB 文件 0600）。
- 影响：同机其他用户可在窗口期（10ms–10s）通过 `ps` 读到 session token，绕过钥匙串本应防的威胁模型；钥匙串写失败时用户以为已加密、实际明文入库且无任何提示。
- 修法（1–2h）：改用 `security -i` 走 stdin 或 PyObjC `SecItemAdd`；失败时写日志 + 在设置页/关于页显示 `token_storage` 状态，README 同口径；数据目录 `chmod 0700`。

### P2-6 每次启动都执行的破坏性前缀清理 `[repro]`

- 位置：`db.py:715-725`（`UPDATE accounts SET token='' WHERE token LIKE 'auth=%'`，且**在 `_schema_lock` 块外**每次 `_init_schema` 都跑）、`auth.py:57`（`SESSION_COOKIE_NAMES` 仍保留 legacy `auth` 捕获，`build_token()` 会生成 `auth=...` 形态）。
- 症状：若捕获到 legacy 形态凭证，**下次启动即被清空**（`token_fp` 保留）→ "重登成功、重启又掉登录"循环。与 `fix/code-audit-2026-09` 分支已修的 M4 问题同源（该分支 main 未合）。
- 修法：用 `PRAGMA user_version` 一次性门控；或直接删掉 legacy `auth` 捕获路径；两条 UPDATE 移入锁内。

### P2-7 `prune_expired` 从不清理 `usage_charts`（保留承诺不一致 + 无界增长） `[repro]`

- 位置：`db.py:1474-1518`（`prune_preview` 只 COUNT `usage_records`；DELETE 只针对 `usage_records`）。
- 症状：GOAT 统计主口径来自 charts，"按同步范围清理"却对 charts 一行不删：提示"已清理 N 条"后 `totals("all")` 仍含历史；charts 跨计费周期无限累积；预览条数误导。
- 修法：`prune_preview` 同时统计 charts，`prune_expired` 同步删除并按表计数；若决定不删，必须在 UI/文档中写明"聚合表不参与清理"。

### P2-8 `data_dir()` 每次调用重解析 + 写删探针；探针瞬时失败会静默切库 `[repro]`

- 位置：`db.py:81-116`（frozen-Windows 分支每次 `makedirs` + 写删 `.write-test`，实测 ~154µs/次；一次 dashboard 请求触发多次）、`db.py:115-116`、`db.py:733-751`。
- 症状：磁盘满/AV 锁文件/权限变化时静默改走 `LOCALAPPDATA` → `db_path()` 变化 → 新请求线程连到另一个空库、payload 缓存重读；旧线程仍指旧库（split-brain），界面表现为"数据全丢"。
- 修法：进程内缓存首次解析结果（`set_data_dir` 失效），探针只跑一次；探针失败保持上次可用路径或显式报错。

### P2-9 本地 HTTP 安全加固：点击劫持 + 零鉴权 `[repro]`

- 位置：`server.py:878-936`（静态响应头只有 Content-Type/Length/Cache-Control/ETag/Last-Modified）、`server.py:1497-1500`、`index.html:7-8`（meta CSP 不含 `frame-ancestors`，且规范上 meta 交付的 `frame-ancestors` 被忽略）、`server.py:1465-1483`（`_reject_non_local`）、`server.py:1523-1529`。
- 症状：① 任意网页扫到 ephemeral 端口后 iframe 本地 UI，被框页面发出的是 **same-origin POST**，Host/Origin 校验全部通过 → prune/删号/注销可被点击劫持；② WebView↔server 之间没有任何 token，同机**其他 OS 用户**（`netstat` 枚举端口）可读全部用量/账号并执行不可恢复操作（实测 logout 后 `usage_records` 10→0）。
- 修法（S/M）：① 四个响应头 `X-Frame-Options: DENY`、`Content-Security-Policy: frame-ancestors 'none'`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`（10 分钟）；② 启动随机 token 注入 WebView URL/`X-GoGauge-Token`，HTTP 层校验（~2h）；③ 顺带校验 `Sec-Fetch-Site`，堵住"无 Origin 的跨站 GET 可驱动带凭证的配额请求"（P3）。

### P2-10 登录流程：回调线程阻塞 UI + 全量同步排最后；`open_login` 无并发锁；`_bounded_call` 线程泄漏 `[repro/trace]`

- 位置：`main.py:1104-1140`（`on_login_success` 在登录监听线程做 `hide/load_url/evaluate_js` 三个无超时跨线程调用；`sync_all_async("full")` 是最后一行 → UI 线程忙时首次同步永不触发；`save_token` 异常被吞后仍走成功流程）、`main.py:1241-1303`（`open_login` 无双飞锁，`ref` 到 `_start_watcher`(L1190) 才写，js_api 每调用一线程 → 快速双击可产生 2 个登录窗/2 个 watcher，先建窗口的 watcher 永不启动）、`auth.py:934-954` 与 `auth.py:898-931`（`_bounded_call` 每次超时新建线程且不回收，主线程被占时 ~1/s 累积；perf 审计 §3#4 的"复用固定 worker"未落地）。
- 修法：sync 前移到 UI 调用之前 + 用 `_bounded_call` 包住 UI 调用 + `save_token` 失败中止成功流程；`open_login` 函数级非阻塞锁；`_bounded_call` 改单例 daemon worker（超时模式下直接返回 None）。

### P2-11 更新流程：前端 15s 超时 < 后端最坏 51.2s；`/api/update/check` 仍是同步阻塞

- 位置：`server.py:947-952`（同步 `check_update()`）、`updater.py`（两来源 × 3 次 × 8s 超时 + 退避 = 最坏 51.2s）、`app.js:322-325`（`API_TIMEOUT_MS = 15000`）、`app.js:1931`（检查更新用默认 `api()`）、`app.js:1904`（下载轮询 180s 上限）。
- 症状：慢网/被墙时前端 15s 就报"请求超时"，而后端仍在跑；下载 worker 还会再做一遍完整检查（共两遍）。
- 备注：`docs/perf-review-desktop.md` §2「次席」列的 `/api/update/check` 异步化**在 main 中并未实现**。
- 修法：改为"POST 触发 + GET 轮询"（复用 download 的 status 模式）；或前端给该请求单独放宽超时（`fix/code-audit-2026-09` 分支已有该改法）；同时按 P1-4 去掉重复检查。

### P2-12 前端账号切换状态复位不完整、刷新不刷、分页不夹紧 `[trace]`

- 位置：`app.js:1604-1617`（顶栏切号无 stats 分支）、`1542-1548`、`1507-1514`、`1781-1789`（登录路径不复位）、`1224-1231`（`pollUntilIdle` 完成只强刷 dashboard）、`1844-1855`/`1880-1890`（导入/清理只刷 dashboard）、`1147-1150`/`1097-1100`（页码不校正）、`1124-1127`（筛选模型不在新选项时 `<select>` 空白但筛选仍生效）。
- 症状：统计页顶栏切号后热力图/模型趋势仍是旧账号；旧账号的 `excludedModels` 会带到新账号少算总量；记录页点"刷新"/同步完成后表格不更新；"第 3 页 共 1 页"空表。
- 修法：抽 `onAccountChanged()` 单一失效点（清 `excludedModels`/`heatmapDays`/`modelTrendData`/`dashCache` + 按当前页刷新）；抽 `refreshCurrentPage()` 供同步/导入/清理复用；分页加夹紧 + 选中值回退。

### P2-13 测试与 CI 缺口（按风险）

- **同步引擎核心无测试**：`tests/test_sync_engine.py:65/81/102` 把 `_sync_one_account` 整个 mock；真实内部只被调用 1 次（`test_server_routes.py:301`，单页成功）；`_sync_one_cc_account`（`server.py:657-727`）、`_max_pages_for`/`_window_boundary_hit`/`_incremental_done`/`_finish_sync` 在 tests 中 **0 引用**。游标/页失败/增量停止回归会"同步成功但静默少数据"；CC 与 opencode 的失败语义已不一致（CC incremental 首页失败即放弃、opencode 会重试）。`[trace]`
- **本地 HTTP 唯一鉴权边界零测试**：`grep -rn '_reject_non_local' tests/` → 0（Host/DNS-rebinding + Origin/CSRF）。`[trace]`
- **CI 全跑 UTC**：`local_date` 断言与同进程 SQLite `localtime` 自比（`test_sync_engine.py:210-215`、`test_perf_db_opt.py:387`、`test_month_cycle.py:157`）→ "本地日误用 UTC"的回归在 CI 永远绿。修：conftest 固定 `TZ=Asia/Shanghai` + 2 条固定时区断言。`[repro]`
- **pywebview stub 依赖字母序**：stub 在 `tests/test_auth_login.py:15-17` 与 `test_perf_runtime_opt.py:33-35` 的模块顶层，`conftest.py` 没有；模拟 CI（无 pywebview）下全套能过，但单跑 `test_login_session.py`/`test_windows_login.py` 或倒序跑直接 ImportError。修：stub 移入 conftest。`[repro]`
- **真实 DPAPI/钥匙串从未执行**（`db.py:188-238` 全被 mock）；**迁移 6 的 `local_date` 存量回填无断言**（`db.py:583-590`）；**备份敌对输入零测试**（现抛裸 `KeyError/AttributeError/ValueError`，实测表见分报告）。`[trace]`
- **Android 17 个 JVM 单测（1,571 行）+ 4 个仪器测试 + 2 个 ArkTS 测试从未在 CI 运行**；`release-harmonyos.yml` 从未成功过（`runs-on: ubuntu-latest` 不装 DevEco 工具链；签名 `if: env.HAP_STORE_PASSWORD != ''` 是死分支——step 级 `if` 看不到本 step 的 `env`）。`[trace]`
- 其它 P3：2 个零断言用例（`test_updater_digest.py:34-38,58-63`，摘要校验可退化成 no-op 仍绿）、`test_perf_runtime_opt.py:55-69` 宽 `except → skip`、5 处死代码 `db._DB = None`（`app/db.py` 中不存在 `_DB`）、`test_sync_engine.py:19` teardown 不清 `_data_dir_override`、CI 无 `timeout-minutes`/pip cache/coverage、action 版本 drift（ci 用 `@v5/@v6`，release 用 `@v4/@v5`）、4 个端点（`/api/update/check`、`/api/update/open`、`/api/accounts/overview`、`/api/usage/sessions`）零测试。

### P2-14 构建/依赖：lock 文件不是 freeze、`build.bat` 绕过 lock、`GoGauge.spec` 无主

- `requirements-macos.lock.txt` 只有 5 个顶层包，缺 pyobjc-*（pywebview 的 macOS 依赖）/proxy_tools/typing_extensions/macholib/altgraph/pyinstaller-hooks-contrib；Windows lock 缺 typing_extensions → 与注释"保证可复现"及 pythonnet 事故教训矛盾。
- `build.bat:13` 用未锁定的 `requirements.txt` + 裸 `pytest pyinstaller`，且**不生成 `app/_build_info.py`** → 本地打包的 exe 冻结后 `_resolve_repo()` 回落 upstream `yphyphyph/opencode-go-gauge`，去**另一个仓库**查更新（CI 与 `build_macos.sh` 都写 `w-PiaoPiao`）。
- `GoGauge.spec` 被 `.gitignore` 的 `*.spec` 忽略、未跟踪、全仓零引用 —— 是一份"看起来是官方 spec"的死文件；真实构建参数在 4 处复制（`release.yml:47-58`、`release-windows.yml:35-46`、`build.bat:17-28`、`build_macos.sh:39-49`），已出现差异（spec `upx=True`；`build_macos.sh` 缺 `--noconfirm --clean`）。
- 修法：lock 改为真 `freeze`；`build.bat` 改用 `requirements-windows.lock.txt` 并生成 `_build_info.py`；构建参数收敛为单一脚本或纳入版本化的 spec。

---

## 四、P3 快速清单（多数可顺手做）

| # | 问题 | 位置 | 工时 |
|---|---|---|---:|
| P3-1 | Windows 上 `mimetypes` 读注册表可能把 `.js` 判成 `text/plain`；补显式 MIME 表 + `nosniff`（`fix/code-audit-2026-09` 分支已有该改法） | `server.py:895` | 0.5h |
| P3-2 | `export_csv` 公式注入（`=HYPERLINK(...)`/`+cmd\|...`/`@SUM`/`-2+3` 原样写出，导入的备份可注入 model 名形成"导入→导出→Excel"链）+ 非原子写毁旧导出 | `backup.py:32-61` | 1h |
| P3-3 | 下载失败兜底固定开 `/releases/latest`，与本文件"Latest 是全平台共享标记，别信它"的注释自相矛盾；`check_update()` 返回的 `release_url` 前端从未使用 | `updater.py:52`、`server.py:958`、`app.js:1919` | 0.5h |
| P3-4 | 预发布版被当稳定版：`_parse_version` 把任意后缀（`v2.2.3-rc1`）当稳定版，列表路径不检查 GitHub `prerelease` 标志 | `updater.py:179-186,278-293` | 1h |
| P3-5 | `/api/sync` 静默丢命令：增量运行中点"全量同步"被丢弃，HTTP 仍返回 `{"ok":true}`，progress.mode 从不变成 full | `server.py:980-995,802-812` | 1h |
| P3-6 | 错误处理缺口：前端 15s 断连后 catch 再写 JSON → BrokenPipe 双 traceback；`GET /%00` 未捕获 `ValueError` → 空响应 + traceback；`str(exc)` 泄漏绝对路径 | `server.py:868-875,1491-1520,878-891` | 2h |
| P3-7 | 明细页 `days` 过滤时 `ORDER BY created_at` 使索引顺序失效（20 万行 94.9ms → 改 `ORDER BY local_date DESC, created_at DESC, usg_id DESC` 后 5.9ms，逐页内容一致）；当前前端不传 `days`，暂不可达 | `db.py:1553-1559` | 0.5h |
| P3-8 | `_raw_payload` 缓存**回写**未持 `_payload_lock`：读线程可把旧值写回缓存（active_account_id/周期键/设置陈旧到下一次写） | `db.py:733-751` | 1h |
| P3-9 | 设置健壮性：`bool("false") == True`；`get_settings` 原样返回库内未校验值（字符串 `sync_interval_sec` 可让同步循环 TypeError）；`_prune_window` 的 `int()` 可抛 | `db.py:1678-1733,1456-1460` | 1h |
| P3-10 | 周期口径不一致：只有 `monthly_reset` 的账号在存储值过期时不向前滚动（60 天前的 reset 直接当"本周期"起点），`period_bounds` 路径会顺延 | `db.py:1875-1915` | 2h |
| P3-11 | `last_inserted_count` 只加不减（真实库 32428 vs `total_records` 8611）且全仓无消费方；`clear_account` 不重置 `last_sync_at` | `db.py:1417-1425,1147-1157` | 0.5h |
| P3-12 | `set_data_dir` 不重置 thread-local 连接与 `_schema_init_path`（目前仅测试调用；未来运行期切库会继续读旧连接） | `db.py:73-78` | 0.5h |
| P3-13 | 前端 `dashRendered` 复用键不含主题/语言/视口 → 切主题/语言/缩放后 5s 内回首页跳过 `renderAll`，图表保留旧色/旧字/旧尺寸 | `app.js:575-582,2050-2077` | 2h |
| P3-14 | 两表"输入"口径不一致（会话表含缓存、记录表不含且未显示 cache_write）；`fmtTokens(999999)==="1000.0k"`；`last_sync_status` 原样英文 | `app.js:266-272,1086,1136,1415`；`db.py:1572,1631` | 2h |
| P3-15 | 可访问性实测：`--text3` 对比度亮 2.91–3.15:1 / 暗 3.33–3.61:1（AA 需 4.5:1），用于全站次级文本；modal 无焦点 trap、登录弹窗无 Esc、用户菜单项是 `div` 不可键盘 | `style.css` 变量、`app.js:393-430` | 2h |
| P3-16 | "N 日"图表实际有 N+1 个数据点（`daily_stats` 含首尾）；未登录停在欢迎页 5 分钟后仍打一次 `/api/sync`（401）；设置 PUT 失败静默 | `db.py:2373-2385,2431-2440`；`app.js:2042,1963-1980` | 1h |
| P3-17 | 登录诊断日志记录完整导航 URL（含 OAuth `code=`/`state`/`return_to`），建议打码 | `auth.py:1093-1094,1152` | 0.5h |
| P3-18 | macOS Cmd+Q / Dock Quit 未武装 `os._exit` 兜底（仅托盘/前端退出武装） | `main.py:116-119` vs `333-353,735,874,885` | 1h |
| P3-19 | 双 API 客户端重复 `_fetch`/HTTPError/体积上限/`QuotaWindow`/`LABEL_*`；`server.py:249` 与前端按**展示文案** `"Monthly"/"5h Rolling"/"Weekly"` 做协议判断，改名/本地化会静默破坏周期落库与卡片样式 | `opencode_api.py:42-116`、`commandcode_api.py:39-193`、`server.py:249`、`app.js:258,628,1318` | 2h |
| P3-20 | `commandcode_api._fetch` 重试不分类（400/404 也重试 3 次；429 忽略 `Retry-After`）；`resp.status` 分支是死代码（`urlopen` 对 4xx/5xx 直接抛 `HTTPError`）；超限检测只看 `Content-Length`（chunked 时静默截断后报"JSON 非法"） | `commandcode_api.py:76-107`、`opencode_api.py:208-243` | 2h |
| P3-21 | 两个 release workflow（android/harmonyos）把 `contents: write` 放在 workflow 级 + checkout 缺 `persist-credentials: false`（跑第三方 gradle/ohpm 的 build job 也持写 token） | `release-android.yml:11-12`、`release-harmonyos.yml:20-21` | 0.5h |
| P3-22 | 文档漂移：`docs/macos.md:53`（英文摘要）仍写 `macos-13`（已退役，CI 用 `macos-15-intel`）；README/README_en 未记录 2.2.2 的"DeepSeek 峰谷分档"功能 | `docs/macos.md`、`README*.md` | 0.5h |
| P3-23 | 死代码/小瑕疵：`main.py:121` 未用 `sender`、`server.py:1462` 未用 `fmt`、`_ASSET_NAME` 死变量、`test_*` 中 5 处 `db._DB = None` | 多处 | 0.5h |
| P3-24 | 旧式平台 tag 会拼出双后缀文件名（`GoGauge-v2.2.1d-macos-macos.zip`）且丢架构信息 | `updater.py:431` | 0.5h |

---

## 五、已检查且正常（明确不要再投入）

- **安全**：静态路径穿越全形态、DNS rebinding（Host 精确匹配）、跨站 POST / `Origin: null` / CORS 全部被挡；导出/导入的"混淆代理"路径授权（用途绑定 + TTL + 归一化）实现完整且测试充分；账号归属隔离；`https_ca` 无校验绕过、零侵入；js_api 暴露面最小（登录窗**没有** js_api）；关闭到托盘/退出裁决/单实例/注销删号清钥匙串均无新问题；日志不含 cookie 值（仅 P3-17 的 OAuth URL 需打码）。
- **前端**：**未发现 P0/P1 XSS**。31 处 `escapeHtml` + 32 处 `innerHTML` 逐字段核对（model / key_name / session_id / 账号名 / workspace_id / quota label / quota.error / 上游 error / release latest·notes）全部为"常量模板 + 已转义字段"或 `textContent`；无 `insertAdjacentHTML/outerHTML/document.write/eval`；HTML 无内联事件处理器；meta CSP `script-src 'self'` 有效。
- **数据层**：perf 审计的覆盖索引/keyset 导出/守卫 upsert/session 单遍聚合/缓存全在位；`_agg_cached` 的 8 个失效点逐一验证；聚合缓存键含账号/口径/排除项/本地日/峰谷口径（不会串味）；迁移 8 已补齐全部索引；charts 的"tokens_in 已含缓存读"口径正确；`forecast.py` 经 2 万例 fuzz 无实锤 bug。
- **更新器**：SHA-256 fail-closed + 非法 hex 拒绝 + 缺失摘要 opt-out、tag 路径穿越消毒（`_safe_tag`）、`.part` 无残留、原子替换、zip CRC / PE 头兜底、统一/旧式 release 混排取最大、macOS 按架构选包（main 已有，且测试比旧分支更全）。
- **同步**：单飞/finally/页数上限/partial/失败隔离（首个账号失败仍继续）均有实现；"同步不删本地数据"语义正确；`/api/usage/prune` 是唯一删除入口（预览 + 二次确认）。
- **测试/CI**：迁移 1/3/4/5/7/8、备份字节一致性与流式、缓存失效、路径授权、更新器选包/摘要、增长护栏均覆盖；25 个测试文件单独跑/倒序跑通过；`-W error::DeprecationWarning` 全绿；无构建产物被跟踪、`.gitignore` 基本完备、tracked 文件权限正常。

---

## 六、建议实施顺序

1. **第 1 轮（1–2 天，止血）**：P1-3 版本号同步 + `preflight` job（否则 v2.2.2 发不出去）；P1-1 重登录目标固化；P2-9 四个响应头（10 分钟即消灭点击劫持）。
2. **第 2 轮（2–3 天，数据完整性）**：P1-2 迁移原子性 + legacy 恢复 + 迁移前备份；P2-2 备份导入映射/校验/事务；P2-3 `local_date` 归一化。
3. **第 3 轮（2 天，正确性/可用性）**：P1-5 charts 口径统一；P1-4 + P2-11 更新器链路（复用资产信息 + 异步检查 + 超时）；P2-4 macOS 自启；P2-5 凭证 argv/明文回退。
4. **第 4 轮（2–3 天，性能与体验）**：P2-1 峰谷档位预计算列 + 按模型起始门；P2-12 前端状态单一失效点；P3-1/2/3 等顺手项。
5. **第 5 轮（测试加固，可与上面并行分派）**：P2-13 的同步引擎分页/失败用例、Host/Origin 边界、conftest 固定 TZ + 移入 webview stub、迁移 6 回填断言、Android 单测进 CI。

---

## 附录 A：复现方式

```bash
cd /Users/yizhiwang/Desktop/opencode/gousage/opencode-go-gauge
.venv/bin/python -m pytest tests/ -q          # 基线: 416 passed, 1 skipped

# 本次复核跑过的关键复现（review 期间生成在 /tmp，可能已被清理）
PYTHONPATH=. .venv/bin/python /tmp/review-runtime/repro_wrong_account.py   # P1-1
PYTHONPATH=. .venv/bin/python /tmp/review-api/repro_updater.py             # P1-4
PYTHONPATH=. .venv/bin/python /tmp/review-db/migrations.py                 # P1-2
PYTHONPATH=. .venv/bin/python /tmp/review-db/probe2.py                     # P1-5 / P2-3
gh api repos/w-PiaoPiao/opencode-go-gauge/branches/main --jq .protected    # P1-3
```

峰谷性能实测（200k 明细行 / 50k charts 行）：`db.set_data_dir("/tmp/review-db/perf-200000-50000")` 后分别以 `peak_split=False/True` 调 `db.model_stats("30d")` / `db.model_daily_stats(30)`。

## 附录 B：审查分工

| 领域 | 范围 | 主要证据 |
|---|---|---|
| 数据层 | `app/db.py`、`app/forecast.py` | 合成库（5 万/20 万行）+ 本机真实库只读 + `EXPLAIN` |
| HTTP·备份 | `app/server.py`、`app/backup.py` | 真实起服务（临时 data_dir）+ 8 个复现脚本 |
| 运行时·登录 | `app/main.py`、`app/auth.py`、`https_ca.py`、`autostart.py` | fake webview + launchd 系统实验 |
| API·更新器·打包 | `opencode_api.py`、`commandcode_api.py`、`updater.py`、`peak_split.py`、构建配置 | 假 HTTP server + 真实库账单反推 |
| 前端 | `app/web/app.js`、`index.html`、`style.css` | 逐行 + sink 扫描 + node 复算 |
| 测试·CI·发布 | `tests/`、`.github/workflows/`、构建配置 | AST 扫描 + 模拟无 pywebview CI + GitHub API 实查 |

---

## 七、实施结果（2026-10-27 完成）

> 本轮**已把报告中全部 P1 / P2 / P3 条目落地**（P3-23 经评估为 API 签名导致的 vulture 误报，保留不改）。
> 工作树改动：**54 个已跟踪文件、8,676 insertions / 1,339 deletions，另新增 14 个代码/配置文件**；**未提交 commit**（便于逐文件 review / 随时回退）。
> 两条硬约束全程遵守：**没有任何版本号变化**（桌面 `2.2.2` / Android `2.2.1d, versionCode 13` / HarmonyOS `1.0.0`）；**登录与凭证存储形态逐字节兼容**（`_KC_SERVICE`、`enc:v2:`、`kc:`、DPAPI 调用方式、数据目录解析规则均未改），并新增回归测试证明"重启/重新打包后登录仍可读"。

### 7.1 验证基线

| 项目 | 实施前 | 实施后 |
|---|---|---|
| `pytest tests/ -q` | 416 passed / 1 skipped | **737 passed / 2 skipped（~70s；2 个 skip 均为平台专属：Windows DPAPI 真跑、Windows 证书存储）** |
| 新增测试 | — | **321 例**（含 48 条 CI/安全契约、同步引擎分页/失败、迁移原子性/崩溃收敛、时区、真实快照兼容、备份导入互斥、真实钥匙串 roundtrip、Windows DPAPI 真跑） |
| coverage（`--cov=app`） | 无 | **75%**（5,858 stmts / 1,490 miss，`--cov-report=term` 实测） |
| `-W error::DeprecationWarning` | 未跑 | **通过**（CI 已加为独立 gate） |
| `compileall` / `node --check` / 6 个 workflow YAML | — | **全部通过** |

### 7.2 关键实机验证（不是只跑单测）

- **登录不丢（真实用户库快照）**：用最终代码打开迁移前（`user_version=0`）与当前（`uv=8`）两份真实库**副本**：
  `integrity_check=ok`；accounts 3 行、token 仍为 `['', 'kc:', 'kc:']`、`token_fp`/`updated_at` 逐字段不变；records 35,366 / charts 1,359 行数不变；settings 原有键值不变（仅新增一次性 marker）；二次初始化幂等。真实目录本身与 `.bak-20261027-213539` 均未被测试再触碰。
- **重新打包冒烟**：`python scripts/build.py --platform macos` → `dist/GoGauge.app`（58.9 MiB），`CFBundleShortVersionString=2.2.2`，`codesign --verify --deep --strict` OK，PYZ 内 `_build_info.UPDATE_REPO` 正确（本 fork），数据目录/凭证存储代码与源码态一致。
- **HTTP 安全端到端**：`GET /` 与 401/304/错误页均带 `X-Frame-Options: DENY` / CSP `frame-ancestors 'none'` / `nosniff` / `no-referrer`；无 token/错 token → 401，正确 token → 200，静态资源免鉴权；`Host: evil.example` → 403；`Sec-Fetch-Site: cross-site` → 403；`GET /%00` → 400；未知 `/api` → JSON 404；prune 返回 `charts_count`/`deleted_charts`；update async/status 正常。
- **峰谷性能（20 万明细行 / 5 万 charts 行，中位数）**：

  | 场景（开启峰谷分档） | 实施前 | 实施后 |
  |---|---:|---:|
  | `model_stats("30d")` | 195.2 ms | **157.4 ms（−19%）** |
  | `model_stats("all")` | 313.0 ms | **201.1 ms（−36%）** |
  | `model_daily_stats(30)` | 179.6 ms | **120.8 ms（−33%）** |
  | 关闭分档（回归基线） | 53.9 / 121.2 / 14.5 ms | 53.6 / 130 / 14.4 ms（无回归） |

  两段式查询把 tier 表达式限制在白名单模型行；与"逐行求值再分组"在 55 天 × 14 时刻 × 6 种模型名网格上逐字段等价，且与 `scripts/peak_split.py` 的 `tier_for` 0 mismatch。
- **版本策略脚本实跑**：`--tag v2.2.2 --platform all` → rc0 + `android_ready=false`（Android 未适配，属预期）；`--tag v2.2.1d --platform desktop` → rc1（tag 与桌面不一致必须拦截）；`v2.2.1d-android --platform android` → rc0。

### 7.3 逐条状态

| 报告条目 | 状态 | 主要落点 |
|---|---|---|
| P1-1 重登录写错账号 | ✅ fixed | `save_token(account_id=…)` + `pending_mode` 固化目标 + 回归测试（登录中途切号写回原目标） |
| P1-2 迁移非原子 | ✅ fixed | `BEGIN;…COMMIT;` 包裹迁移 1/3/8、`*_legacy` 回灌、迁移前自动备份、崩溃模拟测试 |
| P1-3 发布闸门/版本漂移 | ✅ fixed（策略内） | 所有 release workflow 加 `preflight`（pytest+版本脚本）、`ci.yml` 响应 tag、`scripts/check_versions.py`、单平台 hotfix 校验；**未启用分支保护**（仓库设置，`docs/release.md` 写明手动步骤） |
| P1-4 Atom 兜底不能下载 | ✅ fixed | `check_update` 返回 asset_url/digest 复用、`SHA256SUMS.txt` 兜底、不重复联网两遍 |
| P1-5 totals/charts 口径矛盾 | ✅ fixed | charts 空窗口统一返回 0 + 四路口径一致性测试 |
| P2-1 峰谷起始门/性能 | ✅ fixed | 按模型分区起始门（v4-flash 08-17）；两段式查询；遗留：仍比关闭分档慢（见 7.4） |
| P2-2 备份导入/导出 | ✅ fixed | 全账号导出+accountKey、匹配顺序、幂等、单事务、上限/校验、原子写、CSV 注入、读快照 |
| P2-3 local_date 时区 | ✅ fixed | 入口归一化 UTC-Z、非法时间戳拒收、TZ 变更后台重算、峰谷走归一化值 |
| P2-4 macOS 关自启杀自己 | ✅ fixed | `launchctl list` 判定当前进程 → 只删 plist 不 unload + 测试 |
| P2-5 凭证 argv/明文回退 | ✅ fixed | `security -i` stdin + 回读校验；失败回退明文但写日志；`token_storage_mode()`；数据目录 0700 |
| P2-6 每次启动清理凭证 | ✅ fixed | 具名 marker 一次性门控；对"中间版本写坏 user_version 的库"安全 |
| P2-7 prune 不清 charts | ✅ fixed | preview/delete 双表同事务 + API/前端文案 |
| P2-8 data_dir 探针换库 | ✅ fixed | 进程内缓存、探针失败沿用上次可用路径 + 告警 |
| P2-9 点击劫持/零鉴权 | ✅ fixed | 四安全头 + 随机 token（URL fragment 交付，js_api 兜底）+ `Sec-Fetch-Site` 校验 |
| P2-10 登录流程阻塞/线程 | ✅ fixed | 同步先于 UI、有界 UI 调用、保存失败不假装成功、open_login 非阻塞锁、`_bounded_call` 单例 worker |
| P2-11 更新流程 | ✅ fixed | async/status 端点 + 前端 1s×90s 轮询 + 每请求超时 |
| P2-12 前端状态复位 | ✅ fixed | `onAccountChanged()` / `refreshCurrentPage()` / 分页夹紧 |
| P2-13 测试/CI 缺口 | ✅ fixed | 同步引擎（含 CC 分支）、Host/Origin、安全头、迁移回填、TZ 固定、conftest stub、Android JVM 单测进 CI、真实钥匙串 roundtrip、Windows DPAPI 真跑用例 |
| P2-14 构建/依赖 | ✅ fixed | `scripts/build.py` 统一参数+生成 `_build_info`、lock 补全传递依赖、`build.bat/macos.sh` 薄包装、删除无主 spec、`_DEFAULT_REPO` 指向本 fork |
| P3-1…P3-24 | ✅ 全部 fixed / 已评估 | MIME 显式表、CSV 注入、releases 列表页、prerelease 过滤、sync 409、错误处理/`%00`/JSON 404、明细排序、payload 缓存锁、settings 规整、monthly reset 滚动、死代码清理、前端对比度/键盘/i18n/格式、日志打码、Cmd+Q 兜底、双 API 收敛、workflow 权限最小化、文档漂移；P3-23 的 `sender`/`fmt`/`client_address` 为 API 签名，保留 |
| 独立复核与二次修复 | ✅ | 原审查者（db-core / server-http）对修复后的代码逐条复核：db 侧 15/18 fixed + F9 改善认可、server 侧 9/9 fixed；其提出的 N1–N5（时区 marker 时序中断不收敛、DST 无变化全表重写、超大备份导入长锁、超大 JSON 整数 500、脏时间戳静默丢弃、目录权限误改自定义目录、3 个成功响应缺 `ok`）已全部修复并补测试 |

### 7.4 遗留 / 需人工决策

1. **峰谷分档仍比关闭分档慢**（157/201/121 ms vs 54/130/14 ms）：`tier` 判定必须读 `created_at`，而覆盖索引不含该列，引用即回表。本轮遵守"不加 schema 列"的约束只做了两段式优化；若要逼近基线，需要在"加预计算列 / 新覆盖索引"之间重新决策（写放大 + 迁移成本）。
2. **分支保护未启用**：属仓库设置，代码无法自动开启；`docs/release.md` 已写操作步骤。发布硬闸门已由 `preflight` 承担。
3. **GitHub Actions 无法本机实跑**：6 个 workflow 已过 YAML 解析、`check_versions`/`build.py` 已 dry-run；`android-unit-tests` job 与 Windows DPAPI 真跑用例需首次 push 后在 CI 确认。
4. **Windows lock 的 Windows-only 传递依赖**按 PyPI metadata 解析（顶层版本未动），首次 Windows CI 构建若个别 pin 冲突需微调。
5. **Android / HarmonyOS 版本未推进**：按版本策略，Android 仅在侧适配后升版；当前统一 release 会跳过 APK（`android_ready=false`），属预期。
6. **超大备份导入**：单事务原子性保留，导入连接 `busy_timeout=60s` + 导入/同步互斥（409）；1M 记录上限约 20s 可导入；若未来要支持 >~2.5M 行，需要重新评估"分批提交（牺牲单事务原子性）"或提高上限。

### 7.5 过程中的一次测试污染事故（已闭环，如实记录）

实施期间（21:35）有一个测试在 `db.set_data_dir(None)` 后调用登录流程，落到源码运行的默认数据目录 = 用户真实库，触发了**在途版本**的一次迁移。处置与结论：

- 只读审计：`integrity_check=ok`；accounts 3 行、token 仍为 `kc:` 形态且 `updated_at` 未变；records/charts 与迁移前自动备份逐项一致 —— **数据与登录态未受损**；
- 该次迁移留下了 `user_version=8` 与 `local_date_tz` 标记，并生成回滚点 `gousage.db.bak-20261027-213539`（保留未动）；
- 最终版代码用 marker 门控（不依赖裸 `user_version`）、并要求真实库快照迁移验证（见 7.2）——已覆盖"被中间版本写过的库"；
- 测试基建已加**全局沙箱**：conftest import 阶段强制 `GOUSAGE_DATA=<tmp>`，autouse guard 在每用例收尾断言 `db.data_dir()` 不得指向真实目录，违者直接 fail。

### 7.6 回退

改动全在工作树、未提交。整体回退：`git checkout -- app tests .github requirements*.txt build.bat build_macos.sh scripts README.md README_en.md docs`（新增文件手动删除）；也可 `git stash`。用户真实数据目录与 `docs/code-review-2026-10-27.md` 不受代码回退影响。
