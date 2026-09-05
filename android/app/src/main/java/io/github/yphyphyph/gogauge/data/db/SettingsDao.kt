package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Query
import io.github.yphyphyph.gogauge.data.model.AppSettings
import kotlinx.coroutines.sync.withLock
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
        val merged = AppSettings(
            syncIntervalSec = patch.syncIntervalSec.coerceIn(30, 3600),
            windowDays = patch.windowDays?.coerceIn(1, 3650),
            autoSync = patch.autoSync,
            showAccountsPanel = patch.showAccountsPanel,
        )
        // 保存时在既有 payload 上合并覆盖 (与桌面 db.save_settings 的整行 JSON 覆盖不同,
        // 安卓端 settings 行还承载 active_account_id 等运行时键, 不能整包丢弃)
        PayloadLock.mutex.withLock {
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
        }
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
        PayloadLock.mutex.withLock {
            val base = try {
                json.parseToJsonElement(payload() ?: "{}").jsonObject
            } catch (e: Exception) {
                buildJsonObject {}
            }
            val merged = buildJsonObject {
                for ((k, v) in base) put(k, v)
                put("key_names", buildJsonObject { for ((k, v) in filtered) put(k, JsonPrimitive(v)) })
            }
            savePayload(merged.toString(), java.time.Instant.now().toString())
        }
    }

    private fun kotlinx.serialization.json.JsonElement.contentOrNull(): String? {
        return (this as? kotlinx.serialization.json.JsonPrimitive)?.content
    }

    /** 读取账号的下次月度重置时间 (desktop settings payload 键 monthly_reset:{aid} parity). */
    suspend fun getMonthlyReset(accountId: Int): String? {
        val raw = payload() ?: return null
        return try {
            json.parseToJsonElement(raw).jsonObject["monthly_reset:$accountId"]?.let {
                (it as? kotlinx.serialization.json.JsonPrimitive)?.content
            }
        } catch (e: Exception) {
            null
        }
    }

    /** 持久化账号的下次月度重置时间, UTC "yyyy-MM-dd HH:mm:ss" (desktop db.record_monthly_reset parity). */
    suspend fun saveMonthlyReset(accountId: Int, resetUtc: String?) {
        if (resetUtc.isNullOrBlank()) return
        savePayloadKey("monthly_reset:$accountId", resetUtc)
    }

    /** 记录账号当前计费周期起止 (desktop db.record_period_bounds parity, commandcode 真实周期)。 */
    suspend fun savePeriodBounds(accountId: Int, startUtc: String?, endUtc: String?) {
        if (startUtc.isNullOrBlank() || endUtc.isNullOrBlank()) return
        savePayloadKey("period_start:$accountId", startUtc)
        savePayloadKey("period_end:$accountId", endUtc)
    }

    /** 读取账号的计费周期起止 (无记录返回 null 对)。 */
    suspend fun getPeriodBounds(accountId: Int): Pair<String?, String?> {
        val obj = try {
            json.parseToJsonElement(payload() ?: "{}").jsonObject
        } catch (e: Exception) {
            return null to null
        }
        val start = obj["period_start:$accountId"]?.let { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }
        val end = obj["period_end:$accountId"]?.let { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }
        return start to end
    }

    /** 单键写入: 整包读改写互斥, 保留其余键 (PayloadLock 串行)。 */
    private suspend fun savePayloadKey(key: String, value: String) {
        PayloadLock.mutex.withLock {
            val base = try {
                json.parseToJsonElement(payload() ?: "{}").jsonObject
            } catch (e: Exception) {
                buildJsonObject {}
            }
            val merged = buildJsonObject {
                for ((k, v) in base) put(k, v)
                put(key, JsonPrimitive(value))
            }
            savePayload(merged.toString(), java.time.Instant.now().toString())
        }
    }
}

/**
 * 月度重置周期策略 — mirrors desktop db.monthly_cycle_start.
 *
 * - commandcode 等记录过真实计费周期的账号: 直接取 period_start; 周期已过期
 *   (配额未刷新) 时按周期跨度顺延到覆盖当前时刻的最近周期 (上限 1200 次防死循环,
 *   span<=0 视为非法数据回退); 无周期记录时为 null (调用方回退滚动 30 天).
 * - opencode 无真实起点: 由下次重置时间回推 30 天 ("重置-30天" 规则).
 * 时间统一为 UTC "yyyy-MM-dd HH:mm:ss" 字符串, 与持久化格式一致.
 */
object MonthlyCycle {
    const val PERIOD_DAYS = 30
    private val FMT = java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
    private const val MAX_PERIOD_ROLLS = 1200

    /** 推导当前周期起点 (UTC "yyyy-MM-dd HH:mm:ss"); resetUtc 为存储的下次重置时间. */
    fun start(resetUtc: String?, nowUtc: String): String? {
        if (resetUtc.isNullOrBlank()) return null
        return try {
            val reset = java.time.LocalDateTime.parse(resetUtc, FMT)
            val now = java.time.LocalDateTime.parse(nowUtc, FMT)
            val started = if (reset.isAfter(now)) reset.minusDays(PERIOD_DAYS.toLong()) else reset
            started.format(FMT)
        } catch (e: Exception) {
            null
        }
    }

    /**
     * 统一入口: 优先真实计费周期 (commandcode), 无记录回退 monthly_reset 推算
     * (opencode), 两者皆无返回 null (调用方回退滚动 30 天).
     */
    fun startWithPeriod(periodStart: String?, periodEnd: String?, monthlyReset: String?, nowMs: Long): String? {
        if (!periodStart.isNullOrBlank()) {
            return try {
                var start = java.time.LocalDateTime.parse(periodStart, FMT)
                    .atZone(java.time.ZoneOffset.UTC).toInstant().toEpochMilli()
                if (!periodEnd.isNullOrBlank()) {
                    var end = java.time.LocalDateTime.parse(periodEnd, FMT)
                        .atZone(java.time.ZoneOffset.UTC).toInstant().toEpochMilli()
                    var rolled = 0
                    // 顺延跨周期覆盖当前时刻; 上限兜底防异常数据死循环 (desktop parity:
                    // 达到上限取最后起点, 仅 end<=start 非法数据回退 null)
                    while (end <= nowMs && rolled < MAX_PERIOD_ROLLS) {
                        val span = end - start
                        if (span <= 0) return null
                        start = end
                        end += span
                        rolled++
                    }
                }
                fmtUtc(start)
            } catch (e: Exception) {
                null
            }
        }
        return start(monthlyReset, nowUtcString(nowMs))
    }

    /** 当前 UTC 时间 (与存储格式一致)。 */
    fun nowUtc(): String = nowUtcString(System.currentTimeMillis())

    private fun nowUtcString(nowMs: Long): String =
        java.time.LocalDateTime.ofInstant(java.time.Instant.ofEpochMilli(nowMs), java.time.ZoneOffset.UTC).format(FMT)

    private fun fmtUtc(ms: Long): String =
        java.time.LocalDateTime.ofInstant(java.time.Instant.ofEpochMilli(ms), java.time.ZoneOffset.UTC).format(FMT)
}
