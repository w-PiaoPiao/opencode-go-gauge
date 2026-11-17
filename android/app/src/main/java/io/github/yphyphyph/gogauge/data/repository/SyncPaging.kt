package io.github.yphyphyph.gogauge.data.repository

import io.github.yphyphyph.gogauge.util.parseIsoInstant

/**
 * 同步翻页「自然停止点 / 截断」判定 — 纯函数集合 (JVM 单测覆盖,
 * 见 test/.../repository/SyncPagingTest.kt)。
 *
 * 背景 (sync-fix 设计规范 §1 B/C): 增量同步 `since = newest_record_at - 1h`, 休眠
 * 几天后重开可能积压上千条。旧实现一轮只翻 10 页 (1000 条) 就在页数上限处退出,
 * 且收尾静默写 "ok" + 前移游标 —— 缺口从此越不过去, 只能手动全量同步才补得回。
 *
 * 正确的自然停止点只有三个:
 * 1. 游标耗尽 (`cursor == null` → exhausted, 真正到底);
 * 2. 全量模式命中同步范围窗口边界 (该页保留后停);
 * 3. 增量模式命中 since 边界 (本页最早记录 ≤ since → 整个 [since, now] 窗口已连续拉全)。
 *
 * 只有「页数预算用尽、且以上三个自然停止点都没到」才算 truncated; truncated 必须
 * 收尾为 partial 且不推进 newest 游标, 下一轮从同一窗口继续补拉。
 *
 * 「连续两批 0 新增即停」只保留给 since 未知的回退路径 (账号还没有游标) 与
 * commandcode 分支 —— since 已知时它会被「已知数据段」提前触发: 翻到本地已有数据的
 * 区域就停了, 越不过缺口, 这正是本次自动同步漏数据的直接放大器。
 */
internal object SyncPaging {

    /** 截断收尾统一文案 (三端同一措辞, sync-fix 设计规范 §1 C)。 */
    const val TRUNCATED_MESSAGE =
        "达到单轮翻页上限 (数据不完整, 下次同步继续补拉; 如持续出现可手动全量同步)"

    /**
     * 翻页中断 (failedPages>0) 收尾统一文案 — desktop `_finish_sync` 两种 provider
     * 共用同一措辞 (部分页失败同样是 partial 且不推进游标, 下一轮会自动继续补拉)。
     */
    const val FAILED_PAGES_MESSAGE =
        "完成, 但翻页中断 (数据不完整, 下次同步自动继续补拉; 如持续出现可手动全量同步)"

    /** 全量同步模式常量 (与字符串 mode 参数同值)。 */
    private const val MODE_FULL = "full"

    /**
     * 本页最早记录是否已触达 since 边界: 仅增量模式且 since 已知时成立,
     * 且 `pageOldestMs <= sinceMs` (整段 [since, now] 已连续覆盖)。
     */
    fun reachedSince(mode: String, sinceMs: Long?, pageOldestMs: Long?): Boolean =
        mode != MODE_FULL && sinceMs != null && pageOldestMs != null && pageOldestMs <= sinceMs

    /** 记录时间戳集合 -> 毫秒最小值; 无法解析的条目忽略, 全无法解析/空集合返回 null。 */
    fun oldestMillis(createdAts: Iterable<String>): Long? =
        createdAts.mapNotNull { parseIsoInstant(it)?.toEpochMilli() }.minOrNull()

    /**
     * 页数预算用尽时的截断判定 (sync-fix 设计规范 §1 C):
     * `page >= maxPages && !exhausted && !windowBoundaryReached && !reachedSince`。
     *
     * 页数上限只防病态服务端, 不应成为正常缺口追平的终点 —— 一旦为 true, 收尾必须是
     * partial 且**不推进** newest 游标, 否则缺口会被永久跳过。
     */
    fun truncated(
        page: Int,
        maxPages: Int,
        exhausted: Boolean,
        windowBoundaryReached: Boolean,
        reachedSince: Boolean,
    ): Boolean = page >= maxPages && !exhausted && !windowBoundaryReached && !reachedSince

    /**
     * 「连续两批 0 新增即追平」兜底是否生效: 仅增量模式且 **since 未知** (无游标, 退化为
     * 类全量) 时可用; since 已知时禁止早停 (会停在已知数据段、越不过缺口)。
     */
    fun stopOnEmptyBatches(mode: String, sinceMs: Long?, emptyPages: Int): Boolean =
        mode != MODE_FULL && sinceMs == null && emptyPages >= 2

    /** 更新「连续 0 新增批次数」: 本批无新增 +1, 有新增清零。 */
    fun updateEmptyBatches(inserted: Int, emptyPages: Int): Int =
        if (inserted == 0) emptyPages + 1 else 0

    /**
     * 账号本轮实际执行的同步模式 (sync-fix 设计规范 §1 E):
     * 增量轮询里距上次成功全量超过校准周期的账号升级为 full (自动校准历史缺口);
     * 用户显式点「全量同步」时 mode 恒为 full, 语义不变。
     */
    fun effectiveMode(requestedMode: String, fullSyncDue: Boolean): String =
        if (requestedMode != MODE_FULL && fullSyncDue) MODE_FULL else requestedMode
}
