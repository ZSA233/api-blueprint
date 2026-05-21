from __future__ import annotations

from pathlib import Path

from .helpers import *


def test_kotlin_generated_template_files_use_gen_names() -> None:
    template_root = Path("src/api_blueprint/writer/templates/kotlin")
    allowed_preserved_templates = {
        Path("routes/ApiGroupFacade.kt.j2"),
        Path("runtime/ApiClient.kt.j2"),
        Path("server/routes/ApiService.kt.j2"),
        Path("transports/http/HttpApiClient.kt.j2"),
    }

    non_gen_templates = {
        path.relative_to(template_root)
        for path in template_root.rglob("*.kt.j2")
        if not path.name.startswith("Gen") and path.relative_to(template_root) not in allowed_preserved_templates
    }

    assert non_gen_templates == set()
    assert (template_root / "runtime/GenApiTransport.kt.j2").is_file()
    assert (template_root / "transports/http/GenOkHttpApiTransport.kt.j2").is_file()


def test_kotlin_writer_generates_root_runtime_routes_and_http_transport_for_full_route_surface(tmp_path):
    class CommonErr(Model):
        UNKNOWN = Error(-1, "unknown")
        TOKEN_EXPIRE = Error(
            55555,
            "token登录态失效",
            toast=Toast(
                key="auth.token_expire",
                default="登录状态已失效，请重新登录",
                level="warning",
            ),
        )

    class SubmitJson(Model):
        value = String(description="value")

    class SubmitResponse(Model):
        status = String(description="status")

    class FormPayload(Model):
        label = String(description="label")

    class OpenPayload(Model):
        run_id = String(alias="run_id", description="run id")

    class ServerMessage(Model):
        status = String(description="status")

    class ClientMessage(Model):
        text = String(description="text")

    class CloseInfo(Model):
        reason = String(description="reason")

    bp = Blueprint(root="/api", errors=[CommonErr])
    bp.GET("/status").RSP(SubmitResponse)
    views = bp.group("/demo")
    views.GET("/ping").ARGS(q=String(description="q")).RSP(SubmitResponse)
    views.POST("/submit").REQ(SubmitJson).RSP(SubmitResponse)
    views.POST("/form").REQ_FORM(FormPayload).RSP(SubmitResponse)
    views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(ServerMessage).CLOSE(CloseInfo)
    views.CHANNEL("/chat").OPEN(OpenPayload).CLIENT_MESSAGE(ClientMessage).SERVER_MESSAGE(ServerMessage).CLOSE(CloseInfo)
    bp.is_built = True

    root_dir = tmp_path / "kotlin" / "com" / "example" / "generated" / "api"
    route_dir = root_dir / "routes" / "api" / "demo"
    runtime_dir = root_dir / "runtime"
    http_dir = root_dir / "transports" / "http"
    route_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)
    http_dir.mkdir(parents=True)
    (route_dir / "DemoApi.kt").write_text("// USER ROUTE FACADE\n", encoding="utf-8")
    (runtime_dir / "ApiClient.kt").write_text("// USER CLIENT FACADE\n", encoding="utf-8")
    (http_dir / "HttpApiClient.kt").write_text("// USER HTTP FACADE\n", encoding="utf-8")

    stale_route_dir = root_dir / "routes" / "demo"
    stale_route_dir.mkdir(parents=True)
    for stale_file in (
        stale_route_dir / "DemoApi.kt",
        stale_route_dir / "DemoApiModels.kt",
        runtime_dir / "ApiTransport.kt",
        runtime_dir / "ApiException.kt",
        runtime_dir / "Models.kt",
        http_dir / "HttpApiConfig.kt",
        http_dir / "OkHttpApiTransport.kt",
    ):
        stale_file.write_text("package stale\npublic class StaleGenerated\n", encoding="utf-8")

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated", base_url="http://localhost:2333")
    writer.register(bp)
    writer.gen()

    runtime_text = (runtime_dir / "GenApiTransport.kt").read_text(encoding="utf-8")
    errors_text = (runtime_dir / "GenApiErrors.kt").read_text(encoding="utf-8")
    catalog_text = (runtime_dir / "GenApiErrorLookup.kt").read_text(encoding="utf-8")
    generated_client_text = (runtime_dir / "GenApiClient.kt").read_text(encoding="utf-8")
    client_text = (runtime_dir / "ApiClient.kt").read_text(encoding="utf-8")
    route_text = (route_dir / "GenDemoApi.kt").read_text(encoding="utf-8")
    root_route_text = (root_dir / "routes" / "api" / "GenApiApi.kt").read_text(encoding="utf-8")
    route_facade_text = (route_dir / "DemoApi.kt").read_text(encoding="utf-8")
    route_types_text = (route_dir / "GenDemoTypes.kt").read_text(encoding="utf-8")
    transport_text = (http_dir / "GenOkHttpApiTransport.kt").read_text(encoding="utf-8")
    factory_text = (http_dir / "HttpApiClient.kt").read_text(encoding="utf-8")
    http_config_text = (http_dir / "GenHttpApiConfig.kt").read_text(encoding="utf-8")

    for generated_text in (
        runtime_text,
        errors_text,
        catalog_text,
        generated_client_text,
        route_text,
        route_types_text,
        transport_text,
        http_config_text,
    ):
        assert generated_text.startswith(KOTLIN_CLIENT_GENERATED_HEADER)
    assert (runtime_dir / "GenApiTypes.kt").is_file()
    assert (runtime_dir / "GenApiException.kt").is_file()
    assert (runtime_dir / "GenApiErrors.kt").is_file()
    assert (runtime_dir / "GenApiErrorLookup.kt").is_file()
    assert client_text == "// USER CLIENT FACADE\n"
    assert route_facade_text == "// USER ROUTE FACADE\n"
    assert factory_text == "// USER HTTP FACADE\n"
    assert not (runtime_dir / "ApiConfig.kt").exists()
    assert not (runtime_dir / "ApiTransport.kt").exists()
    assert not (runtime_dir / "ApiException.kt").exists()
    assert not (runtime_dir / "Models.kt").exists()
    assert not (runtime_dir / "GenModels.kt").exists()
    assert not (http_dir / "HttpApiConfig.kt").exists()
    assert not (http_dir / "OkHttpApiTransport.kt").exists()
    assert not stale_route_dir.exists()
    assert not (root_dir / "routes" / "api" / "api").exists()
    assert not (tmp_path / "kotlin" / "com" / "example" / "generated" / "endpoints").exists()
    assert not (tmp_path / "kotlin" / "com" / "example" / "generated" / "internal").exists()

    assert "public interface ApiTransport" in runtime_text
    assert "public data class ApiRequestOptions(" in runtime_text
    assert "public val options: ApiRequestOptions = ApiRequestOptions()" in runtime_text
    assert "public val timeout: Duration? = null" in runtime_text
    assert "public interface ApiSocketBridge<Send, Recv>" not in runtime_text
    assert "public interface ApiStreamBridge<Recv, Close>" in runtime_text
    assert "public interface ApiChannelBridge<Recv, Send, Close>" in runtime_text
    assert "public data class StreamConnectOptions<Recv, Close>" in runtime_text
    assert "public val messageSerializer: KSerializer<Recv>" in runtime_text
    assert "public val closeSerializer: KSerializer<Close>" in runtime_text
    assert "public data class ChannelConnectOptions<Recv, Send, Close>" in runtime_text
    assert "public val sendSerializer: KSerializer<Send>" in runtime_text
    assert "public fun <Recv, Close> openStream(" in runtime_text
    assert "public fun <Recv, Send, Close> openChannel(" in runtime_text
    assert (
        'val code = nested["code"]?.jsonPrimitive?.intOrNull ?: '
        "root[envelope.fields.code]?.jsonPrimitive?.intOrNull ?: 0"
    ) in runtime_text
    assert "val message = nestedMessage.ifBlank { root[envelope.fields.message]?.jsonPrimitive?.contentOrNull.orEmpty() }" in runtime_text
    assert "class ApiError" in errors_text
    assert "data class ApiErrorPayload" in errors_text
    assert "data class ApiToastSpec" in errors_text
    assert "fun resolveApiToast(" in errors_text
    assert "ERROR_CATALOG_BY_ID" not in errors_text
    assert '"CommonErr.UNKNOWN"' not in errors_text
    assert '"CommonErr.UNKNOWN"' in catalog_text
    assert "val ApiErrorsByID" in catalog_text
    assert "routeApiErrorsByCode" in catalog_text
    assert "const val TOKEN_EXPIRE: Int = 55555" in catalog_text
    assert 'default = "登录状态已失效，请重新登录"' in catalog_text
    assert "\\u767b" not in catalog_text
    assert "locales" not in catalog_text
    assert "public open class GenApiClient" in generated_client_text
    assert "public val demo: DemoApi = DemoApi(transport)" in generated_client_text

    assert "public open class GenDemoApi" in route_text
    assert "public open class GenApiApi" in root_route_text
    assert 'path = "/api/status"' in root_route_text
    assert "public open suspend fun ping(" in route_text
    assert "query: DemoPingQuery," in route_text
    assert "json: SubmitJson," in route_text
    assert "form: FormPayload," in route_text
    assert "options: ApiRequestOptions = ApiRequestOptions()," in route_text
    assert "options = options" in route_text
    assert "public open fun connectWs(" not in route_text
    assert "public open fun subscribeEvents(" in route_text
    assert "public open fun openChat(" in route_text
    assert 'connectionKind = "legacy_ws"' not in route_text
    assert 'connectionKind = "stream"' in route_text
    assert 'connectionKind = "channel"' in route_text
    assert "query = open.toQueryMap()" in route_text
    assert "open = open" in route_text
    assert "messageSerializer = ServerMessage.serializer()" in route_text
    assert "closeSerializer = CloseInfo.serializer()" in route_text
    assert "sendSerializer = ClientMessage.serializer()" in route_text
    assert "public data class DemoPingQuery" in route_types_text

    assert "public class OkHttpApiTransport" in transport_text
    assert "private val config: HttpApiConfig = HttpApiConfig()" in transport_text
    assert "override suspend fun execute(request: ApiRequest<*>): ApiResponse" in transport_text
    assert "config.defaultHeaders() + request.options.headers" in transport_text
    assert "clientWithTimeout(request.options.timeout ?: config.timeout).newCall" in transport_text
    assert "callTimeout(timeout.inWholeMilliseconds, TimeUnit.MILLISECONDS)" in transport_text
    assert 'toRequestBody("application/json; charset=utf-8".toMediaType())' in transport_text
    assert 'toRequestBody("application/x-www-form-urlencoded; charset=utf-8".toMediaType())' in transport_text
    assert "private fun encodeFormPayload(" in transport_text
    assert "override fun connectSocket(options: SocketConnectOptions): ApiSocketBridge" not in transport_text
    assert "override fun <Recv, Close> openStream(options: StreamConnectOptions<Recv, Close>)" in transport_text
    assert "override fun <Recv, Send, Close> openChannel(" in transport_text
    assert "options: ChannelConnectOptions<Recv, Send, Close>" in transport_text
    assert "OkHttpEventStreamBridge" in transport_text
    assert "WebSocketListener" in transport_text
    assert "InMemoryStreamBridge" not in transport_text
    assert "InMemoryChannelBridge" not in transport_text
    assert "public data class HttpApiConfig" in http_config_text
    assert 'public val baseUrl: String = "http://localhost:2333"' in http_config_text
    assert "public val timeout: Duration? = null" in http_config_text

def test_kotlin_writer_generates_custom_response_envelope_spec(tmp_path):
    class SubmitResponse(Model):
        status = String(description="status")

    class CustomEnvelope(ResponseEnvelope):
        ok = String(description="ok")
        payload = Field(description="payload")

        @classmethod
        def create(cls, data_cls: type[Model]) -> type[ResponseEnvelope]:
            raise NotImplementedError

        @classmethod
        def on_error(cls, err: Error) -> tuple[str, dict[str, object]]:
            return "error", {"ok": "false"}

    bp = Blueprint(root="/api")
    views = bp.group("/demo")
    views.GET("/wrapped", response_envelope=CustomEnvelope).RSP(SubmitResponse)
    bp.is_built = True

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated")
    writer.register(bp)
    writer.gen()

    root_dir = tmp_path / "kotlin" / "com" / "example" / "generated" / "api"
    runtime_models_text = (root_dir / "runtime" / "GenApiTypes.kt").read_text(encoding="utf-8")
    route_text = (root_dir / "routes" / "api" / "demo" / "GenDemoApi.kt").read_text(encoding="utf-8")
    route_facade_text = (root_dir / "routes" / "api" / "demo" / "DemoApi.kt").read_text(encoding="utf-8")
    client_facade_text = (root_dir / "runtime" / "ApiClient.kt").read_text(encoding="utf-8")
    http_facade_text = (root_dir / "transports" / "http" / "HttpApiClient.kt").read_text(encoding="utf-8")

    assert runtime_models_text.startswith(KOTLIN_CLIENT_GENERATED_HEADER)
    assert route_text.startswith(KOTLIN_CLIENT_GENERATED_HEADER)
    assert "CustomEnvelope<T>" not in runtime_models_text
    assert "public val payload: T" not in runtime_models_text
    assert "): SubmitResponse {" in route_text
    assert 'responseEnvelope = ApiResponseEnvelope(name = "CustomEnvelope", kind = "custom"' in route_text
    assert "public class DemoApi" in route_facade_text
    assert ": GenDemoApi(transport)" in route_facade_text
    assert "public class ApiClient" in client_facade_text
    assert ": GenApiClient(transport)" in client_facade_text
    assert "public fun createHttpApiClient" in http_facade_text
    assert "config: HttpApiConfig = HttpApiConfig()" in http_facade_text
