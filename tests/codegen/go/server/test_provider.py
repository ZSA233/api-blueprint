from __future__ import annotations

import re

from .helpers import *


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

    provider_file = output_dir / "providers" / "gen_provider.go"
    provider_impl = output_dir / "providers" / "impl_provider.go"
    provider_context = output_dir / "providers" / "gen_context.go"
    context_impl = output_dir / "providers" / "impl_context.go"
    req_impl = output_dir / "providers" / "impl_req.go"
    rsp_impl = output_dir / "providers" / "impl_rsp.go"
    handle_impl = output_dir / "providers" / "impl_handle.go"
    auth_impl = output_dir / "providers" / "impl_auth.go"
    provider_executor = output_dir / "providers" / "gen_executor.go"
    route_file = output_dir / "routes" / "api" / "demo" / "gen_types.go"
    expected_provider_import = f'providers "example.com/generated/{output_dir.name}/providers"'

    assert provider_file.is_file()
    assert provider_context.is_file()
    assert provider_executor.is_file()
    provider_text = provider_file.read_text(encoding="utf-8")
    provider_impl_text = provider_impl.read_text(encoding="utf-8")
    provider_context_text = provider_context.read_text(encoding="utf-8")
    provider_executor_text = provider_executor.read_text(encoding="utf-8")
    context_impl_text = context_impl.read_text(encoding="utf-8")
    req_impl_text = req_impl.read_text(encoding="utf-8")
    rsp_impl_text = rsp_impl.read_text(encoding="utf-8")
    handle_impl_text = handle_impl.read_text(encoding="utf-8")
    auth_impl_text = auth_impl.read_text(encoding="utf-8")
    assert 'package providers' in provider_text
    assert expected_provider_import in route_file.read_text(encoding="utf-8")
    assert "func (ctx *Context[Path, Query, Body, R]) Next()" in provider_context_text
    assert "ctx.Gin.Next()" not in provider_context_text
    assert "type RouteInfo struct" in provider_context_text
    assert "type HTTPRouteInfo struct" in provider_context_text
    assert "type HTTPRequestInfo struct" in provider_context_text
    assert "type HTTPResponseInfo struct" in provider_context_text
    assert re.search(r"HTTP\s+HTTPRouteInfo", provider_context_text)
    assert re.search(r"Route\s+\*RouteInfo", provider_context_text)
    assert "Request  *RequestContext[Path, Query, Body]" in provider_context_text
    assert "Response *ResponseContext" in provider_context_text
    assert "type ProviderSpec struct" in provider_text
    assert "Handler any" in provider_text
    assert "type Indexer[Path, Query, Body, Response any] struct" in provider_text
    assert "func RegisterProviderFactory(name string, factory ProviderFactory)" in provider_text
    assert "func SelectProvider[Path, Query, Body, Response any]" in provider_impl_text
    assert "func SelectWithSpec[Path, Query, Body, Response any]" not in provider_text
    assert "func SelectInternal[Path, Query, Body, Response any]" not in provider_text
    assert "func Select[Path, Query, Body, Response any]" not in provider_impl_text
    assert "func RegisterProvider(" not in provider_text
    assert "func GetProvider(" not in provider_text
    assert "func NewRouteExecutor[Path, Query, Body, Response any](" in provider_executor_text
    assert "NewRouteExecutorWithInfo" not in provider_executor_text
    assert "NewRouteExecutorWithPlan" not in provider_executor_text
    assert "NewRouteExecutorWithProviders" not in provider_executor_text
    assert "type RoutePlan" not in provider_executor_text
    assert "routePlan" not in provider_executor_text
    assert "ctx.Route = &executor.Route" in provider_executor_text
    assert "do not re-declare generated context types" in context_impl_text
    assert "do not re-declare\n// the generated request types" in req_impl_text
    assert "do not re-declare generated response" in rsp_impl_text
    assert "do not re-declare\n// HandleContext" in handle_impl_text
    assert "AuthContext is intentionally user-owned" in auth_impl_text
    assert "Keep generated provider interfaces and context frames in\n// gen_ files" in provider_impl_text
    req_provider_text = (output_dir / "providers" / "gen_req.go").read_text(encoding="utf-8")
    assert "ctx.Abort(ctx.Request.Error)" in req_provider_text
    assert "Bind  func() (*REQ[Path, Query, Body], error)" in req_provider_text
    assert "ctx.Request.Value, ctx.Request.Error = ctx.Request.Bind()" in req_provider_text

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

    class EchoBody(Model):
        message = String(description="message")

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

    route_adapter = (output_dir / "transports" / "http" / "static" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    assert re.search(r'Root:\s+"static"', route_adapter)
    assert re.search(r"RouteID:\s+RouteIDDoc", route_adapter)
    assert '"req|cache=ttl=60s|handle|rsp=json@CodeMessageDataEnvelope"' in route_adapter

@pytest.mark.toolchain_smoke
def test_golang_pre_req_provider_can_abort_before_lazy_request_bind(tmp_path):
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

    class EchoBody(Model):
        message = String(description="message")

    bp = Blueprint(
        root="/api",
        providers=[
            provider.Custom("precheck"),
            provider.Req(),
            provider.Handle(),
            provider.Rsp(),
        ],
    )
    with bp.group("/demo") as views:
        views.POST("/echo").REQ_JSON(EchoBody).RSP(message=String(description="message"))

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    http_runtime = (output_dir / "transports" / "http" / "gen_engine.go").read_text(
        encoding="utf-8"
    )
    assert "Bind: func() (*provider.REQ[Path, Query, Body], error)" in http_runtime
    assert "ctx.Request = &provider.RequestContext[Path, Query, Body]{" in http_runtime

    (output_dir / "providers" / "pre_req_provider_test.go").write_text(
        """
package providers

import (
	"context"
	"errors"
	"testing"
)

var errPrecheck = errors.New("precheck failed")

type precheckProvider struct{}

func (prov precheckProvider) GetName() string {
	return "precheck"
}

func (prov precheckProvider) Handle(anyCtx ContextInterface) {
	ctx := AdaptContext[any, any, any, any](anyCtx)
	ctx.Abort(errPrecheck)
}

func TestPreReqProviderCanAbortBeforeLazyRequestBind(t *testing.T) {
	RegisterProviderFactory("precheck", func(spec ProviderSpec) Provider {
		return precheckProvider{}
	})
	defer RegisterProviderFactory("precheck", nil)

	bindCalls := 0
	handleCalls := 0
	executor := NewRouteExecutor(
		RouteInfo{Root: "api", RouteID: "api.demo.post.echo", Transport: TransportHTTP},
		"precheck|req=json|handle|rsp=json@CodeMessageDataEnvelope",
		func(c *Context[any, any, any, any], req *REQ[any, any, any]) (*any, error) {
			handleCalls++
			return nil, nil
		},
	)
	ctx := NewHTTPContext[any, any, any, any](context.Background(), nil, nil)
	ctx.Request = &RequestContext[any, any, any]{
		Bind: func() (*REQ[any, any, any], error) {
			bindCalls++
			return &REQ[any, any, any]{}, nil
		},
	}
	err := executor.Run(ctx)
	if !errors.Is(err, errPrecheck) {
		t.Fatalf("expected precheck error, got %v", err)
	}
	if bindCalls != 0 {
		t.Fatalf("request binder should not run after precheck abort, got %d", bindCalls)
	}
	if handleCalls != 0 {
		t.Fatalf("handler should not run after precheck abort, got %d", handleCalls)
	}
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["go", "test", "./providers"],
        cwd=output_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

@pytest.mark.toolchain_smoke
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

    (output_dir / "providers" / "route_factory_test.go").write_text(
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
	ctx := AdaptContext[any, any, any, any](anyCtx)
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
		if _, ok := spec.Handler.(RouteHandler[any, any, any, any]); !ok {
			t.Fatalf("handler is not route typed: %T", spec.Handler)
		}
		return cacheProvider{calls: &providerCalls}
	})

	executor := NewRouteExecutor(
		RouteInfo{Root: "static", RouteID: "static.static.get.doc", Transport: TransportHTTP},
		"cache=ttl=60s",
		func(c *Context[any, any, any, any], req *REQ[any, any, any]) (*any, error) {
			return nil, nil
		},
	)
	if factoryCalls != 1 {
		t.Fatalf("factory should run once at executor creation, got %d", factoryCalls)
	}

	for i := 0; i < 3; i++ {
		ctx := NewHTTPContext[any, any, any, any](context.Background(), nil, nil)
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
        ["go", "test", "./providers"],
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

    assert (output_dir / "providers" / "gen_provider.go").is_file()
    assert (output_dir / "routes" / "providers" / "demo" / "gen_interface.go").is_file()
