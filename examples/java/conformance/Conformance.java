package com.example.apiblueprint.conformance;

import com.example.apiblueprint.api.routes.api.binary.GenBinaryTypes;
import com.example.apiblueprint.api.routes.api.conflict.GenConflictTypes;
import com.example.apiblueprint.api.routes.api.demo.GenDemoTypes;
import com.example.apiblueprint.api.routes.api.media.GenMediaTypes;
import com.example.apiblueprint.api.runtime.GenApiError;
import com.example.apiblueprint.api.runtime.GenApiErrors;
import com.example.apiblueprint.api.runtime.GenApiFilePart;
import com.example.apiblueprint.api.runtime.GenApiRawResponse;
import com.example.apiblueprint.api.runtime.GenApiRequestOptions;
import com.example.apiblueprint.api.runtime.GenApiStreamResponse;
import com.example.apiblueprint.api.runtime.GenApiTypes;
import com.example.apiblueprint.api.transports.http.GenHttpApiConfig;
import com.example.apiblueprint.api.transports.http.HttpApiClient;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
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
        Set<String> selected = scenarioSet(args.length > 1 ? args[1] : "rpc,binary,form,error,naming,sse,websocket,raw,xml,static,header,scalar,enum,map,deprecated,empty-response,audit-binary,binary-response,media,request-options,media-filename-edge,media-error,single-channel");
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
        if (selected.contains("empty-response")) {
            checkEmptyResponse(client);
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
        if (selected.contains("binary-response")) {
            checkBinaryResponse(client);
        }
        if (selected.contains("media")) {
            checkMedia(client);
        }
        if (selected.contains("request-options")) {
            checkRequestOptions(baseUrl);
        }
        if (selected.contains("media-filename-edge")) {
            checkMediaFilenameEdge(client);
        }
        if (selected.contains("media-error")) {
            checkMediaError(client);
        }
        if (selected.contains("error")) {
            checkTypedErrors(client);
        }
        if (selected.contains("naming")) {
            checkNaming(client, altClient);
        }
        if (selected.contains("sse")) {
            checkUnsupported(() -> client.demo.subscribeSweepEvents(new GenApiTypes.SweepOpen("java-sse", null)), "stream");
        }
        if (selected.contains("websocket")) {
            checkUnsupported(() -> client.demo.openAssistantSession(new GenApiTypes.AssistantOpen("java-ws")), "channel");
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
        GenDemoTypes.TestPostResponse post = client.demo.testPost(new GenDemoTypes.TestPostJSON("java", 7));
        require(Objects.equals(List.of("test_post", "java"), post.list()), "testPost.list mismatch: " + post);
        require(Objects.equals(7L, post.map().get("req2").haha()), "testPost.map.req2 mismatch: " + post);

        GenDemoTypes.PutDemoResponse put = client.demo.putDemo(
            new GenDemoTypes.PutDemoQuery("query", 3.5f, null),
            new GenDemoTypes.PutDemoJSON("body", 9)
        );
        require(Objects.equals(List.of("query", "body"), put.list()), "putDemo.list mismatch: " + put);
        require(Objects.equals(9L, put.anonKv().kv1()), "putDemo.anonKv.kv1 mismatch: " + put.anonKv());
    }

    private static void checkForm(HttpApiClient client) throws Exception {
        GenDemoTypes.FormSubmitResponse response = client.demo.formSubmit(
            new GenDemoTypes.FormSubmitForm("java-form", 4, true)
        );
        require(Objects.equals("java-form", response.summary()), "form.summary mismatch: " + response);
        require(Objects.equals(4, response.count()), "form.count mismatch: " + response);
        require(Boolean.TRUE.equals(response.enabled()), "form.enabled mismatch: " + response);
    }

    private static void checkDeprecated(HttpApiClient client) throws Exception {
        GenDemoTypes.PostDeprecatedResponse response = client.demo.postDeprecated(
            new GenDemoTypes.PostDeprecatedJSON("java-deprecated", 3)
        );
        require(Objects.equals(List.of("java-deprecated"), response.list()), "deprecated mismatch: " + response);
    }

    private static void checkEmptyResponse(HttpApiClient client) throws Exception {
        Object response = client.demo.emptyResponse();
        require(response != null, "empty response returned null");
    }

    private static void checkBinary(HttpApiClient client) throws Exception {
        GenBinaryTypes.PacketResponse response = client.binary.packet(
            new GenBinaryTypes.PacketQuery("java-typed"),
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
        GenBinaryTypes.AuditPacketResponse response = client.binary.auditPacket(
            new GenBinaryTypes.AuditPacketQuery("java-audit"),
            buildAuditPacket()
        );
        require(Objects.equals("java-audit", response.trace()), "audit.trace mismatch: " + response);
        require(Objects.equals(2L, response.itemCount()), "audit.itemCount mismatch: " + response);
        require(Objects.equals(2L, response.checksum()), "audit.checksum mismatch: " + response);
    }

    private static void checkBinaryResponse(HttpApiClient client) throws Exception {
        GenBinaryTypes.AuditPacket response = client.binary.auditPacketResponse();
        require(Objects.equals(buildAuditPacket(), response), "binary response mismatch: " + response);
    }

    private static void checkMedia(HttpApiClient client) throws Exception {
        GenApiRawResponse preview = client.media.mediaPreview(
            new GenApiTypes.MediaPreviewRequest(
                "java-media",
                GenApiFilePart.of("preview.jpg", "image/jpeg", sampleJpeg())
            )
        );
        require(preview.contentType().startsWith("image/jpeg"), "media preview contentType=" + preview.contentType());
        require(startsWith(preview.body(), (byte) 0xff, (byte) 0xd8), "media preview body mismatch");

        GenApiRawResponse frame = client.media.mediaFrame();
        require(frame.contentType().startsWith("image/jpeg"), "media frame contentType=" + frame.contentType());
        require(Arrays.equals(sampleJpeg(), frame.body()), "media frame body mismatch");

        GenApiRawResponse download = client.media.mediaDownload();
        require(Objects.equals("media-report.xlsx", download.filename()), "media download filename=" + download.filename());
        require(startsWith(download.body(), (byte) 'P', (byte) 'K'), "media download body mismatch");

        GenApiRawResponse dynamic = client.media.mediaDownloadDynamic();
        require(
            Objects.equals("media-report-dynamic.xlsx", dynamic.filename()),
            "media dynamic filename=" + dynamic.filename()
        );
        require(startsWith(dynamic.body(), (byte) 'P', (byte) 'K'), "media dynamic body mismatch");

        try (GenApiStreamResponse stream = client.media.mediaMjpeg()) {
            String chunk = new String(stream.readAllBytes(), StandardCharsets.ISO_8859_1);
            require(chunk.contains("--frame"), "media mjpeg chunk=" + chunk);
        }
    }

    private static void checkRequestOptions(String baseUrl) throws Exception {
        HttpApiClient timeoutClient = new HttpApiClient(
            new GenHttpApiConfig(
                baseUrl,
                Map.of("x-options-default", "default", "x-options-token", "default"),
                Duration.ofMillis(20)
            )
        );
        GenApiTypes.RequestOptionsResponse ok = timeoutClient.demo.requestOptions(
            new GenDemoTypes.RequestOptionsQuery(30),
            GenApiRequestOptions.builder()
                .header("x-options-token", "per-call")
                .timeout(Duration.ofSeconds(1))
                .build()
        );
        require(Objects.equals("ok", ok.status()), "requestOptions.status mismatch: " + ok);
        require(Objects.equals(30, ok.delayMs()), "requestOptions.delayMs mismatch: " + ok);

        boolean timedOut = false;
        try {
            timeoutClient.demo.requestOptions(
                new GenDemoTypes.RequestOptionsQuery(120),
                GenApiRequestOptions.builder()
                    .header("x-options-token", "per-call")
                    .timeout(Duration.ofMillis(10))
                    .build()
            );
        } catch (Exception error) {
            timedOut = true;
        }
        require(timedOut, "request options short timeout did not fail");
    }

    private static void checkMediaFilenameEdge(HttpApiClient client) throws Exception {
        GenApiRawResponse response = client.media.mediaDownloadFilenameEdge();
        require(Objects.equals("媒体报告.xlsx", response.filename()), "media filename edge=" + response.filename());
        require(startsWith(response.body(), (byte) 'P', (byte) 'K'), "media filename edge body mismatch");
    }

    private static void checkMediaError(HttpApiClient client) throws Exception {
        GenApiRawResponse ok = client.media.mediaErrorFrame(new GenMediaTypes.MediaErrorFrameQuery("ok"));
        require(ok.contentType().startsWith("image/jpeg"), "media error contentType=" + ok.contentType());
        require(startsWith(ok.body(), (byte) 0xff, (byte) 0xd8), "media error body mismatch");

        GenApiError rateLimited = expectApiError(
            () -> client.media.mediaErrorFrame(new GenMediaTypes.MediaErrorFrameQuery("rate_limit")),
            "api.media.get.errorframe"
        );
        require(rateLimited.is(GenApiErrors.DemoErr.RATE_LIMITED), "media error entry mismatch: " + rateLimited.id());
    }

    private static void checkTypedErrors(HttpApiClient client) throws Exception {
        GenDemoTypes.ErrorDemoResponse ok = client.demo.errorDemo(new GenDemoTypes.ErrorDemoQuery("ok"));
        require(Objects.equals("ok", ok.status()), "errorDemo.ok mismatch: " + ok);

        GenApiError rateLimited = expectApiError(() -> client.demo.errorDemo(new GenDemoTypes.ErrorDemoQuery("rate_limit")));
        require(rateLimited.is(GenApiErrors.DemoErr.RATE_LIMITED), "rate limit entry mismatch: " + rateLimited.id());
        require(rateLimited.code() == GenApiErrors.DEMOERR_RATE_LIMITED, "rate limit code mismatch: " + rateLimited.code());
        String rateToast = GenApiError.resolveApiToast(rateLimited.toast(), null, rateLimited.getMessage());
        require(Objects.equals("请等待 30 秒后重试", rateToast), "rate limit toast mismatch: " + rateToast);

        GenApiError unknown = expectApiError(() -> client.demo.errorDemo(new GenDemoTypes.ErrorDemoQuery("unknown")));
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
        GenApiTypes.BlueprintsApiConflictConflictModel api =
            client.conflict.defaultValue(new GenConflictTypes.DefaultQuery("java-api"));
        require(Objects.equals("api-default", api.defaultValue()), "api conflict default mismatch: " + api);
        require(Objects.equals("java-api", api.classValue()), "api conflict class mismatch: " + api);
        require(api.enumValue() == GenApiTypes.KeywordEnum.DEFAULT_VALUE, "api conflict enum mismatch: " + api);

        com.example.apiblueprint.alt.runtime.GenApiTypes.BlueprintsAltConflictConflictModel alt =
            altClient.conflict.defaultValue(
                new com.example.apiblueprint.alt.routes.alt.conflict.GenConflictTypes.DefaultQuery("java-alt")
            );
        require(Objects.equals("alt-default", alt.defaultValue()), "alt conflict default mismatch: " + alt);
        require(Objects.equals("java-alt", alt.classValue()), "alt conflict class mismatch: " + alt);
        require(
            alt.enumValue() == com.example.apiblueprint.alt.runtime.GenApiTypes.KeywordEnum.CLASS_VALUE,
            "alt conflict enum mismatch: " + alt
        );
    }

    private static GenBinaryTypes.DemoPacket buildPacket() {
        byte[] payload = "payload-ok".getBytes(StandardCharsets.UTF_8);
        return new GenBinaryTypes.DemoPacket(
            new GenBinaryTypes.DemoPacketHeader(
                GenBinaryTypes.DemoPacketFlagsValues.HASPAYLOAD | GenBinaryTypes.DemoPacketFlagsValues.HASSCORES,
                0x010203,
                7,
                2,
                (long) payload.length
            ),
            new GenBinaryTypes.DemoPacketBody(
                List.of(
                    new GenBinaryTypes.DemoPacketItem(11L, true, 1.25d, 5, "alpha".getBytes(StandardCharsets.UTF_8)),
                    new GenBinaryTypes.DemoPacketItem(22L, false, 2.5d, 4, "beta".getBytes(StandardCharsets.UTF_8))
                ),
                payload,
                List.of(3.5d, 4.5d),
                12L
            )
        );
    }

    private static GenBinaryTypes.AuditPacket buildAuditPacket() {
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

    private static byte[] sampleJpeg() {
        return new byte[] {
            (byte) 0xff, (byte) 0xd8, (byte) 0xff, (byte) 0xe0, 0x00, 0x10,
            'J', 'F', 'I', 'F', 0x00, 0x01, 0x01, 0x01, 0x00, 0x01,
            0x00, 0x01, 0x00, 0x00, (byte) 0xff, (byte) 0xd9
        };
    }

    private static boolean startsWith(byte[] body, byte... prefix) {
        if (body.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (body[i] != prefix[i]) {
                return false;
            }
        }
        return true;
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

    private static GenApiError expectApiError(ThrowingRunnable action) throws Exception {
        return expectApiError(action, "api.demo.get.errordemo");
    }

    private static GenApiError expectApiError(ThrowingRunnable action, String routeId) throws Exception {
        try {
            action.run();
        } catch (GenApiError error) {
            require(Objects.equals(routeId, error.routeId()), "GenApiError.routeId mismatch: " + error.routeId());
            require(error.rawBody() != null && !error.rawBody().isBlank(), "GenApiError raw body is empty");
            return error;
        }
        throw new IllegalStateException("expected GenApiError");
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
