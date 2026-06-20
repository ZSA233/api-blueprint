from __future__ import annotations

from .helpers import *


@pytest.mark.toolchain_smoke
def test_golang_client_generates_path_params_and_expands_url(tmp_path):
    class DeleteUserMedalPath(Model):
        user = String(description="user")
        medal = String(description="medal")

    class DeleteUserMedalQuery(Model):
        force = String(optional=True)

    class DeleteUserMedalJSON(Model):
        reason = String(description="reason")

    class DeleteUserMedalResponse(Model):
        ok = String(description="ok")

    bp = Blueprint(root="/api", response_envelope=CodeMessageDataEnvelope)
    with bp.group("/medal") as views:
        views.DELETE("/user/{user}/{medal}", operation_id="DeleteUserMedal").REQ_PATH(
            DeleteUserMedalPath
        ).ARGS(DeleteUserMedalQuery).REQ(DeleteUserMedalJSON).RSP(DeleteUserMedalResponse)

    graph = build_contract_graph([bp])
    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client", contract_graph=graph)
    writer.register(bp)
    writer.gen()

    route_client = (output_dir / "routes" / "api" / "medal" / "gen_client.go").read_text(encoding="utf-8")
    route_types = (output_dir / "routes" / "api" / "medal" / "gen_types.go").read_text(encoding="utf-8")
    runtime_client = (output_dir / "runtime" / "gen_client.go").read_text(encoding="utf-8")
    runtime_types = (output_dir / "runtime" / "gen_types.go").read_text(encoding="utf-8")
    transport = (output_dir / "transports" / "http" / "gen_transport.go").read_text(encoding="utf-8")

    assert (
        "func (client *GenMedalClient) DeleteUserMedal(ctx context.Context, "
        "path DeleteUserMedalPath, query DeleteUserMedalQuery, jsonBody DeleteUserMedalJSON, "
        "opts ...runtime.RequestOption)"
    ) in route_client
    assert "PathParams:       path" in route_client
    assert "type DeleteUserMedalPath = runtime.DeleteUserMedalPath" in route_types
    assert "PathParams       any" in runtime_client
    assert 'User  string `json:"user" form:"user" uri:"user"`' in runtime_types
    assert "func expandPath(path string, params any) (string, error)" in transport
    assert "url.PathEscape(value)" in transport

    if shutil.which("go") is None:
        return

    (output_dir / "go.mod").write_text(
        "module example.com/generated/client\n\ngo 1.23.8\n",
        encoding="utf-8",
    )
    (output_dir / "transports" / "http" / "path_params_test.go").write_text(
        """
package http

import "testing"

func TestExpandPathEscapesSegments(t *testing.T) {
	path, err := expandPath("/api/user/{user}/{medal}", struct {
		User  string `uri:"user"`
		Medal string `uri:"medal"`
	}{User: "alice/bob", Medal: "gold medal"})
	if err != nil {
		t.Fatalf("expandPath returned error: %v", err)
	}
	if path != "/api/user/alice%2Fbob/gold%20medal" {
		t.Fatalf("unexpected expanded path: %q", path)
	}
}

func TestExpandPathRequiresAllParams(t *testing.T) {
	_, err := expandPath("/api/user/{user}/{medal}", map[string]string{"user": "alice"})
	if err == nil {
		t.Fatal("expected missing path parameter error")
	}
}
        """.strip()
        + "\n",
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
