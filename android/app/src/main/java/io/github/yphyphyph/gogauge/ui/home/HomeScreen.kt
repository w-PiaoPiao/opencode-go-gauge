package io.github.yphyphyph.gogauge.ui.home

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.widthIn
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.yphyphyph.gogauge.data.model.QuotaResult
import io.github.yphyphyph.gogauge.data.model.Totals
import io.github.yphyphyph.gogauge.ui.MainViewModel
import io.github.yphyphyph.gogauge.ui.theme.Gg
import io.github.yphyphyph.gogauge.ui.theme.GgChart
import io.github.yphyphyph.gogauge.ui.Strings
import io.github.yphyphyph.gogauge.ui.components.Accent
import io.github.yphyphyph.gogauge.ui.components.CardHeader
import io.github.yphyphyph.gogauge.ui.components.EditorialCell
import io.github.yphyphyph.gogauge.ui.components.EditorialGrid
import io.github.yphyphyph.gogauge.ui.components.GgPullIndicator
import io.github.yphyphyph.gogauge.ui.components.GgCard
import io.github.yphyphyph.gogauge.ui.components.Hint
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
        // 按口径一致性判断 (range + 排除集): 统计页可能已把共享的 dashboard
        // 切成别的周期或带上了模型排除; 首页恒全量
        vm.ensureHomeDashboard()
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
                    // 渐变配额条 (桌面端三窗口渐变 parity, 官方暖色系)
                    val (accent, accentEnd) = when (w.label) {
                        "5h Rolling" -> Gg.Primary to GgChart.Cost      // 珊瑚 → kraft
                        "Weekly" -> Gg.Cyan to GgChart.Output           // teal → 橄榄
                        else -> Gg.Amber to Gg.Red                      // amber → error
                    }
                    QuotaCard(
                        label = quotaLabel(w.label, s),
                        usedPercent = w.used,
                        remainingText = "${s.remaining} ${w.remaining.toInt()}%",
                        resetText = "${s.resetsIn} ${Fmt.dur(w.resetInSec.toLong(), s.dUnit, s.hUnit, s.mUnit, s.soon)}",
                        accent = accent,
                        accentEnd = accentEnd,
                        forecastText = forecastLine(w.label, vm.forecast, s),
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
                    animate = vm.settings.chartAnimation,
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
    // 长账号名 (改名上限 50 字符) 必须限宽省略: 头部 Row 是 SpaceBetween,
    // 不设上限时胶囊会吃光剩余宽度, 把刷新按钮挤到 0 宽 (不可见不可点)
    val chipMaxWidth = (LocalConfiguration.current.screenWidthDp * 0.42f).dp
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = MaterialTheme.colorScheme.surfaceContainerHighest,
        modifier = Modifier.widthIn(max = chipMaxWidth).clickable { showSheet = true },
    ) {
        Row(
            Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                active.name,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f, fill = false),
            )
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

/**
 * 每窗口预测小字 (v2.2.0b burn-rate) — 月窗口显示预计用尽日, 5h 显示打满时刻,
 * 周窗口显示剩余可用天数。预测缺失 (配额未就绪/数据不足) 返回 null 不渲染。
 */
private fun forecastLine(label: String, f: io.github.yphyphyph.gogauge.domain.ForecastEngine.Forecast?, s: Strings): String? {
    if (f == null) return null
    return when (label) {
        "5h Rolling" -> f.fiveHourExhaustInMin?.let { min ->
            // >300 分钟 = 按当前速率到重置也打不满, 换提示语
            if (min <= 300) s.fc5hLine.format(Fmt.dur(min * 60, s.dUnit, s.hUnit, s.mUnit, s.soon))
            else s.fcNeverFull
        }
        "Weekly" -> f.weekDaysLeft?.let { d ->
            s.fcWeekLine.format(Fmt.dur((d * 86400).toLong(), s.dUnit, s.hUnit, s.mUnit, s.soon))
        }
        "Monthly" -> f.monthDaysLeft?.let { d ->
            val runOut = java.time.LocalDate.now().plusDays(Math.ceil(d).toLong())
            s.fcMonthLine.format("%d/%d".format(runOut.monthValue, runOut.dayOfMonth))
        }
        else -> null
    }
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
                        .height(8.dp)
                        .background(MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.shapes.extraSmall)
                ) {}
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun QuotaErrorCard(quota: QuotaResult, s: Strings, onRetry: () -> Unit) {
    val shape = RoundedCornerShape(12.dp)
    Column(
        Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(MaterialTheme.colorScheme.errorContainer)
            .border(1.dp, MaterialTheme.colorScheme.outline, shape)
            .padding(vertical = 6.dp),
    ) {
        Text(
            "${s.quotaFail}：${quota.error ?: "?"}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onErrorContainer,
            modifier = Modifier.padding(start = 14.dp, end = 14.dp, top = 12.dp),
        )
        Text(
            s.retryTip,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 14.dp, end = 14.dp, top = 2.dp),
        )
        TextButton(onClick = onRetry, modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)) {
            Text(s.refresh, fontSize = 13.sp, color = MaterialTheme.colorScheme.primary)
        }
    }
}

/** 6 KPI in a 2-col editorial grid — desktop renderOverview parity (与统计页构成网格同语言). */
@Composable
private fun OverviewGrid(totals: Totals, vm: MainViewModel) {
    val s = vm.s
    val totalTokens = totals.totalTokens
    EditorialGrid(
        cells = listOf(
            EditorialCell(s.hitRate, totals.hitRate.toInt().toString() + "%", "${s.hit} ${Fmt.tokens(totals.cacheHitTokens)} · ${s.miss} ${Fmt.tokens(totals.uncachedInputTokens)}", Accent.green),
            EditorialCell(s.hitAmount, Fmt.tokens(totals.cacheHitTokens), "${s.pctOfInput} ${totals.hitRate.toInt()}%", Accent.cyan),
            EditorialCell(s.totalTokens, Fmt.tokens(totalTokens), s.inclCache, Accent.blue),
            EditorialCell(s.totalRequests, Fmt.int(totals.requestCount), s.currentRange, Accent.slate),
            EditorialCell(s.totalCost, Fmt.money(totals.totalCostUsd, vm.currency, vm.dashboard?.usdCny ?: 7.2), "${s.avgPer} ${Fmt.money(if (totals.requestCount > 0) totals.totalCostUsd / totals.requestCount else 0.0, vm.currency, vm.dashboard?.usdCny ?: 7.2)}${s.perReq}", Accent.amber),
            EditorialCell(s.sessions, Fmt.int(totals.sessionCount), s.dedup, Accent.violet),
        ),
        modifier = Modifier.padding(start = 14.dp, end = 14.dp, bottom = 12.dp),
    )
}
