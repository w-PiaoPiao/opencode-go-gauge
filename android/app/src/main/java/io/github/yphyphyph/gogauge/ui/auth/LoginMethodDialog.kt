package io.github.yphyphyph.gogauge.ui.auth

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.yphyphyph.gogauge.auth.Login
import io.github.yphyphyph.gogauge.ui.Strings

/**
 * 登录方式对话框 — desktop showLoginDialog parity, 三种方式:
 * 1) 内置登录窗口 (WebView)
 * 2) 在系统浏览器中打开登录页 (登录后回来粘贴 Cookie 完成)
 * 3) 直接粘贴 Cookie 登录 (先校验再落库)
 */
@Composable
fun LoginMethodDialog(
    provider: String,
    s: Strings,
    busy: Boolean,
    status: String,
    onDismiss: () -> Unit,
    onBuiltIn: () -> Unit,
    onPaste: (String) -> Unit,
) {
    val context = LocalContext.current
    var cookieText by remember { mutableStateOf("") }
    val isGoat = provider == Login.PROVIDER_COMMANDCODE

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (isGoat) s.loginGoatBtn else s.loginBtn) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onBuiltIn,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(s.loginWin) }
                OutlinedButton(
                    onClick = {
                        // 系统浏览器打开登录页 (登录完成后复制 Cookie 回来粘贴)
                        val url = Login.buildLoginUrl(provider)
                        runCatching {
                            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(s.loginExternal) }
                Text(
                    s.loginOr,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    s.loginExternalTip,
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = cookieText,
                    onValueChange = { cookieText = it },
                    placeholder = {
                        Text(
                            if (isGoat) s.cookiePhGoat else s.cookiePhOpencode,
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    enabled = !busy,
                )
                Button(
                    onClick = { onPaste(cookieText) },
                    enabled = !busy && cookieText.isNotBlank(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busy) s.cookieChecking else s.cookiePaste) }
                if (status.isNotEmpty()) {
                    Text(status, fontSize = 12.sp, color = MaterialTheme.colorScheme.error)
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !busy) { Text(s.cancel) }
        },
    )
}
