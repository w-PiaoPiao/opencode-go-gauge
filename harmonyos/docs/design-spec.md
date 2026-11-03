# GoGauge HarmonyOS — 设计规范 / 改造契约 (v1.0)

> 本文是鸿蒙版 UI 改造的唯一契约。Lead 实现 `Theme.ets` / `Cards.ets` / `Charts.ets` /
> `AppRoot.ets` / `HomePage.ets` / `Index.ets` / `LoginPage.ets`；页面成员实现
> `StatsPage.ets` / `RecordsPage.ets` / `SettingsPage.ets`；平台成员实现 `EntryAbility.ets`
> 窗口/字体/图标资源。任何接口变更以本文 + Lead 消息为准。

## 0. 目标与原则

1. **手机布局对标安卓版**（`android/app/src/main/java/.../ui/**`）：底部 Tab、页头（标题 +
   账号胶囊 + 刷新）、周期胶囊行、卡片流、编辑式数据格、下拉刷新。
2. **平板 / PC(2in1) 布局对标桌面版**（`app/web/index.html` + `app/web/style.css`）：
   顶部工具栏（品牌/同步状态/主题/刷新/更新时间/账号胶囊）、左侧图标导航栏、
   页头右侧周期胶囊、内容多列栅格、记录页表格化。
3. **一套品牌视觉**：采用安卓版的暖色「Claude 令牌」体系（象牙底 / 暖白卡 / 珊瑚主色 /
   发丝线），平板与 PC 沿用同一色彩，不套桌面版的紫色皮肤（桌面版是另一个产品形态的皮肤；
   本应用是移动端产品的鸿蒙版）。布局结构照搬桌面版即可满足"参考桌面版"。
4. **鸿蒙原生适配**：一多自适应（断点）、ArkUI 原生动效（弹性/过渡）、下拉刷新、
   2in1 窗口最小尺寸、系统级悬停/焦点反馈、键盘快捷键、系统深色/浅色、安全区、
   启动窗口、应用图标。不得照搬 Android Material 组件外观（不要 Material 底部导航条样式，
   用鸿蒙观感的底部 Tab），也不得照搬桌面版的自绘窗口按钮（2in1 用系统窗口装饰）。

## 1. 设计令牌（`ui/theme/Theme.ets`，静态方法）

> 所有颜色只能来自 Theme，页面/组件禁止硬编码 hex（图表色可由 Theme 提供）。

### 1.1 亮色
| token | 值 | 用途 |
| --- | --- | --- |
| bg | `#F0EEE6` | 画布（页面底） |
| surface | `#FAF9F5` | 卡片/顶栏/侧栏 |
| tile | `#EFE9DE` | 卡内瓷砖（KPI/子块） |
| tileStrong | `#E8E0D2` | 进度轨道/分段容器/胶囊底 |
| border | `#E6DFD8` | 1px 发丝线 |
| text | `#141413` | 主文字 |
| sub | `#6C6A64` | 次级文字 |
| faint | `#87867F` | 三级文字/占位 |
| primary | `#C96442` | 珊瑚主色 |
| primarySoft | `#F4E8E1` | 主色浅底 |
| blue | `#7B96B8` | 数据蓝 |
| green | `#5DB872` | 成功/命中 |
| cyan | `#5DB8A6` | teal |
| amber | `#E8A55A` | 警告/费用 |
| red | `#C64545` | 错误 |
| violet | `#9A7AA0` | 推理/会话 |
| slate | `#87867F` | 中性 |

### 1.2 暗色
bg `#1F1E1B` · surface `#252320` · tile `#2C2A26` · tileStrong `#33302B` · border `#3B3833`
text `#FAF9F5` · sub `#A09D96` · faint `#8E8B82` · primary `#D97757` · primarySoft `#3A2C26`
blue `#8FA9C7` · green `#79C389` · cyan `#79C7B5` · amber `#EBB275` · red `#D96A6A`
violet `#B79ABE` · slate `#8E8B82`

### 1.3 图表语义色（亮暗共用）
input `#7B96B8` · output `#7D8B6A` · reasoning `#9A7AA0` · cache `#5DB8A6` ·
cost `#D4A27F` · extra `#C96442`

### 1.4 热力图档位（0 档 = tile）
亮色 `#E2C0AE #D29880 #BF7154 #A8492B`；暗色 `#564136 #815846 #B07157 #E08A68`

### 1.5 圆角 / 间距 / 阴影
- 卡片圆角 12vp；瓷砖 8vp；胶囊全圆；按钮 8vp。
- 卡片内边距 14vp（紧凑 12vp）；栅格间距 10vp（手机）/ 12vp（宽屏）；页面内边距
  手机 14vp 水平 + 12vp 垂直；宽屏 18/14vp。
- 阴影：仅顶栏/侧栏/卡片用极轻阴影 `{radius: 6, color: '#0D000000', offsetY: 2}`；
  暗色下不用阴影，靠 border。
- 触控目标 ≥ 44vp（手机），PC 可 32vp。

### 1.6 字体
- 标题衬线：注册字体族 `GgSerif`（`gg_serif_sc_regular.otf`，从 `android/app/src/main/res/font/`
  复制到 `resources/rawfile/fonts/`）。用法：`.fontFamily('GgSerif')`。
  * 标题类（页面大标题、卡片标题 titleSmall/titleMedium）用衬线；数字/KPI 不用衬线。
- 正文：系统字体（HarmonyOS Sans）。
- 数字：系统字体 + `fontFeature('"tnum"')` 可用则用，不可用忽略；金额/Token 用 `Fmt`。
- 字号阶梯：页面标题 24/30（手机 22）；卡片标题 15/16；正文 14；次级 12；说明 11；标签 11/12。
- 行高：正文 1.4 倍左右（20/14）。

## 2. 组件契约（Lead 实现，页面只调用）

> ArkUI struct 名与参数即契约。`@Prop` 表示 immutable 输入；`@BuilderParam` 为尾随内容。
> 默认值必须存在，避免页面调用时缺参。所有组件置于 `ui/components/`。

```ts
// Cards.ets
GgCard({ title?: string, hint?: string, dense?: boolean }) { ... }  // 仅一个 @BuilderParam content（尾随闭包）
         // ⚠️ 禁止 content: this.xxx / trailing: this.xxx 传 @Builder 值：ArkUI 子组件会 bind(自身 this)，
         //    builder 内 this 取不到父页面成员 → 运行时 "xxx is not callable" jscrash。
         //    需要卡头右侧控件：GgCard({}) 内自建 Row 头 + 调 this.trailingBuilder()。

CardHeader({ title: string, hint?: string }) { ... }  // trailing 用尾随闭包；同样不可传 builder 值
Hint({ text: string })
KpiCard({ label: string, value: string, sub?: string, accent?: string })   // 瓷砖卡
EditorialCell { label: string; value: string; sub: string; accent: string }
EditorialGrid({ cells: EditorialCell[], columns?: number })  // 手机 2 列 / 宽屏 3 或 6 列
QuotaCard({ label: string, usedPercent: number, remainingText: string,
            resetText: string, accent: string, accentEnd?: string, forecastText?: string })
PillRow({ options: Array<[string, string]>, selected: string, onSelect: (v: string) => void })
SegButtons({ options: Array<[string, string]>, selected: string, onSelect: (v: string) => void })
AccountChip({ name: string, count?: number, onTap: () => void })          // 手机页头胶囊
ModelIcon({ model: string, size?: number })
Loader({ text?: string })            // 居中 LoadingProgress + 文案
EmptyState({ text: string })
QuotaSkeleton()                      // 3 个骨架条
ErrorCard({ title: string, detail: string, retryText: string, onRetry: () => void })
Pager({ page: number, total: number, pageSize: number,
        prevText: string, nextText: string, pageInfo: string,
        onPrev: () => void, onNext: () => void })
```

```ts
// Charts.ets
BarChart24h({ hours: HourStat[], totalMode?: boolean, height?: number })   // 24h 双柱 + 网格
DonutChart({ segments: ChartSegment[], centerValue: string, centerLabel?: string, size?: number })
TrendLineChart({ series: TrendSeries[], labels: string[], height?: number })
ModelTrendChart({ days: string[], series: TrendSeries[], height?: number })  // 面积堆叠简化版
CalendarHeatmap({ days: HeatDay[], ramp: string[], maxValue?: number })     // 7 行 × N 周
```

```ts
// ui/shell/…（AppRoot 内部）
LogoTile({ size?: number })          // 圆角仪表盘图标
```

- 图表统一为 ArkUI `Canvas`（`CanvasRenderingContext2D`）或布局原生绘制；必须在
  `onAreaChange` 后重绘，宽屏/手机同一组件自适应；动画：数据首次出现时 300–450ms
  `Curve.EaseOut`，减少动效不受支持时不阻塞。
- 组件不得读取 Repo/DB；数据全部由页面传入。

## 3. 外壳与断点（`ui/AppRoot.ets`）

### 3.1 断点
以根容器 `onAreaChange` 的宽度（vp）判定：
- `compact`：`width < 600` → 手机形态（底部 TabBar）
- `medium`：`600 ≤ width < 840` → 平板竖屏 / 分屏 / 大屏手机横屏：**桌面式外壳**（顶栏 + 左侧图标导航），
  内容页仍按自身宽度走单列/少列栅格（页面内部 840vp 才切多列）
- `expanded`：`width ≥ 840` → 平板横屏 / 2in1：桌面式外壳 + 内容多列栅格

> 壳层断点常量：`Dimens.SHELL_WIDE_BREAKPOINT = 600`；内容栅格断点：`Dimens.WIDE_BREAKPOINT = 840`。
- 栅格列数由各页 `GridRow` 断点参数决定（见 3.3），不要只靠壳层宽度。

### 3.2 compact（手机）
- 结构：`Column { 内容区 .layoutWeight(1), 底部 TabBar }`。
- 底部 TabBar：`Tabs`（`barPosition: BarPosition.End`）或自绘 Row；高度 56vp + 底部安全区；
  surface 底 + 顶部 1px border；4 个 Tab：首页/统计/记录/设置（图标 22vp + 11fp 文案）；
  选中 = primary 色 + 图标上浮/弹性回弹 150ms；未选中 = faint；点击切换带
  `fade+translateY(6vp)` 200ms 过渡；支持左右滑动切页（Tabs 原生）。
- 页内：每页自带页头：`Row { Text(title 22fp serif bold), Blank, AccountChip, 刷新图标按钮 }`；
  周期胶囊行在页头下方全宽；页面不再有全局顶栏；登出/主题等全部在设置页。
- 下拉刷新：`Refresh({ refreshing: $$syncing })` 包裹内容，`onRefreshing` 触发增量同步；
  顶部指示器用系统样式（primary 色）。
- 安全区：底部 TabBar 处理 navigation bar 安全区；状态栏由系统窗口背景承载
  （`windowStage` 设置窗口背景为 bg，不做全屏沉浸绘制）。

### 3.3 medium / expanded（平板 / PC）
- 结构：`Column { TopBar(48vp), Row { SideRail(64vp), 内容区 .layoutWeight(1) } }`，
  整页 surface/bg 分层：TopBar+SideRail 用 surface，内容区 bg。
- TopBar 左：24vp 仪表盘图标 + `GoGauge`（14fp bold）+ 同步摘要（12fp faint，如
  "上次同步 刚刚 · 本周 15,736 请求 / 明细 365 条"）；右：主题胶囊、刷新胶囊（amber 描边）、
  更新时间 chip、账号胶囊（含账号数徽标）。PC 不画最小化/关闭按钮（用系统窗口装饰）。
- SideRail：宽 64vp（expanded 可 72vp），图标 22vp + 10fp 文案，垂直排列；顶部留 12vp；
  选中 = primary + primarySoft 圆角块 + 左侧 3vp 指示条（用 animateTo 移动）；hover =
  轻高亮；离开选中态有 150ms 过渡。底部固定一个设置/关于入口（避免与内容抢主位）。
- 页头（宽屏）：`Row { 标题(20fp serif), Blank, 周期胶囊行 }`；卡片高度更松（内边距 16）。
- 内容栅格：
  - 统计页两行两栏：`[模型用量 | 用量趋势]`、`[日历热力图 | 模型趋势]`（列宽 1:1.6），
    `md` 下退化为单列。
  - 首页：配额三块并排（`GridRow` sm→1 列、md→3 列）；KPI 6 格 `md` 3 列、`lg` 6 列；
    今日趋势整行。
  - 记录页：宽屏用表格（会话表 8 列 / 记录表 9 列，列宽见桌面 CSS），手机用卡片行。
- 窗口：2in1 最小窗口 720×560vp（EntryAbility `setWindowLimits`）；窗口拉伸时布局实时重排；
  支持 `Ctrl+1..4` 切页、`Ctrl+R`/`F5` 刷新。
- 悬停：nav/卡片/按钮 `hoverEffect(Highlight)`；可点击元素配 `onHover` 记录 hover 状态变色。
- 键盘焦点：可点击项 `focusable(true)` + `onFocus/onBlur` 边框（PC）。

### 3.4 动效规范（鸿蒙独有/原生）
- 页面切换：`animateTo({ duration: 220, curve: Curve.EaseOut })` 做 opacity+translateY。
- Tab 选中：图标 scale 1→1.12→1 + 颜色过渡，`Curve.Spring` / `curves.springMotion()`。
- 卡片入场：首帧 opacity 0/translateY 8 → 1/0，220ms，逐卡片 30ms 阶梯延迟（用数据状态控制）。
- 配额进度条：数据到达后 width 0→used%，450ms `Curve.EaseOut`；环形进度同理。
- 刷新：Refresh 原生回弹；同步中按钮图标旋转（`rotate` + `animation`）。
- 主题切换：颜色 180ms 过渡（可用 `.animation({duration:180, curve: Curve.EaseInOut})`）。
- 触觉：不引入 vibrator（避免额外权限）；用视觉反馈代替。
- 动效降级：读取 `AppPrefs` 无降级设置时一律启用；不得用阻塞式动画影响列表滑动。

## 4. 页面布局契约

### 4.1 HomePage（对标 Android HomeScreen / 桌面首页）
手机：
1. 页头（标题 `homeTitle` + 账号胶囊 + 刷新）。
2. 周期胶囊 `today/7d/30d/month/all`（`PillRow`，全宽横向滚动）。
3. 配额窗口：3 张 `QuotaCard` 堆叠（5h 滚动=primary→amber 渐变、每周=cyan→green、
   每月=amber→red；含剩余%、已用%、重置倒计时、预测小字；无数据时 QuotaSkeleton，
   拉取失败时 ErrorCard + 重试）。
4. `GgCard`「用量概览」：`EditorialGrid` 6 格（缓存命中率/缓存命中量/总 TOKEN/总请求/
   总费用/会话数；每格 semantic 色点 + 主数值 + 副文案）。
5. `GgCard`「今日趋势 24 小时」：`SegButtons`（不含缓存/含缓存）+ `BarChart24h`。
6. 下拉刷新包裹全部内容。
宽屏（桌面版首页结构）：
- 页头标题左、周期胶囊右；配额三块 `GridRow` 一行三列；概览 6 格 md=3/lg=6 列；
  今日趋势整行（图表高 250）。
- 桌面版首页额外的「明细卡」区（今日输入/输出/缓存等 6 小格）可并入 EditorialGrid，不重复实现。

### 4.2 StatsPage（对标 Android StatsScreen / 桌面统计页）
1. 页头 + 周期胶囊（默认 7d；today/7d/30d/month/all）。
2. 4 张 KPI 卡（总费用 amber/总请求 blue/总 TOKEN violet/缓存命中率 green；手机 2×2，
   宽屏 4 列并排）。
3. `GgCard`「Token 构成」：`DonutChart`（输入未命中/输出/推理/缓存读）+ 右侧/下方
   6 格 `EditorialGrid`（输入/输出/推理/缓存读/缓存写/会话数）。
4. `GgCard`「模型用量」：`SegButtons`（输入/输出/成本）+ `DonutChart` 模型占比 +
   前 3 排行列表（`ModelIcon` + 模型名 + 请求/命中率 + 维度数值）。
5. `GgCard`「用量趋势」：`TrendLineChart`（费用/请求/TOKEN 三序列 + 图例）。
6. `GgCard`「日历热力图」：`SegButtons`（TOKEN/请求/成本）+ `CalendarHeatmap`。
7. `GgCard`「模型用量趋势」：`ModelTrendChart`（无数据整卡隐藏）。
宽屏：KPI 4 列；`[模型用量 | 用量趋势]` 两栏 + `[热力图 | 模型趋势]` 两栏。

### 4.3 RecordsPage（对标 Android RecordsScreen / 桌面记录页）
- 页头（`recordsPage`）+ 下拉刷新。
- 手机：两张卡（会话用量 / 使用记录），每张卡片头带总数 hint；行卡片式：
  主行（Key/会话 id + 最后时间/费用）+ 次行（输入/输出/推理/缓存/请求数），点击行无操作；
  底部 `Pager`（第 x / y 页，上一页/下一页，每页 10 条）。
- 宽屏：同两张卡但内部渲染为表格（会话 8 列：Key/会话/最后使用/输入/输出/推理/请求/成本；
  记录 9 列：Key/时间/模型/输入/输出/推理/缓存读/缓存写/费用），表头 faint 11fp，
  行 hover 高亮；列宽百分比参考 `app/web/style.css` 的两表模板；表格撑满卡片高度，
  底部 pager。
- 空数据/错误分别显示 EmptyState / ErrorCard + 重试。

### 4.4 SettingsPage（对标 Android SettingsScreen / 桌面设置页）
分组卡片（每组一个 `GgCard`，行式 `SettingRow` 组件可由页面内部 @Builder 实现）：
1. 账户管理：账号列表（名称/工作区/当前徽标/重命名/重登/删除）、添加账号（跳登录页）。
2. 自动同步：开关（autoSync）、同步间隔胶囊、同步范围胶囊、立即全量同步、按范围清理。
3. 外观：主题（浅色/深色）、语言（中文/English）、货币（USD/CNY）。
4. 更新：当前版本、检查更新（复用 UpdateApi）。
5. 关于：应用介绍、功能列表、开源仓库、隐私说明。
6. 调试（仅 debug 构建）：注入/清除模拟数据、演示模式入口（见 §6）。
- 宽屏：两列分组（账户/同步 | 外观/更新/关于），单列时保持与手机一致的顺序。

### 4.5 Login / Welcome（Index.ets / LoginPage.ets）
- 欢迎页：居中 Logo + GoGauge + 副标题 + 登录按钮 + 隐私提示；debug 构建额外显示
  "演示模式（截图数据）"次级按钮（见 §6）。宽屏时居中卡片式布局（最大宽 480vp）。
- 登录页：现有 Web 登录逻辑不动，只换皮肤；宽屏时居中卡片。

## 5. i18n

- 所有用户可见文案必须 `I18n.t('key')`；新增 key 由 Lead 统一写入 `common/i18n/I18n.ets`
  （ZH+EN 各一份，按字母序插入）。页面成员如缺 key，发消息给 Lead，不要自行改 I18n.ets
  （避免并发写冲突）。
- 已有 key 见 I18n.ets；本轮新增（Lead 负责）：`refresh`, `theme`, `themeLight`, `themeDark`,
  `syncing`, `lastSync`, `tabs`（home/stats/records/settings）, `range_today`, `range_7d`,
  `range_30d`, `range_month`, `range_all`, `remaining`, `usedPercent`, `resetsIn`,
  `quotaFail`, `retry`, `hit`, `miss`, `pctOfInput`, `inclCache`, `currentRange`, `avgPer`,
  `perReq`, `dedup`, `totalN`, `items`, `pageOf`, `ofPages`, `prev`, `next`, `noData`,
  `recordsPage`, `sessionUsage`, `usageRecords`, `colKey`, `colSession`, `colLastUsed`,
  `colInput`, `colOutput`, `colReasoning`, `colCacheRead`, `colCacheWrite`, `colCost`,
  `colRequests`, `heatmapTitle`, `heatmapNoData`, `mtTitle`, `trendHint`, `trendHintGap`,
  `ttPlain`, `ttTotal`, `manageUsers`, `userSwitchTip`, `addUser`, `switchedAccount`,
  `accountOverview`（暂不做总览页）, `followRange`, `overviewTitle`, `cacheWrite`,
  `newCacheWrites`, `demoMode`, `demoModeHint`, `exitDemo`。

## 5.1 隐私合规（AppGallery 审核 7.1/7.5，v1.0 起必须）

- 首次启动（localStorage 无同意标记时）弹隐私政策对话框（同意/拒绝，不得默认勾选）；
  不同意则无法进入登录/主界面；同意状态存 `AppPrefs.isPrivacyAccepted()`。
- 欢迎页底部 + 设置→关于都必须有可点击的「隐私政策」入口，跳转 `pages/PrivacyPage`。
- 隐私政策正文维护在 `common/legal/PrivacyText.ets`（与 docs/release/privacy-policy-*.md 一致）。
- 截图/演示模式下（`--ps demo 1`，仅 debug 构建）自动视为已同意，避免弹窗遮挡截图；release 构建必须正常弹窗。

## 6. 调试演示模式（截图用，仅 debug 构建）

- `EntryAbility.onCreate/onNewWant` 读取 want 参数（**aa 语法是 key/value 两个 token**：
  `aa start ... --ps demo 1 --ps lang zh --ps theme dark --ps page stats`；全部逻辑仅
  `BuildProfile.DEBUG` 为真时生效，release 完全忽略）：
  - `demo 1`：调用 `DemoSeed.run()`（创建 demo 账号 + 注入 **180 天**模拟用量 + 注入 3 个
    配额窗口），随后进入主界面。仅 `BuildProfile.DEBUG` 生效，release 忽略。
  - `lang=zh|en` / `theme=light|dark` / `page=home|stats|records|settings`：写入 AppPrefs/初始页后生效。
- 欢迎页 debug 构建显示「演示模式（截图数据）」按钮，点击同样执行 seed。
- 演示数据不得进入 release 包（`BuildProfile.DEBUG` 守卫 + 设置页调试工具已有先例）。

## 7. 文件所有权 / 并发约定

| 文件 | 所有者 |
| --- | --- |
| ui/theme/Theme.ets · ui/components/** · ui/AppRoot.ets · ui/pages/HomePage.ets · pages/Index.ets · pages/LoginPage.ets · common/i18n/I18n.ets · common/dev/** | Lead |
| ui/pages/StatsPage.ets · ui/pages/RecordsPage.ets | ui-pages 成员 |
| ui/pages/SettingsPage.ets · entryability/EntryAbility.ets · resources/** · module.json5 · AppScope/** | platform-settings 成员 |
| scripts/emu/** · docs/verification-summary.md · docs/runtime-verification.md · docs/store-assets/screenshots/** | emu-verify 成员 |
| docs/release/** · docs/release-guide.md · docs/agc-release-checklist.md | release-materials 成员 |

- 构建由 Lead 串行执行（`cd harmonyos && ./scripts/build.sh hap`）；成员在改完自己的文件后
  可自行构建一次验证，若遇见 "hvigor 正在运行/文件被占用" 属正常并发冲突，重试或等 Lead 构建。
- 禁止 `git commit`、禁止修改他人范围内的文件；跨范围需求发消息给 Lead。
- 所有 `.ets` 必须通过 ArkTS 严格检查（禁止 any、禁止对象字面量类型推断歧义、必需显式类型）。
