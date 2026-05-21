package com.example.apiblueprint.api.routes.api.conflict

import com.example.apiblueprint.api.runtime.ApiTransport

public class ConflictApi internal constructor(
    transport: ApiTransport,
) : GenConflictApi(transport)
