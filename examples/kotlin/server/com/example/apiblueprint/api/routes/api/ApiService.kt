package com.example.apiblueprint.api.routes.api

import com.example.apiblueprint.api.runtime.*

public class ApiService : ApiServiceStub() {

    /**
     * helloChannel
     * CHANNEL /api/ws
     */
    public override suspend fun helloChannel(
        channel: ApiServerChannel<HelloChannelMessage, HelloChannelMessage, DefaultConnectionClose>
    ): Unit {
        return super.helloChannel(
            channel = channel
        )
    }

}
