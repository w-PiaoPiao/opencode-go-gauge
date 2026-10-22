package io.github.yphyphyph.gogauge.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * UpdateApi 纯函数 — 统一 release (同一 release 含全平台资产) 与旧式
 * v*-android tag 并存的兼容逻辑, 与 desktop updater.py 逐条对齐.
 */
class UpdateApiTest {

    @Test
    fun `parse version with letter suffix and platform tail`() {
        assertEquals(listOf(2, 2, 1, 2), UpdateApi.parseVersion("v2.2.1b"))
        assertEquals(listOf(2, 2, 1, 2), UpdateApi.parseVersion("v2.2.1b-android"))
        assertEquals(listOf(2, 2, 1, 0), UpdateApi.parseVersion("2.2.1"))
        assertNull(UpdateApi.parseVersion("nightly"))
        assertNull(UpdateApi.parseVersion("v2.2"))
    }

    @Test
    fun `legacy and unified tag detection`() {
        assertTrue(UpdateApi.isPlatformTag("v2.2.1d-android"))
        assertFalse(UpdateApi.isPlatformTag("v2.2.1d"))
        assertTrue(UpdateApi.isUnifiedTag("v2.2.1d"))
        assertTrue(UpdateApi.isUnifiedTag("v2.2.1b"))
        assertFalse(UpdateApi.isUnifiedTag("v2.2.1d-android"))
        assertFalse(UpdateApi.isUnifiedTag("v2.2.1d-macos"))
        assertFalse(UpdateApi.isUnifiedTag("v2.2.1d-harmony"))
        assertFalse(UpdateApi.isUnifiedTag("latest"))
    }

    @Test
    fun `release applies only when android asset exists`() {
        // 旧式 tag 直接认 (历史 release 可能还没资产/只有单资产)
        assertTrue(UpdateApi.releaseApplies("v2.2.1d-android", emptyList()))
        // 统一 release 必须真的带 APK
        assertTrue(
            UpdateApi.releaseApplies(
                "v2.2.1d",
                listOf("GoGauge-v2.2.1d-windows.exe", "GoGauge-v2.2.1d-android.apk"),
            ),
        )
        // 只发桌面的统一 release 不能误报
        assertFalse(
            UpdateApi.releaseApplies(
                "v2.2.1d",
                listOf("GoGauge-v2.2.1d-windows.exe", "GoGauge-v2.2.1d-macos-arm64.zip"),
            ),
        )
        // 其它平台后缀 tag / 非法 tag 不算
        assertFalse(UpdateApi.releaseApplies("v2.2.1d-macos", listOf("GoGauge-v2.2.1d-android.apk")))
        assertFalse(UpdateApi.releaseApplies("nightly", listOf("GoGauge-nightly.apk")))
    }

    @Test
    fun `pick apk prefers android suffix`() {
        assertEquals(
            "GoGauge-v2.2.1d-android.apk",
            UpdateApi.pickAssetName(
                listOf("GoGauge-v2.2.1d-macos-arm64.zip", "GoGauge-v2.2.1d-android.apk", "other.apk"),
            ),
        )
        assertEquals("legacy.apk", UpdateApi.pickAssetName(listOf("legacy.apk")))
        assertNull(UpdateApi.pickAssetName(listOf("GoGauge-v2.2.1d-windows.exe", " ")))
        assertNull(UpdateApi.pickAssetName(emptyList()))
    }

    @Test
    fun `version comparison`() {
        assertTrue(UpdateApi.isNewer(listOf(2, 2, 1, 1), listOf(2, 2, 1, 0)))
        assertTrue(UpdateApi.isNewer(listOf(2, 2, 2, 0), listOf(2, 2, 1, 26)))
        assertFalse(UpdateApi.isNewer(listOf(2, 2, 1, 0), listOf(2, 2, 1, 0)))
        assertFalse(UpdateApi.isNewer(listOf(2, 2, 0, 0), listOf(2, 2, 1, 0)))
    }
}
