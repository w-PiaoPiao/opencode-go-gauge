package io.github.yphyphyph.gogauge.data.model

import org.junit.Assert.assertEquals
import org.junit.Test

/** 新账号默认命名 — desktop db.add_account 命名规则 parity。 */
class AccountNamingTest {

    @Test
    fun `opencode with workspace hint names by hint`() {
        assertEquals("wrk_abc123", accountDisplayName(PROVIDER_OPENCODE, "wrk_abc123", 3))
    }

    @Test
    fun `opencode hint truncated to 50`() {
        val long = "x".repeat(60)
        assertEquals(50, accountDisplayName(PROVIDER_OPENCODE, long, 1).length)
    }

    @Test
    fun `commandcode names GOAT N`() {
        assertEquals("GOAT 7", accountDisplayName(PROVIDER_COMMANDCODE, "", 7))
        // GOAT 不用 workspace 提示命名 (无 workspace 概念)
        assertEquals("GOAT 7", accountDisplayName(PROVIDER_COMMANDCODE, "wrk_x", 7))
    }

    @Test
    fun `opencode without hint names User N`() {
        assertEquals("User 5", accountDisplayName(PROVIDER_OPENCODE, "", 5))
    }
}
