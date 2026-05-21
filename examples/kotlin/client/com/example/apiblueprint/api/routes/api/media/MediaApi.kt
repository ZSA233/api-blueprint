package com.example.apiblueprint.api.routes.api.media

import com.example.apiblueprint.api.runtime.ApiTransport

public class MediaApi internal constructor(
    transport: ApiTransport,
) : GenMediaApi(transport)
