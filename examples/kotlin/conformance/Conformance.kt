package com.example.apiblueprint.conformance

import com.example.apiblueprint.api.routes.api.binary.BinaryPacketQuery
import com.example.apiblueprint.api.routes.api.binary.BinaryAuditPacketQuery
import com.example.apiblueprint.api.routes.api.binary.AuditPacket
import com.example.apiblueprint.api.routes.api.binary.AuditPacketBody
import com.example.apiblueprint.api.routes.api.binary.AuditPacketFlagsValues
import com.example.apiblueprint.api.routes.api.binary.AuditPacketHeader
import com.example.apiblueprint.api.routes.api.binary.AuditPacketItem
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
import com.example.apiblueprint.api.routes.api.demo.DemoPostDeprecatedJson
import com.example.apiblueprint.api.routes.api.demo.DemoRequestOptionsQuery
import com.example.apiblueprint.api.routes.api.demo.DemoTestPostJson
import com.example.apiblueprint.api.routes.api.hello.HelloAbcQuery
import com.example.apiblueprint.api.routes.api.demo.AssistantClientMessageVariants
import com.example.apiblueprint.api.routes.api.demo.AssistantServerMessage
import com.example.apiblueprint.api.routes.api.demo.AssistantServerMessageHandlers
import com.example.apiblueprint.api.routes.api.demo.SweepStreamMessage
import com.example.apiblueprint.api.routes.api.demo.SweepStreamMessageHandlers
import com.example.apiblueprint.api.routes.api.demo.dispatchAssistantServerMessage
import com.example.apiblueprint.api.routes.api.demo.dispatchSweepStreamMessage
import com.example.apiblueprint.api.routes.api.media.MediaMediaErrorFrameQuery
import com.example.apiblueprint.api.runtime.ApiClient
import com.example.apiblueprint.api.runtime.ApiError
import com.example.apiblueprint.api.runtime.ApiFilePart
import com.example.apiblueprint.api.runtime.ApiRequestOptions
import com.example.apiblueprint.api.runtime.AssistantCancel
import com.example.apiblueprint.api.runtime.AssistantDelta
import com.example.apiblueprint.api.runtime.AssistantDone
import com.example.apiblueprint.api.runtime.AssistantInput
import com.example.apiblueprint.api.runtime.AssistantOpen
import com.example.apiblueprint.api.runtime.ConnectionClose
import com.example.apiblueprint.api.runtime.DemoErr
import com.example.apiblueprint.api.runtime.HelloChannelMsgTypeEnum
import com.example.apiblueprint.api.runtime.KeywordEnum
import com.example.apiblueprint.api.runtime.MapEnum
import com.example.apiblueprint.api.runtime.MediaPreviewRequest
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
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import kotlin.time.Duration.Companion.milliseconds
import kotlin.time.Duration.Companion.seconds

fun main(args: Array<String>) = runBlocking {
    val baseUrl = args.firstOrNull()?.trimEnd('/') ?: error("base URL argument is required")
    val selected = scenarioSet(args.getOrNull(1) ?: "rpc,binary,form,error,naming,sse,websocket,raw,xml,static,header,scalar,enum,map,deprecated,audit-binary,binary-response,media,request-options,media-filename-edge,media-error,single-channel")
    val httpClient = OkHttpClient()
    val altHttpClient = OkHttpClient()
    try {
        val client = createHttpApiClient(HttpApiConfig(baseUrl = baseUrl), httpClient)
        val altClient = createAltHttpApiClient(AltHttpApiConfig(baseUrl = baseUrl), altHttpClient)

        if ("rpc" in selected) {
            checkRpc(client)
        }
        if ("raw" in selected) {
            checkRawHttp(httpClient, "$baseUrl/api/demo/raw", "POST", "", "raw")
        }
        if ("xml" in selected) {
            checkRawHttp(httpClient, "$baseUrl/api/demo/delete\$?arg1=kotlin-xml&arg2=7", "DELETE", "kotlin-xml", "xml")
        }
        if ("static" in selected) {
            checkRawHttp(httpClient, "$baseUrl/static/doc.json", "GET", "", "static.doc")
            checkRawHttp(httpClient, "$baseUrl/static/dochaha", "GET", "hello world", "static")
        }
        if ("header" in selected) {
            checkHeader(httpClient, baseUrl)
        }
        if ("scalar" in selected) {
            checkScalar(client)
        }
        if ("enum" in selected) {
            checkEnum(client)
        }
        if ("map" in selected) {
            checkMap(client)
        }
        if ("deprecated" in selected) {
            checkDeprecated(client)
        }
        if ("form" in selected) {
            checkForm(client)
        }
        if ("binary" in selected) {
            checkBinary(client)
        }
        if ("audit-binary" in selected) {
            checkAuditBinary(client)
        }
        if ("binary-response" in selected) {
            checkBinaryResponse(client)
        }
        if ("media" in selected) {
            checkMedia(client)
        }
        if ("request-options" in selected) {
            checkRequestOptions(baseUrl)
        }
        if ("media-filename-edge" in selected) {
            checkMediaFilenameEdge(client)
        }
        if ("media-error" in selected) {
            checkMediaError(client)
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
        if ("single-channel" in selected) {
            checkRawSingleChannel(httpClient, baseUrl)
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

private suspend fun checkScalar(client: ApiClient) {
    assertEquals("hello-string", client.hello.string(), "hello.string")
    assertEquals(9007199254740991L, client.hello.uint64(), "hello.uint64")
}

private suspend fun checkEnum(client: ApiClient) {
    assertEquals(MapEnum.A, client.hello.stringEmun(), "hello.stringEmun")
    assertEquals(listOf(MapEnum.A, MapEnum.B), client.hello.listEnum(), "hello.listEnum")
}

private suspend fun checkMap(client: ApiClient) {
    val model = client.demo.mapModel()
    assertEquals(101L, model[1]?.haha, "demo.mapModel")
    val hello = client.hello.abc(HelloAbcQuery(type = HelloChannelMsgTypeEnum.PING))
    assertEquals(1L, hello["ping"]?.haha, "hello.abc")
    val enumMap = client.hello.mapEnum()
    assertEquals(11L, enumMap["a"]?.haha, "hello.mapEnum")
}

private suspend fun checkDeprecated(client: ApiClient) {
    val response = client.demo.postDeprecated(DemoPostDeprecatedJson(req1 = "kotlin-deprecated", req2 = 3))
    assertEquals(listOf("kotlin-deprecated"), response.list, "deprecated.list")
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

private suspend fun checkAuditBinary(client: ApiClient) {
    val response = client.binary.auditPacket(BinaryAuditPacketQuery(trace = "kotlin-audit"), buildAuditPacket())
    assertEquals("kotlin-audit", response.trace, "audit.trace")
    assertEquals(2, response.itemCount, "audit.itemCount")
    assertEquals(2, response.checksum, "audit.checksum")
}

private suspend fun checkBinaryResponse(client: ApiClient) {
    val response = client.binary.auditPacketResponse()
    assertEquals(buildAuditPacket(), response, "binaryResponse.packet")
}

private suspend fun checkMedia(client: ApiClient) {
    val preview = client.media.mediaPreview(
        MediaPreviewRequest(
            title = "kotlin-media",
            image = ApiFilePart(filename = "preview.jpg", contentType = "image/jpeg", bytes = sampleJpeg()),
        )
    )
    assertEquals("image/jpeg", preview.contentType, "media.preview.contentType")
    assertStartsWith(preview.body, 0xff, 0xd8, "media.preview.body")

    val frame = client.media.mediaFrame()
    assertEquals("image/jpeg", frame.contentType, "media.frame.contentType")
    assertEquals(true, frame.body.contentEquals(sampleJpeg()), "media.frame.body")

    val download = client.media.mediaDownload()
    assertEquals("media-report.xlsx", download.filename, "media.download.filename")
    assertStartsWith(download.body, 'P'.code, 'K'.code, "media.download.body")

    val dynamic = client.media.mediaDownloadDynamic()
    assertEquals("media-report-dynamic.xlsx", dynamic.filename, "media.dynamic.filename")
    assertStartsWith(dynamic.body, 'P'.code, 'K'.code, "media.dynamic.body")

    val stream = client.media.mediaMjpeg()
    val chunk = stream.use { it.readAllBytes() }.decodeToString()
    assertContains(chunk, "--frame", "media.mjpeg")
}

private suspend fun checkRequestOptions(baseUrl: String) {
    val httpClient = OkHttpClient()
    try {
        val client = createHttpApiClient(
            HttpApiConfig(
                baseUrl = baseUrl,
                defaultHeaders = { mapOf("x-options-default" to "default", "x-options-token" to "default") },
                timeout = 20.milliseconds,
            ),
            httpClient,
        )
        val ok = client.demo.requestOptions(
            DemoRequestOptionsQuery(delayMs = 30),
            options = ApiRequestOptions(
                headers = mapOf("x-options-token" to "per-call"),
                timeout = 1.seconds,
            ),
        )
        assertEquals("ok", ok.status, "requestOptions.status")
        assertEquals(30, ok.delayMs, "requestOptions.delayMs")

        var timedOut = false
        try {
            client.demo.requestOptions(
                DemoRequestOptionsQuery(delayMs = 120),
                options = ApiRequestOptions(
                    headers = mapOf("x-options-token" to "per-call"),
                    timeout = 10.milliseconds,
                ),
            )
        } catch (_: Exception) {
            timedOut = true
        }
        assertEquals(true, timedOut, "requestOptions.shortTimeout")
    } finally {
        shutdownOkHttp(httpClient)
    }
}

private suspend fun checkMediaFilenameEdge(client: ApiClient) {
    val response = client.media.mediaDownloadFilenameEdge()
    assertEquals("媒体报告.xlsx", response.filename, "media.filenameEdge.filename")
    assertStartsWith(response.body, 'P'.code, 'K'.code, "media.filenameEdge.body")
}

private suspend fun checkMediaError(client: ApiClient) {
    val ok = client.media.mediaErrorFrame(MediaMediaErrorFrameQuery(mode = "ok"))
    assertEquals("image/jpeg", ok.contentType, "media.error.contentType")
    assertStartsWith(ok.body, 0xff, 0xd8, "media.error.body")

    val rateLimited = expectApiError("api.media.get.errorframe") {
        client.media.mediaErrorFrame(MediaMediaErrorFrameQuery(mode = "rate_limit"))
    }
    assertEquals(DemoErr.RATE_LIMITED, rateLimited.code, "media.error.code")
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

private fun buildAuditPacket(): AuditPacket =
    AuditPacket(
        header = AuditPacketHeader(flags = AuditPacketFlagsValues.HasItems, itemCount = 2),
        body = AuditPacketBody(
            items = listOf(
                AuditPacketItem(id = 11, code = 101),
                AuditPacketItem(id = 22, code = 202),
            ),
            checksum = 2L,
        ),
    )

private fun sampleJpeg(): ByteArray =
    intArrayOf(
        0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10,
        'J'.code, 'F'.code, 'I'.code, 'F'.code, 0x00, 0x01, 0x01, 0x01, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00, 0xff, 0xd9,
    ).map { it.toByte() }.toByteArray()

private fun checkRawHttp(client: OkHttpClient, url: String, method: String, snippet: String, label: String) {
    val body = if (method == "POST" || method == "PUT" || method == "PATCH") ByteArray(0).toRequestBody(null) else null
    val request = Request.Builder().url(url).method(method, body).build()
    client.newCall(request).execute().use { response ->
        val body = response.body?.string().orEmpty()
        assertEquals(true, response.isSuccessful, "$label.status body=$body")
        assertContains(body, snippet, "$label.body")
    }
}

private fun checkHeader(client: OkHttpClient, baseUrl: String) {
    val request = Request.Builder()
        .url("$baseUrl/api/demo/abc")
        .header("x-token", "conformance-token")
        .build()
    client.newCall(request).execute().use { response ->
        val body = response.body?.string().orEmpty()
        assertEquals(true, response.isSuccessful, "header.status body=$body")
        assertContains(body, "header-ok", "header.body")
    }
}

private fun checkRawSingleChannel(client: OkHttpClient, baseUrl: String) {
    val request = Request.Builder().url(baseUrl.replace("http://", "ws://").replace("https://", "wss://") + "/api/ws").build()
    val opened = CompletableDeferred<Unit>()
    val message = CompletableDeferred<String>()
    val close = CompletableDeferred<Unit>()
    val socket = client.newWebSocket(request, object : okhttp3.WebSocketListener() {
        override fun onOpen(webSocket: okhttp3.WebSocket, response: okhttp3.Response) {
            opened.complete(Unit)
            webSocket.send("""{"type":"ping","data":{"source":"kotlin"}}""")
        }

        override fun onMessage(webSocket: okhttp3.WebSocket, text: String) {
            if (!message.isCompleted) {
                message.complete(text)
            }
        }

        override fun onClosed(webSocket: okhttp3.WebSocket, code: Int, reason: String) {
            if (!close.isCompleted) {
                close.complete(Unit)
            }
        }

        override fun onFailure(webSocket: okhttp3.WebSocket, t: Throwable, response: okhttp3.Response?) {
            if (!message.isCompleted) {
                message.completeExceptionally(t)
            }
            if (!close.isCompleted) {
                close.completeExceptionally(t)
            }
        }
    })
    runBlocking {
        withTimeout(5_000) { opened.await() }
        val received = withTimeout(5_000) { message.await() }
        assertContains(received, "pong", "single-channel.message")
        socket.close(1000, "kotlin complete")
        withTimeout(5_000) { close.await() }
    }
}

private suspend fun expectApiError(routeId: String = "api.demo.get.errordemo", action: suspend () -> Unit): ApiError {
    try {
        action()
    } catch (error: ApiError) {
        assertEquals(routeId, error.routeId, "ApiError.routeId")
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

private fun assertStartsWith(actual: ByteArray, first: Int, second: Int, label: String) {
    if (actual.size < 2 || actual[0] != first.toByte() || actual[1] != second.toByte()) {
        error("$label=${actual.joinToString(prefix = "[", postfix = "]")}")
    }
}
