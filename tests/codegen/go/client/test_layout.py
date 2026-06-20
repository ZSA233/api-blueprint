from __future__ import annotations

import re

from .helpers import *
from api_blueprint.engine.model import Array, Int, OneOf, LegacyStringID


def test_golang_client_writer_uses_go_safe_route_package_segments(tmp_path):
    bp = Blueprint(root="/api-v1")
    with bp.group("/admin/v1") as views:
        views.GET("/ping").RSP()

    graph = build_contract_graph([bp])
    output_dir = tmp_path / "client"

    writer = GolangClientWriter(output_dir, module="example.com/generated/client", contract_graph=graph)
    writer.register(bp)
    writer.gen()

    route_dir = output_dir / "routes" / "api_v1" / "admin_v1"
    assert (route_dir / "gen_client.go").is_file()
    assert "package admin_v1" in (route_dir / "gen_client.go").read_text(encoding="utf-8")
    assert "func (client *GenAdminV1Client) Ping(ctx context.Context" in (route_dir / "gen_client.go").read_text(
        encoding="utf-8"
    )

def test_golang_client_root_facade_disambiguates_same_group_names_across_roots(tmp_path):
    api_bp = Blueprint(root="/api")
    alt_bp = Blueprint(root="/alt")
    with api_bp.group("/conflict") as views:
        views.GET("/default", operation_id="default").RSP()
    with alt_bp.group("/conflict") as views:
        views.GET("/default", operation_id="default").RSP()

    graph = build_contract_graph([api_bp, alt_bp])
    output_dir = tmp_path / "client"

    writer = GolangClientWriter(output_dir, module="example.com/generated/client", contract_graph=graph)
    writer.register(api_bp)
    writer.register(alt_bp)
    writer.gen()

    root_client = (output_dir / "gen_client.go").read_text(encoding="utf-8")
    assert 'api_conflict "example.com/generated/client/routes/api/conflict"' in root_client
    assert 'alt_conflict "example.com/generated/client/routes/alt/conflict"' in root_client
    assert "APIConflict *api_conflict.Client" in root_client
    assert "AltConflict *alt_conflict.Client" in root_client
    assert "APIConflict: api_conflict.NewClient(transport)" in root_client
    assert "AltConflict: alt_conflict.NewClient(transport)" in root_client


def test_golang_client_generates_legacy_json_compat_field_types(tmp_path):
    class LegacyPayload(Model):
        target = OneOf(String(), Array[String](), description="target")
        ids = Array[OneOf(String(), Int())](description="ids")
        normalized = Array[LegacyStringID](description="normalized")
        room_id = LegacyStringID(alias="roomId", description="room id")

    bp = Blueprint(root="/api")
    with bp.group("/legacy") as views:
        views.GET("/payload").RSP(LegacyPayload)

    graph = build_contract_graph([bp])
    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client", contract_graph=graph)
    writer.register(bp)
    writer.gen()

    runtime_types = (output_dir / "runtime" / "gen_types.go").read_text(encoding="utf-8")
    assert re.search(r"\bTarget\s+any\b", runtime_types)
    assert "IDs" in runtime_types and "[]any" in runtime_types
    assert "Normalized []string" in runtime_types
    assert re.search(r"\bRoomID\s+string\b", runtime_types)

@pytest.mark.toolchain_smoke
def test_golang_client_writer_generates_layout_preserves_user_files_and_compiles(tmp_path):
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

    bp = Blueprint(root="/api", errors=[CommonErr], response_envelope=CodeMessageDataEnvelope)
    views = bp.group("/demo")
    views.GET("/ping").ARGS(q=String(description="q")).RSP(SubmitResponse)
    views.POST("/submit").REQ(SubmitJson).RSP(SubmitResponse)
    views.POST("/form").REQ_FORM(FormPayload).RSP(SubmitResponse)
    views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(ServerMessage)
    views.CHANNEL("/chat").OPEN(OpenPayload).CLIENT_MESSAGE(ClientMessage).SERVER_MESSAGE(ServerMessage)

    graph = build_contract_graph([bp])
    output_dir = tmp_path / "client"
    route_dir = output_dir / "routes" / "api" / "demo"
    http_dir = output_dir / "transports" / "http"
    route_dir.mkdir(parents=True)
    http_dir.mkdir(parents=True)
    route_client = route_dir / "client.go"
    http_client = http_dir / "client.go"
    route_client.write_text("package demo\n\n// USER ROUTE CLIENT\n", encoding="utf-8")
    http_client.write_text("package http\n\n// USER HTTP CLIENT\n", encoding="utf-8")

    writer = GolangClientWriter(output_dir, module="example.com/generated/client", base_url="http://localhost:2333", contract_graph=graph)
    writer.register(bp)
    writer.gen()
    writer.gen()

    assert (output_dir / "runtime" / "gen_client.go").is_file()
    assert (output_dir / "runtime" / "gen_errors.go").is_file()
    assert (output_dir / "runtime" / "gen_error_lookup.go").is_file()
    assert (route_dir / "gen_client.go").is_file()
    assert (route_dir / "gen_types.go").is_file()
    assert (http_dir / "gen_config.go").is_file()
    assert (http_dir / "gen_transport.go").is_file()
    assert route_client.read_text(encoding="utf-8") == "package demo\n\n// USER ROUTE CLIENT\n"
    assert http_client.read_text(encoding="utf-8") == "package http\n\n// USER HTTP CLIENT\n"

    runtime_text = (output_dir / "runtime" / "gen_client.go").read_text(encoding="utf-8")
    errors_text = (output_dir / "runtime" / "gen_errors.go").read_text(encoding="utf-8")
    catalog_text = (output_dir / "runtime" / "gen_error_lookup.go").read_text(encoding="utf-8")
    route_text = (route_dir / "gen_client.go").read_text(encoding="utf-8")
    models_text = (route_dir / "gen_types.go").read_text(encoding="utf-8")
    config_text = (http_dir / "gen_config.go").read_text(encoding="utf-8")
    transport_text = (http_dir / "gen_transport.go").read_text(encoding="utf-8")

    assert "BaseURL" not in runtime_text
    assert "base_url" not in runtime_text
    assert "baseUrl" not in runtime_text
    assert "Headers          map[string]string" in runtime_text
    assert "type RequestOption func(*Request)" in runtime_text
    assert "func WithHeader(name string, value string) RequestOption" in runtime_text
    assert "func WithHeaders(headers map[string]string) RequestOption" in runtime_text
    assert "ResponseEnvelope ApiResponseEnvelope" in runtime_text
    assert "RouteID          string" in runtime_text
    assert 'BaseURL        string' in config_text
    assert "DefaultHeaders map[string]string" in config_text
    assert '"http://localhost:2333"' in config_text
    assert "context.Context" in route_text
    assert "func (client *GenDemoClient) Ping(ctx context.Context, query PingQuery, opts ...runtime.RequestOption)" in route_text
    assert "request.ApplyOptions(opts...)" in route_text
    assert "type Client = GenDemoClient" in route_text
    assert "var NewClient = NewGenDemoClient" in route_text
    assert 'ResponseEnvelope: runtime.ApiResponseEnvelope{Name: "CodeMessageDataEnvelope"' in route_text
    assert "func (client *GenDemoClient) SubscribeEvents(ctx context.Context" in route_text
    assert "func (client *GenDemoClient) OpenChat(ctx context.Context" in route_text
    assert "UnsupportedTransportError" in runtime_text
    assert "type ApiError struct" in errors_text
    assert "type ApiErrorPayload struct" in errors_text
    assert "type ApiToastSpec struct" in errors_text
    assert "func ResolveApiToast(" in errors_text
    assert "ErrorCatalogByID" not in errors_text
    assert '"CommonErr.UNKNOWN"' not in errors_text
    assert '"CommonErr.UNKNOWN"' in catalog_text
    assert "ApiErrorsByID" in catalog_text
    assert "routeApiErrorsByCode" in catalog_text
    assert "CommonErrTokenExpire ApiErrorCode = 55555" in catalog_text
    assert '"CommonErr.TOKEN_EXPIRE": {\n' in catalog_text
    assert 'ID:      "CommonErr.TOKEN_EXPIRE",' in catalog_text
    assert 'Toast: ApiToastSpec{\n' in catalog_text
    assert '"登录状态已失效，请重新登录"' in catalog_text
    assert "\\u767b" not in catalog_text
    assert "locales" not in catalog_text
    assert "UnsupportedTransportError" in transport_text
    assert "decodeResponse(httpResponse.Body, request.ResponseEnvelope, request.RouteID, response)" in transport_text
    assert 'envelope.Kind == "" || envelope.Kind == "none"' in transport_text
    assert 'envelope.Kind != "code_message_data" && envelope.Kind != "ok_data_error"' in transport_text
    assert "runtime.NewApiError" in transport_text
    assert "ConnectUnsupported" not in transport_text
    assert "StreamUnsupported" in transport_text
    assert "ChannelUnsupported" in transport_text
    assert "type PingQuery struct" in models_text
    assert "type SubmitJSON = runtime.SubmitJson" in models_text
    assert "type SubmitResponse = runtime.SubmitResponse" in models_text
    assert "type ChatOpen = runtime.OpenPayload" in models_text

    if shutil.which("go") is None:
        return

    (output_dir / "runtime" / "toast_test.go").write_text(
        """
package runtime

import "testing"

func TestResolveApiToastPriority(t *testing.T) {
	payload := ApiToastPayload{
		Key:     "auth.token_expire",
		Default: "登录状态已失效，请重新登录",
	}
	translate := func(key string) (string, bool) {
		if key == "auth.token_expire" {
			return "Sign in again", true
		}
		return "", false
	}
	if got := ResolveApiToast(payload, translate, "fallback"); got != "Sign in again" {
		t.Fatalf("expected translation, got %q", got)
	}
	payload.Text = "企业账号登录已失效，请重新绑定后继续使用"
	if got := ResolveApiToast(payload, translate, "fallback"); got != payload.Text {
		t.Fatalf("expected server override text, got %q", got)
	}
	payload = ApiToastPayload{Default: "默认提示"}
	if got := ResolveApiToast(payload, nil, "fallback"); got != "默认提示" {
		t.Fatalf("expected default, got %q", got)
	}
	if got := ResolveApiToast(ApiToastPayload{}, nil, "fallback"); got != "fallback" {
		t.Fatalf("expected message fallback, got %q", got)
	}
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "client_roundtrip_test.go").write_text(
        """
package client_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	demo "example.com/generated/client/routes/api/demo"
	runtime "example.com/generated/client/runtime"
	httptransport "example.com/generated/client/transports/http"
)

func TestCodeMessageDataEnvelopeRoundTrip(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body demo.SubmitJSON
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode request: %v", err)
		}
		if body.Value == "good" {
			if got := r.Header.Get("X-Default"); got != "base" {
				t.Fatalf("expected default header, got %q", got)
			}
			if got := r.Header.Get("X-Trace-Id"); got != "call" {
				t.Fatalf("expected per-call header override, got %q", got)
			}
			if got := r.Header.Get("X-Batch"); got != "batch" {
				t.Fatalf("expected WithHeaders value, got %q", got)
			}
			if got := r.Header.Get("Content-Type"); !strings.HasPrefix(got, "application/json") {
				t.Fatalf("expected generated content type to win, got %q", got)
			}
		}
		if body.Value == "bad" {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"code":    55555,
				"message": "expired",
				"error": map[string]any{
					"id":      "CommonErr.TOKEN_EXPIRE",
					"group":   "CommonErr",
					"key":     "TOKEN_EXPIRE",
				},
			})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"code":    0,
			"message": "ok",
			"data":    map[string]any{"status": "ok"},
		})
	}))
	defer server.Close()

	transport := httptransport.NewHttpTransport(httptransport.HttpConfig{
		BaseURL: server.URL,
		DefaultHeaders: map[string]string{
			"X-Default":    "base",
			"X-Trace-Id":   "default",
			"Content-Type": "text/plain",
		},
	})
	client := demo.NewClient(transport)
	rsp, err := client.Submit(
		context.Background(),
		demo.SubmitJSON{Value: "good"},
		runtime.WithHeader("X-Trace-Id", "call"),
		runtime.WithHeaders(map[string]string{"X-Batch": "batch"}),
	)
	if err != nil {
		t.Fatalf("submit returned error: %v", err)
	}
	if rsp == nil || rsp.Status != "ok" {
		t.Fatalf("unexpected response: %#v", rsp)
	}

	_, err = client.Submit(context.Background(), demo.SubmitJSON{Value: "bad"})
	var apiErr *runtime.ApiError
	if !errors.As(err, &apiErr) {
		t.Fatalf("expected ApiError, got %T %v", err, err)
	}
	if apiErr.Code() != 55555 || apiErr.Message() != "expired" || apiErr.ID() != "CommonErr.TOKEN_EXPIRE" {
		t.Fatalf("unexpected api error: id=%s code=%d message=%q", apiErr.ID(), apiErr.Code(), apiErr.Message())
	}
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "go.mod").write_text(
        "module example.com/generated/client\n\ngo 1.23.8\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["go", "test", "./..."],
        cwd=output_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
