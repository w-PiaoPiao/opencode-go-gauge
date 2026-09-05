package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.PROVIDER_COMMANDCODE
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Command Code GOAT 响应解析器测试 — 实测样例移植自 desktop tests/test_commandcode_api.py。
 */
class CommandCodeApiTest {

    // 实测响应样例 (2026-09-02, individual-goat)
    private val creditsBody = """
        {
          "credits": {
            "belowThreshold": false,
            "creditThreshold": 0,
            "monthlyCredits": 67.8799891707,
            "purchasedCredits": 0,
            "premiumMonthlyCredits": 0,
            "opensourceMonthlyCredits": 67.8799891707
          },
          "windowLimits": {
            "limited": true,
            "exceeded": null,
            "fiveHour": {"used": 0.0648735266, "cap": 14, "exceeded": false, "resetAt": 1788366123616},
            "weekly": {"used": 2.1200108293, "cap": 35, "exceeded": false, "resetAt": 1788916513968}
          }
        }
    """.trimIndent()

    private val subscriptionBody = """
        {
          "success": true,
          "data": {
            "id": "sub_1UB2cQDSZgxV3MJKrOXJKlf4",
            "status": "active",
            "userId": "bcd0bc0a-a65a-44dc-9420-ce0acf751ff2",
            "orgId": null,
            "currentPeriodStart": "2026-09-02T01:03:43.000Z",
            "currentPeriodEnd": "2026-10-02T01:03:43.000Z",
            "planId": "individual-goat",
            "pendingPhase": null
          }
        }
    """.trimIndent()

    private val usageBody = """
        {
          "usages": [
            {
              "id": "86c1fefd-2010-46b3-9a69-a65284e99600",
              "createdAt": "2026-09-02T11:31:04.353Z",
              "tokensIn": "69691", "tokensOut": "1437", "durationTotal": "14976",
              "status": "completed", "message": null,
              "meta": {"totalCost": 0.002048632, "inputCost": 0.0006325,
                       "outputCost": 0.00094842, "cacheCost": 0.000467712,
                       "model": "deepseek/deepseek-v4-flash",
                       "traceId": "00b590953f609f5554888ffbe17f0aff"},
              "type": "api", "mode": "api"
            }
          ],
          "nextCursor": "cursor-abc"
        }
    """.trimIndent()

    private val nowMs = 1788339000000L

    @Test
    fun `three windows and plan`() {
        val q = CommandCodeApi.parseQuota(creditsBody, subscriptionBody, nowMs)
        assertEquals(true, q.success)
        assertEquals("individual-goat", q.plan)
        assertEquals("2026-09-02T01:03:43.000Z", q.periodStart)
        assertEquals("2026-10-02T01:03:43.000Z", q.periodEnd)
        assertEquals(3, q.windows.size)

        val (five, weekly, monthly) = q.windows
        assertEquals("5h Rolling", five.label)
        assertEquals(14.0, five.total, 1e-9)
        assertEquals("$", five.unit)
        assertEquals(0.0648735266 / 14 * 100, five.used, 1e-9)
        assertTrue(five.resetInSec >= 0)

        assertEquals("Weekly", weekly.label)
        assertEquals(35.0, weekly.total, 1e-9)

        assertEquals("Monthly", monthly.label)
        assertEquals(70.0, monthly.total, 1e-9)
        // 已用 = 池 70 - 剩余 67.88
        assertEquals(100.0 * (70.0 - 67.8799891707) / 70.0, monthly.used, 1e-6)
    }

    @Test
    fun `no subscription - monthly from plan-independent remaining`() {
        val q = CommandCodeApi.parseQuota(creditsBody, null, nowMs)
        assertTrue(q.success)
        assertNull(q.plan)
        assertNull(q.periodStart)
        // 无计划额度表可用: monthly 总额回退为剩余 credits (>0) → used=0
        val monthly = q.windows.last()
        assertEquals("Monthly", monthly.label)
        assertEquals(67.8799891707, monthly.total, 1e-9)
        assertEquals(0.0, monthly.used, 1e-9)
    }

    @Test
    fun `missing windows - failure`() {
        val q = CommandCodeApi.parseQuota("""{"credits": {}}""", null, nowMs)
        assertEquals(false, q.success)
        assertNotNull(q.error)
    }

    @Test
    fun `usage records and cursor`() {
        val (records, cursor) = CommandCodeApi.parseUsage(usageBody)
        assertEquals(1, records.size)
        assertEquals("86c1fefd-2010-46b3-9a69-a65284e99600", records[0].usgId)
        assertEquals("2026-09-02T11:31:04.353Z", records[0].createdAt)
        assertEquals("deepseek/deepseek-v4-flash", records[0].model)
        assertEquals(PROVIDER_COMMANDCODE, records[0].provider)
        assertEquals(69691, records[0].inputTokens)
        assertEquals(1437, records[0].outputTokens)
        assertEquals(0.002048632, records[0].costUsd, 1e-12)
        assertEquals(0L, records[0].costRaw)
        assertEquals("cursor-abc", cursor)
    }

    @Test
    fun `usage empty and invalid json`() {
        assertEquals(0, CommandCodeApi.parseUsage("""{"usages": []}""").first.size)
        try {
            CommandCodeApi.parseUsage("not-json")
            throw AssertionError("expected OpenCodeApiException")
        } catch (e: OpenCodeApiException) {
            // expected
        }
    }

    @Test
    fun `usage drops records without valid timestamp`() {
        val body = """{"usages": [{"id": "u1", "createdAt": "", "tokensIn": "1"}]}"""
        assertEquals(0, CommandCodeApi.parseUsage(body).first.size)
    }

    @Test
    fun `charts parse`() {
        val body = """
            {"data": [
              {"model": "deepseek/deepseek-v4-flash", "provider": "deepseek",
               "timeBucket": "2026-09-02 10:35:00", "requests": 3,
               "totalCost": 0.012, "inputCost": 0.005, "outputCost": 0.006,
               "cacheCost": 0.001, "creditsTotal": 0.012,
               "tokensIn": 1000, "tokensOut": 200, "tokensTotal": 1200,
               "cacheReadInputTokens": 600, "cacheCreationInputTokens": 40}
            ]}
        """.trimIndent()
        val rows = CommandCodeApi.parseCharts(body)
        assertEquals(1, rows.size)
        val r = rows[0]
        assertEquals("deepseek/deepseek-v4-flash", r.model)
        assertEquals("2026-09-02 10:35:00", r.timeBucket)
        assertEquals(3, r.requests)
        assertEquals(1000, r.tokensIn)
        assertEquals(600, r.cacheReadTokens)
        assertEquals(0.012, r.totalCost, 1e-12)
    }

    @Test
    fun `cookie header normalization`() {
        val cookieName = CommandCodeApi.AUTH_COOKIE_NAME
        assertEquals("$cookieName=v1", CommandCodeApi.buildCookieHeader("v1"))
        assertEquals("$cookieName=v1", CommandCodeApi.buildCookieHeader("a=1; $cookieName=v1; b=2"))
        assertEquals("$cookieName=v1", CommandCodeApi.buildCookieHeader("Cookie: $cookieName=v1"))
    }
}
