from __future__ import annotations

import subprocess

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint, Error, Model, provider
from api_blueprint.engine.model import String
from api_blueprint.engine.wrapper import GeneralWrapper
from api_blueprint.writer.golang import GolangResponseWrapper
from api_blueprint.writer.golang.writer import GolangWriter


def test_golang_response_wrapper_preserves_generic_type_parameters():
    wrapper = GolangResponseWrapper("RSP_JSON", GeneralWrapper)
    assert wrapper.proto_def_name == "RSP_JSON_GeneralWrapper[T any]"
    assert wrapper.generic_types(True) == "[T any]"


def test_golang_writer_uses_fixed_providers_package(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    provider_file = output_dir / "views" / "providers" / "gen_provider.go"
    provider_impl = output_dir / "views" / "providers" / "impl_provider.go"
    provider_context = output_dir / "views" / "providers" / "gen_context.go"
    provider_executor = output_dir / "views" / "providers" / "gen_executor.go"
    route_file = output_dir / "views" / "routes" / "api" / "demo" / "gen_protos.go"
    expected_provider_import = f'providers "example.com/generated/{output_dir.name}/views/providers"'

    assert provider_file.is_file()
    assert provider_context.is_file()
    assert provider_executor.is_file()
    provider_text = provider_file.read_text(encoding="utf-8")
    provider_impl_text = provider_impl.read_text(encoding="utf-8")
    provider_context_text = provider_context.read_text(encoding="utf-8")
    provider_executor_text = provider_executor.read_text(encoding="utf-8")
    assert 'package providers' in provider_text
    assert expected_provider_import in route_file.read_text(encoding="utf-8")
    assert "func (ctx *Context[Q, B, P]) Next()" in provider_context_text
    assert "ctx.Gin.Next()" not in provider_context_text
    assert "type RouteInfo struct" in provider_context_text
    assert "Route    *RouteInfo" in provider_context_text
    assert "type ProviderSpec struct" in provider_text
    assert "Handler any" in provider_text
    assert "type Indexer[Q, B, P any] struct" in provider_text
    assert "func RegisterProviderFactory(name string, factory ProviderFactory)" in provider_text
    assert "func SelectProvider[Q, B, P any]" in provider_impl_text
    assert "func SelectWithSpec[Q, B, P any]" not in provider_text
    assert "func SelectInternal[Q, B, P any]" not in provider_text
    assert "func Select[Q, B, P any]" not in provider_impl_text
    assert "func RegisterProvider(" not in provider_text
    assert "func GetProvider(" not in provider_text
    assert "func NewRouteExecutor[Q, B, P any](" in provider_executor_text
    assert "NewRouteExecutorWithInfo" not in provider_executor_text
    assert "NewRouteExecutorWithPlan" not in provider_executor_text
    assert "NewRouteExecutorWithProviders" not in provider_executor_text
    assert "type RoutePlan" not in provider_executor_text
    assert "routePlan" not in provider_executor_text
    assert "ctx.Route = &executor.Route" in provider_executor_text
    assert "ctx.Abort(ctx.Req.Error)" in (output_dir / "views" / "providers" / "gen_req.go").read_text(
        encoding="utf-8"
    )


def test_golang_writer_can_use_contract_graph_route_adapter(monkeypatch, tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    graph = build_contract_graph([bp])

    def reject_legacy_router_contract(_router):
        raise AssertionError("legacy router route_contract should not be used")

    monkeypatch.setattr(
        "api_blueprint.writer.core.contract_adapters.route_contract_from_router",
        reject_legacy_router_contract,
    )

    writer = GolangWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    interface_text = (output_dir / "views" / "routes" / "api" / "demo" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    assert "Ping(ctx *CTX_Ping, req *REQ_Ping)" in interface_text


def test_golang_contract_graph_adapter_owns_request_and_response_models(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    class SubmitJson(Model):
        value = String(description="value")

    class SubmitResponse(Model):
        status = String(description="status")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.POST("/submit").ARGS(q=String(description="q")).REQ(SubmitJson).RSP(SubmitResponse)

    graph = build_contract_graph([bp])
    router.req_query = None
    router.req_json = None
    router.rsp_model = None

    writer = GolangWriter(output_dir, contract_graph=graph)
    writer.register(bp)
    writer.gen()

    route_models = (output_dir / "views" / "routes" / "api" / "demo" / "gen_protos.go").read_text(
        encoding="utf-8"
    )
    shared_models = (
        output_dir
        / "views"
        / "routes"
        / "api"
        / "_gen_protos"
        / "protos.go"
    ).read_text(encoding="utf-8")
    assert "type REQ_Submit_QUERY struct" in route_models
    assert "type REQ_Submit_JSON = protos.SubmitJson" in route_models
    assert "type RSP_Submit_BODY = protos.SubmitResponse" in route_models
    assert "type SubmitJson struct" in shared_models
    assert "type SubmitResponse struct" in shared_models


def test_golang_writer_can_generate_core_without_http_adapter(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    stale_engine = output_dir / "views" / "engine.go"
    stale_http = output_dir / "views" / "api" / "demo" / "_http"
    stale_http.mkdir(parents=True)
    stale_engine.parent.mkdir(parents=True, exist_ok=True)
    stale_engine.write_text("package views\n", encoding="utf-8")
    (stale_http / "gen_interface.go").write_text("package httptransport\n", encoding="utf-8")

    writer = GolangWriter(output_dir, enabled_transports=())
    writer.register(bp)
    writer.gen()

    assert not (output_dir / "views" / "_http").exists()
    assert not (output_dir / "views" / "api" / "_http").exists()
    assert not (output_dir / "views" / "api" / "demo" / "_http").exists()
    assert not (output_dir / "views" / "engine.go").exists()

    generated_core = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            output_dir / "views" / "routes" / "api" / "gen_blueprint.go",
            output_dir / "views" / "routes" / "api" / "demo" / "gen_interface.go",
            output_dir / "views" / "providers" / "gen_context.go",
            output_dir / "views" / "providers" / "gen_req.go",
            output_dir / "views" / "providers" / "gen_rsp.go",
        )
        if path.is_file()
    )
    assert "github.com/gin-gonic/gin" not in generated_core
    assert "RequireHTTP" not in generated_core


def test_golang_writer_generates_core_only_when_no_http_adapter_is_enabled(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir, enabled_transports=())
    writer.register(bp)
    writer.gen()

    assert (output_dir / "views" / "routes" / "api" / "demo" / "gen_interface.go").is_file()
    assert not (output_dir / "views" / "transports" / "http").exists()


def test_golang_writer_generates_http_adapter_separately_from_core(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    root_adapter = output_dir / "views" / "transports" / "http" / "api" / "gen_blueprint.go"
    route_adapter = output_dir / "views" / "transports" / "http" / "api" / "demo" / "gen_interface.go"
    core_route = output_dir / "views" / "routes" / "api" / "demo" / "gen_interface.go"

    assert root_adapter.is_file()
    assert route_adapter.is_file()
    root_adapter_text = root_adapter.read_text(encoding="utf-8")
    route_adapter_text = route_adapter.read_text(encoding="utf-8")
    assert "package api" in root_adapter_text
    assert "sharedroot" not in root_adapter_text
    assert "Router *sharedroot.Router" not in root_adapter_text
    assert "package demo" in route_adapter_text
    assert 'github.com/gin-gonic/gin' in route_adapter_text
    assert "func Mount(eng *gin.Engine, impl *shared.Router) *shared.Router" in route_adapter_text
    assert "func NewRouter(eng *gin.Engine) *shared.Router" in route_adapter_text
    assert "func NewImpl(eng *gin.Engine) *shared.Router" in route_adapter_text
    assert "return NewRouter(eng)" in route_adapter_text
    assert 'httptransport.GET(' in route_adapter_text
    assert "sharedprovider.NewRouteExecutor(" in route_adapter_text
    assert 'Root:      "api"' in route_adapter_text
    assert 'Group:     "demo"' in route_adapter_text
    assert 'Namespace: "demo"' in route_adapter_text
    assert 'Service:   "DemoService"' in route_adapter_text
    assert 'Operation: "Ping"' in route_adapter_text
    assert 'RouteID:   "api.demo.get.ping"' in route_adapter_text
    assert 'Path:      "/api/demo/ping"' in route_adapter_text
    assert 'Methods:   []string{"GET"}' in route_adapter_text
    assert "Transport: sharedprovider.TransportHTTP" in route_adapter_text
    assert "\n\t\t\t\"\",\n" in route_adapter_text
    assert "eng,\n\n\t\tfalse," not in route_adapter_text
    assert "NewRouteExecutorWithPlan" not in route_adapter_text
    assert 'github.com/gin-gonic/gin' not in core_route.read_text(encoding="utf-8")
    assert "func NewImpl(eng *gin.Engine)" not in core_route.read_text(encoding="utf-8")


def test_golang_writer_generates_stream_and_channel_contracts(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    class Open(Model):
        run_id = String(description="run id")

    class TaskState(Model):
        status = String(description="status")

    class TaskProgress(Model):
        value = String(description="value")

    class ClientInput(Model):
        text = String(description="text")

    bp = Blueprint(root="/api", providers=[provider.Req(), provider.Auth(), provider.Handle(), provider.Rsp()])
    with bp.group("/runs") as views:
        views.STREAM("/events").OPEN(Open).SERVER_MESSAGE(
            "TaskStreamMessage",
            state=TaskState,
            progress=TaskProgress,
        )
        views.CHANNEL("/chat").OPEN(Open).CLIENT_MESSAGE(ClientInput).SERVER_MESSAGE(TaskState)

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    core_interface = (output_dir / "views" / "routes" / "api" / "runs" / "gen_interface.go").read_text(encoding="utf-8")
    core_models = (output_dir / "views" / "routes" / "api" / "runs" / "gen_protos.go").read_text(encoding="utf-8")
    provider_connection = (output_dir / "views" / "providers" / "gen_connection.go").read_text(encoding="utf-8")
    http_adapter = (output_dir / "views" / "transports" / "http" / "api" / "runs" / "gen_interface.go").read_text(encoding="utf-8")
    impl = (output_dir / "views" / "routes" / "api" / "runs" / "impl.go").read_text(encoding="utf-8")
    gen_impl = (output_dir / "views" / "routes" / "api" / "runs" / "gen_impl.go").read_text(encoding="utf-8")

    assert (
        "Events(\n"
        "\t\tctx *CTX_Events,\n"
        "\t\tstream providers.Stream[OPEN_Events, TaskStreamMessage, CLOSE_Events],\n"
        "\t) error"
        in core_interface
    )
    assert (
        "Chat(\n"
        "\t\tctx *CTX_Chat,\n"
        "\t\tchannel providers.Channel[OPEN_Chat, SERVER_Chat_MESSAGE, CLIENT_Chat_MESSAGE, CLOSE_Chat],\n"
        "\t) error"
        in core_interface
    )
    assert "type TaskStreamMessage struct" in core_models
    assert "type CLOSE_Events = protos.DefaultConnectionClose" in core_models
    assert "type CLOSE_Chat = protos.DefaultConnectionClose" in core_models
    assert 'const TaskStreamMessageTypeState = "state"' in core_models
    assert "type Stream[O, S, CL any] interface" in provider_connection
    assert "Close(*CL) error" in provider_connection
    assert "Abort(code int, reason string) error" in provider_connection
    assert "type Channel[O, S, C, CL any] interface" in provider_connection
    assert 'Scope:     sharedprovider.ConnectionScope("session")' in http_adapter
    assert "httptransport.STREAM(" in http_adapter
    assert "httptransport.STREAM[" not in http_adapter
    assert "httptransport.CHANNEL(" in http_adapter
    assert "httptransport.CHANNEL[" not in http_adapter
    assert "connection scope[%s] is not supported by the default HTTP runtime" in (
        output_dir / "views" / "transports" / "http" / "gen_engine.go"
    ).read_text(encoding="utf-8")
    assert "serverMessage, err := NewTaskStreamMessageState(&serverData)" not in gen_impl
    assert "clientMessage, err := channel.Recv(ctx)" not in gen_impl
    assert 'return fmt.Errorf("not implemented")' in gen_impl
    assert "serverMessage, err := NewTaskStreamMessageState(&serverData)" not in impl
    assert "clientMessage, err := channel.Recv(ctx)" not in impl


def test_golang_http_adapter_respects_already_written_gin_response(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/callback").HTTP_RAW_RESPONSE()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_adapter = (output_dir / "views" / "transports" / "http" / "api" / "demo" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    http_runtime = (output_dir / "views" / "transports" / "http" / "gen_engine.go").read_text(encoding="utf-8")
    assert "sharedprovider.NewRouteExecutor(" in route_adapter
    assert 'RouteID:   "api.demo.post.callback"' in route_adapter
    assert "\n\t\t\t\"\",\n" in route_adapter
    assert "eng,\n\t\ttrue," in route_adapter
    assert "if ginCtx.Writer.Written() {" in http_runtime
    assert "ginCtx.JSON(http.StatusOK, response)" in http_runtime


def test_golang_provider_custom_enters_route_executor_sequence(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(
        root="/static",
        providers=[
            provider.Req(),
            provider.Custom("cache", "ttl=60s"),
            provider.Handle(),
            provider.Rsp(),
        ],
    )
    bp.GET("/doc").RSP(message=String(description="message"))

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_adapter = (output_dir / "views" / "transports" / "http" / "static" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    assert 'Root:      "static"' in route_adapter
    assert 'RouteID:   "static.static.get.doc"' in route_adapter
    assert '"req|cache=ttl=60s|handle|rsp=json@NoneWrapper"' in route_adapter


def test_golang_route_aware_provider_factory_runs_at_executor_creation(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    (output_dir / "views" / "providers" / "route_factory_test.go").write_text(
        """
package providers

import (
	"context"
	"testing"
)

type cacheProvider struct {
	calls *int
}

func (prov cacheProvider) GetName() string {
	return "cache"
}

func (prov cacheProvider) Handle(anyCtx ContextInterface) {
	*prov.calls++
	ctx := AdaptContext[any, any, any](anyCtx)
	if ctx.Route == nil || ctx.Route.Root != "static" {
		ctx.Abort(nil)
		return
	}
	ctx.Next()
}

func TestRouteAwareProviderFactory(t *testing.T) {
	factoryCalls := 0
	providerCalls := 0
	RegisterProviderFactory("cache", func(spec ProviderSpec) Provider {
		factoryCalls++
		if spec.Name != "cache" || spec.Data != "ttl=60s" {
			t.Fatalf("unexpected provider spec: %#v", spec)
		}
		if spec.Route.Root != "static" || spec.Route.Transport != TransportHTTP {
			t.Fatalf("unexpected route info: %#v", spec.Route)
		}
		if _, ok := spec.Handler.(RouteHandler[any, any, any]); !ok {
			t.Fatalf("handler is not route typed: %T", spec.Handler)
		}
		return cacheProvider{calls: &providerCalls}
	})

	executor := NewRouteExecutor(
		RouteInfo{Root: "static", RouteID: "static.static.get.doc", Transport: TransportHTTP},
		"cache=ttl=60s",
		func(c *Context[any, any, any], req *REQ[any, any]) (*any, error) {
			return nil, nil
		},
	)
	if factoryCalls != 1 {
		t.Fatalf("factory should run once at executor creation, got %d", factoryCalls)
	}

	for i := 0; i < 3; i++ {
		ctx := NewHTTPContext[any, any, any](context.Background(), nil, nil)
		if err := executor.Run(ctx); err != nil {
			t.Fatalf("executor run failed: %v", err)
		}
		if ctx.Route == nil || ctx.Route.RouteID != "static.static.get.doc" {
			t.Fatalf("context route not set: %#v", ctx.Route)
		}
	}
	if factoryCalls != 1 {
		t.Fatalf("factory should not run on request path, got %d", factoryCalls)
	}
	if providerCalls != 3 {
		t.Fatalf("provider should run once per request, got %d", providerCalls)
	}
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["go", "test", "./views/providers"],
        cwd=output_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_golang_writer_allows_business_root_named_providers(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    bp = Blueprint(root="/providers")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert (output_dir / "views" / "providers" / "gen_provider.go").is_file()
    assert (output_dir / "views" / "routes" / "providers" / "demo" / "gen_interface.go").is_file()


def test_golang_writer_generates_only_declared_error_models(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    class UsedErr(Model):
        BOOM = Error(1001, "boom")

    class UnusedErr(Model):
        NOISE = Error(1002, "noise")

    bp = Blueprint(root="/api", errors=[UsedErr])
    with bp.group("/demo") as views:
        views.GET("/ping").RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    assert (output_dir / "errors" / "used_err" / "gen_errors.go").is_file()
    assert not (output_dir / "errors" / "unused_err").exists()
