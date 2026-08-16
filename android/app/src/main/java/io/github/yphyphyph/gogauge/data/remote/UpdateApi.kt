package io.github.yphyphyph.gogauge.data.remote

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

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
 */
class UpdateApi(
    private val client: OkHttpClient = OpenCodeApi.defaultClient(),
) {
    companion object {
        const val REPO = "yphyphyph/opencode-go-gauge"
        const val RELEASES_URL = "https://api.github.com/repos/$REPO/releases/latest"
        const val RELEASE_PAGE_URL = "https://github.com/$REPO/releases/latest"
        private const val TIMEOUT_MS = 8_000L
        private val TAG_RE = Regex("""^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$""")
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

    /** Check latest release vs local version. Throws on network/parse failure. */
    suspend fun checkUpdate(currentVersion: String): UpdateInfo = withContext(Dispatchers.IO) {
        val req = Request.Builder()
            .url(RELEASES_URL)
            .header("User-Agent", "GoGauge/$currentVersion")
            .header("Accept", "application/vnd.github+json")
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw OpenCodeApiException("GitHub API HTTP ${resp.code}")
            val data = json.decodeFromString<ReleaseResponse>(resp.body?.string() ?: "")
            val latest = parseVersion(data.tagName)
            val current = parseVersion(currentVersion)
            val hasUpdate = latest != null && current != null && isNewer(latest, current)
            UpdateInfo(
                hasUpdate = hasUpdate,
                current = currentVersion,
                latest = data.tagName,
                releaseUrl = data.htmlUrl,
                notes = (data.body ?: "").trim().take(600),
            )
        }
    }
}
