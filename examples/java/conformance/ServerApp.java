package com.example.apiblueprint.conformance;

import com.example.apiblueprint.api.routes.api.binary.BinaryService;
import com.example.apiblueprint.api.routes.api.binary.BinaryServiceStub;
import com.example.apiblueprint.api.routes.api.binary.BinaryTypes;
import com.example.apiblueprint.api.routes.api.ApiService;
import com.example.apiblueprint.api.routes.api.ApiServiceStub;
import com.example.apiblueprint.api.routes.api.conflict.ConflictService;
import com.example.apiblueprint.api.routes.api.conflict.ConflictServiceStub;
import com.example.apiblueprint.api.routes.api.conflict.ConflictTypes;
import com.example.apiblueprint.api.routes.api.demo.DemoService;
import com.example.apiblueprint.api.routes.api.demo.DemoServiceStub;
import com.example.apiblueprint.api.routes.api.demo.DemoTypes;
import com.example.apiblueprint.api.routes.api.hello.HelloService;
import com.example.apiblueprint.api.routes.api.hello.HelloServiceStub;
import com.example.apiblueprint.api.routes.api.hello.HelloTypes;
import com.example.apiblueprint.api.runtime.ApiError;
import com.example.apiblueprint.api.runtime.ApiErrorPayload;
import com.example.apiblueprint.api.runtime.ApiErrors;
import com.example.apiblueprint.api.runtime.ApiServerChannel;
import com.example.apiblueprint.api.runtime.ApiServerStream;
import com.example.apiblueprint.api.runtime.ApiToastPayload;
import com.example.apiblueprint.api.runtime.ApiTypes;
import com.example.apiblueprint.api.transports.http.api.GenApiController;
import com.example.apiblueprint.api.transports.http.api.binary.GenBinaryController;
import com.example.apiblueprint.api.transports.http.api.conflict.GenConflictController;
import com.example.apiblueprint.api.transports.http.api.demo.GenDemoController;
import com.example.apiblueprint.api.transports.http.api.hello.GenHelloController;
import com.example.apiblueprint.static_.routes.static_.StaticService;
import com.example.apiblueprint.static_.routes.static_.StaticServiceStub;
import com.example.apiblueprint.static_.routes.static_.StaticTypes;
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

    private static final class ApiServiceImpl extends ApiServiceStub {
        @Override
        public void helloChannel(
            ApiServerChannel<ApiTypes.HelloChannelMessage, ApiTypes.HelloChannelMessage, Object> channel
        ) throws Exception {
            channel.receive();
            channel.send(new ApiTypes.HelloChannelMessage(ApiTypes.HelloChannelMsgTypeEnum.PONG, Map.of("source", "java")));
            channel.close(new ApiTypes.DefaultConnectionClose(1000, "single channel complete", null));
        }
    }

    private static final class DemoServiceImpl extends DemoServiceStub {
        @Override
        public ApiTypes.ApiDemoA abc(DemoTypes.AbcQuery query) {
            return demoModel("header-ok");
        }

        @Override
        public DemoTypes.TestPostResponse testPost(DemoTypes.TestPostJSON json) {
            return new DemoTypes.TestPostResponse(
                List.of("test_post", json.req1()),
                Map.of("req2", new ApiTypes.ApiDemoMap(json.req2().longValue()))
            );
        }

        @Override
        public DemoTypes.DeleteResponse delete(DemoTypes.DeleteQuery query) {
            return new DemoTypes.DeleteResponse(
                List.of(query.arg1()),
                List.of(new DemoTypes.AnonDeleteAnonList(7L, List.of("xml")))
            );
        }

        @Override
        public DemoTypes.PostDeprecatedResponse postDeprecated(DemoTypes.PostDeprecatedJSON json) {
            return new DemoTypes.PostDeprecatedResponse(List.of(json.req1()));
        }

        @Override
        public DemoTypes.RawResponse raw() {
            return new DemoTypes.RawResponse(List.of("raw"), Map.of(1L, List.of(demoModel("raw"))));
        }

        @Override
        public DemoTypes.MapModelResponse mapModel() {
            return new DemoTypes.MapModelResponse();
        }

        @Override
        public DemoTypes.FormSubmitResponse formSubmit(DemoTypes.FormSubmitForm form) {
            return new DemoTypes.FormSubmitResponse(form.title(), form.count(), form.enabled());
        }

        @Override
        public DemoTypes.PutDemoResponse putDemo(DemoTypes.PutDemoQuery query, DemoTypes.PutDemoJSON json) {
            return new DemoTypes.PutDemoResponse(
                List.of(query.arg1(), json.req1()),
                new DemoTypes.AnonFunc1putAnonKv(json.req2().longValue(), List.of(query.arg2().doubleValue(), json.req2().doubleValue()))
            );
        }

        @Override
        public DemoTypes.ErrorDemoResponse errorDemo(DemoTypes.ErrorDemoQuery query) {
            String mode = query == null || query.mode() == null ? "ok" : query.mode();
            return switch (mode) {
                case "rate_limit" -> throwApiError(new ApiErrorPayload(
                    "DemoErr.RATE_LIMITED",
                    "",
                    "",
                    ApiErrors.DEMOERR_RATE_LIMITED,
                    "",
                    new ApiToastPayload("demo.rate_limited", "warning", "请求过于频繁，请稍后再试", "请等待 30 秒后重试")
                ));
                case "unknown" -> throwApiError(new ApiErrorPayload(
                    "",
                    "",
                    "",
                    70001,
                    "example undefined business error",
                    new ApiToastPayload("", "error", "", "")
                ));
                default -> new DemoTypes.ErrorDemoResponse("ok");
            };
        }

        @Override
        public void sweepEvents(
            ApiTypes.SweepOpen openData,
            ApiServerStream<DemoTypes.SweepStreamMessage, ApiTypes.ConnectionClose> stream
        ) throws Exception {
            stream.send(DemoTypes.SweepStreamMessageVariants.state(
                new ApiTypes.SweepState("java sweep " + openData.runId())
            ));
            stream.close(new ApiTypes.ConnectionClose(1000, "example stream complete", null));
        }

        @Override
        public void assistantSession(
            ApiTypes.AssistantOpen openData,
            ApiServerChannel<DemoTypes.AssistantClientMessage, DemoTypes.AssistantServerMessage, ApiTypes.ConnectionClose> channel
        ) throws Exception {
            DemoTypes.AssistantClientMessage first = channel.receive();
            if (first == null) {
                channel.close(new ApiTypes.ConnectionClose(1000, "empty session", null));
                return;
            }
            DemoTypes.dispatchAssistantClientMessage(first, new DemoTypes.AssistantClientMessageHandlers<Void>() {
                @Override
                public Void input(ApiTypes.AssistantInput data, DemoTypes.AssistantClientMessage message) throws Exception {
                    channel.send(DemoTypes.AssistantServerMessageVariants.delta(
                        new ApiTypes.AssistantDelta(openData.sessionId() + ":" + data.text())
                    ));
                    return null;
                }

                @Override
                public Void cancel(ApiTypes.AssistantCancel data, DemoTypes.AssistantClientMessage message) throws Exception {
                    channel.close(new ApiTypes.ConnectionClose(1000, data.reason(), null));
                    return null;
                }
            });
            DemoTypes.AssistantClientMessage second = channel.receive();
            if (second != null) {
                DemoTypes.dispatchAssistantClientMessage(second, new DemoTypes.AssistantClientMessageHandlers<Void>() {
                    @Override
                    public Void input(ApiTypes.AssistantInput data, DemoTypes.AssistantClientMessage message) {
                        return null;
                    }

                    @Override
                    public Void cancel(ApiTypes.AssistantCancel data, DemoTypes.AssistantClientMessage message) throws Exception {
                        channel.close(new ApiTypes.ConnectionClose(1000, data.reason(), null));
                        return null;
                    }
                });
            }
        }

        private static DemoTypes.ErrorDemoResponse throwApiError(ApiErrorPayload payload) {
            throw new ApiError(payload, "api.demo.get.errordemo", "", null);
        }
    }

    private static final class BinaryServiceImpl extends BinaryServiceStub {
        @Override
        public BinaryTypes.PacketResponse packet(BinaryTypes.PacketQuery query, BinaryTypes.DemoPacket binary) {
            BinaryTypes.DemoPacketBody body = binary.body();
            return new BinaryTypes.PacketResponse(
                query.trace(),
                1L,
                binary.header().itemCount().longValue(),
                new String(body.payload(), StandardCharsets.UTF_8),
                body.scores().stream().mapToDouble(Double::doubleValue).sum(),
                new String(body.items().get(0).label(), StandardCharsets.UTF_8),
                body.items().stream().map(BinaryTypes.DemoPacketItem::id).toList(),
                body.checksum()
            );
        }

        @Override
        public BinaryTypes.AuditPacketResponse auditPacket(BinaryTypes.AuditPacketQuery query, BinaryTypes.AuditPacket binary) {
            return new BinaryTypes.AuditPacketResponse(
                query.trace(),
                binary.header().itemCount().longValue(),
                binary.body().checksum()
            );
        }
    }

    private static final class HelloServiceImpl extends HelloServiceStub {
        @Override
        public HelloTypes.StringResponse string() {
            return new HelloTypes.StringResponse();
        }
    }

    private static final class StaticServiceImpl extends StaticServiceStub {
        @Override
        public StaticTypes.DocJsonResponse docJson() {
            return new StaticTypes.DocJsonResponse();
        }

        @Override
        public StaticTypes.DochahaResponse dochaha() {
            return new StaticTypes.DochahaResponse("hello world");
        }
    }

    private static final class ConflictServiceImpl extends ConflictServiceStub {
        @Override
        public ApiTypes.BlueprintsApiConflictConflictModel defaultValue(ConflictTypes.DefaultQuery query) {
            return new ApiTypes.BlueprintsApiConflictConflictModel(
                "api-default",
                query.classValue(),
                ApiTypes.KeywordEnum.DEFAULT_VALUE
            );
        }
    }

    private static final class AltConflictServiceImpl
        extends com.example.apiblueprint.alt.routes.alt.conflict.ConflictServiceStub {
        @Override
        public com.example.apiblueprint.alt.runtime.ApiTypes.BlueprintsAltConflictConflictModel defaultValue(
            com.example.apiblueprint.alt.routes.alt.conflict.ConflictTypes.DefaultQuery query
        ) {
            return new com.example.apiblueprint.alt.runtime.ApiTypes.BlueprintsAltConflictConflictModel(
                "alt-default",
                query.classValue(),
                com.example.apiblueprint.alt.runtime.ApiTypes.KeywordEnum.CLASS_VALUE
            );
        }
    }

    private static ApiTypes.ApiDemoA demoModel(String label) {
        return new ApiTypes.ApiDemoA(
            label,
            1,
            1.5f,
            List.of(1L, 2L, 3L),
            List.of(new ApiTypes.ApiDemoSubA(Map.of("a", 1), List.of(new ApiTypes.ApiDemoMap(1L)))),
            ApiTypes.ColorEnum.RED,
            ApiTypes.StatusEnum.RUNNING,
            List.of(ApiTypes.StatusEnum.PENDING, ApiTypes.StatusEnum.RUNNING)
        );
    }
}
