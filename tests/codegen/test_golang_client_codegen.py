from __future__ import annotations

import shutil
import subprocess

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint, Error, CodeMessageDataEnvelope, Model, Toast
from api_blueprint.engine.binary_schema import parse_binary_schema
from api_blueprint.engine.model import String
from api_blueprint.writer.golang.client import GolangClientWriter


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
    assert "ResponseEnvelope ApiResponseEnvelope" in runtime_text
    assert "RouteID          string" in runtime_text
    assert 'BaseURL string' in config_text
    assert '"http://localhost:2333"' in config_text
    assert "context.Context" in route_text
    assert "func (client *GenDemoClient) Ping(ctx context.Context" in route_text
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

	transport := httptransport.NewHttpTransport(httptransport.HttpConfig{BaseURL: server.URL})
	client := demo.NewClient(transport)
	rsp, err := client.Submit(context.Background(), demo.SubmitJSON{Value: "good"})
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


def test_golang_client_generates_named_message_keyframe_helpers(tmp_path):
    class OpenPayload(Model):
        run_id = String(alias="run_id", description="run id")

    class AssistantInput(Model):
        text = String(description="text")

    class AssistantCancel(Model):
        reason = String(description="reason")

    class AssistantDelta(Model):
        chunk = String(description="chunk")

    class AssistantDone(Model):
        status = String(description="status")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        )
        views.STREAM("/single-events").OPEN(OpenPayload).SERVER_MESSAGE(
            "AssistantSingleMessage",
            delta=AssistantDelta,
        )
        views.CHANNEL("/assistant").OPEN(OpenPayload).CLIENT_MESSAGE(
            "AssistantClientMessage",
            input=AssistantInput,
            cancel=AssistantCancel,
        ).SERVER_MESSAGE(
            "AssistantServerMessage",
            delta=AssistantDelta,
            done=AssistantDone,
        )

    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
    writer.register(bp)
    writer.gen()

    route_dir = output_dir / "routes" / "api" / "demo"
    types_text = (route_dir / "gen_types.go").read_text(encoding="utf-8")
    messages_text = (route_dir / "gen_messages.go").read_text(encoding="utf-8")
    cases_text = (route_dir / "gen_message_cases.go").read_text(encoding="utf-8")

    assert "type AssistantClientMessage struct" not in types_text
    assert "type AssistantClientMessage struct" in messages_text
    assert "type AssistantSingleMessage struct" in messages_text
    assert "const AssistantClientMessageTypeCancel = \"cancel\"" in messages_text
    assert "const AssistantSingleMessageTypeDelta = \"delta\"" in messages_text
    assert "func NewAssistantClientMessageCancel(data *AssistantClientMessage_Cancel_DATA)" in messages_text
    assert "func (msg *AssistantClientMessage) DecodeCancel()" in messages_text
    assert "func VisitAssistantSingleMessage[C any](" in cases_text
    assert "type AssistantClientMessageProcessor[C any] interface" in cases_text
    assert "OnInput(ctx C, msg *AssistantClientMessageInputCase) error" in cases_text
    assert "func VisitAssistantClientMessage[C any](" in cases_text
    assert "func AsAssistantClientMessageError(err error)" in cases_text
    assert "AssistantClientMessageErrorHandlerFailed" in cases_text
    assert "func (msg *AssistantClientMessageCancelCase) Decode()" in cases_text


def test_golang_client_generates_binary_body_interface_and_schema_writer(tmp_path):
    class SubmitResponse(Model):
        status = String(description="status")

    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | Kind | 1 | const=1 | kind |
| flags | Flags | 1 | min=0 | flags |
| pad0 | padding | 1 | | pad |
| code | u24 | 1 | min=1,max=16777215 | code |
| delta | i24 | 1 | min=-8,max=8 | delta |
| payload_len | u16 | 1 | max=16,sizeof=payload | payload length |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| payload | bytes | payload_len | | payload |

## enum Kind : u16

| name | value | comment |
|---|---:|---|
| Metric | 1 | metric |
| Debug | 2 | debug |

## bitflags Flags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasPayload | 0 | | payload |
| Mode | 1..2 | enum=Kind | mode |
| Reserved | 3..31 | const=0 | reserved |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api", response_envelope=CodeMessageDataEnvelope)
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(SubmitResponse)

    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
    writer.register(bp)
    writer.gen()

    route_text = (output_dir / "routes" / "api" / "binary" / "gen_client.go").read_text(encoding="utf-8")
    schema_text = (output_dir / "routes" / "api" / "binary" / "gen_binary.go").read_text(encoding="utf-8")
    runtime_text = (output_dir / "runtime" / "binary" / "gen_runtime.go").read_text(encoding="utf-8")
    transport_text = (output_dir / "transports" / "http" / "gen_transport.go").read_text(encoding="utf-8")

    assert "binaryBody runtimebinary.Body" in route_text
    assert "Binary:           binaryBody" in route_text
    assert "package binary" in schema_text
    assert not (output_dir / "routes" / "api" / "binary" / "wire").exists()
    assert "type DemoPacketKind uint16" in schema_text
    assert "type DemoPacketFlags uint32" in schema_text
    assert "func (f DemoPacketFlags) HasPayload() bool" in schema_text
    assert "func (f DemoPacketFlags) WithHasPayload(enabled bool) DemoPacketFlags" in schema_text
    assert "func (f DemoPacketFlags) Mode() DemoPacketKind" in schema_text
    assert "func (f DemoPacketFlags) WithMode(value DemoPacketKind) DemoPacketFlags" in schema_text
    assert "DemoPacketFlagsReservedMask DemoPacketFlags = 4294967288" in schema_text
    assert "func (f DemoPacketFlags) HasReservedBits() bool" in schema_text
    assert "func (f DemoPacketFlags) Validate() error" in schema_text
    assert "ClearReservedBits" not in schema_text
    assert "DemoPacketFlagsReserved   DemoPacketFlags" not in schema_text
    assert "reserved bits must be zero" in schema_text
    assert "writer.WriteUint24" in schema_text
    assert "writer.WriteInt24" in schema_text
    assert "runtimebinary.RequireSignedRange" in schema_text
    assert "func NewDemoPacketBody(contentLength int64" in schema_text
    assert "type Body interface" in runtime_text
    assert "func RequireSignedRange(" in runtime_text
    assert "body.WriteBinary" in transport_text
    assert "json.Marshal(request.Binary)" not in transport_text


def test_golang_client_binary_writer_uses_payload_context_paths_for_nested_structs(tmp_path):
    class SubmitResponse(Model):
        status = String(description="status")

    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u16 | 1 | max=1,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api", response_envelope=CodeMessageDataEnvelope)
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(SubmitResponse)

    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
    writer.register(bp)
    writer.gen()

    schema_text = (output_dir / "routes" / "api" / "binary" / "gen_binary.go").read_text(encoding="utf-8")
    runtime_text = (output_dir / "runtime" / "binary" / "gen_runtime.go").read_text(encoding="utf-8")

    assert 'if err := writeDemoPacketHeader(&value.Header, writer, state); err != nil {\n\t\treturn runtimebinary.WrapField("DemoPacket.header", err)\n\t}' in schema_text
    assert 'if err := writeDemoPacketBody(&value.Body, writer, state); err != nil {\n\t\treturn runtimebinary.WrapField("DemoPacket.body", err)\n\t}' in schema_text
    assert "func writeDemoPacketItem(value *DemoPacketItem, writer *runtimebinary.Writer, state *demoPacketBinaryState) error" in schema_text
    assert 'return runtimebinary.WrapField("Item", err)' in schema_text
    assert 'writeDemoPacketItem(&value.Items[index], writer, state); err != nil {\n\t\t\treturn runtimebinary.WrapIndex("items", index, err)\n\t\t}' in schema_text
    assert 'runtimebinary.RequireRange("item_count", uint64(value.ItemCount), 0, 1)' in schema_text
    assert 'runtimebinary.RequireRange("id", uint64(value.ID), 1, ^uint64(0))' in schema_text
    assert "value.Item_count" not in schema_text
    assert "value.Id" not in schema_text
    assert "runtimebinary.JoinPath(path," not in schema_text
    assert "runtimebinary.IndexPath(" not in schema_text
    assert "func WrapField(path string, err error) error" in runtime_text
    assert "func IndexPath(path string, index int) string" in runtime_text


def test_golang_client_binary_writer_reports_nested_schema_paths_without_success_path_allocations(tmp_path):
    class SubmitResponse(Model):
        status = String(description="status")

    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u16 | 1 | max=1,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api", response_envelope=CodeMessageDataEnvelope)
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(SubmitResponse)

    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
    writer.register(bp)
    writer.gen()

    if shutil.which("go") is None:
        return

    (output_dir / "go.mod").write_text(
        "module example.com/generated/client\n\ngo 1.23.8\n",
        encoding="utf-8",
    )
    (output_dir / "routes" / "api" / "binary" / "binary_path_test.go").write_text(
        """
package binary

import (
	"bytes"
	"strings"
	"testing"
)

func TestDemoPacketWriteBinaryReportsNestedPath(t *testing.T) {
	packet := DemoPacket{
		Header: DemoPacketHeader{ItemCount: 1},
		Body: DemoPacketBody{
			Items: []DemoPacketItem{{ID: 0}},
		},
	}
	err := packet.WriteBinary(&bytes.Buffer{})
	if err == nil {
		t.Fatal("expected write error")
	}
	if !strings.Contains(err.Error(), "DemoPacket.body.items[0].id:") {
		t.Fatalf("unexpected error path: %v", err)
	}
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["go", "test", "./routes/api/binary"],
        cwd=output_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_golang_client_binary_writer_uses_compact_go_spacing(tmp_path):
    class SubmitResponse(Model):
        status = String(description="status")

    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| item_count | u16 | 1 | max=1,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | Item | item_count | | items |
| checksum | u32 | 1 | min=1 | checksum |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1,max=999 | item id |
| enabled | bool | 1 | | enabled |
""".strip(),
        source_path="demo_packet.md",
    )
    bp = Blueprint(root="/api", response_envelope=CodeMessageDataEnvelope)
    with bp.group("/binary") as views:
        views.POST("/packet").REQ_BINARY(schema).RSP(SubmitResponse)

    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
    writer.register(bp)
    writer.gen()

    schema_text = (output_dir / "routes" / "api" / "binary" / "gen_binary.go").read_text(encoding="utf-8")

    assert "func writeDemoPacketHeader(value *DemoPacketHeader, writer *runtimebinary.Writer, state *demoPacketBinaryState, path string) error {\n\n\t" not in schema_text
    assert "func writeDemoPacketBody(value *DemoPacketBody, writer *runtimebinary.Writer, state *demoPacketBinaryState, path string) error {\n\n\t" not in schema_text
    assert "func writeDemoPacketItem(value *DemoPacketItem, writer *runtimebinary.Writer, state *demoPacketBinaryState, path string) error {\n\n\t" not in schema_text
    assert "for index := range value.Items {\n\n\t\t" not in schema_text
    assert "\n\n\tif err :=" not in schema_text
