package com.example.apiblueprint.api.routes.api.demo

import com.example.apiblueprint.api.runtime.ApiTransport

public class DemoApi internal constructor(
    transport: ApiTransport,
) : GenDemoApi(transport)
