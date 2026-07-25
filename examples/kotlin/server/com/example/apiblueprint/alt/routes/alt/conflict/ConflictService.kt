package com.example.apiblueprint.alt.routes.alt.conflict

import com.example.apiblueprint.alt.runtime.*

public class ConflictService : ConflictServiceStub() {

    /**
     * Alt naming conflict example
     * GET /alt/conflict/default
     */
    public override suspend fun default(
        query: ConflictDefaultQuery
    ): ConflictModel {
        return super.default(
            query = query
        )
    }

}
