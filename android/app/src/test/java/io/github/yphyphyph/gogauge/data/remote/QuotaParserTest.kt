package io.github.yphyphyph.gogauge.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class QuotaParserTest {

    // Mirrors real dashboard HTML: JS literals with both field orders
    private val html = """
        <html><body>
        <script>
        window.__APP_DATA__ = {};
        var ${'$'}R = [];
        // usagePercent first
        rollingUsage: ${'$'}R[12] = {usagePercent: 34.5, resetInSec: 43199, isActive: true, something: "x"};
        // resetInSec first
        weeklyUsage: ${'$'}R[13] = {resetInSec: 518400, usagePercent: 12.3, isActive: true};
        // usagePercent first, negative guard value
        monthlyUsage: ${'$'}R[14] = {usagePercent: 105.7, resetInSec: 15552000, isActive: true};
        </script>
        </body></html>
    """.trimIndent()

    @Test
    fun `parses all three quota windows with both field orders`() {
        val windows = QuotaParser.parseQuotaHtml(html, nowMillis = 1_752_000_000_000L)
        assertEquals(3, windows.size)

        val rolling = windows[0]
        assertEquals("5h Rolling", rolling.label)
        assertEquals(34.5, rolling.used, 0.001)
        assertEquals(65.5, rolling.remaining, 0.001)
        assertEquals(43199, rolling.resetInSec)

        val weekly = windows[1]
        assertEquals("Weekly", weekly.label)
        assertEquals(12.3, weekly.used, 0.001)
        assertEquals(518400, weekly.resetInSec)

        val monthly = windows[2]
        assertEquals("Monthly", monthly.label)
    }

    @Test
    fun `clamps usage percent to 0-100`() {
        val windows = QuotaParser.parseQuotaHtml(html)
        val monthly = windows.first { it.label == "Monthly" }
        assertEquals(100.0, monthly.used, 0.001)
        assertEquals(0.0, monthly.remaining, 0.001)
    }

    @Test
    fun `returns empty list when no quota markers`() {
        assertTrue(QuotaParser.parseQuotaHtml("<html><body>nothing here</body></html>").isEmpty())
    }

    @Test
    fun `resetAt is now plus resetInSec`() {
        val now = 1_752_000_000_000L // 2025-07-16T...
        val windows = QuotaParser.parseQuotaHtml(html, nowMillis = now)
        val rolling = windows[0]
        val expected = java.time.Instant.ofEpochMilli(now).plusSeconds(43199)
        assertEquals(expected.toString(), rolling.resetAt)
    }
}
