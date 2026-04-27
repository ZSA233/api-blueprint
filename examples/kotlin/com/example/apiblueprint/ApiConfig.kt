package com.example.apiblueprint

import okhttp3.OkHttpClient

public data class ApiConfig(
    public val baseUrl: String = "http://localhost:2333",
    public val httpClient: OkHttpClient = OkHttpClient(),
    public val defaultHeaders: suspend () -> Map<String, String> = { emptyMap() },
)
