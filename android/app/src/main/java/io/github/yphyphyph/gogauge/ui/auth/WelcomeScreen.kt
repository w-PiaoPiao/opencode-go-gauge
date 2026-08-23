package io.github.yphyphyph.gogauge.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.yphyphyph.gogauge.ui.MainViewModel

/**
 * Welcome page shown when not logged in — port of the desktop login overlay.
 */
@Composable
fun WelcomeScreen(vm: MainViewModel, onLogin: () -> Unit) {
    val s = vm.s
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
        Text(
            "◉",
            fontSize = 52.sp,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(8.dp))
        Text("GoGauge", style = MaterialTheme.typography.titleLarge)
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
        Text(
            s.loginNote,
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(40.dp))
    }
}
