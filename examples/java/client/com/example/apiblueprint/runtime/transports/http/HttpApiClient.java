package com.example.apiblueprint.runtime.transports.http;

import com.example.apiblueprint.runtime.runtime.ApiClient;

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
