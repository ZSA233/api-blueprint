package com.example.apiblueprint.conformance;

import com.example.apiblueprint.api.routes.api.binary.BinaryTypes;
import com.example.apiblueprint.api.routes.api.conflict.ConflictTypes;
import com.example.apiblueprint.api.routes.api.demo.DemoTypes;
import com.example.apiblueprint.api.runtime.ApiError;
import com.example.apiblueprint.api.runtime.ApiErrors;
import com.example.apiblueprint.api.runtime.ApiTypes;
import com.example.apiblueprint.api.transports.http.HttpApiClient;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import java.util.Set;

public final class Conformance {
    private Conformance() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1 || args[0].isBlank()) {
            throw new IllegalArgumentException("base URL argument is required");
        }
        String baseUrl = args[0];
        Set<String> selected = scenarioSet(args.length > 1 ? args[1] : "rpc,binary,form,error,naming,sse,websocket,raw,xml,static,header,scalar,enum,map,deprecated,audit-binary,single-channel");
        HttpApiClient client = HttpApiClient.create(baseUrl);
        com.example.apiblueprint.alt.transports.http.HttpApiClient altClient =
            com.example.apiblueprint.alt.transports.http.HttpApiClient.create(baseUrl);

        if (selected.contains("rpc")) {
            checkRpc(client);
        }
        if (selected.contains("raw")) {
            checkRawHttp(baseUrl + "/api/demo/raw", "POST", "", "raw");
        }
        if (selected.contains("xml")) {
            checkRawHttp(baseUrl + "/api/demo/delete$?arg1=java-xml&arg2=7", "DELETE", "java-xml", "xml");
        }
        if (selected.contains("static")) {
            checkRawHttp(baseUrl + "/static/doc.json", "GET", "", "static.doc");
            checkRawHttp(baseUrl + "/static/dochaha", "GET", "hello world", "static");
        }
        if (selected.contains("header")) {
            checkHeader(baseUrl);
        }
        if (selected.contains("scalar")) {
            checkRawHttp(baseUrl + "/api/hello/string", "GET", "hello-string", "scalar.string");
            checkRawHttp(baseUrl + "/api/hello/uint64", "GET", "9007199254740991", "scalar.uint64");
        }
        if (selected.contains("enum")) {
            checkRawHttp(baseUrl + "/api/hello/string-emun", "GET", "\"a\"", "enum.string");
            checkRawHttp(baseUrl + "/api/hello/list-enum", "GET", "\"b\"", "enum.list");
        }
        if (selected.contains("map")) {
            checkRawHttp(baseUrl + "/api/demo/map_model", "POST", "101", "map.model");
            checkRawHttp(baseUrl + "/api/hello/abc?type=ping", "GET", "ping", "map.abc");
            checkRawHttp(baseUrl + "/api/hello/map-enum", "GET", "11", "map.enum");
        }
        if (selected.contains("deprecated")) {
            checkDeprecated(client);
        }
        if (selected.contains("form")) {
            checkForm(client);
        }
        if (selected.contains("binary")) {
            checkBinary(client);
        }
        if (selected.contains("audit-binary")) {
            checkAuditBinary(client);
        }
        if (selected.contains("error")) {
            checkTypedErrors(client);
        }
        if (selected.contains("naming")) {
            checkNaming(client, altClient);
        }
        if (selected.contains("sse")) {
            checkUnsupported(() -> client.demo.subscribeSweepEvents(new ApiTypes.SweepOpen("java-sse", null)), "stream");
        }
        if (selected.contains("websocket")) {
            checkUnsupported(() -> client.demo.openAssistantSession(new ApiTypes.AssistantOpen("java-ws")), "channel");
        }
        if (selected.contains("single-channel")) {
            checkUnsupported(() -> client.api.openHelloChannel(), "channel");
        }
        System.out.println("java conformance passed");
    }

    private static Set<String> scenarioSet(String raw) {
        return Set.of(Arrays.stream(raw.split(",")).map(String::trim).filter(item -> !item.isEmpty()).toArray(String[]::new));
    }

    private static void checkRpc(HttpApiClient client) throws Exception {
        DemoTypes.TestPostResponse post = client.demo.testPost(new DemoTypes.TestPostJSON("java", 7));
        require(Objects.equals(List.of("test_post", "java"), post.list()), "testPost.list mismatch: " + post);
        require(Objects.equals(7L, post.map().get("req2").haha()), "testPost.map.req2 mismatch: " + post);

        DemoTypes.PutDemoResponse put = client.demo.putDemo(
            new DemoTypes.PutDemoQuery("query", 3.5f, null),
            new DemoTypes.PutDemoJSON("body", 9)
        );
        require(Objects.equals(List.of("query", "body"), put.list()), "putDemo.list mismatch: " + put);
        require(Objects.equals(9L, put.anonKv().kv1()), "putDemo.anonKv.kv1 mismatch: " + put.anonKv());
    }

    private static void checkForm(HttpApiClient client) throws Exception {
        DemoTypes.FormSubmitResponse response = client.demo.formSubmit(
            new DemoTypes.FormSubmitForm("java-form", 4, true)
        );
        require(Objects.equals("java-form", response.summary()), "form.summary mismatch: " + response);
        require(Objects.equals(4, response.count()), "form.count mismatch: " + response);
        require(Boolean.TRUE.equals(response.enabled()), "form.enabled mismatch: " + response);
    }

    private static void checkDeprecated(HttpApiClient client) throws Exception {
        DemoTypes.PostDeprecatedResponse response = client.demo.postDeprecated(
            new DemoTypes.PostDeprecatedJSON("java-deprecated", 3)
        );
        require(Objects.equals(List.of("java-deprecated"), response.list()), "deprecated mismatch: " + response);
    }

    private static void checkBinary(HttpApiClient client) throws Exception {
        BinaryTypes.PacketResponse response = client.binary.packet(
            new BinaryTypes.PacketQuery("java-typed"),
            buildPacket()
        );
        require(Objects.equals("java-typed", response.trace()), "binary.trace mismatch: " + response);
        require(Objects.equals(1L, response.version()), "binary.version mismatch: " + response);
        require(Objects.equals(2L, response.itemCount()), "binary.itemCount mismatch: " + response);
        require(Objects.equals("payload-ok", response.payload()), "binary.payload mismatch: " + response);
        require(Objects.equals(8.0d, response.scoreSum()), "binary.scoreSum mismatch: " + response);
        require(Objects.equals("alpha", response.firstLabel()), "binary.firstLabel mismatch: " + response);
        require(Objects.equals(List.of(11L, 22L), response.itemIds()), "binary.itemIds mismatch: " + response);
        require(Objects.equals(12L, response.checksum()), "binary.checksum mismatch: " + response);
    }

    private static void checkAuditBinary(HttpApiClient client) throws Exception {
        BinaryTypes.AuditPacketResponse response = client.binary.auditPacket(
            new BinaryTypes.AuditPacketQuery("java-audit"),
            buildAuditPacket()
        );
        require(Objects.equals("java-audit", response.trace()), "audit.trace mismatch: " + response);
        require(Objects.equals(2L, response.itemCount()), "audit.itemCount mismatch: " + response);
        require(Objects.equals(2L, response.checksum()), "audit.checksum mismatch: " + response);
    }

    private static void checkTypedErrors(HttpApiClient client) throws Exception {
        DemoTypes.ErrorDemoResponse ok = client.demo.errorDemo(new DemoTypes.ErrorDemoQuery("ok"));
        require(Objects.equals("ok", ok.status()), "errorDemo.ok mismatch: " + ok);

        ApiError rateLimited = expectApiError(() -> client.demo.errorDemo(new DemoTypes.ErrorDemoQuery("rate_limit")));
        require(rateLimited.is(ApiErrors.DemoErr.RATE_LIMITED), "rate limit entry mismatch: " + rateLimited.id());
        require(rateLimited.code() == ApiErrors.DEMOERR_RATE_LIMITED, "rate limit code mismatch: " + rateLimited.code());
        String rateToast = ApiError.resolveApiToast(rateLimited.toast(), null, rateLimited.getMessage());
        require(Objects.equals("请等待 30 秒后重试", rateToast), "rate limit toast mismatch: " + rateToast);

        ApiError unknown = expectApiError(() -> client.demo.errorDemo(new DemoTypes.ErrorDemoQuery("unknown")));
        require(Objects.equals("", unknown.id()), "unknown id mismatch: " + unknown.id());
        require(unknown.code() == 70001, "unknown code mismatch: " + unknown.code());
        require(
            Objects.equals("example undefined business error", unknown.apiMessage()),
            "unknown message mismatch: code="
                + unknown.code()
                + " message="
                + unknown.apiMessage()
                + " raw="
                + unknown.rawBody()
        );
    }

    private static void checkNaming(
        HttpApiClient client,
        com.example.apiblueprint.alt.transports.http.HttpApiClient altClient
    ) throws Exception {
        ApiTypes.BlueprintsApiConflictConflictModel api =
            client.conflict.defaultValue(new ConflictTypes.DefaultQuery("java-api"));
        require(Objects.equals("api-default", api.defaultValue()), "api conflict default mismatch: " + api);
        require(Objects.equals("java-api", api.classValue()), "api conflict class mismatch: " + api);
        require(api.enumValue() == ApiTypes.KeywordEnum.DEFAULT_VALUE, "api conflict enum mismatch: " + api);

        com.example.apiblueprint.alt.runtime.ApiTypes.BlueprintsAltConflictConflictModel alt =
            altClient.conflict.defaultValue(
                new com.example.apiblueprint.alt.routes.alt.conflict.ConflictTypes.DefaultQuery("java-alt")
            );
        require(Objects.equals("alt-default", alt.defaultValue()), "alt conflict default mismatch: " + alt);
        require(Objects.equals("java-alt", alt.classValue()), "alt conflict class mismatch: " + alt);
        require(
            alt.enumValue() == com.example.apiblueprint.alt.runtime.ApiTypes.KeywordEnum.CLASS_VALUE,
            "alt conflict enum mismatch: " + alt
        );
    }

    private static BinaryTypes.DemoPacket buildPacket() {
        byte[] payload = "payload-ok".getBytes(StandardCharsets.UTF_8);
        return new BinaryTypes.DemoPacket(
            new BinaryTypes.DemoPacketHeader(
                BinaryTypes.DemoPacketFlagsValues.HASPAYLOAD | BinaryTypes.DemoPacketFlagsValues.HASSCORES,
                0x010203,
                7,
                2,
                (long) payload.length
            ),
            new BinaryTypes.DemoPacketBody(
                List.of(
                    new BinaryTypes.DemoPacketItem(11L, true, 1.25d, 5, "alpha".getBytes(StandardCharsets.UTF_8)),
                    new BinaryTypes.DemoPacketItem(22L, false, 2.5d, 4, "beta".getBytes(StandardCharsets.UTF_8))
                ),
                payload,
                List.of(3.5d, 4.5d),
                12L
            )
        );
    }

    private static BinaryTypes.AuditPacket buildAuditPacket() {
        return new BinaryTypes.AuditPacket(
            new BinaryTypes.AuditPacketHeader(BinaryTypes.AuditPacketFlagsValues.HASITEMS, 2),
            new BinaryTypes.AuditPacketBody(
                List.of(
                    new BinaryTypes.AuditPacketItem(11L, 101),
                    new BinaryTypes.AuditPacketItem(22L, 202)
                ),
                2L
            )
        );
    }

    private static void checkRawHttp(String url, String method, String snippet, String label) throws Exception {
        HttpResponse<String> response = HttpClient.newHttpClient().send(
            HttpRequest.newBuilder(URI.create(url)).method(method, HttpRequest.BodyPublishers.noBody()).build(),
            HttpResponse.BodyHandlers.ofString()
        );
        require(response.statusCode() == 200, label + " status=" + response.statusCode() + " body=" + response.body());
        if (!snippet.isEmpty()) {
            require(response.body().contains(snippet), label + " body=" + response.body());
        }
    }

    private static void checkHeader(String baseUrl) throws Exception {
        HttpResponse<String> response = HttpClient.newHttpClient().send(
            HttpRequest.newBuilder(URI.create(baseUrl + "/api/demo/abc"))
                .header("x-token", "conformance-token")
                .GET()
                .build(),
            HttpResponse.BodyHandlers.ofString()
        );
        require(response.statusCode() == 200, "header status=" + response.statusCode() + " body=" + response.body());
        require(response.body().contains("header-ok"), "header body=" + response.body());
    }

    private static ApiError expectApiError(ThrowingRunnable action) throws Exception {
        try {
            action.run();
        } catch (ApiError error) {
            require(Objects.equals("api.demo.get.errordemo", error.routeId()), "ApiError.routeId mismatch: " + error.routeId());
            require(error.rawBody() != null && !error.rawBody().isBlank(), "ApiError raw body is empty");
            return error;
        }
        throw new IllegalStateException("expected ApiError");
    }

    private static void checkUnsupported(ThrowingRunnable action, String snippet) throws Exception {
        try {
            action.run();
        } catch (UnsupportedOperationException error) {
            require(error.getMessage() != null && error.getMessage().contains(snippet), "unsupported message mismatch: " + error);
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
}
