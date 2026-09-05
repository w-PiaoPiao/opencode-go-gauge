package io.github.yphyphyph.gogauge.data.remote

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import org.w3c.dom.Element
import java.io.ByteArrayInputStream
import java.io.IOException
import java.util.concurrent.TimeUnit
import javax.xml.parsers.DocumentBuilderFactory

/** GitHub release check result. */
data class UpdateInfo(
    val hasUpdate: Boolean,
    val current: String,
    val latest: String,
    val releaseUrl: String,
    val notes: String,
)

/**
 * Check GitHub Releases for a newer version — port of updater.py (desktop).
 * Lightweight prompt only; download happens via the system browser.
 *
 * 流程: 优先请求 GitHub API 最新 release -> 解析 tag -> 与本地版本比较;
 * API 受未认证限流(403)/502/超时影响时, 自动降级到 Releases Atom 流(不受 API 限流),
 * 两者均失败才抛可读错误 (desktop updater.py v1.0.2 parity).
 */
class UpdateApi(
    private val client: OkHttpClient = OpenCodeApi.defaultClient(),
) {
    companion object {
        // fork 发布仓库: 安卓 APK 由本 fork 的 release 分发, 更新检查指向 fork
        const val REPO = "w-PiaoPiao/opencode-go-gauge"
        // 列表接口而非 /releases/latest: 仓库 Latest 是全平台共享的一个标记,
        // 其他平台 (-macos/-windows) 发布后占据 Latest 会把安卓更新判断带偏
        // (tag 后缀被剥掉后版本比较失真). 这里只认 -android 条目 — desktop updater.py parity.
        const val RELEASES_URL = "https://api.github.com/repos/$REPO/releases?per_page=30"
        const val ATOM_URL = "https://github.com/$REPO/releases.atom"
        const val RELEASE_PAGE_URL = "https://github.com/$REPO/releases/latest"
        // 平台 tag 后缀: 更新检查只认带此后缀且版本前缀合法的 release 条目
        private const val PLATFORM_SUFFIX = "-android"
        // 境内直连 GitHub 间歇性 502/超时/重置, 自动重试提高成功率 (desktop parity)
        private const val MAX_ATTEMPTS = 3
        private const val RETRY_SLEEP_MS = 800L
        private const val ATOM_NS = "http://www.w3.org/2005/Atom"
        // 版本号支持三段数字 + 可选字母预发布后缀 (2.1.0b > 2.1.0) 及 -/+ 起尾缀
        // (2.1.0-macos / 2.1.0b-android, 尾缀不参与比较) — desktop updater.py parity
        private val TAG_RE = Regex("""^v?(\d+)\.(\d+)\.(\d+)([a-z])?(?:[-+].*)?$""")
        private val HTML_TAG_RE = Regex("<[^>]*>")
        private val WS_RE = Regex("\\s+")
    }

    private val json = Json { ignoreUnknownKeys = true }

    @Serializable
    private data class ReleaseResponse(
        @SerialName("tag_name") val tagName: String = "",
        @SerialName("html_url") val htmlUrl: String = RELEASE_PAGE_URL,
        @SerialName("body") val body: String? = null,
    )

    /** 四元组比较 (字母后缀按 a=1,b=2... 计入第四位, 无后缀=0) — desktop _parse_version parity. */
    private fun parseVersion(text: String): List<Int>? {
        val m = TAG_RE.matchEntire(text.trim()) ?: return null
        val suffix = m.groupValues[4]
        val letterRank = if (suffix.isEmpty()) 0 else suffix[0] - 'a' + 1
        return listOf(
            m.groupValues[1].toInt(),
            m.groupValues[2].toInt(),
            m.groupValues[3].toInt(),
            letterRank,
        )
    }

    /** tag 是否为本平台 release (如 v2.1.0-android): 版本前缀合法且带 -android 后缀. */
    private fun isPlatformTag(tag: String): Boolean {
        val t = tag.trim().lowercase()
        return t.endsWith(PLATFORM_SUFFIX) && parseVersion(t) != null
    }

    private fun isNewer(latest: List<Int>, current: List<Int>): Boolean {
        for (i in latest.indices) {
            if (latest[i] != current[i]) return latest[i] > current[i]
        }
        return false
    }

    /** 请求 URL 返回文本, 网络/HTTP 失败自动重试; 重试耗尽抛最后一次错误. */
    private suspend fun fetchText(url: String, accept: String, ua: String): String = withContext(Dispatchers.IO) {
        var last: Exception? = null
        for (attempt in 0 until MAX_ATTEMPTS) {
            try {
                val req = Request.Builder()
                    .url(url)
                    .header("User-Agent", ua)
                    .header("Accept", accept)
                    .build()
                val body = client.newCall(req).execute().use { resp ->
                    if (!resp.isSuccessful) throw OpenCodeApiException("GitHub HTTP ${resp.code}")
                    resp.body?.string() ?: ""
                }
                return@withContext body
            } catch (e: IOException) {
                last = e
                if (attempt < MAX_ATTEMPTS - 1) delay(RETRY_SLEEP_MS)
            } catch (e: OpenCodeApiException) {
                last = e
                if (attempt < MAX_ATTEMPTS - 1) delay(RETRY_SLEEP_MS)
            }
        }
        throw last ?: OpenCodeApiException("未知网络错误")
    }

    private fun stripHtml(text: String): String {
        var t = HTML_TAG_RE.replace(text.orEmpty(), " ")
        t = WS_RE.replace(t, " ")
        return t.trim()
    }

    /** 从 Releases Atom 流解析最新的本平台 (-android) release (desktop _fetch_latest_atom parity). */
    private fun parseAtom(text: String): Triple<String, String, String> {
        val factory = DocumentBuilderFactory.newInstance()
        factory.isNamespaceAware = true
        val doc = factory.newDocumentBuilder().parse(ByteArrayInputStream(text.toByteArray()))
        val entries = doc.getElementsByTagNameNS(ATOM_NS, "entry")
        if (entries.length == 0) {
            throw OpenCodeApiException("GitHub Releases 订阅流为空，未获取到版本信息")
        }

        // 流内混排各平台 release, 逐条过滤, 首个本平台条目即最新
        for (i in 0 until entries.length) {
            val entry = entries.item(i) as? Element ?: continue

            val idEl = entry.getElementsByTagNameNS(ATOM_NS, "id").item(0) as? Element
            val tag = idEl?.textContent?.trim()?.substringAfterLast('/') ?: ""
            if (!isPlatformTag(tag)) continue

            var releaseUrl = RELEASE_PAGE_URL
            val links = entry.getElementsByTagNameNS(ATOM_NS, "link")
            for (j in 0 until links.length) {
                val el = links.item(j) as? Element ?: continue
                if (el.getAttribute("rel") == "alternate" && "/releases/tag/" in (el.getAttribute("href") ?: "")) {
                    releaseUrl = el.getAttribute("href")
                    break
                }
            }

            val contentEl = entry.getElementsByTagNameNS(ATOM_NS, "content").item(0) as? Element
            val notes = contentEl?.textContent?.let { stripHtml(it) } ?: ""
            return Triple(tag, releaseUrl, notes)
        }
        throw OpenCodeApiException("Releases 订阅流中暂无 $PLATFORM_SUFFIX 版本")
    }

    /** Check latest release vs local version. Throws on network/parse failure. */
    suspend fun checkUpdate(currentVersion: String): UpdateInfo = withContext(Dispatchers.IO) {
        val ua = "GoGauge/$currentVersion"
        val errors = mutableListOf<String>()
        var tag = ""
        var releaseUrl = RELEASE_PAGE_URL
        var notes = ""

        try {
            // API 按创建时间倒序返回, 首个本平台 (-android) 条目即最新 (desktop parity)
            val data = json.decodeFromString<List<ReleaseResponse>>(
                fetchText(RELEASES_URL, "application/vnd.github+json", ua)
            )
            for (rel in data) {
                if (!isPlatformTag(rel.tagName)) continue
                tag = rel.tagName
                releaseUrl = rel.htmlUrl
                notes = (rel.body ?: "").trim().take(600)
                break
            }
        } catch (e: Exception) {
            // 首次失败仅记录, 交由 Atom 兜底 (desktop parity)
            errors.add(e.message ?: e.toString())
        }

        if (tag.isEmpty()) {
            try {
                val atom = parseAtom(fetchText(ATOM_URL, "application/atom+xml,application/xml", ua))
                tag = atom.first
                releaseUrl = atom.second
                notes = atom.third.take(600)
            } catch (e: Exception) {
                errors.add(e.message ?: e.toString())
            }
        }

        if (tag.isEmpty()) {
            throw OpenCodeApiException(
                "无法连接 GitHub，无法检查更新（${errors.joinToString("；")}）。\n" +
                    "通常是境内直连 GitHub 暂时不可用：请稍后重试，" +
                    "或开启系统代理 / VPN 后再次「检查更新」。",
            )
        }

        val latest = parseVersion(tag)
        val current = parseVersion(currentVersion)
        val hasUpdate = latest != null && current != null && isNewer(latest, current)
        UpdateInfo(
            hasUpdate = hasUpdate,
            current = currentVersion,
            latest = tag,
            releaseUrl = releaseUrl,
            notes = notes,
        )
    }
}
