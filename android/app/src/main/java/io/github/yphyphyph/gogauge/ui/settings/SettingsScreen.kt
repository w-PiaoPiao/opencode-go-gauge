package io.github.yphyphyph.gogauge.ui.settings

import android.widget.Toast
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.yphyphyph.gogauge.data.model.AccountInfo
import io.github.yphyphyph.gogauge.data.model.AppSettings
import io.github.yphyphyph.gogauge.BuildConfig
import io.github.yphyphyph.gogauge.ui.MainViewModel
import io.github.yphyphyph.gogauge.ui.Strings
import io.github.yphyphyph.gogauge.ui.components.CardHeader
import io.github.yphyphyph.gogauge.ui.components.GgPullIndicator
import io.github.yphyphyph.gogauge.ui.components.GgCard
import io.github.yphyphyph.gogauge.ui.components.PillRow
import io.github.yphyphyph.gogauge.util.Fmt

/** Settings page: 用户管理 / auto-sync / appearance / data / update / about. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(vm: MainViewModel = viewModel()) {
    val s = vm.s
    val context = LocalContext.current
    LaunchedEffect(Unit) { vm.refreshSettings() }

    var confirmDialog by remember { mutableStateOf<ConfirmAction?>(null) }
    var renameTarget by remember { mutableStateOf<AccountInfo?>(null) }

    fun toast(msg: String) = Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()

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
        Text(s.settingsTitle, style = MaterialTheme.typography.titleLarge)

        // ---- account: 用户管理 (desktop 设置页用户列表 parity) ----
        GgCard {
            CardHeader(s.setAccount, trailing = {
                TextButton(onClick = { vm.startLogin("add") }) {
                    Text(s.addUser, fontSize = 13.sp)
                }
            })
            val users = vm.accounts.filter { it.hasToken }
            if (users.isEmpty()) {
                Text(
                    s.noUsers,
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                )
            } else {
                Column {
                    users.forEachIndexed { i, acc ->
                        UserRow(
                            acc = acc,
                            isActive = acc.id == vm.activeAccountId,
                            s = s,
                            onSwitch = {
                                vm.switchAccount(acc.id)
                                toast(s.switchedAccount)
                            },
                            onRelogin = { confirmDialog = ConfirmAction.Relogin },
                            onRename = { renameTarget = acc },
                            onLogout = { confirmDialog = ConfirmAction.LogoutUser(acc.id, acc.name) },
                            onDelete = { confirmDialog = ConfirmAction.DeleteUser(acc.id, acc.name) },
                        )
                        if (i < users.lastIndex) {
                            Box(
                                Modifier
                                    .fillMaxWidth()
                                    .height(1.dp)
                                    .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.15f))
                            )
                        }
                    }
                }
            }
        }

        // ---- auto sync ----
        GgCard {
            CardHeader(s.setAutoSync)
            SetRow(
                s.autoSync, s.autoSyncDesc,
                trailing = {
                    Switch(
                        checked = vm.settings.autoSync,
                        onCheckedChange = { on ->
                            vm.saveSettings(vm.settings.copy(autoSync = on))
                        },
                    )
                },
            )
            SetRow(
                s.syncInterval, s.syncIntervalDesc,
                stacked = true,
                trailing = {
                    PillRow(
                        options = listOf(
                            "60" to s.min1, "300" to s.min5, "900" to s.min15, "1800" to s.min30,
                        ),
                        selected = vm.settings.syncIntervalSec.toString(),
                        onSelect = { v ->
                            vm.saveSettings(vm.settings.copy(syncIntervalSec = v.toInt()))
                        },
                    )
                },
            )
            SetRow(
                s.syncRange, s.syncRangeDesc,
                stacked = true,
                trailing = {
                    PillRow(
                        options = listOf(
                            "30" to s.d30short, "60" to s.d60, "90" to s.d90, "180" to s.d180, "all" to s.all,
                        ),
                        selected = (vm.settings.windowDays ?: -1).let { if (it == -1) "all" else it.toString() },
                        onSelect = { v ->
                            vm.saveSettings(vm.settings.copy(windowDays = if (v == "all") null else v.toInt()))
                        },
                    )
                },
            )
            SetRow(
                s.fullSync,
                if (vm.progress.running) "${s.syncing} · ${s.pageOf} ${vm.progress.page + 1} · ${s.totalN} ${Fmt.int(vm.progress.inserted)}"
                else s.fullSyncDesc,
                trailing = {
                    TextButton(onClick = { confirmDialog = ConfirmAction.FullSync }, enabled = !vm.progress.running) {
                        Text(s.startFullSync, fontSize = 13.sp)
                    }
                },
            )
        }

        // ---- appearance ----
        GgCard {
            CardHeader(s.setAppearance)
            SetRow(
                s.theme, s.themeDesc,
                stacked = true,
                trailing = {
                    PillRow(
                        options = listOf("light" to s.light, "dark" to s.dark),
                        selected = if (vm.darkMode) "dark" else "light",
                        onSelect = { vm.changeDarkMode(it == "dark") },
                    )
                },
            )
            SetRow(
                s.overviewPanel, s.overviewPanelDesc,
                trailing = {
                    Switch(
                        checked = vm.settings.showAccountsPanel,
                        onCheckedChange = { on ->
                            vm.saveSettings(vm.settings.copy(showAccountsPanel = on))
                        },
                    )
                },
            )
            SetRow(
                s.currency, s.currencyDesc,
                stacked = true,
                trailing = {
                    PillRow(
                        options = listOf("CNY" to "¥ CNY", "USD" to "\$ USD"),
                        selected = vm.currency,
                        onSelect = vm::changeCurrency,
                    )
                },
            )
            SetRow(
                s.language, s.languageDesc,
                stacked = true,
                trailing = {
                    PillRow(
                        options = listOf("zh" to "中文", "en" to "English"),
                        selected = vm.lang,
                        onSelect = vm::changeLang,
                    )
                },
            )
        }

        // ---- data ----
        GgCard {
            CardHeader(s.setData)
            SetRow(s.dataDir, vm.datadir.ifEmpty { "—" })
            SetRow(
                s.syncInfo,
                vm.dashboard?.sync?.let { sync ->
                    sync.lastSyncAt?.let { "${s.lastSync} ${Fmt.dateTime(it)} (${sync.lastSyncStatus}) · ${s.totalN} ${Fmt.int(sync.totalRecords)} ${s.items}" }
                        ?: s.never
                } ?: s.never,
            )
        }

        // ---- update ----
        GgCard {
            CardHeader(s.setUpdate)
            SetRow(s.currentVersion, "v${BuildConfig.VERSION_NAME}")
            SetRow(
                s.checkUpdate,
                vm.updateStatus.ifEmpty { s.checkUpdateDesc },
                trailing = {
                    TextButton(onClick = vm::checkUpdate) { Text(s.checkUpdateBtn, fontSize = 13.sp) }
                },
            )
        }

        // ---- about ----
        GgCard {
            CardHeader(s.aboutTitle)
            Text(
                s.introText,
                fontSize = 13.sp,
                lineHeight = 22.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
            Text(
                s.aboutFeatures,
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.padding(start = 16.dp, top = 6.dp),
            )
            Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 10.dp)) {
                listOf(s.feat1, s.feat2, s.feat3, s.feat4, s.feat5).forEach {
                    Text("• $it", fontSize = 12.5.sp, lineHeight = 22.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Text(
                "${s.thanksText} OpenCode · ${s.pageFoot.replace("{version}", "v${BuildConfig.VERSION_NAME}")}",
                fontSize = 11.5.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
            )
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

    renameTarget?.let { acc ->
        var name by remember(acc.id) { mutableStateOf(acc.name) }
        AlertDialog(
            onDismissRequest = { renameTarget = null },
            title = { Text(s.renameTitle) },
            text = {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it.take(50) },
                    singleLine = true,
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    vm.renameAccount(acc.id, name) { ok -> if (ok) toast(s.userRenamed) }
                    renameTarget = null
                }) { Text(s.save) }
            },
            dismissButton = {
                TextButton(onClick = { renameTarget = null }) { Text(s.cancel) }
            },
        )
    }

    confirmDialog?.let { action ->
        val (title, message, okText, danger) = when (action) {
            ConfirmAction.Relogin -> Quad(s.relogin, s.reloginConfirm, s.goLogin, false)
            is ConfirmAction.LogoutUser ->
                Quad(s.logout, s.logoutUserConfirm.replace("{name}", action.name), s.ok, true)
            is ConfirmAction.DeleteUser ->
                Quad(s.deleteTitle, s.deleteUserConfirm.replace("{name}", action.name), s.confirm, true)
            ConfirmAction.FullSync -> Quad(s.fullSync, s.fullSyncConfirm, s.startSync, false)
        }
        AlertDialog(
            onDismissRequest = { confirmDialog = null },
            title = { Text(title) },
            text = { Text(message, fontSize = 13.sp) },
            confirmButton = {
                TextButton(onClick = {
                    confirmDialog = null
                    when (action) {
                        ConfirmAction.Relogin -> vm.startLogin("relogin")
                        is ConfirmAction.LogoutUser -> {
                            vm.logoutActive()
                            toast(s.loggedOut)
                        }
                        is ConfirmAction.DeleteUser -> {
                            vm.deleteAccount(action.id)
                            toast(s.userDeleted)
                        }
                        ConfirmAction.FullSync -> vm.startSync("full")
                    }
                }) {
                    Text(okText, color = if (danger) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmDialog = null }) { Text(s.cancel) }
            },
        )
    }
}

private sealed interface ConfirmAction {
    data object Relogin : ConfirmAction
    data class LogoutUser(val id: Int, val name: String) : ConfirmAction
    data class DeleteUser(val id: Int, val name: String) : ConfirmAction
    data object FullSync : ConfirmAction
}

private data class Quad<T>(val a: T, val b: T, val c: T, val d: Boolean)

/** 单个用户行 — desktop renderUsersList user-row parity. */
@Composable
private fun UserRow(
    acc: AccountInfo,
    isActive: Boolean,
    s: Strings,
    onSwitch: () -> Unit,
    onRelogin: () -> Unit,
    onRename: () -> Unit,
    onLogout: () -> Unit,
    onDelete: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(acc.name, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
                if (isActive) {
                    Spacer(Modifier.width(6.dp))
                    Text(
                        s.currentUserBadge,
                        fontSize = 10.sp,
                        color = MaterialTheme.colorScheme.tertiary,
                        modifier = Modifier
                            .background(
                                MaterialTheme.colorScheme.tertiary.copy(alpha = 0.12f),
                                RoundedCornerShape(6.dp),
                            )
                            .padding(horizontal = 5.dp, vertical = 1.dp),
                    )
                }
            }
            Text(
                "${acc.workspaceId} · ${s.loggedIn}",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.width(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (isActive) {
                TextButton(onClick = onRelogin) { Text(s.relogin, fontSize = 13.sp) }
                TextButton(onClick = onRename) { Text(s.renameBtn, fontSize = 13.sp) }
                TextButton(onClick = onLogout) {
                    Text(s.logout, fontSize = 13.sp, color = MaterialTheme.colorScheme.error)
                }
            } else {
                TextButton(onClick = onSwitch) { Text(s.switchTo, fontSize = 13.sp) }
                TextButton(onClick = onRename) { Text(s.renameBtn, fontSize = 13.sp) }
                TextButton(onClick = onDelete) {
                    Text(s.deleteUser, fontSize = 13.sp, color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}

@Composable
private fun SetRow(
    label: String,
    desc: String,
    trailing: (@Composable () -> Unit)? = null,
    stacked: Boolean = false,
) {
    if (stacked) {
        // Wide controls (pill groups) get their own full-width row so the label
        // and options never squeeze each other on narrow screens.
        Column(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 10.dp),
        ) {
            Column {
                Text(label, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                Text(desc, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
                trailing?.invoke()
            }
        }
    } else {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(label, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                Text(desc, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.width(10.dp))
            trailing?.invoke()
        }
    }
}
