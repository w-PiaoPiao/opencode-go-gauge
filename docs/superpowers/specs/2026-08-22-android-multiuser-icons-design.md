# 安卓端同步上游 v1.0.3 + v2.0.0 功能 — 设计文档

日期:2026-08-22
分支:`feat/android`
上游来源:`yphyphyph/opencode-go-gauge` main 分支两个提交:

- `1da23ce` feat: v1.0.3 - 修复 hy3 等混元系列模型图标
- `fd65fe4` feat: v2.0.0 - 多用户支持

## 目标

把桌面端上述两个提交的功能完整移植到 Android(Kotlin + Jetpack Compose)端,保持与桌面端 db.py / server.py 的同构("desktop parity" 约定),存量安装无损升级。

## 范围决策(已与用户确认)

| 决策点 | 结论 |
|---|---|
| v1.0.3 模型图标 | **连图标一起移植**(安卓新增图标渲染能力,含 hy 前缀匹配修复) |
| 用户切换入口 | **主页头部账号胶囊(底部弹窗快捷切换)+ 设置页完整管理** |
| 数据层方案 | **方案 A:单库 + `account_id` 列过滤**,与桌面端完全同构 |
| 版本号 | `versionName "2.0.0"` / `versionCode 4`(沿用"版本号对齐 main"惯例) |

---

## 1. 数据层(Room 迁移 v1→v2)

### 1.1 Schema 变更(语义与桌面 db.py `_init_schema` 迁移一一对应)

1. **`account` → `accounts`**:新建多行表
   ```sql
   CREATE TABLE accounts (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     name TEXT NOT NULL DEFAULT 'Default',
     workspace_id TEXT NOT NULL DEFAULT 'Default',
     resolved_workspace_id TEXT,
     token TEXT NOT NULL DEFAULT '',
     created_at TEXT NOT NULL,
     updated_at TEXT NOT NULL
   );
   ```
   迁移:旧 `account` 单行数据拷入 `accounts`(仅当目标为空,保证幂等),随后 `DROP TABLE account`;全新库种子 `(1,'Default','Default',NULL,'',now,now)`。
2. **`usage_records.account_id`**:`ALTER TABLE usage_records ADD COLUMN account_id INTEGER NOT NULL DEFAULT 1`;新增索引 `idx_usage_account_time(account_id, created_at DESC)`(旧索引保留)。
3. **`usage_sync_state` 重建**:`RENAME TO usage_sync_state_legacy` → 建新表(`account_id INTEGER PRIMARY KEY`,其余列不变)→ 无损搬运旧行(id → account_id)→ DROP legacy。
4. Room `@Database(version = 2)` + 手写 `Migration(1, 2)` 执行上述 SQL。

### 1.2 实体/DAO 变更

- `AccountEntity` 改映射到 `accounts` 表;`SyncStateEntity` 主键改 `accountId`。
- **活跃账号存于 `settings.payload.active_account_id`**(SettingsDao 增加 JSON 键,与 key_names 共存;沿用 `_raw_payload/_write_payload` 合并写模式)。
- 新增账号管理方法(SyncDao 或独立 AccountDao),全部对齐桌面 db.py:
  - `getActiveAccountId()`:活跃账号未登录但有其他已登录账号时自动让位给最小已登录 id;全部未登录维持原选择(保证欢迎页登录落到既有行);无任何账号返回 0。
  - `setActiveAccount(id)`、`listAccounts()`(id 升序)、`countAccounts()`、`countLoggedInAccounts()`
  - `addAccount(token, hint, switch=true)`:相同 token(TRIM 后)视为同一用户,更新 workspace 提示后返回其 id;否则插入新行,name = hint 前 50 字符或 `"User N"`,并确保 state 行存在
  - `renameAccount(id, name)`:strip + 截断 50 字符,空名返回 false
  - `deleteAccount(id)`:级联删除该账号 usage_records + usage_sync_state + accounts 行;若删除的是活跃账号,活跃位移到剩余最小 id;无剩余则清除 active_account_id 键
  - `clearAccount()`(退出登录):保留账号行,清 token/resolved_workspace_id,删该账号 records,重置该账号 sync state
  - `saveToken(token, ws)`:重登语义 —— 更新活跃账号凭证并重置其增量游标(deepest_page_fetched=-1)
- **UsageDao 全部查询加 `accountId: Int` 参数**:totals/dailyStats/todayTrend/modelStats/sessionStatsPage/usageRecordsPage/pruneOldRecords/insertUsageRecords/listModels/recordBounds 等 WHERE 注入 `account_id = :accountId`(RawQuery 动态拼接处同样注入)。

## 2. 同步引擎与仓库层(DashboardRepository,对齐 server.py v2.0.0)

### 2.1 配额缓存分槽

- `quotaCache` 由单槽改为 `Map<Int /*accountId*/, QuotaCache>`;防重入布尔改 `MutableSet<Int>`;TTL 仍 30s。
- `ensureQuota()` 仅针对当前活跃账号刷新;失败也写 null 缓存(TTL 内不重试)。

### 2.2 同步流程重构

- 抽出私有方法 `syncOneAccount(aid, name, mode, windowDays)`:承载现有单账号逻辑(工作区解析、分批拉取、窗口裁剪、状态落库),显式传入账号上下文:
  - token/workspace 从该账号行读取;resolved_workspace 写回该账号;
  - 记录写入带 aid;prune 按 aid;updateSyncState 按 aid。
- `syncUsage(mode)`:
  - `full`:仅活跃账号(无 token 则"未登录");
  - `incremental`:顺序轮询所有已登录账号;任一账号失败即中断返回(桌面 parity);
  - 全局 running 守卫保持单飞;`totalInserted/pages` 跨账号累计;partial 聚合判定照抄桌面。
- `SyncProgress` 增加 `account: String = ""` 字段(当前正在同步的账号名),UI 可展示。

### 2.3 其他仓库层改动

- key_names 缓存改为**合并写入**:`merged = get(); merged += fresh; save(merged)`(key_id 全局唯一,多账号各补各条目)。
- 新增 API:`accounts()`、`switchAccount(id)`(校验存在且已登录)、`renameAccount(id, name)`、`deleteAccount(id) -> remainingCount`、`addAccountLogin(token, hint)`、`logoutActive()`。
- `loadDashboard` 的 totals 等聚合全部传活跃账号 id;`loggedIn` 口径改为"存在已登录账号"(对齐桌面 `/api/dashboard`)。

### 2.4 MainViewModel

- 登录模式:`pendingLoginMode: "add" | "relogin"`。设置页「添加用户」与主页胶囊菜单均以 add 打开 LoginScreen;`completeLogin(token, hint)` 按模式分别调 `addAccountLogin(switch=true)` 或 `saveToken`。
- 新增状态:`accounts: List<AccountInfo>`、`activeAccountId: Int`;切换/删除/退出/登录成功后统一 `refreshAccounts() + loadDashboard()`(记录/会话页数据置空重拉)。
- `checkState()` 使用新的活跃账号解析;所有账号均未登录时回欢迎页。

## 3. UI(Compose)

### 3.1 设置页用户管理(SettingsScreen 改造)

- 原「账户」卡片重构:标题行 `OpenCode 账户` + 右侧「添加用户」TextButton(add 模式进登录页)。
- 用户列表(仅显示 has_token 账号,退出即移除语义):每行显示 名称(+「当前」徽标)/ workspace · 已登录,操作按钮:
  - 当前账号:`重新登录`(relogin 确认弹窗)/ `重命名` / `退出登录`(危险确认)
  - 其他账号:`切换为当前` / `重命名` / `删除`(危险确认:"确定删除用户「X」?本地用量数据将一并清除")
- 重命名弹窗:TextField 预填现名,≤50 字符。
- 无已登录账号时列表显示空态文案;全部退出 → showLogin 欢迎页。
- 移除旧的单账号四行(登录状态/工作区/登录方式/退出登录)。

### 3.2 主页头部账号胶囊(新增)

- HomeScreen 标题旁小徽标:`账号名 · N`(N=已登录数,>1 时显示);点击弹出 `ModalBottomSheet`:
  - 已登录账号列表,当前账号前 ✓;点击即 `switchAccount(id)` 并刷新;
  - 底部固定「管理用户」入口 → 导航到设置页 tab。
- 切换成功 toast「已切换账号」。

### 3.3 模型图标移植(v1.0.3 对齐)

- 桌面 `app/web/icons/*.svg` 共 13 个转为 VectorDrawable XML 放 `res/drawable/`(`ic_model_deepseek/glm/gpt/gpt_color/grok/grok_color/hy/kimi/meta/mimo/mimo_color/minimax/qwen.xml`)。
- 新增 `ui/components/ModelIcons.kt`:
  - 映射表 `{deepseek, glm, gpt, grok, kimi, meta, mimo, minimax, qwen, muse→meta}`;
  - 取模型名小写首段(split "-")[精确匹配];未命中且 `startsWith("hy")` → hy(**v1.0.3 修复**);再兜底 deepseek;
  - 深色主题下 gpt/grok/mimo 用 `-color` 变体(与桌面 modelIcon 一致);
  - 渲染为 16dp Image(painterResource)。
- 应用位置:统计页模型排行列表行、记录页模型单元格。

### 3.4 i18n 与版本

- Strings.kt 中英各补 ~15 条:setUsers/addUser/addUserTip/userSwitchTip/switchTo/currentUserBadge/renameBtn/renameTitle/deleteUser/deleteUserConfirm/userDeleted/userRenamed/switchedAccount/noUsers/logoutUserConfirm/loggedOut/reloginConfirmNew/save 等,中文文案照抄桌面 I18N。
- `android/app/build.gradle.kts`:`versionCode = 4`,`versionName = "2.0.0"`。

## 4. 测试策略

- **Room Migration 测试**:`MigrationTestHelper` 建 v1 库灌样例数据 → runMigrationsAndValidate(v2) → 断言 accounts 拷贝、usage_records.account_id 默认 1、sync_state 主键迁移无损。
- **DAO 多账号测试**(instrumented 或 Robolectric):
  - 两账号各插记录 → 各自 totals/modelStats/分页互不串扰;
  - addAccount 相同 token 去重;rename 截断 50;deleteAccount 级联 + 活跃位回退最小 id;
  - getActiveAccountId 让位逻辑(活跃未登录→最小已登录;全未登录→维持)。
- **同步引擎测试**:双账号 incremental 轮询顺序与各自游标;full 仅活跃账号;单账号失败中断。
- **图标映射单测**:hy/hy2/hy3 等前缀→hy、muse→meta、未知模型→deepseek、深色变体选择。
- 构建验证:`./gradlew assembleDebug testDebugUnitTest`。

## 5. 明确不做(YAGNI)

- 不做安卓端顶栏下拉菜单的跨页面常驻(仅主页胶囊入口)。
- 不移植桌面端登录窗 watcher/evaluate_js 兜底机制(安卓为进程内 WebView 登录,无跨窗口问题)。
- 不改 UpdateApi 的比较逻辑(版本号升级后自然生效)。
