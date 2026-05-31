package com.example.apiblueprint.legacy.routes.legacy.room

import com.example.apiblueprint.legacy.runtime.ApiTransport

public class RoomApi internal constructor(
    transport: ApiTransport,
) : GenRoomApi(transport)
