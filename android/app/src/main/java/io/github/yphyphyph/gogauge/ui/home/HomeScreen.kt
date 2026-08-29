package io.github.yphyphyph.gogauge.ui.home

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.yphyphyph.gogauge.data.model.QuotaResult
import io.github.yphyphyph.gogauge.data.model.Totals
import io.github.yphyphyph.gogauge.ui.MainViewModel
import io.github.yphyphyph.gogauge.ui.Strings
import io.github.yphyphyph.gogauge.ui.components.Accent
import io.github.yphyphyph.gogauge.ui.components.CardHeader
import io.github.yphyphyph.gogauge.ui.components.GgPullIndicator
import io.github.yphyphyph.gogauge.ui.components.GgCard
import io.github.yphyphyph.gogauge.ui.components.Hint
import io.github.yphyphyph.gogauge.ui.components.KpiCard
import io.github.yphyphyph.gogauge.ui.components.PillRow
import io.github.yphyphyph.gogauge.ui.components.QuotaCard
import io.github.yphyphyph.gogauge.ui.components.TodayBarChart
import io.github.yphyphyph.gogauge.util.Fmt

/** Home page: quota windows + overview KPIs + today's 24h trend. Pull-to-refresh at top. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(vm: MainViewModel = viewModel(), onManageUsers: () -> Unit = {}) {
    val s = vm.s
    LaunchedEffect(Unit) {
        if (vm.dashboard == null) vm.loadDashboard(range = vm.homeRange)
    }

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
        // page header: title + account chip + refresh; range pills full-width below
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(s.homeTitle, style = MaterialTheme.typography.titleLarge)
            Row(verticalAlignment = Alignment.CenterVertically) {
                AccountSwitcher(vm, s, onManageUsers = onManageUsers)
                IconButton(
                    onClick = vm::refreshNow,
                    enabled = !vm.isSyncing(),
                ) {
                    Icon(
                        Icons.Filled.Refresh,
                        contentDescription = s.refresh,
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        PillRow(
            options = listOf(
                "today" to s.today, "7d" to s.d7, "30d" to s.d30, "month" to s.month, "all" to s.all,
            ),
            selected = vm.homeRange,
            onSelect = vm::changeHomeRange,
            modifier = Modifier.fillMaxWidth(),
        )

        val data = vm.dashboard
        val quota = data?.quota
        when {
            quota == null -> QuotaSkeleton()
            !quota.success -> QuotaErrorCard(quota, s, onRetry = vm::refreshNow)
            else -> Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                quota.windows.forEach { w ->
                    val accent = when (w.label) {
                        "5h Rolling" -> MaterialTheme.colorScheme.primary
                        "Weekly" -> Accent.blue
                        else -> Accent.amber
                    }
                    QuotaCard(
                        label = quotaLabel(w.label, s),
                        usedPercent = w.used,
                        remainingText = "${s.remaining} ${w.remaining.toInt()}%",
                        resetText = "${s.resetsIn} ${Fmt.dur(w.resetInSec.toLong(), s.dUnit, s.hUnit, s.mUnit, s.soon)}",
                        accent = accent,
                    )
                }
            }
        }

        // overview 6 KPIs (2 columns)
        data?.let { d ->
            GgCard {
                CardHeader(s.overviewTitle, trailing = { Hint(s.followRange) })
                OverviewGrid(d.totals, vm)
            }
            // today's 24h trend
            GgCard {
                CardHeader("${s.todayTrend}  ${s.hours24}")
                TodayBarChart(
                    data = d.todayTrend,
                    s = s,
                    labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    gridLineColor = MaterialTheme.colorScheme.outline,
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

/**
 * 主页头部账号胶囊 — desktop 顶栏 tb-login 胶囊 + 快捷切换菜单的移动端对应物:
 * 显示当前账号名与已登录数徽标 (>1 时), 点击弹出底部弹窗快捷切换/管理入口.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AccountSwitcher(vm: MainViewModel, s: Strings, onManageUsers: () -> Unit) {
    val context = LocalContext.current
    var showSheet by remember { mutableStateOf(false) }
    val active = vm.accounts.firstOrNull { it.id == vm.activeAccountId && it.hasToken }
        ?: return
    // 未登录态由欢迎页接管; 单账号时隐藏计数徽标避免噪音
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f),
        modifier = Modifier.clickable { showSheet = true },
    ) {
        Row(
            Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(active.name, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
            if (vm.loggedInCount > 1) {
                Spacer(Modifier.width(4.dp))
                Text(
                    "${vm.loggedInCount}",
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier
                        .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                        .padding(horizontal = 4.dp),
                )
            }
        }
    }
    if (showSheet) {
        ModalBottomSheet(onDismissRequest = { showSheet = false }) {
            Text(
                s.userSwitchTip,
                fontSize = 13.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 2.dp),
            )
            vm.accounts.filter { it.hasToken }.forEach { acc ->
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clickable {
                            showSheet = false
                            if (acc.id != vm.activeAccountId) {
                                vm.switchAccount(acc.id)
                                Toast.makeText(context, s.switchedAccount, Toast.LENGTH_SHORT).show()
                            }
                        }
                        .padding(horizontal = 20.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (acc.id == vm.activeAccountId) {
                        Icon(
                            Icons.Filled.Check,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.width(22.dp),
                        )
                    } else {
                        Spacer(Modifier.width(22.dp))
                    }
                    Column(Modifier.padding(start = 8.dp)) {
                        Text(acc.name, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Text(
                            acc.workspaceId,
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            HorizontalDivider()
            Row(
                Modifier
                    .fillMaxWidth()
                    .clickable {
                        showSheet = false
                        onManageUsers()
                    }
                    .padding(horizontal = 20.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Filled.Settings,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.width(22.dp),
                )
                Text(s.manageUsers, fontSize = 14.sp, modifier = Modifier.padding(start = 8.dp))
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun quotaLabel(label: String, s: Strings): String = when (label) {
    "5h Rolling" -> s.rolling
    "Weekly" -> s.weekly
    "Monthly" -> s.monthly
    else -> label
}

@Composable
private fun QuotaSkeleton() {
    repeat(3) {
        GgCard {
            Column(Modifier.padding(16.dp)) {
                Text("—", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(10.dp))
                Row(
                    Modifier
                        .fillMaxWidth()
                        .height(12.dp)
                        .background(MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.shapes.extraSmall)
                ) {}
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun QuotaErrorCard(quota: QuotaResult, s: Strings, onRetry: () -> Unit) {
    GgCard {
        Text(
            "${s.quotaFail}：${quota.error ?: "?"}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(start = 14.dp, end = 14.dp, top = 14.dp),
        )
        Text(
            s.retryTip,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 14.dp, end = 14.dp, top = 2.dp),
        )
        TextButton(onClick = onRetry, modifier = Modifier.padding(start = 4.dp, bottom = 6.dp)) {
            Text(s.refresh, fontSize = 13.sp, color = MaterialTheme.colorScheme.primary)
        }
    }
}

/** 6 KPI cards in a 2-column grid — desktop renderOverview parity. */
@Composable
private fun OverviewGrid(totals: Totals, vm: MainViewModel) {
    val s = vm.s
    val totalTokens = totals.totalTokens
    val cards = listOf(
        Triple(s.hitRate, totals.hitRate.toInt().toString() + "%", "${s.hit} ${Fmt.tokens(totals.cacheHitTokens)} · ${s.miss} ${Fmt.tokens(totals.uncachedInputTokens)}") to Accent.green,
        Triple(s.hitAmount, Fmt.tokens(totals.cacheHitTokens), "${s.pctOfInput} ${totals.hitRate.toInt()}%") to Accent.cyan,
        Triple(s.totalTokens, Fmt.tokens(totalTokens), s.inclCache) to Accent.blue,
        Triple(s.totalRequests, Fmt.int(totals.requestCount), s.currentRange) to Accent.slate,
        Triple(s.totalCost, Fmt.money(totals.totalCostUsd, vm.currency, vm.dashboard?.usdCny ?: 7.2), "${s.avgPer} ${Fmt.money(if (totals.requestCount > 0) totals.totalCostUsd / totals.requestCount else 0.0, vm.currency, vm.dashboard?.usdCny ?: 7.2)}${s.perReq}") to Accent.amber,
        Triple(s.sessions, Fmt.int(totals.sessionCount), s.dedup) to Accent.violet,
    )
    Column(Modifier.padding(start = 14.dp, end = 14.dp, bottom = 12.dp)) {
        cards.chunked(2).forEach { row ->
            Row(
                Modifier.fillMaxWidth().padding(bottom = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                row.forEach { (c, accent) ->
                    KpiCard(
                        label = c.first, value = c.second, sub = c.third, accent = accent,
                        modifier = Modifier.weight(1f),
                    )
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}
