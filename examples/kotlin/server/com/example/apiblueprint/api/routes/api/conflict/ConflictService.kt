package com.example.apiblueprint.api.routes.api.conflict

import com.example.apiblueprint.api.runtime.*

public class ConflictService : ConflictServiceStub() {

    /**
     * Naming conflict example
     * GET /api/conflict/default
     */
    public override suspend fun default(
        query: ConflictDefaultQuery
    ): ConflictModel {
        return super.default(
            query = query
        )
    }

}
