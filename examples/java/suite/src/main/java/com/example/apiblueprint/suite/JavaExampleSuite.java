package com.example.apiblueprint.suite;

import com.example.apiblueprint.api.routes.api.binary.BinaryService;
import com.example.apiblueprint.api.routes.api.binary.GenBinaryServiceModels;
import com.example.apiblueprint.api.routes.api.binary.GenBinaryServiceStub;
import com.example.apiblueprint.api.routes.api.demo.DemoService;
import com.example.apiblueprint.api.routes.api.demo.GenDemoServiceModels;
import com.example.apiblueprint.api.routes.api.demo.GenDemoServiceStub;
import com.example.apiblueprint.api.runtime.GenModels;
import com.example.apiblueprint.api.runtime.binary.ApiBinaryBody;
import com.example.apiblueprint.api.transports.http.api.GenApiController;
import com.example.apiblueprint.api.transports.http.api.binary.GenBinaryController;
import com.example.apiblueprint.api.transports.http.api.demo.GenDemoController;
import com.example.apiblueprint.static_.transports.http.static_.GenStaticController;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayOutputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;

@SpringBootConfiguration(proxyBeanMethods = false)
@EnableAutoConfiguration
@Import({
    GenApiController.class,
    GenBinaryController.class,
    GenDemoController.class,
    GenStaticController.class
})
public class JavaExampleSuite {
    public static void main(String[] args) throws Exception {
        SpringApplication application = new SpringApplication(JavaExampleSuite.class);
        application.setEnvironmentPrefix("api-blueprint-suite");
        application.setDefaultProperties(Map.of(
            "server.port", "0",
            "spring.main.banner-mode", "off",
            "debug", "false",
            "logging.level.root", "WARN",
            "logging.level.org.springframework", "WARN",
            "logging.level.org.apache.catalina", "ERROR",
            "logging.level.org.apache.tomcat", "ERROR"
        ));
        try (ConfigurableApplicationContext context = application.run(args)) {
            int port = ((WebServerApplicationContext) context).getWebServer().getPort();
            String baseUrl = "http://127.0.0.1:" + port;
            checkGeneratedApiClient(baseUrl);
            checkGeneratedStaticClient(baseUrl);
            checkUnsupportedConnections(baseUrl);
        }
        System.out.println("java example suite passed");
    }

    @Bean
    public ObjectMapper objectMapper() {
        return new ObjectMapper();
    }

    @Bean
    public DemoService demoService() {
        return new DemoServiceImpl();
    }

    @Bean
    public BinaryService binaryService() {
        return new BinaryServiceImpl();
    }

    @Bean
    public com.example.apiblueprint.static_.routes.static_.StaticService staticService() {
        return new StaticServiceImpl();
    }

    private static void checkGeneratedApiClient(String baseUrl) throws Exception {
        var apiClient = new com.example.apiblueprint.api.transports.http.HttpApiClient(
            new com.example.apiblueprint.api.transports.http.GenHttpApiConfig(baseUrl)
        );

        var post = apiClient.demo.testPost(
            new com.example.apiblueprint.api.routes.api.demo.GenDemoApiModels.ReqTestPostJson("suite", 7)
        );
        require(Objects.equals(List.of("test_post", "suite"), post.list()), "demo.testPost list mismatch: " + post);
        require(
            post.map() != null
                && post.map().get("req2") != null
                && Objects.equals(7L, post.map().get("req2").haha()),
            "demo.testPost map mismatch: " + post
        );

        var put = apiClient.demo.z1put(
            new com.example.apiblueprint.api.routes.api.demo.GenDemoApiModels.ReqFunc1putQuery("query", 3.5f, null),
            new com.example.apiblueprint.api.routes.api.demo.GenDemoApiModels.ReqFunc1putJson("body", 9)
        );
        require(Objects.equals(List.of("query", "body"), put.list()), "demo.z1put list mismatch: " + put);
        require(put.anonKv() != null, "demo.z1put anonKv missing");
        require(Objects.equals(9L, put.anonKv().kv1()), "demo.z1put kv1 mismatch: " + put.anonKv());
        require(Objects.equals(List.of(3.5d, 9.0d), put.anonKv().kv2()), "demo.z1put kv2 mismatch: " + put.anonKv());

        var binary = apiClient.binary.packet(
            new com.example.apiblueprint.api.routes.api.binary.GenBinaryApiModels.ReqPacketQuery("java-binary"),
            ApiBinaryBody.of(buildDemoPacketFixture("ABP1", 2, "payload-ok"))
        );
        require(Objects.equals("java-binary", binary.trace()), "binary trace mismatch: " + binary);
        require(Objects.equals(1L, binary.version()), "binary version mismatch: " + binary);
        require(Objects.equals(2L, binary.itemCount()), "binary itemCount mismatch: " + binary);
        require(Objects.equals("payload-ok", binary.payload()), "binary payload mismatch: " + binary);
        require(Objects.equals(8.0d, binary.scoreSum()), "binary scoreSum mismatch: " + binary);
        require(Objects.equals("alpha", binary.firstLabel()), "binary firstLabel mismatch: " + binary);
        require(Objects.equals(List.of(11L, 22L), binary.itemIds()), "binary itemIds mismatch: " + binary);
        require(Objects.equals(12L, binary.checksum()), "binary checksum mismatch: " + binary);
    }

    private static void checkGeneratedStaticClient(String baseUrl) throws Exception {
        var staticClient = new com.example.apiblueprint.static_.transports.http.HttpApiClient(
            new com.example.apiblueprint.static_.transports.http.GenHttpApiConfig(baseUrl)
        );
        var response = staticClient.staticValue.dochaha();
        require(Objects.equals("suite-static", response.a()), "static.dochaha mismatch: " + response);
    }

    private static void checkUnsupportedConnections(String baseUrl) throws Exception {
        var apiClient = new com.example.apiblueprint.api.transports.http.HttpApiClient(
            new com.example.apiblueprint.api.transports.http.GenHttpApiConfig(baseUrl)
        );
        expectUnsupported(apiClient.api::connectWs, "WebSocket");
        expectUnsupported(() -> apiClient.demo.subscribeSweepEvents(new GenModels.SweepOpen("suite", null)), "stream");
        expectUnsupported(() -> apiClient.demo.openAssistantSession(new GenModels.AssistantOpen("suite")), "channel");

        HttpClient httpClient = HttpClient.newHttpClient();
        requireStatus(httpClient, baseUrl + "/api/ws", 501, "legacy_ws route is not implemented");
        requireStatus(httpClient, baseUrl + "/api/demo/sweep-events", 501, "stream route is not implemented");
    }

    private static void requireStatus(HttpClient client, String url, int status, String bodySnippet) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create(url)).GET().build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        require(response.statusCode() == status, url + " status " + response.statusCode() + " body " + response.body());
        require(response.body().contains(bodySnippet), url + " body mismatch: " + response.body());
    }

    private static void expectUnsupported(ThrowingRunnable action, String snippet) throws Exception {
        try {
            action.run();
        } catch (UnsupportedOperationException exc) {
            require(exc.getMessage() != null && exc.getMessage().contains(snippet), "unsupported message mismatch: " + exc);
            return;
        }
        throw new IllegalStateException("expected UnsupportedOperationException containing " + snippet);
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new IllegalStateException(message);
        }
    }

    private interface ThrowingRunnable {
        void run() throws Exception;
    }

    private static final class DemoServiceImpl extends GenDemoServiceStub {
        @Override
        public GenDemoServiceModels.RspTestPost testPost(GenDemoServiceModels.ReqTestPostJson json) {
            return new GenDemoServiceModels.RspTestPost(
                List.of("test_post", json.req1()),
                Map.of("req2", new com.example.apiblueprint.api.runtime.GenModels.ApiDemoMap(json.req2().longValue()))
            );
        }

        @Override
        public GenDemoServiceModels.RspFunc1put z1put(
            GenDemoServiceModels.ReqFunc1putQuery query,
            GenDemoServiceModels.ReqFunc1putJson json
        ) {
            return new GenDemoServiceModels.RspFunc1put(
                List.of(query.arg1(), json.req1()),
                new GenDemoServiceModels.AnonFunc1putAnonKv(
                    json.req2().longValue(),
                    List.of(query.arg2().doubleValue(), json.req2().doubleValue())
                )
            );
        }
    }

    private static final class BinaryServiceImpl extends GenBinaryServiceStub {
        @Override
        public GenBinaryServiceModels.RspPacket packet(
            GenBinaryServiceModels.ReqPacketQuery query,
            ApiBinaryBody binaryBody
        ) {
            ParsedDemoPacket packet = parseDemoPacket(binaryBody.toBytes());
            return new GenBinaryServiceModels.RspPacket(
                query.trace(),
                packet.version(),
                packet.itemCount(),
                packet.payload(),
                packet.scoreSum(),
                packet.firstLabel(),
                packet.itemIds(),
                packet.checksum()
            );
        }
    }

    private static final class StaticServiceImpl
        extends com.example.apiblueprint.static_.routes.static_.GenStaticServiceStub {
        @Override
        public com.example.apiblueprint.static_.routes.static_.GenStaticServiceModels.RspDochaha dochaha() {
            return new com.example.apiblueprint.static_.routes.static_.GenStaticServiceModels.RspDochaha("suite-static");
        }
    }

    private record ParsedDemoPacket(
        long version,
        long itemCount,
        String payload,
        double scoreSum,
        String firstLabel,
        List<Long> itemIds,
        long checksum
    ) {
    }

    private static ParsedDemoPacket parseDemoPacket(byte[] bytes) {
        ByteBuffer buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        String magic = readAscii(buffer, 4);
        require("ABP1".equals(magic), "binary magic mismatch: " + magic);
        long version = readU16(buffer);
        long kind = readU16(buffer);
        require(kind == 1L, "binary kind mismatch: " + kind);
        long flags = Integer.toUnsignedLong(buffer.getInt());
        require((flags & 1L) != 0L, "binary flags missing payload bit: " + flags);
        buffer.get();
        buffer.get();
        buffer.get();
        long shortCode = readU24(buffer);
        require(shortCode == 0x010203L, "binary shortCode mismatch: " + shortCode);
        readI24(buffer);
        long itemCount = readU16(buffer);
        long payloadLen = Integer.toUnsignedLong(buffer.getInt());
        long scoreCount = readU16(buffer);

        List<Long> itemIds = new ArrayList<>();
        String firstLabel = "";
        for (int index = 0; index < itemCount; index++) {
            long id = Integer.toUnsignedLong(buffer.getInt());
            itemIds.add(id);
            buffer.get();
            buffer.getDouble();
            int labelLen = Byte.toUnsignedInt(buffer.get());
            String label = readAscii(buffer, labelLen);
            if (index == 0) {
                firstLabel = label;
            }
        }

        String payload = readAscii(buffer, Math.toIntExact(payloadLen));
        double scoreSum = 0.0d;
        for (int index = 0; index < scoreCount; index++) {
            scoreSum += buffer.getDouble();
        }
        long checksum = Integer.toUnsignedLong(buffer.getInt());
        require(!buffer.hasRemaining(), "binary packet has trailing bytes: " + buffer.remaining());
        return new ParsedDemoPacket(version, itemCount, payload, scoreSum, firstLabel, List.copyOf(itemIds), checksum);
    }

    private static byte[] buildDemoPacketFixture(String magic, int itemCount, String payload) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        writeBytes(out, magic.substring(0, 4).getBytes(StandardCharsets.US_ASCII));
        writeU16(out, 1);
        writeU16(out, 1);
        writeU32(out, 1 | 2);
        writeBytes(out, new byte[] {0});
        writeBytes(out, new byte[] {0, 0});
        writeU24(out, 0x010203);
        writeI24(out, 7);
        writeU16(out, itemCount);
        writeU32(out, payload.getBytes(StandardCharsets.UTF_8).length);
        writeU16(out, 2);
        writeItem(out, 11, true, 1.25d, "alpha");
        writeItem(out, 22, false, 2.5d, "beta");
        writeBytes(out, payload.getBytes(StandardCharsets.UTF_8));
        writeF64(out, 3.5d);
        writeF64(out, 4.5d);
        writeU32(out, itemCount + payload.getBytes(StandardCharsets.UTF_8).length);
        return out.toByteArray();
    }

    private static void writeItem(ByteArrayOutputStream out, int id, boolean enabled, double value, String label) {
        writeU32(out, id);
        writeBytes(out, new byte[] {(byte) (enabled ? 1 : 0)});
        writeF64(out, value);
        byte[] labelBytes = label.getBytes(StandardCharsets.UTF_8);
        writeBytes(out, new byte[] {(byte) labelBytes.length});
        writeBytes(out, labelBytes);
    }

    private static String readAscii(ByteBuffer buffer, int length) {
        byte[] bytes = new byte[length];
        buffer.get(bytes);
        return new String(bytes, StandardCharsets.UTF_8);
    }

    private static long readU16(ByteBuffer buffer) {
        return Short.toUnsignedLong(buffer.getShort());
    }

    private static long readU24(ByteBuffer buffer) {
        int b0 = Byte.toUnsignedInt(buffer.get());
        int b1 = Byte.toUnsignedInt(buffer.get());
        int b2 = Byte.toUnsignedInt(buffer.get());
        return b0 | (b1 << 8) | (b2 << 16);
    }

    private static int readI24(ByteBuffer buffer) {
        int value = (int) readU24(buffer);
        if ((value & 0x800000) != 0) {
            value |= 0xFF000000;
        }
        return value;
    }

    private static void writeBytes(ByteArrayOutputStream out, byte[] bytes) {
        out.writeBytes(bytes);
    }

    private static void writeU16(ByteArrayOutputStream out, int value) {
        out.write(value & 0xFF);
        out.write((value >>> 8) & 0xFF);
    }

    private static void writeU24(ByteArrayOutputStream out, int value) {
        out.write(value & 0xFF);
        out.write((value >>> 8) & 0xFF);
        out.write((value >>> 16) & 0xFF);
    }

    private static void writeI24(ByteArrayOutputStream out, int value) {
        writeU24(out, value & 0xFFFFFF);
    }

    private static void writeU32(ByteArrayOutputStream out, int value) {
        out.write(value & 0xFF);
        out.write((value >>> 8) & 0xFF);
        out.write((value >>> 16) & 0xFF);
        out.write((value >>> 24) & 0xFF);
    }

    private static void writeF64(ByteArrayOutputStream out, double value) {
        writeBytes(out, ByteBuffer.allocate(Double.BYTES).order(ByteOrder.LITTLE_ENDIAN).putDouble(value).array());
    }
}
