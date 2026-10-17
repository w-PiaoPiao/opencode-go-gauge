package io.github.yphyphyph.gogauge.ui.theme

import androidx.compose.ui.graphics.Color

// Claude 官方设计令牌 (light) — 象牙画布 / 暖白卡 / 发丝线三层表面
object Gg {
    val Bg = Color(0xFFF0EEE6)          // ivory canvas (claude.ai 应用的暖米底)
    val Card = Color(0xFFFAF9F5)        // 暖白卡 (比画布亮一档)
    val Tile = Color(0xFFEFE9DE)        // 卡内砖块 (比卡深一档)
    val TileStrong = Color(0xFFE8E0D2)  // 强调砖/分段容器/进度轨道
    val Border = Color(0xFFE6DFD8)      // hairline
    val Text = Color(0xFF141413)        // ink
    val Text2 = Color(0xFF6C6A64)       // muted
    val Primary = Color(0xFFC96442)     // 珊瑚(交互)
    val PrimarySoft = Color(0xFFF4E8E1)
    val Blue = Color(0xFF7B96B8)        // 雾蓝 (数据)
    val Green = Color(0xFF5DB872)       // success
    val Cyan = Color(0xFF5DB8A6)        // teal
    val Amber = Color(0xFFE8A55A)       // warning/amber
    val Red = Color(0xFFC64545)         // error
    val Slate = Color(0xFF87867F)
}

// 暗色主题 — 暖炭体系
object GgDark {
    val Bg = Color(0xFF1F1E1B)
    val Card = Color(0xFF252320)
    val Tile = Color(0xFF2C2A26)
    val TileStrong = Color(0xFF33302B)
    val Border = Color(0xFF3B3833)
    val Text = Color(0xFFFAF9F5)
    val Text2 = Color(0xFFA09D96)
    val Primary = Color(0xFFD97757)
    val PrimarySoft = Color(0xFF3A2C26)
    val Blue = Color(0xFF8FA9C7)
    val Green = Color(0xFF79C389)
    val Cyan = Color(0xFF79C7B5)
    val Amber = Color(0xFFEBB275)
    val Red = Color(0xFFD96A6A)
    val Slate = Color(0xFF8E8B82)
}

// 图表语义色 — 暖调克制系 (亮暗主题共用; 暗块上已足够对比)
object GgChart {
    val Input = Color(0xFF7B96B8)
    val Output = Color(0xFF7D8B6A)
    val Reasoning = Color(0xFF9A7AA0)
    val Cache = Color(0xFF5DB8A6)
    val Cost = Color(0xFFD4A27F)
    val Extra = Color(0xFFC96442)
}
