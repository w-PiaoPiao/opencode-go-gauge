package io.github.yphyphyph.gogauge.data.db

import androidx.room.Dao
import androidx.room.Query
import androidx.room.Upsert

/**
 * 配额快照 DAO — quota_snapshots 表的读写。
 * 小组件 (Glance) / 磁贴 (TileService) / 常驻通知在 app 进程外或独立入口渲染,
 * 统一从这张表取最近一次成功拉取的窗口数据。
 */
@Dao
abstract class QuotaSnapshotDao {

    @Upsert
    abstract suspend fun upsertAll(snapshots: List<QuotaSnapshotEntity>)

    @Query("SELECT * FROM quota_snapshots")
    abstract suspend fun all(): List<QuotaSnapshotEntity>

    @Query("SELECT * FROM quota_snapshots WHERE account_id = :accountId")
    abstract suspend fun forAccount(accountId: Int): QuotaSnapshotEntity?

    /** 删除账号时同步清快照 (配额缓存槽清理的持久层对应物)。 */
    @Query("DELETE FROM quota_snapshots WHERE account_id = :accountId")
    abstract suspend fun delete(accountId: Int)
}
