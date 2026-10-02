package io.github.yphyphyph.gogauge.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.yphyphyph.gogauge.R
import io.github.yphyphyph.gogauge.auth.Login
import io.github.yphyphyph.gogauge.ui.MainViewModel
import io.github.yphyphyph.gogauge.ui.theme.TitleSerif

/**
 * Welcome page shown when not logged in — port of the desktop login overlay.
 * 两个登录入口 (desktop welcome parity): OpenCode 主按钮 + Command Code GOAT 次按钮
 * (GOAT 点击后弹登录方式对话框: 内置窗口 / 系统浏览器 / 粘贴 Cookie)。
 */
@Composable
fun WelcomeScreen(vm: MainViewModel, onLogin: () -> Unit, onLoginGoat: () -> Unit) {
    val s = vm.s
    var goatDialog by remember { mutableStateOf(false) }
    Column(
        Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Spacer(Modifier.height(48.dp))
        Icon(
            painter = painterResource(R.drawable.ic_spike),
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(52.dp),
        )
        Spacer(Modifier.height(10.dp))
        Text(
            "GoGauge",
            fontFamily = TitleSerif,
            fontSize = 40.sp,
            fontWeight = FontWeight.Normal,
            color = MaterialTheme.colorScheme.onBackground,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            s.welcomeDesc,
            fontSize = 14.sp,
            lineHeight = 22.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(22.dp))
        Column(Modifier.fillMaxWidth()) {
            listOf(s.welcomeFeat1, s.welcomeFeat2, s.welcomeFeat3).forEach {
                Text(
                    "✓ $it",
                    fontSize = 13.sp,
                    lineHeight = 26.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.height(26.dp))
        Button(
            onClick = onLogin,
            modifier = Modifier.fillMaxWidth().height(50.dp),
            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
        ) {
            Text(s.loginBtn, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.height(8.dp))
        // Command Code GOAT 登录入口 (desktop welcome 的 btn-login-goat parity;
        // 点击弹登录方式对话框: 内置窗口 / 系统浏览器 / 粘贴 Cookie)
        OutlinedButton(
            onClick = { goatDialog = true },
            modifier = Modifier.fillMaxWidth().height(50.dp),
        ) {
            Text(s.loginGoatBtn, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.height(8.dp))
        Text(
            s.loginNote,
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(40.dp))
    }

    if (goatDialog) {
        LoginMethodDialog(
            provider = Login.PROVIDER_COMMANDCODE,
            s = s,
            busy = vm.pasteLoginStatus == s.cookieChecking,
            status = vm.pasteLoginStatus.takeIf { it.isNotEmpty() && it != s.cookieChecking } ?: "",
            onDismiss = {
                goatDialog = false
                vm.cancelLogin()
            },
            onBuiltIn = {
                goatDialog = false
                onLoginGoat()
            },
            onPaste = { token ->
                vm.pasteLogin(token, Login.PROVIDER_COMMANDCODE) { ok -> if (ok) goatDialog = false }
            },
        )
    }
}
