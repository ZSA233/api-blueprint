from __future__ import annotations

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
    assert 'package providers' in provider_text
    assert expected_provider_import in route_file.read_text(encoding="utf-8")
    assert "func (ctx *Context[Q, B, P]) Next()" in provider_context_text
    assert "ctx.Gin.Next()" not in provider_context_text
    assert "type RouteInfo struct" in provider_context_text
    assert "type HTTPRouteInfo struct" in provider_context_text
    assert "type HTTPRequestInfo struct" in provider_context_text
    assert "type HTTPResponseInfo struct" in provider_context_text
    assert "HTTP      HTTPRouteInfo" in provider_context_text
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
    assert "ctx.Abort(ctx.Req.Error)" in (output_dir / "providers" / "gen_req.go").read_text(
        encoding="utf-8"
    )

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

    route_adapter = (output_dir / "transports" / "http" / "static" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    assert 'Root:      "static"' in route_adapter
    assert 'RouteID:   "static.static.get.doc"' in route_adapter
    assert '"req|cache=ttl=60s|handle|rsp=json@CodeMessageDataEnvelope"' in route_adapter

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
