package io.github.yphyphyph.gogauge.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class UsageParserTest {

    // Mirrors a server-fn response: mixed POST (space) and GET (no-space) record formats
    private val response = """
        window.__SERVER_DATA__ = {ok: true};
        const ${'$'}R = [];
        ${'$'}R[0] = {version: 1};
        ${'$'}R[1] = {id: "usg_abc123", timeCreated: ${'$'}R[2] = new Date("2025-08-01T10:00:00.000Z"), model: "deepseek-chat", provider: "deepseek", inputTokens: 1234, outputTokens: 567, reasoningTokens: 89, cacheReadTokens: 100, cacheWrite5mTokens: 50, cacheWrite1hTokens: 25, cost: 12345678, keyID: "key_1", sessionID: "ses_1", enrichment:${'$'}R[3]={plan:"lite"}};
        ${'$'}R[4] = {id:"usg_def456",timeCreated:${'$'}R[5]=new Date("2025-08-01T09:30:00.000Z"),model:"gpt-4o",provider:"openai",inputTokens:100,outputTokens:200,reasoningTokens:0,cacheReadTokens:0,cacheWrite5mTokens:0,cacheWrite1hTokens:0,cost:5000000,keyID:"key_2",sessionID:""};
        ${'$'}R[6] = {id: "usg_ghi789", timeCreated: ${'$'}R[7] = new Date("2025-08-01T08:00:00.000Z"), model: "glm-4", provider: "zhipu", inputTokens: null, outputTokens: 0, reasoningTokens: null, cacheReadTokens: 0, cacheWrite5mTokens: 0, cacheWrite1hTokens: 0, cost: 0, keyID: "", sessionID: ""};
    """.trimIndent()

    @Test
    fun `parses records in both GET and POST formats`() {
        val records = UsageParser.parseUsageResponse(response)
        assertEquals(3, records.size)

        val first = records[0]
        assertEquals("usg_abc123", first.usgId)
        assertEquals("2025-08-01T10:00:00.000Z", first.createdAt)
        assertEquals("deepseek-chat", first.model)
        assertEquals("deepseek", first.provider)
        assertEquals(1234, first.inputTokens)
        assertEquals(567, first.outputTokens)
        assertEquals(89, first.reasoningTokens)
        assertEquals(100, first.cacheReadTokens)
        assertEquals(50, first.cacheWrite5mTokens)
        assertEquals(25, first.cacheWrite1hTokens)
        assertEquals(12_345_678L, first.costRaw)
        assertEquals(0.12345678, first.costUsd, 1e-9)
        assertEquals("key_1", first.keyId)
        assertEquals("ses_1", first.sessionId)
        assertEquals("lite", first.plan)

        val second = records[1]
        assertEquals("usg_def456", second.usgId)
        assertEquals("gpt-4o", second.model)
        assertEquals(100, second.inputTokens)
        assertNull(second.plan) // no enrichment in this record

        val third = records[2]
        assertEquals("usg_ghi789", third.usgId)
        assertEquals(0, third.inputTokens) // null → 0 (desktop parity)
        assertEquals(0, third.reasoningTokens)
    }

    @Test
    fun `returns empty list for garbage input`() {
        assertTrue(UsageParser.parseUsageResponse("no records here").isEmpty())
    }

    @Test
    fun `skips records without timeCreated`() {
        val text = """
            const ${'$'}R = [];
            ${'$'}R[1] = {id: "usg_no_time", model: "x", inputTokens: 1, outputTokens: 1};
        """.trimIndent()
        assertTrue(UsageParser.parseUsageResponse(text).isEmpty())
    }
}
