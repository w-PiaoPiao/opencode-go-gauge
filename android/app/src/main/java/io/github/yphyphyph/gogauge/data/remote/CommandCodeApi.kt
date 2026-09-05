package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.QuotaResult
import io.github.yphyphyph.gogauge.data.model.QuotaWindow
import io.github.yphyphyph.gogauge.data.model.UsageChartBucket
import io.github.yphyphyph.gogauge.data.model.UsageRecord
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * Command Code (commandcode.ai) GOAT 套餐 API client — commandcode_api.py 的 1:1 移植。
 *
 * - 配额: GET /internal/billing/credits + /internal/billing/subscriptions
 *   (5h/weekly 按 used/cap 换算百分比; monthly = 计划池 - 剩余 credits)
 * - 明细: GET /internal/usage?limit=N&cursor=... 游标翻页 (服务端仅 24h/100 条)
 * - 聚合: GET /internal/usage/charts?period=billing (模型 × 5min 桶全周期)
 *
 * 鉴权: httpOnly cookie `__Secure-commandcode_prod_.session_token`。
 * 解析器为 companion 纯函数 (输入 JSON 文本), 便于 JVM 单测。
 */
class CommandCodeApi(private val client: OkHttpClient = OpenCodeApi.defaultClient()) {

    /** 抓取当前账号配额 (5h/weekly/monthly)。绝不抛异常 —— 失败返回带 error 的 QuotaResult。 */
    suspend fun fetchQuota(token: String): QuotaResult {
        val nowIso = Instant.now().toString()
        if (token.isBlank()) {
            return QuotaResult("Default", "commandcode", false, nowIso, error = "未配置 token")
        }
        return try {
            val credits = get("/billing/credits", token)
            val sub = try {
                get("/billing/subscriptions", token)
            } catch (e: Exception) {
                null // 订阅缺失不影响配额主数据
            }
            parseQuota(credits.toString(), sub?.toString(), System.currentTimeMillis())
        } catch (e: Exception) {
            QuotaResult("Default", "commandcode", false, nowIso, error = e.message ?: "未知错误")
        }
    }

    /** 拉一页用量记录; 返回 (records, nextCursor)。首页不传 cursor。 */
    suspend fun fetchUsagePage(token: String, cursor: String? = null, limit: Int = DEFAULT_LIMIT): Pair<List<UsageRecord>, String?> {
        val safeLimit = limit.coerceIn(1, MAX_LIMIT)
        val data = get("/usage", token, mapOf("limit" to safeLimit.toString(), "cursor" to cursor))
        return parseUsage(data.toString())
    }

    /** 拉取全计费周期聚合 (模型 × 5min 桶); period 透传, 服务端目前仅识别 billing。 */
    suspend fun fetchUsageCharts(token: String, period: String = "billing"): List<UsageChartBucket> {
        val data = get("/usage/charts", token, mapOf("period" to period))
        return parseCharts(data.toString())
    }

    // ------------------------------------------------------------------
    // HTTP
    // ------------------------------------------------------------------

    private suspend fun get(path: String, token: String, params: Map<String, String?> = emptyMap()): JsonObject {
        val cookie = buildCookieHeader(token)
        if (cookie.isEmpty()) throw OpenCodeApiException("token 为空")
        val sb = StringBuilder(API_BASE + path)
        val parts = params.filter { !it.value.isNullOrEmpty() }
            .map { (k, v) -> "$k=${java.net.URLEncoder.encode(v, "UTF-8")}" }
        if (parts.isNotEmpty()) sb.append("?").append(parts.joinToString("&"))
        val body = fetch(sb.toString(), cookie)
        return try {
            json.parseToJsonElement(body).jsonObject
        } catch (e: Exception) {
            throw OpenCodeApiException("响应不是合法 JSON")
        }
    }

    private suspend fun fetch(url: String, cookie: String): String = withContext(Dispatchers.IO) {
        var lastExc: Exception? = null
        for (attempt in 0 until FETCH_RETRIES) {
            try {
                val req = Request.Builder().url(url)
                    .header("Cookie", cookie)
                    .header("User-Agent", USER_AGENT)
                    .header("Accept", "application/json, text/plain, */*")
                    .build()
                client.newCall(req).execute().use { resp ->
                    val status = resp.code
                    val declared = resp.header("Content-Length")?.toLongOrNull() ?: 0L
                    if (declared > MAX_BODY_BYTES) {
                        throw OpenCodeApiException("响应过大 ($declared 字节, 上限 $MAX_BODY_BYTES)")
                    }
                    val body = readBounded(resp)
                    when {
                        status == 401 || status == 403 ->
                            throw AuthException("认证失败 (HTTP $status)，请重新登录")
                        status !in 200..299 ->
                            throw OpenCodeApiException("请求返回 HTTP $status")
                        else -> return@withContext body
                    }
                }
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

    private fun readBounded(resp: okhttp3.Response): String =
        resp.body?.byteStream()?.use { input ->
            val buf = java.io.ByteArrayOutputStream()
            val chunk = ByteArray(64 * 1024)
            var total = 0
            while (true) {
                val n = input.read(chunk)
                if (n < 0) break
                total += n
                if (total > MAX_BODY_BYTES) {
                    throw OpenCodeApiException("响应过大 (超过 $MAX_BODY_BYTES 字节)")
                }
                buf.write(chunk, 0, n)
            }
            buf.toString("UTF-8")
        } ?: ""

    companion object {
        const val API_BASE = "https://api.commandcode.ai/internal"
        const val AUTH_COOKIE_NAME = "__Secure-commandcode_prod_.session_token"
        const val USER_AGENT =
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
        const val MAX_BODY_BYTES = 4 * 1024 * 1024
        const val FETCH_RETRIES = 2
        const val DEFAULT_LIMIT = 50
        const val MAX_LIMIT = 100
        private val RETRY_BACKOFF_MS = listOf(500L, 1500L, 3000L)

        private val json = Json { ignoreUnknownKeys = true }

        // 已知计划的月度额度池 ($) — desktop _plan_monthly_allowance parity
        private val PLAN_ALLOWANCE = mapOf(
            "individual-goat" to 70.0,
            "individual-pro" to 80.0,
            "individual-go" to 10.0,
        )

        /** Normalize token into the session cookie segment (desktop build_cookie_header parity). */
        fun buildCookieHeader(token: String): String {
            var cookie = token.trim()
            if (cookie.startsWith("cookie:", ignoreCase = true)) cookie = cookie.substring(7).trim()
            if (cookie.isEmpty()) return ""
            for (part in cookie.split(";")) {
                val p = part.trim()
                if (p.startsWith(AUTH_COOKIE_NAME + "=")) return p
            }
            return "$AUTH_COOKIE_NAME=$cookie"
        }

        // ------------------------------------------------------------------
        // 纯函数解析器 (desktop parse_credits_response / parse_usage_response /
        // parse_charts_response parity, 输入为 JSON 文本便于单测)
        // ------------------------------------------------------------------

        private fun obj(e: kotlinx.serialization.json.JsonElement?): JsonObject? =
            (e as? JsonObject)

        private fun str(o: JsonObject?, key: String): String? {
            val p = o?.get(key) as? kotlinx.serialization.json.JsonPrimitive ?: return null
            if (p is kotlinx.serialization.json.JsonNull) return null
            return p.content.takeIf { it.isNotEmpty() }
        }

        private fun num(o: JsonObject?, key: String): Double? {
            val p = o?.get(key) as? kotlinx.serialization.json.JsonPrimitive ?: return null
            if (p is kotlinx.serialization.json.JsonNull) return null
            return p.content.toDoubleOrNull()
        }

        private fun intOr(v: Double?): Int = v?.toInt() ?: 0

        private fun doubleOr(v: Double?, default: Double = 0.0): Double = v ?: default

        /**
         * 把 credits + subscriptions 响应合并为 QuotaResult (desktop parse_credits_response parity)。
         * monthly = 计划额度池 - 剩余 credits; 5h/weekly 按 used/cap 换算百分比。
         */
        fun parseQuota(creditsBodyText: String, subscriptionBodyText: String?, nowMs: Long): QuotaResult {
            val creditsBody = try {
                json.parseToJsonElement(creditsBodyText).jsonObject
            } catch (e: Exception) {
                throw OpenCodeApiException("credits 响应不是合法 JSON")
            }
            val subBody = subscriptionBodyText?.let {
                try {
                    json.parseToJsonElement(it).jsonObject
                } catch (e: Exception) {
                    null
                }
            }
            val credits = obj(creditsBody["credits"]) ?: JsonObject(emptyMap())
            val limits = obj(creditsBody["windowLimits"]) ?: JsonObject(emptyMap())
            val windows = mutableListOf<QuotaWindow>()

            val five = obj(limits["fiveHour"])
            if (five != null) {
                windows += windowFrom(
                    label = "5h Rolling",
                    used = doubleOr(num(five, "used")),
                    cap = doubleOr(num(five, "cap")),
                    resetMs = (num(five, "resetAt") ?: 0.0).toLong(),
                    nowMs = nowMs,
                )
            }
            val weekly = obj(limits["weekly"])
            if (weekly != null) {
                windows += windowFrom(
                    label = "Weekly",
                    used = doubleOr(num(weekly, "used")),
                    cap = doubleOr(num(weekly, "cap")),
                    resetMs = (num(weekly, "resetAt") ?: 0.0).toLong(),
                    nowMs = nowMs,
                )
            }

            // 订阅期 (月度): 月池 = 计划额度; 已用 = 月池 - 剩余 credits
            val subData = obj(subBody?.get("data"))
            val plan = str(subData, "planId")
            val active = subData != null && str(subData, "status") == "active"
            var periodStart: String? = null
            var periodEnd: String? = null
            if (active) {
                periodStart = str(subData, "currentPeriodStart")
                periodEnd = str(subData, "currentPeriodEnd")
            }
            val remainingCredits = doubleOr(num(credits, "monthlyCredits"))
            val planTotal = plan?.let { PLAN_ALLOWANCE[it.lowercase().replace("_", "-")] }
                ?: remainingCredits.takeIf { it > 0 }
            if (planTotal != null && planTotal > 0) {
                val usedVal = (planTotal - remainingCredits).coerceAtLeast(0.0)
                val usedPct = (usedVal / planTotal * 100.0).coerceIn(0.0, 100.0)
                var resetAtIso = ""
                var resetIn = 0
                if (periodEnd != null) {
                    try {
                        val endMs = Instant.parse(periodEnd.replace("Z", "+00:00")).toEpochMilli()
                        resetAtIso = fmtIso(endMs)
                        resetIn = ((endMs - nowMs) / 1000).toInt().coerceAtLeast(0)
                    } catch (e: Exception) {
                        // 周期非法: 月度窗口无重置时间
                    }
                }
                windows += QuotaWindow(
                    label = "Monthly",
                    used = usedPct,
                    remaining = Math.round((100.0 - usedPct) * 10) / 10.0,
                    total = planTotal,
                    unit = "$",
                    resetAt = resetAtIso,
                    resetInSec = resetIn,
                )
            }

            val result = QuotaResult(
                name = "Default",
                workspaceId = "commandcode", // commandcode 无 workspace 概念
                success = windows.isNotEmpty(),
                updatedAt = fmtIso(nowMs),
                windows = windows,
                plan = plan,
                periodStart = periodStart,
                periodEnd = periodEnd,
            )
            if (windows.isEmpty()) {
                // copy 携带错误信息
                return result.copy(error = "无法从 credits 响应解析额度数据")
            }
            return result
        }

        /** (used, cap, resetAt ms) -> 百分比窗口 (desktop _parse_window_percent parity)。 */
        private fun windowFrom(label: String, used: Double, cap: Double, resetMs: Long, nowMs: Long): QuotaWindow {
            val usedPct = if (cap > 0) (used / cap * 100.0).coerceIn(0.0, 100.0) else 0.0
            return QuotaWindow(
                label = label,
                used = usedPct,
                remaining = Math.round((100.0 - usedPct) * 10) / 10.0,
                total = cap,
                unit = "$",
                resetAt = fmtIso(if (resetMs > 0) resetMs else nowMs),
                resetInSec = ((resetMs / 1000) - nowMs / 1000).toInt().coerceAtLeast(0),
            )
        }

        /** 解析 /internal/usage 响应为 (records, nextCursor) (desktop parse_usage_response parity)。 */
        fun parseUsage(text: String): Pair<List<UsageRecord>, String?> {
            val data = try {
                json.parseToJsonElement(text).jsonObject
            } catch (e: Exception) {
                throw OpenCodeApiException("usage 响应不是合法 JSON")
            }
            val records = mutableListOf<UsageRecord>()
            val usages = data["usages"]
            if (usages is kotlinx.serialization.json.JsonArray) {
                for (item in usages) {
                    val o = item as? JsonObject ?: continue
                    val id = str(o, "id") ?: continue
                    val createdAtRaw = str(o, "createdAt") ?: ""
                    // created_at 无时区即丢弃: 防止入库成永不清理/永不匹配周期的僵尸行
                    val createdAt = normalizeCreatedAt(createdAtRaw) ?: continue
                    val meta = obj(o["meta"])
                    val model = str(meta, "model") ?: str(o, "model") ?: "unknown"
                    records += UsageRecord(
                        usgId = id,
                        createdAt = createdAt,
                        model = model,
                        provider = io.github.yphyphyph.gogauge.data.model.PROVIDER_COMMANDCODE,
                        inputTokens = intOr(num(o, "tokensIn")),
                        outputTokens = intOr(num(o, "tokensOut")),
                        reasoningTokens = 0,
                        cacheReadTokens = 0,
                        cacheWrite5mTokens = 0,
                        cacheWrite1hTokens = 0,
                        costRaw = 0,
                        keyId = "",
                        sessionId = "", // commandcode 无会话概念
                        plan = null,
                        costUsdOverride = doubleOr(num(meta, "totalCost")),
                    )
                }
            }
            val nextCursor = str(data, "nextCursor")
            return records to nextCursor
        }

        /** 校验并原样保留 ISO 时间串 (desktop _normalize_created_at parity)。 */
        fun normalizeCreatedAt(value: String): String? {
            if (value.isEmpty()) return null
            return try {
                Instant.parse(value.replace("Z", "+00:00"))
                value
            } catch (e: Exception) {
                null
            }
        }

        /** 解析 /internal/usage/charts 响应为聚合行列表 (desktop parse_charts_response parity)。 */
        fun parseCharts(text: String): List<UsageChartBucket> {
            val data = try {
                json.parseToJsonElement(text).jsonObject
            } catch (e: Exception) {
                throw OpenCodeApiException("charts 响应不是合法 JSON")
            }
            val rows = mutableListOf<UsageChartBucket>()
            val arr = data["data"]
            if (arr is kotlinx.serialization.json.JsonArray) {
                for (item in arr) {
                    val o = item as? JsonObject ?: continue
                    val bucket = str(o, "timeBucket") ?: continue
                    rows += UsageChartBucket(
                        model = str(o, "model") ?: "unknown",
                        provider = str(o, "provider") ?: "",
                        timeBucket = bucket,
                        requests = intOr(num(o, "requests")),
                        inputCost = doubleOr(num(o, "inputCost")),
                        outputCost = doubleOr(num(o, "outputCost")),
                        cacheCost = doubleOr(num(o, "cacheCost")),
                        totalCost = doubleOr(num(o, "totalCost")),
                        creditsTotal = doubleOr(num(o, "creditsTotal")),
                        tokensIn = intOr(num(o, "tokensIn")),
                        tokensOut = intOr(num(o, "tokensOut")),
                        tokensTotal = intOr(num(o, "tokensTotal")),
                        cacheReadTokens = intOr(num(o, "cacheReadInputTokens")),
                        cacheCreationTokens = intOr(num(o, "cacheCreationInputTokens")),
                    )
                }
            }
            return rows
        }

        private fun fmtIso(ms: Long): String =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'")
                .withZone(ZoneOffset.UTC)
                .format(Instant.ofEpochMilli(ms))
    }
}
