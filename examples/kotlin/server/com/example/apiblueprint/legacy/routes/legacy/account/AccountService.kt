package com.example.apiblueprint.legacy.routes.legacy.account

import com.example.apiblueprint.legacy.runtime.*

public class AccountService : AccountServiceStub() {

    /**
     * Rootless account profile example
     * GET /account/profile
     */
    public override suspend fun accountProfile(
    ): AccountProfile {
        return super.accountProfile(
        )
    }

}
