package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Query
import io.github.yphyphyph.gogauge.data.model.AppSettings
import io.github.yphyphyph.gogauge.util.parseIsoInstant
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
                chartAnimation = obj["chart_animation"]?.jsonPrimitive?.contentOrNull()
                    ?.toBooleanStrictOrNull() ?: defaults().chartAnimation,
                persistentNotification = obj["persistent_notification"]?.jsonPrimitive?.contentOrNull()
                    ?.toBooleanStrictOrNull() ?: defaults().persistentNotification,
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
            chartAnimation = patch.chartAnimation,
            persistentNotification = patch.persistentNotification,
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
                put("chart_animation", JsonPrimitive(merged.chartAnimation))
                put("persistent_notification", JsonPrimitive(merged.persistentNotification))
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
        val normalized = MonthlyCycle.normalize(resetUtc) ?: return
        savePayloadKey("monthly_reset:$accountId", normalized)
    }

    /** 记录账号当前计费周期起止 (desktop db.record_period_bounds parity, commandcode 真实周期)。 */
    suspend fun savePeriodBounds(accountId: Int, startUtc: String?, endUtc: String?) {
        // ISO -> UTC "yyyy-MM-dd HH:mm:ss" 归一化后再入库 (desktop _parse_utc_naive parity;
        // 漏掉这步会让「本月」的 FMT 解析永远失败 -> 退化为滚动 30 天)
        val start = MonthlyCycle.normalize(startUtc) ?: return
        val end = MonthlyCycle.normalize(endUtc) ?: return
        savePayloadKey("period_start:$accountId", start)
        savePayloadKey("period_end:$accountId", end)
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

    /** 一次性维护标记 (payload 布尔键): 幂等数据修复的"只跑一次"语义。 */
    suspend fun getMaintenanceFlag(key: String): Boolean {
        val raw = payload() ?: return false
        return try {
            json.parseToJsonElement(raw).jsonObject[key]?.let {
                (it as? JsonPrimitive)?.content == "1"
            } ?: false
        } catch (e: Exception) {
            false
        }
    }

    suspend fun setMaintenanceFlag(key: String) {
        savePayloadKey(key, "1")
    }

    /**
     * 小组件账号选择 (v2.2.0b): 键 `widget_account:{appWidgetId}`,
     * 值 "active" (跟随活跃账号) 或 "account:{id}" (固定账号)。默认 "active"。
     */
    suspend fun getWidgetAccount(appWidgetId: Int): String {
        val raw = payload() ?: return "active"
        return try {
            json.parseToJsonElement(raw).jsonObject["widget_account:$appWidgetId"]
                ?.let { (it as? JsonPrimitive)?.content } ?: "active"
        } catch (e: Exception) {
            "active"
        }
    }

    suspend fun setWidgetAccount(appWidgetId: Int, mode: String) {
        savePayloadKey("widget_account:$appWidgetId", mode)
    }

    /** 小组件被移除时清掉对应配置键 (payload 键少, 整包读改写成本可忽略)。 */
    suspend fun removeWidgetAccount(appWidgetId: Int) {
        PayloadLock.mutex.withLock {
            val base = try {
                json.parseToJsonElement(payload() ?: "{}").jsonObject
            } catch (e: Exception) {
                buildJsonObject {}
            }
            val merged = buildJsonObject {
                for ((k, v) in base) if (k != "widget_account:$appWidgetId") put(k, v)
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

    /**
     * 归一化周期时间串: 接受 ISO (Z/偏移/毫秒) 与 "yyyy-MM-dd HH:mm:ss" 两种形态,
     * 输出 UTC "yyyy-MM-dd HH:mm:ss"; 无法解析返回 null (desktop db._parse_utc_naive parity)。
     *
     * CC 的 currentPeriodStart/End 是 ISO 串 ("2026-09-02T01:03:43.000Z"), 若直接
     * 按 FMT 解析必然失败 —— 原先 savePeriodBounds 未归一化, 导致「本月」周期
     * 静默退化为滚动 30 天。
     */
    fun normalize(raw: String?): String? {
        if (raw.isNullOrBlank()) return null
        return try {
            java.time.LocalDateTime.parse(raw, FMT).format(FMT)
        } catch (e: Exception) {
            val instant = parseIsoInstant(raw) ?: return null
            java.time.LocalDateTime.ofInstant(instant, java.time.ZoneOffset.UTC).format(FMT)
        }
    }

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
     * 统一入口: 优先真实计费周期 (commandcode), 无记录/串非法回退 monthly_reset 推算
     * (opencode), 两者皆无返回 null (调用方回退滚动 30 天)。周期串先经 [normalize]
     * 归一化, 存量 ISO 数据也能生效。
     */
    fun startWithPeriod(periodStart: String?, periodEnd: String?, monthlyReset: String?, nowMs: Long): String? {
        val ps = normalize(periodStart)
        if (ps != null) {
            return try {
                var start = java.time.LocalDateTime.parse(ps, FMT)
                    .atZone(java.time.ZoneOffset.UTC).toInstant().toEpochMilli()
                val pe = normalize(periodEnd)
                if (pe != null) {
                    var end = java.time.LocalDateTime.parse(pe, FMT)
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
        return start(normalize(monthlyReset), nowUtcString(nowMs))
    }

    /** 当前 UTC 时间 (与存储格式一致)。 */
    fun nowUtc(): String = nowUtcString(System.currentTimeMillis())

    private fun nowUtcString(nowMs: Long): String =
        java.time.LocalDateTime.ofInstant(java.time.Instant.ofEpochMilli(nowMs), java.time.ZoneOffset.UTC).format(FMT)

    private fun fmtUtc(ms: Long): String =
        java.time.LocalDateTime.ofInstant(java.time.Instant.ofEpochMilli(ms), java.time.ZoneOffset.UTC).format(FMT)
}
