package io.github.yphyphyph.gogauge.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Instant

class IsoTimeTest {

    @Test
    fun parsesUtcZulu() {
        assertEquals(
            Instant.parse("2026-09-02T11:31:04.353Z"),
            parseIsoInstant("2026-09-02T11:31:04.353Z"),
        )
        assertEquals(
            Instant.parse("2026-09-02T11:31:04Z"),
            parseIsoInstant("2026-09-02T11:31:04Z"),
        )
    }

    /** Android 13 及以下 Instant.parse 拒绝 "+00:00" (JDK-8166138): 本函数必须兜住。 */
    @Test
    fun parsesExplicitOffsets() {
        assertEquals(
            Instant.parse("2026-09-02T11:31:04.353Z"),
            parseIsoInstant("2026-09-02T11:31:04.353+00:00"),
        )
        assertEquals(
            Instant.parse("2026-09-02T03:31:04Z"),
            parseIsoInstant("2026-09-02T11:31:04+08:00"),
        )
    }

    @Test
    fun rejectsMissingTimezoneAndGarbage() {
        assertNull(parseIsoInstant("2026-09-02T11:31:04.353"))
        assertNull(parseIsoInstant("2026-09-02 11:31:04"))
        assertNull(parseIsoInstant("not-a-date"))
        assertNull(parseIsoInstant(""))
        assertNull(parseIsoInstant("   "))
        assertNull(parseIsoInstant(null))
    }
}
