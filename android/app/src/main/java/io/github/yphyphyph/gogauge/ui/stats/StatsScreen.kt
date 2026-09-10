package io.github.yphyphyph.gogauge.ui.stats

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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.yphyphyph.gogauge.data.model.Totals
import io.github.yphyphyph.gogauge.ui.MainViewModel
import io.github.yphyphyph.gogauge.ui.components.Accent
import io.github.yphyphyph.gogauge.ui.components.CardHeader
import io.github.yphyphyph.gogauge.ui.components.GgPullIndicator
import io.github.yphyphyph.gogauge.ui.components.GgCard
import io.github.yphyphyph.gogauge.ui.components.Hint
import io.github.yphyphyph.gogauge.ui.components.KpiCard
import io.github.yphyphyph.gogauge.ui.components.ModelIcon
import io.github.yphyphyph.gogauge.ui.components.ModelPieChart
import io.github.yphyphyph.gogauge.ui.components.PillRow
import io.github.yphyphyph.gogauge.ui.components.TrendLineChart
import io.github.yphyphyph.gogauge.ui.theme.NumFontFamily
import io.github.yphyphyph.gogauge.util.Fmt

/** Stats page: 4 KPI + token breakdown + model doughnut/ranking + usage trend. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StatsScreen(vm: MainViewModel = viewModel()) {
    val s = vm.s
    LaunchedEffect(Unit) {
        // 按 range 一致性判断: 首页可能已把共享的 dashboard 切成别的周期
        vm.ensureDashboard(vm.statsRange)
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
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(s.statsTitle, style = MaterialTheme.typography.titleLarge)
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
        PillRow(
            options = listOf(
                "today" to s.today, "7d" to s.d7, "30d" to s.d30, "month" to s.month, "all" to s.all,
            ),
            selected = vm.statsRange,
            onSelect = vm::changeStatsRange,
            modifier = Modifier.fillMaxWidth(),
        )

        val d = vm.dashboard
        if (d != null) {
            StatsTotalGrid(d.totals, vm)

            // token breakdown 2x3
            GgCard {
                CardHeader(s.tokenBreakdown)
                BreakdownGrid(d.totals, vm)
            }

            // model usage: doughnut + ranking
            GgCard {
                CardHeader(
                    s.modelUsage,
                    trailing = {
                        Row(horizontalArrangement = Arrangement.spacedBy(0.dp)) {
                            listOf("input" to s.input, "output" to s.output, "cost" to s.cost).forEach { (v, label) ->
                                val active = vm.modelDim == v
                                Text(
                                    label,
                                    fontSize = 12.sp,
                                    fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                                    color = if (active) MaterialTheme.colorScheme.primary
                                    else MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier
                                        .padding(horizontal = 8.dp, vertical = 4.dp)
                                        .clickable { vm.changeModelDim(v) },
                                )
                            }
                        }
                    },
                )
                ModelPieChart(
                    models = d.models,
                    dim = vm.modelDim,
                    s = s,
                    labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    currency = vm.currency,
                    usdCny = d.usdCny,
                )
                d.models.sortedByDescending {
                    when (vm.modelDim) {
                        "output" -> it.totalOutputTokens.toDouble()
                        "cost" -> it.totalCostUsd
                        // input: 含缓存命中的总输入 (与 Charts.getVal 同口径)
                        else -> it.totalInputTokens.toDouble()
                    }
                }.take(3).forEachIndexed { i, m ->
                    // 数值列与排序维度一致: 输入/输出显示 Token 数, 只有成本维度显示金额
                    // (原先无论选哪个维度都显示金额)
                    val rankToken = if (vm.modelDim == "cost") {
                        Fmt.money(m.totalCostUsd, vm.currency, d.usdCny)
                    } else {
                        val v = if (vm.modelDim == "output") m.totalOutputTokens else m.totalInputTokens
                        Fmt.tokens(v.toLong())
                    }
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 14.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("#${i + 1}", fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant, fontFamily = NumFontFamily, fontSize = 12.sp)
                        Spacer(Modifier.padding(horizontal = 6.dp))
                        ModelIcon(model = m.model, dark = vm.darkMode, modifier = Modifier.padding(end = 6.dp))
                        Text(m.model, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, maxLines = 1, modifier = Modifier.weight(1f))
                        Text(
                            "${Fmt.int(m.requestCount)} · ${s.hitRate} ${m.hitRate.toInt()}%",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                        )
                        Spacer(Modifier.padding(horizontal = 4.dp))
                        Text(
                            rankToken,
                            fontSize = 12.sp,
                            fontFamily = NumFontFamily,
                            maxLines = 1,
                            textAlign = TextAlign.End,
                            // 定宽右对齐: Token 简写 (12.03M) 与金额 (¥78.53) 宽度不同,
                            // 不固定会随维度切换左右抖动
                            modifier = Modifier.widthIn(min = 58.dp),
                        )
                    }
                }
            }

            // usage trend
            GgCard {
                CardHeader(s.usageTrend, trailing = { Hint(s.trendHint) })
                TrendLineChart(
                    trend = d.trend,
                    s = s,
                    labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                    gridLineColor = MaterialTheme.colorScheme.outline,
                    currency = vm.currency,
                    usdCny = d.usdCny,
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
@Composable
private fun StatsTotalGrid(totals: Totals, vm: MainViewModel) {
    val s = vm.s
    val usdCny = vm.dashboard?.usdCny ?: 7.2
    val totalTokens = totals.totalTokens
    val cards = listOf(
        Triple(s.totalCost, Fmt.money(totals.totalCostUsd, vm.currency, usdCny), "${s.avgPer} ${Fmt.money(if (totals.requestCount > 0) totals.totalCostUsd / totals.requestCount else 0.0, vm.currency, usdCny)}${s.perReq}") to Accent.amber,
        Triple(s.totalRequests, Fmt.int(totals.requestCount), s.currentRange) to Accent.blue,
        Triple(s.totalTokens, Fmt.tokens(totalTokens), "${s.input} ${Fmt.tokens(totals.totalInputTokens)} · ${s.output} ${Fmt.tokens(totals.totalOutputTokens)}") to Accent.violet,
        Triple(s.hitRate, totals.hitRate.toInt().toString() + "%", "${s.hit} ${Fmt.tokens(totals.cacheHitTokens)} / ${s.miss} ${Fmt.tokens(totals.uncachedInputTokens)}") to Accent.green,
    )
    Column {
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
            }
        }
    }
}

/** Token breakdown 2x3 — desktop renderDetail6 parity. */
@Composable
private fun BreakdownGrid(totals: Totals, vm: MainViewModel) {
    val s = vm.s
    val total = totals.uncachedInputTokens + totals.totalOutputTokens + totals.totalReasoningTokens
    val cells = listOf(
        Triple(s.input, Fmt.tokens(totals.uncachedInputTokens), "${s.inclCache} ${Fmt.tokens(totals.totalInputTokens)}"),
        Triple(s.output, Fmt.tokens(totals.totalOutputTokens), s.output),
        Triple(s.colReasoning, Fmt.tokens(totals.totalReasoningTokens), if (total > 0) (totals.totalReasoningTokens.toDouble() / total * 100).toInt().toString() + "%" else "0%"),
        Triple(s.colCacheRead, Fmt.tokens(totals.cacheHitTokens), "${s.hitRate} ${totals.hitRate.toInt()}%"),
        Triple(s.cacheWrite, Fmt.tokens(totals.cacheWriteTokens), s.newCacheWrites),
        Triple(s.sessions, Fmt.int(totals.sessionCount), s.dedup),
    )
    Column(Modifier.padding(horizontal = 14.dp, vertical = 4.dp)) {
        cells.chunked(2).forEach { row ->
            Row(
                Modifier.fillMaxWidth().padding(bottom = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                row.forEach { (label, v, sub) ->
                    Column(
                        Modifier
                            .weight(1f)
                            .background(MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.shapes.medium)
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                    ) {
                        Text(label, fontSize = 11.5.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(v, fontSize = 17.sp, fontWeight = FontWeight.Bold, fontFamily = NumFontFamily)
                        Text(sub, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, fontFamily = NumFontFamily)
                    }
                }
            }
        }
    }
}
