package io.github.yphyphyph.gogauge.ui.components

import org.junit.Assert.assertEquals
import org.junit.Test

/** 模型图标映射 — desktop app.js modelIcon (含 v1.0.3 hy 前缀修复) parity。 */
class ModelIconsTest {

    @Test
    fun exactBaseMatch() {
        assertEquals("deepseek", ModelIcons.resolve("deepseek-chat"))
        assertEquals("glm", ModelIcons.resolve("GLM-4.5"))
        assertEquals("kimi", ModelIcons.resolve("kimi-k2"))
        assertEquals("minimax", ModelIcons.resolve("MiniMax-Text-01"))
    }

    @Test
    fun aliasMuseMapsToMeta() {
        assertEquals("meta", ModelIcons.resolve("muse-1"))
        assertEquals("meta", ModelIcons.resolve("meta-llama-3"))
    }

    @Test
    fun hunyuanPrefixFallback() {
        // v1.0.3 修复: hy2/hy3 等非精确首段按 hy 前缀回退
        assertEquals("hy", ModelIcons.resolve("hy3"))
        assertEquals("hy", ModelIcons.resolve("hy2-preview"))
        assertEquals("hy", ModelIcons.resolve("HY-x"))
        assertEquals("hy", ModelIcons.resolve("hy"))
    }

    @Test
    fun unknownFallsBackToDeepseek() {
        assertEquals("deepseek", ModelIcons.resolve("gemma-2"))
        assertEquals("deepseek", ModelIcons.resolve(""))
    }

    @Test
    fun monochromeTrio() {
        assertEquals(true, ModelIcons.isMonochrome("gpt"))
        assertEquals(true, ModelIcons.isMonochrome("grok"))
        assertEquals(true, ModelIcons.isMonochrome("mimo"))
        assertEquals(false, ModelIcons.isMonochrome("deepseek"))
        assertEquals(false, ModelIcons.isMonochrome("hy"))
    }
}
