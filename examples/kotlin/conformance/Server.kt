package com.example.apiblueprint.conformance

import com.example.apiblueprint.api.routes.api.binary.BinaryPacketResponse
import com.example.apiblueprint.api.routes.api.binary.BinaryPacketQuery
import com.example.apiblueprint.api.routes.api.binary.BinaryAuditPacketResponse
import com.example.apiblueprint.api.routes.api.binary.BinaryAuditPacketQuery
import com.example.apiblueprint.api.routes.api.binary.BinaryWidePacketResponse
import com.example.apiblueprint.api.routes.api.binary.BinaryWidePacketQuery
import com.example.apiblueprint.api.routes.api.binary.AuditPacket
import com.example.apiblueprint.api.routes.api.binary.AuditPacketBody
import com.example.apiblueprint.api.routes.api.binary.AuditPacketFlagsValues
import com.example.apiblueprint.api.routes.api.binary.AuditPacketHeader
import com.example.apiblueprint.api.routes.api.binary.AuditPacketItem
import com.example.apiblueprint.api.routes.api.binary.DemoPacket
import com.example.apiblueprint.api.routes.api.binary.WidePacket
import com.example.apiblueprint.api.routes.api.binary.BinaryServiceStub
import com.example.apiblueprint.api.routes.api.conflict.ConflictDefaultQuery
import com.example.apiblueprint.api.routes.api.conflict.ConflictServiceStub
import com.example.apiblueprint.api.routes.api.ApiServiceStub
import com.example.apiblueprint.api.routes.api.demo.*
import com.example.apiblueprint.api.routes.api.hello.*
import com.example.apiblueprint.api.routes.api.media.MediaMediaErrorFrameQuery
import com.example.apiblueprint.api.routes.api.media.MediaServiceStub
import com.example.apiblueprint.api.runtime.*
import com.example.apiblueprint.api.transports.ktor.api.binary.registerBinaryRoutes
import com.example.apiblueprint.api.transports.ktor.api.registerApiRoutes
import com.example.apiblueprint.api.transports.ktor.api.conflict.registerConflictRoutes as registerApiConflictRoutes
import com.example.apiblueprint.api.transports.ktor.api.demo.registerDemoRoutes
import com.example.apiblueprint.api.transports.ktor.api.hello.registerHelloRoutes
import com.example.apiblueprint.api.transports.ktor.api.media.registerMediaRoutes
import com.example.apiblueprint.alt.routes.alt.conflict.ConflictServiceStub as AltConflictServiceStub
import com.example.apiblueprint.alt.transports.ktor.alt.conflict.registerConflictRoutes as registerAltConflictRoutes
import com.example.apiblueprint.legacy.routes.legacy.account.AccountServiceStub as LegacyAccountServiceStub
import com.example.apiblueprint.legacy.routes.legacy.legacyjson.LegacyJsonServiceStub
import com.example.apiblueprint.legacy.routes.legacy.room.RoomRoomListResponse as LegacyRoomListResponse
import com.example.apiblueprint.legacy.routes.legacy.room.RoomServiceStub as LegacyRoomServiceStub
import com.example.apiblueprint.legacy.runtime.AccountProfile as LegacyAccountProfile
import com.example.apiblueprint.legacy.runtime.LegacyJsonCompatPayload
import com.example.apiblueprint.legacy.runtime.RoomSummary as LegacyRoomSummary
import com.example.apiblueprint.legacy.transports.ktor.legacy.account.registerAccountRoutes as registerLegacyAccountRoutes
import com.example.apiblueprint.legacy.transports.ktor.legacy.legacyjson.registerLegacyJsonRoutes
import com.example.apiblueprint.legacy.transports.ktor.legacy.room.registerRoomRoutes as registerLegacyRoomRoutes
import io.ktor.server.application.install
import io.ktor.server.application.call
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty
import io.ktor.server.routing.routing
import io.ktor.server.response.respondText
import io.ktor.server.request.path
import io.ktor.server.routing.get
import io.ktor.server.websocket.WebSockets
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlin.math.roundToInt
import kotlinx.coroutines.delay

fun main() {
    val addr = System.getenv("API_BLUEPRINT_EXAMPLE_ADDR") ?: "127.0.0.1:0"
    val host = addr.substringBefore(":")
    val port = addr.substringAfter(":", "0").toInt()
    val apiServerConfig = apiServerConfig()
    embeddedServer(Netty, host = host, port = port) {
        install(WebSockets)
        routing {
            get("/api/demo/request-options") {
                if (
                    call.request.headers["x-options-default"] != "default" ||
                    call.request.headers["x-options-token"] != "per-call"
                ) {
                    call.respondText(
                        """{"detail":"request options headers missing"}""",
                        contentType = io.ktor.http.ContentType.Application.Json,
                        status = io.ktor.http.HttpStatusCode(418, "I'm a teapot"),
                    )
                    return@get
                }
                val delayMs = call.request.queryParameters["delay_ms"]?.toIntOrNull()
                    ?: call.request.queryParameters["delayMs"]?.toIntOrNull()
                    ?: 0
                if (delayMs > 0) {
                    delay(delayMs.toLong())
                }
                call.respondText(
                    """{"code":0,"message":"ok","data":{"status":"ok","delayMs":$delayMs,"delay_ms":$delayMs}}""",
                    contentType = io.ktor.http.ContentType.Application.Json,
                )
            }
            registerDemoRoutes(DemoServiceImpl())
            registerBinaryRoutes(BinaryServiceImpl(), config = apiServerConfig)
            registerMediaRoutes(MediaServiceImpl())
            registerApiRoutes(ApiServiceImpl())
            registerHelloRoutes(HelloServiceImpl())
            registerApiConflictRoutes(ConflictServiceImpl())
            registerAltConflictRoutes(AltConflictServiceImpl())
            registerLegacyAccountRoutes(LegacyAccountServiceImpl())
            registerLegacyRoomRoutes(LegacyRoomServiceImpl())
            registerLegacyJsonRoutes(LegacyJsonServiceImpl())
            get("/static/doc.json") {
                call.respondText("{}", contentType = io.ktor.http.ContentType.Application.Json)
            }
            get("/static/dochaha") {
                call.respondText("""{"a":"hello world"}""", contentType = io.ktor.http.ContentType.Application.Json)
            }
        }
    }.start(wait = true)
}

private fun apiServerConfig(): ApiServerConfig {
    if (System.getenv("API_BLUEPRINT_ENABLE_BR_STUB") != "1") {
        return ApiServerConfig()
    }
    return ApiServerConfig(binaryContentDecoders = mapOf<String, ApiBinaryContentDecoder>("br" to ::decodeBrStub))
}

private fun decodeBrStub(body: ByteArray): ByteArray {
    val prefix = byteArrayOf(66, 82, 83, 84, 85, 66, 0)
    if (body.size < prefix.size || prefix.indices.any { body[it] != prefix[it] }) {
        throw IllegalArgumentException("invalid br stub payload")
    }
    return body.copyOfRange(prefix.size, body.size)
}

private class ApiServiceImpl : ApiServiceStub() {
    override suspend fun helloChannel(
        channel: ApiServerChannel<HelloChannelMessage, HelloChannelMessage, DefaultConnectionClose>,
    ) {
        channel.receive()
        channel.send(HelloChannelMessage(HelloChannelMsgTypeEnum.PONG, kotlinx.serialization.json.JsonObject(mapOf("source" to kotlinx.serialization.json.JsonPrimitive("kotlin")))))
        channel.close(DefaultConnectionClose(code = 1000, reason = "single channel complete"))
    }
}

private class DemoServiceImpl : DemoServiceStub() {
    override suspend fun abc(query: DemoAbcQuery): ApiDemoA = demoModel("header-ok")

    override suspend fun testPost(json: DemoTestPostJson): DemoTestPostResponse =
        DemoTestPostResponse(
            list = listOf("test_post", json.req1),
            map = mapOf("req2" to ApiDemoMap((json.req2 ?: 0).toLong())),
        )

    override suspend fun formSubmit(form: DemoFormSubmitForm): DemoFormSubmitResponse =
        DemoFormSubmitResponse(summary = form.title, count = form.count ?: 0, enabled = form.enabled ?: false)

    override suspend fun requestOptions(query: DemoRequestOptionsQuery): RequestOptionsResponse {
        val delayMs = query.delayMs ?: 0
        if (delayMs > 0) {
            delay(delayMs.toLong())
        }
        return RequestOptionsResponse(status = "ok", delayMs = delayMs)
    }

    override suspend fun pathEcho(path: PathEchoPath): PathEchoResponse =
        PathEchoResponse(item = path.item, badge = path.badge, combined = "${path.item}:${path.badge}")

    override suspend fun emptyResponse(): DemoEmptyResponseResponse = DemoEmptyResponseResponse()

    override suspend fun putDemo(query: DemoPutDemoQuery, json: DemoPutDemoJson): DemoPutDemoResponse =
        DemoPutDemoResponse(
            list = listOf(query.arg1.orEmpty(), json.req1),
            anonKv = AnonFunc1putAnonKv(
                kv1 = json.req2 ?: 0,
                kv2 = listOf((query.arg2 ?: 0f).toDouble(), (json.req2 ?: 0).toDouble()),
            ),
        )

    override suspend fun delete(query: DemoDeleteQuery): String = query.arg1.orEmpty()

    override suspend fun postDeprecated(json: DemoPostDeprecatedJson): DemoPostDeprecatedResponse =
        DemoPostDeprecatedResponse(list = listOf(json.req1))

    override suspend fun raw(): DemoRawResponse =
        DemoRawResponse(list = listOf("raw"), list2 = mapOf(1L to listOf(demoModel("raw"))))

    override suspend fun mapModel(): DemoMapModelResponse = mapOf(1 to ApiDemoMap(101))

    override suspend fun errorDemo(query: DemoErrorDemoQuery): DemoErrorDemoResponse =
        when (query.mode ?: "ok") {
            "rate_limit" -> throw ApiError(
                ApiErrorPayload(
                    id = "DemoErr.RATE_LIMITED",
                    code = DemoErr.RATE_LIMITED,
                    toast = ApiToastPayload(
                        key = "demo.rate_limited",
                        level = "warning",
                        default = "请求过于频繁，请稍后再试",
                        text = "请等待 30 秒后重试",
                    ),
                )
            )
            "unknown" -> throw ApiError(
                ApiErrorPayload(
                    code = 70001,
                    message = "example undefined business error",
                )
            )
            else -> DemoErrorDemoResponse(status = "ok")
        }

    override suspend fun sweepEvents(
        openData: SweepOpen,
        stream: ApiServerStream<SweepStreamMessage, ConnectionClose>,
    ) {
        stream.send(SweepStreamMessageVariants.state(SweepState(status = "kotlin sweep ${openData.runId}")))
        stream.close(ConnectionClose(code = 1000, reason = "example stream complete"))
    }

    override suspend fun assistantSession(
        openData: AssistantOpen,
        channel: ApiServerChannel<AssistantClientMessage, AssistantServerMessage, ConnectionClose>,
    ) {
        val first = channel.receive() ?: run {
            channel.close(ConnectionClose(code = 1000, reason = "empty session"))
            return
        }
        when (first.type) {
            "input" -> {
                val data = ApiJson.decodeFromJsonElement(AssistantInput.serializer(), first.data ?: JsonNull)
                channel.send(AssistantServerMessageVariants.delta(AssistantDelta("${openData.sessionId}:${data.text}")))
            }
            "cancel" -> {
                val data = ApiJson.decodeFromJsonElement(AssistantCancel.serializer(), first.data ?: JsonNull)
                channel.close(ConnectionClose(code = 1000, reason = data.reason))
            }
        }
        val second = channel.receive() ?: return
        if (second.type == "cancel") {
            val data = ApiJson.decodeFromJsonElement(AssistantCancel.serializer(), second.data ?: JsonNull)
            channel.close(ConnectionClose(code = 1000, reason = data.reason))
        }
    }
}

private class BinaryServiceImpl : BinaryServiceStub() {
    override suspend fun packet(query: BinaryPacketQuery, binary: DemoPacket): BinaryPacketResponse {
        return BinaryPacketResponse(
            trace = query.trace.orEmpty(),
            version = binary.header.version,
            itemCount = binary.body.items.size,
            payload = binary.body.payload.decodeToString(),
            scoreSum = binary.body.scores.sum().roundToInt().toDouble(),
            firstLabel = binary.body.items.firstOrNull()?.label?.decodeToString().orEmpty(),
            itemIds = binary.body.items.map { it.id.toInt() },
            checksum = binary.body.checksum.toInt(),
        )
    }

    override suspend fun auditPacket(query: BinaryAuditPacketQuery, binary: AuditPacket): BinaryAuditPacketResponse {
        return BinaryAuditPacketResponse(
            trace = query.trace.orEmpty(),
            itemCount = binary.header.itemCount,
            checksum = binary.body.checksum.toInt(),
        )
    }

    override suspend fun widePacket(query: BinaryWidePacketQuery, binary: WidePacket): BinaryWidePacketResponse {
        return BinaryWidePacketResponse(
            trace = query.trace.orEmpty(),
            payloadSize = binary.body.payload.size.toLong(),
            signedWide = binary.header.signedWide,
            checksum = binary.body.checksum,
        )
    }

    override suspend fun auditPacketResponse(): AuditPacket = buildAuditPacket()
}

private class MediaServiceImpl : MediaServiceStub() {
    override suspend fun mediaPreview(multipart: MediaPreviewRequest): ApiRawResponse =
        ApiRawResponse(body = sampleJpeg(), contentType = "image/jpeg")

    override suspend fun mediaFrame(): ApiRawResponse =
        ApiRawResponse(body = sampleJpeg(), contentType = "image/jpeg")

    override suspend fun mediaDownload(): ApiRawResponse =
        ApiRawResponse(
            body = "PK\u0003\u0004api-blueprint media report\n".encodeToByteArray(),
            contentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    override suspend fun mediaDownloadDynamic(): ApiRawResponse =
        ApiRawResponse(
            body = "PK\u0003\u0004api-blueprint media report dynamic\n".encodeToByteArray(),
            contentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename = "media-report-dynamic.xlsx",
        )

    override suspend fun mediaDownloadFilenameEdge(): ApiRawResponse =
        ApiRawResponse(
            body = "PK\u0003\u0004api-blueprint media report filename edge\n".encodeToByteArray(),
            contentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename = "媒体报告.xlsx",
        )

    override suspend fun mediaErrorFrame(query: MediaMediaErrorFrameQuery): ApiRawResponse {
        if (query.mode == "rate_limit") {
            throw ApiError(
                ApiErrorPayload(
                    id = "DemoErr.RATE_LIMITED",
                    code = DemoErr.RATE_LIMITED,
                    toast = ApiToastPayload(
                        key = "demo.rate_limited",
                        level = "warning",
                        default = "请求过于频繁，请稍后再试",
                        text = "请等待 30 秒后重试",
                    ),
                )
            )
        }
        return ApiRawResponse(body = sampleJpeg(), contentType = "image/jpeg")
    }

    override suspend fun mediaMjpeg(): ApiStreamResponse =
        ApiStreamResponse(
            body = "--frame\r\nContent-Type: image/jpeg\r\n\r\n".encodeToByteArray() +
                sampleJpeg() +
                "\r\n".encodeToByteArray(),
            contentType = "multipart/x-mixed-replace; boundary=frame",
        )
}

private class HelloServiceImpl : HelloServiceStub() {
    override suspend fun abc(query: HelloAbcQuery): HelloAbcResponse =
        mapOf("hello" to ApiHelloMap(1001), (query.type.wireValue) to ApiHelloMap(1))

    override suspend fun mapEnum(): HelloMapEnumResponse =
        mapOf("a" to ApiHelloMap(11), "b" to ApiHelloMap(22))

    override suspend fun listEnum(): HelloListEnumResponse = listOf(MapEnum.A, MapEnum.B)

    override suspend fun string(): HelloStringResponse = "hello-string"

    override suspend fun uint64(): HelloUint64Response = 9007199254740991L

    override suspend fun stringEmun(): HelloStringEmunResponse = MapEnum.A
}

private class ConflictServiceImpl : ConflictServiceStub() {
    override suspend fun default(query: ConflictDefaultQuery): ConflictModel =
        ConflictModel(default = "api-default", `class` = query.`class`.orEmpty(), enum = KeywordEnum.DEFAULT)
}

private class AltConflictServiceImpl : AltConflictServiceStub() {
    override suspend fun default(
        query: com.example.apiblueprint.alt.routes.alt.conflict.ConflictDefaultQuery,
    ): com.example.apiblueprint.alt.runtime.ConflictModel =
        com.example.apiblueprint.alt.runtime.ConflictModel(
            default = "alt-default",
            `class` = query.`class`.orEmpty(),
            enum = com.example.apiblueprint.alt.runtime.KeywordEnum.CLASS,
        )
}

private class LegacyAccountServiceImpl : LegacyAccountServiceStub() {
    override suspend fun accountProfile(): LegacyAccountProfile =
        LegacyAccountProfile(userId = "1000010", nickname = "legacy-user")
}

private class LegacyRoomServiceImpl : LegacyRoomServiceStub() {
    override suspend fun roomList(): LegacyRoomListResponse =
        LegacyRoomListResponse(
            rooms = listOf(LegacyRoomSummary(roomId = "100", title = "legacy-room"))
        )
}

private class LegacyJsonServiceImpl : LegacyJsonServiceStub() {
    override suspend fun legacyJsonCompat(): LegacyJsonCompatPayload =
        LegacyJsonCompatPayload(
            target = JsonArray(listOf(JsonPrimitive("legacy-room"), JsonPrimitive("backup-room"))),
            ids = listOf(JsonPrimitive("1"), JsonPrimitive(2), JsonPrimitive("3")),
            normalizedIds = listOf("1", "2", "3"),
        )
}

private fun demoModel(label: String): ApiDemoA =
    ApiDemoA(
        bc = label,
        a = 1,
        efg = 1.5f,
        hijk = listOf(1, 2, 3),
        lmnop = listOf(ApiDemoSubA(hello = mapOf("a" to 1), amap = listOf(ApiDemoMap(1)))),
        enumColor = ColorEnum.RED,
        enumStatus = StatusEnum.RUNNING,
        enumList = listOf(StatusEnum.PENDING, StatusEnum.RUNNING),
    )

private fun buildAuditPacket(): AuditPacket =
    AuditPacket(
        header = AuditPacketHeader(flags = AuditPacketFlagsValues.HasItems, itemCount = 2),
        body = AuditPacketBody(
            items = listOf(
                AuditPacketItem(id = 11, code = 101),
                AuditPacketItem(id = 22, code = 202),
            ),
            checksum = 2,
        ),
    )

private fun sampleJpeg(): ByteArray =
    intArrayOf(
        0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10,
        'J'.code, 'F'.code, 'I'.code, 'F'.code, 0x00, 0x01, 0x01, 0x01, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00, 0xff, 0xd9,
    ).map { it.toByte() }.toByteArray()
