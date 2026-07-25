package com.example.apiblueprint.legacy.routes.legacy.legacyjson

import com.example.apiblueprint.legacy.runtime.*

public class LegacyJsonService : LegacyJsonServiceStub() {

    /**
     * Legacy JSON compatibility example
     * GET /legacy-json/compat
     */
    public override suspend fun legacyJsonCompat(
    ): LegacyJsonCompatPayload {
        return super.legacyJsonCompat(
        )
    }

}
