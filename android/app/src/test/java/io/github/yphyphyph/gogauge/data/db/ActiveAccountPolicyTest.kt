package io.github.yphyphyph.gogauge.data.db

import org.junit.Assert.assertEquals
import org.junit.Test

/** 活跃账号解析策略 — desktop db.get_active_account_id 决策逻辑 parity。 */
class ActiveAccountPolicyTest {

    private fun snap(vararg pairs: Pair<Int, Boolean>) = pairs.map {
        ActiveAccountPolicy.Snapshot(it.first, it.second)
    }

    @Test
    fun storedLoggedInKept() {
        val accounts = snap(1 to true, 2 to true)
        assertEquals(2, ActiveAccountPolicy.resolve(2, accounts))
    }

    @Test
    fun storedLoggedOutYieldsToMinLoggedIn() {
        val accounts = snap(1 to false, 3 to true, 5 to true)
        assertEquals(3, ActiveAccountPolicy.resolve(1, accounts))
    }

    @Test
    fun allLoggedOutKeepsStored() {
        val accounts = snap(1 to false, 2 to false)
        assertEquals(2, ActiveAccountPolicy.resolve(2, accounts))
    }

    @Test
    fun noStoredPrefersMinLoggedIn() {
        val accounts = snap(4 to false, 7 to true, 9 to true)
        assertEquals(7, ActiveAccountPolicy.resolve(null, accounts))
    }

    @Test
    fun missingStoredRowFallsBackToMinLoggedIn() {
        val accounts = snap(1 to true)
        assertEquals(1, ActiveAccountPolicy.resolve(99, accounts))
    }

    @Test
    fun nothingAtAllReturnsZero() {
        assertEquals(0, ActiveAccountPolicy.resolve(null, emptyList()))
    }

    @Test
    fun noStoredNoLoggedInUsesMinAnyId() {
        val accounts = snap(3 to false, 8 to false)
        assertEquals(3, ActiveAccountPolicy.resolve(null, accounts))
    }
}
