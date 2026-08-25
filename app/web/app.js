/* GoGauge - 4 页 (首页/用量统计/设置/关于) + 双主题 + 中英国际化 */
"use strict";

const $ = (id) => document.getElementById(id);

/* ================= 国际化 ================= */
const I18N = {
  zh: {
    syncing: "同步中", themeDark: "暗色", themeLight: "亮色", refresh: "刷新",
    homeTitle: "用量统计总览", today: "今天", d7: "近7天", d30: "近30天", all: "全部",
    overviewTitle: "用量概览", followRange: "数据跟随时间范围",
    todayTrend: "今日趋势", hours24: "24 小时",
    statsTitle: "用量统计", tokenBreakdown: "Token 构成",
    modelUsage: "模型用量", input: "输入", output: "输出", cost: "成本",
    usageTrend: "用量趋势", usageRecords: "使用记录", allModels: "全部模型",
    recordsPage: "使用记录",
    sessionUsage: "会话用量", colSession: "会话", colKey: "Key 名称", colLastUsed: "最后使用", colRequests: "请求/Token", unassigned: "未归属",
    accountOverview: "账户总览", costTrend7d: "7 日费用趋势对比",
    todayTotalReq: "今日总请求", todayTotalTokens: "今日总 TOKEN", todayTotalCost: "今日总费用", todayTotalInput: "今日总输入",
    activeAccount: "当前活跃", quotaNotReady: "配额获取中…",
    overviewPanel: "账户总览面板", overviewPanelDesc: "侧边栏显示多账户总览入口，聚合展示各账户配额与用量",
    setUpdate: "软件更新", currentVersion: "当前版本", checkUpdate: "检查更新", checkUpdateDesc: "检查 GitHub 上是否有新版本", checkUpdateBtn: "检查更新",
    checkingUpdate: "检查中…", updateFound: "发现新版本", updateNone: "已是最新版本", updateFailed: "检查更新失败", goDownload: "前往下载",
    autostart: "开机自启", autostartDesc: "登录系统时自动启动并驻留菜单栏",
    downloading: "下载中…", updateReady: "新版本已下载到「下载」文件夹", downloadFailed: "下载失败", openReleasePage: "打开发布页", autostartFail: "开机自启设置失败",
    colTime: "时间", colModel: "模型", colInput: "输入", colOutput: "输出",
    colReasoning: "推理", colCacheRead: "缓存读", colCost: "费用", colPlan: "PLAN",
    prev: "上一页", next: "下一页",
    settingsTitle: "设置", setAccount: "OpenCode 账户", setLoginState: "登录状态",
    setWorkspace: "工作区", setLoginMethod: "登录方式",
    loginMethodDesc: "内置浏览器 (WebView2) 打开官方授权页，自动回填",
    relogin: "重新登录", setLogout: "退出登录", logoutDesc: "清除本地 token 与缓存数据", logout: "退出登录",
    setAutoSync: "自动同步", autoSync: "自动增量同步", autoSyncDesc: "按间隔拉取最新用量记录",
    syncInterval: "同步间隔", syncIntervalDesc: "多久自动同步一次",
    min1: "1 分钟", min5: "5 分钟", min15: "15 分钟", min30: "30 分钟",
    syncRange: "同步范围", syncRangeDesc: "本地保留与首次拉取的历史窗口；\"所有\"= 拉取全部（500 页保险）",
    d30short: "30天", d60: "60天", d90: "90天", d180: "180天",
    fullSync: "立即全量同步", fullSyncDesc: "重新拉取历史记录，补全数据", startFullSync: "开始全量同步",
    setAppearance: "外观", theme: "主题", themeDesc: "亮色 / 深色，顶栏按钮快捷切换",
    light: "浅色", dark: "深色", currency: "默认货币", currencyDesc: "费用主显示货币（实时汇率）",
    language: "语言 / Language", languageDesc: "界面显示语言",
    setData: "数据", dataDir: "数据目录", syncInfo: "同步记录",
    aboutTitle: "关于", aboutIntro: "简介",
    introText: "是一款本地优先的 OpenCode Go 用量面板：配额窗口、Token 构成、模型排行与使用记录整理在同一处，打开即见。所有数据仅保存在本地，登录凭证只用于同步官方接口。",
    aboutFeatures: "功能", feat1: "配额窗口实时监控（滚动 5 小时 / 每周 / 每月）",
    feat2: "今日用量与 24 小时趋势", feat3: "各模型 Token 消耗排行与用量趋势",
    feat4: "详细使用记录分页浏览（10 条/页）", feat5: "自动同步数据，无需手动刷新",
    aboutTech: "技术栈", aboutLinks: "链接", aboutThanks: "致谢", thanksText: "数据提供",
    pageFoot: "{version} · GoGauge · 数据仅保存在本地 · 数据提供 OpenCode",
    loginTitle: "连接 OpenCode Go",
    welcomeDesc: "本地优先的 OpenCode Go 用量仪表盘 — 配额窗口、Token 构成、模型排行、使用记录，打开即见。",
    welcomeFeat1: "配额实时监控（5 小时 / 每周 / 每月）",
    welcomeFeat2: "Token 全维度统计与 24 小时趋势",
    welcomeFeat3: "数据仅保存在本机，安全私密",
    loginBtn: "立即登录",
    loginNote: "点击后将打开 OpenCode Go 官方授权页完成登录。",
    quitApp: "退出应用",
    rolling: "滚动用量", weekly: "每周用量", monthly: "每月用量",
    remaining: "剩余", used: "已用", resetsIn: "重置于",
    hitRate: "缓存命中率", hitAmount: "缓存命中量", totalTokens: "总 TOKEN 消耗",
    totalRequests: "总请求", totalCost: "总费用", sessions: "会话数",
    hit: "命中", miss: "未命中", pctOfInput: "占输入", inclCache: "含缓存命中",
    currentRange: "当前范围", avgPer: "均", perReq: "/次", dedup: "去重 sessionID",
    noData: "暂无记录", loadFailed: "加载失败", totalN: "共", items: "条",
    pageOf: "第", ofPages: "页",
    loggedIn: "已登录", notLoggedIn: "未登录", connected: "已连接", notConnected: "未连接",
    lastSync: "上次同步", records: "条记录", updatedAt: "更新于",
    justNow: "刚刚", minAgo: "分钟前", hrAgo: "小时前", dayAgo: "天前", never: "从未同步",
    day: "天", hour: "小时", minute: "分钟", soon: "即将重置",
    dUnit: "天", hUnit: "小时", mUnit: "分钟",
    confirm: "确认", cancel: "取消", ok: "确定",
    fullSyncConfirm: "将重新拉取历史记录（按同步范围），确定开始？", startSync: "开始同步",
    reloginConfirm: "将清除本地数据并打开官方授权页重新登录，确定？", goLogin: "去登录",
    logoutConfirm: "退出将清除本地 token 与全部缓存数据，确定退出？", quit: "退出",
    quotaFail: "配额获取失败", retryTip: "点击右上角刷新重试",
    syncIntervalSet: "同步间隔已设为", syncRangeUpdated: "同步范围已更新，下次全量同步生效",
    trendHint: "30 天", totalTokenHint: "含缓存命中",
    setUsers: "用户管理", addUser: "添加用户", addUserTip: "登录新的 OpenCode Go 账号并保存到本机",
    userSwitchTip: "切换用户", userCountTip: "已登录用户数",
    switchTo: "切换", currentUserBadge: "当前", renameBtn: "重命名", deleteUser: "删除",
    renameTitle: "重命名用户", save: "保存", deleteUserTitle: "删除用户",
    deleteUserConfirm: "确定删除用户「{name}」？其本地用量数据与同步记录将一并清除，且无法恢复。",
    userDeleted: "用户已删除", userRenamed: "已重命名", switchedAccount: "已切换账号",
    noUsers: "暂无账号，点击右上角「添加用户」登录",
    setToCurrent: "设为当前", loggedOut: "已退出登录",
    logoutUserConfirm: "将退出「{name}」并清除其本地用量数据与同步记录，确定？",
    reloginConfirmNew: "将打开官方授权页重新登录当前账号，确定？",
  },
  en: {
    syncing: "Syncing", themeDark: "Dark", themeLight: "Light", refresh: "Refresh",
    homeTitle: "Usage Overview", today: "Today", d7: "7 Days", d30: "30 Days", all: "All",
    overviewTitle: "Usage Overview", followRange: "Follows selected range",
    todayTrend: "Today's Trend", hours24: "24 Hours",
    statsTitle: "Usage Stats", tokenBreakdown: "Token Breakdown",
    modelUsage: "Model Usage", input: "Input", output: "Output", cost: "Cost",
    usageTrend: "Usage Trend", usageRecords: "Usage Records", allModels: "All Models",
    recordsPage: "Records",
    sessionUsage: "Session Usage", colSession: "Session", colKey: "Key Name", colLastUsed: "Last Used", colRequests: "Requests/Token", unassigned: "Unassigned",
    accountOverview: "Accounts Overview", costTrend7d: "7-Day Cost Trend",
    todayTotalReq: "Today Requests", todayTotalTokens: "Today Tokens", todayTotalCost: "Today Cost", todayTotalInput: "Today Input",
    activeAccount: "Active", quotaNotReady: "Fetching quota…",
    overviewPanel: "Accounts Panel", overviewPanelDesc: "Show multi-account overview entry in sidebar",
    setUpdate: "Software Update", currentVersion: "Current Version", checkUpdate: "Check Updates", checkUpdateDesc: "Check GitHub for new versions", checkUpdateBtn: "Check Updates",
    checkingUpdate: "Checking…", updateFound: "New Version Available", updateNone: "You're up to date", updateFailed: "Check failed", goDownload: "Go to Download",
    autostart: "Launch at Login", autostartDesc: "Start automatically and stay in the menu bar when you log in",
    downloading: "Downloading…", updateReady: "New version saved to Downloads", downloadFailed: "Download failed", openReleasePage: "Open Releases Page", autostartFail: "Failed to update launch-at-login",
    colTime: "Time", colModel: "Model", colInput: "Input", colOutput: "Output",
    colReasoning: "Reasoning", colCacheRead: "Cache Read", colCost: "Cost", colPlan: "PLAN",
    prev: "Prev", next: "Next",
    settingsTitle: "Settings", setAccount: "OpenCode Account", setLoginState: "Login Status",
    setWorkspace: "Workspace", setLoginMethod: "Login Method",
    loginMethodDesc: "Built-in browser (WebView2) opens the official auth page and auto-fills",
    relogin: "Re-login", setLogout: "Logout", logoutDesc: "Clear local token and cached data", logout: "Logout",
    setAutoSync: "Auto Sync", autoSync: "Auto incremental sync", autoSyncDesc: "Fetch latest usage records at interval",
    syncInterval: "Sync Interval", syncIntervalDesc: "How often to auto sync",
    min1: "1 min", min5: "5 min", min15: "15 min", min30: "30 min",
    syncRange: "Sync Range", syncRangeDesc: "Local history window for initial fetch; \"All\" = fetch everything (500-page safety cap)",
    d30short: "30d", d60: "60d", d90: "90d", d180: "180d",
    fullSync: "Full Sync Now", fullSyncDesc: "Re-fetch history records to fill gaps", startFullSync: "Start Full Sync",
    setAppearance: "Appearance", theme: "Theme", themeDesc: "Light / Dark, quick toggle in top bar",
    light: "Light", dark: "Dark", currency: "Currency", currencyDesc: "Primary currency for costs (live FX rate)",
    language: "Language", languageDesc: "Interface language",
    setData: "Data", dataDir: "Data Directory", syncInfo: "Sync History",
    aboutTitle: "About", aboutIntro: "Intro",
    introText: "is a local-first OpenCode Go usage dashboard: quota windows, token breakdown, model ranking and usage records in one place. All data stays on your machine; credentials are only used to sync official APIs.",
    aboutFeatures: "Features", feat1: "Quota window monitoring (5h rolling / weekly / monthly)",
    feat2: "Today's usage with 24-hour trend", feat3: "Per-model token ranking and usage trend",
    feat4: "Paginated usage records (10 per page)", feat5: "Auto sync — no manual refresh needed",
    aboutTech: "Tech Stack", aboutLinks: "Links", aboutThanks: "Thanks", thanksText: "Data provided by",
    pageFoot: "{version} · GoGauge · Local-only data · Data by OpenCode",
    loginTitle: "Connect OpenCode Go",
    welcomeDesc: "A local-first OpenCode Go usage dashboard — quota windows, token breakdown, model ranking and usage records in one place.",
    welcomeFeat1: "Real-time quota monitoring (5h / weekly / monthly)",
    welcomeFeat2: "Full token stats with 24-hour trend",
    welcomeFeat3: "All data stays on your machine — private & safe",
    loginBtn: "Login Now",
    loginNote: "Clicking opens the official OpenCode Go authorization page.",
    quitApp: "Quit App",
    rolling: "Rolling Usage", weekly: "Weekly Usage", monthly: "Monthly Usage",
    remaining: "Remaining", used: "Used", resetsIn: "Resets in",
    hitRate: "Cache Hit Rate", hitAmount: "Cache Hits", totalTokens: "Total Tokens",
    totalRequests: "Requests", totalCost: "Total Cost", sessions: "Sessions",
    hit: "hit", miss: "missed", pctOfInput: "of input", inclCache: "incl. cache hits",
    currentRange: "current range", avgPer: "avg", perReq: "/req", dedup: "dedup sessionID",
    noData: "No records", loadFailed: "Failed to load", totalN: "Total", items: "records",
    pageOf: "Page", ofPages: "of",
    loggedIn: "Logged in", notLoggedIn: "Not logged in", connected: "Connected", notConnected: "Not connected",
    lastSync: "Last sync", records: "records", updatedAt: "Updated",
    justNow: "just now", minAgo: "min ago", hrAgo: "hr ago", dayAgo: "d ago", never: "Never synced",
    day: "d", hour: "h", minute: "m", soon: "resets soon",
    dUnit: "d", hUnit: "h", mUnit: "m",
    confirm: "Confirm", cancel: "Cancel", ok: "OK",
    fullSyncConfirm: "This will re-fetch all history records (per sync range). Continue?", startSync: "Start Sync",
    reloginConfirm: "This will clear local data and open the auth page. Continue?", goLogin: "Go Login",
    logoutConfirm: "This will clear local token and all cached data. Continue?", quit: "Logout",
    quotaFail: "Quota fetch failed", retryTip: "Click refresh in top bar to retry",
    syncIntervalSet: "Sync interval set to", syncRangeUpdated: "Sync range updated, takes effect on next full sync",
    trendHint: "30 days", totalTokenHint: "incl. cache hits",
    setUsers: "User Management", addUser: "Add User", addUserTip: "Sign in with another OpenCode Go account",
    userSwitchTip: "Switch user", userCountTip: "Logged-in users",
    switchTo: "Switch", currentUserBadge: "Active", renameBtn: "Rename", deleteUser: "Delete",
    renameTitle: "Rename User", save: "Save", deleteUserTitle: "Delete User",
    deleteUserConfirm: "Delete user \"{name}\"? Their local usage data and sync history will be removed permanently.",
    userDeleted: "User deleted", userRenamed: "Renamed", switchedAccount: "Account switched",
    noUsers: "No accounts yet — click \"Add User\" to sign in",
    setToCurrent: "Make Active", loggedOut: "Signed out",
    logoutUserConfirm: "Sign out \"{name}\" and remove their local usage data and sync history?",
    reloginConfirmNew: "This opens the auth page to re-login the current account. Continue?",
  },
};
let lang = "zh";
function t(key) { return (I18N[lang] && I18N[lang][key]) || I18N.zh[key] || key; }

let state = {
  page: "home",
  range: "today",
  statsRange: "7d",
  modelDim: "input",
  data: null,
  exchangeRate: 7.0,
  currency: "CNY",
  darkMode: false,
  syncTimer: null,
  quotaRetryTimer: null,
  ovRetryTimer: null,
  records: { page: 1, pageSize: 7, total: 0, model: "" },
  sessions: { page: 1, pageSize: 7, total: 0 },
  settings: { sync_interval_sec: 300, window_days: 60, auto_sync: true },
};

const COLOR = { input: "#4f8ef7", output: "#22c55e", reasoning: "#a78bfa", cache: "#06b6d4", cost: "#d97706" };
const QUOTA_LABEL = { "5h Rolling": () => t("rolling"), "Weekly": () => t("weekly"), "Monthly": () => t("monthly") };
const PLAN_BADGE = { lite: "GO", sub: "GO", byok: "BYOK" };

/* ---------------- 格式化 ---------------- */
function fmtTokens(n) {
  n = Number(n) || 0;
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(Math.round(n));
}
function fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }
function fmtMoney(usd) {
  usd = Number(usd) || 0;
  if (state.currency === "CNY") {
    const v = usd * state.exchangeRate;
    return "¥" + (v >= 1 ? v.toFixed(2) : v.toFixed(4));
  }
  if (usd >= 1) return "$" + usd.toFixed(2);
  if (usd > 0) return "$" + usd.toFixed(4);
  return "$0";
}
function fmtDur(sec) {
  sec = Math.max(0, Number(sec) || 0);
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  if (d > 0) return d + " " + t("dUnit") + " " + h + " " + t("hUnit");
  if (h > 0) return h + " " + t("hUnit") + " " + m + " " + t("mUnit");
  if (m > 0) return m + " " + t("mUnit");
  return t("soon");
}
function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const pad = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function fmtRelative(iso) {
  if (!iso) return t("never");
  const d = new Date(iso);
  if (isNaN(d)) return t("never");
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return t("justNow");
  if (diff < 3600) return Math.floor(diff / 60) + " " + t("minAgo");
  if (diff < 86400) return Math.floor(diff / 3600) + " " + t("hrAgo");
  return Math.floor(diff / 86400) + " " + t("dayAgo");
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/* ---------------- API ---------------- */
const API_TIMEOUT_MS = 15000;  // 本地服务异常时避免永久"加载中"
async function api(path, opts = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS);
  try {
    const resp = await fetch(path, { headers: { "Content-Type": "application/json" }, signal: ctrl.signal, ...opts });
    if (!resp.ok) {
      let msg = "HTTP " + resp.status;
      try { const b = await resp.json(); if (b && b.error) msg = b.error; } catch (e) { /* 无 body 或非 JSON 时保持默认 */ }
      throw new Error(msg);
    }
    return await resp.json();
  } catch (e) {
    if (e && e.name === "AbortError") throw new Error("请求超时");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/* ---------------- 语言切换 ---------------- */
function applyLang(l) {
  lang = l === "en" ? "en" : "zh";
  try { localStorage.setItem("gousage-lang", lang); } catch (e) { /* ignore */ }
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  // 静态 data-i18n 文案
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("#set-lang-pills .pill").forEach((b) => b.classList.toggle("active", b.dataset.v === lang));
  // 版本号: 唯一来源为后端 /api/version (app/__init__.py), 前端动态获取
  const ver = APP_VERSION ? "v" + APP_VERSION : "GoGauge";
  document.getElementById("about-sub").textContent = `${ver} · OpenCode Go Usage Panel`;
  const pf = document.querySelector('[data-i18n="pageFoot"]');
  if (pf) pf.textContent = t("pageFoot").replace("{version}", ver);
  const sv = document.getElementById("set-version");
  if (sv) sv.textContent = APP_VERSION ? `v${APP_VERSION}` : "—";
  // 动态内容重渲染
  if (state.data) {
    renderAll(state.data);
    renderSettings();
    loadRecords().catch(() => {});
  }
}

/* ---------------- 弹框 / Toast ---------------- */
function showModal({ title = t("confirm"), message = "", okText = t("ok"), cancelText = t("cancel"), danger = false, onOk }) {
  const overlay = $("modal-overlay");
  $("modal-title").textContent = title;
  $("modal-message").innerHTML = message;
  $("modal-ok").textContent = okText;
  $("modal-cancel").textContent = cancelText;
  $("modal-cancel").hidden = !cancelText;
  const icon = $("modal-icon");
  icon.className = "modal-icon" + (danger ? " danger" : "");
  icon.textContent = danger ? "⚠" : "?";
  overlay.hidden = false;
  const cleanup = () => { overlay.hidden = true; $("modal-ok").onclick = null; $("modal-cancel").onclick = null; };
  $("modal-ok").onclick = () => { cleanup(); onOk && onOk(); };
  $("modal-cancel").onclick = () => { cleanup(); };
}
function toast(msg, type = "ok") {
  const wrap = $("toast-wrap");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 300); }, 3200);
}

/* ---------------- 标题栏 ---------------- */
// macOS 使用原生标题栏 + 左上角红黄绿交通灯; 隐藏自定义窗口控制按钮.
function isMac() {
  return /Mac|iPhone|iPod|iPad/i.test((navigator.platform || "") + (navigator.userAgent || ""));
}
async function pywebviewApi() {
  try { if (window.pywebview && window.pywebview.api) return window.pywebview.api; } catch (e) { /* ignore */ }
  return null;
}
function adaptTitlebar() {
  // macOS: 原生标题栏提供 关闭/最小化/缩放, 移除页内自定义窗口按钮.
  const mac = isMac();
  ["tb-min", "tb-close", "tb-sep"].forEach((id) => { const el = $(id); if (el) el.hidden = mac; });
  document.documentElement.classList.toggle("os-mac", mac);
}
function bindTitlebar() {
  adaptTitlebar();
  $("tb-min").addEventListener("click", async () => { const a = await pywebviewApi(); if (a) a.minimize(); });
  $("tb-close").addEventListener("click", async () => { const a = await pywebviewApi(); if (a) a.close(); });
  $("tb-theme").addEventListener("click", () => applyDarkMode(document.documentElement.dataset.theme !== "dark"));

  /* 标题栏拖动 (自实现, 替代 pywebview easy_drag):
     easy_drag 的 JS 用 clientX 记起点、screenX 算增量 (DPI 缩放下两坐标系
     不同源), 后端 move() 再乘一次缩放, 高 DPI 屏幕拖动会漂移抽动.
     这里用相邻两次 mousemove 的屏幕增量 (screenX/screenY 物理像素) 交给
     后端 move_by, 后端以同坐标系 SetWindowPos 增量移动, 1:1 跟随.
     关键点:
     1) 增量取相邻事件差值, 不能取按下点差值 — 否则每次都按总位移叠加到
        窗口当前位置, 连续触发会累积放大, 拖远一点就飞出屏幕;
     2) mousemove 频率远高于 js_api 往返速度, 逐事件调用会丢消息/乱序,
        先把增量累积到 pending, 用 requestAnimationFrame 合并成一次
        move_by 再发, 保证每次移动都精确送达. */
  let drag = null;
  let pending = { x: 0, y: 0 };
  let rafId = null;
  function flushDrag() {
    rafId = null;
    if (pending.x === 0 && pending.y === 0) return;
    const dx = pending.x, dy = pending.y;
    pending = { x: 0, y: 0 };
    pywebviewApi().then((a) => { if (a && a.move_by) a.move_by(dx, dy); });
  }
  document.querySelector(".tb").addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    if (e.target.closest("button, a")) return;  // 标题栏控件不触发拖动
    drag = { lx: e.screenX, ly: e.screenY };
    pending = { x: 0, y: 0 };
    e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!drag) return;
    pending.x += e.screenX - drag.lx;
    pending.y += e.screenY - drag.ly;
    drag.lx = e.screenX;
    drag.ly = e.screenY;
    if (!rafId) rafId = requestAnimationFrame(flushDrag);
  });
  window.addEventListener("mouseup", () => {
    drag = null;
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    flushDrag();  // 释放残留增量, 避免窗口停在半路
  });
}

/* ---------------- 主题 / 货币 ---------------- */
function applyDarkMode(on) {
  state.darkMode = on;
  document.documentElement.dataset.theme = on ? "dark" : "light";
  $("tb-theme").innerHTML = `◐ <span data-i18n="${on ? "themeLight" : "themeDark"}">${on ? t("themeLight") : t("themeDark")}</span>`;
  try { localStorage.setItem("gousage-dark", on ? "1" : "0"); } catch (e) { /* ignore */ }
  syncThemePills();
  refreshIcons();
  rerenderCharts();
}
function syncThemePills() {
  document.querySelectorAll("#set-theme-pills .pill").forEach((b) => b.classList.toggle("active", b.dataset.v === (state.darkMode ? "dark" : "light")));
}
function applyCurrency(cur) {
  state.currency = cur;
  document.querySelectorAll("#set-currency-pills .pill").forEach((b) => b.classList.toggle("active", b.dataset.v === cur));
  try { localStorage.setItem("gousage-currency", cur); } catch (e) { /* ignore */ }
  if (!state.data) return;
  rerenderCharts();
  renderOverview(state.data.totals);
  renderStatsTotal(state.data.totals);
  renderDetail6(state.data.totals);
  loadRecords().catch(() => {});
  if (state.page === "overview") loadOverview(true).catch(() => {});  // 总览页费用随货币即时换算
}

/* ---------------- 页面路由 ---------------- */
function switchPage(page) {
  state.page = page;
  document.querySelectorAll(".page").forEach((p) => (p.hidden = true));
  $("page-" + page).hidden = false;
  document.querySelectorAll(".side-item").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  if (page === "home" || page === "stats") loadDashboard();
  if (page === "overview") loadOverview().catch(() => {});
  if (page === "records") { loadSessions().catch(() => {}); loadRecords().catch(() => {}); }
  if (page === "settings") renderSettings();
}

/* ---------------- 骨架屏 ---------------- */
function renderSkeletons() {
  const sBlock = `<div class="ub skeleton"><div class="sk-line w40"></div><div class="sk-line w20 lg"></div><div class="sk-bar"></div><div class="sk-line w60"></div></div>`;
  $("usage-blocks").innerHTML = sBlock.repeat(3);
  const sKpi = `<div class="card kpi skeleton"><div class="sk-line w30"></div><div class="sk-line w40 lg"></div><div class="sk-line w50"></div></div>`;
  $("overview-grid").innerHTML = sKpi.repeat(6);
  // 趋势图骨架: 保留 canvas, 叠加灰色遮罩 (数据到后移除)
  const trendBox = document.querySelector(".today-trend .chart-box");
  if (trendBox) trendBox.classList.add("sk-box");
  if (!$("stats-total-cards").innerHTML) $("stats-total-cards").innerHTML = sKpi.repeat(4);
  if (!$("stats-detail6").innerHTML) $("stats-detail6").innerHTML = `<div class="tc skeleton"><div class="sk-line w40"></div><div class="sk-line w50 lg"></div><div class="sk-line w30"></div></div>`.repeat(6);
}

/* ---------------- 数据加载 ---------------- */
let loadSeq = 0;
async function loadDashboard(quiet = false) {
  const seq = ++loadSeq;
  if (!state.data) renderSkeletons();
  showLoading(true);
  try {
    const range = state.page === "stats" ? state.statsRange : state.range;
    const data = await api(`/api/dashboard?range=${range}`);
    if (seq !== loadSeq) return;
    renderAll(data);
    showLoading(false);
  } catch (e) {
    if (seq === loadSeq) showLoading(false);
    if (!quiet) console.error("dashboard load failed", e);
  }
}
function showLoading(show) { $("top-loading").hidden = !show; }

/* ---------------- 首页: 用量块 ---------------- */
function renderUsageBlocks(quota) {
  const row = $("usage-blocks");
  if (!quota || !quota.success) {
    if (quota && !quota.success) {
      clearTimeout(state.quotaRetryTimer);
      row.innerHTML = `<div class="ub ub-error">${t("quotaFail")}：${escapeHtml(quota.error || "?")}，${t("retryTip")}</div>`;
      return;
    }
    if (state.quotaRetryTimer) clearTimeout(state.quotaRetryTimer);
    state.quotaRetryTimer = setTimeout(() => loadDashboard(true), 5000);
    row.innerHTML = `<div class="ub skeleton"><div class="sk-line w40"></div><div class="sk-line w20 lg"></div><div class="sk-bar"></div><div class="sk-line w60"></div></div>`.repeat(3);
    return;
  }
  if (state.quotaRetryTimer) { clearTimeout(state.quotaRetryTimer); state.quotaRetryTimer = null; }
  const blocks = [];
  for (const w of quota.windows || []) {
    const used = Number(w.used) || 0;
    blocks.push({
      cls: w.label === "5h Rolling" ? "c-rolling" : w.label === "Weekly" ? "c-week" : "c-month",
      label: (QUOTA_LABEL[w.label] || (() => w.label))(),
      used: used,
      remaining: (Number(w.remaining) || 0).toFixed(0) + "%",
      reset: `${t("resetsIn")} ${fmtDur(w.reset_in_sec)}`,
    });
  }
  row.innerHTML = blocks.map((b) => `
    <div class="ub ${b.cls}">
      <div class="ub-head"><span class="ub-l">${b.label}</span><span class="ub-rem">${t("remaining")} ${b.remaining}</span></div>
      <div class="ub-bar"><div class="ub-bar-fill" style="width:${b.used}%"></div></div>
      <div class="ub-meta"><span>${t("used")} ${b.used.toFixed(0)}%</span><span>${b.reset}</span></div>
    </div>`).join("");
}

/* ---------------- 首页: 用量概览 6 格 ---------------- */
function renderOverview(totals) {
  const totalTokens = totals.total_input_tokens + totals.total_output_tokens + totals.total_reasoning_tokens;
  const cards = [
    { cls: "c-green", l: t("hitRate"), v: totals.hit_rate.toFixed(1) + "%", s: `${t("hit")} ${fmtTokens(totals.cache_hit_tokens)} · ${t("miss")} ${fmtTokens(totals.uncached_input_tokens)}` },
    { cls: "c-cyan", l: t("hitAmount"), v: fmtTokens(totals.cache_hit_tokens), s: `${t("pctOfInput")} ${totals.hit_rate.toFixed(1)}%` },
    { cls: "c-blue", l: t("totalTokens"), v: fmtTokens(totalTokens), s: t("inclCache") },
    { cls: "c-slate", l: t("totalRequests"), v: fmtInt(totals.request_count), s: t("currentRange") },
    { cls: "c-amber", l: t("totalCost"), v: fmtMoney(totals.total_cost_usd), s: `${t("avgPer")} ${fmtMoney(totals.request_count ? totals.total_cost_usd / totals.request_count : 0)}${t("perReq")}` },
    { cls: "c-violet", l: t("sessions"), v: fmtInt(totals.session_count), s: t("dedup") },
  ];
  $("overview-grid").innerHTML = cards.map((c) => `
    <div class="card kpi ${c.cls}"><div class="kpi-l">${c.l}</div><div class="kpi-v">${c.v}</div><div class="kpi-s">${c.s}</div></div>`).join("");
}

/* ---------------- 首页: 今日趋势 24h ---------------- */
let cToday = null;
function chartToday(trend) {
  const canvas = $("today-chart");
  if (cToday) cToday.destroy();
  const box = canvas ? canvas.parentElement : null;
  if (box) box.classList.remove("sk-box");  // 移除骨架遮罩
  if (!trend || !trend.length) { cToday = null; return; }
  cToday = new Chart(canvas, {
    type: "bar",
    data: {
      labels: trend.map((d) => d.hour),
      datasets: [
        { label: t("input"), data: trend.map((d) => d.input), backgroundColor: COLOR.input, borderRadius: 2, barPercentage: 0.8 },
        { label: t("output"), data: trend.map((d) => d.output), backgroundColor: COLOR.output, borderRadius: 2, barPercentage: 0.8 },
      ],
    },
    options: {
      responsive: false, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, color: cssVar("--text2") } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: cssVar("--text3"), font: { size: 10 }, maxTicksLimit: 8 } },
        y: { grid: { color: cssVar("--grid") }, ticks: { color: cssVar("--text3"), font: { size: 10 }, callback: (v) => fmtTokens(v) } },
      },
    },
  });
  cToday.resize();
}

/* ---------------- 统计页: 4 总卡 + 6 明细 ---------------- */
function renderStatsTotal(totals) {
  const totalTokens = totals.total_input_tokens + totals.total_output_tokens + totals.total_reasoning_tokens;
  const cards = [
    { cls: "c-amber", l: t("totalCost"), v: fmtMoney(totals.total_cost_usd), s: `${t("avgPer")} ${fmtMoney(totals.request_count ? totals.total_cost_usd / totals.request_count : 0)}${t("perReq")}` },
    { cls: "c-blue", l: t("totalRequests"), v: fmtInt(totals.request_count), s: t("currentRange") },
    { cls: "c-violet", l: t("totalTokens"), v: fmtTokens(totalTokens), s: `${t("input")} ${fmtTokens(totals.total_input_tokens)} · ${t("output")} ${fmtTokens(totals.total_output_tokens)}` },
    { cls: "c-green", l: t("hitRate"), v: totals.hit_rate.toFixed(1) + "%", s: `${t("hit")} ${fmtTokens(totals.cache_hit_tokens)} / ${t("miss")} ${fmtTokens(totals.uncached_input_tokens)}` },
  ];
  $("stats-total-cards").innerHTML = cards.map((c) => `
    <div class="card kpi ${c.cls}"><div class="kpi-l">${c.l}</div><div class="kpi-v">${c.v}</div><div class="kpi-s">${c.s}</div></div>`).join("");
}
function renderDetail6(totals) {
  const total = totals.uncached_input_tokens + totals.total_output_tokens + totals.total_reasoning_tokens;
  const cards = [
    { l: t("input"), v: fmtTokens(totals.uncached_input_tokens), s: `${t("inclCache")} ${fmtTokens(totals.total_input_tokens)}` },
    { l: t("output"), v: fmtTokens(totals.total_output_tokens), s: t("output") },
    { l: t("colReasoning"), v: fmtTokens(totals.total_reasoning_tokens), s: total ? ((totals.total_reasoning_tokens / total) * 100).toFixed(1) + "%" : "0%" },
    { l: t("colCacheRead"), v: fmtTokens(totals.cache_hit_tokens), s: `${t("hitRate")} ${totals.hit_rate.toFixed(1)}%` },
    { l: lang === "zh" ? "缓存写" : "Cache Write", v: fmtTokens(totals.cache_write_tokens), s: lang === "zh" ? "新写入缓存" : "new cache writes" },
    { l: t("sessions"), v: fmtInt(totals.session_count), s: t("dedup") },
  ];
  $("stats-detail6").innerHTML = cards.map((c) => `
    <div class="tc"><div class="tc-l">${c.l}</div><div class="tc-v">${c.v}</div><div class="tc-s">${c.s}</div></div>`).join("");
}

/* ---------------- 统计页: 模型用量 ---------------- */
let cModel = null;
function chartModel(models) {
  const canvas = $("mr-chart");
  if (cModel) cModel.destroy();
  if (!models || !models.length) { cModel = null; $("mr-list").innerHTML = ""; return; }
  const dim = state.modelDim;
  const getVal = (m) => (dim === "input" ? m.uncached_input_tokens : dim === "output" ? m.total_output_tokens : m.total_cost_usd);
  const fmt = dim === "cost" ? (v) => fmtMoney(v) : fmtTokens;
  const sorted = [...models].sort((a, b) => getVal(b) - getVal(a));
  const top = sorted.slice(0, 6);
  const total = sorted.reduce((s, m) => s + getVal(m), 0);
  const palette = [COLOR.input, COLOR.output, COLOR.reasoning, COLOR.cache, COLOR.cost, "#ec4899"];
  cModel = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: top.map((m) => m.model),
      datasets: [{ data: top.map(getVal), backgroundColor: palette, borderWidth: 2, borderColor: cssVar("--card") }],
    },
    options: {
      responsive: false, maintainAspectRatio: false, cutout: "60%",
      plugins: {
        legend: { position: "right", labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, color: cssVar("--text2") } },
        tooltip: { callbacks: { label: (it) => ` ${it.label}: ${fmt(it.parsed)}${total ? ` (${((it.parsed / total) * 100).toFixed(1)}%)` : ""}` } },
      },
    },
  });
  cModel.resize();
  $("mr-list").innerHTML = sorted.slice(0, 3).map((m, i) => `
    <div class="mr-item"><span class="mr-rank">#${i + 1}</span>
    <span class="mr-name">${modelIcon(m.model)}<span class="txt">${escapeHtml(m.model)}</span></span>
    <span class="mr-sub">${fmtInt(m.request_count)} · ${t("hitRate")} ${m.hit_rate}%</span>
    <span class="mr-cost">${fmtMoney(m.total_cost_usd)}</span></div>`).join("");
}

/* ---------------- 统计页: 用量趋势 ---------------- */
let cTrend = null;
function chartTrend(trend) {
  const canvas = $("trend-chart");
  if (cTrend) cTrend.destroy();
  if (!trend || !trend.length) { cTrend = null; return; }
  cTrend = new Chart(canvas, {
    data: {
      labels: trend.map((d) => d.date.slice(5)),
      datasets: [
        { type: "line", label: t("totalCost"), data: trend.map((d) => d.total_cost_usd), borderColor: COLOR.input, borderWidth: 2, pointRadius: 1.5, tension: 0.3, yAxisID: "y" },
        { type: "line", label: t("totalRequests"), data: trend.map((d) => d.request_count), borderColor: COLOR.output, borderWidth: 2, pointRadius: 1.5, tension: 0.3, yAxisID: "y1", borderDash: [4, 3] },
        { type: "line", label: t("totalTokens"), data: trend.map((d) => d.total_input_tokens + d.total_output_tokens + d.total_reasoning_tokens), borderColor: COLOR.reasoning, borderWidth: 2, pointRadius: 1.5, tension: 0.3, yAxisID: "y2" },
      ],
    },
    options: {
      responsive: false, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, color: cssVar("--text2") } },
        tooltip: {
          callbacks: {
            label: (item) => {
              if (item.dataset.label === t("totalTokens")) return ` ${item.dataset.label}: ${fmtTokens(item.parsed.y)}`;
              if (item.dataset.label === t("totalRequests")) return ` ${item.dataset.label}: ${fmtInt(item.parsed.y)}`;
              return ` ${item.dataset.label}: ${fmtMoney(item.parsed.y)}`;
            },
          },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: cssVar("--text3"), font: { size: 10 }, maxTicksLimit: 8 } },
        y: { position: "left", grid: { color: cssVar("--grid") }, ticks: { color: cssVar("--text3"), font: { size: 10 }, callback: (v) => fmtMoney(v) } },
        y1: { position: "right", grid: { display: false }, ticks: { color: cssVar("--text3"), font: { size: 10 } } },
        y2: { position: "right", display: false },  // 总 Token 独立隐藏轴
      },
    },
  });
  cTrend.resize();
}

/* ---------------- 会话用量 ---------------- */
let sesSeq = 0;
async function loadSessions() {
  const seq = ++sesSeq;
  const body = $("sessions-body");
  try {
    const q = new URLSearchParams({ page: state.sessions.page, page_size: 7 });
    const data = await api(`/api/usage/sessions?${q}`);
    if (seq !== sesSeq) return; // 丢弃过期响应 (快速切页/翻页时旧请求)
    state.sessions.total = data.total;
    $("ses-count").textContent = `${t("totalN")} ${fmtInt(data.total)} ${t("sessions")}`;
    if (!data.records.length) {
      body.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text3);padding:20px">${t("noData")}</td></tr>`;
    } else {
      let html = data.records.map((s) => `
        <tr><td class="key-name">${escapeHtml(s.key_name || "—")}</td>
        ${s.session_id
          ? `<td title="${escapeHtml(s.session_id)}">${escapeHtml(shortId(s.session_id))}</td>`
          : `<td class="unassigned">${t("unassigned")}</td>`}
        <td>${fmtDateTime(s.last_at)}</td>
        <td class="num">${fmtTokens(s.total_input_tokens)}</td>
        <td class="num">${fmtTokens(s.total_output_tokens)}</td>
        <td class="num">${fmtTokens(s.total_reasoning_tokens)}</td>
        <td class="num">${fmtInt(s.request_count)} / ${fmtTokens(s.total_input_tokens + s.total_output_tokens + s.total_reasoning_tokens)}</td>
        <td class="num">${fmtMoney(s.total_cost_usd)}</td></tr>`).join("");
      // 固定 7 行, 不足补空行
      if (data.records.length < 7) {
        html += ('<tr>' + '<td>&nbsp;</td>'.repeat(8) + '</tr>').repeat(7 - data.records.length);
      }
      body.innerHTML = html;
    }
    const totalPages = Math.max(1, Math.ceil(data.total / 7));
    $("ses-pager").textContent = `${t("pageOf")} ${state.sessions.page} ${t("ofPages")} ${totalPages}`;
    $("ses-prev").disabled = state.sessions.page <= 1;
    $("ses-next").disabled = state.sessions.page >= totalPages;
  } catch (e) {
    if (seq === sesSeq) body.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--red);padding:20px">${t("loadFailed")}: ${escapeHtml(e.message)}</td></tr>`;
  }
}
function shortId(id) {
  const s = String(id || "");
  // 会话 ID 较长时省略中间, 保留头尾便于区分
  if (s.length <= 24) return s;
  const head = s.slice(0, 10);
  const tail = s.slice(-6);
  return `${head}…${tail}`;
}
function fmtDateTimeShort(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const pad = (x) => String(x).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/* ---------------- 使用记录 ---------------- */
let recSeq = 0;
async function loadRecords() {
  const seq = ++recSeq;
  const body = $("records-body");
  try {
    const q = new URLSearchParams({ page: state.records.page, page_size: 7 });
    if (state.records.model) q.set("model", state.records.model);
    const data = await api(`/api/usage/records?${q}`);
    if (seq !== recSeq) return; // 丢弃过期响应 (快速切页/翻页时旧请求)
    state.records.total = data.total;
    const sel = $("rec-model-filter");
    const cur = sel.value;
    sel.innerHTML = '<option value="">' + t("allModels") + '</option>' + data.models.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join("");
    sel.value = state.records.model || cur || "";
    $("rec-count").textContent = `${t("totalN")} ${fmtInt(data.total)} ${t("items")}`;
    if (!data.records.length) {
      body.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text3);padding:24px">${t("noData")}</td></tr>`;
    } else {
      let html = data.records.map((r) => `
        <tr><td class="key-name">${escapeHtml(r.key_name || "—")}</td>
        <td>${fmtDateTime(r.created_at)}</td>
        <td><span class="model-cell">${modelIcon(r.model)}${escapeHtml(r.model)}</span></td>
        <td class="num">${fmtTokens(r.input_tokens)}</td>
        <td class="num">${fmtTokens(r.output_tokens)}</td>
        <td class="num">${fmtTokens(r.reasoning_tokens)}</td>
        <td class="num">${fmtTokens(r.cache_read_tokens)}</td>
        <td class="num">${fmtMoney(r.cost_usd)}</td></tr>`).join("");
      // 固定 7 行, 不足补空行
      if (data.records.length < 7) {
        html += ('<tr>' + '<td>&nbsp;</td>'.repeat(8) + '</tr>').repeat(7 - data.records.length);
      }
      body.innerHTML = html;
    }
    const totalPages = Math.max(1, Math.ceil(data.total / 7));
    $("rec-pager").textContent = `${t("pageOf")} ${state.records.page} ${t("ofPages")} ${totalPages}`;
    $("pg-prev").disabled = state.records.page <= 1;
    $("pg-next").disabled = state.records.page >= totalPages;
  } catch (e) {
    if (seq === recSeq) body.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--red);padding:24px">${t("loadFailed")}: ${escapeHtml(e.message)}</td></tr>`;
  }
}

/* ---------------- 模型图标 ---------------- */
function modelIcon(m) {
  const s = String(m || "").toLowerCase();
  const base = s.split("-")[0];
  const map = { deepseek: "deepseek", glm: "glm", gpt: "gpt", grok: "grok", kimi: "kimi", meta: "meta", mimo: "mimo", minimax: "minimax", muse: "meta", qwen: "qwen", hy: "hy" };
  // hy2/hy3 等混元系列模型统一使用 hy 图标 (首段非精确 hy 时按前缀匹配)
  let name = map[base];
  if (!name) name = base.startsWith("hy") ? "hy" : "deepseek";
  const dark = document.documentElement.dataset.theme === "dark";
  const themed = dark && ["gpt", "grok", "mimo"].includes(name) ? `${name}-color` : name;
  return `<img src="icons/${themed}.svg" alt="${escapeHtml(m)}" title="${escapeHtml(m)}" style="width:16px;height:16px">`;
}
function refreshIcons() {
  if (!document.getElementById("page-stats").hidden) chartModel(state.data?.models);
}

/* ---------------- 组装 ---------------- */
function renderAll(data) {
  state.data = data;
  if (data.exchange_rate?.usd_cny) state.exchangeRate = data.exchange_rate.usd_cny;
  renderUsageBlocks(data.quota);
  renderOverview(data.totals);
  const homeVisible = !document.getElementById("page-home").hidden;
  const statsVisible = !document.getElementById("page-stats").hidden;
  // 只重建当前可见页面的图表 (hidden 页面的 canvas 尺寸为 0, 创建会失败)
  if (homeVisible) chartToday(data.today_trend);
  if (statsVisible) {
    renderStatsTotal(data.totals);
    renderDetail6(data.totals);
    chartModel(data.models);
    chartTrend(data.trend);
    $("trend-hint").textContent = t("trendHint");
  }
  $("tb-sync").textContent = data.logged_in ? `${t("lastSync")} ${fmtRelative(data.sync?.last_sync_at)} · ${fmtInt(data.sync?.total_records || 0)} ${t("records")}` : t("notLoggedIn");
  const accLabel = data.account_name || maskWs(data);
  $("tb-login").innerHTML = data.logged_in ? `<b>${t("loggedIn")}</b> · ${escapeHtml(accLabel)}` : t("notLoggedIn");
  $("tb-login").style.color = data.logged_in ? "" : "var(--red)";
  $("tb-login").title = t("userSwitchTip");
  const uc = $("tb-user-count");
  if (uc) {
    uc.hidden = !(Number(data.accounts_logged_in) > 0);
    uc.textContent = String(data.accounts_logged_in ?? 0);  // 仅已登录数 (与列表口径一致)
    uc.title = t("userCountTip");
  }
  const st = data.server_time || "";
  if (st) $("tb-updated").textContent = `${t("updatedAt")} ${st.slice(0, 16).replace("T", " ")}`;
  renderSyncBanner(data.progress);
  renderSettingsSyncProgress(data.progress);
}
function maskWs(data) {
  const ws = data?.quota?.workspace_id || "";
  return ws.length > 12 ? ws.slice(0, 8) + "…" : ws;
}

/* ---------------- 同步 ---------------- */
async function startSync(mode) {
  $("tb-refresh").disabled = true;
  $("btn-full-sync").disabled = true;
  try { await api("/api/sync?mode=" + mode, { method: "POST" }); } catch (e) { console.error(e); }
  pollUntilIdle();
}
function pollUntilIdle() {
  if (state.syncTimer) clearInterval(state.syncTimer);
  state.syncTimer = setInterval(async () => {
    try {
      const st = await api("/api/state");
      renderSyncBanner(st.progress);
      renderSettingsSyncProgress(st.progress);
      if (!st.progress.running) {
        clearInterval(state.syncTimer); state.syncTimer = null;
        $("tb-refresh").disabled = false;
        $("btn-full-sync").disabled = false;
        await loadDashboard();
        if (state.page === "settings") renderSettings();
        if (state.page === "overview") loadOverview(true).catch(() => {});
      }
    } catch (e) { /* ignore */ }
  }, 2500);
}
function renderSyncBanner(progress) {
  $("sync-indicator").hidden = !(progress && progress.running);
}
function renderSettingsSyncProgress(progress) {
  if (!progress || !progress.running) {
    $("set-sync-progress-desc").textContent = t("fullSyncDesc");
    $("set-sync-progress-val").textContent = "";
    return;
  }
  const phase = progress.phase === "usage" ? t("syncing") : t("syncing");
  $("set-sync-progress-desc").textContent = `${phase} · ${t("pageOf")} ${progress.page + 1}`;
  $("set-sync-progress-val").textContent = `${t("totalN")} ${fmtInt(progress.inserted)}`;
}

/* ---------------- 账户总览面板 (多账户聚合) ---------------- */
let ovSeq = 0;
let cOvTrendChart = null;
const OV_COLORS = ["#7c5cf6", "#4f8ef7", "#22c55e", "#d97706", "#06b6d4", "#ec4899"];

/* 开关控制侧边栏入口显隐; 关闭时若停留在总览页则退回首页 */
function applyOverviewPanel(show) {
  const btn = document.getElementById("side-overview");
  if (btn) btn.hidden = !show;
  if (!show && state.page === "overview") switchPage("home");
}

async function loadOverview(quiet = false) {
  const seq = ++ovSeq;
  if (!quiet) {
    const sKpi = `<div class="card kpi skeleton"><div class="sk-line w30"></div><div class="sk-line w40 lg"></div><div class="sk-line w50"></div></div>`;
    $("ov-summary-cards").innerHTML = sKpi.repeat(4);
    $("ov-accounts").innerHTML = `<div class="card ov-acc skeleton" style="height:140px"></div>`.repeat(2);
  }
  try {
    const data = await api("/api/accounts/overview");
    if (seq !== ovSeq) return; // 丢弃过期响应 (快速切换页面时旧请求)
    if (data.exchange_rate?.usd_cny) state.exchangeRate = data.exchange_rate.usd_cny;
    renderAccountOverview(data);
    // 已登录账号配额缓存缺失 (后台刷新中), 5s 后静默重拉一次
    const missing = (data.accounts || []).some((a) => a.logged_in && !a.quota);
    clearTimeout(state.ovRetryTimer);
    if (missing) state.ovRetryTimer = setTimeout(() => { if (state.page === "overview") loadOverview(true); }, 5000);
  } catch (e) {
    if (!quiet) toast(e.message || t("loadFailed"), "err");
  }
}

function renderAccountOverview(data) {
  const accounts = (data.accounts || []).map((a, i) => ({ ...a, color: OV_COLORS[i % OV_COLORS.length] }));
  // ---- 顶部汇总: 今日合计 ----
  const sum = accounts.reduce((acc, a) => {
    const tt = a.today || {};
    acc.req += tt.request_count || 0;
    acc.in += tt.total_input_tokens || 0;
    acc.out += tt.total_output_tokens || 0;
    acc.rsn += tt.total_reasoning_tokens || 0;
    acc.cost += tt.total_cost_usd || 0;
    return acc;
  }, { req: 0, in: 0, out: 0, rsn: 0, cost: 0 });
  const cards = [
    { cls: "c-violet", l: t("todayTotalReq"), v: fmtInt(sum.req) },
    { cls: "c-blue", l: t("todayTotalTokens"), v: fmtTokens(sum.in + sum.out + sum.rsn) },
    { cls: "c-cyan", l: t("todayTotalInput"), v: fmtTokens(sum.in) },
    { cls: "c-amber", l: t("todayTotalCost"), v: fmtMoney(sum.cost) },
  ];
  $("ov-summary-cards").innerHTML = cards.map((c) => `
    <div class="card kpi ${c.cls}"><div class="kpi-l">${c.l}</div><div class="kpi-v">${c.v}</div></div>`).join("");

  // ---- 7 日费用趋势对比 ----
  chartOvTrend(accounts);

  // ---- 账号卡片 ----
  $("ov-accounts").innerHTML = accounts.length
    ? accounts.map((a) => renderAccountCard(a)).join("")
    : `<div class="card ov-acc"><div class="ov-quota-empty">${t("noUsers")}</div></div>`;
}

function renderAccountCard(a) {
  // 配额三窗口: 有缓存时展示, 缓存未就绪 (后台刷新中) 显示占位
  let quotaHtml;
  if (a.quota && a.quota.success && a.quota.windows) {
    quotaHtml = `<div class="ov-quota-grid">${a.quota.windows.map((w) => {
      const used = Number(w.used) || 0;
      const cls = w.label === "5h Rolling" ? "c-rolling" : w.label === "Weekly" ? "c-week" : "c-month";
      return `<div class="ub ${cls} ov-ub">
        <div class="ub-head"><span class="ub-l">${(QUOTA_LABEL[w.label] || (() => w.label))()}</span><span class="ub-rem">${t("remaining")} ${(Number(w.remaining) || 0).toFixed(0)}%</span></div>
        <div class="ub-bar"><div class="ub-bar-fill" style="width:${used}%"></div></div>
        <div class="ub-meta"><span>${t("used")} ${used.toFixed(0)}%</span><span>${t("resetsIn")} ${fmtDur(w.reset_in_sec)}</span></div>
      </div>`;
    }).join("")}</div>`;
  } else {
    quotaHtml = `<div class="ov-quota-empty">${t("quotaNotReady")}</div>`;
  }
  const tt = a.today || {};
  const spark = sparklineSvg((a.today_trend || []).map((d) => d.input + d.output + d.reasoning), a.color);
  return `<div class="card ov-acc">
    <div class="ov-acc-head">
      <span class="ov-acc-name">${escapeHtml(a.name)}</span>
      <span class="ov-acc-badges">${a.active ? `<span class="plan-badge">${t("activeAccount")}</span>` : ""}</span>
      <span class="ov-acc-sync">${t("lastSync")} ${fmtRelative(a.last_sync_at)}</span>
    </div>
    ${quotaHtml}
    <div class="tc-grid ov-today">
      <div class="tc"><div class="tc-l">${t("totalRequests")}</div><div class="tc-v">${fmtInt(tt.request_count)}</div></div>
      <div class="tc"><div class="tc-l">${t("input")}</div><div class="tc-v">${fmtTokens(tt.total_input_tokens)}</div></div>
      <div class="tc"><div class="tc-l">${t("output")}</div><div class="tc-v">${fmtTokens(tt.total_output_tokens)}</div></div>
      <div class="tc"><div class="tc-l">${t("colReasoning")}</div><div class="tc-v">${fmtTokens(tt.total_reasoning_tokens)}</div></div>
      <div class="tc"><div class="tc-l">${t("colCost")}</div><div class="tc-v">${fmtMoney(tt.total_cost_usd)}</div></div>
      <div class="tc"><div class="tc-l">${t("todayTrend")}</div><div class="tc-v ov-spark">${spark}</div></div>
    </div>
  </div>`;
}

/* 24h 迷你趋势: 纯 SVG 折线 (无 Chart 实例, 轻量随卡片渲染) */
function sparklineSvg(values, color) {
  const w = 120, h = 30, n = values.length;
  if (!n) return `<svg viewBox="0 0 ${w} ${h}" class="spark"></svg>`;
  const max = Math.max(...values, 1);
  const step = n > 1 ? w / (n - 1) : w;
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(h - 2 - (v / max) * (h - 4)).toFixed(1)}`);
  return `<svg viewBox="0 0 ${w} ${h}" class="spark" preserveAspectRatio="none">
    <polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
    <polyline points="0,${h} ${pts.join(" ")} ${w},${h}" fill="${color}" opacity="0.12" stroke="none"/>
  </svg>`;
}

/* 7 日费用对比: 全部账号合计为 总费用/请求/Token 三条线, 与用量趋势样式一致 */
function chartOvTrend(accounts) {
  const canvas = $("ov-trend-chart");
  if (!canvas) return;
  if (cOvTrendChart) { cOvTrendChart.destroy(); cOvTrendChart = null; }
  const dated = accounts.filter((a) => (a.daily7 || []).length);
  if (!dated.length) return;
  const dateSet = new Set();
  dated.forEach((a) => a.daily7.forEach((d) => dateSet.add(d.date)));
  const labels = [...dateSet].sort();
  // 全部账号合计: 每日 总费用 / 请求数 / Token 总数 (输入+输出+推理)
  const costSum = {}, reqSum = {}, tokSum = {};
  dated.forEach((a) => a.daily7.forEach((d) => {
    costSum[d.date] = (costSum[d.date] || 0) + (d.total_cost_usd || 0);
    reqSum[d.date] = (reqSum[d.date] || 0) + (d.request_count || 0);
    tokSum[d.date] = (tokSum[d.date] || 0) + (d.total_input_tokens || 0) + (d.total_output_tokens || 0) + (d.total_reasoning_tokens || 0);
  }));
  const costData = labels.map((dt) => costSum[dt] || 0);
  const reqData = labels.map((dt) => reqSum[dt] || 0);
  const tokData = labels.map((dt) => tokSum[dt] || 0);
  cOvTrendChart = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: t("totalCost"), data: costData, borderColor: COLOR.input, borderWidth: 2, pointRadius: 1.5, tension: 0.3, yAxisID: "y" },
        { label: t("totalRequests"), data: reqData, borderColor: COLOR.output, borderWidth: 2, pointRadius: 1.5, tension: 0.3, borderDash: [4, 3], yAxisID: "y1" },
        { label: t("totalTokens"), data: tokData, borderColor: COLOR.reasoning, borderWidth: 2, pointRadius: 1.5, tension: 0.3, borderDash: [4, 3], yAxisID: "y2" },
      ],
    },
    options: {
      responsive: false, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 }, color: cssVar("--text2") } },
        tooltip: { callbacks: { label: (it) => it.dataset.label === t("totalRequests") ? ` ${it.dataset.label}: ${fmtInt(it.parsed.y)}` : it.dataset.label === t("totalTokens") ? ` ${it.dataset.label}: ${fmtTokens(it.parsed.y)}` : ` ${it.dataset.label}: ${fmtMoney(it.parsed.y)}` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: cssVar("--text3"), font: { size: 10 }, maxTicksLimit: 7 } },
        y: { position: "left", grid: { color: cssVar("--grid") }, ticks: { color: cssVar("--text3"), font: { size: 10 }, callback: (v) => fmtMoney(v) } },
        y1: { position: "right", grid: { display: false }, ticks: { color: cssVar("--text3"), font: { size: 10 } } },
        y2: { position: "right", display: false },  // 总 Token 独立隐藏轴 (与用量趋势一致)
      },
    },
  });
  cOvTrendChart.resize();
}

/* ---------------- 设置页 ---------------- */
async function renderSettings() {
  try {
    const st = await api("/api/state");
    $("set-sync-info").textContent = st.sync && st.sync.last_sync_at
      ? `${t("lastSync")} ${fmtDateTime(st.sync.last_sync_at)} (${st.sync.last_sync_status}) · ${t("totalN")} ${fmtInt(st.sync.total_records || 0)} ${t("items")}`
      : t("never");
    $("set-datadir").textContent = st.datadir || "—";
    const settings = await api("/api/settings");
    state.settings = settings;
    syncSettingsPills();
    $("set-auto-sync").checked = settings.auto_sync !== false;
    // 开机自启仅 mac 打包版展示 (LaunchAgent 实现)
    const macApp = isMac() && window.pywebview !== undefined;
    $("row-autostart").hidden = !macApp;
    if (macApp) $("set-autostart").checked = settings.autostart === true;
    $("set-overview-panel").checked = settings.show_accounts_panel === true;
    await fetchAccounts();  // 账户列表 (失败不阻塞其他设置渲染)
  } catch (e) { /* ignore */ }
}
function syncSettingsPills() {
  const s = state.settings;
  document.querySelectorAll("#set-interval-pills .pill").forEach((b) => b.classList.toggle("active", Number(b.dataset.v) === Number(s.sync_interval_sec)));
  document.querySelectorAll("#set-window-pills .pill").forEach((b) => b.classList.toggle("active", (s.window_days == null ? "all" : String(s.window_days)) === b.dataset.v));
}

/* ---------------- 多用户: 顶栏切换器 ---------------- */

/* 登录流程期间的账户变化监视: 登录窗是独立窗口, 成功后的跨窗口通知
   (load_url 同URL跳过 / evaluate_js 时序) 均不可靠, 用短轮询兜底保证
   账户列表/顶栏计数即时刷新. 5 分钟无变化自动停止. */
let loginWatchTimer = null;
function startLoginWatch() {
  stopLoginWatch();
  let baseline = "";
  const startedAt = Date.now();
  const poll = async () => {
    if (Date.now() - startedAt > 5 * 60 * 1000) { stopLoginWatch(); return; }
    try {
      const r = await api("/api/accounts");
      const sig = JSON.stringify((r.accounts || []).map((a) => [a.id, a.has_token, a.name])) + "|" + r.active_id;
      if (!baseline) { baseline = sig; return; }  // 首轮采基线
      if (sig !== baseline) {
        stopLoginWatch();
        await loadDashboard();
        if (state.page === "settings") renderSettings().catch(() => {});
        else if (state.page === "records") { loadSessions().catch(() => {}); loadRecords().catch(() => {}); }
        if (state.page === "overview") loadOverview(true).catch(() => {});
      }
    } catch (e) { /* ignore */ }
  };
  poll();
  loginWatchTimer = setInterval(poll, 2000);
}
function stopLoginWatch() {
  if (loginWatchTimer) { clearInterval(loginWatchTimer); loginWatchTimer = null; }
}

async function toggleUserMenu(force) {
  const menu = $("user-menu");
  if (!menu) return;
  const show = force !== undefined ? force : menu.hidden;
  if (!show) { menu.hidden = true; return; }
  try {
    const r = await api("/api/accounts");
    renderUserMenu((r.accounts || []).filter((a) => a.has_token), r.active_id);
    menu.hidden = false;
  } catch (e) { toast(t("loadFailed"), "err"); }
}
function renderUserMenu(accounts, activeId) {
  const menu = $("user-menu");
  menu.innerHTML = (accounts.length ? accounts.map((a) => `
    <div class="um-item" data-id="${a.id}">
      <span class="um-check">${a.id === activeId ? "✓" : ""}</span>
      <span class="um-meta">
        <span class="um-name">${escapeHtml(a.name)}</span>
        <span class="um-ws">${escapeHtml(a.workspace_id || "—")}${a.has_token ? "" : " · " + t("notLoggedIn")}</span>
      </span>
    </div>`).join("") : `<div class="um-item um-empty">${t("noUsers")}</div>`) +
    `<div class="um-item um-manage" id="um-manage"><span class="um-check">⚙</span><span class="um-meta"><span class="um-name">${t("setUsers")}</span></span></div>`;
  menu.querySelectorAll(".um-item[data-id]").forEach((el) => {
    el.addEventListener("click", async () => {
      const id = Number(el.dataset.id);
      toggleUserMenu(false);
      if (id === activeId) return;
      try {
        await api("/api/accounts/switch", { method: "POST", body: JSON.stringify({ id }) });
        toast(t("switchedAccount"));
        await loadDashboard();
        if (state.page === "settings") renderSettings().catch(() => {});
        else if (state.page === "records") { loadSessions().catch(() => {}); loadRecords().catch(() => {}); }
        if (state.page === "overview") loadOverview(true).catch(() => {});
      } catch (e) { toast(e.message || t("loadFailed"), "err"); }
    });
  });
  const mg = $("um-manage");
  if (mg) mg.addEventListener("click", () => { toggleUserMenu(false); switchPage("settings"); });
}

/* ---------------- 多用户: 设置页列表 ---------------- */
async function fetchAccounts() {
  const r = await api("/api/accounts");
  renderUsersList(r.accounts || [], r.active_id);
}
function renderUsersList(accounts, activeId) {
  const box = $("users-list");
  if (!box) return;
  const users = (accounts || []).filter((a) => a.has_token);  // 未登录行不展示 (退出即移除语义)
  if (!users.length) {
    box.innerHTML = `<div class="hint" style="padding:12px 16px">${t("noUsers")}</div>`;
    return;
  }
  box.innerHTML = users.map((a) => {
    const isActive = a.id === activeId;
    const actions = isActive
      ? `<button class="btn" data-act="relogin">${t("relogin")}</button>
         <button class="btn" data-act="rename">${t("renameBtn")}</button>
         <button class="btn btn-danger" data-act="logout">${t("logout")}</button>`
      : `<button class="btn" data-act="switch">${t("switchTo")}</button>
         <button class="btn" data-act="rename">${t("renameBtn")}</button>
         <button class="btn btn-danger" data-act="delete">${t("deleteUser")}</button>`;
    return `
    <div class="user-row${isActive ? " active" : ""}" data-id="${a.id}">
      <div class="ur-meta">
        <div class="ur-name">${escapeHtml(a.name)}${isActive ? `<span class="badge ok ur-badge">${t("currentUserBadge")}</span>` : ""}</div>
        <div class="ur-ws">${escapeHtml(a.workspace_id || "—")} · ${t("loggedIn")}</div>
      </div>
      <div class="ur-actions">${actions}</div>
    </div>`;
  }).join("");
}
async function onUserRowAction(id, act) {
  if (act === "switch") {
    try {
      await api("/api/accounts/switch", { method: "POST", body: JSON.stringify({ id }) });
      toast(t("switchedAccount"));
      await loadDashboard();
      renderSettings().catch(() => {});
      if (state.page === "overview") loadOverview(true).catch(() => {});
    } catch (e) { toast(e.message || t("loadFailed"), "err"); }
    return;
  }
  if (act === "relogin") {
    startLoginWatch();
    const a = await pywebviewApi();
    if (a && a.open_login) { a.open_login("relogin"); return; }
    try {  // 浏览器兜底
      await api("/api/relogin", { method: "POST", body: "{}" });
      toast(t("loginNote"));
    } catch (e) { toast(e.message || t("loadFailed"), "err"); }
    return;
  }
  if (act === "logout") {
    const accounts = (await api("/api/accounts").catch(() => ({ accounts: [] }))).accounts || [];
    const acc = accounts.find((x) => x.id === id);
    showModal({
      title: t("logout"), danger: true,
      message: escapeHtml(t("logoutUserConfirm").replace("{name}", acc ? acc.name : "")),
      okText: t("confirm"),
      onOk: async () => {
        try {
          await api("/api/logout", { method: "POST", body: "{}" });
          toast(t("loggedOut"));
          const r = await api("/api/accounts").catch(() => ({ accounts: [] }));
          renderUsersList(r.accounts || [], r.active_id);
          await loadDashboard();
          if (state.page === "overview") loadOverview(true).catch(() => {});  // 退出后账号卡片即时移除
          if (!(r.accounts || []).some((x) => x.has_token)) showLoginOverlay(true);  // 全部退出 -> 欢迎页
        } catch (e) { toast(e.message || t("loadFailed"), "err"); }
      },
    });
    return;
  }
  const accounts = (await api("/api/accounts").catch(() => ({ accounts: [] }))).accounts || [];
  const acc = accounts.find((x) => x.id === id);
  if (act === "rename") {
    let renamed = acc ? acc.name : "";
    showModal({
      title: t("renameTitle"),
      message: `<input id="rename-input" class="select" maxlength="50" value="${escapeHtml(renamed)}">`,
      okText: t("save"),
      onOk: async () => {
        try {
          await api("/api/accounts/rename", { method: "POST", body: JSON.stringify({ id, name: renamed }) });
          toast(t("userRenamed"));
          renderSettings().catch(() => {});
          loadDashboard(true);
          if (state.page === "overview") loadOverview(true).catch(() => {});  // 卡片名称即时更新
        } catch (e) { toast(e.message || t("loadFailed"), "err"); }
      },
    });
    const input = $("rename-input");
    if (input) {
      input.addEventListener("input", () => { renamed = input.value; });
      input.focus();
    }
    return;
  }
  if (act === "delete") {
    showModal({
      title: t("deleteUserTitle"), danger: true,
      message: escapeHtml(t("deleteUserConfirm").replace("{name}", acc ? acc.name : `#${id}`)),
      okText: t("confirm"),
      onOk: async () => {
        try {
          const r = await api("/api/accounts/delete", { method: "POST", body: JSON.stringify({ id }) });
          toast(t("userDeleted"));
          await loadDashboard();
          renderSettings().catch(() => {});
          if (state.page === "overview") loadOverview(true).catch(() => {});
          if ((r.remaining ?? 1) === 0) showLoginOverlay(true);
        } catch (e) { toast(e.message || t("loadFailed"), "err"); }
      },
    });
  }
}

/* ---------------- 登录状态 ---------------- */
let loginPollTimer = null;
function showLoginOverlay(show) {
  // 遮罩背景不透明, 直接显示即可覆盖页面; 不要隐藏 .app (会连同遮罩一起隐藏)
  $("login-overlay").hidden = !show;
  if (show) {
    // 欢迎页显示时轮询登录状态: 独立登录窗登录成功后自动进入面板
    if (loginPollTimer) clearInterval(loginPollTimer);
    loginPollTimer = setInterval(async () => {
      try {
        const st = await api("/api/state");
        if (st.logged_in) {
          clearInterval(loginPollTimer);
          loginPollTimer = null;
          showLoginOverlay(false);
          await loadDashboard();
          renderSettings().catch(() => {});
          if (state.page === "overview") loadOverview(true).catch(() => {});  // 新登录账号卡片即时出现
        }
      } catch (e) { /* ignore */ }
    }, 2000);
  } else if (loginPollTimer) {
    clearInterval(loginPollTimer);
    loginPollTimer = null;
  }
}
async function checkState() {
  try {
    const st = await api("/api/state");
    if (!st.logged_in) { showLoginOverlay(true); return; }
    showLoginOverlay(false);
    if (st.progress && st.progress.running) pollUntilIdle();
    await loadDashboard();
  } catch (e) { console.error("state check failed", e); }
}

/* 登录成功通知 (后端 evaluate_js 触发, 见 main.on_login_success):
   就地刷新数据/顶栏/账户列表, 不依赖整页重载 (同 URL load_url 可能被跳过) */
window.gousageOnLoginSuccess = async function () {
  try {
    const st = await api("/api/state");
    if (st.logged_in) showLoginOverlay(false);  // 欢迎页场景: 直接进入面板
  } catch (e) { /* ignore */ }
  loadDashboard().catch(() => {});
  if (state.page === "settings") renderSettings().catch(() => {});
  else if (state.page === "records") { loadSessions().catch(() => {}); loadRecords().catch(() => {}); }
};

/* ---------------- 事件绑定 ---------------- */
function bindEvents() {
  document.querySelectorAll(".side-item").forEach((btn) => btn.addEventListener("click", () => switchPage(btn.dataset.page)));

  document.querySelectorAll("#home-pills .pill").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#home-pills .pill").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); state.range = b.dataset.r; loadDashboard();
  }));
  document.querySelectorAll("#stats-pills .pill").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#stats-pills .pill").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); state.statsRange = b.dataset.r; loadDashboard();
  }));
  $("mr-dim").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    document.querySelectorAll("#mr-dim button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active"); state.modelDim = b.dataset.dim;
    if (state.data) chartModel(state.data.models);
  });
  $("tb-refresh").addEventListener("click", () => startSync("incremental"));
  $("btn-full-sync").addEventListener("click", () => {
    showModal({ title: t("fullSync"), message: t("fullSyncConfirm"), okText: t("startSync"), onOk: () => startSync("full") });
  });
  $("pg-prev").addEventListener("click", () => { if (state.records.page > 1) { state.records.page--; loadRecords(); } });
  $("pg-next").addEventListener("click", () => { state.records.page++; loadRecords(); });
  $("ses-prev").addEventListener("click", () => { if (state.sessions.page > 1) { state.sessions.page--; loadSessions(); } });
  $("ses-next").addEventListener("click", () => { state.sessions.page++; loadSessions(); });
  $("rec-model-filter").addEventListener("change", (e) => { state.records.model = e.target.value; state.records.page = 1; loadRecords(); });

  // 半自动更新: 后台下载新版本 zip 到 ~/Downloads, 完成后 Finder 定位;
  // 失败兜底打开 Releases 页手动下载.
  async function downloadUpdateFlow(desc) {
    try {
      const start = await api("/api/update/download", { method: "POST" });
      if (start && start.ok === false) throw new Error(start.error || "");
      if (desc) desc.textContent = t("downloading");
      for (let i = 0; i < 120; i++) {  // 1.5s x 120 ≈ 3 分钟上限
        await new Promise((res) => setTimeout(res, 1500));
        const st = await api("/api/update/download/status");
        if (st.state === "done") {
          toast(t("updateReady"));
          if (desc) desc.textContent = `${t("updateReady")}${st.latest ? ` (${st.latest})` : ""}`;
          return;
        }
        if (st.state === "no_update") { toast(t("updateNone")); return; }
        if (st.state === "error" || st.state === "no_asset") throw new Error(st.error || st.state);
      }
      throw new Error("timeout");
    } catch (e) {
      showModal({
        title: t("downloadFailed"), message: escapeHtml(e.message || ""), okText: t("openReleasePage"),
        onOk: () => { api("/api/update/open", { method: "POST" }).catch(() => {}); },
      });
    }
  }

  // 检查更新: 有新版 -> 弹窗 -> 应用内下载 zip 并在 Finder 定位
  $("btn-check-update").addEventListener("click", async () => {
    const btn = $("btn-check-update");
    const desc = $("set-update-desc");
    const prevText = btn.textContent;
    btn.disabled = true;
    btn.textContent = t("checkingUpdate");
    try {
      const r = await api("/api/update/check");
      if (r.error) throw new Error(r.error);
      if (r.has_update) {
        desc.textContent = `${t("updateFound")} ${r.latest}`;
        showModal({
          title: t("updateFound"),
          message: `<b>${r.latest}</b> (${t("currentVersion")} v${r.current})<br><br>${escapeHtml((r.notes || "").slice(0, 300)) || ""}`,
          okText: t("goDownload"),
          onOk: () => { downloadUpdateFlow(desc); },
        });
      } else {
        desc.textContent = `${t("updateNone")} (v${r.current})`;
        toast(t("updateNone"));
      }
    } catch (e) {
      desc.textContent = `${t("updateFailed")}: ${t("checkUpdateDesc")}`;
      showModal({ title: t("updateFailed"), message: escapeHtml(e.message || ""), okText: t("ok") });
    } finally {
      btn.disabled = false;
      btn.textContent = prevText;
    }
  });

  document.querySelectorAll("#set-interval-pills .pill").forEach((b) => b.addEventListener("click", async () => {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ sync_interval_sec: Number(b.dataset.v) }) });
    state.settings = await api("/api/settings");
    syncSettingsPills(); restartAutoSync(); toast(`${t("syncIntervalSet")} ${b.textContent}`);
  }));
  document.querySelectorAll("#set-window-pills .pill").forEach((b) => b.addEventListener("click", async () => {
    const v = b.dataset.v === "all" ? null : Number(b.dataset.v);
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ window_days: v }) });
    state.settings = await api("/api/settings");
    syncSettingsPills();
    toast(t("syncRangeUpdated"));
  }));
  document.querySelectorAll("#set-theme-pills .pill").forEach((b) => b.addEventListener("click", () => applyDarkMode(b.dataset.v === "dark")));
  document.querySelectorAll("#set-currency-pills .pill").forEach((b) => b.addEventListener("click", () => applyCurrency(b.dataset.v)));
  document.querySelectorAll("#set-lang-pills .pill").forEach((b) => b.addEventListener("click", () => applyLang(b.dataset.v)));
  $("set-auto-sync").addEventListener("change", (e) => {
    state.settings.auto_sync = e.target.checked;
    api("/api/settings", { method: "PUT", body: JSON.stringify({ auto_sync: e.target.checked }) }).catch(() => {});
    restartAutoSync();
  });
  $("set-autostart").addEventListener("change", (e) => {
    state.settings.autostart = e.target.checked;
    api("/api/settings", { method: "PUT", body: JSON.stringify({ autostart: e.target.checked }) })
      .then((r) => { if (r && r.autostart_applied === false) toast(t("autostartFail")); })
      .catch(() => {});
  });
  // 账户总览面板开关: 控制侧边栏入口显隐 (关闭时停留在总览页则退回首页)
  $("set-overview-panel").addEventListener("change", (e) => {
    state.settings.show_accounts_panel = e.target.checked;
    api("/api/settings", { method: "PUT", body: JSON.stringify({ show_accounts_panel: e.target.checked }) }).catch(() => {});
    applyOverviewPanel(e.target.checked);
  });
  // 账户操作已合并进「OpenCode 账户」卡片内的账号行 (relogin/logout 为行级动作)

  // 多用户: 顶栏切换器 + 设置页账户列表
  $("tb-login").addEventListener("click", () => toggleUserMenu());
  document.addEventListener("click", (e) => {
    const menu = $("user-menu");
    if (menu && !menu.hidden && !e.target.closest(".user-switch")) toggleUserMenu(false);
  });
  $("btn-add-user").addEventListener("click", async () => {
    startLoginWatch();
    const a = await pywebviewApi();
    if (a && a.open_login) { a.open_login("add"); return; }
    try {  // 浏览器环境兜底
      await api("/api/accounts/add", { method: "POST", body: "{}" });
      toast(t("loginNote"));
    } catch (e) { toast(e.message || t("loadFailed"), "err"); }
  });
  $("users-list").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const row = e.target.closest(".user-row");
    if (!row) return;
    onUserRowAction(Number(row.dataset.id), btn.dataset.act).catch((err) => toast(String(err.message || err), "err"));
  });
  $("btn-login").addEventListener("click", async () => {
    startLoginWatch();
    const a = await pywebviewApi();
    if (a && a.open_login) { a.open_login(); return; }  // 弹出独立登录窗口
    // 浏览器环境兜底: 跳转授权页
    $("btn-login").disabled = true;
    $("btn-login").textContent = t("loginBtn") + "…";
    await api("/api/relogin", { method: "POST" });
  });
  $("btn-quit-app").addEventListener("click", async () => {
    const a = await pywebviewApi();
    if (a) a.quit();
  });
  bindTitlebar();
}

/* ---------------- 自动同步 ---------------- */
let autoSyncTimer = null;
function restartAutoSync() {
  if (autoSyncTimer) clearInterval(autoSyncTimer);
  if (state.settings.auto_sync === false) return;
  const sec = Math.max(30, Number(state.settings?.sync_interval_sec) || 300) * 1000;
  autoSyncTimer = setInterval(() => {
    const prog = state.data && state.data.progress;
    if (!prog || !prog.running) startSync("incremental");
  }, sec);
}

/* ---------------- 图表辅助 ---------------- */
function cssVar(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim() || "#8a94a8";
}
function rerenderCharts() {
  if (!state.data) return;
  if (!document.getElementById("page-home").hidden) chartToday(state.data.today_trend);
  if (!document.getElementById("page-stats").hidden) {
    chartModel(state.data.models);
    chartTrend(state.data.trend);
  }
}

/* 窗口尺寸变化: 长防抖(250ms)后执行一次轻量 chart.resize()
   (只处理可见页图表 — hidden 页面容器尺寸为 0, resize() 会死循环卡死) */
function safeResize(chart) {
  if (!chart || !chart.canvas) return;
  const box = chart.canvas.parentElement;
  if (box && box.clientWidth > 0 && box.clientHeight > 0) chart.resize();
}
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (!document.getElementById("page-home").hidden) safeResize(cToday);
    if (!document.getElementById("page-stats").hidden) {
      safeResize(cModel);
      safeResize(cTrend);
    }
    if (!document.getElementById("page-overview").hidden) safeResize(cOvTrendChart);
  }, 250);
});

/* ---------------- 启动 ---------------- */
let APP_VERSION = "";  // 后端版本号 (app/__init__.py), 唯一版本源
(async function init() {
  let dark = false, cur = "CNY", l = "zh";
  try {
    dark = localStorage.getItem("gousage-dark") === "1";
    cur = localStorage.getItem("gousage-currency") || "CNY";
    l = localStorage.getItem("gousage-lang") || "zh";
  } catch (e) { /* ignore */ }
  try { const v = await api("/api/version"); APP_VERSION = v.version || ""; } catch (e) { /* ignore */ }
  applyLang(l);
  applyDarkMode(dark);
  applyCurrency(cur);
  bindEvents();
  try { state.settings = await api("/api/settings"); } catch (e) { /* ignore */ }
  syncSettingsPills();
  $("set-auto-sync").checked = state.settings.auto_sync !== false;
  $("set-overview-panel").checked = state.settings.show_accounts_panel === true;
  applyOverviewPanel(state.settings.show_accounts_panel === true);
  await checkState();
  restartAutoSync();
})();
