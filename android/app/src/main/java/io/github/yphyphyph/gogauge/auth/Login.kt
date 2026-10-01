package io.github.yphyphyph.gogauge.auth

import java.net.URI
import java.net.URLDecoder
import java.net.URLEncoder

/**
 * Login URL builder + cookie extraction — ports of auth.py (desktop).
 * 支持双 provider: opencode 与 commandcode (GOAT)。
 *
 * opencode 侧 2026-09 控制台改版 (v2.2.0): 旧授权页 auth.opencode.ai/authorize
 * 已下线, 登录入口为 https://opencode.ai/console/login, 会话 cookie 为
 * __Host-console_session (兼容旧 auth)。
 */
object Login {

    const val PROVIDER_OPENCODE = "opencode"
    const val PROVIDER_COMMANDCODE = "commandcode"

    // ---- opencode (控制台改版后) ----
    const val CONSOLE_LOGIN_URL = "https://opencode.ai/console/login"
    const val LOGIN_NEXT_PATH = "/console/"
    /** 新版会话 cookie; 旧版 auth= 仅作历史账号兼容 (读/写都优先新版)。 */
    const val SESSION_COOKIE_NAME = "__Host-console_session"
    const val LEGACY_SESSION_COOKIE_NAME = "auth"
    const val OPENDCODE_DOMAIN = "https://opencode.ai"

    // ---- commandcode (GOAT) — auth.py CC_* constants parity ----
    const val CC_LOGIN_BASE = "https://commandcode.ai/signin"
    const val CC_AUTH_COOKIE_NAME = "__Secure-commandcode_prod_.session_token"
    const val CC_DOMAIN = "https://commandcode.ai"

    /** 登录页 URL 里的工作区提示 — 控制台改版后为 /console/wrk_xxx (旧 /workspace/ 兼容)。 */
    private val WORKSPACE_URL_RE = Regex("/(?:console|workspace)/(wrk_[A-Za-z0-9]+)")

    fun normalizeProvider(provider: String?): String =
        if (provider == PROVIDER_COMMANDCODE) PROVIDER_COMMANDCODE else PROVIDER_OPENCODE

    /** Build the login URL for the given provider (auth.build_login_url parity). */
    fun buildLoginUrl(provider: String?): String {
        if (normalizeProvider(provider) == PROVIDER_COMMANDCODE) return CC_LOGIN_BASE
        // 控制台改版: 登录入口 = /console/login, next 指回控制台
        return CONSOLE_LOGIN_URL + "?next=" + URLEncoder.encode(LOGIN_NEXT_PATH, "UTF-8")
    }

    /**
     * Extract the session cookie segment — port of build_cookie_header.
     * 候选名优先级: __Host-console_session (新版) > auth (旧版兼容)。
     */
    fun extractAuthCookie(cookieHeader: String?): String? {
        if (cookieHeader.isNullOrBlank()) return null
        var cookie = cookieHeader.trim()
        if (cookie.startsWith("cookie:", ignoreCase = true)) cookie = cookie.substring(7).trim()
        val parts = cookie.split(";").map { it.trim() }.filter { it.isNotEmpty() }
        for (name in listOf(SESSION_COOKIE_NAME, LEGACY_SESSION_COOKIE_NAME)) {
            // 值必须非空: "name=" 的空 cookie 被当作有效凭证落库后, 会以"登录成功"
            // 假象进入请求全 401 的状态 (desktop _pick_session_cookie 有 value.strip() 校验)
            parts.firstOrNull { it.startsWith("$name=") && it.substringAfter('=').isNotBlank() }
                ?.let { return it }
        }
        return null
    }

    /** Extract the commandcode session cookie segment (commandcode_api.build_cookie_header parity). */
    fun extractSessionCookie(cookieHeader: String?): String? {
        if (cookieHeader.isNullOrBlank()) return null
        var cookie = cookieHeader.trim()
        if (cookie.startsWith("cookie:", ignoreCase = true)) cookie = cookie.substring(7).trim()
        for (part in cookie.split(";")) {
            val p = part.trim()
            // 同 extractAuthCookie: 空值 cookie 不是有效凭证
            if (p.startsWith(CC_AUTH_COOKIE_NAME + "=") && p.substringAfter('=').isNotBlank()) return p
        }
        return null
    }

    /** Extract workspace id from a login-page URL — port of _WORKSPACE_URL_RE usage. */
    fun extractWorkspaceHint(url: String?): String {
        if (url.isNullOrBlank()) return "Default"
        return WORKSPACE_URL_RE.find(url)?.groupValues?.get(1) ?: "Default"
    }

    /** Whether the page is on opencode.ai (any subdomain — cookie domain is readable there). */
    fun isOnOpencodeDomain(url: String?): Boolean {
        if (url.isNullOrBlank()) return false
        val host = runCatching { java.net.URI(url).host }.getOrNull() ?: return false
        return host == "opencode.ai" || host.endsWith(".opencode.ai")
    }

    /** Whether the page is on commandcode.ai (any subdomain) — auth._target_host parity。 */
    fun isOnCommandcodeDomain(url: String?): Boolean {
        if (url.isNullOrBlank()) return false
        val host = runCatching { java.net.URI(url).host }.getOrNull() ?: return false
        return host == "commandcode.ai" || host.endsWith(".commandcode.ai")
    }

    // ------------------------------------------------------------------
    // 登录入口偏离 / GitHub OAuth 续跑 — ports of auth.py v2.2.0
    // ------------------------------------------------------------------

    private val GITHUB_HOST_RE = Regex("^https://(?:[\\w.-]*\\.)?github\\.com(?:/|$)", RegexOption.IGNORE_CASE)

    /** GitHub 授权入口: /login?client_id= 或 /login/oauth/authorize?… */
    private val GITHUB_OAUTH_ENTRY_RE = Regex("^https://github\\.com/login(?:\\?|/oauth/authorize\\?)", RegexOption.IGNORE_CASE)

    /** 登录流程中间页 (登录表单/两步验证/设备验证) — 等待用户操作, 不算卡死。 */
    private val GITHUB_FLOW_RE = Regex("^https://github\\.com/(?:login(?:[/?]|$)|sessions(?:/|$)|two_factor)", RegexOption.IGNORE_CASE)
    private val RETURN_TO_RE = Regex("[?&]return_to=(.+)$")

    /**
     * 页面是否被残留会话带离了登录入口 (auth.login_entry_lost parity).
     *
     * 仅 commandcode 判定: 登录入口是 /signin 单页, 页面加载完却停在该域其它路径
     * (官网/控制台) 说明服务端按残留会话重定向走了, 用户没有登录机会.
     * opencode 的 OAuth 合法跨多域多路径, 不判定.
     *
     * 豁免带 code= 的 OAuth 成功回调: 服务端正要据此种会话, 判偏离会把刚建立的
     * 会话清掉 (失败回调带 error= 不豁免 —— 清会话拉回登录页正是期望行为).
     */
    fun isOffLoginEntry(url: String?, provider: String?): Boolean {
        if (normalizeProvider(provider) != PROVIDER_COMMANDCODE) return false
        if (!isOnCommandcodeDomain(url)) return false
        val target = url ?: return false
        val path = runCatching { URI(target).path }.getOrNull() ?: return false
        if (path.startsWith("/signin")) return false
        if (queryParam(target, "code") != null) return false
        return true
    }

    /** 取 query 参数首个值 (URL 解码后); 不存在返回 null. */
    private fun queryParam(url: String, key: String): String? {
        val query = runCatching { URI(url).rawQuery }.getOrNull() ?: return null
        for (part in query.split("&")) {
            if (part.isEmpty()) continue
            val eq = part.indexOf('=')
            val k = urlDecode(if (eq >= 0) part.substring(0, eq) else part)
            if (k == key) return urlDecode(if (eq >= 0) part.substring(eq + 1) else "")
        }
        return null
    }

    /**
     * GitHub 页面分类 (auth._classify_github_url parity):
     * "entry"(授权入口) / "flow"(登录流程页) / "stuck"(无关页) / null(非 GitHub)。
     */
    fun classifyGithubUrl(url: String?): String? {
        if (url.isNullOrBlank() || !GITHUB_HOST_RE.containsMatchIn(url)) return null
        if (GITHUB_OAUTH_ENTRY_RE.containsMatchIn(url) && "client_id=" in url) return "entry"
        if (GITHUB_FLOW_RE.containsMatchIn(url)) return "flow"
        return "stuck"
    }

    /**
     * 从 GitHub 登录入口 URL 提取可续跑的 authorize URL (auth._authorize_url_from_entry parity).
     *
     * 入口形如 github.com/login?client_id=...&return_to=%2Flogin%2Foauth%2Fauthorize%3F...
     * (return_to 可能未编码/编码/混合编码); 提取 authorize 路径后规范化 query, 让
     * 已登录会话直接续跑授权 (2FA 后丢 return_to 卡无关页的自动恢复)。
     */
    fun authorizeUrlFromEntry(entryUrl: String?): String? {
        if (entryUrl.isNullOrBlank()) return null
        var target: String? = null
        val idx = entryUrl.indexOf("/login/oauth/authorize")
        if (idx >= 0) {
            target = entryUrl.substring(idx)
        } else {
            val m = RETURN_TO_RE.find(entryUrl)
            if (m != null) {
                val decoded = runCatching { unquoteAsIs(m.groupValues[1]) }.getOrNull().orEmpty()
                val i = decoded.indexOf("/login/oauth/authorize")
                if (i >= 0) target = decoded.substring(i)
            }
        }
        return target?.let { normalizeAuthorizeTarget(it) }
    }

    /**
     * 规范化 authorize 目标 URL 的 query (auth._normalize_authorize_target parity):
     * 混合编码时 redirect_uri 可能是双重编码, GitHub 解一层后与注册回调失配而报错;
     * 这里把每个 query 值解到不含百分号编码, 再统一单层编码重建, 并去掉
     * prompt=select_account (已登录续跑不需要账号选择器)。
     */
    fun normalizeAuthorizeTarget(target: String): String? {
        val qIdx = target.indexOf('?')
        val path = if (qIdx >= 0) target.substring(0, qIdx) else target
        val query = if (qIdx >= 0) target.substring(qIdx + 1) else ""
        val pairs = mutableListOf<Pair<String, String>>()
        for (part in query.split("&")) {
            if (part.isEmpty()) continue
            val eq = part.indexOf('=')
            val key = urlDecode(if (eq >= 0) part.substring(0, eq) else part)
            var value = urlDecode(if (eq >= 0) part.substring(eq + 1) else "")
            if (key == "prompt" && value == "select_account") continue
            var iter = 0
            while (iter < 3 && '%' in value) {
                val decoded = runCatching { unquoteAsIs(value) }.getOrNull() ?: break
                if (decoded == value) break
                value = decoded
                iter++
            }
            pairs.add(key to value)
        }
        if (pairs.none { it.first == "client_id" }) return null
        return "https://github.com" + path + "?" + pairs.joinToString("&") { (k, v) ->
            urlEncode(k) + "=" + urlEncode(v)
        }
    }

    /** query 参数解码 (Python parse_qsl 语义: `+` = 空格); 非法转义保留原值 (unquote 不抛)。 */
    private fun urlDecode(s: String): String =
        runCatching { URLDecoder.decode(s, "UTF-8") }.getOrDefault(s)

    /** Python unquote 语义: `+` 保持字面, 只解百分号编码 (非法编码保留原值)。 */
    private fun unquoteAsIs(s: String): String =
        runCatching { URLDecoder.decode(s.replace("+", "%2B"), "UTF-8") }.getOrDefault(s)

    /** Python urlencode 语义 (quote_plus: 空格 -> `+`)。 */
    private fun urlEncode(s: String): String = URLEncoder.encode(s, "UTF-8")
}
