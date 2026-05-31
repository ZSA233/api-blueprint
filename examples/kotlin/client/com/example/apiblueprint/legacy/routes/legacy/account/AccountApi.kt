package com.example.apiblueprint.legacy.routes.legacy.account

import com.example.apiblueprint.legacy.runtime.ApiTransport

public class AccountApi internal constructor(
    transport: ApiTransport,
) : GenAccountApi(transport)
