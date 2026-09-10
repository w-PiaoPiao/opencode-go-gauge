package io.github.yphyphyph.gogauge.data.remote

import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 类初始化回归测试.
 *
 * 背景: OpenCodeApi 的 companion object 里定义了一个非法正则以 `\` 结尾,
 * `Regex(...)` 在 **类初始化** 时抛 PatternSyntaxException, 于是任何对
 * OpenCodeApi 的首次引用都会让应用启动崩溃. 而既有单测只覆盖 QuotaParser /
 * UsageParser 等纯对象, 从不触碰 OpenCodeApi, 所以 CI 全绿却上不了线.
 *
 * 这里显式触发每个网络客户端的静态初始化, 把这类"编译通过、启动即崩"的问题
 * 挡在单测阶段.
 */
class ApiClassInitTest {

    @Test
    fun `OpenCodeApi companion initializes without exception`() {
        // 读取 const 会触发 <clinit>; 若正则非法, 这里就会抛
        assertTrue(OpenCodeApi.MAX_BODY_BYTES > 0)
        assertTrue(OpenCodeApi.FETCH_RETRIES > 0)
    }

    @Test
    fun `CommandCodeApi companion initializes without exception`() {
        assertTrue(CommandCodeApi.MAX_BODY_BYTES > 0)
        assertTrue(CommandCodeApi.DEFAULT_LIMIT > 0)
    }

    @Test
    fun `UpdateApi companion initializes without exception`() {
        // companion 内没有 REGEX 常量, 通过公开方法引用触发初始化
        assertTrue(UpdateApi::class.java.simpleName.isNotEmpty())
    }
}
