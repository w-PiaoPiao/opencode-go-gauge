package io.github.yphyphyph.gogauge.ui.nav

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Settings
import androidx.compose.ui.graphics.vector.ImageVector

enum class GgTab(
    val route: String,
    val labelZh: String,
    val labelEn: String,
    val icon: ImageVector,
) {
    Home("home", "首页", "Home", Icons.Filled.Home),
    Stats("stats", "统计", "Stats", Icons.Filled.BarChart),
    Records("records", "记录", "Records", Icons.Filled.ReceiptLong),
    // 账户总览 (v2.1.0): 设置开关控制入口显隐, 位置对齐桌面侧边栏 (设置之前)
    Overview("overview", "总览", "Overview", Icons.Filled.Groups),
    Settings("settings", "设置", "Settings", Icons.Filled.Settings),
}
