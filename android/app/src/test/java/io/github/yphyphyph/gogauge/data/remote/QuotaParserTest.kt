package io.github.yphyphyph.gogauge.data.remote

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

/**
 * /console/api/go/status 解析测试 — 夹具与桌面 tests/test_opencode_api.py 同源
 * (2026-09 控制台改版后的真实响应结构, 值已改写)。
 */
class QuotaParserTest {

    private val json = Json { ignoreUnknownKeys = true }

    private val goStatus = json.parseToJsonElement(
        """
        {
          "subscriberUserId": "acc_01KXDVHYS30679FFKQ113J8FWY",
          "product": "go",
          "useBalance": false,
          "access": {
            "startsAt": "2026-09-26T12:06:25.000Z",
            "endsAt": "2026-10-26T12:06:25.000Z",
            "cancelAtPeriodEnd": false,
            "meters": {
              "fiveHour": {
                "startsAt": "2026-09-26T12:27:01.804Z",
                "resetsAt": "2026-09-26T17:27:01.804Z",
                "limitMicroCents": "1200000000",
                "usedMicroCents": "7632295"
              },
              "week": {
                "startsAt": "2026-09-21T00:00:00.000Z",
                "resetsAt": "2026-09-28T00:00:00.000Z",
                "limitMicroCents": "3000000000",
                "usedMicroCents": "7632295"
              },
              "month": {"limitMicroCents": "6000000000", "usedMicroCents": "7632295"}
            }
          }
        }
        """.trimIndent()
    )

    private val nowMillis = Instant.parse("2026-09-26T12:56:25Z").toEpochMilli()

    @Test
    fun `parses three windows from string micro-cent values`() {
        val windows = QuotaParser.parseGoStatus(goStatus, nowMillis)
        assertEquals(3, windows.size)

        val rolling = windows[0]
        assertEquals("5h Rolling", rolling.label)
        // 7632295 / 1200000000 * 100 = 0.636… -> round2
        assertEquals(0.64, rolling.used, 0.001)
        assertEquals(99.36, rolling.remaining, 0.001)
        assertEquals(100.0, rolling.total, 0.001)
        assertEquals("%", rolling.unit)
        assertEquals("2026-09-26T17:27:01.804Z", rolling.resetAt)
        // 17:27:01.804Z - 12:56:25Z = 16236.804s -> 截断取整
        assertEquals(16236, rolling.resetInSec)

        val weekly = windows[1]
        assertEquals("Weekly", weekly.label)
        assertEquals(0.25, weekly.used, 0.001)  // 7632295 / 3000000000 * 100

        val monthly = windows[2]
        assertEquals("Monthly", monthly.label)
        assertEquals(0.13, monthly.used, 0.001)  // 7632295 / 6000000000 * 100
        // 月额度无 resetsAt: 重置时间取 access.endsAt
        assertEquals("2026-10-26T12:06:25Z", monthly.resetAt)
    }

    @Test
    fun `skips meters with zero or missing limit`() {
        val payload = json.parseToJsonElement(
            """
            {"access": {"meters": {
              "fiveHour": {"limitMicroCents": "0", "usedMicroCents": "10"},
              "week": {"limitMicroCents": "100", "usedMicroCents": "50"}
            }}}
            """.trimIndent()
        )
        val windows = QuotaParser.parseGoStatus(payload, nowMillis)
        assertEquals(1, windows.size)
        assertEquals("Weekly", windows[0].label)
        assertEquals(50.0, windows[0].used, 0.001)
        assertEquals(50.0, windows[0].remaining, 0.001)
    }

    @Test
    fun `clamps usage percent into 0-100`() {
        val payload = json.parseToJsonElement(
            """
            {"access": {"meters": {
              "fiveHour": {"limitMicroCents": "100", "usedMicroCents": "150"}
            }}}
            """.trimIndent()
        )
        val windows = QuotaParser.parseGoStatus(payload, nowMillis)
        assertEquals(1, windows.size)
        assertEquals(100.0, windows[0].used, 0.001)
        assertEquals(0.0, windows[0].remaining, 0.001)
    }

    @Test
    fun `malformed payloads yield empty list`() {
        assertTrue(QuotaParser.parseGoStatus(null, nowMillis).isEmpty())
        assertTrue(QuotaParser.parseGoStatus(json.parseToJsonElement("{}"), nowMillis).isEmpty())
        assertTrue(
            QuotaParser.parseGoStatus(json.parseToJsonElement("""{"access": {}}"""), nowMillis).isEmpty()
        )
        assertTrue(
            QuotaParser.parseGoStatus(json.parseToJsonElement("[]"), nowMillis).isEmpty()
        )
    }
}
