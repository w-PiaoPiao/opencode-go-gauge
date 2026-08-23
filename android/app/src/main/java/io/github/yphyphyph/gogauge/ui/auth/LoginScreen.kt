package io.github.yphyphyph.gogauge.ui.auth

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.os.Message
import android.util.Log
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.yphyphyph.gogauge.auth.Login
import io.github.yphyphyph.gogauge.data.remote.OpenCodeApi
import io.github.yphyphyph.gogauge.ui.MainViewModel
import kotlinx.coroutines.delay

/**
 * Full-screen login page: embeds the official OpenCode authorization page in a WebView,
 * captures the auth cookie once the user lands back on opencode.ai — port of auth.py (desktop).
 *
 * Details:
 * - Desktop user agent is used (opencode.ai redirects mobile UAs away from the auth flow)
 * - Multiple windows supported (GitHub OAuth may open popups)
 * - Cookie capture checks every opencode.ai subdomain (www / workspace / auth) on a 500ms
 *   poll plus every page finish; the domain check matches any "*.opencode.ai" host.
 * - A top progress bar shows while any page (GitHub OAuth hops included) is loading,
 *   so the user always sees feedback during redirects.
 */
@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun LoginScreen(vm: MainViewModel = viewModel(), onCancel: () -> Unit) {
    val s = vm.s
    val wvRef = remember { mutableStateOf<WebView?>(null) }
    var loading by remember { mutableStateOf(true) }

    // Try to capture the auth cookie from the current page. Returns true once captured.
    fun tryCapture(wv: WebView): Boolean {
        val url = wv.url ?: return false
        if (!Login.isOnOpencodeDomain(url)) return false
        // Check every opencode.ai host: the site may land on www.opencode.ai etc.
        val cookie = listOf(
            "https://opencode.ai",
            "https://www.opencode.ai",
            "https://auth.opencode.ai",
        ).mapNotNull { CookieManager.getInstance().getCookie(it) }
            .joinToString(";")
        val auth = Login.extractAuthCookie(cookie)
        if (auth != null) {
            val workspace = Login.extractWorkspaceHint(url)
            Log.i("GoGauge", "login cookie captured, ws=$workspace url=$url")
            vm.completeLogin(auth, workspace)
            return true
        }
        return false
    }

    // Poll loop (desktop LoginWatcher parity, faster at 500ms)
    LaunchedEffect(Unit) {
        while (true) {
            delay(500)
            val wv = wvRef.value ?: continue
            if (tryCapture(wv)) return@LaunchedEffect
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(s.loginTitle, style = MaterialTheme.typography.titleMedium) },
                navigationIcon = {
                    IconButton(onClick = onCancel) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
            )
        },
    ) { innerPadding ->
        Box(Modifier.fillMaxSize().padding(innerPadding)) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    WebView(ctx).apply {
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        settings.setSupportMultipleWindows(true)
                        // Desktop UA: opencode.ai redirects mobile UAs away from auth
                        settings.userAgentString = OpenCodeApi.USER_AGENT
                        CookieManager.getInstance().setAcceptCookie(true)
                        CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
                        webViewClient = object : WebViewClient() {
                            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                                loading = true
                                Log.d("GoGauge", "login page start: $url")
                            }

                            override fun onPageFinished(view: WebView?, url: String?) {
                                loading = false
                                Log.d("GoGauge", "login page done: $url")
                                if (view != null && !tryCapture(view)) {
                                    // Some SPA hops finish before cookies land; keep polling anyway.
                                    Log.d("GoGauge", "no auth cookie yet at $url")
                                }
                            }
                        }
                        webChromeClient = object : WebChromeClient() {
                            override fun onCreateWindow(
                                view: WebView?,
                                isDialog: Boolean,
                                isUserGesture: Boolean,
                                resultMsg: Message?,
                            ): Boolean {
                                // Route window.open popups (e.g. GitHub OAuth) into this WebView
                                val transport = resultMsg?.obj as? WebView.WebViewTransport ?: return false
                                transport.webView = this@apply
                                resultMsg.sendToTarget()
                                return true
                            }
                        }
                        loadUrl(Login.buildLoginUrl())
                    }.also { wvRef.value = it }
                },
                // Tear the WebView down when this composable leaves composition so we
                // don't leak a WebView on every visit to the login page.
                onRelease = { wv ->
                    wv.stopLoading()
                    wv.loadUrl("about:blank")
                    wv.destroy()
                    if (wvRef.value === wv) wvRef.value = null
                },
            )
            // Loading feedback during page hops (auth page → GitHub → back)
            if (loading) {
                Column(
                    Modifier
                        .align(Alignment.TopCenter)
                        .fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    LinearProgressIndicator(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(3.dp),
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            if (loading) {
                Column(
                    Modifier
                        .align(Alignment.Center)
                        .padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.height(12.dp))
                    Text(
                        if (vm.lang == "en") "Loading…" else "正在加载…",
                        fontSize = 13.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }
    }
}
