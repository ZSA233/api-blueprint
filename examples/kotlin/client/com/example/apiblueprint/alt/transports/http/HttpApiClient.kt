package com.example.apiblueprint.alt.transports.http

import com.example.apiblueprint.alt.runtime.ApiClient
import okhttp3.OkHttpClient

public fun createHttpApiClient(
    config: HttpApiConfig = HttpApiConfig(),
    httpClient: OkHttpClient = OkHttpClient(),
): ApiClient {
    return ApiClient(OkHttpApiTransport(config, httpClient))
}
