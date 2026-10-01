package io.github.yphyphyph.gogauge.data.db

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * TokenCipher 的 Android Keystore 往返验证 — 需要真实 Keystore, 只能跑
 * instrumented (connectedDebugAndroidTest); JVM 单测无法覆盖。
 */
@RunWith(AndroidJUnit4::class)
class TokenCipherTest {

    @Test
    fun roundTripEncryptDecrypt() {
        val plain = "__Host-console_session=abc123; other=1"
        val stored = TokenCipher.encrypt(plain)
        assertTrue("must be encrypted at rest: $stored", stored.startsWith("enc:v1:"))
        assertNotEquals(plain, stored)
        assertEquals(plain, TokenCipher.decrypt(stored))
    }

    @Test
    fun distinctCiphertextPerCall() {
        // GCM 随机 IV: 同一明文两次加密结果不同, 都解得回明文
        val a = TokenCipher.encrypt("same-token")
        val b = TokenCipher.encrypt("same-token")
        assertNotEquals(a, b)
        assertEquals("same-token", TokenCipher.decrypt(a))
        assertEquals("same-token", TokenCipher.decrypt(b))
    }

    @Test
    fun emptyAndLegacyPlaintextPassThrough() {
        assertEquals("", TokenCipher.encrypt(""))
        assertEquals("", TokenCipher.decrypt(""))
        // 升级前的明文数据没有前缀: 原样读出 (下次写入自动加密)
        assertEquals("legacy-plain-token", TokenCipher.decrypt("legacy-plain-token"))
    }

    @Test
    fun alreadyEncryptedIsIdempotent() {
        val once = TokenCipher.encrypt("tok")
        assertEquals(once, TokenCipher.encrypt(once))
    }

    @Test
    fun corruptCiphertextNeverThrows() {
        val stored = TokenCipher.encrypt("tok")
        val corrupted = stored.dropLast(4) + "AAAA"
        // 解密失败按未登录处理 (空串), 绝不能让查询路径被异常击穿
        assertEquals("", TokenCipher.decrypt(corrupted))
        assertEquals("", TokenCipher.decrypt("enc:v1:not-base64!!!"))
    }
}
