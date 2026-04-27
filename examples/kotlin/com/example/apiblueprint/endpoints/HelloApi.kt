package com.example.apiblueprint.endpoints

import com.example.apiblueprint.internal.HttpExecutor
import com.example.apiblueprint.models.*
import kotlinx.serialization.builtins.serializer

public class HelloApi internal constructor(
    private val executor: HttpExecutor,
) {

    public suspend fun abc(
        query: HelloAbcQuery,
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<HelloAbcResponse> {
        return executor.request(
            method = "GET",
            path = "/api/hello/abc",
            query = query.toQueryMap(),
            headers = headers,
            responseSerializer = GeneralResponse.serializer(HelloAbcResponse.serializer()),
        )
    }

    public suspend fun mapEnum(
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<HelloMapEnumResponse> {
        return executor.request(
            method = "GET",
            path = "/api/hello/map-enum",
            headers = headers,
            responseSerializer = GeneralResponse.serializer(HelloMapEnumResponse.serializer()),
        )
    }

    public suspend fun listEnum(
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<HelloListEnumResponse> {
        return executor.request(
            method = "GET",
            path = "/api/hello/list-enum",
            headers = headers,
            responseSerializer = GeneralResponse.serializer(HelloListEnumResponse.serializer()),
        )
    }

    public suspend fun string(
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<HelloStringResponse> {
        return executor.request(
            method = "GET",
            path = "/api/hello/string",
            headers = headers,
            responseSerializer = GeneralResponse.serializer(HelloStringResponse.serializer()),
        )
    }

    public suspend fun uint64(
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<HelloUint64Response> {
        return executor.request(
            method = "GET",
            path = "/api/hello/uint64",
            headers = headers,
            responseSerializer = GeneralResponse.serializer(HelloUint64Response.serializer()),
        )
    }

    public suspend fun stringEmun(
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<HelloStringEmunResponse> {
        return executor.request(
            method = "GET",
            path = "/api/hello/string-emun",
            headers = headers,
            responseSerializer = GeneralResponse.serializer(HelloStringEmunResponse.serializer()),
        )
    }

    public suspend fun helloWay(
        query: HelloHelloWayQuery,
        headers: Map<String, String> = emptyMap(),
    ): Unit {
        return executor.request(
            method = "GET",
            path = "/api/hello/hello-way",
            query = query.toQueryMap(),
            headers = headers,
            responseSerializer = Unit.serializer(),
        )
    }

    private fun HelloAbcQuery.toQueryMap(): Map<String, String?> = mapOf(
        "arg1" to arg1?.toString(),
        "arg3" to arg3?.toString(),
        "arg2" to arg2?.toString(),
        "type" to type.toString()
    )

    private fun HelloHelloWayQuery.toQueryMap(): Map<String, String?> = mapOf(
        "arg1" to arg1?.toString()
    )
}
