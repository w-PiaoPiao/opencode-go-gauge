package io.github.yphyphyph.gogauge.auth

import java.net.URLEncoder
import java.util.UUID

/**
 * Login URL builder + cookie extraction — ports of auth.py (desktop).
 * 支持双 provider: opencode 与 commandcode (GOAT)。
 */
object Login {

    const val PROVIDER_OPENCODE = "opencode"
    const val PROVIDER_COMMANDCODE = "commandcode"

    // ---- opencode ----
    const val LOGIN_BASE = "https://auth.opencode.ai/authorize"
    const val LOGIN_CLIENT_ID = "app"
    const val LOGIN_REDIRECT_URI = "https://opencode.ai/auth/callback"
    const val AUTH_COOKIE_NAME = "auth"
    const val OPENDCODE_DOMAIN = "https://opencode.ai"

    // ---- commandcode (GOAT) — auth.py CC_* constants parity ----
    const val CC_LOGIN_BASE = "https://commandcode.ai/signin"
    const val CC_AUTH_COOKIE_NAME = "__Secure-commandcode_prod_.session_token"
    const val CC_DOMAIN = "https://commandcode.ai"

    private val WORKSPACE_URL_RE = Regex("/workspace/(wrk_[A-Za-z0-9]+)")

    fun normalizeProvider(provider: String?): String =
        if (provider == PROVIDER_COMMANDCODE) PROVIDER_COMMANDCODE else PROVIDER_OPENCODE

    /** Build the login URL for the given provider (auth.build_login_url parity). */
    fun buildLoginUrl(provider: String?): String {
        if (normalizeProvider(provider) == PROVIDER_COMMANDCODE) return CC_LOGIN_BASE
        val params = mapOf(
            "client_id" to LOGIN_CLIENT_ID,
            "redirect_uri" to LOGIN_REDIRECT_URI,
            "response_type" to "code",
            "state" to UUID.randomUUID().toString().replace("-", ""),
        )
        return LOGIN_BASE + "?" + params.entries.joinToString("&") { (k, v) ->
            "$k=${URLEncoder.encode(v, "UTF-8")}"
        }
    }

    /** Extract the `auth=<value>` cookie segment — port of build_cookie_header. */
    fun extractAuthCookie(cookieHeader: String?): String? {
        if (cookieHeader.isNullOrBlank()) return null
        var cookie = cookieHeader.trim()
        if (cookie.startsWith("cookie:", ignoreCase = true)) cookie = cookie.substring(7).trim()
        for (part in cookie.split(";")) {
            val p = part.trim()
            if (p.startsWith("auth=")) return p
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
            if (p.startsWith(CC_AUTH_COOKIE_NAME + "=")) return p
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
}
