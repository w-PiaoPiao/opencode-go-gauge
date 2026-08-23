package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Transaction
import io.github.yphyphyph.gogauge.data.model.AccountInfo
import io.github.yphyphyph.gogauge.data.model.SyncState
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.time.Instant

/**
 * Account / sync-state / active-account DAO — mirrors desktop db.py v2.0.0
 * (accounts 多行表 + usage_sync_state 按账号主键 + settings.payload.active_account_id).
 */
@Dao
abstract class SyncDao {

    private val json = Json { ignoreUnknownKeys = true }

    // ------------------------------------------------------------------
    // 账号行 (desktop db.py accounts 表访问)
    // ------------------------------------------------------------------

    @Query("SELECT * FROM accounts ORDER BY id ASC")
    abstract suspend fun listAccountRows(): List<AccountEntity>

    @Query("SELECT * FROM accounts WHERE id = :id")
    abstract suspend fun accountRowById(id: Int): AccountEntity?

    @Query("SELECT MIN(id) FROM accounts WHERE TRIM(token) != ''")
    abstract suspend fun minLoggedInId(): Int?

    @Query("SELECT MIN(id) FROM accounts")
    abstract suspend fun minAnyId(): Int?

    @Query("SELECT COUNT(*) FROM accounts")
    abstract suspend fun countAccountsRaw(): Int

    @Query("SELECT COUNT(*) FROM accounts WHERE TRIM(token) != ''")
    abstract suspend fun countLoggedInAccountsRaw(): Int

    /** desktop add_account 显式取 MAX(id)+1 作主键 (非 AUTOINCREMENT 语义, 保持 id 连续). */
    @Query("SELECT COALESCE(MAX(id), 0) + 1 FROM accounts")
    abstract suspend fun nextAccountId(): Int

    @Insert
    abstract suspend fun insertAccountRow(row: AccountEntity)

    @Query(
        "UPDATE accounts SET token = :token, workspace_id = :workspaceId," +
            " resolved_workspace_id = NULL, updated_at = :updatedAt WHERE id = :id"
    )
    abstract suspend fun updateCredential(id: Int, token: String, workspaceId: String, updatedAt: String)

    @Query(
        "UPDATE accounts SET workspace_id = :workspaceId, updated_at = :updatedAt WHERE id = :id"
    )
    abstract suspend fun updateWorkspaceHint(id: Int, workspaceId: String, updatedAt: String)

    @Query(
        "UPDATE accounts SET resolved_workspace_id = :workspaceId, updated_at = :updatedAt WHERE id = :id"
    )
    abstract suspend fun saveResolvedWorkspace(id: Int, workspaceId: String, updatedAt: String)

    @Query(
        "UPDATE accounts SET name = :name, updated_at = :updatedAt WHERE id = :id"
    )
    abstract suspend fun renameAccountRow(id: Int, name: String, updatedAt: String): Int

    @Query("UPDATE accounts SET token = '', resolved_workspace_id = NULL, updated_at = :updatedAt WHERE id = :id")
    abstract suspend fun clearToken(id: Int, updatedAt: String)

    @Query("DELETE FROM accounts WHERE id = :id")
    abstract suspend fun deleteAccountRow(id: Int)

    // ------------------------------------------------------------------
    // settings payload 底层读写 (active_account_id 与 key_names 等共用一行 JSON;
    // 与 SettingsDao 各自读改写, 键互不覆盖)
    // ------------------------------------------------------------------

    @Query("SELECT payload FROM settings WHERE id = 1")
    abstract suspend fun rawPayload(): String?

    @Query("UPDATE settings SET payload = :payload, updated_at = :updatedAt WHERE id = 1")
    abstract suspend fun writePayload(payload: String, updatedAt: String)

    private fun parsePayload(raw: String?): MutableMap<String, kotlinx.serialization.json.JsonElement> =
        try {
            json.parseToJsonElement(raw ?: "{}").jsonObject.toMutableMap()
        } catch (e: Exception) {
            mutableMapOf()
        }

    private suspend fun persistPayload(transform: (MutableMap<String, kotlinx.serialization.json.JsonElement>) -> Unit) {
        val data = parsePayload(rawPayload())
        transform(data)
        writePayload(kotlinx.serialization.json.JsonObject(data).toString(), Instant.now().toString())
    }

    suspend fun readStoredActiveId(): Int? =
        parsePayload(rawPayload())["active_account_id"]
            ?.let { (it as? JsonPrimitive)?.content?.toIntOrNull() }

    suspend fun writeStoredActiveId(accountId: Int) {
        persistPayload { it.put("active_account_id", JsonPrimitive(accountId)) }
    }

    suspend fun removeStoredActiveId() {
        persistPayload { it.remove("active_account_id") }
    }

    // ------------------------------------------------------------------
    // 活跃账号 (desktop db.get_active_account_id / set_active_account parity)
    // ------------------------------------------------------------------

    /**
     * 当前活跃账号 id; 无任何账号时返回 0.
     * 决策逻辑抽到 [ActiveAccountPolicy] (纯函数, JVM 单测覆盖);
     * 此处负责快照读取与结果回写.
     */
    @Transaction
    open suspend fun getActiveAccountId(): Int {
        val rows = listAccountRows()
        val stored = readStoredActiveId()
        val resolved = ActiveAccountPolicy.resolve(
            stored,
            rows.map { ActiveAccountPolicy.Snapshot(it.id, it.hasToken) },
        )
        // 偏好已登录账号的让位结果需要落库; 无变化时不写 (desktop 仅在切换时 persist)
        if (rows.isNotEmpty() && resolved != (stored ?: 0)) {
            when {
                resolved > 0 -> writeStoredActiveId(resolved)
                else -> removeStoredActiveId()
            }
        }
        return resolved
    }

    /** 切换活跃账号; 目标不存在返回 false (desktop db.set_active_account). */
    open suspend fun setActiveAccount(accountId: Int): Boolean {
        if (accountRowById(accountId) == null) return false
        writeStoredActiveId(accountId)
        return true
    }

    private suspend fun requireActiveId(): Int = getActiveAccountId()

    // ------------------------------------------------------------------
    // 账号摘要 / CRUD (desktop db.py parity)
    // ------------------------------------------------------------------

    private fun AccountEntity.toInfo() = AccountInfo(
        id = id,
        name = name,
        workspaceId = workspaceId,
        resolvedWorkspaceId = resolvedWorkspaceId,
        hasToken = hasToken,
    )

    /** 活跃账号摘要; 无账号返回 null (desktop get_account 空 dict 口径由仓库层转换). */
    suspend fun getAccount(): AccountInfo? = accountRowById(requireActiveId())?.toInfo()

    suspend fun listAccounts(): List<AccountInfo> = listAccountRows().map { it.toInfo() }

    suspend fun countAccounts(): Int = countAccountsRaw()

    suspend fun countLoggedInAccounts(): Int = countLoggedInAccountsRaw()

    /**
     * 添加新账号; 若已有完全相同的 token 则视为同一用户, 更新工作区提示后返回其 id
     * (desktop db.add_account).
     */
    @Transaction
    open suspend fun addAccount(token: String, workspaceHint: String = "", switch: Boolean = true): Int {
        val trimmed = token.trim()
        val hint = workspaceHint.trim()
        val now = Instant.now().toString()
        if (trimmed.isNotEmpty()) {
            val existing = listAccountRows().firstOrNull { it.token.trim() == trimmed }
            if (existing != null) {
                if (hint.isNotEmpty()) updateWorkspaceHint(existing.id, hint, now)
                if (switch) writeStoredActiveId(existing.id)
                return existing.id
            }
        }
        val newId = nextAccountId()
        insertAccountRow(
            AccountEntity(
                id = newId,
                name = hint.take(50).ifEmpty { "User $newId" },
                workspaceId = hint.ifEmpty { "Default" },
                token = trimmed,
                createdAt = now,
                updatedAt = now,
            ),
        )
        ensureStateRow(newId)
        if (switch) writeStoredActiveId(newId)
        return newId
    }

    /** 重命名; 名称去空白截断 50 字符, 空名失败 (desktop db.rename_account). */
    suspend fun renameAccount(accountId: Int, name: String): Boolean {
        val cleaned = name.trim().take(50)
        if (cleaned.isEmpty()) return false
        return renameAccountRow(accountId, cleaned, Instant.now().toString()) > 0
    }

    /**
     * 删除账号及其本地全部数据 (级联), 返回剩余账号数
     * (desktop db.delete_account: records+state+行一起删; 被删的是活跃位则回退最小 id, 无剩余则清键).
     */
    @Transaction
    open suspend fun deleteAccount(accountId: Int): Int {
        deleteRecordsForAccount(accountId)
        deleteSyncStateForAccount(accountId)
        deleteAccountRow(accountId)
        val remaining = countAccountsRaw()
        if (readStoredActiveId() == accountId) {
            val nxt = minAnyId()
            if (nxt != null) writeStoredActiveId(nxt) else removeStoredActiveId()
        }
        return remaining
    }

    /**
     * 退出登录当前活跃账号: 清除其凭证与本地缓存数据 (保留账号行便于重新登录)
     * (desktop db.clear_account).
     */
    @Transaction
    open suspend fun clearAccount() {
        val aid = requireActiveId()
        if (aid == 0) return
        val now = Instant.now().toString()
        deleteRecordsForAccount(aid)
        clearToken(aid, now)
        ensureStateRow(aid)
        resetSyncStateForAccount(aid)
    }

    /** 重新登录语义: 更新活跃账号凭证并重置其增量游标 (desktop db.save_token). */
    @Transaction
    open suspend fun saveToken(token: String, workspaceId: String) {
        val aid = requireActiveId()
        if (aid == 0) return
        updateCredential(aid, token.trim(), workspaceId.trim().ifEmpty { "Default" }, Instant.now().toString())
        ensureStateRow(aid)
        resetCursorForAccount(aid)
    }

    // ------------------------------------------------------------------
    // 同步状态 (desktop db.py usage_sync_state 访问, 按账号)
    // ------------------------------------------------------------------

    @Query("SELECT * FROM usage_sync_state WHERE account_id = :accountId")
    abstract suspend fun syncRow(accountId: Int): SyncStateEntity?

    @Query("INSERT OR IGNORE INTO usage_sync_state (account_id, deepest_page_fetched) VALUES (:accountId, -1)")
    abstract suspend fun ensureStateRow(accountId: Int)

    @Query(
        """
        UPDATE usage_sync_state
        SET last_sync_at = :at, last_sync_status = :status, last_sync_error = :error,
            last_inserted_count = last_inserted_count + :inserted
        WHERE account_id = :accountId
        """
    )
    abstract suspend fun bumpSyncState(accountId: Int, status: String, error: String?, inserted: Int, at: String)

    @Query(
        """
        UPDATE usage_sync_state
        SET last_sync_status = NULL, last_sync_error = NULL, last_inserted_count = 0,
            deepest_page_fetched = -1, total_records = 0,
            oldest_record_at = NULL, newest_record_at = NULL
        WHERE account_id = :accountId
        """
    )
    abstract suspend fun resetSyncStateForAccount(accountId: Int)

    @Query("UPDATE usage_sync_state SET deepest_page_fetched = -1 WHERE account_id = :accountId")
    abstract suspend fun resetCursorForAccount(accountId: Int)

    @Query("DELETE FROM usage_sync_state WHERE account_id = :accountId")
    abstract suspend fun deleteSyncStateForAccount(accountId: Int)

    @Query(
        "SELECT COUNT(*) AS count, MIN(created_at) AS oldest, MAX(created_at) AS newest" +
            " FROM usage_records WHERE account_id = :accountId"
    )
    abstract suspend fun recordBoundsRaw(accountId: Int): UsageDao.BoundsRow

    @Query(
        "UPDATE usage_sync_state SET total_records = :total, oldest_record_at = :oldest," +
            " newest_record_at = :newest WHERE account_id = :accountId"
    )
    abstract suspend fun setSyncTotals(accountId: Int, total: Int, oldest: String?, newest: String?)

    /** Persist sync result and refresh totals — mirrors db.update_sync_state + _refresh_sync_totals (按账号). */
    @Transaction
    open suspend fun updateSyncStateAndTotals(accountId: Int, status: String, error: String?, inserted: Int) {
        val now = Instant.now().toString()
        ensureStateRow(accountId)
        bumpSyncState(accountId, status, error, inserted, now)
        val b = recordBoundsRaw(accountId)
        setSyncTotals(accountId, b.count, b.oldest, b.newest)
    }

    suspend fun getSyncState(): SyncState = getSyncStateFor(getActiveAccountId())

    suspend fun getSyncStateFor(accountId: Int): SyncState {
        val row = syncRow(accountId) ?: return SyncState()
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

    /** 按账号删除其全部用量记录 (级联删除用; Room DAO 允许跨表 @Query)。 */
    @Query("DELETE FROM usage_records WHERE account_id = :accountId")
    abstract suspend fun deleteRecordsForAccount(accountId: Int)

    // ------------------------------------------------------------------
    // 凭据快捷读取 (活跃账号; desktop db.get_token/get_workspace_hint parity)
    // ------------------------------------------------------------------

    suspend fun getToken(): String = accountRowById(getActiveAccountId())?.token?.trim() ?: ""

    suspend fun getTokenFor(accountId: Int): String = accountRowById(accountId)?.token?.trim() ?: ""

    suspend fun getWorkspaceHint(): String {
        val row = accountRowById(getActiveAccountId()) ?: return "Default"
        return row.resolvedWorkspaceId ?: row.workspaceId.ifBlank { "Default" }
    }

    suspend fun getWorkspaceHintFor(accountId: Int): String {
        val row = accountRowById(accountId) ?: return "Default"
        return row.resolvedWorkspaceId ?: row.workspaceId.ifBlank { "Default" }
    }
}
