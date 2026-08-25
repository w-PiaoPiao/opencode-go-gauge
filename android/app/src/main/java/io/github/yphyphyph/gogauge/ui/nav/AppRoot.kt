package io.github.yphyphyph.gogauge.ui.nav

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import io.github.yphyphyph.gogauge.ui.MainViewModel
import io.github.yphyphyph.gogauge.ui.auth.LoginScreen
import io.github.yphyphyph.gogauge.ui.auth.WelcomeScreen
import io.github.yphyphyph.gogauge.ui.home.HomeScreen
import io.github.yphyphyph.gogauge.ui.overview.OverviewScreen
import io.github.yphyphyph.gogauge.ui.records.RecordsScreen
import io.github.yphyphyph.gogauge.ui.settings.SettingsScreen
import io.github.yphyphyph.gogauge.ui.stats.StatsScreen
import io.github.yphyphyph.gogauge.ui.theme.GoGaugeTheme

/** App root: welcome/login flow when logged out; bottom-nav shell when logged in. */
@Composable
fun AppRoot() {
    val vm: MainViewModel = viewModel()
    var loginOpen by remember { mutableStateOf(false) }

    // Once login succeeds the VM flips showLogin=false; close the login overlay so
    // the app automatically transitions into the main shell.
    LaunchedEffect(vm.showLogin) {
        if (!vm.showLogin) loginOpen = false
    }

    GoGaugeTheme(darkTheme = vm.darkMode) {
        when {
            vm.showLogin && !loginOpen -> WelcomeScreen(vm, onLogin = { loginOpen = true })
            loginOpen -> LoginScreen(vm, onCancel = { loginOpen = false })
            else -> MainShell(vm)
        }
    }
}

@Composable
private fun MainShell(vm: MainViewModel) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = backStackEntry?.destination

    // 账户总览入口由设置开关控制 (desktop applyOverviewPanel parity);
    // 关闭时若停留在总览页则退回首页
    val showOverviewTab = vm.settings.showAccountsPanel
    LaunchedEffect(showOverviewTab) {
        if (!showOverviewTab &&
            currentDestination?.hierarchy?.any { it.route == GgTab.Overview.route } == true
        ) {
            navController.navigate(GgTab.Home.route) {
                popUpTo(navController.graph.startDestinationId) { saveState = true }
                launchSingleTop = true
                restoreState = true
            }
        }
    }

    Scaffold(
        bottomBar = {
            NavigationBar {
                GgTab.entries.filter { it != GgTab.Overview || showOverviewTab }.forEach { tab ->
                    NavigationBarItem(
                        selected = currentDestination?.hierarchy?.any { it.route == tab.route } == true,
                        onClick = {
                            navController.navigate(tab.route) {
                                popUpTo(navController.graph.startDestinationId) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(tab.icon, contentDescription = tab.labelZh) },
                        label = { Text(if (vm.lang == "en") tab.labelEn else tab.labelZh) },
                    )
                }
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = GgTab.Home.route,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(GgTab.Home.route) {
                HomeScreen(vm, onManageUsers = {
                    navController.navigate(GgTab.Settings.route) {
                        popUpTo(navController.graph.startDestinationId) { saveState = true }
                        launchSingleTop = true
                        restoreState = true
                    }
                })
            }
            composable(GgTab.Stats.route) { StatsScreen(vm) }
            composable(GgTab.Records.route) { RecordsScreen(vm) }
            composable(GgTab.Overview.route) { OverviewScreen(vm) }
            composable(GgTab.Settings.route) { SettingsScreen(vm) }
        }
    }
}
