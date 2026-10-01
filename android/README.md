# GoGauge Android — OpenCode Go / Command Code GOAT 用量仪表盘(安卓版)

与桌面版(同仓库根目录)功能一致的安卓原生应用:Kotlin + Jetpack Compose + Room + MPAndroidChart。UI 按手机屏幕重新布局(单列卡片、底部导航、更大字号),保证小屏可读性。

## 功能(与桌面版一致,含 Command Code GOAT)

- **配额窗口实时监控**:滚动 5 小时 / 每周 / 每月,进度条 + 剩余比例 + 重置倒计时
- **用量概览**:缓存命中率 / 命中量 / 总 TOKEN(含缓存命中)/ 请求数 / 费用 / 会话数
- **今日趋势**:24 小时输入 / 输出柱状图
- **用量统计**:Token 构成(输入 / 输出 / 推理 / 缓存读 / 缓存写 / 会话)、模型用量环形图 + 排行(输入 / 输出 / 成本切换)、费用 / 请求 / 总 TOKEN 三线趋势;环形图图例点击可排除/恢复模型,总卡 / Token 构成 / 排行 / 趋势全局联动重聚合(排除仅作用于统计页,切换账号自动清空)
- **会话历史**:按会话聚合,卡片列表 + 分页
- **使用记录**:请求级明细卡片列表 + 分页 + 模型筛选
- **账户总览面板**(v2.1.0):设置中可开关,底部导航显示入口;今日合计 KPI(总请求 / 总 TOKEN / 总输入 / 总费用)、账号卡片(配额三窗口 + 今日用量 + 24h 迷你趋势)、7 日费用趋势对比(跨账号合计三条线);非活跃账号配额后台刷新,退出账号即清理其配额缓存
- **Command Code GOAT 支持**:登录 commandcode.ai 账号,5 小时 / 每周 / 每月三窗口配额、请求级明细、全周期聚合统计(统计口径以 usage_charts 聚合为准),账号带 GOAT 来源徽标
- **多种登录方式**(对齐桌面):内置 WebView 加载官方授权页自动捕获会话 cookie(opencode `__Host-console_session` / 旧 `auth` 兼容,GOAT 为 session_token);也可在系统浏览器完成登录后**粘贴 Cookie** 直接登录(先拉配额校验凭证有效再落库);打开登录页前清残留会话(防被旧凭证带离登录入口),轮询中持续自愈(commandcode 偏离 /signin 自动拉回、GitHub 2FA 后卡无关页面自动续跑授权入口),重新登录后配额缓存随凭证失效立即重拉
- **应用内更新**:检查 GitHub Releases(仅认 `-android` 条目),发现新版可直接下载 APK(校验 GitHub SHA-256 摘要)并触发系统安装器;未授权"安装未知应用"时引导到系统设置
- **自动同步**:增量 / 全量;前台按 1 / 5 / 15 / 30 分钟定时,后台 WorkManager 每 15 分钟(安卓系统最小周期)
- **双主题**:亮色 / 深色一键切换;中英双语界面
- **本地优先**:数据保存在应用私有目录 SQLite(`filesDir`),token 仅用于同步官方接口,并以 Android Keystore 不可导出密钥做 AES-256-GCM 加密落库(对齐桌面 DPAPI/Keychain;旧明文数据读取自动兼容,下次写入即加密)

## 技术栈

Kotlin 2.2 · Jetpack Compose (Material 3) · Room 2.7 · OkHttp · kotlinx.serialization · MPAndroidChart · WorkManager

## 构建

环境要求:JDK 17+、Android SDK(platform 36、build-tools 36)、Gradle 8.13(直接使用仓库外的 `../../tools/gradle-8.13/bin/gradle`,不依赖 wrapper)。

```bash
# 首次:SDK 路径
echo "sdk.dir=$ANDROID_HOME" > local.properties

# 构建 debug APK
GRADLE_USER_HOME=$PWD/../../.gradle-home ../../tools/gradle-8.13/bin/gradle assembleDebug
# 产物:app/build/outputs/apk/debug/app-debug.apk

# 构建 release APK(使用工作区 debug keystore 签名,个人侧载用)
GRADLE_USER_HOME=$PWD/../../.gradle-home ../../tools/gradle-8.13/bin/gradle assembleRelease

# 单元测试(解析器 / 格式化,fixtures 对齐桌面版正则)
GRADLE_USER_HOME=$PWD/../../.gradle-home ../../tools/gradle-8.13/bin/gradle testDebugUnitTest

# Instrumented 测试(Keystore token 加密 / Room DAO 集成; 需连接设备或模拟器,
# 多设备时用 ANDROID_SERIAL=emulator-5556 限定目标)
GRADLE_USER_HOME=$PWD/../../.gradle-home ../../tools/gradle-8.13/bin/gradle connectedDebugAndroidTest
```

> 说明:`GRADLE_USER_HOME` 指向工作区是因为本环境 `~/.gradle` 不可写;普通开发机可省略。

## 与桌面版的关系

- **解析逻辑同源**:`data/remote/QuotaParser.kt`、`UsageParser.kt` 是桌面版 `opencode_api.py` 的 1:1 移植(2026-09 控制台改版后的 `/console/api` JSON 解析:配额 `go/status`、明细 `request-logs` 游标分页、工作区 `orgs`、Key 名称 `service-accounts`);`data/db/UsageDao.kt` 的 SQL 与 `db.py` 逐句对应。若 opencode.ai 接口格式变化,需同步修改两处。`data/remote/CommandCodeApi.kt` 对应桌面版 `commandcode_api.py`(GOAT 数据源)。
- **升级提示**:opencode.ai 改版后旧会话凭证(`auth=…`)已失效,升级后 opencode 账号会回到欢迎页引导重新登录(仅清凭证,历史记录保留);commandcode 账号不受影响。
- **平台适配**:
  - 系统托盘/关闭最小化 → 安卓无此概念,由后台 WorkManager 同步替代
  - 同步间隔 1/5 分钟仅前台精确生效,后台最低 15 分钟(系统限制)
  - 欢迎页「退出应用」按钮 → 安卓移除(系统返回即退出)

## 目录结构

```
app/src/main/java/io/github/yphyphyph/gogauge/
├── MainActivity.kt / GoGaugeApp.kt   # 入口 + 依赖装配 + WorkManager 调度
├── auth/                             # 登录 URL 构造、cookie 提取(移植 auth.py)
├── data/
│   ├── db/                           # Room 实体/DAO(schema 与 db.py 一致)
│   ├── remote/                       # OpenCode API + 配额/用量正则解析器(移植 opencode_api.py)
│   ├── model/                        # 数据模型
│   └── repository/                   # DashboardRepository:同步引擎/缓存/聚合(移植 server.py)
├── sync/                             # WorkManager 后台同步
├── ui/
│   ├── MainViewModel.kt              # 共享状态(语言/主题/货币/分页/自动同步)
│   ├── Strings.kt                    # 中英文案(移植 app.js I18N)
│   ├── components/                   # 卡片/KPI/配额进度/Pill/图表包装
│   ├── home/ stats/ records/ settings/ overview/ auth/   # 六个页面
│   └── nav/                          # 底部导航(总览入口按设置开关显隐)
└── util/Fmt.kt                       # 格式化(移植 app.js fmt*)
```

## 验证记录(模拟器 Emulator_API_35, API 35 / Android 15)

- [x] 欢迎页 → WebView 登录页流程
- [x] 首页:配额卡 / 6 KPI / 今日趋势图(注入 360 条模拟数据验证)
- [x] 统计页:4 KPI / Token 构成 / 模型环形图 / 排行 / 趋势图
- [x] 记录页:会话列表(25 会话)/ 使用记录 / 分页 / 模型筛选
- [x] 设置页:账户 / 自动同步 / 外观 / 数据 / 更新 / 关于
- [x] 账户总览页(v2.1.0):开关显隐 / 今日合计 KPI / 账号卡片配额与今日用量 / 7 日趋势对比(单测 + 构建验证, 多账号实机数据待回归)
- [x] 深色模式切换、中英语言切换
- [x] 14 个单元测试通过(解析器双格式 / 字段顺序 / 格式化边界)

## 全量审查修复与兼容性回归(2026-10)

针对"Android 13 及以下统计全 0 / CC 明细全丢"等审查发现做了一轮全量修复;
回归环境: 单元测试(JVM) + instrumented 测试(TestAPI33 模拟器, API 33 / Android 13) + 冷启动冒烟。

- [x] **旧版日期解析(根因)**: `Instant.parse` 的 ISO_INSTANT 在 OpenJDK 12 之前只接受
      字面 `Z`(JDK-8166138), Android 8.0–13 的 libcore 基于 OpenJDK ≤11 —— 新增统一
      宽容解析入口 `util/IsoTime.kt parseIsoInstant` 并替换全部调用点;
      API 33 实测: 修复前 `+00:00` 与 `Z` 双双解析失败, 修复后两种格式均通过
- [x] **CC 月度周期归一化**: `savePeriodBounds` 落库前 ISO → UTC "yyyy-MM-dd HH:mm:ss"
      归一化(桌面 `_parse_utc_naive` parity), 读取侧同步宽容; API 33 实测归一化正确
- [x] **旧版存量数据回填**: 升级后一次性把历史行 `local_date=NULL` 补成正确本地日
      (SQL 口径与 Kotlin `localDateOf` 一致, instrumented 测试覆盖) —— 旧设备升级后
      历史统计立即恢复, 无需等待重新同步
- [x] **token 加密落库**: Android Keystore AES-256-GCM(`data/db/TokenCipher.kt`),
      Room DAO 层自动加解密, 旧明文平滑兼容; instrumented 测试覆盖往返/随机 IV/
      损坏不崩/DAO 集成(落库密文、读取明文)
- [x] 同步 running 标志卡死、锁顺序反转、翻页上限静默截断、账号周期键残留、
      更新包摘要 fail-closed、登录页返回键、记录页下拉刷新、错误三态与重试、
      设置快速连写覆盖、WebView 清理竞速与加载失败重试、点击目标 ≥44dp 等
- [x] 83 个单元测试 + 7 个 instrumented 测试全部通过; API 33 模拟器冷启动无崩溃
