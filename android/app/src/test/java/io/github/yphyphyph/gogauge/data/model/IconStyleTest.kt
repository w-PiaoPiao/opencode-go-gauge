package io.github.yphyphyph.gogauge.data.model

import org.junit.Assert.assertEquals
import org.junit.Test

/** 图标风格跨端契约 (settings key `icon_style`: blue / terracotta) 容错 — 非法/缺失值回落 blue。 */
class IconStyleTest {

    @Test
    fun `contract values are kept verbatim`() {
        assertEquals("blue", IconStyle.normalize(IconStyle.BLUE))
        assertEquals("terracotta", IconStyle.normalize(IconStyle.TERRACOTTA))
    }

    @Test
    fun `dirty and missing values fall back to blue`() {
        assertEquals("blue", IconStyle.normalize(null))
        assertEquals("blue", IconStyle.normalize(""))
        assertEquals("blue", IconStyle.normalize("warm"))
        assertEquals("blue", IconStyle.normalize("Blue"))
        assertEquals("blue", IconStyle.normalize("TERRACOTTA"))
        assertEquals("blue", IconStyle.normalize(" terracotta "))
    }

    @Test
    fun `defaults are blue`() {
        assertEquals("blue", IconStyle.DEFAULT)
        assertEquals("blue", AppSettings().iconStyle)
    }
}
