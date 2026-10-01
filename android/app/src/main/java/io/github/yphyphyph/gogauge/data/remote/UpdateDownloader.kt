package io.github.yphyphyph.gogauge.data.remote

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

/**
 * 更新包下载与安装 — desktop updater.py 的应用内下载 parity
 * (`/api/update/download` + `/update/open`): 下载 APK 到应用私有目录 →
 * SHA-256 校验 (GitHub 官方 digest) → FileProvider 触发系统安装器。
 */
object UpdateDownloader {

    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .build()
    }

    /**
     * 下载 APK 到 cacheDir/updates/; 校验失败或下载中断时删除临时文件并抛错。
     *
     * @param digest GitHub API 的 assets[].digest, 形如 "sha256:<hex>";
     *   缺失/非法一律拒绝安装 (desktop _verify_digest fail-closed parity)。
     * @param onProgress 0-100 (contentLength 不可知时不回调)
     */
    suspend fun download(
        context: Context,
        url: String,
        fileName: String,
        digest: String?,
        onProgress: (Int) -> Unit,
    ): File = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val safeName = fileName.ifBlank { "GoGauge-update.apk" }
            .replace(Regex("[^A-Za-z0-9._-]"), "_")
        val target = File(dir, safeName)
        val tmp = File(dir, "$safeName.part")
        try {
            client.newCall(Request.Builder().url(url).build()).execute().use { resp ->
                if (!resp.isSuccessful) throw OpenCodeApiException("下载失败 (HTTP ${resp.code})")
                val body = resp.body ?: throw OpenCodeApiException("下载失败 (空响应)")
                val total = body.contentLength()
                var read = 0L
                tmp.outputStream().use { out ->
                    body.byteStream().use { input ->
                        val buf = ByteArray(64 * 1024)
                        while (true) {
                            val n = input.read(buf)
                            if (n < 0) break
                            out.write(buf, 0, n)
                            read += n
                            if (total > 0) onProgress((read * 100 / total).toInt().coerceIn(0, 100))
                        }
                    }
                }
            }
            verifyDigest(tmp, digest)
            if (target.exists()) target.delete()
            if (!tmp.renameTo(target)) {
                tmp.copyTo(target, overwrite = true)
                tmp.delete()
            }
            onProgress(100)
            target
        } catch (e: Exception) {
            tmp.delete()
            throw e
        }
    }

    /**
     * SHA-256 校验 (desktop _verify_digest parity, fail-closed): 摘要缺失、算法不受支持
     * 或格式非法时一律拒绝安装。先前的实现遇到空摘要 return 跳过校验 —— 被篡改或
     * 拼错的资产仍会进入安装流程, 桌面端已按 fail-closed 修复, 安卓此前未同步。
     * GitHub 对本仓库全部资产都返回 "sha256:<hex>", 严格要求不影响正常更新。
     */
    private fun verifyDigest(file: File, digest: String?) {
        val d = digest?.trim()?.lowercase().orEmpty()
        if (!d.startsWith("sha256:")) {
            throw OpenCodeApiException("下载包缺少官方 SHA-256 摘要, 已阻止安装")
        }
        val expected = d.substringAfter(":").trim()
        if (expected.length != 64 || expected.any { it !in "0123456789abcdef" }) {
            throw OpenCodeApiException("下载包摘要格式非法, 已阻止安装")
        }
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(1 shl 16)
            while (true) {
                val n = input.read(buf)
                if (n < 0) break
                md.update(buf, 0, n)
            }
        }
        val actual = md.digest().joinToString("") { "%02x".format(it) }
        if (actual != expected) {
            throw OpenCodeApiException("更新包 SHA-256 校验失败")
        }
    }

    /** 触发系统安装器 (FileProvider + ACTION_VIEW)。 */
    fun install(context: Context, file: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    /** 是否已允许本应用安装未知来源应用 (minSdk 26, canRequestPackageInstalls 恒可用)。 */
    fun canInstall(context: Context): Boolean =
        context.packageManager.canRequestPackageInstalls()

    /** 跳转"安装未知应用"授权页。 */
    fun openInstallSettings(context: Context) {
        runCatching {
            context.startActivity(
                Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${context.packageName}"),
                ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
    }
}
