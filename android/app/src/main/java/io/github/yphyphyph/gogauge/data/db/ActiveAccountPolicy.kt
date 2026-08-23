package io.github.yphyphyph.gogauge.data.db

/**
 * 活跃账号解析策略 — desktop db.get_active_account_id 决策逻辑的纯函数抽取
 * (便于 JVM 单测; DAO 层负责持久化)。
 *
 * 规则 (desktop parity):
 * - 存储的活跃账号已登录 → 维持
 * - 存储的活跃账号未登录, 但存在其他已登录账号 → 让位给最小的已登录账号
 *   (保证应用启动时默认落在可用的账号上)
 * - 全部未登录 → 维持原选择 (使欢迎页登录能落到既有行)
 * - 无存储值/存储值不存在 → 最小已登录账号; 再退而求全部最小 id; 无任何账号返回 0
 */
object ActiveAccountPolicy {

    /** 账号快照 (id + 是否已登录)。 */
    data class Snapshot(val id: Int, val hasToken: Boolean)

    fun resolve(storedActiveId: Int?, accounts: List<Snapshot>): Int {
        val loggedMin = accounts.filter { it.hasToken }.minOfOrNull { it.id }
        if (storedActiveId != null && storedActiveId > 0) {
            val row = accounts.firstOrNull { it.id == storedActiveId }
            if (row != null) {
                if (row.hasToken) return storedActiveId
                if (loggedMin != null) return loggedMin // 活跃行未登录但有其他已登录账号 -> 让位
                return storedActiveId                    // 全部未登录: 维持原选择
            }
        }
        if (loggedMin != null) return loggedMin
        return accounts.minOfOrNull { it.id } ?: 0
    }

    /** 解析结果是否需要回写 (DAO 层据此决定 persist)。 */
    fun needsPersist(resolved: Int, storedActiveId: Int?): Boolean = resolved != (storedActiveId ?: 0)
}
