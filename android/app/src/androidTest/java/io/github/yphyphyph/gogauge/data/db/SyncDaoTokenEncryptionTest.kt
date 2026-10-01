package io.github.yphyphyph.gogauge.data.db

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * SyncDao 的 token 加解密集成验证 (真实 Room + Android Keystore):
 * 写入落库必须是密文, 明面读取必须是明文, 旧明文数据平滑兼容。
 */
@RunWith(AndroidJUnit4::class)
class SyncDaoTokenEncryptionTest {

    private fun openDb(): AppDatabase =
        Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext<Context>(),
            AppDatabase::class.java,
        ).build()

    @Test
    fun tokenIsEncryptedAtRestAndDecryptedOnRead() = runBlocking {
        val db = openDb()
        try {
            val dao = db.syncDao()
            dao.insertAccountRow(
                AccountEntity(id = 1, name = "A", workspaceId = "wrk_x", token = "plain-token-1"),
            )
            // 明面读取: 明文
            assertEquals("plain-token-1", dao.accountRowById(1)?.token)
            assertEquals("plain-token-1", dao.getTokenFor(1))
            // 底层存储: 密文, 且不等于明文
            val raw = dao.accountRowByIdRaw(1)?.token ?: ""
            assertTrue("at-rest token must be encrypted: $raw", raw.startsWith("enc:v1:"))
            assertNotEquals("plain-token-1", raw)
            assertTrue(dao.accountRowById(1)!!.hasToken)

            // updateCredential 路径同样加密
            dao.updateCredential(1, "rotated-token", "wrk_y", "opencode", "now")
            assertEquals("rotated-token", dao.accountRowById(1)?.token)
            assertTrue(dao.accountRowByIdRaw(1)!!.token.startsWith("enc:v1:"))
        } finally {
            db.close()
        }
    }

    @Test
    fun legacyPlaintextReadsThroughAndClearTokenStaysEmpty() = runBlocking {
        val db = openDb()
        try {
            val dao = db.syncDao()
            // 升级前的明文行 (绕过包装直插底层): 读取原样返回
            dao.insertAccountRowRaw(AccountEntity(id = 2, name = "legacy", token = "legacy-plain"))
            assertEquals("legacy-plain", dao.accountRowById(2)?.token)

            dao.insertAccountRow(AccountEntity(id = 3, name = "B", token = "tok-3"))
            dao.clearToken(3, "now")
            assertEquals("", dao.accountRowById(3)?.token)
            assertEquals("", dao.accountRowByIdRaw(3)?.token)
            assertFalse(dao.accountRowById(3)!!.hasToken)
            // SQL 层"已登录"计数 (TRIM(token) != '') 对密文/明文/空串口径正确
            assertEquals(1, dao.countLoggedInAccountsRaw())
            assertEquals(2, dao.minLoggedInId())
        } finally {
            db.close()
        }
    }
}
