package com.example.apiblueprint.api.transports.http;

import com.example.apiblueprint.api.runtime.ApiClient;

public class HttpApiClient extends ApiClient {
    public HttpApiClient() {
        this(new GenHttpApiConfig());
    }

    public HttpApiClient(GenHttpApiConfig config) {
        super(new GenJdkHttpApiTransport(config));
    }
}