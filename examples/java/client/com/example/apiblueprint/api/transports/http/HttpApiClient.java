package com.example.apiblueprint.api.transports.http;

import com.example.apiblueprint.api.runtime.ApiClient;

public class HttpApiClient extends ApiClient {
    public static HttpApiClient create(String baseUrl) {
        return new HttpApiClient(new GenHttpApiConfig(baseUrl));
    }

    public HttpApiClient() {
        this(new GenHttpApiConfig());
    }

    public HttpApiClient(GenHttpApiConfig config) {
        super(new GenJdkHttpApiTransport(config));
    }
}
