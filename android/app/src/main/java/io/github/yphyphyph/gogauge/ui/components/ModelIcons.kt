package io.github.yphyphyph.gogauge.ui.components

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import io.github.yphyphyph.gogauge.R

/**
 * 模型图标映射 — mirrors desktop app.js modelIcon (v1.0.3 含 hy 前缀回退修复).
 * resolve 为纯函数便于 JVM 单测; 渲染层按主题选择深色变体或动态着色。
 */
object ModelIcons {

    /** 模型名首段精确匹配表 (desktop app.js map parity)。 */
    private val MAP = mapOf(
        "deepseek" to "deepseek",
        "glm" to "glm",
        "gpt" to "gpt",
        "grok" to "grok",
        "kimi" to "kimi",
        "meta" to "meta",
        "mimo" to "mimo",
        "minimax" to "minimax",
        "muse" to "meta",
        "qwen" to "qwen",
        "hy" to "hy",
    )

    /**
     * 解析模型名 → 图标键。未命中精确匹配时 hy2/hy3 等混元系列按前缀回退到 hy,
     * 其余兜底 deepseek (desktop v1.0.3 语义)。
     */
    fun resolve(model: String): String {
        val s = model.trim().lowercase()
        val base = s.split("-").firstOrNull().orEmpty()
        return MAP[base] ?: if (base.startsWith("hy")) "hy" else "deepseek"
    }

    /** 单色图标 (SVG currentColor), 浅色主题需动态着色 — desktop 深色换 -color 变体同源。 */
    fun isMonochrome(key: String): Boolean = key == "gpt" || key == "grok" || key == "mimo"

    fun drawableRes(key: String, dark: Boolean): Int = when (key) {
        "deepseek" -> R.drawable.ic_model_deepseek
        "glm" -> R.drawable.ic_model_glm
        "gpt" -> if (dark) R.drawable.ic_model_gpt_color else R.drawable.ic_model_gpt
        "grok" -> if (dark) R.drawable.ic_model_grok_color else R.drawable.ic_model_grok
        "kimi" -> R.drawable.ic_model_kimi
        "meta" -> R.drawable.ic_model_meta
        "mimo" -> if (dark) R.drawable.ic_model_mimo_color else R.drawable.ic_model_mimo
        "minimax" -> R.drawable.ic_model_minimax
        "qwen" -> R.drawable.ic_model_qwen
        else -> R.drawable.ic_model_hy
    }
}

/** 16dp 模型图标 — 对应桌面端 <img src="icons/xx.svg" width=16>。 */
@Composable
fun ModelIcon(
    model: String,
    dark: Boolean,
    modifier: Modifier = Modifier,
    size: Dp = 16.dp,
    tint: Color = LocalContentColor.current,
) {
    val key = ModelIcons.resolve(model)
    val painter = painterResource(ModelIcons.drawableRes(key, dark))
    if (ModelIcons.isMonochrome(key)) {
        Icon(painter, contentDescription = model, modifier = modifier.size(size), tint = tint)
    } else {
        Image(painter, contentDescription = model, modifier = modifier.size(size))
    }
}
