package io.github.yphyphyph.gogauge.data.backup

import android.content.Context
import android.net.Uri
import io.github.yphyphyph.gogauge.data.db.AppDatabase
import io.github.yphyphyph.gogauge.data.db.UsageRecordEntity
import io.github.yphyphyph.gogauge.data.model.PROVIDER_OPENCODE
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import java.io.BufferedReader
import java.io.InputStreamReader
import java.time.Instant
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream

/**
 * 导出/导入 (v2.2.0b) — SAF Uri 写读, 不需要存储权限。
 *
 * - CSV: usage_records 明细流式分页导出 (表格软件可直接打开);
 * - JSON 备份: 账号 (不含凭证) + 全部用量记录, gzip 压缩;
 *   导入按 usg_id 幂等 upsert, 凭证不迁移 (Android Keystore 密钥不可导出),
 *   恢复后的账号需重新登录。
 */
object BackupManager {

    private const val EXPORT_PAGE = 1000

    // ------------------------------------------------------------------
    // CSV
    // ------------------------------------------------------------------

    private val CSV_HEADER = listOf(
        "created_at", "model", "provider", "input_tokens", "output_tokens",
        "reasoning_tokens", "cache_read_tokens", "cache_write_5m_tokens",
        "cache_write_1h_tokens", "cost_usd", "session_id", "key_id", "plan", "account_id",
    )

    private fun csvField(v: Any?): String {
        val s = v?.toString() ?: ""
        return if (s.contains(',') || s.contains('"') || s.contains('\n')) {
            '"' + s.replace("\"", "\"\"") + '"'
        } else s
    }

    /** 导出全部账号的用量明细为 CSV (无 token 凭证, 只有统计列)。 */
    suspend fun exportCsv(context: Context, uri: Uri) {
        val db = AppDatabase.get(context)
        val accounts = db.syncDao().listAccounts().filter { it.hasToken }
        context.contentResolver.openOutputStream(uri)?.use { raw ->
            java.io.BufferedWriter(java.io.OutputStreamWriter(raw, Charsets.UTF_8)).use { w ->
                w.write(CSV_HEADER.joinToString(","))
                w.write("\n")
                for (acc in accounts) {
                    var offset = 0
                    while (true) {
                        val page = db.usageDao().exportPage(acc.id, EXPORT_PAGE, offset)
                        if (page.isEmpty()) break
                        for (r in page) {
                            w.write(
                                listOf(
                                    r.createdAt, r.model, r.provider, r.inputTokens, r.outputTokens,
                                    r.reasoningTokens, r.cacheReadTokens, r.cacheWrite5mTokens,
                                    r.cacheWrite1hTokens, r.costUsd, r.sessionId, r.keyId, r.plan, r.accountId,
                                ).joinToString(",") { csvField(it) }
                            )
                            w.write("\n")
                        }
                        offset += page.size
                        if (page.size < EXPORT_PAGE) break
                    }
                }
            }
        } ?: throw IllegalStateException("无法打开导出文件")
    }

    // ------------------------------------------------------------------
    // JSON backup
    // ------------------------------------------------------------------

    @Serializable
    data class BackupAccount(
        val id: Int,
        val name: String,
        val workspaceId: String,
        val provider: String,
        val hasToken: Boolean,
    )

    @Serializable
    data class BackupRecord(
        val usgId: String,
        val createdAt: String,
        val model: String,
        val provider: String? = null,
        val inputTokens: Int = 0,
        val outputTokens: Int = 0,
        val reasoningTokens: Int = 0,
        val cacheReadTokens: Int = 0,
        val cacheWrite5mTokens: Int = 0,
        val cacheWrite1hTokens: Int = 0,
        val costUsd: Double = 0.0,
        val keyId: String? = null,
        val sessionId: String? = null,
        val plan: String? = null,
        val localDate: String? = null,
        val accountId: Int = 1,
    )

    @Serializable
    data class BackupFile(
        val app: String = "GoGauge",
        val version: Int = 1,
        val exportedAt: String,
        val accounts: List<BackupAccount>,
        val records: List<BackupRecord>,
    )

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    suspend fun exportBackup(context: Context, uri: Uri) {
        val db = AppDatabase.get(context)
        val accounts = db.syncDao().listAccounts().map {
            BackupAccount(it.id, it.name, it.workspaceId, it.provider, it.hasToken)
        }
        val records = mutableListOf<BackupRecord>()
        for (acc in accounts) {
            var offset = 0
            while (true) {
                val page = db.usageDao().exportPage(acc.id, EXPORT_PAGE, offset)
                if (page.isEmpty()) break
                records += page.map { r -> r.toBackup() }
                offset += page.size
                if (page.size < EXPORT_PAGE) break
            }
        }
        val body = json.encodeToString(
            BackupFile.serializer(),
            BackupFile(exportedAt = Instant.now().toString(), accounts = accounts, records = records),
        )
        context.contentResolver.openOutputStream(uri)?.use { raw ->
            java.io.BufferedOutputStream(GZIPOutputStream(raw, 1 shl 16)).use { out ->
                out.write(body.toByteArray(Charsets.UTF_8))
            }
        } ?: throw IllegalStateException("无法打开导出文件")
    }

    /** 导入结果 (新增账号数 / 新增记录数 / 跳过账号数)。 */
    data class ImportResult(val accountsAdded: Int, val recordsAdded: Int, val accountsSkipped: Int)

    /**
     * 导入备份并合并: 记录按 usg_id 幂等 upsert; 账号按 (provider, workspace_id) 去重,
     * 只建空账号行 (凭证不可迁移, 需重新登录)。
     */
    suspend fun importBackup(context: Context, uri: Uri): ImportResult {
        val body = context.contentResolver.openInputStream(uri)?.use { raw ->
            BufferedReader(InputStreamReader(GZIPInputStream(raw, 1 shl 16), Charsets.UTF_8))
                .use { it.readText() }
        } ?: throw IllegalStateException("无法读取备份文件")
        val file = json.decodeFromString(BackupFile.serializer(), body)

        val db = AppDatabase.get(context)
        var accountsAdded = 0
        var accountsSkipped = 0
        val idRemap = HashMap<Int, Int>() // 备份账号 id -> 本地账号 id

        for (acc in file.accounts) {
            val existing = db.syncDao().listAccounts().firstOrNull {
                it.provider == acc.provider && it.workspaceId == acc.workspaceId
            }
            if (existing != null) {
                idRemap[acc.id] = existing.id
                accountsSkipped++
            } else {
                // 空 token 建占位行 (addAccountData 对空凭证跳过去重, 直接建行);
                // 凭证不可迁移, 恢复后用户重新登录即可复用历史记录
                val newId = db.syncDao().addAccount("", acc.workspaceId, switch = false, acc.provider)
                db.syncDao().renameAccount(newId, acc.name)
                idRemap[acc.id] = newId
                accountsAdded++
            }
        }

        var recordsAdded = 0
        val nowIso = Instant.now().toString()
        file.records.chunked(EXPORT_PAGE).forEach { chunk ->
            val entities = chunk.map { r ->
                UsageRecordEntity(
                    usgId = r.usgId,
                    createdAt = r.createdAt,
                    model = r.model,
                    provider = r.provider,
                    inputTokens = r.inputTokens,
                    outputTokens = r.outputTokens,
                    reasoningTokens = r.reasoningTokens,
                    cacheReadTokens = r.cacheReadTokens,
                    cacheWrite5mTokens = r.cacheWrite5mTokens,
                    cacheWrite1hTokens = r.cacheWrite1hTokens,
                    costUsd = r.costUsd,
                    keyId = r.keyId,
                    sessionId = r.sessionId,
                    plan = r.plan,
                    syncedAt = nowIso,
                    accountId = idRemap[r.accountId] ?: 1,
                    localDate = r.localDate,
                )
            }
            recordsAdded += db.usageDao().insertUsageRecords(entities, entities.first().accountId)
        }
        return ImportResult(accountsAdded, recordsAdded, accountsSkipped)
    }

    private fun UsageRecordEntity.toBackup() = BackupRecord(
        usgId = usgId, createdAt = createdAt, model = model, provider = provider,
        inputTokens = inputTokens, outputTokens = outputTokens, reasoningTokens = reasoningTokens,
        cacheReadTokens = cacheReadTokens, cacheWrite5mTokens = cacheWrite5mTokens,
        cacheWrite1hTokens = cacheWrite1hTokens, costUsd = costUsd,
        keyId = keyId, sessionId = sessionId, plan = plan, localDate = localDate, accountId = accountId,
    )
}
