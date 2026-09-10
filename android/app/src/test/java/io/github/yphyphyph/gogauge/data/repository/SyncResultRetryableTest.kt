package io.github.yphyphyph.gogauge.data.repository

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * SyncResult 重试语义测试.
 *
 * 背景: SyncWorker 此前把「未登录」之外的所有失败都映射为 Result.retry(),
 * 于是一个永久性的鉴权失败 (或"已有同步在跑"这种非错误状态) 会让 WorkManager
 * 按指数退避无限重试. 现在按 [SyncResult.retryable] 区分, 这里锁定默认值与
 * 各构造点的约定.
 */
class SyncResultRetryableTest {

    @Test
    fun `defaults to retryable for unknown errors`() {
        // 未显式分类的失败倾向于重试 (网络抖动是常见原因)
        val r = SyncResult(ok = false, error = "网络错误")
        assertTrue(r.retryable)
        assertFalse(r.ok)
    }

    @Test
    fun `permanent failures are marked not retryable`() {
        val notLoggedIn = SyncResult(ok = false, error = "未登录", retryable = false)
        val alreadyRunning = SyncResult(ok = false, error = "已有同步任务进行中", retryable = false)
        val authFailed = SyncResult(ok = false, error = "认证失败 (HTTP 401)，请重新登录", retryable = false)

        assertFalse(notLoggedIn.retryable)
        assertFalse(alreadyRunning.retryable)
        assertFalse(authFailed.retryable)
    }

    @Test
    fun `successful results carry retryable default without meaning`() {
        val ok = SyncResult(ok = true, inserted = 5, pages = 2)
        assertTrue(ok.ok)
        assertFalse(ok.partial)
        // partial 成功仍算成功: 不应触发 WorkManager 重试整个任务
        val partial = SyncResult(ok = true, partial = true, inserted = 3)
        assertTrue(partial.ok)
    }

    @Test
    fun `partial success is still ok`() {
        // 落库部分数据的同步不应被当成失败重跑 (会重复网络请求)
        val r = SyncResult(ok = true, partial = true, failedPages = 2, inserted = 10)
        assertTrue(r.ok)
        assertTrue(r.partial)
        assertTrue(r.failedPages == 2)
    }
}
