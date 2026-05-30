package com.example.apiblueprint.runtime.transports.http

import com.example.apiblueprint.runtime.runtime.ApiClient
import okhttp3.OkHttpClient

public fun createHttpApiClient(
    config: HttpApiConfig = HttpApiConfig(),
    httpClient: OkHttpClient = OkHttpClient(),
): ApiClient {
    return ApiClient(OkHttpApiTransport(config, httpClient))
}
