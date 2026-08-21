package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.QuotaResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.concurrent.TimeUnit

/** OpenCode API errors. */
open class OpenCodeApiException(message: String) : Exception(message)

/** Auth failure (401/403) — token invalid or expired. */
class AuthException(message: String) : OpenCodeApiException(message)

/**
 * OpenCode Go API client — 1:1 port of opencode_api.py (desktop).
 * Two capabilities:
 *  1. quota: fetch opencode.ai dashboard HTML, regex-parse 5h/weekly/monthly usage
 *  2. usage: call opencode.ai/_server server-fn endpoint, parse each request's token/cost detail
 */
class OpenCodeApi(private val client: OkHttpClient = defaultClient()) {

    companion object {
        const val DASHBOARD_BASE = "https://opencode.ai/workspace"
        const val WORKSPACE_SERVER_ID =
            "def39973159c7f0483d8793a822b8dbb10d067e12c65455fcb4608459ba0234f"
        const val DEFAULT_USAGE_SERVER_ID =
            "bfd684bfc2e4eed05cd0b518f5e4eafd3f3376e3938abb9e536e7c03df831e5c"
        const val USER_AGENT =
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/148.0"
        // Mobile-tuned network budget. opencode.ai is frequently slow to answer, and with
        // the desktop's 30s / 3-retry budget a single hung request can stall the refresh
        // spinner for ~90s. Cap each attempt so failures surface in seconds; the retry
        // loop still absorbs transient blips on modest mobile links. (Desktop parity:
        // opencode_api.py uses 30s / 3 retries — fine there because the desktop syncs on
        // a background thread and never blocks the UI.)
        const val CONNECT_TIMEOUT_SEC = 10L
        const val READ_TIMEOUT_SEC = 15L
        const val WRITE_TIMEOUT_SEC = 15L
        const val MAX_BODY_BYTES = 4 * 1024 * 1024
        const val FETCH_RETRIES = 2
        private val RETRY_BACKOFF_MS = listOf(500L, 1500L, 3000L)
        private val WORKSPACE_ID_RE = Regex("wrk_[A-Za-z0-9]+")
        private val WORKSPACE_ENTRY_RE = Regex(
            """id\s*:\s*"(wrk_[^"]+)"[^{}]*?name\s*:\s*"([^"]*)"""",
            setOf(RegexOption.DOT_MATCHES_ALL),
        )
        // keys 页面内嵌响应数据形如 {id:"key_xxx",name:"gongsi",key:"sk-...",...}
        private val KEY_ENTRY_RE = Regex("""\{id:"(key_[A-Za-z0-9]+)",name:"([^"]*)"\""")

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(CONNECT_TIMEOUT_SEC, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SEC, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SEC, TimeUnit.SECONDS)
            .followRedirects(true)
            .build()
    }

    /** Normalize token into the auth cookie segment. */
    fun buildCookieHeader(token: String): String {
        var cookie = token.trim()
        if (cookie.startsWith("cookie:", ignoreCase = true)) cookie = cookie.substring(7).trim()
        if (cookie.isEmpty()) return ""
        for (part in cookie.split(";")) {
            val p = part.trim()
            if (p.startsWith("auth=")) return p
        }
        return "auth=$cookie"
    }

    private suspend fun fetch(url: String, headers: Map<String, String>): String =
        withContext(Dispatchers.IO) {
            var lastExc: Exception? = null
            for (attempt in 0 until FETCH_RETRIES) {
                try {
                    val rb = Request.Builder().url(url)
                    for ((k, v) in headers) rb.header(k, v)
                    val result = client.newCall(rb.build()).execute().use { resp ->
                        val status = resp.code
                        val body = resp.body?.string()?.take(MAX_BODY_BYTES) ?: ""
                        when {
                            status == 401 || status == 403 ->
                                throw AuthException("认证失败 (HTTP $status)，请重新登录")
                            status == 404 ->
                                throw OpenCodeApiException("工作区不存在 (HTTP 404)")
                            status !in 200..299 ->
                                throw OpenCodeApiException("请求返回 HTTP $status")
                            else -> body
                        }
                    }
                    return@withContext result
                } catch (e: IOException) {
                    lastExc = e
                    if (attempt < FETCH_RETRIES - 1) delay(RETRY_BACKOFF_MS[attempt])
                } catch (e: AuthException) {
                    throw e
                } catch (e: OpenCodeApiException) {
                    throw e
                }
            }
            throw OpenCodeApiException("网络错误: $lastExc")
        }

    private suspend fun serverCall(serverId: String, args: List<Any?>, refererPath: String, token: String): String {
        val cookie = buildCookieHeader(token)
        if (cookie.isEmpty()) throw OpenCodeApiException("token 为空")
        val url = "https://opencode.ai/_server?id=" +
            java.net.URLEncoder.encode(serverId, "UTF-8") +
            "&args=" + java.net.URLEncoder.encode(argsToJson(args), "UTF-8")
        val headers = mapOf(
            "Cookie" to cookie,
            "X-Server-Id" to serverId,
            "X-Server-Instance" to "server-fn:${System.currentTimeMillis() * 1000}",
            "User-Agent" to USER_AGENT,
            "Origin" to "https://opencode.ai",
            "Referer" to "https://opencode.ai$refererPath",
            "Accept" to "text/javascript, application/json;q=0.9, */*;q=0.8",
        )
        return fetch(url, headers)
    }

    private fun argsToJson(args: List<Any?>): String {
        // Python json.dumps style: strings quoted, ints plain, null
        val sb = StringBuilder("[")
        for ((i, a) in args.withIndex()) {
            if (i > 0) sb.append(",")
            sb.append(
                when (a) {
                    null -> "null"
                    is String -> "\"" + a.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
                    else -> a.toString()
                }
            )
        }
        sb.append("]")
        return sb.toString()
    }

    // ------------------------------------------------------------------
    // Workspace resolution
    // ------------------------------------------------------------------

    fun extractWorkspaceId(raw: String): String {
        val value = raw.trim()
        if (value.isEmpty()) return ""
        if (value.startsWith("wrk_") && value.length > 4) return value
        return WORKSPACE_ID_RE.find(value)?.value ?: ""
    }

    /** Fetch all workspaces (id, name) for the account. */
    suspend fun fetchWorkspaceRefs(token: String): List<Pair<String, String>> {
        val cookie = buildCookieHeader(token)
        if (cookie.isEmpty()) throw OpenCodeApiException("token 为空")
        val url = "https://opencode.ai/_server?id=" +
            java.net.URLEncoder.encode(WORKSPACE_SERVER_ID, "UTF-8")
        val headers = mapOf(
            "Cookie" to cookie,
            "X-Server-Id" to WORKSPACE_SERVER_ID,
            "X-Server-Instance" to "server-fn:${System.currentTimeMillis() * 1000}",
            "User-Agent" to USER_AGENT,
            "Origin" to "https://opencode.ai",
            "Referer" to "https://opencode.ai",
            "Accept" to "text/javascript, application/json;q=0.9, */*;q=0.8",
        )
        val text = fetch(url, headers)
        val refs = mutableListOf<Pair<String, String>>()
        val seen = HashSet<String>()
        for (m in WORKSPACE_ENTRY_RE.findAll(text)) {
            val workspaceId = m.groupValues[1]
            val name = m.groupValues[2].trim()
            if (workspaceId in seen) continue
            seen.add(workspaceId)
            refs.add(workspaceId to name)
        }
        if (refs.isEmpty()) throw OpenCodeApiException("无法从账号数据解析工作区 ID")
        return refs
    }

    /** Resolve workspace hint (id / name / Default) into wrk_xxx ID. */
    suspend fun resolveWorkspaceId(hint: String, token: String): String {
        val resolved = extractWorkspaceId(hint)
        if (resolved.isNotEmpty()) return resolved
        val refs = fetchWorkspaceRefs(token)
        val hintL = hint.trim().lowercase()
        if (hintL.isNotEmpty()) {
            for ((workspaceId, name) in refs) {
                if (workspaceId.lowercase() == hintL || name.lowercase() == hintL) {
                    return workspaceId
                }
            }
        }
        if (refs.isNotEmpty()) return refs[0].first
        throw OpenCodeApiException("无法从 \"$hint\" 解析工作区 ID")
    }

    // ------------------------------------------------------------------
    // Quota
    // ------------------------------------------------------------------

    /** Fetch quota windows for a workspace. Never throws — returns QuotaResult with error. */
    suspend fun fetchQuota(token: String, workspaceHint: String = "Default"): QuotaResult {
        val nowIso = java.time.Instant.now().toString()
        val hint = (workspaceHint.ifBlank { "Default" }).trim()
        if (token.isBlank()) {
            return QuotaResult("Default", hint, false, nowIso, error = "未配置 token")
        }
        return try {
            val workspaceId = resolveWorkspaceId(hint, token)
            val cookie = buildCookieHeader(token)
            if (cookie.isEmpty()) throw OpenCodeApiException("token 为空")
            val url = "$DASHBOARD_BASE/${java.net.URLEncoder.encode(workspaceId, "UTF-8")}/go"
            val headers = mapOf(
                "Cookie" to cookie,
                "User-Agent" to USER_AGENT,
                "Accept" to "text/html, application/xhtml+xml",
            )
            // dashboard HTML is slow: shorter timeout + fewer retries (desktop parity)
            val html = withContext(Dispatchers.IO) {
                var last: Exception? = null
                for (attempt in 0 until 2) {
                    try {
                        val rb = Request.Builder().url(url)
                        for ((k, v) in headers) rb.header(k, v)
                        val result = client.newCall(rb.build()).execute().use { resp ->
                            when (resp.code) {
                                401, 403 -> throw AuthException("认证失败 (HTTP ${resp.code})，请重新登录")
                                404 -> throw OpenCodeApiException("工作区不存在 (HTTP 404)")
                            }
                            if (resp.code !in 200..299) throw OpenCodeApiException("请求返回 HTTP ${resp.code}")
                            resp.body?.string()?.take(MAX_BODY_BYTES) ?: ""
                        }
                        return@withContext result
                    } catch (e: IOException) {
                        last = e
                        if (attempt == 0) delay(500)
                    } catch (e: AuthException) {
                        throw e
                    } catch (e: OpenCodeApiException) {
                        throw e
                    }
                }
                throw OpenCodeApiException("网络错误: $last")
            }
            val windows = QuotaParser.parseQuotaHtml(html)
            if (windows.isEmpty()) throw OpenCodeApiException("无法从 Dashboard HTML 解析额度数据")
            QuotaResult("Default", workspaceId, true, nowIso, windows = windows)
        } catch (e: Exception) {
            QuotaResult("Default", hint, false, nowIso, error = e.message ?: "未知错误")
        }
    }

    // ------------------------------------------------------------------
    // Usage records
    // ------------------------------------------------------------------

    /** Fetch one page of usage records (50 per page, page starts at 0). */
    suspend fun fetchUsagePage(
        token: String,
        workspaceId: String,
        page: Int = 0,
        keyId: String? = null,
        usageServerId: String? = null,
    ): List<io.github.yphyphyph.gogauge.data.model.UsageRecord> {
        val args = mutableListOf<Any?>(workspaceId as Any?)
        if (keyId != null) {
            if (page > 0) {
                args.add(page); args.add(keyId)
            } else {
                args.add(keyId)
            }
        } else if (page > 0) {
            args.add(page)
        }
        val serverId = usageServerId ?: DEFAULT_USAGE_SERVER_ID
        val text = serverCall(serverId, args, "/workspace/$workspaceId/usage", token)
        return UsageParser.parseUsageResponse(text)
    }

    /**
     * 拉取工作区下所有 API key 的名称映射 (key_id -> 名称) — port of
     * opencode_api.fetch_key_names (desktop). keys 页面内嵌响应数据形如
     * {id:"key_xxx",name:"gongsi",key:"sk-...",...}, 正则提取 id 与 name 即可.
     * 页面拉取或解析失败时返回空 map, 不影响主流程 (desktop parity).
     */
    suspend fun fetchKeyNames(token: String, workspaceId: String): Map<String, String> {
        val cookie = buildCookieHeader(token)
        if (cookie.isEmpty()) return emptyMap()
        val url = "$DASHBOARD_BASE/$workspaceId/keys"
        val headers = mapOf(
            "Cookie" to cookie,
            "User-Agent" to USER_AGENT,
            "Origin" to "https://opencode.ai",
            "Referer" to "$DASHBOARD_BASE/$workspaceId/keys",
            "Accept" to "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        return try {
            val html = fetch(url, headers)
            val names = linkedMapOf<String, String>()
            for (m in KEY_ENTRY_RE.findAll(html)) {
                val id = m.groupValues[1]
                val name = m.groupValues[2].trim()
                if (id.isNotEmpty() && name.isNotEmpty()) names.putIfAbsent(id, name)
            }
            names
        } catch (e: Exception) {
            emptyMap()
        }
    }
}
