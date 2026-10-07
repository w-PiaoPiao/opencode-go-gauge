package io.github.yphyphyph.gogauge.widget

import android.appwidget.AppWidgetManager
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.lifecycleScope
import androidx.glance.appwidget.updateAll
import io.github.yphyphyph.gogauge.GoGaugeApp
import io.github.yphyphyph.gogauge.data.db.AppDatabase
import io.github.yphyphyph.gogauge.data.model.AccountInfo
import io.github.yphyphyph.gogauge.ui.EnStrings
import io.github.yphyphyph.gogauge.ui.Strings
import io.github.yphyphyph.gogauge.ui.ZhStrings
import io.github.yphyphyph.gogauge.ui.theme.GoGaugeTheme
import kotlinx.coroutines.launch

/**
 * 小组件配置页 (v2.2.0b) — 选择展示账号: 跟随活跃 / 固定某账号。
 * 选择写入 settings payload 键 `widget_account:{appWidgetId}` 并立即刷新小组件。
 */
class QuotaWidgetConfigActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setResult(RESULT_CANCELED) // 用户中途退出时系统自动回收 widget id
        val appWidgetId = intent?.extras?.getInt(
            AppWidgetManager.EXTRA_APPWIDGET_ID,
            AppWidgetManager.INVALID_APPWIDGET_ID,
        ) ?: AppWidgetManager.INVALID_APPWIDGET_ID
        if (appWidgetId == AppWidgetManager.INVALID_APPWIDGET_ID) {
            finish()
            return
        }

        val prefs = getSharedPreferences("gousage-prefs", MODE_PRIVATE)
        val s: Strings = if (prefs.getString("lang", "zh") == "en") EnStrings else ZhStrings

        setContent {
            GoGaugeTheme(darkTheme = prefs.getBoolean("dark", false)) {
                WidgetConfigContent(appWidgetId, s) { mode ->
                    lifecycleScope.launch {
                        AppDatabase.get(applicationContext)
                            .settingsDao().setWidgetAccount(appWidgetId, mode)
                        QuotaWidget().updateAll(this@QuotaWidgetConfigActivity)
                        val out = Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
                        setResult(RESULT_OK, out)
                        finish()
                    }
                }
            }
        }
    }
}

@Composable
private fun WidgetConfigContent(appWidgetId: Int, s: Strings, onPick: (String) -> Unit) {
    var mode by remember { mutableStateOf("active") }
    var accounts by remember { mutableStateOf<List<AccountInfo>>(emptyList()) }
    LaunchedEffect(appWidgetId) {
        val db = AppDatabase.get(GoGaugeApp.instance)
        mode = db.settingsDao().getWidgetAccount(appWidgetId)
        accounts = db.syncDao().listAccounts().filter { it.hasToken }
    }

    Column(
        Modifier.padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(s.wgAccountLabel, style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(8.dp))
        ConfigOption(s.wgAccountActive, "active", mode) { mode = it }
        HorizontalDivider()
        accounts.forEach { acc ->
            ConfigOption(acc.name, "account:${acc.id}", mode) { mode = it }
            HorizontalDivider()
        }
        Spacer(Modifier.height(16.dp))
        Surface(
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onPick(mode) },
        ) {
            Text(
                s.save,
                color = MaterialTheme.colorScheme.onPrimary,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(vertical = 12.dp),
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun ConfigOption(label: String, value: String, selected: String, onSelect: (String) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable { onSelect(value) }
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = value == selected, onClick = { onSelect(value) })
        Spacer(Modifier.width(8.dp))
        Text(label, fontSize = 14.sp, maxLines = 1)
    }
}
