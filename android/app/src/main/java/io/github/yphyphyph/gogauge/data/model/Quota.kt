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

/** Quota fetch result — mirrors opencode_api.QuotaResult (desktop). */
@Serializable
data class QuotaResult(
    val name: String,
    val workspaceId: String,
    val success: Boolean,
    val updatedAt: String,
    val windows: List<QuotaWindow> = emptyList(),
    val error: String? = null,
)
