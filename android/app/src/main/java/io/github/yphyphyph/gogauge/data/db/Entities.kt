package io.github.yphyphyph.gogauge.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/** Mirrors desktop db.py `account` table (snake_case column names). */
@Entity(tableName = "account")
data class AccountEntity(
    @PrimaryKey val id: Int = 1,
    @ColumnInfo(name = "name") val name: String = "Default",
    @ColumnInfo(name = "workspace_id") val workspaceId: String = "Default",
    @ColumnInfo(name = "resolved_workspace_id") val resolvedWorkspaceId: String? = null,
    @ColumnInfo(name = "token") val token: String = "",
    @ColumnInfo(name = "created_at") val createdAt: String = "",
    @ColumnInfo(name = "updated_at") val updatedAt: String = "",
)

/** Mirrors desktop db.py `usage_records` table (snake_case column names). */
@Entity(
    tableName = "usage_records",
    indices = [
        Index(value = ["created_at"], name = "idx_usage_time"),
        Index(value = ["session_id"], name = "idx_usage_session"),
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
    @ColumnInfo(name = "cost_raw") val costRaw: Int = 0,
    @ColumnInfo(name = "cost_usd") val costUsd: Double = 0.0,
    @ColumnInfo(name = "key_id") val keyId: String? = null,
    @ColumnInfo(name = "session_id") val sessionId: String? = null,
    @ColumnInfo(name = "plan") val plan: String? = null,
    @ColumnInfo(name = "synced_at") val syncedAt: String = "",
)

/** Mirrors desktop db.py `usage_sync_state` table (snake_case column names). */
@Entity(tableName = "usage_sync_state")
data class SyncStateEntity(
    @PrimaryKey val id: Int = 1,
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
