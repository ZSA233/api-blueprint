package com.example.apiblueprint.api.routes.api.hello

import com.example.apiblueprint.api.runtime.*

public class HelloService : HelloServiceStub() {

    /**
     * 这是abc的summary
     * GET /api/hello/abc
     */
    public override suspend fun abc(
        query: HelloAbcQuery
    ): HelloAbcResponse {
        return super.abc(
            query = query
        )
    }

    /**
     * map-enum
     * GET /api/hello/map-enum
     */
    public override suspend fun mapEnum(
    ): HelloMapEnumResponse {
        return super.mapEnum(
        )
    }

    /**
     * list-enum
     * GET /api/hello/list-enum
     */
    public override suspend fun listEnum(
    ): HelloListEnumResponse {
        return super.listEnum(
        )
    }

    /**
     * string
     * GET /api/hello/string
     */
    public override suspend fun string(
    ): HelloStringResponse {
        return super.string(
        )
    }

    /**
     * uint64
     * GET /api/hello/uint64
     */
    public override suspend fun uint64(
    ): HelloUint64Response {
        return super.uint64(
        )
    }

    /**
     * string-enum
     * GET /api/hello/string-emun
     */
    public override suspend fun stringEmun(
    ): HelloStringEmunResponse {
        return super.stringEmun(
        )
    }

    /**
     * hello-way
     * GET /api/hello/hello-way
     */
    public override suspend fun helloWay(
        query: HelloHelloWayQuery
    ): Unit {
        return super.helloWay(
            query = query
        )
    }

}
