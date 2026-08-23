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
        const val REPO = "yphyphyph/opencode-go-gauge"
        const val RELEASES_URL = "https://api.github.com/repos/$REPO/releases/latest"
        const val ATOM_URL = "https://github.com/$REPO/releases.atom"
        const val RELEASE_PAGE_URL = "https://github.com/$REPO/releases/latest"
        // 境内直连 GitHub 间歇性 502/超时/重置, 自动重试提高成功率 (desktop parity)
        private const val MAX_ATTEMPTS = 3
        private const val RETRY_SLEEP_MS = 800L
        private const val ATOM_NS = "http://www.w3.org/2005/Atom"
        private val TAG_RE = Regex("""^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$""")
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

    private fun parseVersion(text: String): Triple<Int, Int, Int>? {
        val m = TAG_RE.matchEntire(text.trim()) ?: return null
        return Triple(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].toInt())
    }

    private fun isNewer(latest: Triple<Int, Int, Int>, current: Triple<Int, Int, Int>): Boolean {
        return latest.first > current.first ||
            (latest.first == current.first &&
                (latest.second > current.second ||
                    (latest.second == current.second && latest.third > current.third)))
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

    /** 从 Releases Atom 流解析最新 release (desktop _fetch_latest_atom parity). */
    private fun parseAtom(text: String): Triple<String, String, String> {
        val factory = DocumentBuilderFactory.newInstance()
        factory.isNamespaceAware = true
        val doc = factory.newDocumentBuilder().parse(ByteArrayInputStream(text.toByteArray()))
        val entry = doc.getElementsByTagNameNS(ATOM_NS, "entry").item(0) as? Element
            ?: throw OpenCodeApiException("GitHub Releases 订阅流为空，未获取到版本信息")

        val idEl = entry.getElementsByTagNameNS(ATOM_NS, "id").item(0) as? Element
        val tag = idEl?.textContent?.trim()?.substringAfterLast('/') ?: ""

        var releaseUrl = RELEASE_PAGE_URL
        val links = entry.getElementsByTagNameNS(ATOM_NS, "link")
        for (i in 0 until links.length) {
            val el = links.item(i) as? Element ?: continue
            if (el.getAttribute("rel") == "alternate" && "/releases/tag/" in (el.getAttribute("href") ?: "")) {
                releaseUrl = el.getAttribute("href")
                break
            }
        }

        val contentEl = entry.getElementsByTagNameNS(ATOM_NS, "content").item(0) as? Element
        val notes = contentEl?.textContent?.let { stripHtml(it) } ?: ""
        return Triple(tag, releaseUrl, notes)
    }

    /** Check latest release vs local version. Throws on network/parse failure. */
    suspend fun checkUpdate(currentVersion: String): UpdateInfo = withContext(Dispatchers.IO) {
        val ua = "GoGauge/$currentVersion"
        val errors = mutableListOf<String>()
        var tag = ""
        var releaseUrl = RELEASE_PAGE_URL
        var notes = ""

        try {
            val data = json.decodeFromString<ReleaseResponse>(
                fetchText(RELEASES_URL, "application/vnd.github+json", ua)
            )
            tag = data.tagName
            releaseUrl = data.htmlUrl
            notes = (data.body ?: "").trim().take(600)
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
