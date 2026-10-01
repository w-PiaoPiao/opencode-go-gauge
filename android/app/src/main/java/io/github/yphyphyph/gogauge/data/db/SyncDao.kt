package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Transaction
import io.github.yphyphyph.gogauge.data.model.AccountInfo
import io.github.yphyphyph.gogauge.data.model.PROVIDER_COMMANDCODE
import io.github.yphyphyph.gogauge.data.model.PROVIDER_OPENCODE
import io.github.yphyphyph.gogauge.data.model.SyncState
import io.github.yphyphyph.gogauge.data.model.accountDisplayName
import kotlinx.coroutines.sync.withLock
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
    //
    // token 以 Keystore 加密形态落库 (见 TokenCipher): 所有对外方法给出/接收明文,
    // 加解密在此层完成. SQL 层的 TRIM(token) != '' 判定对密文同样成立 (密文非空)。
    // ------------------------------------------------------------------

    /** 原始行 (token 为存储形态) — 仅本类包装方法使用。 */
    @Query("SELECT * FROM accounts ORDER BY id ASC")
    abstract suspend fun listAccountRowsRaw(): List<AccountEntity>

    @Query("SELECT * FROM accounts WHERE id = :id")
    abstract suspend fun accountRowByIdRaw(id: Int): AccountEntity?

    /** 账号行 (token 已解密)。 */
    suspend fun listAccountRows(): List<AccountEntity> =
        listAccountRowsRaw().map { it.copy(token = TokenCipher.decrypt(it.token)) }

    suspend fun accountRowById(id: Int): AccountEntity? =
        accountRowByIdRaw(id)?.let { it.copy(token = TokenCipher.decrypt(it.token)) }

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
    abstract suspend fun insertAccountRowRaw(row: AccountEntity)

    /** 写入前加密 token; 空串 (未登录占位) 原样落库。 */
    suspend fun insertAccountRow(row: AccountEntity) =
        insertAccountRowRaw(row.copy(token = TokenCipher.encrypt(row.token)))

    @Query(
        "UPDATE accounts SET token = :token, workspace_id = :workspaceId," +
            " resolved_workspace_id = NULL, provider = :provider, updated_at = :updatedAt WHERE id = :id"
    )
    abstract suspend fun updateCredentialRaw(
        id: Int,
        token: String,
        workspaceId: String,
        provider: String,
        updatedAt: String,
    )

    /** 更新凭证 (token 加密后落库)。 */
    suspend fun updateCredential(
        id: Int,
        token: String,
        workspaceId: String,
        provider: String,
        updatedAt: String,
    ) = updateCredentialRaw(id, TokenCipher.encrypt(token.trim()), workspaceId, provider, updatedAt)

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
        PayloadLock.mutex.withLock {
            val data = parsePayload(rawPayload())
            transform(data)
            writePayload(kotlinx.serialization.json.JsonObject(data).toString(), Instant.now().toString())
        }
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
    /**
     * 当前活跃账号 id; 无任何账号时返回 0.
     * 决策逻辑抽到 [ActiveAccountPolicy] (纯函数, JVM 单测覆盖);
     * 此处负责快照读取与结果回写.
     *
     * 注意这里**不能**加 @Transaction: 写回走 [persistPayload] (PayloadLock) ——
     * 事务持写连接后再取 Mutex, 会与 SettingsDao "先取锁再写库" 的路径反向锁序
     * 互等。快照不原子可接受: resolve 是收敛的, 下次调用会再修正。
     */
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
        provider = provider,
    )

    /** 活跃账号摘要; 无账号返回 null (desktop get_account 空 dict 口径由仓库层转换). */
    suspend fun getAccount(): AccountInfo? = accountRowById(requireActiveId())?.toInfo()

    suspend fun listAccounts(): List<AccountInfo> = listAccountRows().map { it.toInfo() }

    suspend fun countAccounts(): Int = countAccountsRaw()

    suspend fun countLoggedInAccounts(): Int = countLoggedInAccountsRaw()

    /**
     * 添加新账号; 若已有同一 provider 的相同 token 则视为同一用户, 更新工作区提示后返回其 id
     * (desktop db.add_account: 按 (provider, token) 去重; GOAT 账号命名 GOAT N)。
     *
     * 账号行写入在事务内, 活跃位回写在事务外经 PayloadLock 完成 (锁序约定见
     * [getActiveAccountId]); 账号行写入中途失败时的活跃位偏差由下次 resolve 自愈。
     */
    suspend fun addAccount(
        token: String,
        workspaceHint: String = "",
        switch: Boolean = true,
        provider: String = PROVIDER_OPENCODE,
    ): Int {
        val id = addAccountData(token.trim(), workspaceHint.trim(), provider)
        if (switch) writeStoredActiveId(id)
        return id
    }

    @Transaction
    open suspend fun addAccountData(
        token: String,
        hint: String,
        provider: String,
    ): Int {
        val now = Instant.now().toString()
        if (token.isNotEmpty()) {
            val existing = listAccountRows()
                .firstOrNull { it.provider == provider && it.token.trim() == token }
            if (existing != null) {
                // workspace 提示仅对 opencode 有意义 (desktop parity)
                if (hint.isNotEmpty() && provider == PROVIDER_OPENCODE) {
                    updateWorkspaceHint(existing.id, hint, now)
                }
                return existing.id
            }
        }
        val newId = nextAccountId()
        insertAccountRow(
            AccountEntity(
                id = newId,
                name = accountDisplayName(provider, hint, newId),
                workspaceId = hint.ifEmpty { "Default" },
                token = token,
                provider = provider,
                createdAt = now,
                updatedAt = now,
            ),
        )
        ensureStateRow(newId)
        return newId
    }

    /** 重命名; 名称去空白截断 50 字符, 空名失败 (desktop db.rename_account). */
    suspend fun renameAccount(accountId: Int, name: String): Boolean {
        val cleaned = name.trim().take(50)
        if (cleaned.isEmpty()) return false
        return renameAccountRow(accountId, cleaned, Instant.now().toString()) > 0
    }

    /**
     * 删除账号及其本地全部数据 (级联), 返回剩余账号数 (desktop db.delete_account:
     * records+charts+state+行一起删; 被删的是活跃位则回退最小 id, 并清理该账号
     * 残留的周期/月度重置键)。
     *
     * 账号 id 是 MAX(id)+1 分配, 删末位后再加账号会复用 id —— 周期键必须清掉,
     * 否则新账号「本月」会读到已删账号的计费周期。
     *
     * 数据删除在事务内; payload 处理 (活跃位回退 + 周期键清理) 在事务外经
     * PayloadLock 完成 —— 锁序约定见 [getActiveAccountId]。
     */
    suspend fun deleteAccount(accountId: Int): Int {
        val remaining = deleteAccountData(accountId)
        val nextId = minAnyId()
        persistPayload { data ->
            data.remove("period_start:$accountId")
            data.remove("period_end:$accountId")
            data.remove("monthly_reset:$accountId")
            val active = (data["active_account_id"] as? JsonPrimitive)?.content?.toIntOrNull()
            if (active == accountId) {
                if (nextId != null) {
                    data["active_account_id"] = JsonPrimitive(nextId)
                } else {
                    data.remove("active_account_id")
                }
            }
        }
        return remaining
    }

    @Transaction
    open suspend fun deleteAccountData(accountId: Int): Int {
        deleteRecordsForAccount(accountId)
        // charts 聚合也必须清: 否则 chartsReady() 仍非空, 重新添加同 id 账号后
        // 仪表盘会继续用上一个计费周期的陈旧聚合值
        deleteChartsForAccount(accountId)
        deleteSyncStateForAccount(accountId)
        deleteAccountRow(accountId)
        return countAccountsRaw()
    }

    /**
     * 退出登录当前活跃账号: 清除其凭证与本地缓存数据 (保留账号行便于重新登录)
     * (desktop db.clear_account).
     */
    suspend fun clearAccount() {
        val aid = requireActiveId()  // 事务外: 依赖 PayloadLock 写回活跃位
        if (aid == 0) return
        clearAccountData(aid)
    }

    @Transaction
    open suspend fun clearAccountData(aid: Int) {
        val now = Instant.now().toString()
        deleteRecordsForAccount(aid)
        deleteChartsForAccount(aid)  // 同 deleteAccount: 防止登出后残留聚合值
        clearToken(aid, now)
        ensureStateRow(aid)
        resetSyncStateForAccount(aid)
    }

    /** 重新登录语义: 更新活跃账号凭证与 provider, 并重置其增量游标 (desktop db.save_token). */
    suspend fun saveToken(token: String, workspaceId: String, provider: String = PROVIDER_OPENCODE) {
        val aid = requireActiveId()  // 事务外: 依赖 PayloadLock 写回活跃位
        if (aid == 0) return
        saveTokenData(aid, token, workspaceId, provider)
    }

    @Transaction
    open suspend fun saveTokenData(aid: Int, token: String, workspaceId: String, provider: String) {
        updateCredential(aid, token.trim(), workspaceId.trim().ifEmpty { "Default" }, provider, Instant.now().toString())
        ensureStateRow(aid)
        resetCursorForAccount(aid)
    }

    /** 读取账号的 provider; 账号不存在回退 opencode (desktop db.get_account_provider parity)。 */
    suspend fun getAccountProvider(accountId: Int): String =
        accountRowById(accountId)?.provider?.takeIf { it.isNotBlank() } ?: PROVIDER_OPENCODE

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

    /** usage_charts 聚合行按账号清除 (登出/删除账号时调用, 见 deleteAccount 说明). */
    @Query("DELETE FROM usage_charts WHERE account_id = :accountId")
    abstract suspend fun deleteChartsForAccount(accountId: Int)

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
