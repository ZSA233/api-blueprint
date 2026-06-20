from __future__ import annotations

from .helpers import *
from api_blueprint.engine.schema import Int


def test_golang_server_codegen_emits_multipart_and_raw_response_contracts(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text("module example.com/generated\n\ngo 1.23.8\n", encoding="utf-8")

    bp = Blueprint(root="/api", providers=[provider.Req(), provider.Handle(), provider.Rsp()])
    with bp.group("/media") as views:
        views.POST("/preview").REQ_MULTIPART(MediaUpload).RSP_BYTES(content_type="image/jpeg")
        views.GET("/download").RSP_FILE(content_type="application/vnd.ms-excel", filename="report.xls")
        views.GET("/mjpeg").RSP_BYTE_STREAM(content_type="multipart/x-mixed-replace")

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    req_provider = (output_dir / "providers" / "gen_req.go").read_text(encoding="utf-8")
    rsp_provider = (output_dir / "providers" / "gen_rsp.go").read_text(encoding="utf-8")
    shared_types = (output_dir / "routes" / "api" / "_gen_types" / "types.go").read_text(encoding="utf-8")
    route_types = (output_dir / "routes" / "api" / "media" / "gen_types.go").read_text(encoding="utf-8")
    http_config = (output_dir / "transports" / "http" / "gen_config.go").read_text(encoding="utf-8")
    http_runtime = (output_dir / "transports" / "http" / "gen_engine.go").read_text(encoding="utf-8")
    http_route = (output_dir / "transports" / "http" / "api" / "media" / "gen_interface.go").read_text(encoding="utf-8")

    assert "type MultipartFile struct" in req_provider
    assert "BindMultipart bool" in req_provider
    assert "type RawResponse struct" in rsp_provider
    assert 'providers "example.com/generated/golang/providers"' in shared_types
    assert "Image providers.MultipartFile" in shared_types
    assert "type RSP_Preview = providers.RawResponse" in route_types
    assert "type ServerConfig struct" in http_config
    assert "MaxRequestBodyBytes:" in http_config and "16 * mib" in http_config
    assert "MultipartMemoryBytes:" in http_config and "8 * mib" in http_config
    assert "MultipartSingleFileBytes:" in http_config and "32 * mib" in http_config
    assert "DecompressedBinaryBytes:" in http_config and "16 * mib" in http_config
    assert "type BinaryContentDecoder func(io.Reader) (io.ReadCloser, error)" in http_config
    assert "BinaryContentDecoders" in http_config and "map[string]BinaryContentDecoder" in http_config
    assert "WebSocketInsecureSkipVerify" in http_config
    assert "bindMultipart" in http_runtime
    assert "http.MaxBytesReader(ginCtx.Writer, ginCtx.Request.Body, limit)" in http_runtime
    assert "ginCtx.Request.ParseMultipartForm(config.MultipartMemoryBytes)" in http_runtime
    assert "header.Size > maxBytes" in http_runtime
    assert "limitReader(gzipReader, config.DecompressedBinaryBytes" in http_runtime
    assert "binaryContentDecoder(config, encoding)" in http_runtime
    assert "writeRawResponse" in http_runtime
    assert '"req=M|handle|rsp=bytes@CodeMessageDataEnvelope"' in http_route
    assert "HTTP: sharedprovider.HTTPRouteInfo{" in http_route
    assert 'DefaultFilename: "report.xls"' in http_route
    assert "writeRawResponse(ginCtx, rspProvider.Type, rspProvider.Route.HTTP.Response.DefaultFilename, response)" in http_runtime

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

    stale_engine = output_dir / "engine.go"
    stale_http = output_dir / "api" / "demo" / "_http"
    stale_http.mkdir(parents=True)
    stale_engine.parent.mkdir(parents=True, exist_ok=True)
    stale_engine.write_text("package views\n", encoding="utf-8")
    (stale_http / "gen_interface.go").write_text("package httptransport\n", encoding="utf-8")

    writer = GolangWriter(output_dir, enabled_transports=())
    writer.register(bp)
    writer.gen()

    assert not (output_dir / "_http").exists()
    assert not (output_dir / "api" / "_http").exists()
    assert not (output_dir / "api" / "demo" / "_http").exists()
    assert not (output_dir / "engine.go").exists()

    generated_core = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            output_dir / "routes" / "api" / "gen_blueprint.go",
            output_dir / "routes" / "api" / "demo" / "gen_interface.go",
            output_dir / "providers" / "gen_context.go",
            output_dir / "providers" / "gen_req.go",
            output_dir / "providers" / "gen_rsp.go",
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

    assert (output_dir / "routes" / "api" / "demo" / "gen_interface.go").is_file()
    assert not (output_dir / "transports" / "http").exists()


def test_golang_server_struct_tags_keep_alias_with_omitempty(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text("module example.com/generated\n\ngo 1.23.8\n", encoding="utf-8")

    class DemoBody(Model):
        self_ = Int(alias="self", optional=True)

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/alias").REQ(DemoBody).RSP()

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    shared_types = (output_dir / "routes" / "api" / "_gen_types" / "types.go").read_text(encoding="utf-8")
    assert 'Self int `json:"self,omitempty" xml:"self,omitempty" form:"self,omitempty" binding:"omitempty"`' in shared_types

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

    root_adapter = output_dir / "transports" / "http" / "api" / "gen_blueprint.go"
    route_adapter = output_dir / "transports" / "http" / "api" / "demo" / "gen_interface.go"
    core_route = output_dir / "routes" / "api" / "demo" / "gen_interface.go"

    assert root_adapter.is_file()
    assert route_adapter.is_file()
    root_adapter_text = root_adapter.read_text(encoding="utf-8")
    route_adapter_text = route_adapter.read_text(encoding="utf-8")
    assert "package api" in root_adapter_text
    assert "func NewBlueprint(router gin.IRouter) *Blueprint" in root_adapter_text
    assert "NewRouter(router)" in root_adapter_text
    assert "sharedroot" not in root_adapter_text
    assert "Router *sharedroot.Router" not in root_adapter_text
    assert "package demo" in route_adapter_text
    assert 'github.com/gin-gonic/gin' in route_adapter_text
    assert '"reflect"' in route_adapter_text
    assert "func Mount(router gin.IRouter, impl shared.RouterInterface) shared.RouterInterface" in route_adapter_text
    assert "return MountSelected(router, impl, nil)" in route_adapter_text
    assert "func MountSelected(router gin.IRouter, impl shared.RouterInterface, routeIDs map[string]struct{}) shared.RouterInterface" in route_adapter_text
    assert "func NewRouter(router gin.IRouter) *shared.Router" in route_adapter_text
    assert "func NewImpl(router gin.IRouter) *shared.Router" in route_adapter_text
    assert "return NewRouter(router)" in route_adapter_text
    assert "Mount(router, impl)" in route_adapter_text
    assert "func isNilRouterInterface(impl shared.RouterInterface) bool" in route_adapter_text
    assert "func shouldMountRoute(routeIDs map[string]struct{}, routeID string) bool" in route_adapter_text
    assert 'if shouldMountRoute(routeIDs, "api.demo.get.ping") {' in route_adapter_text
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
    assert "HTTP: sharedprovider.HTTPRouteInfo{" in route_adapter_text
    assert any(
        spec in route_adapter_text
        for spec in (
            '"",',
            '"req|handle|rsp=json@CodeMessageDataEnvelope",',
        )
    )
    assert "eng,\n\n\t\tfalse," not in route_adapter_text
    assert "rawResponse bool" not in (output_dir / "transports" / "http" / "gen_engine.go").read_text(encoding="utf-8")
    assert "binaryContentEncodings" not in (output_dir / "transports" / "http" / "gen_engine.go").read_text(encoding="utf-8")
    assert "NewRouteExecutorWithPlan" not in route_adapter_text
    assert 'github.com/gin-gonic/gin' not in core_route.read_text(encoding="utf-8")
    assert "func NewImpl(eng *gin.Engine)" not in core_route.read_text(encoding="utf-8")

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

    route_adapter = (output_dir / "transports" / "http" / "api" / "demo" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    http_runtime = (output_dir / "transports" / "http" / "gen_engine.go").read_text(encoding="utf-8")
    assert "sharedprovider.NewRouteExecutor(" in route_adapter
    assert 'RouteID:   "api.demo.post.callback"' in route_adapter
    assert any(
        spec in route_adapter
        for spec in (
            '"",',
            '"req|handle|rsp=json@CodeMessageDataEnvelope",',
        )
    )
    assert "ManualResponse:  true" in route_adapter
    assert "router,\n" in route_adapter
    assert "eng,\n\t\ttrue," not in route_adapter
    assert "if ginCtx.Writer.Written() {" in http_runtime
    assert "route.HTTP.Response.ManualResponse" in http_runtime
    assert "ginCtx.JSON(http.StatusOK, response)" in http_runtime

def test_golang_http_adapter_accepts_irouter_and_external_adapter(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8

require (
	github.com/coder/websocket v1.8.14
	github.com/gin-gonic/gin v1.12.0
)
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

    (tmp_path / "http_adapter_compile_test.go").write_text(
        r'''
package generated_test

import (
	"testing"

	"github.com/gin-gonic/gin"

	shared "example.com/generated/golang/routes/api/demo"
	apihttp "example.com/generated/golang/transports/http/api"
	demohttp "example.com/generated/golang/transports/http/api/demo"
)

type externalDemoAdapter struct {
	*shared.Router
}

func newEngine() *gin.Engine {
	gin.SetMode(gin.TestMode)
	return gin.New()
}

func TestHTTPAdapterAcceptsEngineGroupAndExternalInterface(t *testing.T) {
	if router := demohttp.NewRouter(newEngine()); router == nil {
		t.Fatal("NewRouter returned nil")
	}
	if impl := demohttp.NewImpl(newEngine()); impl == nil {
		t.Fatal("NewImpl returned nil")
	}
	if mounted := demohttp.Mount(newEngine(), nil); mounted == nil {
		t.Fatal("Mount nil fallback returned nil")
	}
	if bp := apihttp.NewBlueprint(newEngine()); bp == nil || bp.DemoRouter == nil {
		t.Fatalf("NewBlueprint(engine) returned invalid blueprint: %#v", bp)
	}

	groupEngine := newEngine()
	group := groupEngine.Group("/v1")
	adapter := &externalDemoAdapter{Router: shared.NewRouter()}
	if returned := demohttp.Mount(group, adapter); returned != adapter {
		t.Fatalf("Mount(group, adapter) returned %T, want external adapter", returned)
	}

	blueprintEngine := newEngine()
	if bp := apihttp.NewBlueprint(blueprintEngine.Group("/v1")); bp == nil || bp.DemoRouter == nil {
		t.Fatalf("NewBlueprint(group) returned invalid blueprint: %#v", bp)
	}
}

func TestHTTPAdapterFallsBackForTypedNilAdapter(t *testing.T) {
	var adapter *externalDemoAdapter
	mounted := demohttp.Mount(newEngine(), adapter)
	if _, ok := mounted.(*shared.Router); !ok {
		t.Fatalf("Mount typed nil fallback returned %T, want *shared.Router", mounted)
	}
}
'''.lstrip(),
        encoding="utf-8",
    )

    tidy_result = subprocess.run(
        ["go", "mod", "tidy"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert tidy_result.returncode == 0, tidy_result.stdout + tidy_result.stderr

    result = subprocess.run(
        ["go", "test", "./..."],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
