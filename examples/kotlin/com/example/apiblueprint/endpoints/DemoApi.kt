package com.example.apiblueprint.endpoints

import com.example.apiblueprint.internal.HttpExecutor
import com.example.apiblueprint.models.*
import kotlinx.serialization.builtins.serializer

public class DemoApi internal constructor(
    private val executor: HttpExecutor,
) {

    public suspend fun abc(
        query: DemoAbcQuery,
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<ApiDemoA> {
        return executor.request(
            method = "GET",
            path = "/api/demo/abc",
            query = query.toQueryMap(),
            headers = headers,
            responseSerializer = GeneralResponse.serializer(ApiDemoA.serializer()),
        )
    }

    public suspend fun testPost(
        body: DemoTestPostJson,
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<DemoTestPostResponse> {
        return executor.request(
            method = "POST",
            path = "/api/demo/test_post",
            headers = headers,
            body = body,
            bodySerializer = DemoTestPostJson.serializer(),
            responseSerializer = GeneralResponse.serializer(DemoTestPostResponse.serializer()),
        )
    }

    public suspend fun func1put(
        query: DemoFunc1putQuery,
        body: DemoFunc1putJson,
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<DemoFunc1putResponse> {
        return executor.request(
            method = "PUT",
            path = "/api/demo/1put",
            query = query.toQueryMap(),
            headers = headers,
            body = body,
            bodySerializer = DemoFunc1putJson.serializer(),
            responseSerializer = GeneralResponse.serializer(DemoFunc1putResponse.serializer()),
        )
    }

    public suspend fun postDeprecated(
        body: DemoPostDeprecatedJson,
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<DemoPostDeprecatedResponse> {
        return executor.request(
            method = "POST",
            path = "/api/demo/post_deprecated",
            headers = headers,
            body = body,
            bodySerializer = DemoPostDeprecatedJson.serializer(),
            responseSerializer = GeneralResponse.serializer(DemoPostDeprecatedResponse.serializer()),
        )
    }

    public suspend fun raw(
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<DemoRawResponse> {
        return executor.request(
            method = "POST",
            path = "/api/demo/raw",
            headers = headers,
            responseSerializer = GeneralResponse.serializer(DemoRawResponse.serializer()),
        )
    }

    public suspend fun mapModel(
        headers: Map<String, String> = emptyMap(),
    ): GeneralResponse<DemoMapModelResponse> {
        return executor.request(
            method = "POST",
            path = "/api/demo/map_model",
            headers = headers,
            responseSerializer = GeneralResponse.serializer(DemoMapModelResponse.serializer()),
        )
    }

    private fun DemoAbcQuery.toQueryMap(): Map<String, String?> = mapOf(
        "arg1" to arg1?.toString(),
        "arg3" to arg3?.toString(),
        "arg2" to arg2?.toString()
    )

    private fun DemoFunc1putQuery.toQueryMap(): Map<String, String?> = mapOf(
        "arg1" to arg1?.toString(),
        "arg2" to arg2?.toString(),
        "arg3" to arg3?.toString()
    )
}
