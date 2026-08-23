package io.github.yphyphyph.gogauge.auth

import java.net.URLEncoder
import java.util.UUID

/**
 * Login URL builder + cookie extraction — ports of auth.py (desktop).
 */
object Login {

    const val LOGIN_BASE = "https://auth.opencode.ai/authorize"
    const val LOGIN_CLIENT_ID = "app"
    const val LOGIN_REDIRECT_URI = "https://opencode.ai/auth/callback"
    const val AUTH_COOKIE_NAME = "auth"
    const val OPENDCODE_DOMAIN = "https://opencode.ai"

    private val WORKSPACE_URL_RE = Regex("/workspace/(wrk_[A-Za-z0-9]+)")

    /** Build the OAuth authorize URL — port of auth.build_login_url. */
    fun buildLoginUrl(): String {
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
}
