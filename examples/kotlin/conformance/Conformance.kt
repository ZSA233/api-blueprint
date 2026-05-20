package com.example.apiblueprint.conformance

import com.example.apiblueprint.api.routes.api.binary.BinaryPacketQuery
import com.example.apiblueprint.api.routes.api.binary.DemoPacket
import com.example.apiblueprint.api.routes.api.binary.DemoPacketBody
import com.example.apiblueprint.api.routes.api.binary.DemoPacketFlagsValues
import com.example.apiblueprint.api.routes.api.binary.DemoPacketHeader
import com.example.apiblueprint.api.routes.api.binary.DemoPacketItem
import com.example.apiblueprint.api.routes.api.conflict.ConflictDefaultQuery as ApiConflictDefaultQuery
import com.example.apiblueprint.api.routes.api.demo.DemoErrorDemoQuery
import com.example.apiblueprint.api.routes.api.demo.DemoFormSubmitForm
import com.example.apiblueprint.api.routes.api.demo.DemoPutDemoJson
import com.example.apiblueprint.api.routes.api.demo.DemoPutDemoQuery
import com.example.apiblueprint.api.routes.api.demo.DemoTestPostJson
import com.example.apiblueprint.api.routes.api.demo.AssistantClientMessageVariants
import com.example.apiblueprint.api.routes.api.demo.AssistantServerMessage
import com.example.apiblueprint.api.routes.api.demo.AssistantServerMessageHandlers
import com.example.apiblueprint.api.routes.api.demo.SweepStreamMessage
import com.example.apiblueprint.api.routes.api.demo.SweepStreamMessageHandlers
import com.example.apiblueprint.api.routes.api.demo.dispatchAssistantServerMessage
import com.example.apiblueprint.api.routes.api.demo.dispatchSweepStreamMessage
import com.example.apiblueprint.api.runtime.ApiClient
import com.example.apiblueprint.api.runtime.ApiError
import com.example.apiblueprint.api.runtime.AssistantCancel
import com.example.apiblueprint.api.runtime.AssistantDelta
import com.example.apiblueprint.api.runtime.AssistantDone
import com.example.apiblueprint.api.runtime.AssistantInput
import com.example.apiblueprint.api.runtime.AssistantOpen
import com.example.apiblueprint.api.runtime.ConnectionClose
import com.example.apiblueprint.api.runtime.DemoErr
import com.example.apiblueprint.api.runtime.KeywordEnum
import com.example.apiblueprint.api.runtime.SweepLog
import com.example.apiblueprint.api.runtime.SweepOpen
import com.example.apiblueprint.api.runtime.SweepProgress
import com.example.apiblueprint.api.runtime.SweepState
import com.example.apiblueprint.api.runtime.resolveApiToast
import com.example.apiblueprint.api.transports.http.HttpApiConfig
import com.example.apiblueprint.api.transports.http.createHttpApiClient
import com.example.apiblueprint.alt.routes.alt.conflict.ConflictDefaultQuery as AltConflictDefaultQuery
import com.example.apiblueprint.alt.runtime.ApiClient as AltApiClient
import com.example.apiblueprint.alt.runtime.KeywordEnum as AltKeywordEnum
import com.example.apiblueprint.alt.transports.http.HttpApiConfig as AltHttpApiConfig
import com.example.apiblueprint.alt.transports.http.createHttpApiClient as createAltHttpApiClient
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient

fun main(args: Array<String>) = runBlocking {
    val baseUrl = args.firstOrNull()?.trimEnd('/') ?: error("base URL argument is required")
    val selected = scenarioSet(args.getOrNull(1) ?: "rpc,binary,form,error,naming,sse,websocket")
    val httpClient = OkHttpClient()
    val altHttpClient = OkHttpClient()
    try {
        val client = createHttpApiClient(HttpApiConfig(baseUrl = baseUrl), httpClient)
        val altClient = createAltHttpApiClient(AltHttpApiConfig(baseUrl = baseUrl), altHttpClient)

        if ("rpc" in selected) {
            checkRpc(client)
        }
        if ("form" in selected) {
            checkForm(client)
        }
        if ("binary" in selected) {
            checkBinary(client)
        }
        if ("error" in selected) {
            checkTypedErrors(client)
        }
        if ("naming" in selected) {
            checkNaming(client, altClient)
        }
        if ("sse" in selected) {
            checkSse(client)
        }
        if ("websocket" in selected) {
            checkWebSocket(client)
        }
        println("kotlin conformance passed")
    } finally {
        shutdownOkHttp(httpClient)
        shutdownOkHttp(altHttpClient)
    }
}

private fun scenarioSet(raw: String): Set<String> =
    raw.split(",").map { it.trim() }.filter { it.isNotEmpty() }.toSet()

private fun shutdownOkHttp(client: OkHttpClient) {
    client.dispatcher.executorService.shutdown()
    client.connectionPool.evictAll()
    client.cache?.close()
}

private suspend fun checkRpc(client: ApiClient) {
    val post = client.demo.testPost(DemoTestPostJson(req1 = "kotlin", req2 = 7))
    assertEquals(listOf("test_post", "kotlin"), post.list, "testPost.list")
    assertEquals(7L, post.map["req2"]?.haha, "testPost.map.req2")

    val put = client.demo.putDemo(
        query = DemoPutDemoQuery(arg1 = "query", arg2 = 3.5f),
        json = DemoPutDemoJson(req1 = "body", req2 = 9),
    )
    assertEquals(listOf("query", "body"), put.list, "putDemo.list")
    assertEquals(9, put.anonKv.kv1, "putDemo.anonKv.kv1")
}

private suspend fun checkForm(client: ApiClient) {
    val response = client.demo.formSubmit(DemoFormSubmitForm(title = "kotlin-form", count = 4, enabled = true))
    assertEquals("kotlin-form", response.summary, "formSubmit.summary")
    assertEquals(4, response.count, "formSubmit.count")
    assertEquals(true, response.enabled, "formSubmit.enabled")
}

private suspend fun checkBinary(client: ApiClient) {
    val response = client.binary.packet(BinaryPacketQuery(trace = "kotlin-typed"), buildPacket())
    assertEquals("kotlin-typed", response.trace, "binary.trace")
    assertEquals(1, response.version, "binary.version")
    assertEquals(2, response.itemCount, "binary.itemCount")
    assertEquals("payload-ok", response.payload, "binary.payload")
    assertEquals(8.0, response.scoreSum, "binary.scoreSum")
    assertEquals("alpha", response.firstLabel, "binary.firstLabel")
    assertEquals(listOf(11, 22), response.itemIds, "binary.itemIds")
    assertEquals(12, response.checksum, "binary.checksum")
}

private suspend fun checkTypedErrors(client: ApiClient) {
    val ok = client.demo.errorDemo(DemoErrorDemoQuery(mode = "ok"))
    assertEquals("ok", ok.status, "errorDemo.ok")

    val rateLimited = expectApiError {
        client.demo.errorDemo(DemoErrorDemoQuery(mode = "rate_limit"))
    }
    assertEquals(DemoErr.RATE_LIMITED, rateLimited.code, "rateLimit.code")
    assertEquals("DemoErr.RATE_LIMITED", rateLimited.id, "rateLimit.id")
    assertEquals(
        "请等待 30 秒后重试",
        resolveApiToast(rateLimited.toast, fallbackMessage = rateLimited.message.orEmpty()),
        "rateLimit.toast",
    )

    val unknown = expectApiError {
        client.demo.errorDemo(DemoErrorDemoQuery(mode = "unknown"))
    }
    assertEquals("", unknown.id, "unknown.id")
    assertEquals(70001, unknown.code, "unknown.code")
    assertEquals("example undefined business error", unknown.message ?: "", "unknown.message")
}

private suspend fun checkNaming(client: ApiClient, altClient: AltApiClient) {
    val api = client.conflict.default(ApiConflictDefaultQuery(`class` = "kotlin-api"))
    assertEquals("api-default", api.default, "apiConflict.default")
    assertEquals("kotlin-api", api.`class`, "apiConflict.class")
    assertEquals(KeywordEnum.DEFAULT, api.enum, "apiConflict.enum")

    val alt = altClient.conflict.default(AltConflictDefaultQuery(`class` = "kotlin-alt"))
    assertEquals("alt-default", alt.default, "altConflict.default")
    assertEquals("kotlin-alt", alt.`class`, "altConflict.class")
    assertEquals(AltKeywordEnum.CLASS, alt.enum, "altConflict.enum")
}

private suspend fun checkSse(client: ApiClient) {
    val stream = client.demo.subscribeSweepEvents(SweepOpen(runId = "kotlin-sse"))
    val message = CompletableDeferred<SweepStreamMessage>()
    val close = CompletableDeferred<ConnectionClose>()
    stream.onMessage { if (!message.isCompleted) message.complete(it) }
    stream.onClose { if (!close.isCompleted) close.complete(it) }

    val received = withTimeout(5_000) { message.await() }
    val status = dispatchSweepStreamMessage(received, object : SweepStreamMessageHandlers<String> {
        override fun state(data: SweepState, message: SweepStreamMessage): String = data.status
        override fun progress(data: SweepProgress, message: SweepStreamMessage): String =
            "${data.current}/${data.total}"
        override fun log(data: SweepLog, message: SweepStreamMessage): String = "${data.level}:${data.message}"
    })
    assertContains(status, "kotlin-sse", "sse.message")

    val closed = withTimeout(5_000) { close.await() }
    assertEquals(1000, closed.code, "sse.close.code")
    assertEquals("example stream complete", closed.reason, "sse.close.reason")
}

private suspend fun checkWebSocket(client: ApiClient) {
    val channel = client.demo.openAssistantSession(AssistantOpen(sessionId = "kotlin-ws"))
    val message = CompletableDeferred<AssistantServerMessage>()
    val close = CompletableDeferred<ConnectionClose>()
    channel.onMessage { if (!message.isCompleted) message.complete(it) }
    channel.onClose { if (!close.isCompleted) close.complete(it) }
    channel.send(AssistantClientMessageVariants.input(AssistantInput(text = "hello")))

    val received = withTimeout(5_000) { message.await() }
    val text = dispatchAssistantServerMessage(received, object : AssistantServerMessageHandlers<String> {
        override fun delta(data: AssistantDelta, message: AssistantServerMessage): String = data.text
        override fun done(data: AssistantDone, message: AssistantServerMessage): String = data.messageId
        override fun log(data: SweepLog, message: AssistantServerMessage): String = "${data.level}:${data.message}"
    })
    assertContains(text, "kotlin-ws", "websocket.message.session")
    assertContains(text, "hello", "websocket.message.text")

    channel.send(AssistantClientMessageVariants.cancel(AssistantCancel(reason = "kotlin complete")))
    val closed = withTimeout(5_000) { close.await() }
    assertEquals(1000, closed.code, "websocket.close.code")
    assertEquals("kotlin complete", closed.reason, "websocket.close.reason")
}

private fun buildPacket(): DemoPacket {
    val payload = "payload-ok".encodeToByteArray()
    return DemoPacket(
        header = DemoPacketHeader(
            flags = DemoPacketFlagsValues.HasPayload + DemoPacketFlagsValues.HasScores,
            shortCode = 0x010203,
            signedDelta = 7,
            itemCount = 2,
            payloadLen = payload.size.toLong(),
        ),
        body = DemoPacketBody(
            items = listOf(
                DemoPacketItem(
                    id = 11,
                    enabled = true,
                    value = 1.25,
                    labelLen = 5,
                    label = "alpha".encodeToByteArray(),
                ),
                DemoPacketItem(
                    id = 22,
                    enabled = false,
                    value = 2.5,
                    labelLen = 4,
                    label = "beta".encodeToByteArray(),
                ),
            ),
            payload = payload,
            scores = listOf(3.5, 4.5),
            checksum = 12,
        ),
    )
}

private suspend fun expectApiError(action: suspend () -> Unit): ApiError {
    try {
        action()
    } catch (error: ApiError) {
        assertEquals("api.demo.get.errordemo", error.routeId, "ApiError.routeId")
        return error
    }
    error("expected ApiError")
}

private fun assertEquals(expected: Any?, actual: Any?, label: String) {
    if (expected != actual) {
        error("$label=$actual expected $expected")
    }
}

private fun assertContains(actual: String, expectedPart: String, label: String) {
    if (!actual.contains(expectedPart)) {
        error("$label=$actual expected to contain $expectedPart")
    }
}
