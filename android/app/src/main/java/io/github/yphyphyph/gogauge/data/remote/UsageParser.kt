package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.UsagePage
import io.github.yphyphyph.gogauge.data.model.UsageRecord
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.time.Instant

/**
 * request-logs 解析 — 1:1 port of opencode_api.py parse_request_logs (desktop, 控制台改版后).
 *
 * ``GET /console/api/request-logs`` 的 items[] 仅 category=="inference" 计入用量
 * (api 类是控制台自身接口调用); ``cost`` 为 USD 浮点, 还原为 1e-8 单位存 cost_raw;
 * 新接口不再区分 5m/1h 缓存写入, 统一记入缓存写入列 (合计口径不变)。
 * 旧 /_server server-fn 响应解析已随改版下线。
 */
object UsageParser {

    private const val CATEGORY_INFERENCE = "inference"

    private fun JsonElement?.asLong(default: Long = 0L): Long {
        val text = (this as? JsonPrimitive)?.content ?: return default
        if (text.isEmpty() || text == "null") return default
        return text.toDoubleOrNull()?.toLong() ?: default
    }

    private fun JsonElement?.asDouble(default: Double = 0.0): Double {
        val text = (this as? JsonPrimitive)?.content ?: return default
        if (text.isEmpty() || text == "null") return default
        return text.toDoubleOrNull() ?: default
    }

    private fun JsonElement?.asText(): String {
        val text = (this as? JsonPrimitive)?.content ?: return ""
        return if (text == "null") "" else text
    }

    /** 毫秒时间戳 -> ISO ``...Z``; 非法值返回空串。 */
    private fun isoFromMs(ms: Long): String {
        if (ms <= 0) return ""
        return try {
            Instant.ofEpochMilli(ms).toString()
        } catch (e: Exception) {
            ""
        }
    }

    private fun recordFromItem(item: JsonObject): UsageRecord? {
        val usgId = item["id"].asText().trim()
        val createdAt = isoFromMs(item["startedAt"].asLong())
        if (usgId.isEmpty() || createdAt.isEmpty()) return null
        val cacheWrite = item["cacheWriteTokens"].asLong().toInt()
        return UsageRecord(
            usgId = usgId,
            createdAt = createdAt,
            model = item["model"].asText().trim(),
            provider = item["provider"].asText().trim(),
            inputTokens = item["inputTokens"].asLong().toInt(),
            outputTokens = item["outputTokens"].asLong().toInt(),
            reasoningTokens = item["reasoningTokens"].asLong().toInt(),
            cacheReadTokens = item["cacheReadTokens"].asLong().toInt(),
            // 新接口不再区分 5m/1h 缓存写入, 统一记入 5m 列 (合计口径不变)
            cacheWrite5mTokens = cacheWrite,
            cacheWrite1hTokens = 0,
            costRaw = Math.round(item["cost"].asDouble() * 100_000_000.0),
            keyId = item["serviceAPIKeyID"].asText().trim(),
            sessionId = item["sessionID"].asText().trim(),
            plan = item["product"].asText().trim().ifEmpty { null },
        )
    }

    /**
     * Parse one ``/console/api/request-logs`` response into a page of usage records.
     * 只保留 inference 类请求; nextCursor 供续翻, retentionDays 为服务端保留窗口。
     */
    fun parseRequestLogs(payload: JsonElement?): UsagePage {
        val obj = payload as? JsonObject ?: return UsagePage()
        val records = mutableListOf<UsageRecord>()
        val items = obj["items"] as? JsonArray
        if (items != null) {
            for (element in items) {
                val item = element as? JsonObject ?: continue
                if (item["category"].asText().trim().lowercase() != CATEGORY_INFERENCE) {
                    continue  // 控制台自身接口调用, 不计入用量
                }
                recordFromItem(item)?.let { records += it }
            }
        }
        val cursor = obj["nextCursor"].asText().trim().ifEmpty { null }
        val retention = (obj["retentionDays"] as? JsonPrimitive)?.content?.toDoubleOrNull()?.toInt()
        return UsagePage(records = records, nextCursor = cursor, retentionDays = retention)
    }
}
