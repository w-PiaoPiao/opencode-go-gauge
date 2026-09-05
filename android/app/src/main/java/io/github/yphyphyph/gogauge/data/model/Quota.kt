package io.github.yphyphyph.gogauge.data.model

import kotlinx.serialization.Serializable

/** Quota window — mirrors opencode_api.QuotaWindow (desktop). */
@Serializable
data class QuotaWindow(
    val label: String,
    val used: Double,          // percent 0-100
    val remaining: Double,     // percent
    val total: Double,
    val unit: String,
    val resetAt: String,       // ISO
    val resetInSec: Int,
)

/** Quota fetch result — mirrors opencode_api/commandcode_api QuotaResult (desktop). */
@Serializable
data class QuotaResult(
    val name: String,
    val workspaceId: String,
    val success: Boolean,
    val updatedAt: String,
    val windows: List<QuotaWindow> = emptyList(),
    val error: String? = null,
    // commandcode 附加字段 (desktop commandcode_api.QuotaResult parity)
    val plan: String? = null,
    val periodStart: String? = null,   // ISO, 订阅计费周期起点
    val periodEnd: String? = null,     // ISO, 订阅计费周期终点 (= 月度窗口重置)
)
