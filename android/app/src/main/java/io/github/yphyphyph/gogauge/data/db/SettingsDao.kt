package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Query
import io.github.yphyphyph.gogauge.data.model.AppSettings
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Settings DAO — mirrors desktop db.py settings table (JSON payload). */
@Dao
abstract class SettingsDao {

    private val json = Json { ignoreUnknownKeys = true }

    @Query("SELECT payload FROM settings WHERE id = 1")
    abstract suspend fun payload(): String?

    @Query("UPDATE settings SET payload = :payload, updated_at = :updatedAt WHERE id = 1")
    abstract suspend fun savePayload(payload: String, updatedAt: String)

    private fun defaults() = AppSettings()

    suspend fun getSettings(): AppSettings {
        val raw = payload() ?: return defaults()
        return try {
            val obj = json.parseToJsonElement(raw).jsonObject
            AppSettings(
                syncIntervalSec = (obj["sync_interval_sec"]?.jsonPrimitive?.contentOrNull()?.toIntOrNull())
                    ?.coerceIn(30, 3600) ?: defaults().syncIntervalSec,
                windowDays = when (val v = obj["window_days"]?.jsonPrimitive?.contentOrNull()) {
                    null, "", "null", "all", "所有" -> null
                    else -> v.toIntOrNull()?.coerceIn(1, 3650) ?: defaults().windowDays
                },
                autoSync = obj["auto_sync"]?.jsonPrimitive?.contentOrNull()?.toBooleanStrictOrNull() ?: defaults().autoSync,
                showAccountsPanel = obj["show_accounts_panel"]?.jsonPrimitive?.contentOrNull()
                    ?.toBooleanStrictOrNull() ?: defaults().showAccountsPanel,
            )
        } catch (e: Exception) {
            defaults()
        }
    }

    suspend fun saveSettings(patch: AppSettings): AppSettings {
        val current = getSettings()
        val merged = AppSettings(
            syncIntervalSec = patch.syncIntervalSec.coerceIn(30, 3600),
            windowDays = patch.windowDays?.coerceIn(1, 3650),
            autoSync = patch.autoSync,
            showAccountsPanel = patch.showAccountsPanel,
        )
        // 保存时在既有 payload 上合并覆盖 (与桌面 db.save_settings 的整行 JSON 覆盖不同,
        // 安卓端 settings 行还承载 active_account_id 等运行时键, 不能整包丢弃)
        val base = try {
            json.parseToJsonElement(payload() ?: "{}").jsonObject
        } catch (e: Exception) {
            buildJsonObject {}
        }
        val keyNames = getKeyNames()
        val payload = buildJsonObject {
            for ((k, v) in base) put(k, v)
            put("sync_interval_sec", JsonPrimitive(merged.syncIntervalSec))
            put("window_days", merged.windowDays?.let { JsonPrimitive(it) } ?: JsonNull)
            put("auto_sync", JsonPrimitive(merged.autoSync))
            put("show_accounts_panel", JsonPrimitive(merged.showAccountsPanel))
            put("key_names", buildJsonObject { for ((k, v) in keyNames) put(k, JsonPrimitive(v)) })
        }.toString()
        savePayload(payload, java.time.Instant.now().toString())
        return merged
    }

    /** 读取缓存的 key_id -> 显示名称 映射 (desktop db.get_key_names parity). */
    suspend fun getKeyNames(): Map<String, String> {
        val raw = payload() ?: return emptyMap()
        return try {
            val obj = json.parseToJsonElement(raw).jsonObject
            val names = obj["key_names"]?.jsonObject ?: return emptyMap()
            names.mapValues { it.value.jsonPrimitive.content }
        } catch (e: Exception) {
            emptyMap()
        }
    }

    /** 持久化 key_id -> 显示名称 映射到 settings payload (desktop db.save_key_names parity). */
    suspend fun saveKeyNames(names: Map<String, String>) {
        val filtered = names.filter { it.key.isNotEmpty() && it.value.isNotEmpty() }
        val raw = payload() ?: "{}"
        val base = try {
            json.parseToJsonElement(raw).jsonObject
        } catch (e: Exception) {
            buildJsonObject {}
        }
        val merged = buildJsonObject {
            for ((k, v) in base) put(k, v)
            put("key_names", buildJsonObject { for ((k, v) in filtered) put(k, JsonPrimitive(v)) })
        }
        savePayload(merged.toString(), java.time.Instant.now().toString())
    }

    private fun kotlinx.serialization.json.JsonElement.contentOrNull(): String? {
        return (this as? kotlinx.serialization.json.JsonPrimitive)?.content
    }
}
