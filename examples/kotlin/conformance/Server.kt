package com.example.apiblueprint.conformance

import com.example.apiblueprint.api.routes.api.binary.BinaryPacketResponse
import com.example.apiblueprint.api.routes.api.binary.BinaryPacketQuery
import com.example.apiblueprint.api.routes.api.binary.BinaryAuditPacketResponse
import com.example.apiblueprint.api.routes.api.binary.BinaryAuditPacketQuery
import com.example.apiblueprint.api.routes.api.binary.BinaryServiceStub
import com.example.apiblueprint.api.routes.api.conflict.ConflictDefaultQuery
import com.example.apiblueprint.api.routes.api.conflict.ConflictServiceStub
import com.example.apiblueprint.api.routes.api.ApiServiceStub
import com.example.apiblueprint.api.routes.api.demo.*
import com.example.apiblueprint.api.routes.api.hello.*
import com.example.apiblueprint.api.runtime.*
import com.example.apiblueprint.api.runtime.binary.ApiBinaryBody
import com.example.apiblueprint.api.runtime.binary.toByteArray
import com.example.apiblueprint.api.transports.ktor.api.binary.registerBinaryRoutes
import com.example.apiblueprint.api.transports.ktor.api.registerApiRoutes
import com.example.apiblueprint.api.transports.ktor.api.conflict.registerConflictRoutes as registerApiConflictRoutes
import com.example.apiblueprint.api.transports.ktor.api.demo.registerDemoRoutes
import com.example.apiblueprint.api.transports.ktor.api.hello.registerHelloRoutes
import com.example.apiblueprint.alt.routes.alt.conflict.ConflictServiceStub as AltConflictServiceStub
import com.example.apiblueprint.alt.transports.ktor.alt.conflict.registerConflictRoutes as registerAltConflictRoutes
import io.ktor.server.application.install
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty
import io.ktor.server.routing.routing
import io.ktor.server.response.respondText
import io.ktor.server.routing.get
import io.ktor.server.websocket.WebSockets
import kotlinx.serialization.json.JsonNull
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.roundToInt

fun main() {
    val addr = System.getenv("API_BLUEPRINT_EXAMPLE_ADDR") ?: "127.0.0.1:0"
    val host = addr.substringBefore(":")
    val port = addr.substringAfter(":", "0").toInt()
    embeddedServer(Netty, host = host, port = port) {
        install(WebSockets)
        routing {
            registerDemoRoutes(DemoServiceImpl())
            registerBinaryRoutes(BinaryServiceImpl())
            registerApiRoutes(ApiServiceImpl())
            registerHelloRoutes(HelloServiceImpl())
            registerApiConflictRoutes(ConflictServiceImpl())
            registerAltConflictRoutes(AltConflictServiceImpl())
            get("/static/doc.json") {
                call.respondText("{}", contentType = io.ktor.http.ContentType.Application.Json)
            }
            get("/static/dochaha") {
                call.respondText("""{"a":"hello world"}""", contentType = io.ktor.http.ContentType.Application.Json)
            }
        }
    }.start(wait = true)
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
    override suspend fun packet(query: BinaryPacketQuery, binaryBody: ApiBinaryBody): BinaryPacketResponse {
        val packet = parsePacket(binaryBody.toByteArray())
        return BinaryPacketResponse(
            trace = query.trace.orEmpty(),
            version = packet.version,
            itemCount = packet.itemIds.size,
            payload = packet.payload,
            scoreSum = packet.scoreSum,
            firstLabel = packet.firstLabel,
            itemIds = packet.itemIds,
            checksum = packet.checksum,
        )
    }

    override suspend fun auditPacket(query: BinaryAuditPacketQuery, binaryBody: ApiBinaryBody): BinaryAuditPacketResponse {
        val packet = parseAuditPacket(binaryBody.toByteArray())
        return BinaryAuditPacketResponse(
            trace = query.trace.orEmpty(),
            itemCount = packet.itemCount,
            checksum = packet.checksum,
        )
    }
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

private data class ParsedPacket(
    val version: Int,
    val payload: String,
    val scoreSum: Double,
    val firstLabel: String,
    val itemIds: List<Int>,
    val checksum: Int,
)

private data class ParsedAuditPacket(
    val itemCount: Int,
    val checksum: Int,
)

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

private fun parsePacket(bytes: ByteArray): ParsedPacket {
    val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    val magic = readUtf8(buffer, 4)
    check(magic == "ABP1") { "binary magic mismatch: $magic" }
    val version = readU16(buffer)
    val kind = readU16(buffer)
    check(kind == 1) { "binary kind mismatch: $kind" }
    val flags = Integer.toUnsignedLong(buffer.int)
    check((flags and 1L) != 0L) { "binary flags missing payload bit: $flags" }
    buffer.get()
    buffer.get()
    buffer.get()
    val shortCode = readU24(buffer)
    check(shortCode == 0x010203) { "binary shortCode mismatch: $shortCode" }
    readI24(buffer)
    val itemCount = readU16(buffer)
    val payloadLen = Integer.toUnsignedLong(buffer.int).toInt()
    val scoreCount = readU16(buffer)
    val itemIds = mutableListOf<Int>()
    var firstLabel = ""
    repeat(itemCount) { index ->
        itemIds += buffer.int
        buffer.get()
        buffer.double
        val labelLen = buffer.get().toInt() and 0xFF
        val label = readUtf8(buffer, labelLen)
        if (index == 0) {
            firstLabel = label
        }
    }
    val payload = readUtf8(buffer, payloadLen)
    var scoreSum = 0.0
    repeat(scoreCount) {
        scoreSum += buffer.double
    }
    val checksum = Integer.toUnsignedLong(buffer.int).toInt()
    check(!buffer.hasRemaining()) { "binary packet has trailing bytes: ${buffer.remaining()}" }
    return ParsedPacket(
        version = version,
        payload = payload,
        scoreSum = scoreSum.roundToInt().toDouble(),
        firstLabel = firstLabel,
        itemIds = itemIds,
        checksum = checksum,
    )
}

private fun parseAuditPacket(bytes: ByteArray): ParsedAuditPacket {
    val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    val kind = readU16(buffer)
    check(kind == 2) { "audit kind mismatch: $kind" }
    val flags = Integer.toUnsignedLong(buffer.int)
    check((flags and 1L) != 0L) { "audit flags missing items bit: $flags" }
    val itemCount = readU16(buffer)
    repeat(itemCount) {
        buffer.int
        buffer.short
    }
    val checksum = Integer.toUnsignedLong(buffer.int).toInt()
    check(!buffer.hasRemaining()) { "audit packet has trailing bytes: ${buffer.remaining()}" }
    return ParsedAuditPacket(itemCount = itemCount, checksum = checksum)
}

private fun readUtf8(buffer: ByteBuffer, size: Int): String {
    val bytes = ByteArray(size)
    buffer.get(bytes)
    return bytes.decodeToString()
}

private fun readU16(buffer: ByteBuffer): Int = java.lang.Short.toUnsignedInt(buffer.short)

private fun readU24(buffer: ByteBuffer): Int {
    val b0 = buffer.get().toInt() and 0xFF
    val b1 = buffer.get().toInt() and 0xFF
    val b2 = buffer.get().toInt() and 0xFF
    return b0 or (b1 shl 8) or (b2 shl 16)
}

private fun readI24(buffer: ByteBuffer): Int {
    var value = readU24(buffer)
    if ((value and 0x800000) != 0) {
        value = value or -0x1000000
    }
    return value
}
