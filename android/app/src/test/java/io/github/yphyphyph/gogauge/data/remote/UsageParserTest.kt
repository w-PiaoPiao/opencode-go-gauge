package io.github.yphyphyph.gogauge.data.remote

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

/**
 * /console/api/request-logs 解析测试 — 夹具与桌面 tests/test_opencode_api.py 同源
 * (2026-09 控制台改版后的真实响应结构, 值已改写)。
 */
class UsageParserTest {

    private val json = Json { ignoreUnknownKeys = true }

    private val requestLogs = json.parseToJsonElement(
        """
        {
          "items": [
            {
              "id": "c34d84dc-d6e8-4d09-8a48-55d636a772d2",
              "requestID": "c34d84dc-d6e8-4d09-8a48-55d636a772d2",
              "workspaceID": "wrk_01KXDVHZMY578NZ300DTR7WYE8",
              "startedAt": 1790427391447,
              "finishedAt": 1790427392447,
              "outcome": "succeeded",
              "category": "inference",
              "protocol": "openai-chat",
              "product": "go",
              "sessionID": "1e2a34d4-f057-45bd-8f0f-21c05481fa00",
              "serviceAPIKeyID": "sk_01M3ESWS60E7J9STN1MHFQPYRM",
              "requestedModel": "deepseek-v4.1-flash",
              "model": "deepseek-v4.1-flash",
              "provider": "opencode",
              "inputTokens": 2480,
              "outputTokens": 1273,
              "reasoningTokens": 629,
              "cacheReadTokens": 130944,
              "cacheWriteTokens": 0,
              "cost": 0.00152863
            },
            {
              "id": "287fbd65-5f3c-405a-b16b-4501c49c064d",
              "startedAt": 1790427749237,
              "category": "api",
              "serviceAPIKeyID": null,
              "model": null,
              "inputTokens": 0,
              "cost": 0
            },
            {
              "id": "9d42a3c0-20b4-4354-9bfe-82d7a2f36058",
              "startedAt": 1790427740000,
              "category": "inference",
              "product": "go",
              "sessionID": "",
              "serviceAPIKeyID": "sk_01M3ESWS60E7J9STN1MHFQPYRM",
              "model": "kimi-k3",
              "provider": "opencode",
              "inputTokens": 100,
              "outputTokens": 20,
              "reasoningTokens": 0,
              "cacheReadTokens": 0,
              "cacheWriteTokens": 4096,
              "cost": "0.0000387"
            }
          ],
          "nextCursor": "{\"v\":2,\"kind\":\"list\",\"until\":1790427382939}",
          "until": 1790427382939,
          "retentionDays": 30
        }
        """.trimIndent()
    )

    @Test
    fun `keeps only inference records and maps fields`() {
        val page = UsageParser.parseRequestLogs(requestLogs)
        assertEquals(2, page.records.size)

        val first = page.records[0]
        assertEquals("c34d84dc-d6e8-4d09-8a48-55d636a772d2", first.usgId)
        // startedAt 毫秒 -> ISO ...Z
        assertEquals(Instant.ofEpochMilli(1790427391447).toString(), first.createdAt)
        assertEquals("deepseek-v4.1-flash", first.model)
        assertEquals("opencode", first.provider)
        assertEquals(2480, first.inputTokens)
        assertEquals(1273, first.outputTokens)
        assertEquals(629, first.reasoningTokens)
        assertEquals(130944, first.cacheReadTokens)
        // 新接口单一 cacheWriteTokens 记入 5m 列, 1h 恒 0
        assertEquals(0, first.cacheWrite5mTokens)
        assertEquals(0, first.cacheWrite1hTokens)
        // cost 为 USD 浮点 -> 1e-8 单位
        assertEquals(152_863L, first.costRaw)
        assertEquals("sk_01M3ESWS60E7J9STN1MHFQPYRM", first.keyId)
        assertEquals("1e2a34d4-f057-45bd-8f0f-21c05481fa00", first.sessionId)
        assertEquals("go", first.plan)

        // api 类 (控制台自身调用) 已被过滤: 第二条应是 kimi-k3
        val second = page.records[1]
        assertEquals("kimi-k3", second.model)
        assertEquals(4096, second.cacheWrite5mTokens)
        assertEquals(0, second.cacheWrite1hTokens)
        assertEquals(3870L, second.costRaw)  // 字符串数字 cost 也兼容
    }

    @Test
    fun `exposes cursor and retention`() {
        val page = UsageParser.parseRequestLogs(requestLogs)
        assertEquals("{\"v\":2,\"kind\":\"list\",\"until\":1790427382939}", page.nextCursor)
        assertEquals(30, page.retentionDays)
    }

    @Test
    fun `malformed payloads yield empty page`() {
        val empty = UsageParser.parseRequestLogs(null)
        assertTrue(empty.records.isEmpty())
        assertNull(empty.nextCursor)
        assertNull(empty.retentionDays)

        assertTrue(UsageParser.parseRequestLogs(json.parseToJsonElement("{}")).records.isEmpty())
        assertTrue(UsageParser.parseRequestLogs(json.parseToJsonElement("[]")).records.isEmpty())
        assertTrue(
            UsageParser.parseRequestLogs(json.parseToJsonElement("""{"items": []}""")).records.isEmpty()
        )
    }

    @Test
    fun `skips records without id or startedAt`() {
        val payload = json.parseToJsonElement(
            """
            {"items": [
              {"id": "x", "category": "inference", "startedAt": 0},
              {"category": "inference", "startedAt": 1790427391447},
              {"id": "ok", "category": "inference", "startedAt": 1790427391447}
            ]}
            """.trimIndent()
        )
        val page = UsageParser.parseRequestLogs(payload)
        assertEquals(1, page.records.size)
        assertEquals("ok", page.records[0].usgId)
    }
}
