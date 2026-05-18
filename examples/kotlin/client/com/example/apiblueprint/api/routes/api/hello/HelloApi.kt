package com.example.apiblueprint.api.routes.api.hello

import com.example.apiblueprint.api.runtime.ApiTransport

public class HelloApi internal constructor(
    transport: ApiTransport,
) : GenHelloApi(transport)
