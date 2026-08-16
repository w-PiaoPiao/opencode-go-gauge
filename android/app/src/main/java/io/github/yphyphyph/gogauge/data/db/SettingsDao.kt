package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Query
import io.github.yphyphyph.gogauge.data.model.AppSettings
import kotlinx.serialization.json.Json
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
        )
        val payload = buildString {
            append("{\"sync_interval_sec\":").append(merged.syncIntervalSec)
            append(",\"window_days\":").append(merged.windowDays ?: "null")
            append(",\"auto_sync\":").append(merged.autoSync)
            append("}")
        }
        savePayload(payload, java.time.Instant.now().toString())
        return merged
    }

    private fun kotlinx.serialization.json.JsonElement.contentOrNull(): String? {
        return (this as? kotlinx.serialization.json.JsonPrimitive)?.content
    }
}
