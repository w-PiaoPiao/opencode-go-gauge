package io.github.yphyphyph.gogauge.data.db

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import android.util.Log
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * 账号 token 的静态加密 — desktop `_storage_encode` (DPAPI / Keychain) 的安卓对应物。
 *
 * Android Keystore 生成**不可导出**的 AES-256-GCM 密钥 (应用私有, 不随 DB 文件泄漏),
 * 密文以 `enc:v1:` + base64(iv || ciphertext) 落库。旧明文数据没有前缀, 读取时原样
 * 返回 (平滑升级), 下次写入自动加密。
 *
 * 失败语义: 加密不可用时回退明文 (不阻断登录); 解密失败返回空串 —— 查询路径绝不能
 * 被解密异常击穿, 最坏情况是该账号显示未登录, 用户重新登录即可。
 */
internal object TokenCipher {

    private const val PREFIX = "enc:v1:"
    private const val KEY_ALIAS = "gogauge_token_key"
    private const val KEYSTORE = "AndroidKeyStore"
    private const val GCM_TAG_BITS = 128
    private const val GCM_IV_BYTES = 12

    @Volatile
    private var cachedKey: SecretKey? = null

    private fun key(): SecretKey {
        cachedKey?.let { return it }
        synchronized(this) {
            cachedKey?.let { return it }
            val ks = KeyStore.getInstance(KEYSTORE).apply { load(null) }
            val existing = ks.getEntry(KEY_ALIAS, null) as? KeyStore.SecretKeyEntry
            val generated = existing?.secretKey ?: KeyGenerator
                .getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
                .apply {
                    init(
                        KeyGenParameterSpec.Builder(
                            KEY_ALIAS,
                            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                        )
                            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                            .setKeySize(256)
                            .build(),
                    )
                }
                .generateKey()
            cachedKey = generated
            return generated
        }
    }

    /** 明文 -> 存储形态; 空串原样返回 (未登录占位); 已加密串幂等返回。 */
    fun encrypt(plain: String): String {
        if (plain.isEmpty() || plain.startsWith(PREFIX)) return plain
        return try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key())
            val ct = cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
            PREFIX + Base64.encodeToString(cipher.iv + ct, Base64.NO_WRAP)
        } catch (e: Exception) {
            Log.w("GoGauge", "token encrypt failed, storing plaintext", e)
            plain
        }
    }

    /** 存储形态 -> 明文; 无前缀视为旧明文原样返回; 解密失败返回空串 (视为未登录)。 */
    fun decrypt(stored: String): String {
        if (stored.isEmpty() || !stored.startsWith(PREFIX)) return stored
        return try {
            val raw = Base64.decode(stored.substring(PREFIX.length), Base64.NO_WRAP)
            if (raw.size <= GCM_IV_BYTES) return ""
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(
                Cipher.DECRYPT_MODE,
                key(),
                GCMParameterSpec(GCM_TAG_BITS, raw.copyOfRange(0, GCM_IV_BYTES)),
            )
            String(cipher.doFinal(raw.copyOfRange(GCM_IV_BYTES, raw.size)), Charsets.UTF_8)
        } catch (e: Exception) {
            Log.w("GoGauge", "token decrypt failed; treating account as signed out", e)
            ""
        }
    }
}
