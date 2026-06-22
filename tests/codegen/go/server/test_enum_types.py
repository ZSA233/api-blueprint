from __future__ import annotations

import enum as py_enum
import re
import subprocess

import pytest

from .helpers import *
from api_blueprint.engine.schema import Array, Enum, Map, String


class ResOp(py_enum.IntEnum):
    CREATE = 1  # Create item
    UPDATE = 2  # Update item


class GiftStatus(py_enum.IntEnum):
    ACTIVE = 1
    PAUSED = 2


class GiftFormat(py_enum.StrEnum):
    CARD = "card"
    COIN = "coin"


class BusinessType(py_enum.IntEnum):
    SINGLE_CHAT = 1
    PROFILE = 3
    SOCIAL = 5


class NestedGift(Model):
    status = Enum[GiftStatus]()


class OpRequest(Model):
    op = Enum[ResOp]()
    status = Enum[GiftStatus](omitempty=True)
    format = Enum[GiftFormat]()
    statuses = Array[Enum[GiftStatus]]()
    by_name = Map[String, Enum[GiftStatus]]()
    nested = NestedGift(description="nested")


class OpResponse(Model):
    op = Enum[ResOp]()


class PlainResponse(Model):
    name = String()


def _write_module(tmp_path):
    output_dir = tmp_path / "golang"
    output_dir.mkdir()
    (tmp_path / "go.mod").write_text("module example.com/generated\n\ngo 1.23.8\n", encoding="utf-8")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/op").REQ(OpRequest).RSP(OpResponse)
        views.POST("/inline").REQ(op=Enum[ResOp]()).RSP(status=Enum[GiftStatus]())
        views.GET("/enum-query", operation_id="EnumQuery").ARGS(status=Enum[GiftStatus]()).RSP(OpResponse)
        views.POST("/enum-form", operation_id="EnumForm").REQ_FORM(status=Enum[GiftStatus]()).RSP(OpResponse)
        views.DELETE("/enum-path/{status}", operation_id="EnumPath").REQ_PATH(status=Enum[GiftStatus]()).RSP(OpResponse)
    with bp.group("/first") as views:
        views.GET("/list", operation_id="List").ARGS(name=String()).RSP(PlainResponse)
    with bp.group("/risk_hit") as views:
        views.GET("/list", operation_id="List").ARGS(business_type=Enum[BusinessType]()).RSP(PlainResponse)
    with bp.group("/plain") as views:
        views.GET("/name").RSP(PlainResponse)

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()
    return output_dir


def _assert_go_field_type(source: str, field_name: str, type_name: str) -> None:
    assert re.search(rf"\b{re.escape(field_name)}\s+{re.escape(type_name)}\b", source)


def test_golang_server_route_dtos_use_typed_enums(tmp_path):
    output_dir = _write_module(tmp_path)

    shared_types = (output_dir / "routes" / "api" / "_gen_types" / "types.go").read_text(encoding="utf-8")
    demo_types = (output_dir / "routes" / "api" / "demo" / "gen_types.go").read_text(encoding="utf-8")
    risk_hit_types = (output_dir / "routes" / "api" / "risk_hit" / "gen_types.go").read_text(encoding="utf-8")
    plain_types = (output_dir / "routes" / "api" / "plain" / "gen_types.go").read_text(encoding="utf-8")
    enums_source = (output_dir / "routes" / "api" / "_gen_enums" / "enums.go").read_text(encoding="utf-8")

    assert 'enums "example.com/generated/golang/routes/api/_gen_enums"' in shared_types
    _assert_go_field_type(shared_types, "Op", "enums.ResOp")
    _assert_go_field_type(shared_types, "Status", "enums.GiftStatus")
    _assert_go_field_type(shared_types, "Format", "enums.GiftFormat")
    _assert_go_field_type(shared_types, "Statuses", "[]enums.GiftStatus")
    _assert_go_field_type(shared_types, "ByName", "map[string]enums.GiftStatus")
    assert 'binding:"oneof=1 2"' in shared_types
    assert 'binding:"omitempty,oneof=1 2"' in shared_types
    assert 'binding:"oneof=card coin"' in shared_types

    assert 'enums "example.com/generated/golang/routes/api/_gen_enums"' in demo_types
    assert "Op enums.ResOp" in demo_types
    assert "Status enums.GiftStatus" in demo_types
    assert "type REQ_EnumQuery_QUERY struct" in demo_types
    assert "type REQ_EnumForm_FORM struct" in demo_types
    assert "type REQ_EnumPath_PATH struct" in demo_types
    assert "BusinessType enums.BusinessType" in risk_hit_types
    assert "_gen_enums" not in plain_types

    assert "type BusinessType int" in enums_source
    assert "CREATE = 1 // Create item" in enums_source
    assert "UPDATE = 2 // Update item" in enums_source
    assert "--marshal" not in enums_source
    assert "--nocase --names --values --mustparse" in enums_source


@pytest.mark.toolchain_smoke
def test_golang_server_typed_enums_keep_scalar_json_wire(tmp_path):
    output_dir = _write_module(tmp_path)

    generated_enum = output_dir / "routes" / "api" / "_gen_enums" / "enums_gen.go"
    assert generated_enum.is_file()
    generated_enum_text = generated_enum.read_text(encoding="utf-8")
    assert "MarshalText" not in generated_enum_text
    assert "UnmarshalText" not in generated_enum_text

    (output_dir / "routes" / "api" / "_gen_types" / "enum_wire_test.go").write_text(
        r'''
package types_test

import (
	"encoding/json"
	"strings"
	"testing"

	enums "example.com/generated/golang/routes/api/_gen_enums"
	types "example.com/generated/golang/routes/api/_gen_types"
)

func TestTypedEnumScalarJSONWire(t *testing.T) {
	payload := types.OpRequest{
		Op:       enums.ResOpCREATE,
		Status:   enums.GiftStatusPAUSED,
		Format:   enums.GiftFormatCARD,
		Statuses: []enums.GiftStatus{enums.GiftStatusACTIVE, enums.GiftStatusPAUSED},
		ByName:   map[string]enums.GiftStatus{"demo": enums.GiftStatusPAUSED},
		Nested:   &types.NestedGift{Status: enums.GiftStatusACTIVE},
	}

	encoded, err := json.Marshal(payload)
	if err != nil {
		t.Fatal(err)
	}
	wire := string(encoded)
	if !strings.Contains(wire, `"op":1`) || !strings.Contains(wire, `"status":2`) {
		t.Fatalf("numeric enum encoded as non-numeric wire: %s", wire)
	}
	if strings.Contains(wire, "CREATE") || strings.Contains(wire, "PAUSED") {
		t.Fatalf("numeric enum leaked enum names into wire: %s", wire)
	}
	if !strings.Contains(wire, `"format":"card"`) {
		t.Fatalf("string enum did not keep string value wire: %s", wire)
	}

	var decoded types.OpRequest
	if err := json.Unmarshal([]byte(`{"op":2,"status":1,"format":"coin","statuses":[1,2],"by_name":{"demo":2},"nested":{"status":1}}`), &decoded); err != nil {
		t.Fatal(err)
	}
	if decoded.Op != enums.ResOpUPDATE || decoded.Status != enums.GiftStatusACTIVE || decoded.Format != enums.GiftFormatCOIN {
		t.Fatalf("decoded enum values mismatch: %#v", decoded)
	}
}
'''.lstrip(),
        encoding="utf-8",
    )
    (output_dir / "routes" / "api" / "demo" / "enum_bind_test.go").write_text(
        r'''
package demo

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	enums "example.com/generated/golang/routes/api/_gen_enums"
	"github.com/gin-gonic/gin"
)

func queryContext(rawURL string) *gin.Context {
	recorder := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(recorder)
	ctx.Request = httptest.NewRequest(http.MethodGet, rawURL, nil)
	return ctx
}

func formContext(body string) *gin.Context {
	recorder := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(recorder)
	ctx.Request = httptest.NewRequest(http.MethodPost, "/", strings.NewReader(body))
	ctx.Request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	return ctx
}

func pathContext(value string) *gin.Context {
	recorder := httptest.NewRecorder()
	ctx, _ := gin.CreateTestContext(recorder)
	ctx.Params = gin.Params{{Key: "status", Value: value}}
	ctx.Request = httptest.NewRequest(http.MethodDelete, "/", nil)
	return ctx
}

func TestTypedEnumBinding(t *testing.T) {
	gin.SetMode(gin.TestMode)

	var query REQ_EnumQuery_QUERY
	if err := queryContext("/?status=1").ShouldBindQuery(&query); err != nil {
		t.Fatal(err)
	}
	if query.Status != enums.GiftStatusACTIVE {
		t.Fatalf("query enum mismatch: %#v", query)
	}
	var badQuery REQ_EnumQuery_QUERY
	if err := queryContext("/?status=9").ShouldBindQuery(&badQuery); err == nil {
		t.Fatal("expected invalid query enum to fail validation")
	}

	var form REQ_EnumForm_FORM
	if err := formContext("status=2").ShouldBind(&form); err != nil {
		t.Fatal(err)
	}
	if form.Status != enums.GiftStatusPAUSED {
		t.Fatalf("form enum mismatch: %#v", form)
	}
	var badForm REQ_EnumForm_FORM
	if err := formContext("status=9").ShouldBind(&badForm); err == nil {
		t.Fatal("expected invalid form enum to fail validation")
	}

	var path REQ_EnumPath_PATH
	if err := pathContext("1").ShouldBindUri(&path); err != nil {
		t.Fatal(err)
	}
	if path.Status != enums.GiftStatusACTIVE {
		t.Fatalf("path enum mismatch: %#v", path)
	}
	var badPath REQ_EnumPath_PATH
	if err := pathContext("9").ShouldBindUri(&badPath); err == nil {
		t.Fatal("expected invalid path enum to fail validation")
	}
}
'''.lstrip(),
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
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
