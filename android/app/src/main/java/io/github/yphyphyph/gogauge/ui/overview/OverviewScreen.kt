package io.github.yphyphyph.gogauge.ui.overview

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.yphyphyph.gogauge.data.model.AccountOverview
import io.github.yphyphyph.gogauge.data.model.DailyStat
import io.github.yphyphyph.gogauge.ui.MainViewModel
import io.github.yphyphyph.gogauge.ui.Strings
import io.github.yphyphyph.gogauge.ui.components.Accent
import io.github.yphyphyph.gogauge.ui.components.CardHeader
import io.github.yphyphyph.gogauge.ui.components.GgPullIndicator
import io.github.yphyphyph.gogauge.ui.components.GgCard
import io.github.yphyphyph.gogauge.ui.components.Hint
import io.github.yphyphyph.gogauge.ui.components.KpiCard
import io.github.yphyphyph.gogauge.ui.components.QuotaCard
import io.github.yphyphyph.gogauge.ui.components.Sparkline
import io.github.yphyphyph.gogauge.ui.components.TrendLineChart
import io.github.yphyphyph.gogauge.ui.theme.NumFontFamily
import io.github.yphyphyph.gogauge.util.Fmt

/**
 * 账户总览面板 — desktop v2.1.0 page-overview 移动端移植:
 * 今日合计 KPI (总请求 / 总 TOKEN / 总输入 / 总费用) +
 * 账号卡片 (配额三窗口 + 今日用量 + 24h 迷你趋势) +
 * 7 日费用趋势对比 (全部账号合计的 总费用 / 请求 / Token 三条线).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OverviewScreen(vm: MainViewModel = viewModel()) {
    val s = vm.s

    // 进入页面开始 5s 静默重拉循环; 离开页面停止 (desktop ovRetryTimer parity)
    DisposableEffect(Unit) {
        vm.setOverviewVisible(true)
        onDispose { vm.setOverviewVisible(false) }
    }
    LaunchedEffect(Unit) { vm.loadOverview() }
    // 底层数据变化 (同步完成 / 账号切换 / 登录变动) 时静默刷新
    LaunchedEffect(vm.dashboard, vm.accounts, vm.activeAccountId) { vm.loadOverview(true) }

    val ptrState = rememberPullToRefreshState()
    Box(Modifier.fillMaxSize()) {
        PullToRefreshBox(
            isRefreshing = vm.isSyncing(),
            onRefresh = { vm.refreshNow() },
            state = ptrState,
            modifier = Modifier.fillMaxSize(),
            indicator = {},
        ) {
            Column(
                Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 14.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(s.accountOverview, style = MaterialTheme.typography.titleLarge)
                    IconButton(onClick = { vm.loadOverview() }, enabled = !vm.isSyncing()) {
                        Icon(
                            Icons.Filled.Refresh,
                            contentDescription = s.refresh,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }

                val data = vm.overview
                if (data == null) {
                    Box(
                        Modifier.fillMaxWidth().padding(vertical = 40.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(modifier = Modifier.width(28.dp))
                    }
                } else {
                    // ---- 今日合计 (跨账号求和) ----
                    SummaryCards(data.accounts, vm, data.usdCny)

                    // ---- 账号卡片 ----
                    if (data.accounts.isEmpty()) {
                        GgCard {
                            Text(
                                s.noUsers,
                                fontSize = 13.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                            )
                        }
                    } else {
                        data.accounts.forEachIndexed { i, acc ->
                            AccountCard(acc, vm, data.usdCny, OvColors[i % OvColors.size])
                        }
                    }

                    // ---- 7 日费用趋势对比: 全部账号合计三条线 (置于账号卡片下方, 桌面 parity) ----
                    GgCard {
                        CardHeader(s.costTrend7d, trailing = { Hint("7 ${s.day}") })
                        TrendLineChart(
                            trend = mergeDaily(data.accounts.map { it.daily7 }),
                            s = s,
                            labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            gridLineColor = MaterialTheme.colorScheme.outline,
                            currency = vm.currency,
                            usdCny = data.usdCny,
                        )
                    }
                }
                Spacer(Modifier.height(8.dp))
            }
        }
        GgPullIndicator(
            state = ptrState,
            isRefreshing = vm.isSyncing(),
            modifier = Modifier.align(Alignment.TopCenter),
        )
    }
}

/** 账号配色 — desktop OV_COLORS parity (按账号顺序循环取色). */
private val OvColors = listOf(
    androidx.compose.ui.graphics.Color(0xFF7C5CF6),
    androidx.compose.ui.graphics.Color(0xFF4F8EF7),
    androidx.compose.ui.graphics.Color(0xFF22C55E),
    androidx.compose.ui.graphics.Color(0xFFD97706),
    androidx.compose.ui.graphics.Color(0xFF06B6D4),
    androidx.compose.ui.graphics.Color(0xFFEC4899),
)

/** 今日合计 KPI — desktop renderAccountOverview sum cards parity (violet/blue/cyan/amber). */
@Composable
private fun SummaryCards(accounts: List<AccountOverview>, vm: MainViewModel, usdCny: Double) {
    val s = vm.s
    var req = 0L
    var inputTokens = 0L
    var outputTokens = 0L
    var reasoningTokens = 0L
    var costUsd = 0.0
    accounts.forEach { a ->
        req += a.today.requestCount
        inputTokens += a.today.totalInputTokens
        outputTokens += a.today.totalOutputTokens
        reasoningTokens += a.today.totalReasoningTokens
        costUsd += a.today.totalCostUsd
    }
    val cards = listOf(
        Triple(s.todayTotalReq, Fmt.int(req), "") to Accent.violet,
        Triple(s.todayTotalTokens, Fmt.tokens(inputTokens + outputTokens + reasoningTokens), "") to Accent.blue,
        Triple(s.todayTotalInput, Fmt.tokens(inputTokens), "") to Accent.cyan,
        Triple(s.todayTotalCost, Fmt.money(costUsd, vm.currency, usdCny), "") to Accent.amber,
    )
    Column {
        cards.chunked(2).forEach { row ->
            Row(
                Modifier.fillMaxWidth().padding(bottom = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                row.forEach { (c, accent) ->
                    KpiCard(label = c.first, value = c.second, sub = c.third, accent = accent, modifier = Modifier.weight(1f))
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/** 单账号卡片 — desktop renderAccountCard parity. */
@Composable
private fun AccountCard(acc: AccountOverview, vm: MainViewModel, usdCny: Double, accentColor: androidx.compose.ui.graphics.Color) {
    val s = vm.s
    GgCard {
        // 头部: 名称 + 当前活跃徽标 + 上次同步时间
        Row(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(acc.name, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 1)
            if (acc.active) {
                Spacer(Modifier.width(6.dp))
                Text(
                    s.activeAccount,
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.tertiary,
                    modifier = Modifier
                        .background(MaterialTheme.colorScheme.tertiary.copy(alpha = 0.12f), RoundedCornerShape(6.dp))
                        .padding(horizontal = 5.dp, vertical = 1.dp),
                )
            }
            Spacer(Modifier.weight(1f))
            Text(
                "${s.lastSync} ${Fmt.relative(acc.lastSyncAt, s.justNow, s.minAgo, s.hrAgo, s.dayAgo, s.never)}",
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
        }

        // 配额三窗口: 缓存未就绪时显示占位 (后台刷新中)
        val quota = acc.quota
        if (quota != null && quota.success && quota.windows.isNotEmpty()) {
            Column(
                Modifier.padding(horizontal = 14.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                quota.windows.forEach { w ->
                    QuotaCard(
                        label = quotaLabel(w.label, s),
                        usedPercent = w.used,
                        remainingText = "${s.remaining} ${w.remaining.toInt()}%",
                        resetText = "${s.resetsIn} ${Fmt.dur(w.resetInSec.toLong(), s.dUnit, s.hUnit, s.mUnit, s.soon)}",
                        accent = quotaAccent(w.label),
                    )
                }
            }
        } else {
            Text(
                s.quotaNotReady,
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .padding(horizontal = 16.dp, vertical = 4.dp)
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f), RoundedCornerShape(10.dp))
                    .padding(horizontal = 14.dp, vertical = 12.dp),
            )
        }

        // 今日用量 6 格 (含 24h 迷你趋势)
        TodayGrid(acc, vm, usdCny, accentColor)
        Spacer(Modifier.height(6.dp))
    }
}

/** 今日用量 2 列网格 — desktop .tc-grid.ov-today parity, 第 6 格为 24h sparkline. */
@Composable
private fun TodayGrid(acc: AccountOverview, vm: MainViewModel, usdCny: Double, accentColor: androidx.compose.ui.graphics.Color) {
    val s = vm.s
    val tt = acc.today
    val cells: List<Triple<String, String, String?>> = listOf(
        Triple(s.totalRequests, Fmt.int(tt.requestCount), null),
        Triple(s.input, Fmt.tokens(tt.totalInputTokens), null),
        Triple(s.output, Fmt.tokens(tt.totalOutputTokens), null),
        Triple(s.colReasoning, Fmt.tokens(tt.totalReasoningTokens), null),
        Triple(s.colCost, Fmt.money(tt.totalCostUsd, vm.currency, usdCny), null),
        Triple(s.todayTrend, "", null),  // sparkline 占位格
    )
    Column(Modifier.padding(start = 14.dp, end = 14.dp, top = 10.dp)) {
        cells.chunked(2).forEach { row ->
            Row(
                Modifier.fillMaxWidth().padding(bottom = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                row.forEach { (label, v, _) ->
                    Column(
                        Modifier
                            .weight(1f)
                            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f), RoundedCornerShape(10.dp))
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                    ) {
                        Text(label, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (label == s.todayTrend) {
                            Sparkline(
                                values = acc.todayTrend.map { it.input + it.output + it.reasoning },
                                color = accentColor,
                                modifier = Modifier.fillMaxWidth().height(30.dp),
                            )
                        } else {
                            Text(v, fontSize = 15.sp, fontWeight = FontWeight.Bold, fontFamily = NumFontFamily)
                        }
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/** 合并各账号 daily7 为按日合计序列 (保持日期升序) — chartOvTrend 合计口径 parity. */
private fun mergeDaily(lists: List<List<DailyStat>>): List<DailyStat> {
    val byDate = LinkedHashMap<String, DailyStat>()
    lists.flatten().forEach { d ->
        val prev = byDate[d.date]
        byDate[d.date] = if (prev == null) d else prev.copy(
            totalInputTokens = prev.totalInputTokens + d.totalInputTokens,
            uncachedInputTokens = prev.uncachedInputTokens + d.uncachedInputTokens,
            totalReasoningTokens = prev.totalReasoningTokens + d.totalReasoningTokens,
            cacheHitTokens = prev.cacheHitTokens + d.cacheHitTokens,
            cacheWriteTokens = prev.cacheWriteTokens + d.cacheWriteTokens,
            totalOutputTokens = prev.totalOutputTokens + d.totalOutputTokens,
            totalCostUsd = prev.totalCostUsd + d.totalCostUsd,
            requestCount = prev.requestCount + d.requestCount,
        )
    }
    return byDate.values.sortedBy { it.date }
}

@Composable
private fun quotaLabel(label: String, s: Strings): String = when (label) {
    "5h Rolling" -> s.rolling
    "Weekly" -> s.weekly
    "Monthly" -> s.monthly
    else -> label
}

@Composable
private fun quotaAccent(label: String) = when (label) {
    "5h Rolling" -> MaterialTheme.colorScheme.primary
    "Weekly" -> Accent.blue
    else -> Accent.amber
}
