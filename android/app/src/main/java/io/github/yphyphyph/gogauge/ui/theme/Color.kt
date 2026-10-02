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
    val Text3 = Color(0xFF8E8B82)       // muted-soft
    val Primary = Color(0xFFC96442)     // 珊瑚(交互)
    val PrimaryStrong = Color(0xFFA9583E)
    val PrimarySoft = Color(0xFFF4E8E1)
    val Blue = Color(0xFF7B96B8)        // 雾蓝 (数据)
    val Green = Color(0xFF5DB872)       // success
    val Purple = Color(0xFF9A7AA0)      // fig
    val Cyan = Color(0xFF5DB8A6)        // teal
    val Amber = Color(0xFFE8A55A)       // warning/amber
    val Red = Color(0xFFC64545)         // error
    val Muted = Color(0xFFEFE9DE)
    val Grid = Color(0xFFE6DFD8)
    val Slate = Color(0xFF87867F)
    // 暗色数据块 (备用; 暗色主题下与卡片同系)
    val DarkBlock = Color(0xFF1F1E1B)
    val DarkBlockBorder = Color(0xFF181715)
    val DarkGrid = Color(0xFF3B3833)
    val OnDark = Color(0xFFFAF9F5)
    val OnDarkSoft = Color(0xFFA09D96)
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
    val Text3 = Color(0xFF6E6B64)
    val Primary = Color(0xFFD97757)
    val PrimaryStrong = Color(0xFFE08D6E)
    val PrimarySoft = Color(0xFF3A2C26)
    val Blue = Color(0xFF8FA9C7)
    val Green = Color(0xFF79C389)
    val Purple = Color(0xFFB295B8)
    val Cyan = Color(0xFF79C7B5)
    val Amber = Color(0xFFEBB275)
    val Red = Color(0xFFD96A6A)
    val Muted = Color(0xFF2C2A26)
    val Grid = Color(0xFF3B3833)
    val Slate = Color(0xFF8E8B82)
    // 暗色主题下数据块与卡片同系, 略深一层保持"暗块"节奏
    val DarkBlock = Color(0xFF181715)
    val DarkBlockBorder = Color(0xFF141413)
    val DarkGrid = Color(0xFF33302B)
    val OnDark = Color(0xFFFAF9F5)
    val OnDarkSoft = Color(0xFFA09D96)
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
