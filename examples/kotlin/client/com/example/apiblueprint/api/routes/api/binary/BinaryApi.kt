package com.example.apiblueprint.api.routes.api.binary

import com.example.apiblueprint.api.runtime.ApiTransport

public class BinaryApi internal constructor(
    transport: ApiTransport,
) : GenBinaryApi(transport)
