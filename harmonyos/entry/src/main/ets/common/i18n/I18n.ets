/**
 * 中英文案 —— Android Strings.kt / app.js I18N 的 ArkTS 移植 (运行时字典, zh/en)。
 */
import { AppPrefs } from '../store/AppPrefs'

// zh keys: 95, en keys: 95 (program regenerated)
const ZH: Map<string, string> = new Map()
ZH.set('about_title', '关于')
ZH.set('account', '账号')
ZH.set('all_models', '全部模型')
ZH.set('appearance', '外观')
ZH.set('by_cost', '按成本')
ZH.set('by_input', '按输入')
ZH.set('by_output', '按输出')
ZH.set('by_tokens', '按 TOKEN')
ZH.set('cache_hit', '缓存命中')
ZH.set('cache_label', '缓存')
ZH.set('cancel', '取消')
ZH.set('cost', '费用')
ZH.set('currency', '货币')
ZH.set('currencyCny', '人民币 CNY')
ZH.set('currencyUsd', '美元 USD')
ZH.set('current', '当前')
ZH.set('d_unit', '天')
ZH.set('days30', '30 天')
ZH.set('daysAll', '所有')
ZH.set('goLogin', '立即登录')
ZH.set('h_unit', '小时')
ZH.set('hit_rate', '缓存命中率')
ZH.set('hours24', '24 小时')
ZH.set('in_label', '入')
ZH.set('input', '输入')
ZH.set('items', '条')
ZH.set('key_prefix', 'Key:')
ZH.set('language', '语言')
ZH.set('loading', '数据加载中…')
ZH.set('logout', '退出')
ZH.set('m_unit', '分钟')
ZH.set('min1', '1 分钟')
ZH.set('min15', '15 分钟')
ZH.set('min30', '30 分钟')
ZH.set('min5', '5 分钟')
ZH.set('model_rank', '模型用量排行')
ZH.set('monthly', '每月')
ZH.set('notLoggedIn', '未登录')
ZH.set('out_label', '出')
ZH.set('output', '输出')
ZH.set('overview', '用量概览')
ZH.set('privacy', '数据仅保存在本机，cookie 不上传')
ZH.set('quota_empty', '暂无配额数据，登录后将自动同步')
ZH.set('quota_windows', '配额窗口')
ZH.set('reasoning', '推理')
ZH.set('req_unit', '请求')
ZH.set('requests', '请求数')
ZH.set('rolling5h', '滚动 5 小时')
ZH.set('session_prefix', '会话')
ZH.set('sessions', '会话数')
ZH.set('settings_account', '账户管理')
ZH.set('settings_add', '添加账号')
ZH.set('settings_delete', '删除')
ZH.set('settings_delete_confirm', '删除该账号将同时清除其本地数据，确定？')
ZH.set('settings_relogin', '重新登录')
ZH.set('settings_rename', '重命名')
ZH.set('settings_save', '保存')
ZH.set('settings_switch', '切换')
ZH.set('soon', '即将重置')
ZH.set('sync', '同步')
ZH.set('login_success', '登录成功，正在进入仪表盘…')
ZH.set('login_failed', '登录失败')
ZH.set('db_init_failed', '数据库初始化失败')
ZH.set('welcome_sub', 'OpenCode Go 用量仪表盘 · HarmonyOS NEXT')
ZH.set('welcome_hint', '登录后自动同步用量数据，数据仅保存在本机')
ZH.set('sync_fail', '同步失败')
ZH.set('sync_full', '立即全量同步')
ZH.set('sync_full_desc', '重新拉取完整历史（数据多时较慢）')
ZH.set('prune_now', '按同步范围清理')
ZH.set('prune_now_desc', '删除所有账号中早于同步范围边界的本地记录（删除不可恢复）')
ZH.set('prune_confirm', '将删除本地 %1 天前（早于 %2）的 %3 条记录，删除后不可恢复，确定继续？')
ZH.set('prune_none', '同步范围为「所有」，本地数据不受限制，无需清理')
ZH.set('prune_empty', '同步范围内没有需要清理的记录')
ZH.set('prune_done', '已清理 %1 条本地记录')
ZH.set('sync_interval', '同步间隔')
ZH.set('sync_range', '同步范围')
ZH.set('sync_title', '自动同步')
ZH.set('syncing', '同步中…')
ZH.set('tab_home', '首页')
ZH.set('tab_records', '使用记录')
ZH.set('tab_sessions', '会话')
ZH.set('tab_settings', '设置')
ZH.set('tab_stats', '统计')
ZH.set('theme', '主题')
ZH.set('themeDark', '深色')
ZH.set('themeLight', '亮色')
ZH.set('today_trend', '今日趋势')
ZH.set('token_composition', 'Token 构成')
ZH.set('total_label', '共')
ZH.set('total_tokens', '总 TOKEN')
ZH.set('trend_title', '费用 / 请求 / TOKEN 趋势')
ZH.set('ungrouped', '未归属')
ZH.set('ungrouped_key', '未归属 (Key)')
ZH.set('update_check', '检查更新')
ZH.set('update_checking', '检查中…')
ZH.set('update_fail', '检查更新失败')
ZH.set('update_has', '发现新版本，请打开 GitHub Releases 下载')
ZH.set('update_none', '已是最新版本')
ZH.set('update_title', '更新')
ZH.set('version', '版本')
ZH.set('weekly', '每周')

// ---- v1.0 UI 改造新增文案 (ZH) —— 页面/组件只允许通过 I18n.t 使用 ----
const EXTRA_ZH: string[][] = [
  ['refresh', '刷新'],
  ['lastSync', '上次同步'],
  ['updatedAt', '更新于'],
  ['today', '今天'],
  ['d7', '近7天'],
  ['d30', '近30天'],
  ['month', '本周期'],
  ['all', '全部'],
  ['homeTitle', '用量统计总览'],
  ['overviewTitle', '用量概览'],
  ['followRange', '数据跟随时间范围'],
  ['todayTrend', '今日趋势'],
  ['quotaFail', '配额获取失败'],
  ['retryTip', '点击刷新重试'],
  ['retry', '重试'],
  ['remaining', '剩余'],
  ['used', '已用'],
  ['resetsIn', '重置于'],
  ['windowNotStarted', '窗口未开始'],
  ['resetUnknown', '重置时间未知'],
  ['fcExhaust', '预计耗尽于 %1'],
  ['fcNeverFull', '预计不会打满（%1%%）'],
  ['quotaRolling', '滚动 5 小时'],
  ['quotaWeekly', '每周用量'],
  ['quotaMonthly', '每月用量'],
  ['hitAmount', '缓存命中量'],
  ['totalRequests', '总请求'],
  ['totalCost', '总费用'],
  ['hit', '命中'],
  ['miss', '未命中'],
  ['pctOfInput', '占输入'],
  ['inclCache', '含缓存命中'],
  ['currentRange', '当前范围'],
  ['avgPer', '均'],
  ['perReq', '/次'],
  ['dedup', '去重 sessionID'],
  ['ttPlain', '不含缓存'],
  ['ttTotal', '含缓存'],
  ['statsTitle', '用量统计'],
  ['modelUsage', '模型用量'],
  ['usageTrend', '用量趋势'],
  ['cacheWrite', '缓存写'],
  ['newCacheWrites', '新写入缓存'],
  ['heatmapTitle', '日历热力图'],
  ['heatmapNoData', '本地暂无历史数据'],
  ['mtTitle', '模型用量趋势'],
  ['trendHint', '30 天'],
  ['trendHintGap', '30 天（%1 天前无数据）'],
  ['hmPeak', '峰值'],
  ['hmCurStreak', '当前连续'],
  ['hmMaxStreak', '最长连续'],
  ['recordsPage', '使用记录'],
  ['sessionUsage', '会话用量'],
  ['usageRecords', '使用记录'],
  ['prev', '上一页'],
  ['next', '下一页'],
  ['totalN', '共'],
  ['colLastUsed', '最后使用'],
  ['colRequests', '请求数'],
  ['colInput', '输入'],
  ['colOutput', '输出'],
  ['colReasoning', '推理'],
  ['colCacheRead', '缓存读'],
  ['colCacheWrite', '缓存写'],
  ['colCost', '费用'],
  ['colKey', '密钥'],
  ['colSession', '会话'],
  ['colModel', '模型'],
  ['colTime', '时间'],
  ['pageOf', '第'],
  ['ofPages', '页'],
  ['settingsTitle', '设置'],
  ['setAccount', 'OpenCode 账户'],
  ['relogin', '重新登录'],
  ['setAutoSync', '自动同步'],
  ['autoSync', '自动增量同步'],
  ['autoSyncDesc', '按间隔拉取最新用量记录'],
  ['syncIntervalDesc', '多久自动同步一次'],
  ['syncRangeDesc', '本地保留与首次拉取的历史窗口'],
  ['d30short', '30 天'],
  ['d60', '60 天'],
  ['d90', '90 天'],
  ['d180', '180 天'],
  ['setAppearance', '外观'],
  ['themeDesc', '亮色 / 深色'],
  ['light', '浅色'],
  ['dark', '深色'],
  ['currencyDesc', '费用主显示货币（实时汇率）'],
  ['languageDesc', '界面显示语言'],
  ['setUpdate', '软件更新'],
  ['currentVersion', '当前版本'],
  ['checkUpdate', '检查更新'],
  ['checkUpdateDesc', '检查 GitHub 上是否有新版本'],
  ['checkingUpdate', '检查中…'],
  ['aboutTitle', '关于'],
  ['introText', '是一款本地优先的 OpenCode Go 用量面板：配额窗口、Token 构成、模型排行与使用记录整理在同一处，打开即见。所有数据仅保存在本地，登录凭证只用于同步官方接口。'],
  ['aboutFeatures', '功能'],
  ['feat1', '配额窗口实时监控（滚动 5 小时 / 每周 / 每月）'],
  ['feat2', '今日用量与 24 小时趋势'],
  ['feat3', '各模型 Token 消耗排行与用量趋势'],
  ['feat4', '详细使用记录分页浏览（10 条/页）'],
  ['feat5', '自动同步数据，无需手动刷新'],
  ['thanksText', '数据提供'],
  ['pageFoot', '{version} · GoGauge · 数据仅保存在本地 · 数据提供 OpenCode'],
  ['welcomeDesc', '本地优先的 OpenCode Go 用量仪表盘 — 配额窗口、Token 构成、模型排行、使用记录，打开即见。'],
  ['welcomeFeat1', '配额实时监控（5 小时 / 每周 / 每月）'],
  ['welcomeFeat2', 'Token 全维度统计与 24 小时趋势'],
  ['welcomeFeat3', '数据仅保存在本机，安全私密'],
  ['demoMode', '演示模式（截图数据）'],
  ['demoModeHint', '仅调试版本可用：注入本地模拟数据'],
  ['manageUsers', '管理用户'],
  ['addUser', '添加用户'],
  ['noUsers', '暂无账号，请先登录'],
  ['userSwitchTip', '切换用户'],
  ['switchedAccount', '已切换账号'],
  ['currentUserBadge', '当前'],
  ['renameTitle', '重命名用户'],
  ['deleteTitle', '删除用户'],
  ['deleteUserConfirm', '确定删除用户「%1」？其本地用量数据与同步记录将一并清除。'],
  ['userDeleted', '用户已删除'],
  ['userRenamed', '已重命名'],
  ['logoutUserConfirm', '将退出「%1」并清除其本地用量数据与同步记录，确定？'],
  ['ok', '确定'],
  ['confirm', '确认'],
  ['loginTitle', '连接 OpenCode Go'],
  ['loginNote', '点击后将打开 OpenCode Go 官方授权页完成登录。'],
  ['loginExternalTip', '内置窗口白屏时：在系统浏览器完成登录 → 复制 Cookie → 粘贴到下方'],
  ['cookiePaste', '用粘贴的 Cookie 登录'],
  ['cookieEmpty', '请先粘贴 Cookie'],
  ['cookieChecking', '正在校验凭证…'],
  ['cookieInvalid', '凭证无效'],
  ['cookiePhOpencode', '粘贴完整 Cookie（含 __Host-console_session=…），可从已登录浏览器 DevTools 复制'],
  ['pruneTitle', '按同步范围清理'],
  ['heatmapRange', '近 6 个月'],
  ['noData', '暂无记录'],
  ['fewer', '少'],
  ['more', '多'],
  ['workspace', '工作区'],
  ['openSource', '开源仓库'],
  ['debugTools', '调试工具'],
  ['injectSample', '注入模拟数据'],
  ['clearSample', '清除模拟数据'],
  ['sampleInjected', '已注入 %1 条模拟记录'],
  ['sampleCleared', '已清除 %1 条模拟记录'],
  ['openLinkFailed', '无法打开浏览器'],
  ['privacyTitle', '隐私政策'],
  ['privacyAgree', '同意并继续'],
  ['privacyDecline', '不同意'],
  ['privacyEntry', '查看《隐私政策》'],
  ['privacyDeclinedTip', '需同意隐私政策后才能使用本应用'],
  ['privacyShort', '数据仅保存在本机，不会上传到开发者服务器'],
  ['localData', '数据仅保存在本机'],
  ['notSyncedYet', '尚未同步'],
  ['justNow', '刚刚'],
  ['minAgo', '分钟前'],
  ['hrAgo', '小时前'],
  ['dayAgo', '天前'],
  ['never', '从未同步'],
  ['loginLoading', '正在加载授权页…'],
  ['thanksSub', '感谢 yphyphyph 开源原始项目'],
  ['loginPageTitle', 'OpenCode Go 登录'],
]
for (const kv of EXTRA_ZH) {
  ZH.set(kv[0], kv[1])
}

const EN: Map<string, string> = new Map()
EN.set('about_title', 'About')
EN.set('account', 'Account')
EN.set('all_models', 'All models')
EN.set('appearance', 'Appearance')
EN.set('by_cost', 'by cost')
EN.set('by_input', 'by input')
EN.set('by_output', 'by output')
EN.set('by_tokens', 'by tokens')
EN.set('cache_hit', 'Cache Hit')
EN.set('cache_label', 'Cache')
EN.set('cancel', 'Cancel')
EN.set('cost', 'Cost')
EN.set('currency', 'Currency')
EN.set('currencyCny', 'CNY')
EN.set('currencyUsd', 'USD')
EN.set('current', 'Current')
EN.set('d_unit', 'd')
EN.set('days30', '30 days')
EN.set('daysAll', 'All')
EN.set('goLogin', 'Log in now')
EN.set('h_unit', 'h')
EN.set('hit_rate', 'Cache Hit Rate')
EN.set('hours24', '24 hours')
EN.set('in_label', 'In')
EN.set('input', 'Input')
EN.set('items', 'items')
EN.set('key_prefix', 'Key:')
EN.set('language', 'Language')
EN.set('loading', 'Loading…')
EN.set('logout', 'Logout')
EN.set('m_unit', 'm')
EN.set('min1', '1 min')
EN.set('min15', '15 min')
EN.set('min30', '30 min')
EN.set('min5', '5 min')
EN.set('model_rank', 'Model Ranking')
EN.set('monthly', 'Monthly')
EN.set('notLoggedIn', 'Not logged in')
EN.set('out_label', 'Out')
EN.set('output', 'Output')
EN.set('overview', 'Overview')
EN.set('privacy', 'Data stays on device; cookies are never uploaded')
EN.set('quota_empty', 'No quota data yet — sync after sign in')
EN.set('quota_windows', 'Quota Windows')
EN.set('reasoning', 'Reasoning')
EN.set('req_unit', 'req')
EN.set('requests', 'Requests')
EN.set('rolling5h', '5h Rolling')
EN.set('session_prefix', 'Session')
EN.set('sessions', 'Sessions')
EN.set('settings_account', 'Accounts')
EN.set('settings_add', 'Add account')
EN.set('settings_delete', 'Delete')
EN.set('settings_delete_confirm', 'Delete this account and its local data?')
EN.set('settings_relogin', 'Re-login')
EN.set('settings_rename', 'Rename')
EN.set('settings_save', 'Save')
EN.set('settings_switch', 'Switch')
EN.set('soon', 'soon')
EN.set('sync', 'Sync')
EN.set('login_success', 'Login succeeded, entering dashboard…')
EN.set('login_failed', 'Login failed')
EN.set('db_init_failed', 'Database initialization failed')
EN.set('welcome_sub', 'OpenCode Go usage dashboard · HarmonyOS NEXT')
EN.set('welcome_hint', 'Usage syncs automatically after login. Data stays on this device.')
EN.set('sync_fail', 'Sync failed')
EN.set('sync_full', 'Full sync now')
EN.set('sync_full_desc', 'Re-fetch full history (slower with lots of data)')
EN.set('prune_now', 'Purge by Range')
EN.set('prune_now_desc', 'Delete local records older than the sync range across all accounts (irreversible)')
EN.set('prune_confirm', 'Delete %3 local records older than %1 days (before %2)? This cannot be undone.')
EN.set('prune_none', 'Sync range is "All" — local data is unlimited, nothing to purge')
EN.set('prune_empty', 'Nothing to purge within the current sync range')
EN.set('prune_done', 'Purged %1 local records')
EN.set('sync_interval', 'Interval')
EN.set('sync_range', 'Range')
EN.set('sync_title', 'Auto Sync')
EN.set('syncing', 'Syncing…')
EN.set('tab_home', 'Home')
EN.set('tab_records', 'Records')
EN.set('tab_sessions', 'Sessions')
EN.set('tab_settings', 'Settings')
EN.set('tab_stats', 'Stats')
EN.set('theme', 'Theme')
EN.set('themeDark', 'Dark')
EN.set('themeLight', 'Light')
EN.set('today_trend', 'Today Trend')
EN.set('token_composition', 'Token Composition')
EN.set('total_label', 'Total')
EN.set('total_tokens', 'Total Tokens')
EN.set('trend_title', 'Cost / Requests / Tokens Trend')
EN.set('ungrouped', 'Ungrouped')
EN.set('ungrouped_key', 'Ungrouped (Key)')
EN.set('update_check', 'Check update')
EN.set('update_checking', 'Checking…')
EN.set('update_fail', 'Update check failed')
EN.set('update_has', 'New version available, open GitHub Releases to download')
EN.set('update_none', 'Up to date')
EN.set('update_title', 'Update')
EN.set('version', 'Version')
EN.set('weekly', 'Weekly')

// ---- v1.0 UI 改造新增文案 (EN) ----
const EXTRA_EN: string[][] = [
  ['refresh', 'Refresh'],
  ['lastSync', 'Last sync'],
  ['updatedAt', 'Updated'],
  ['today', 'Today'],
  ['d7', '7 Days'],
  ['d30', '30 Days'],
  ['month', 'This Cycle'],
  ['all', 'All'],
  ['homeTitle', 'Usage Overview'],
  ['overviewTitle', 'Usage Overview'],
  ['followRange', 'Follows selected range'],
  ['todayTrend', 'Today Trend'],
  ['quotaFail', 'Quota fetch failed'],
  ['retryTip', 'Tap refresh to retry'],
  ['retry', 'Retry'],
  ['remaining', 'Remaining'],
  ['used', 'Used'],
  ['resetsIn', 'Resets in'],
  ['windowNotStarted', 'Window not started'],
  ['resetUnknown', 'Reset time unknown'],
  ['fcExhaust', 'Runs out in %1'],
  ['fcNeverFull', 'Won\'t fill before reset (%1%%)'],
  ['quotaRolling', '5h Rolling'],
  ['quotaWeekly', 'Weekly Usage'],
  ['quotaMonthly', 'Monthly Usage'],
  ['hitAmount', 'Cache Hits'],
  ['totalRequests', 'Requests'],
  ['totalCost', 'Total Cost'],
  ['hit', 'hit'],
  ['miss', 'missed'],
  ['pctOfInput', 'of input'],
  ['inclCache', 'incl. cache hits'],
  ['currentRange', 'current range'],
  ['avgPer', 'avg'],
  ['perReq', '/req'],
  ['dedup', 'dedup sessionID'],
  ['ttPlain', 'Excl. cache'],
  ['ttTotal', 'Incl. cache'],
  ['statsTitle', 'Usage Stats'],
  ['modelUsage', 'Model Usage'],
  ['usageTrend', 'Usage Trend'],
  ['cacheWrite', 'Cache Write'],
  ['newCacheWrites', 'new cache writes'],
  ['heatmapTitle', 'Daily Heatmap'],
  ['heatmapNoData', 'No local history yet'],
  ['mtTitle', 'Model Usage Trend'],
  ['trendHint', '30 days'],
  ['trendHintGap', '30 days (no data for the first %1 days)'],
  ['hmPeak', 'Peak'],
  ['hmCurStreak', 'Current streak'],
  ['hmMaxStreak', 'Longest streak'],
  ['recordsPage', 'Records'],
  ['sessionUsage', 'Session Usage'],
  ['usageRecords', 'Usage Records'],
  ['prev', 'Prev'],
  ['next', 'Next'],
  ['totalN', 'Total'],
  ['colLastUsed', 'Last Used'],
  ['colRequests', 'Requests'],
  ['colInput', 'Input'],
  ['colOutput', 'Output'],
  ['colReasoning', 'Reasoning'],
  ['colCacheRead', 'Cache Read'],
  ['colCacheWrite', 'Cache Write'],
  ['colCost', 'Cost'],
  ['colKey', 'Key'],
  ['colSession', 'Session'],
  ['colModel', 'Model'],
  ['colTime', 'Time'],
  ['pageOf', 'Page'],
  ['ofPages', 'of'],
  ['settingsTitle', 'Settings'],
  ['setAccount', 'OpenCode Account'],
  ['relogin', 'Re-login'],
  ['setAutoSync', 'Auto Sync'],
  ['autoSync', 'Auto incremental sync'],
  ['autoSyncDesc', 'Fetch latest usage records at interval'],
  ['syncIntervalDesc', 'How often to auto sync'],
  ['syncRangeDesc', 'Local history window for the first fetch'],
  ['d30short', '30d'],
  ['d60', '60d'],
  ['d90', '90d'],
  ['d180', '180d'],
  ['setAppearance', 'Appearance'],
  ['themeDesc', 'Light / Dark'],
  ['light', 'Light'],
  ['dark', 'Dark'],
  ['currencyDesc', 'Primary currency for costs (live FX rate)'],
  ['languageDesc', 'Interface language'],
  ['setUpdate', 'Software Update'],
  ['currentVersion', 'Current Version'],
  ['checkUpdate', 'Check Updates'],
  ['checkUpdateDesc', 'Check GitHub for new versions'],
  ['checkingUpdate', 'Checking…'],
  ['aboutTitle', 'About'],
  ['introText', 'is a local-first OpenCode Go usage dashboard: quota windows, token breakdown, model ranking and usage records in one place. All data stays on your machine; credentials are only used to sync official APIs.'],
  ['aboutFeatures', 'Features'],
  ['feat1', 'Quota window monitoring (5h rolling / weekly / monthly)'],
  ['feat2', 'Today\'s usage with 24-hour trend'],
  ['feat3', 'Per-model token ranking and usage trend'],
  ['feat4', 'Paginated usage records (10 per page)'],
  ['feat5', 'Auto sync — no manual refresh needed'],
  ['thanksText', 'Data provided by'],
  ['pageFoot', '{version} · GoGauge · Local-only data · Data by OpenCode'],
  ['welcomeDesc', 'A local-first OpenCode Go usage dashboard — quota windows, token breakdown, model ranking and usage records in one place.'],
  ['welcomeFeat1', 'Real-time quota monitoring (5h / weekly / monthly)'],
  ['welcomeFeat2', 'Full token stats with 24-hour trend'],
  ['welcomeFeat3', 'All data stays on your machine — private & safe'],
  ['demoMode', 'Demo Mode (screenshot data)'],
  ['demoModeHint', 'Debug builds only: injects local sample data'],
  ['manageUsers', 'Manage users'],
  ['addUser', 'Add User'],
  ['noUsers', 'No accounts yet — sign in first'],
  ['userSwitchTip', 'Switch user'],
  ['switchedAccount', 'Account switched'],
  ['currentUserBadge', 'Active'],
  ['renameTitle', 'Rename User'],
  ['deleteTitle', 'Delete User'],
  ['deleteUserConfirm', 'Delete user \"%1\"? Their local usage and sync data will be removed.'],
  ['userDeleted', 'User deleted'],
  ['userRenamed', 'Renamed'],
  ['logoutUserConfirm', 'Sign out \"%1\" and remove their local usage and sync data?'],
  ['ok', 'OK'],
  ['confirm', 'Confirm'],
  ['loginTitle', 'Connect OpenCode Go'],
  ['loginNote', 'Clicking opens the official OpenCode Go authorization page.'],
  ['loginExternalTip', 'If the built-in window fails: sign in via browser → copy the Cookie → paste below'],
  ['cookiePaste', 'Sign in with pasted cookie'],
  ['cookieEmpty', 'Paste a cookie first'],
  ['cookieChecking', 'Validating credential…'],
  ['cookieInvalid', 'Invalid credential'],
  ['cookiePhOpencode', 'Paste the full Cookie (with __Host-console_session=…) copied from a signed-in browser DevTools'],
  ['pruneTitle', 'Purge by Range'],
  ['heatmapRange', 'Last 6 months'],
  ['noData', 'No records'],
  ['fewer', 'Less'],
  ['more', 'More'],
  ['workspace', 'Workspace'],
  ['openSource', 'Open Source'],
  ['debugTools', 'Debug Tools'],
  ['injectSample', 'Inject sample data'],
  ['clearSample', 'Clear sample data'],
  ['sampleInjected', 'Injected %1 sample records'],
  ['sampleCleared', 'Cleared %1 sample records'],
  ['openLinkFailed', 'Could not open browser'],
  ['privacyTitle', 'Privacy Policy'],
  ['privacyAgree', 'Agree and continue'],
  ['privacyDecline', 'Decline'],
  ['privacyEntry', 'View Privacy Policy'],
  ['privacyDeclinedTip', 'You must agree to the Privacy Policy to use this app'],
  ['privacyShort', 'Data stays on this device and is never uploaded to the developer'],
  ['localData', 'Data stored on this device'],
  ['notSyncedYet', 'Not synced yet'],
  ['justNow', 'just now'],
  ['minAgo', 'min ago'],
  ['hrAgo', 'hr ago'],
  ['dayAgo', 'd ago'],
  ['never', 'Never synced'],
  ['loginLoading', 'Loading authorization page…'],
  ['thanksSub', 'Thanks to yphyphyph for the original open-source project'],
  ['loginPageTitle', 'OpenCode Go Sign-in'],
]
for (const kv of EXTRA_EN) {
  EN.set(kv[0], kv[1])
}

export class I18n {
  static t(key: string): string {
    const lang = AppPrefs.getLanguage()
    const dict = lang === 'en' ? EN : ZH
    const v = dict.get(key)
    return v !== undefined ? v : key
  }
}
