from __future__ import annotations

import shutil
import subprocess

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint, Error, Model, Toast
from api_blueprint.engine.model import String
from api_blueprint.writer.golang.client import GolangClientWriter


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

    class BinaryPayload(Model):
        checksum = String(description="checksum")

    class OpenPayload(Model):
        run_id = String(alias="run_id", description="run id")

    class ServerMessage(Model):
        status = String(description="status")

    class ClientMessage(Model):
        text = String(description="text")

    bp = Blueprint(root="/api", errors=[CommonErr])
    views = bp.group("/demo")
    views.GET("/ping").ARGS(q=String(description="q")).RSP(SubmitResponse)
    views.POST("/submit").REQ(SubmitJson).RSP(SubmitResponse)
    views.POST("/form").REQ_FORM(FormPayload).RSP(SubmitResponse)
    views.POST("/binary").REQ_BIN(BinaryPayload).RSP(SubmitResponse)
    views.WS("/ws").ARGS(token=String(description="token")).SEND(ClientMessage).RECV(ServerMessage)
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
    assert (output_dir / "runtime" / "gen_error_catalog.go").is_file()
    assert (route_dir / "gen_client.go").is_file()
    assert (route_dir / "gen_models.go").is_file()
    assert (http_dir / "gen_config.go").is_file()
    assert (http_dir / "gen_transport.go").is_file()
    assert route_client.read_text(encoding="utf-8") == "package demo\n\n// USER ROUTE CLIENT\n"
    assert http_client.read_text(encoding="utf-8") == "package http\n\n// USER HTTP CLIENT\n"

    runtime_text = (output_dir / "runtime" / "gen_client.go").read_text(encoding="utf-8")
    errors_text = (output_dir / "runtime" / "gen_errors.go").read_text(encoding="utf-8")
    catalog_text = (output_dir / "runtime" / "gen_error_catalog.go").read_text(encoding="utf-8")
    route_text = (route_dir / "gen_client.go").read_text(encoding="utf-8")
    models_text = (route_dir / "gen_models.go").read_text(encoding="utf-8")
    config_text = (http_dir / "gen_config.go").read_text(encoding="utf-8")
    transport_text = (http_dir / "gen_transport.go").read_text(encoding="utf-8")

    assert "BaseURL" not in runtime_text
    assert "base_url" not in runtime_text
    assert "baseUrl" not in runtime_text
    assert 'BaseURL string' in config_text
    assert '"http://localhost:2333"' in config_text
    assert "context.Context" in route_text
    assert "func (client *GenDemoClient) Ping(ctx context.Context" in route_text
    assert "func (client *GenDemoClient) ConnectWs(ctx context.Context" in route_text
    assert "func (client *GenDemoClient) SubscribeEvents(ctx context.Context" in route_text
    assert "func (client *GenDemoClient) OpenChat(ctx context.Context" in route_text
    assert "UnsupportedTransportError" in runtime_text
    assert "type ApiCodeError struct" in errors_text
    assert "type ApiToastSpec struct" in errors_text
    assert "func ResolveApiToast(" in errors_text
    assert "ErrorCatalogByID" not in errors_text
    assert '"CommonErr.UNKNOWN"' not in errors_text
    assert '"CommonErr.UNKNOWN"' in catalog_text
    assert "CommonErrTokenExpire ApiErrorCode = 55555" in catalog_text
    assert '"CommonErr.TOKEN_EXPIRE": {\n' in catalog_text
    assert 'ID:      "CommonErr.TOKEN_EXPIRE",' in catalog_text
    assert 'Toast: ApiToastSpec{\n' in catalog_text
    assert '"登录状态已失效，请重新登录"' in catalog_text
    assert "\\u767b" not in catalog_text
    assert "locales" not in catalog_text
    assert "UnsupportedTransportError" in transport_text
    assert "ConnectUnsupported" in transport_text
    assert "StreamUnsupported" in transport_text
    assert "ChannelUnsupported" in transport_text
    assert "type REQ_Ping_QUERY struct" in models_text
    assert "type REQ_Submit_JSON = runtime.SubmitJson" in models_text
    assert "type RSP_Submit_BODY = runtime.SubmitResponse" in models_text

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
