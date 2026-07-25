package com.example.apiblueprint.runtime.routes.runtime.status

import com.example.apiblueprint.runtime.runtime.*

public class StatusService : StatusServiceStub() {

    /**
     * Runtime root naming example
     * GET /runtime/status/current
     */
    public override suspend fun runtimeCurrentStatus(
    ): RuntimeStatus {
        return super.runtimeCurrentStatus(
        )
    }

}
