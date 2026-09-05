package io.github.yphyphyph.gogauge.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/** Mirrors desktop db.py `accounts` multi-row table (snake_case column names). */
@Entity(tableName = "accounts")
data class AccountEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    @ColumnInfo(name = "name") val name: String = "Default",
    @ColumnInfo(name = "workspace_id") val workspaceId: String = "Default",
    @ColumnInfo(name = "resolved_workspace_id") val resolvedWorkspaceId: String? = null,
    @ColumnInfo(name = "token") val token: String = "",
    @ColumnInfo(name = "provider") val provider: String = "opencode",
    @ColumnInfo(name = "created_at") val createdAt: String = "",
    @ColumnInfo(name = "updated_at") val updatedAt: String = "",
) {
    /** desktop db._account_dict has_token 口径: TRIM(token) != '' */
    val hasToken: Boolean get() = token.trim().isNotEmpty()
}

/**
 * Mirrors desktop db.py `usage_charts` table — commandcode 全计费周期的
 * (模型 × 5min 时间桶) 聚合快照, 统计口径以此为准 (明细接口仅 24h/100 条)。
 * tokens_in 已包含缓存读 (tokensTotal = tokensIn + tokensOut)。
 */
@Entity(
    tableName = "usage_charts",
    primaryKeys = ["account_id", "model", "time_bucket"],
    indices = [
        Index(value = ["account_id", "time_bucket"], name = "idx_charts_account_time"),
    ],
)
data class UsageChartEntity(
    @ColumnInfo(name = "account_id") val accountId: Int,
    @ColumnInfo(name = "model") val model: String,
    @ColumnInfo(name = "provider") val provider: String? = null,
    @ColumnInfo(name = "time_bucket") val timeBucket: String,  // UTC "yyyy-MM-dd HH:mm:ss"
    @ColumnInfo(name = "requests") val requests: Int = 0,
    @ColumnInfo(name = "input_cost") val inputCost: Double = 0.0,
    @ColumnInfo(name = "output_cost") val outputCost: Double = 0.0,
    @ColumnInfo(name = "cache_cost") val cacheCost: Double = 0.0,
    @ColumnInfo(name = "total_cost") val totalCost: Double = 0.0,
    @ColumnInfo(name = "credits_total") val creditsTotal: Double = 0.0,
    @ColumnInfo(name = "tokens_in") val tokensIn: Int = 0,
    @ColumnInfo(name = "tokens_out") val tokensOut: Int = 0,
    @ColumnInfo(name = "tokens_total") val tokensTotal: Int = 0,
    @ColumnInfo(name = "cache_read_tokens") val cacheReadTokens: Int = 0,
    @ColumnInfo(name = "cache_creation_tokens") val cacheCreationTokens: Int = 0,
    @ColumnInfo(name = "synced_at") val syncedAt: String = "",
)

/** Mirrors desktop db.py v2.0.0 `usage_records` table — records belong to an account. */
@Entity(
    tableName = "usage_records",
    indices = [
        Index(value = ["created_at"], name = "idx_usage_time"),
        Index(value = ["session_id"], name = "idx_usage_session"),
        Index(value = ["account_id", "created_at"], name = "idx_usage_account_time"),
    ],
)
data class UsageRecordEntity(
    @PrimaryKey @ColumnInfo(name = "usg_id") val usgId: String,
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "model") val model: String,
    @ColumnInfo(name = "provider") val provider: String? = null,
    @ColumnInfo(name = "input_tokens") val inputTokens: Int,
    @ColumnInfo(name = "output_tokens") val outputTokens: Int,
    @ColumnInfo(name = "reasoning_tokens") val reasoningTokens: Int = 0,
    @ColumnInfo(name = "cache_read_tokens") val cacheReadTokens: Int = 0,
    @ColumnInfo(name = "cache_write_5m_tokens") val cacheWrite5mTokens: Int = 0,
    @ColumnInfo(name = "cache_write_1h_tokens") val cacheWrite1hTokens: Int = 0,
    @ColumnInfo(name = "cost_raw") val costRaw: Long = 0,
    @ColumnInfo(name = "cost_usd") val costUsd: Double = 0.0,
    @ColumnInfo(name = "key_id") val keyId: String? = null,
    @ColumnInfo(name = "session_id") val sessionId: String? = null,
    @ColumnInfo(name = "plan") val plan: String? = null,
    @ColumnInfo(name = "synced_at") val syncedAt: String = "",
    // desktop db.insert_usage_records: 记录归属账号 (v2.0.0 多用户维度列)
    @ColumnInfo(name = "account_id") val accountId: Int = 1,
)

/**
 * Mirrors desktop db.py v2.0.0 `usage_sync_state` table — one cursor row per account.
 * 主键从单行 id 改为 account_id (迁移 3 无损重建).
 */
@Entity(tableName = "usage_sync_state")
data class SyncStateEntity(
    @PrimaryKey @ColumnInfo(name = "account_id") val accountId: Int,
    @ColumnInfo(name = "last_sync_at") val lastSyncAt: String? = null,
    @ColumnInfo(name = "last_sync_status") val lastSyncStatus: String? = null,
    @ColumnInfo(name = "last_sync_error") val lastSyncError: String? = null,
    @ColumnInfo(name = "last_inserted_count") val lastInsertedCount: Int = 0,
    @ColumnInfo(name = "deepest_page_fetched") val deepestPageFetched: Int = -1,
    @ColumnInfo(name = "total_records") val totalRecords: Int = 0,
    @ColumnInfo(name = "oldest_record_at") val oldestRecordAt: String? = null,
    @ColumnInfo(name = "newest_record_at") val newestRecordAt: String? = null,
)

/** Mirrors desktop db.py `settings` table (JSON payload row). */
@Entity(tableName = "settings")
data class SettingsEntity(
    @PrimaryKey val id: Int = 1,
    @ColumnInfo(name = "payload") val payload: String = "{}",
    @ColumnInfo(name = "updated_at") val updatedAt: String = "",
)
