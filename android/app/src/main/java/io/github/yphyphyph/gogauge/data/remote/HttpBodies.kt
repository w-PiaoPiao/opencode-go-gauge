package io.github.yphyphyph.gogauge.data.remote

import okhttp3.Response
import java.io.ByteArrayOutputStream

/**
 * 有界响应体读取 (data/remote 共用).
 *
 * 直接 `body.string()` 会把整个响应读进内存才判断大小, 一个异常或恶意的超大响应
 * 就能耗尽内存. 这里流式读取, 一旦超过 [maxBytes] 立即中止并抛错.
 *
 * @throws OpenCodeApiException 超过上限时
 */
internal fun readBoundedBody(resp: Response, maxBytes: Int): String =
    resp.body?.byteStream()?.use { input ->
        val buf = ByteArrayOutputStream()
        val chunk = ByteArray(64 * 1024)
        var total = 0
        while (true) {
            val n = input.read(chunk)
            if (n < 0) break
            total += n
            if (total > maxBytes) {
                throw OpenCodeApiException("响应过大 (超过 $maxBytes 字节)")
            }
            buf.write(chunk, 0, n)
        }
        buf.toString("UTF-8")
    } ?: ""

/** 与 OpenCodeApi.MAX_BODY_BYTES 同值: 用量/仪表盘类响应的统一上限 (4 MiB). */
internal const val DEFAULT_MAX_BODY_BYTES = 4 * 1024 * 1024
