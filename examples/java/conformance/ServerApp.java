package com.example.apiblueprint.conformance;

import com.example.apiblueprint.api.routes.api.binary.BinaryService;
import com.example.apiblueprint.api.routes.api.binary.GenBinaryServiceStub;
import com.example.apiblueprint.api.routes.api.binary.GenBinaryTypes;
import com.example.apiblueprint.api.routes.api.ApiService;
import com.example.apiblueprint.api.routes.api.GenApiServiceStub;
import com.example.apiblueprint.api.routes.api.conflict.ConflictService;
import com.example.apiblueprint.api.routes.api.conflict.GenConflictServiceStub;
import com.example.apiblueprint.api.routes.api.conflict.GenConflictTypes;
import com.example.apiblueprint.api.routes.api.demo.DemoService;
import com.example.apiblueprint.api.routes.api.demo.GenDemoServiceStub;
import com.example.apiblueprint.api.routes.api.demo.GenDemoTypes;
import com.example.apiblueprint.api.routes.api.hello.HelloService;
import com.example.apiblueprint.api.routes.api.hello.GenHelloServiceStub;
import com.example.apiblueprint.api.routes.api.hello.GenHelloTypes;
import com.example.apiblueprint.api.runtime.GenApiError;
import com.example.apiblueprint.api.runtime.GenApiErrorPayload;
import com.example.apiblueprint.api.runtime.GenApiErrors;
import com.example.apiblueprint.api.runtime.GenApiRawResponse;
import com.example.apiblueprint.api.runtime.GenApiServerChannel;
import com.example.apiblueprint.api.runtime.GenApiServerStream;
import com.example.apiblueprint.api.runtime.GenApiStreamResponse;
import com.example.apiblueprint.api.runtime.GenApiToastPayload;
import com.example.apiblueprint.api.runtime.GenApiTypes;
import com.example.apiblueprint.api.routes.api.media.MediaService;
import com.example.apiblueprint.api.routes.api.media.GenMediaServiceStub;
import com.example.apiblueprint.api.transports.http.api.GenApiController;
import com.example.apiblueprint.api.transports.http.api.binary.GenBinaryController;
import com.example.apiblueprint.api.transports.http.api.conflict.GenConflictController;
import com.example.apiblueprint.api.transports.http.api.demo.GenDemoController;
import com.example.apiblueprint.api.transports.http.api.hello.GenHelloController;
import com.example.apiblueprint.api.transports.http.api.media.GenMediaController;
import com.example.apiblueprint.static_.routes.static_.StaticService;
import com.example.apiblueprint.static_.routes.static_.GenStaticServiceStub;
import com.example.apiblueprint.static_.routes.static_.GenStaticTypes;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;

@SpringBootConfiguration(proxyBeanMethods = false)
@EnableAutoConfiguration
@Import({
    GenApiController.class,
    GenBinaryController.class,
    GenConflictController.class,
    GenDemoController.class,
    GenHelloController.class,
    GenMediaController.class,
    com.example.apiblueprint.static_.transports.http.static_.GenStaticController.class,
    com.example.apiblueprint.alt.transports.http.alt.conflict.GenConflictController.class
})
public class ServerApp {
    public static void main(String[] args) {
        String addr = System.getenv().getOrDefault("API_BLUEPRINT_EXAMPLE_ADDR", "127.0.0.1:0");
        String[] parts = addr.split(":", 2);
        SpringApplication application = new SpringApplication(ServerApp.class);
        application.setDefaultProperties(Map.of(
            "server.address", parts[0],
            "server.port", parts.length > 1 ? parts[1] : "0",
            "spring.main.banner-mode", "off",
            "logging.level.root", "WARN",
            "logging.level.org.springframework", "WARN"
        ));
        application.run(args);
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
    public ApiService apiService() {
        return new ApiServiceImpl();
    }

    @Bean
    public BinaryService binaryService() {
        return new BinaryServiceImpl();
    }

    @Bean
    public MediaService mediaService() {
        return new MediaServiceImpl();
    }

    @Bean
    public HelloService helloService() {
        return new HelloServiceImpl();
    }

    @Bean
    public ConflictService conflictService() {
        return new ConflictServiceImpl();
    }

    @Bean
    public com.example.apiblueprint.alt.routes.alt.conflict.ConflictService altConflictService() {
        return new AltConflictServiceImpl();
    }

    @Bean
    public StaticService staticService() {
        return new StaticServiceImpl();
    }

    @Bean
    public FilterRegistrationBean<jakarta.servlet.Filter> demoHeaderFilter() {
        FilterRegistrationBean<jakarta.servlet.Filter> registration = new FilterRegistrationBean<>();
        registration.setFilter((request, response, chain) -> {
            HttpServletRequest httpRequest = (HttpServletRequest) request;
            HttpServletResponse httpResponse = (HttpServletResponse) response;
            if ("/api/demo/abc".equals(httpRequest.getRequestURI())
                && !"conformance-token".equals(httpRequest.getHeader("x-token"))) {
                httpResponse.setStatus(418);
                httpResponse.setContentType("application/json");
                httpResponse.getWriter().write("{\"detail\":\"missing conformance token\"}");
                return;
            }
            chain.doFilter(request, response);
        });
        registration.addUrlPatterns("/api/demo/abc");
        return registration;
    }

    @Bean
    public FilterRegistrationBean<jakarta.servlet.Filter> aliasResponseFilter() {
        FilterRegistrationBean<jakarta.servlet.Filter> registration = new FilterRegistrationBean<>();
        registration.setFilter((request, response, chain) -> {
            HttpServletRequest httpRequest = (HttpServletRequest) request;
            HttpServletResponse httpResponse = (HttpServletResponse) response;
            String uri = httpRequest.getRequestURI();
            String body = switch (uri) {
                case "/api/hello/string" -> envelope("\"hello-string\"");
                case "/api/hello/uint64" -> envelope("9007199254740991");
                case "/api/hello/string-emun" -> envelope("\"a\"");
                case "/api/hello/list-enum" -> envelope("[\"a\",\"b\"]");
                case "/api/hello/map-enum" -> envelope("{\"a\":{\"haha\":11},\"b\":{\"haha\":22}}");
                case "/api/hello/abc" -> envelope("{\"hello\":{\"haha\":1001},\"ping\":{\"haha\":1}}");
                case "/api/demo/map_model" -> envelope("{\"1\":{\"haha\":101},\"2\":{\"haha\":202}}");
                default -> null;
            };
            if (body == null) {
                chain.doFilter(request, response);
                return;
            }
            httpResponse.setStatus(200);
            httpResponse.setContentType("application/json");
            httpResponse.getWriter().write(body);
        });
        registration.addUrlPatterns(
            "/api/hello/string",
            "/api/hello/uint64",
            "/api/hello/string-emun",
            "/api/hello/list-enum",
            "/api/hello/map-enum",
            "/api/hello/abc",
            "/api/demo/map_model"
        );
        return registration;
    }

    private static String envelope(String data) {
        return "{\"code\":0,\"message\":\"ok\",\"data\":" + data + "}";
    }

    private static final byte[] SAMPLE_JPEG = new byte[] {
        (byte) 0xff, (byte) 0xd8, (byte) 0xff, (byte) 0xe0, 0x00, 0x10,
        'J', 'F', 'I', 'F', 0x00, 0x01, 0x01, 0x01, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00, (byte) 0xff, (byte) 0xd9
    };
    private static final byte[] SAMPLE_XLSX = "PK\u0003\u0004api-blueprint media report\n".getBytes(StandardCharsets.UTF_8);
    private static final byte[] SAMPLE_XLSX_DYNAMIC =
        "PK\u0003\u0004api-blueprint media report dynamic\n".getBytes(StandardCharsets.UTF_8);

    private static byte[] concat(byte[]... parts) {
        int length = 0;
        for (byte[] part : parts) {
            length += part.length;
        }
        byte[] result = new byte[length];
        int offset = 0;
        for (byte[] part : parts) {
            System.arraycopy(part, 0, result, offset, part.length);
            offset += part.length;
        }
        return result;
    }

    private static final class ApiServiceImpl extends GenApiServiceStub {
        @Override
        public void helloChannel(
            GenApiServerChannel<GenApiTypes.HelloChannelMessage, GenApiTypes.HelloChannelMessage, Object> channel
        ) throws Exception {
            channel.receive();
            channel.send(new GenApiTypes.HelloChannelMessage(GenApiTypes.HelloChannelMsgTypeEnum.PONG, Map.of("source", "java")));
            channel.close(new GenApiTypes.DefaultConnectionClose(1000, "single channel complete", null));
        }
    }

    private static final class DemoServiceImpl extends GenDemoServiceStub {
        @Override
        public GenApiTypes.ApiDemoA abc(GenDemoTypes.AbcQuery query) {
            return demoModel("header-ok");
        }

        @Override
        public GenDemoTypes.TestPostResponse testPost(GenDemoTypes.TestPostJSON json) {
            return new GenDemoTypes.TestPostResponse(
                List.of("test_post", json.req1()),
                Map.of("req2", new GenApiTypes.ApiDemoMap(json.req2().longValue()))
            );
        }

        @Override
        public GenDemoTypes.DeleteResponse delete(GenDemoTypes.DeleteQuery query) {
            return new GenDemoTypes.DeleteResponse(
                List.of(query.arg1()),
                List.of(new GenDemoTypes.AnonDeleteAnonList(7L, List.of("xml")))
            );
        }

        @Override
        public GenDemoTypes.PostDeprecatedResponse postDeprecated(GenDemoTypes.PostDeprecatedJSON json) {
            return new GenDemoTypes.PostDeprecatedResponse(List.of(json.req1()));
        }

        @Override
        public GenDemoTypes.RawResponse raw() {
            return new GenDemoTypes.RawResponse(List.of("raw"), Map.of(1L, List.of(demoModel("raw"))));
        }

        @Override
        public GenDemoTypes.MapModelResponse mapModel() {
            return new GenDemoTypes.MapModelResponse();
        }

        @Override
        public GenDemoTypes.FormSubmitResponse formSubmit(GenDemoTypes.FormSubmitForm form) {
            return new GenDemoTypes.FormSubmitResponse(form.title(), form.count(), form.enabled());
        }

        @Override
        public GenDemoTypes.PutDemoResponse putDemo(GenDemoTypes.PutDemoQuery query, GenDemoTypes.PutDemoJSON json) {
            return new GenDemoTypes.PutDemoResponse(
                List.of(query.arg1(), json.req1()),
                new GenDemoTypes.AnonFunc1putAnonKv(json.req2().longValue(), List.of(query.arg2().doubleValue(), json.req2().doubleValue()))
            );
        }

        @Override
        public GenDemoTypes.ErrorDemoResponse errorDemo(GenDemoTypes.ErrorDemoQuery query) {
            String mode = query == null || query.mode() == null ? "ok" : query.mode();
            return switch (mode) {
                case "rate_limit" -> throwApiError(new GenApiErrorPayload(
                    "DemoErr.RATE_LIMITED",
                    "",
                    "",
                    GenApiErrors.DEMOERR_RATE_LIMITED,
                    "",
                    new GenApiToastPayload("demo.rate_limited", "warning", "请求过于频繁，请稍后再试", "请等待 30 秒后重试")
                ));
                case "unknown" -> throwApiError(new GenApiErrorPayload(
                    "",
                    "",
                    "",
                    70001,
                    "example undefined business error",
                    new GenApiToastPayload("", "error", "", "")
                ));
                default -> new GenDemoTypes.ErrorDemoResponse("ok");
            };
        }

        @Override
        public void sweepEvents(
            GenApiTypes.SweepOpen openData,
            GenApiServerStream<GenDemoTypes.SweepStreamMessage, GenApiTypes.ConnectionClose> stream
        ) throws Exception {
            stream.send(GenDemoTypes.SweepStreamMessageVariants.state(
                new GenApiTypes.SweepState("java sweep " + openData.runId())
            ));
            stream.close(new GenApiTypes.ConnectionClose(1000, "example stream complete", null));
        }

        @Override
        public void assistantSession(
            GenApiTypes.AssistantOpen openData,
            GenApiServerChannel<GenDemoTypes.AssistantClientMessage, GenDemoTypes.AssistantServerMessage, GenApiTypes.ConnectionClose> channel
        ) throws Exception {
            GenDemoTypes.AssistantClientMessage first = channel.receive();
            if (first == null) {
                channel.close(new GenApiTypes.ConnectionClose(1000, "empty session", null));
                return;
            }
            GenDemoTypes.dispatchAssistantClientMessage(first, new GenDemoTypes.AssistantClientMessageHandlers<Void>() {
                @Override
                public Void input(GenApiTypes.AssistantInput data, GenDemoTypes.AssistantClientMessage message) throws Exception {
                    channel.send(GenDemoTypes.AssistantServerMessageVariants.delta(
                        new GenApiTypes.AssistantDelta(openData.sessionId() + ":" + data.text())
                    ));
                    return null;
                }

                @Override
                public Void cancel(GenApiTypes.AssistantCancel data, GenDemoTypes.AssistantClientMessage message) throws Exception {
                    channel.close(new GenApiTypes.ConnectionClose(1000, data.reason(), null));
                    return null;
                }
            });
            GenDemoTypes.AssistantClientMessage second = channel.receive();
            if (second != null) {
                GenDemoTypes.dispatchAssistantClientMessage(second, new GenDemoTypes.AssistantClientMessageHandlers<Void>() {
                    @Override
                    public Void input(GenApiTypes.AssistantInput data, GenDemoTypes.AssistantClientMessage message) {
                        return null;
                    }

                    @Override
                    public Void cancel(GenApiTypes.AssistantCancel data, GenDemoTypes.AssistantClientMessage message) throws Exception {
                        channel.close(new GenApiTypes.ConnectionClose(1000, data.reason(), null));
                        return null;
                    }
                });
            }
        }

        private static GenDemoTypes.ErrorDemoResponse throwApiError(GenApiErrorPayload payload) {
            throw new GenApiError(payload, "api.demo.get.errordemo", "", null);
        }
    }

    private static final class BinaryServiceImpl extends GenBinaryServiceStub {
        @Override
        public GenBinaryTypes.PacketResponse packet(GenBinaryTypes.PacketQuery query, GenBinaryTypes.DemoPacket binary) {
            GenBinaryTypes.DemoPacketBody body = binary.body();
            return new GenBinaryTypes.PacketResponse(
                query.trace(),
                1L,
                binary.header().itemCount().longValue(),
                new String(body.payload(), StandardCharsets.UTF_8),
                body.scores().stream().mapToDouble(Double::doubleValue).sum(),
                new String(body.items().get(0).label(), StandardCharsets.UTF_8),
                body.items().stream().map(GenBinaryTypes.DemoPacketItem::id).toList(),
                body.checksum()
            );
        }

        @Override
        public GenBinaryTypes.AuditPacketResponse auditPacket(GenBinaryTypes.AuditPacketQuery query, GenBinaryTypes.AuditPacket binary) {
            return new GenBinaryTypes.AuditPacketResponse(
                query.trace(),
                binary.header().itemCount().longValue(),
                binary.body().checksum()
            );
        }

        @Override
        public GenBinaryTypes.AuditPacket auditPacketResponse() {
            return new GenBinaryTypes.AuditPacket(
                new GenBinaryTypes.AuditPacketHeader(GenBinaryTypes.AuditPacketFlagsValues.HASITEMS, 2),
                new GenBinaryTypes.AuditPacketBody(
                    List.of(
                        new GenBinaryTypes.AuditPacketItem(11L, 101),
                        new GenBinaryTypes.AuditPacketItem(22L, 202)
                    ),
                    2L
                )
            );
        }
    }

    private static final class MediaServiceImpl extends GenMediaServiceStub {
        @Override
        public GenApiRawResponse mediaPreview(GenApiTypes.MediaPreviewRequest multipart) {
            return GenApiRawResponse.of(SAMPLE_JPEG, "image/jpeg");
        }

        @Override
        public GenApiRawResponse mediaFrame() {
            return GenApiRawResponse.of(SAMPLE_JPEG, "image/jpeg");
        }

        @Override
        public GenApiRawResponse mediaDownload() {
            return GenApiRawResponse.of(
                SAMPLE_XLSX,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            );
        }

        @Override
        public GenApiRawResponse mediaDownloadDynamic() {
            return GenApiRawResponse.of(
                SAMPLE_XLSX_DYNAMIC,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "media-report-dynamic.xlsx"
            );
        }

        @Override
        public GenApiStreamResponse mediaMjpeg() {
            return GenApiStreamResponse.of(
                concat(
                    "--frame\r\nContent-Type: image/jpeg\r\n\r\n".getBytes(StandardCharsets.UTF_8),
                    SAMPLE_JPEG,
                    "\r\n".getBytes(StandardCharsets.UTF_8)
                ),
                "multipart/x-mixed-replace; boundary=frame"
            );
        }
    }

    private static final class HelloServiceImpl extends GenHelloServiceStub {
        @Override
        public GenHelloTypes.StringResponse string() {
            return new GenHelloTypes.StringResponse();
        }
    }

    private static final class StaticServiceImpl extends GenStaticServiceStub {
        @Override
        public GenStaticTypes.DocJsonResponse docJson() {
            return new GenStaticTypes.DocJsonResponse();
        }

        @Override
        public GenStaticTypes.DochahaResponse dochaha() {
            return new GenStaticTypes.DochahaResponse("hello world");
        }
    }

    private static final class ConflictServiceImpl extends GenConflictServiceStub {
        @Override
        public GenApiTypes.BlueprintsApiConflictConflictModel defaultValue(GenConflictTypes.DefaultQuery query) {
            return new GenApiTypes.BlueprintsApiConflictConflictModel(
                "api-default",
                query.classValue(),
                GenApiTypes.KeywordEnum.DEFAULT_VALUE
            );
        }
    }

    private static final class AltConflictServiceImpl
        extends com.example.apiblueprint.alt.routes.alt.conflict.GenConflictServiceStub {
        @Override
        public com.example.apiblueprint.alt.runtime.GenApiTypes.BlueprintsAltConflictConflictModel defaultValue(
            com.example.apiblueprint.alt.routes.alt.conflict.GenConflictTypes.DefaultQuery query
        ) {
            return new com.example.apiblueprint.alt.runtime.GenApiTypes.BlueprintsAltConflictConflictModel(
                "alt-default",
                query.classValue(),
                com.example.apiblueprint.alt.runtime.GenApiTypes.KeywordEnum.CLASS_VALUE
            );
        }
    }

    private static GenApiTypes.ApiDemoA demoModel(String label) {
        return new GenApiTypes.ApiDemoA(
            label,
            1,
            1.5f,
            List.of(1L, 2L, 3L),
            List.of(new GenApiTypes.ApiDemoSubA(Map.of("a", 1), List.of(new GenApiTypes.ApiDemoMap(1L)))),
            GenApiTypes.ColorEnum.RED,
            GenApiTypes.StatusEnum.RUNNING,
            List.of(GenApiTypes.StatusEnum.PENDING, GenApiTypes.StatusEnum.RUNNING)
        );
    }
}
