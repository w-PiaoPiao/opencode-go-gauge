# GoGauge 1.0.0 发布说明（首版）

> 用于 AGC「版本信息 → 新版本特性」字段，以及 GitHub Releases / 应用市场更新页。
> 字段限制：新版本特性（中国大陆站点）≤500 字符；非中国大陆站点 ≤1000 字符。
> 来源：<https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-intro-0000002313477961>（以 AGC 后台实际提示为准）

## 中文（可直接粘贴，约 150 字符）

HarmonyOS NEXT 首版发布：OpenCode Go 配额窗口、用量概览与时间范围切换、今日趋势、用量统计（Token 构成/模型排行/趋势/日历热力图/模型用量趋势）、使用记录、多账号与自动同步；亮/暗双主题、中英文界面；数据仅存本机，不含广告与统计 SDK。首次使用需登录你自己的 OpenCode 账号。

## 中文（详细版，用于 GitHub Release / 应用内更新说明）

### 新增

- **配额窗口**：滚动 5 小时、每周、每月三档窗口的已用比例、剩余额度与重置倒计时。
- **用量概览**：缓存命中率、缓存命中量、总 Token（含缓存命中）、总请求、总费用（含单次均价）、会话数 6 项指标，支持「今天 / 近 7 天 / 近 30 天 / 本周期 / 全部」时间范围切换。
- **今日趋势**：24 小时输入 / 输出柱状图。
- **用量统计**：Token 构成环形图（输入 / 输出 / 推理 / 缓存读 / 缓存写 / 会话数）、模型用量环形图与排行（输入 / 输出 / 费用切换，含请求数与缓存命中率）、30 天费用 / 请求 / Token 趋势。
- **日历热力图**：近 6 个月每日用量热力（总 Token / 总请求 / 费用切换），含峰值、当前连续、最长连续天数。
- **模型用量趋势**：近 30 天按模型堆叠的面积图。
- **使用记录**：会话聚合与请求级明细双视图，支持模型筛选、分页、Key 名称与单条费用展示。
- **多账号**：添加 / 切换 / 重命名 / 删除 / 重新登录，用量按账号隔离。
- **自动同步**：前台 1 / 5 / 15 / 30 分钟增量同步 + 后台周期同步（系统最短 20 分钟）；同步范围 30 / 60 / 90 / 180 天或全部；支持「立即全量同步」。
- **外观**：亮色 / 深色双主题，中文 / English 双语，美元 / 人民币货币切换。
- **多设备**：适配手机、平板与 PC/2in1 屏幕形态，窄屏底部导航、宽屏左侧导航（v1.0 应用市场按手机 + PC/2in1 发布，平板由手机兼容分发）。

### 说明

- 本版本为 HarmonyOS NEXT 首发版：Command Code / GOAT 账号支持与跨账号「账户总览面板」**尚未实现**，后续版本补齐。
- 数据仅保存在本机应用私有目录，登录凭证仅用于访问 opencode.ai 官方接口。
- 本应用为第三方非官方客户端，与 OpenCode / OpenCode Go 运营方无隶属关系。

## English (paste into the "What's new" field; ~700 characters, limit 1,000 outside mainland China)

First release for HarmonyOS NEXT: quota windows, usage overview with time-range switching, today's trend, usage stats (token composition, model ranking, trends, daily heatmap, model usage trend), usage records, multi-account and auto sync; light/dark themes and a Chinese/English UI. All data stays on your device; no ads and no analytics SDK. Sign in with your own OpenCode account to get started.

### Details

- **Quota windows**: rolling 5-hour, weekly and monthly windows with used ratio, remaining quota and reset countdown.
- **Usage overview**: six KPIs — cache hit rate, cached tokens, total tokens (cached included), requests, cost (with average per request) and sessions — plus a Today / Last 7 days / Last 30 days / Current cycle / All range switch.
- **Today's trend**: 24-hour input/output bar chart.
- **Usage stats**: token composition donut (input / output / reasoning / cache read / cache write / sessions), model usage donut and ranking (by input / output / cost), 30-day cost / request / token trends.
- **Daily heatmap**: last 6 months of daily usage (total tokens / requests / cost) with peak, current streak and longest streak.
- **Model usage trend**: 30-day stacked area chart by model.
- **Usage records**: session-grouped and request-level views with model filtering, pagination, key names and per-request cost.
- **Multi-account**: add / switch / rename / delete / re-login with per-account data isolation.
- **Auto sync**: foreground incremental sync at 1 / 5 / 15 / 30 minutes plus background sync (20-minute minimum on HarmonyOS); sync range 30 / 60 / 90 / 180 days or all; manual full sync.
- **Appearance**: light/dark theme, Chinese/English UI, USD/CNY currency.
- **Devices**: phone, tablet and PC/2in1 with responsive navigation.

### Notes

- This is the first HarmonyOS NEXT release: Command Code / GOAT support and the cross-account overview panel are **not implemented yet**.
- Data stays in the app-private directory on your device; the login credential is used only for official opencode.ai APIs.
- Unofficial third-party client; not affiliated with OpenCode / OpenCode Go.

## 版本号对照

| 字段 | 值 | 来源 |
| --- | --- | --- |
| versionName | `1.0.0` | `AppScope/app.json5` |
| versionCode | `1000000` | `AppScope/app.json5` |
| bundleName | `io.github.yphyphyph.gogauge` | `AppScope/app.json5` |
| 构建模式 | release | AGC 要求上架包为 Release 类型 |

> versionCode 递增规则见 `../release-guide.md` §11；下一次功能版本建议 `1.1.0 / 1000100`，修复版本 `1.0.1 / 1000001`（须严格递增且 ≤ 2,147,483,647）。
