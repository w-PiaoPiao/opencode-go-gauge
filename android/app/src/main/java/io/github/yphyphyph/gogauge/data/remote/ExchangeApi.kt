package io.github.yphyphyph.gogauge.data.remote

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/** USD→CNY exchange rate — port of server.py _fetch_usd_cny (desktop). */
class ExchangeApi(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(6, TimeUnit.SECONDS)
        .writeTimeout(6, TimeUnit.SECONDS)
        .build(),
) {
    private val json = Json { ignoreUnknownKeys = true }

    @Serializable
    private data class RateResponse(
        @SerialName("rates") val rates: Map<String, Double> = emptyMap(),
    )

    /** Fetch USD→CNY; throws on network failure (caller keeps cached/default value). */
    suspend fun fetchUsdCny(): Double = withContext(Dispatchers.IO) {
        val req = Request.Builder()
            .url("https://open.er-api.com/v6/latest/USD")
            .header("User-Agent", "GoGauge/1.0")
            .header("Accept", "application/json")
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw OpenCodeApiException("汇率接口 HTTP ${resp.code}")
            val body = resp.body?.string() ?: ""
            val data = json.decodeFromString<RateResponse>(body)
            data.rates["CNY"]?.takeIf { it > 0 }
                ?: throw OpenCodeApiException("汇率接口缺少 CNY")
        }
    }
}
