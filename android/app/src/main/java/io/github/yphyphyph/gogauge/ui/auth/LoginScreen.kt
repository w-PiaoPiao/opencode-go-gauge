package io.github.yphyphyph.gogauge.ui.auth

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.os.Message
import android.os.SystemClock
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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

// 登录自愈限额 — desktop auth.py 常量 parity
private const val ENTRY_RESET_INTERVAL_MS = 10_000L  // 入口偏离自愈的相邻 reset 间隔
private const val ENTRY_RESET_MAX = 6                // 入口偏离自愈次数上限
private const val GITHUB_STUCK_GRACE_MS = 3_000L     // 确认 GitHub 已登录后的宽限期
private const val GITHUB_MAX_RELOADS = 3             // OAuth 续跑次数上限

/** 清空 WebView Cookie — 残留会话会把登录页带离入口 (desktop clear_provider_cookies 的全清口径). */
private fun clearLoginCookies() {
    CookieManager.getInstance().removeAllCookies(null)
    CookieManager.getInstance().flush()
}

/** 读 GitHub 页面已登录用户名 (meta user-login); 未登录/读取失败返回 "". */
private suspend fun readGithubUser(wv: WebView): String = suspendCancellableCoroutine { cont ->
    wv.evaluateJavascript(
        "(document.querySelector('meta[name=user-login]')||{}).content||''"
    ) { value ->
        if (cont.isActive) cont.resume(value?.trim('"')?.takeIf { it != "null" }.orEmpty())
    }
}

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
 * - Entry cleanup: cookies are wiped before the login URL loads, so a leftover
 *   session can't bounce the window off the sign-in page (desktop v2.1.0e parity).
 * - Self-healing poll loop (desktop v2.2.0 parity): commandcode pages taken off
 *   /signin by a stale session are reset and pulled back (rate-limited), and a
 *   GitHub OAuth flow stuck on an unrelated page after sign-in is resumed via
 *   the recorded authorize entry.
 */
@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun LoginScreen(vm: MainViewModel = viewModel(), onCancel: () -> Unit) {
    val s = vm.s
    val wvRef = remember { mutableStateOf<WebView?>(null) }
    // WebView 无 isDestroyed() API: onRelease 释放时置位, 供异步回调判断
    val wvReleased = remember { AtomicBoolean(false) }
    var loading by remember { mutableStateOf(true) }

    // Try to capture the auth cookie from the current page. Returns true once captured.
    fun tryCapture(wv: WebView): Boolean {
        val url = wv.url ?: return false
        // provider 感知: commandcode (GOAT) 与 opencode 的目标域/cookie 名不同
        val provider = Login.normalizeProvider(vm.pendingLoginProvider)
        val isCC = provider == Login.PROVIDER_COMMANDCODE
        if (isCC) {
            if (!Login.isOnCommandcodeDomain(url)) return false
        } else if (!Login.isOnOpencodeDomain(url)) {
            return false
        }
        val cookie = if (isCC) {
            CookieManager.getInstance().getCookie("https://commandcode.ai")
        } else {
            // Check every opencode.ai host: the site may land on www.opencode.ai etc.
            listOf(
                "https://opencode.ai",
                "https://www.opencode.ai",
                "https://auth.opencode.ai",
            ).mapNotNull { CookieManager.getInstance().getCookie(it) }
                .joinToString(";")
        }
        val token = if (isCC) Login.extractSessionCookie(cookie) else Login.extractAuthCookie(cookie)
        if (token != null) {
            val workspace = if (isCC) "Default" else Login.extractWorkspaceHint(url)
            Log.i("GoGauge", "login cookie captured, provider=$provider ws=$workspace url=$url")
            // 登录完成即清空 WebView cookie: OAuth/会话 cookie 不留在本地 cookie 库
            CookieManager.getInstance().removeAllCookies(null)
            CookieManager.getInstance().flush()
            vm.completeLogin(token, workspace)
            return true
        }
        return false
    }

    // Poll loop (desktop LoginWatcher parity, faster at 500ms):
    // 捕获 cookie 之外还承担两条自愈链路 —— commandcode 入口偏离持续拉回
    // (desktop _check_entry_drift) 与 GitHub OAuth 卡死续跑 (desktop _watch_github)。
    LaunchedEffect(Unit) {
        var entryResets = 0
        var lastEntryReset: Long? = null
        var oauthEntry: String? = null
        var stuckSince: Long? = null
        var reloads = 0
        while (true) {
            delay(500)
            try {
                val wv = wvRef.value ?: continue
                if (tryCapture(wv)) return@LaunchedEffect
                val url = wv.url ?: continue
                val provider = Login.normalizeProvider(vm.pendingLoginProvider)
                val now = SystemClock.elapsedRealtime()

                // 1) 入口偏离持续判定: 页面加载完成时检查一两次覆盖不到"客户端路由慢跳"
                //    (登录页加载完还在 /signin, 之后页面 JS 才检测到残留会话并跳官网);
                //    每轮轮询发现偏离即清会话拉回, 限流防与打开时的清理打环。
                if (Login.isOffLoginEntry(url, provider)) {
                    val cooled = lastEntryReset?.let { now - it >= ENTRY_RESET_INTERVAL_MS } ?: true
                    if (cooled && entryResets < ENTRY_RESET_MAX) {
                        entryResets++
                        lastEntryReset = now
                        Log.i("GoGauge", "login entry drift -> reset #$entryResets (url=$url)")
                        // 先停旧页面再清 cookie: 旧页面 JS 的定时请求会拿到服务端续发的
                        // Set-Cookie, 直接清存在竞速 (desktop reset_login_session 顺序 parity)
                        wv.stopLoading()
                        clearLoginCookies()
                        wv.loadUrl(Login.buildLoginUrl(provider))
                        continue
                    }
                }

                // 2) GitHub OAuth 续跑: 2FA 后丢 return_to 卡在无关页面时, 确认 GitHub
                //    已登录后宽限 3s 重新拉起授权入口 (奇偶交替重构/原始入口; Android
                //    统一用重构 URL —— 无编码问题的兜底见 desktop 的交替策略)。
                //    流程页 (登录表单/两步验证) 正常等待用户操作, 不打扰。
                val cls = Login.classifyGithubUrl(url)
                if (cls == "entry") {
                    oauthEntry = url
                    stuckSince = null
                } else if (cls == "flow") {
                    stuckSince = null
                } else if (cls == "stuck") {
                    if (stuckSince == null) stuckSince = now
                    val since = stuckSince ?: now
                    if (now - since >= GITHUB_STUCK_GRACE_MS && reloads < GITHUB_MAX_RELOADS) {
                        val target = Login.authorizeUrlFromEntry(oauthEntry)
                        if (target == null) {
                            Log.w("GoGauge", "github signed-in but OAuth entry missing; cannot resume")
                            reloads = GITHUB_MAX_RELOADS  // 无入口可续跑, 停止重试
                        } else if (readGithubUser(wv).isNotEmpty()) {
                            reloads++
                            stuckSince = null
                            Log.i("GoGauge", "github stalled -> resume #$reloads: $target")
                            wv.loadUrl(target)
                        }
                    }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // 单轮失败 (页面销毁竞态/JS 读取失败等) 不终止监听: 下一轮继续
                Log.w("GoGauge", "login watcher tick failed", e)
            }
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
                        // 先清残留会话再进登录页 (desktop v2.1.0e "登录窗口复用清残留会话"
                        // parity): CookieManager 全应用共享, 上次未完成的登录可能留下会话
                        // cookie —— commandcode 页面 JS 会据此把窗口带离 /signin.
                        CookieManager.getInstance().removeAllCookies {
                            CookieManager.getInstance().flush()
                            // 用户可能已离开登录页 (onRelease 释放了 WebView): 别对已
                            // 销毁实例 loadUrl
                            if (!wvReleased.get()) loadUrl(Login.buildLoginUrl(vm.pendingLoginProvider))
                        }
                    }.also { wvRef.value = it }
                },
                // Tear the WebView down when this composable leaves composition so we
                // don't leak a WebView on every visit to the login page.
                onRelease = { wv ->
                    wvReleased.set(true)
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
