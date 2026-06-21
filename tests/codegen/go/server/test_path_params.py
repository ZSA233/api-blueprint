from __future__ import annotations

import re

from .helpers import *


@pytest.mark.toolchain_smoke
def test_golang_server_binds_path_query_and_body_request_slots(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text(
        """
module example.com/generated

go 1.23.8

require github.com/gin-gonic/gin v1.10.1
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    class DeleteUserMedalPath(Model):
        user = String(description="user")
        medal = String(description="medal")

    class DeleteUserMedalQuery(Model):
        force = String(optional=True)

    class DeleteUserMedalJSON(Model):
        reason = String(description="reason")

    class DeleteUserMedalResponse(Model):
        ok = String(description="ok")

    bp = Blueprint(root="/api")
    with bp.group("/medal") as views:
        views.DELETE("/user/{user}/{medal}", operation_id="DeleteUserMedal").REQ_PATH(
            DeleteUserMedalPath
        ).ARGS(DeleteUserMedalQuery).REQ(DeleteUserMedalJSON).RSP(DeleteUserMedalResponse)

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    route_types = (output_dir / "routes" / "api" / "medal" / "gen_types.go").read_text(encoding="utf-8")
    shared_types = (output_dir / "routes" / "api" / "_gen_types" / "types.go").read_text(encoding="utf-8")
    provider_req = (output_dir / "providers" / "gen_wrapper.go").read_text(encoding="utf-8")
    provider_context = (output_dir / "providers" / "gen_context.go").read_text(encoding="utf-8")
    http_runtime = (output_dir / "transports" / "http" / "gen_engine.go").read_text(encoding="utf-8")
    http_route = (output_dir / "transports" / "http" / "api" / "medal" / "gen_interface.go").read_text(
        encoding="utf-8"
    )
    route_constants = (output_dir / "routes" / "api" / "medal" / "gen_routes.go").read_text(encoding="utf-8")

    assert "type REQ_DeleteUserMedal_PATH = types.DeleteUserMedalPath" in route_types
    assert "type REQ_DeleteUserMedal = providers.REQ[\n\tREQ_DeleteUserMedal_PATH," in route_types
    assert "type REQ[Path, Query, Body any] struct" in provider_req
    assert "Path  *Path" in provider_req
    assert "Query *Query" in provider_req
    assert "Body  *Body" in provider_req
    assert "type Context[Path, Query, Body, R any] struct" in provider_context
    assert "Request  *RequestContext[Path, Query, Body]" in provider_context
    assert "Response *ResponseContext" in provider_context
    assert 'User  string `json:"user" xml:"user" form:"user" uri:"user"`' in shared_types
    assert "RoutePathDeleteUserMedal" in route_constants
    assert '"/api/medal/user/{user}/{medal}"' in route_constants
    assert "RoutePathDeleteUserMedal" in http_route
    assert "shared.RoutePathDeleteUserMedal" in http_route
    assert 'HTTPRoutePathDeleteUserMedal = "/api/medal/user/:user/:medal"' in http_route
    assert "httptransport.DELETE(\n\t\t\tHTTPRoutePathDeleteUserMedal," in http_route
    assert re.search(r"Path:\s+RoutePathDeleteUserMedal", http_route)
    assert 'PathParams:             []string{"user", "medal"}' in http_route
    assert '"req=path,query,json|handle|rsp=json@CodeMessageDataEnvelope"' in http_route
    assert "BindPath" in http_runtime
    assert "ginCtx.ShouldBindUri(target)" in http_runtime
    assert ".Q" not in route_types
    assert ".B" not in route_types

    if shutil.which("go") is None:
        return

    (output_dir / "routes" / "api" / "medal" / "path_bind_test.go").write_text(
        """
package medal

import (
	"testing"
)

func TestTypedRequestSlotsCompile(t *testing.T) {
	req := &REQ_DeleteUserMedal{
		Path:  &REQ_DeleteUserMedal_PATH{User: "alice", Medal: "gold"},
		Query: &REQ_DeleteUserMedal_QUERY{Force: "yes"},
		Body:  &REQ_DeleteUserMedal_JSON{Reason: "cleanup"},
	}
	if req.Path.User != "alice" || req.Path.Medal != "gold" {
		t.Fatalf("path not bound: %#v", req.Path)
	}
	if req.Query.Force != "yes" {
		t.Fatalf("query not bound: %#v", req.Query)
	}
	if req.Body.Reason != "cleanup" {
		t.Fatalf("body not bound: %#v", req.Body)
	}
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "transports" / "http" / "api" / "medal" / "path_bind_test.go").write_text(
        """
package medal

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"testing"

	shared "example.com/generated/golang/routes/api/medal"
	"github.com/gin-gonic/gin"
)

type adapter struct{}

func (adapter) DeleteUserMedal(ctx *shared.CTX_DeleteUserMedal, req *shared.REQ_DeleteUserMedal) (*shared.RSP_DeleteUserMedal, error) {
	if req.Path == nil || req.Path.User != "alice" || req.Path.Medal != "gold" {
		panic("path params not bound")
	}
	if req.Query == nil || req.Query.Force != "yes" {
		panic("query params not bound")
	}
	if req.Body == nil || req.Body.Reason != "cleanup" {
		panic("json body not bound")
	}
	return &shared.RSP_DeleteUserMedal{Ok: "ok"}, nil
}

func TestMountBindsPathQueryAndBody(t *testing.T) {
	gin.SetMode(gin.TestMode)
	engine := gin.New()
	Mount(engine, adapter{})

	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodDelete, "/api/medal/user/alice/gold?force=yes", bytes.NewBufferString(`{"reason":"cleanup"}`))
	request.Header.Set("Content-Type", "application/json")
	engine.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("unexpected status %d: %s", recorder.Code, recorder.Body.String())
	}
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    tidy = subprocess.run(
        ["go", "mod", "tidy"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert tidy.returncode == 0, tidy.stdout + tidy.stderr

    result = subprocess.run(
        ["go", "test", "./..."],
        cwd=output_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
