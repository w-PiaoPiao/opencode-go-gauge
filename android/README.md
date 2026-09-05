# GoGauge Android — OpenCode Go / Command Code GOAT 用量仪表盘(安卓版)

与桌面版(同仓库根目录)功能一致的安卓原生应用:Kotlin + Jetpack Compose + Room + MPAndroidChart。UI 按手机屏幕重新布局(单列卡片、底部导航、更大字号),保证小屏可读性。

## 功能(与桌面版一致,含 Command Code GOAT)

- **配额窗口实时监控**:滚动 5 小时 / 每周 / 每月,进度条 + 剩余比例 + 重置倒计时
- **用量概览**:缓存命中率 / 命中量 / 总 TOKEN(含缓存命中)/ 请求数 / 费用 / 会话数
- **今日趋势**:24 小时输入 / 输出柱状图
- **用量统计**:Token 构成(输入 / 输出 / 推理 / 缓存读 / 缓存写 / 会话)、模型用量环形图 + 排行(输入 / 输出 / 成本切换)、费用 / 请求 / 总 TOKEN 三线趋势
- **会话历史**:按会话聚合,卡片列表 + 分页
- **使用记录**:请求级明细卡片列表 + 分页 + 模型筛选
- **账户总览面板**(v2.1.0):设置中可开关,底部导航显示入口;今日合计 KPI(总请求 / 总 TOKEN / 总输入 / 总费用)、账号卡片(配额三窗口 + 今日用量 + 24h 迷你趋势)、7 日费用趋势对比(跨账号合计三条线);非活跃账号配额后台刷新,退出账号即清理其配额缓存
- **Command Code GOAT 支持**:登录 commandcode.ai 账号,5 小时 / 每周 / 每月三窗口配额、请求级明细、全周期聚合统计(统计口径以 usage_charts 聚合为准),账号带 GOAT 来源徽标
- **内置 WebView 登录**:加载官方授权页,登录后自动捕获 auth cookie 与工作区(GOAT 为 session_token)
- **自动同步**:增量 / 全量;前台按 1 / 5 / 15 / 30 分钟定时,后台 WorkManager 每 15 分钟(安卓系统最小周期)
- **双主题**:亮色 / 深色一键切换;中英双语界面
- **本地优先**:数据保存在应用私有目录 SQLite(`filesDir`),token 仅用于同步官方接口

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
```

> 说明:`GRADLE_USER_HOME` 指向工作区是因为本环境 `~/.gradle` 不可写;普通开发机可省略。

## 与桌面版的关系

- **解析逻辑同源**:`data/remote/QuotaParser.kt`、`UsageParser.kt` 是桌面版 `opencode_api.py` 的 1:1 移植(正则逐条对应,含字段顺序双兼容);`data/db/UsageDao.kt` 的 SQL 与 `db.py` 逐句对应。若 opencode.ai 接口格式变化,需同步修改两处。`data/remote/CommandCodeApi.kt` 对应桌面版 `commandcode_api.py`(GOAT 数据源)。
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
