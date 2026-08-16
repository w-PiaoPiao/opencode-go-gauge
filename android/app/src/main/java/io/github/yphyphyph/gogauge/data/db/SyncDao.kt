package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Transaction
import io.github.yphyphyph.gogauge.data.model.AccountInfo
import io.github.yphyphyph.gogauge.data.model.SyncState
import java.time.Instant

/** Account + sync-state DAO — mirrors desktop db.py account & usage_sync_state access. */
@Dao
abstract class SyncDao {

    @Query("SELECT * FROM account WHERE id = 1")
    abstract suspend fun accountRow(): AccountEntity?

    @Query(
        "UPDATE account SET token = :token, workspace_id = :workspaceId, resolved_workspace_id = NULL," +
            " updated_at = :updatedAt WHERE id = 1"
    )
    abstract suspend fun saveToken(token: String, workspaceId: String, updatedAt: String)

    @Query("UPDATE account SET resolved_workspace_id = :workspaceId, updated_at = :updatedAt WHERE id = 1")
    abstract suspend fun saveResolvedWorkspace(workspaceId: String, updatedAt: String)

    @Query("UPDATE account SET token = '', resolved_workspace_id = NULL, updated_at = :updatedAt WHERE id = 1")
    abstract suspend fun clearToken(updatedAt: String)

    suspend fun getAccount(): AccountInfo {
        val row = accountRow()
        return AccountInfo(
            name = row?.name ?: "Default",
            workspaceId = row?.workspaceId ?: "Default",
            resolvedWorkspaceId = row?.resolvedWorkspaceId,
            hasToken = !(row?.token?.isBlank() ?: true),
        )
    }

    suspend fun getToken(): String = accountRow()?.token?.trim() ?: ""

    suspend fun getWorkspaceHint(): String {
        val row = accountRow() ?: return "Default"
        return row.resolvedWorkspaceId ?: row.workspaceId.ifBlank { "Default" }
    }

    // ------------------------------------------------------------------
    // Sync state
    // ------------------------------------------------------------------

    @Query("SELECT * FROM usage_sync_state WHERE id = 1")
    abstract suspend fun syncRow(): SyncStateEntity?

    @Query(
        """
        UPDATE usage_sync_state
        SET last_sync_at = :at, last_sync_status = :status, last_sync_error = :error,
            last_inserted_count = last_inserted_count + :inserted
        WHERE id = 1
        """
    )
    abstract suspend fun updateSyncState(status: String, error: String?, inserted: Int, at: String)

    @Query(
        """
        UPDATE usage_sync_state
        SET last_sync_at = :at, last_sync_status = :status, last_sync_error = :error,
            last_inserted_count = :inserted, deepest_page_fetched = -1, total_records = 0,
            oldest_record_at = NULL, newest_record_at = NULL
        WHERE id = 1
        """
    )
    abstract suspend fun resetSyncState(at: String, status: String?, error: String?, inserted: Int)

    @Query("SELECT COUNT(*) AS count, MIN(created_at) AS oldest, MAX(created_at) AS newest FROM usage_records")
    abstract suspend fun recordBoundsRaw(): UsageDao.BoundsRow

    @Query(
        "UPDATE usage_sync_state SET total_records = :total, oldest_record_at = :oldest," +
            " newest_record_at = :newest WHERE id = 1"
    )
    abstract suspend fun setSyncTotals(total: Int, oldest: String?, newest: String?)

    /** Persist sync result and refresh totals — mirrors db.update_sync_state + _refresh_sync_totals. */
    @Transaction
    open suspend fun updateSyncStateAndTotals(status: String, error: String?, inserted: Int) {
        val now = Instant.now().toString()
        updateSyncState(status, error, inserted, now)
        val b = recordBoundsRaw()
        setSyncTotals(b.count, b.oldest, b.newest)
    }

    /** Full reset on logout — mirrors db.clear_account. */
    @Transaction
    open suspend fun clearAccount() {
        val now = Instant.now().toString()
        deleteAllRecords()
        clearToken(now)
        resetSyncState(now, null, null, 0)
    }

    @Query("DELETE FROM usage_records")
    abstract suspend fun deleteAllRecords()

    suspend fun getSyncState(): SyncState {
        val row = syncRow() ?: return SyncState()
        return SyncState(
            lastSyncAt = row.lastSyncAt,
            lastSyncStatus = row.lastSyncStatus,
            lastSyncError = row.lastSyncError,
            lastInsertedCount = row.lastInsertedCount,
            deepestPageFetched = row.deepestPageFetched,
            totalRecords = row.totalRecords,
            oldestRecordAt = row.oldestRecordAt,
            newestRecordAt = row.newestRecordAt,
        )
    }
}
