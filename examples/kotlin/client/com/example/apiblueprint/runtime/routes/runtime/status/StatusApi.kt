package com.example.apiblueprint.runtime.routes.runtime.status

import com.example.apiblueprint.runtime.runtime.ApiTransport

public class StatusApi internal constructor(
    transport: ApiTransport,
) : GenStatusApi(transport)
