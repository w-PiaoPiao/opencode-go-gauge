package io.github.yphyphyph.gogauge.data.remote

import io.github.yphyphyph.gogauge.data.model.UsageRecord

/**
 * server-fn usage response parser — 1:1 port of opencode_api.py (desktop).
 * Compatible with GET (no space: id:"usg_...") and POST (space: id: "usg_...") formats.
 */
object UsageParser {

    private val RECORD_ANCHOR = Regex("""id:\s*"(usg_[^"]+)"""")
    private val PLAN_RE = Regex(
        """id:\s*"(usg_[^"]+)"[^}]*?enrichment:\${'$'}R\[\d+\]=\{plan:"([^"]+)"\}""",
        setOf(RegexOption.DOT_MATCHES_ALL),
    )
    private val CREATED_RE = Regex("""timeCreated:\s*\${'$'}R\[\d+\]\s*=\s*new Date\("([^"]+)"\)""")

    private fun parseNumField(body: String, name: String): Int {
        val m = Regex("""${Regex.escape(name)}:\s*(\d+|null)""").find(body) ?: return 0
        val v = m.groupValues[1]
        return if (v == "null") 0 else v.toIntOrNull() ?: 0
    }

    /** cost 字段用 Long: costRaw 单位 1e-8 USD, Int 在单条 > $21.47 时溢出归零. */
    private fun parseLongField(body: String, name: String): Long {
        val m = Regex("""${Regex.escape(name)}:\s*(\d+|null)""").find(body) ?: return 0
        val v = m.groupValues[1]
        return if (v == "null") 0 else v.toLongOrNull() ?: 0
    }

    private fun parseStrField(body: String, name: String): String {
        val m = Regex("""${Regex.escape(name)}:\s*"([^"]*)"""").find(body)
        return m?.groupValues?.get(1) ?: ""
    }

    /** Parse one server-fn response body into UsageRecord list. */
    fun parseUsageResponse(text: String): List<UsageRecord> {
        val plans = HashMap<String, String>()
        for (m in PLAN_RE.findAll(text)) {
            plans[m.groupValues[1]] = m.groupValues[2]
        }

        val anchors = RECORD_ANCHOR.findAll(text).toList()
        val records = mutableListOf<UsageRecord>()
        for (i in anchors.indices) {
            val m = anchors[i]
            val end = if (i + 1 < anchors.size) anchors[i + 1].range.first else text.length
            val body = text.substring(m.range.last + 1, end)
            val created = CREATED_RE.find(body) ?: continue
            val usgId = m.groupValues[1]
            records += UsageRecord(
                usgId = usgId,
                createdAt = created.groupValues[1],
                model = parseStrField(body, "model"),
                provider = parseStrField(body, "provider"),
                inputTokens = parseNumField(body, "inputTokens"),
                outputTokens = parseNumField(body, "outputTokens"),
                reasoningTokens = parseNumField(body, "reasoningTokens"),
                cacheReadTokens = parseNumField(body, "cacheReadTokens"),
                cacheWrite5mTokens = parseNumField(body, "cacheWrite5mTokens"),
                cacheWrite1hTokens = parseNumField(body, "cacheWrite1hTokens"),
                costRaw = parseLongField(body, "cost"),
                keyId = parseStrField(body, "keyID"),
                sessionId = parseStrField(body, "sessionID"),
                plan = plans[usgId],
            )
        }
        return records
    }
}
