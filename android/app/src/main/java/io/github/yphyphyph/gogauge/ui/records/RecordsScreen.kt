package io.github.yphyphyph.gogauge.ui.records

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.yphyphyph.gogauge.data.model.PageResult
import io.github.yphyphyph.gogauge.data.model.SessionStat
import io.github.yphyphyph.gogauge.data.model.UsageRecordRow
import io.github.yphyphyph.gogauge.ui.MainViewModel
import io.github.yphyphyph.gogauge.ui.components.CardHeader
import io.github.yphyphyph.gogauge.ui.components.GgCard
import io.github.yphyphyph.gogauge.ui.components.Hint
import io.github.yphyphyph.gogauge.ui.theme.NumFontFamily
import io.github.yphyphyph.gogauge.util.Fmt

/** Records page: session usage + usage records as readable card lists. */
@Composable
fun RecordsScreen(vm: MainViewModel = viewModel()) {
    val s = vm.s
    LaunchedEffect(Unit) {
        vm.loadSessions()
        vm.loadRecords()
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(s.recordsPage, style = MaterialTheme.typography.titleLarge)

        // ---- sessions ----
        GgCard {
            CardHeader(
                s.sessionUsage,
                trailing = { Hint(vm.sessions?.let { "${s.totalN} ${Fmt.int(it.total)} ${s.sessions}" } ?: "") },
            )
            val sessions = vm.sessions
            if (sessions == null || sessions.records.isEmpty()) {
                Text(
                    s.noData,
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                sessions.records.forEach { SessionRow(it, vm) }
                Pager(
                    page = vm.sessionsPage,
                    total = sessions.total,
                    pageSize = 10,
                    onPrev = vm::sessionsPrev,
                    onNext = vm::sessionsNext,
                    s = s,
                )
            }
        }

        // ---- usage records ----
        GgCard {
            CardHeader(
                s.usageRecords,
                trailing = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        ModelFilter(vm)
                        Spacer(Modifier.width(8.dp))
                        Hint(vm.records?.let { "${s.totalN} ${Fmt.int(it.total)} ${s.items}" } ?: "")
                    }
                },
            )
            val records = vm.records
            if (records == null || records.records.isEmpty()) {
                Text(
                    s.noData,
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                records.records.forEach { RecordRow(it, vm) }
                Pager(
                    page = vm.recordsPage,
                    total = records.total,
                    pageSize = 10,
                    onPrev = vm::recordsPrev,
                    onNext = vm::recordsNext,
                    s = s,
                )
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun SessionRow(st: SessionStat, vm: MainViewModel) {
    val s = vm.s
    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 8.dp)
            .background(MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.shapes.small)
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (st.sessionId.isBlank()) s.unassigned else shortId(st.sessionId),
                fontWeight = FontWeight.SemiBold,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
                color = if (st.sessionId.isBlank()) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
            )
            Text(
                Fmt.money(st.totalCostUsd, vm.currency, vm.dashboard?.usdCny ?: 7.2),
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = NumFontFamily,
            )
        }
        Text(
            "${s.colLastUsed} ${Fmt.dateTimeShort(st.lastAt)} · ${Fmt.int(st.requestCount)} ${s.colRequests.replace("/Token", "")}",
            fontSize = 11.5.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            "${s.colInput} ${Fmt.tokens(st.totalInputTokens)} · ${s.colOutput} ${Fmt.tokens(st.totalOutputTokens)} · ${s.colReasoning} ${Fmt.tokens(st.totalReasoningTokens)}",
            fontSize = 11.5.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontFamily = NumFontFamily,
        )
    }
}

@Composable
private fun RecordRow(r: UsageRecordRow, vm: MainViewModel) {
    val s = vm.s
    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 6.dp)
            .background(MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.shapes.small)
            .padding(horizontal = 12.dp, vertical = 9.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                r.model,
                fontWeight = FontWeight.SemiBold,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            Text(
                Fmt.money(r.costUsd, vm.currency, vm.dashboard?.usdCny ?: 7.2),
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = NumFontFamily,
            )
        }
        Text(Fmt.dateTime(r.createdAt), fontSize = 11.5.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            "${s.colInput} ${Fmt.tokens(r.inputTokens)} · ${s.colOutput} ${Fmt.tokens(r.outputTokens)} · ${s.colReasoning} ${Fmt.tokens(r.reasoningTokens)} · ${s.colCacheRead} ${Fmt.tokens(r.cacheReadTokens)}",
            fontSize = 11.5.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontFamily = NumFontFamily,
        )
    }
}

@Composable
private fun ModelFilter(vm: MainViewModel) {
    val s = vm.s
    var expanded by remember { mutableStateOf(false) }
    Column {
        TextButton(onClick = { expanded = true }, contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 8.dp, vertical = 0.dp)) {
            Text(
                vm.recordsFilter ?: s.allModels,
                fontSize = 12.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text(s.allModels, fontSize = 13.sp) },
                onClick = {
                    vm.changeRecordsFilter(null)
                    expanded = false
                },
            )
            vm.models.forEach { m ->
                DropdownMenuItem(
                    text = { Text(m, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    onClick = {
                        vm.changeRecordsFilter(m)
                        expanded = false
                    },
                )
            }
        }
    }
}

@Composable
private fun Pager(
    page: Int,
    total: Int,
    pageSize: Int,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    s: io.github.yphyphyph.gogauge.ui.Strings,
) {
    val totalPages = maxOf(1, (total + pageSize - 1) / pageSize)
    Row(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Button(
            onClick = onPrev,
            enabled = page > 1,
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                contentColor = MaterialTheme.colorScheme.onSurface,
            ),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        ) { Text(s.prev, fontSize = 13.sp) }
        Text(
            "${s.pageOf} $page ${s.ofPages} $totalPages",
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 12.dp),
        )
        Button(
            onClick = onNext,
            enabled = page < totalPages,
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                contentColor = MaterialTheme.colorScheme.onSurface,
            ),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        ) { Text(s.next, fontSize = 13.sp) }
    }
}

private fun shortId(id: String): String = if (id.length > 18) id.take(16) + "…" else id
