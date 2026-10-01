package io.github.yphyphyph.gogauge.data.remote

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * OpenCodeApi.buildCookieHeader 归一化测试 — 用例与桌面
 * tests/test_opencode_api.py 的 test_cookie_* 一一对应。
 */
class OpenCodeApiCookieTest {

    private val api = OpenCodeApi()

    @Test
    fun `raw value gets new session cookie name`() {
        assertEquals("__Host-console_session=st_0019e474-abcd", api.buildCookieHeader("st_0019e474-abcd"))
    }

    @Test
    fun `session cookie full pair passthrough`() {
        assertEquals("__Host-console_session=st_abc", api.buildCookieHeader("__Host-console_session=st_abc"))
    }

    @Test
    fun `legacy auth pair passthrough`() {
        assertEquals("auth=Fe26.2**deadbeef", api.buildCookieHeader("auth=Fe26.2**deadbeef"))
    }

    @Test
    fun `strips cookie prefix and picks session segment`() {
        assertEquals(
            "__Host-console_session=st_xyz",
            api.buildCookieHeader("Cookie: foo=1; __Host-console_session=st_xyz; bar=2"),
        )
    }

    @Test
    fun `empty token yields empty header`() {
        assertEquals("", api.buildCookieHeader(""))
        assertEquals("", api.buildCookieHeader("   "))
        assertEquals("", api.buildCookieHeader("Cookie:"))
    }
}
