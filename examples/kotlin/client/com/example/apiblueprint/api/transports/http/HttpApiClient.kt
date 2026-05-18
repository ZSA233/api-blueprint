package com.example.apiblueprint.api.transports.http

import com.example.apiblueprint.api.runtime.ApiClient
import okhttp3.OkHttpClient

public fun createHttpApiClient(
    config: HttpApiConfig = HttpApiConfig(),
    httpClient: OkHttpClient = OkHttpClient(),
): ApiClient {
    return ApiClient(OkHttpApiTransport(config, httpClient))
}
