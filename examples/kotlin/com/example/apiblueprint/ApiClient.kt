package com.example.apiblueprint

import com.example.apiblueprint.endpoints.*
import com.example.apiblueprint.internal.HttpExecutor

public class ApiClient(
    public val config: ApiConfig = ApiConfig(),
) {
    private val executor: HttpExecutor = HttpExecutor(config)
    public val demo: DemoApi = DemoApi(executor)
    public val hello: HelloApi = HelloApi(executor)
}
