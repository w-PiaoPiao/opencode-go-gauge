package io.github.yphyphyph.gogauge.ui.theme

import androidx.compose.ui.graphics.Color

// GoGauge brand palette — ported from desktop style.css (light)
object Gg {
    val Bg = Color(0xFFF7F6F4)
    val Card = Color(0xFFFFFFFF)
    val Border = Color(0xFFEAE7F2)
    val Text = Color(0xFF221F33)
    val Text2 = Color(0xFF5F5B73)
    val Text3 = Color(0xFF938EA8)
    val Primary = Color(0xFF7C5CF6)
    val PrimaryStrong = Color(0xFF6A46EA)
    val PrimarySoft = Color(0xFFF2EEFE)
    val Blue = Color(0xFF4F8EF7)
    val Green = Color(0xFF22C55E)
    val Purple = Color(0xFFA78BFA)
    val Cyan = Color(0xFF06B6D4)
    val Amber = Color(0xFFD97706)
    val Red = Color(0xFFEF4444)
    val Muted = Color(0xFFF1EFF6)
    val Grid = Color(0xFFEFEDF5)
    val Slate = Color(0xFF64748B)
}

// Dark theme palette — ported from desktop style.css html[data-theme="dark"]
object GgDark {
    val Bg = Color(0xFF14121A)
    val Card = Color(0xFF1D1A26)
    val Border = Color(0xFF2E2A3D)
    val Text = Color(0xFFE9E6F5)
    val Text2 = Color(0xFFA8A3C0)
    val Text3 = Color(0xFF6F6A87)
    val Primary = Color(0xFF9D7CF8)
    val PrimaryStrong = Color(0xFF8B6CF6)
    val PrimarySoft = Color(0xFF272040)
    val Blue = Color(0xFF4F8EF7)
    val Green = Color(0xFF22C55E)
    val Purple = Color(0xFFA78BFA)
    val Cyan = Color(0xFF06B6D4)
    val Amber = Color(0xFFD97706)
    val Red = Color(0xFFEF4444)
    val Muted = Color(0xFF232030)
    val Grid = Color(0xFF29253A)
    val Slate = Color(0xFF64748B)
}

// Chart / semantic accent colors (shared by both themes, same as desktop COLOR map)
object GgChart {
    val Input = Color(0xFF4F8EF7)
    val Output = Color(0xFF22C55E)
    val Reasoning = Color(0xFFA78BFA)
    val Cache = Color(0xFF06B6D4)
    val Cost = Color(0xFFD97706)
    val Extra = Color(0xFFEC4899)
}
