package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.QuotaResult
import io.github.yphyphyph.gogauge.data.model.UsagePage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.concurrent.TimeUnit

/** OpenCode API errors. */
open class OpenCodeApiException(message: String) : Exception(message)

/** Auth failure (401) — token invalid or expired. */
class AuthException(message: String) : OpenCodeApiException(message)

/**
 * 瞬时 HTTP 故障 — 内部标记为可重试, 让 fetch 的重试循环接住.
 * 不对外抛出: 重试耗尽后统一转成 OpenCodeApiException.
 */
internal class RetryableHttpException(message: String) : Exception(message)

/**
 * OpenCode Console API 客户端 (2026-09 控制台改版后) — 1:1 port of opencode_api.py (desktop).
 *
 * - 会话 Cookie: ``__Host-console_session`` (旧 ``auth`` 兼容历史 token)
 * - 配额: GET /console/api/go/status      (旧 dashboard HTML 解析已下线)
 * - 明细: GET /console/api/request-logs   (游标分页; 服务端仅保留 30 天)
 * - 工作区: GET /console/api/orgs;  Key 名称: GET /console/api/service-accounts
 *
 * 所有 /console/api 请求除 Cookie 外还需 ``x-org-id: <wrk_xxx>`` 头 (org 即工作区).
 */
class OpenCodeApi(private val client: OkHttpClient = defaultClient()) {

    companion object {
        const val CONSOLE_ORIGIN = "https://opencode.ai"
        const val CONSOLE_LOGIN_URL = "https://opencode.ai/console/login"
        const val API_BASE = "https://opencode.ai/console/api"
        const val SESSION_COOKIE = "__Host-console_session"
        const val LEGACY_SESSION_COOKIE = "auth"
        /** request-logs 单页条数 (接口上限 100). */
        const val USAGE_PAGE_SIZE = 100

        const val USER_AGENT =
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/148.0"

        // Mobile-tuned network budget. opencode.ai is frequently slow to answer, and with
        // the desktop's 30s / 3-retry budget a single hung request can stall the refresh
        // spinner for ~90s. Cap each attempt so failures surface in seconds; the retry
        // loop still absorbs transient blips on modest mobile links.
        const val CONNECT_TIMEOUT_SEC = 10L
        const val READ_TIMEOUT_SEC = 15L
        const val WRITE_TIMEOUT_SEC = 15L
        const val MAX_BODY_BYTES = 4 * 1024 * 1024
        const val FETCH_RETRIES = 2
        private val RETRY_BACKOFF_MS = listOf(500L, 1500L, 3000L)
        private val WORKSPACE_ID_RE = Regex("wrk_[A-Za-z0-9]+")
        private val COOKIE_PAIR_RE = Regex("^[A-Za-z0-9_.\\-]+\\s*=\\s*\\S+$")

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(CONNECT_TIMEOUT_SEC, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SEC, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SEC, TimeUnit.SECONDS)
            .followRedirects(true)
            .build()
    }

    private val json = Json { ignoreUnknownKeys = true }

    /**
     * 把 token 规范化为 Cookie 头 — port of opencode_api.build_cookie_header.
     *
     * 支持三种输入: 完整 Cookie 串 (``__Host-console_session=st_xxx`` / ``auth=Fe26...``,
     * 直接取该段)、``Cookie:`` 前缀串、纯值 (补上新版会话 Cookie 名)。
     */
    fun buildCookieHeader(token: String): String {
        var raw = token.trim()
        if (raw.startsWith("cookie:", ignoreCase = true)) raw = raw.substring(7).trim()
        if (raw.isEmpty()) return ""
        for (part in raw.split(";")) {
            val p = part.trim()
            if (p.isEmpty()) continue
            val name = p.substringBefore("=").trim().lowercase()
            if (name == SESSION_COOKIE.lowercase() || name == LEGACY_SESSION_COOKIE) return p
        }
        // 形如 name=value 的其它 Cookie 原样透传, 纯值则按新版会话 Cookie 处理
        if (COOKIE_PAIR_RE.matches(raw)) return raw
        return "$SESSION_COOKIE=$raw"
    }

    /**
     * GET 请求, 自动重试 — port of opencode_api._fetch.
     * 401 -> AuthException; 403/404 -> 立即失败 (确定性错误); 其余非 2xx 与网络错误重试。
     */
    private suspend fun fetchText(
        url: String,
        headers: Map<String, String>,
        retries: Int = FETCH_RETRIES,
    ): String = withContext(Dispatchers.IO) {
        var lastExc: Exception? = null
        for (attempt in 0 until retries) {
            try {
                val rb = Request.Builder().url(url)
                for ((k, v) in headers) rb.header(k, v)
                val result = client.newCall(rb.build()).execute().use { resp ->
                    val status = resp.code
                    when {
                        status == 401 -> throw AuthException("登录已过期，请重新登录")
                        status == 403 -> throw OpenCodeApiException("无访问权限 (HTTP 403)")
                        status == 404 -> throw OpenCodeApiException("工作区不存在或接口不可用 (HTTP 404)")
                        status !in 200..299 -> throw RetryableHttpException("请求返回 HTTP $status")
                        else -> {
                            val declared = resp.header("Content-Length")?.toLongOrNull() ?: 0L
                            if (declared > MAX_BODY_BYTES) {
                                throw OpenCodeApiException(
                                    "响应过大 (${declared / (1 shl 20)} MiB," +
                                        " 上限 ${MAX_BODY_BYTES / (1 shl 20)} MiB)"
                                )
                            }
                            readBounded(resp)
                        }
                    }
                }
                return@withContext result
            } catch (e: RetryableHttpException) {
                lastExc = e
                if (attempt < retries - 1) delay(RETRY_BACKOFF_MS[attempt.coerceAtMost(RETRY_BACKOFF_MS.size - 1)])
            } catch (e: IOException) {
                lastExc = e
                if (attempt < retries - 1) delay(RETRY_BACKOFF_MS[attempt.coerceAtMost(RETRY_BACKOFF_MS.size - 1)])
            } catch (e: AuthException) {
                throw e
            } catch (e: OpenCodeApiException) {
                throw e
            }
        }
        throw OpenCodeApiException("网络错误: $lastExc")
    }

    /** 流式读取响应体, 超 MAX_BODY_BYTES 即中止 (防止先整读内存再截断). */
    private fun readBounded(resp: okhttp3.Response): String =
        readBoundedBody(resp, MAX_BODY_BYTES)

    /** 调用 /console/api 下接口, 返回解析后的 JSON — port of opencode_api._api_get. */
    private suspend fun apiGet(
        path: String,
        token: String,
        orgId: String? = null,
        params: Map<String, String?> = emptyMap(),
        retries: Int = FETCH_RETRIES,
    ): JsonElement {
        val cookie = buildCookieHeader(token)
        if (cookie.isEmpty()) throw OpenCodeApiException("token 为空")
        var url = "$API_BASE$path"
        val query = params.entries
            .filter { it.value != null }
            .joinToString("&") { (k, v) ->
                java.net.URLEncoder.encode(k, "UTF-8") + "=" + java.net.URLEncoder.encode(v!!, "UTF-8")
            }
        if (query.isNotEmpty()) url += "?$query"
        val headers = mutableMapOf(
            "Cookie" to cookie,
            "Accept" to "application/json",
            "User-Agent" to USER_AGENT,
            "Origin" to CONSOLE_ORIGIN,
            "Referer" to "$CONSOLE_ORIGIN/console/",
        )
        if (!orgId.isNullOrBlank()) headers["x-org-id"] = orgId
        val text = fetchText(url, headers, retries = retries)
        return try {
            json.parseToJsonElement(text)
        } catch (e: Exception) {
            throw OpenCodeApiException("接口返回非 JSON 数据")
        }
    }

    private fun JsonElement?.asText(): String {
        val text = (this as? JsonPrimitive)?.content ?: return ""
        return if (text == "null") "" else text
    }

    // ------------------------------------------------------------------
    // Workspace resolution (GET /orgs)
    // ------------------------------------------------------------------

    fun extractWorkspaceId(raw: String): String {
        val value = raw.trim()
        if (value.isEmpty()) return ""
        if (value.startsWith("wrk_") && value.length > 4) return value
        return WORKSPACE_ID_RE.find(value)?.value ?: ""
    }

    /** Fetch all workspaces (id, name) for the account — port of fetch_workspace_refs. */
    suspend fun fetchWorkspaceRefs(token: String): List<Pair<String, String>> {
        val data = apiGet("/orgs", token)
        val refs = mutableListOf<Pair<String, String>>()
        val seen = HashSet<String>()
        if (data is JsonArray) {
            for (element in data) {
                val item = element as? JsonObject ?: continue
                val workspaceId = item["id"].asText().trim()
                if (workspaceId.isEmpty() || workspaceId in seen) continue
                seen.add(workspaceId)
                refs.add(workspaceId to item["name"].asText().trim())
            }
        }
        if (refs.isEmpty()) throw OpenCodeApiException("无法获取工作区列表 (账号下没有工作区)")
        return refs
    }

    /**
     * 解析工作区提示 -> (workspace_id, 显示名) — port of _resolve_workspace.
     * hint 已是 wrk_xxx 时直接采用; 否则拉一次工作区列表按 ID/名称匹配, 匹配不到取第一个。
     */
    private suspend fun resolveWorkspace(hint: String, token: String): Pair<String, String> {
        val resolved = extractWorkspaceId(hint)
        if (resolved.isNotEmpty()) return resolved to ""
        val refs = fetchWorkspaceRefs(token)
        val hintL = hint.trim().lowercase()
        if (hintL.isNotEmpty()) {
            for ((workspaceId, name) in refs) {
                if (workspaceId.lowercase() == hintL || name.lowercase() == hintL) {
                    return workspaceId to name
                }
            }
        }
        return refs[0]
    }

    /** Resolve workspace hint (id / name / Default) into wrk_xxx ID. */
    suspend fun resolveWorkspaceId(hint: String, token: String): String =
        resolveWorkspace(hint, token).first

    // ------------------------------------------------------------------
    // Quota (GET /go/status)
    // ------------------------------------------------------------------

    /** Fetch quota windows for a workspace. Never throws — returns QuotaResult with error. */
    suspend fun fetchQuota(token: String, workspaceHint: String = "Default"): QuotaResult {
        val nowIso = java.time.Instant.now().toString()
        val hint = (workspaceHint.ifBlank { "Default" }).trim()
        if (token.isBlank()) {
            return QuotaResult("Default", hint, false, nowIso, error = "未配置 token")
        }
        var name = hint
        return try {
            val (workspaceId, wsName) = resolveWorkspace(hint, token)
            if (wsName.isNotEmpty()) name = wsName
            val payload = apiGet("/go/status", token, orgId = workspaceId, retries = 2)
            val windows = QuotaParser.parseGoStatus(payload)
            if (windows.isEmpty()) {
                throw OpenCodeApiException("账号未订阅 OpenCode Go (接口无额度数据)")
            }
            // 真实计费周期起止: 「本周期」筛选的起点数据源 (desktop fetch_quota parity)
            val (periodStart, periodEnd) = QuotaParser.parseGoPeriod(payload)
            QuotaResult(
                name, workspaceId, true, nowIso, windows = windows,
                periodStart = periodStart, periodEnd = periodEnd,
            )
        } catch (e: CancellationException) {
            // 协程取消必须向上传播: 否则被取消的调用会继续跑完阻塞请求,
            // 并把"取消失败"当成一次配额错误写进缓存
            throw e
        } catch (e: Exception) {
            QuotaResult(name, hint, false, nowIso, error = e.message ?: "未知错误")
        }
    }

    // ------------------------------------------------------------------
    // Usage records (GET /request-logs, 游标分页)
    // ------------------------------------------------------------------

    /**
     * 拉取一页用量明细 (游标分页, 按时间倒序) — port of fetch_usage_page.
     *
     * @param cursor 上一页返回的 nextCursor; 首页传 null
     * @param sinceMs 只取该毫秒时间戳之后的记录 (增量同步用)
     */
    suspend fun fetchUsagePage(
        token: String,
        workspaceId: String,
        cursor: String? = null,
        limit: Int = USAGE_PAGE_SIZE,
        sinceMs: Long? = null,
    ): UsagePage {
        val params = mutableMapOf<String, String?>(
            "limit" to limit.coerceIn(1, USAGE_PAGE_SIZE).toString(),
        )
        if (!cursor.isNullOrBlank()) params["cursor"] = cursor
        if (sinceMs != null && sinceMs > 0) params["since"] = sinceMs.toString()
        val payload = apiGet("/request-logs", token, orgId = workspaceId, params = params)
        return UsageParser.parseRequestLogs(payload)
    }

    // ------------------------------------------------------------------
    // Key 名称 (GET /service-accounts)
    // ------------------------------------------------------------------

    /**
     * 拉取工作区下所有 API key 的名称映射 (key_id -> 名称) — port of fetch_key_names.
     * service-accounts 响应形如 ``{"items":[{account:{...}, keys:[{id,name},...]}]}``;
     * 失败时返回空 map (不影响主流程)。
     */
    suspend fun fetchKeyNames(token: String, workspaceId: String): Map<String, String> {
        val payload = try {
            apiGet("/service-accounts", token, orgId = workspaceId, retries = 2)
        } catch (e: CancellationException) {
            throw e  // 取消不当作"拉取失败"
        } catch (e: Exception) {
            return emptyMap()
        }
        val names = linkedMapOf<String, String>()
        val items = (payload as? JsonObject)?.get("items") as? JsonArray ?: return names
        for (entry in items) {
            val obj = entry as? JsonObject ?: continue
            val keys = obj["keys"] as? JsonArray ?: continue
            for (key in keys) {
                val k = key as? JsonObject ?: continue
                val keyId = k["id"].asText().trim()
                val name = k["name"].asText().trim()
                if (keyId.isNotEmpty() && name.isNotEmpty()) names.putIfAbsent(keyId, name)
            }
        }
        return names
    }
}
