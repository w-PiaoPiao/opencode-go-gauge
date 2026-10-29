package io.github.yphyphyph.gogauge.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Gg.Primary,
    onPrimary = Color.White,
    primaryContainer = Gg.PrimarySoft,
    onPrimaryContainer = Gg.Text,
    secondary = Gg.Blue,
    onSecondary = Color.White,
    tertiary = Gg.Green,
    onTertiary = Color.White,
    background = Gg.Bg,
    onBackground = Gg.Text,
    surface = Gg.Card,
    onSurface = Gg.Text,
    surfaceVariant = Gg.Tile,
    onSurfaceVariant = Gg.Text2,
    surfaceContainerHighest = Gg.TileStrong,
    outline = Gg.Border,
    outlineVariant = Gg.Border,
    error = Gg.Red,
    onError = Color.White,
    errorContainer = Color(0xFFF7E9E4),
    onErrorContainer = Gg.Red,
)

private val DarkColors = darkColorScheme(
    primary = GgDark.Primary,
    onPrimary = Color(0xFF1F1E1B),
    primaryContainer = GgDark.PrimarySoft,
    onPrimaryContainer = GgDark.Text,
    secondary = GgDark.Blue,
    onSecondary = Color(0xFF1F1E1B),
    tertiary = GgDark.Green,
    onTertiary = Color(0xFF1F1E1B),
    background = GgDark.Bg,
    onBackground = GgDark.Text,
    surface = GgDark.Card,
    onSurface = GgDark.Text,
    surfaceVariant = GgDark.Tile,
    onSurfaceVariant = GgDark.Text2,
    surfaceContainerHighest = GgDark.TileStrong,
    outline = GgDark.Border,
    outlineVariant = GgDark.Border,
    error = GgDark.Red,
    onError = Color(0xFF1F1E1B),
    errorContainer = Color(0xFF3D2624),
    onErrorContainer = GgDark.Red,
)

/** 热力图档 1..4 配色 (档 0 取 surfaceVariant): 亮暗各一套, 由 GoGaugeTheme 注入.
 *  ColorScheme 的语义槽位不够放 4 个热力档, 单开一个 CompositionLocal 比塞进
 *  secondaryContainer 之类的槽位清楚. */
val LocalHeatRamp = staticCompositionLocalOf { Gg.Heat }

@Composable
fun GoGaugeTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = Typography,
    ) {
        CompositionLocalProvider(
            LocalHeatRamp provides if (darkTheme) GgDark.Heat else Gg.Heat,
            content = content,
        )
    }
}
