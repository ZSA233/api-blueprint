package com.example.apiblueprint.legacy.routes.legacy.room

import com.example.apiblueprint.legacy.runtime.*

public class RoomService : RoomServiceStub() {

    /**
     * Rootless room list example
     * GET /room/list
     */
    public override suspend fun roomList(
    ): RoomRoomListResponse {
        return super.roomList(
        )
    }

}
