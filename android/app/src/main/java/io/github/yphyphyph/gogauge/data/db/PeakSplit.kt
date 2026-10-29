package io.github.yphyphyph.gogauge.data.db

import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

/**
 * DeepSeek 峰谷分档规则 — 与桌面 `app/db.py` 的 `_peak_tier_sql` / `_PRICING_GATES`
 * / `_CN_HOLIDAYS` 同口径 (desktop v2.2.2, 含审查修复 P2-1/I9)。
 *
 * 背景: DeepSeek 两条 flash 主线自各自起始门起实行两档计价 —— 北京时间周一至周五
 * 09:00-12:00 / 14:00-18:00 为高峰, 其余时段 (含周末与法定节假日全天) 为空闲, 空闲价
 * 恰为高峰价的一半。区间左闭右开 (11:59:59 仍为高峰价, 12:00:07 已切空闲价);
 * 调休补班的周六实测仍按空闲价, 故判定只看「周一到周五 + 非法定节假日」, 不看调休上班日。
 *
 * 纯展示层: 只改统计页的模型标签 (拆成「模型 峰」「模型 谷」两条), 不动任何落库数据。
 *
 * 时区: created_at / time_bucket 均以 UTC 存, 北京峰窗换成 UTC 后是固定的
 * 01:00-03:59 / 06:00-09:59, 且窗口内 UTC 日期与北京日期相同, 因此 SQL 侧直接做
 * 字符串比较即可 (不要改成每行 datetime(+8h) 再多次 strftime, 那会让 30 天聚合慢 2~6 倍)。
 */
object PeakSplit {

    /**
     * 计价起始门 (UTC 日 + UTC 时刻): 北京时间 00:00 = 前一 UTC 日 16:00。
     *
     * 两条 flash 主线的两档计价起始日不同 —— 用统一门会把 2026-08-17 起就已按峰谷
     * 计费的 deepseek-v4-flash 记录错当成单一价 (P2-1/I9; 真实账单逐条反证)。
     */
    val PRICING_GATES: Map<String, Pair<String, String>> = linkedMapOf(
        "deepseek-v4.1-flash" to ("2026-09-09" to "16:00"), // 北京 2026-09-10 00:00
        "deepseek-v4-flash" to ("2026-08-16" to "16:00"),   // 北京 2026-08-17 00:00
    )

    /** 参与分档的模型 (两档计价只适用于 flash 主线, 精确名可带 provider/ 前缀)。 */
    val MODELS: List<String> = PRICING_GATES.keys.toList()

    const val TIER_PEAK = "peak"
    const val TIER_OFF = "off"
    /** 展示后缀 (与桌面 `_PEAK_SUFFIX` 逐字一致: 前导空格 + 单字)。 */
    const val SUFFIX_PEAK = " 峰"
    const val SUFFIX_OFF = " 谷"

    /**
     * 国务院办公厅《关于2026年部分节假日安排的通知》放假日 (调休上班的周末不在其中)。
     * 起始门之后的窗口只落在 2026 年; 新增年份需补表, 没有表的年份只按周末判定。
     */
    val CN_HOLIDAYS: Set<String> = buildSet {
        addAll(listOf("2026-01-01", "2026-01-02", "2026-01-03"))
        for (d in 15..23) add("2026-02-%02d".format(d))
        addAll(listOf("2026-04-04", "2026-04-05", "2026-04-06"))
        for (d in 1..5) add("2026-05-%02d".format(d))
        addAll(listOf("2026-06-19", "2026-06-20", "2026-06-21"))
        addAll(listOf("2026-09-25", "2026-09-26", "2026-09-27"))
        for (d in 1..7) add("2026-10-%02d".format(d))
    }

    /**
     * 高峰窗口 (UTC 小时, 整点对齐): 北京 09:00-12:00 / 14:00-18:00 = UTC
     * 01:00-03:59 / 06:00-09:59。对 HH:MM 串来说等价于小时 IN (...), 少一次区间比较。
     */
    private val PEAK_UTC_HOURS = listOf("01", "02", "03", "06", "07", "08", "09")

    /**
     * 模型名匹配 SQL: 精确名或 `provider/` 前缀名 (与 scripts/peak_split.py 同规则)。
     * 用 `COLLATE NOCASE` / 默认大小写不敏感的 LIKE, 避免每行多次 `lower()` 调用。
     */
    fun modelMatchSql(col: String, model: String): String =
        "($col COLLATE NOCASE = '$model' OR $col LIKE '%/$model')"

    /** 命中分档模型的谓词 (作用于 model 列)。 */
    val flashSql: String =
        "(" + MODELS.joinToString(" OR ") { modelMatchSql("model", it) } + ")"

    /** 两段式查询的「基准」分支: 排除分档模型, 完全不做 tier 表达式 (性能, 见 P2-1)。 */
    val baseSql: String = "NOT $flashSql"

    /**
     * tier 表达式 + 绑定参数 (法定节假日日期)。
     *
     * 参数必须按 SQL 文本出现顺序绑定 —— 表达式放在 SELECT 列表时, 这些参数要排在
     * WHERE 的参数之前。
     *
     * @param col 时间列名 (`created_at` 明细 / `time_bucket` charts 桶)
     */
    fun tierSql(col: String): Pair<String, List<String>> {
        val holidays = CN_HOLIDAYS.sorted()
        val placeholders = holidays.joinToString(", ") { "?" }
        val date = "substr($col, 1, 10)"
        val hhmm = "substr($col, 12, 5)"
        val hoursIn = PEAK_UTC_HOURS.joinToString(", ") { "'$it'" }
        val inWindow = "substr($col, 12, 2) IN ($hoursIn)"
        val peakCase = "(CASE WHEN $inWindow" +
            " AND strftime('%w', $col) BETWEEN '1' AND '5'" +
            " AND $date NOT IN ($placeholders)" +
            " THEN '$TIER_PEAK' ELSE '$TIER_OFF' END)"
        // 每个模型一个起始门; 门判定用 CASE 归约成 0/1, 外层只写一份 peak_case ——
        // 否则节假日的占位符会随写法重复出现, 调用方绑定参数个数对不上。
        val gateBranches = MODELS.joinToString(" ") { model ->
            val (gateDate, gateHhmm) = PRICING_GATES.getValue(model)
            val sinceStart = "($date > '$gateDate'" +
                " OR ($date = '$gateDate' AND $hhmm >= '$gateHhmm'))"
            "WHEN ${modelMatchSql("model", model)} THEN $sinceStart"
        }
        val gateSql = "CASE $gateBranches ELSE 0 END"
        return "CASE WHEN ($gateSql) THEN $peakCase ELSE '' END" to holidays
    }

    /**
     * 档位 -> 展示用模型名 (非分档模型原样返回)。
     *
     * 查询把 tier 作为独立列返回, 由这里在 Kotlin 侧拼后缀 —— 不在 SQL 里拼
     * (label 表达式若同时出现在 SELECT 与 GROUP BY, 节假日占位符会翻倍)。
     */
    fun labelFor(model: String, tier: String?): String = when (tier) {
        TIER_PEAK -> "$model$SUFFIX_PEAK"
        TIER_OFF -> "$model$SUFFIX_OFF"
        else -> model
    }

    /**
     * 剥掉「峰 / 谷」后缀还原真实模型名。
     *
     * 排除是**模型级**动作 (总量/趋势无法按档拆): 统计页图例给出的是带后缀的名字,
     * 不剥就会 `model NOT IN ('xxx 峰')` 一条也匹配不上, 点图例等于没反应。
     */
    fun stripSuffix(model: String): String {
        val m = model.trim()
        for (suffix in listOf(SUFFIX_PEAK, SUFFIX_OFF)) {
            if (m.endsWith(suffix) && m.length > suffix.length) {
                return m.dropLast(suffix.length)
            }
        }
        return m
    }

    /** 该模型是否参与分档 (精确名或 provider/ 前缀名, 大小写不敏感)。 */
    fun isSplitModel(model: String): Boolean {
        val m = model.trim().lowercase()
        return MODELS.any { m == it || m.endsWith("/$it") }
    }

    /**
     * 单行档位判定 — 与 [tierSql] 逐字段等价 (JVM 单测与文档用; 查询路径走 SQL)。
     *
     * @param createdAtUtc UTC 时间串 (`2026-10-27T01:30:00Z` / `2026-10-27 01:30:00`)
     * @return `"peak"` / `"off"`; 非分档模型或起始门之前返回 null (不拆)
     */
    fun tierOf(createdAtUtc: String, model: String): String? {
        if (!isSplitModel(model)) return null
        val gate = PRICING_GATES.entries.firstOrNull { (name, _) ->
            val m = model.trim().lowercase()
            m == name || m.endsWith("/$name")
        }?.value ?: return null
        val ts = parseUtc(createdAtUtc) ?: return null
        val (gateDate, gateHhmm) = gate
        val dateText = "%04d-%02d-%02d".format(ts.year, ts.monthValue, ts.dayOfMonth)
        val hhmmText = "%02d:%02d".format(ts.hour, ts.minute)
        val sinceStart = dateText > gateDate ||
            (dateText == gateDate && hhmmText >= gateHhmm)
        if (!sinceStart) return null
        val weekday = ts.dayOfWeek
        val isWorkday = weekday != DayOfWeek.SATURDAY && weekday != DayOfWeek.SUNDAY
        val inWindow = ts.hour in listOf(1, 2, 3, 6, 7, 8, 9)
        return if (inWindow && isWorkday && dateText !in CN_HOLIDAYS) TIER_PEAK else TIER_OFF
    }

    /** 解析 UTC 时间串: 支持 "YYYY-MM-DDTHH:MM[:SS[.fff]]Z/±HH:MM" 与 "YYYY-MM-DD HH:MM:SS"。 */
    internal fun parseUtc(text: String): LocalDateTime? {
        val t = text.trim()
        if (t.isEmpty()) return null
        return try {
            // 带偏移 (Z / +08:00): 先换算到 UTC 再取本地时刻 —— 直接 substr 取数字会把
            // "+08:00" 的本地时刻当成 UTC, 峰谷判定整体偏 8 小时
            OffsetDateTime.parse(t)
                .withOffsetSameInstant(ZoneOffset.UTC)
                .toLocalDateTime()
        } catch (e: Exception) {
            try {
                val spaced = t.replace('T', ' ')
                LocalDateTime.parse(
                    if (spaced.length >= 19) spaced.substring(0, 19) else spaced,
                    java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"),
                )
            } catch (e2: Exception) {
                try {
                    LocalDate.parse(t.substring(0, 10)).atStartOfDay()
                } catch (e3: Exception) {
                    null
                }
            }
        }
    }
}
