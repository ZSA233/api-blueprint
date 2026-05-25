from __future__ import annotations

from .helpers import *


def test_golang_writer_generates_binary_schema_parser_and_http_binding(tmp_path):
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

    schema = parse_binary_schema(
        """
# packet DemoPacket

endian: little
content-type: application/octet-stream
content-encoding: identity,gzip,br

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| magic | bytes | 4 | const="DEMO" | magic |
| flags | Flags | 1 | min=0 | flags |
| item_num | u32 | 1 | min=1,max=8,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| session_id_len | u32 | 1 | max=128,sizeof=session_id | session id length |
| session_id | string | session_id_len | encoding=utf8 | session id |
| items | Item | item_num | | items |

## struct Item

| field | type | count | rule | comment |
|---|---|---:|---|---|
| value | u32 | 1 | max=100 | value |

## enum Mode : u8

| name | value | comment |
|---|---:|---|
| Normal | 0 | normal |
| Fast | 1 | fast |

## bitflags Flags : u32

| name | bits | rule | comment |
|---|---:|---|---|
| HasItems | 0 | | has items |
| Mode | 1..2 | enum=Mode | mode |
| Reserved | 3..31 | const=0 | reserved |
        """.strip(),
        source_path=tmp_path / "demo_packet.md",
    )

    bp = Blueprint(root="/api", providers=[provider.Req(), provider.Handle(), provider.Rsp()])
    with bp.group("/demo") as views:
        views.POST("/binary").ARGS(token=String(description="token")).REQ_BINARY(schema).RSP(ok=String(description="ok"))

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    binary_parser = (output_dir / "routes" / "api" / "demo" / "_gen_binary" / "gen_binary.go").read_text(
        encoding="utf-8"
    )
    binary_runtime = (output_dir / "runtime" / "binary" / "gen_runtime.go").read_text(
        encoding="utf-8"
    )
    route_models = (output_dir / "routes" / "api" / "demo" / "gen_types.go").read_text(
        encoding="utf-8"
    )
    req_provider = (output_dir / "providers" / "gen_req.go").read_text(encoding="utf-8")
    http_runtime = (output_dir / "transports" / "http" / "gen_engine.go").read_text(encoding="utf-8")
    http_route = (output_dir / "transports" / "http" / "api" / "demo" / "gen_interface.go").read_text(
        encoding="utf-8"
    )

    assert "package binary" in binary_parser
    assert "package binaryruntime" in binary_runtime
    assert "func ParseDemoPacket(r io.Reader) (*DemoPacket, error)" in binary_parser
    assert "func (msg *DemoPacket) DecodeBinary(r io.Reader) error" in binary_parser
    assert "evalBinaryExpr" not in binary_parser
    assert "vars map[string]uint64" not in binary_parser
    assert 'fmt.Sprintf("%s.' not in binary_parser
    assert "\n\n\n" not in binary_parser
    assert "if out.Magic != [4]byte{68, 69, 77, 79}" in binary_parser
    assert "var fixed [12]byte" in binary_parser
    assert "&4294967288 != 0" in binary_parser
    assert "func (f DemoPacketFlags) HasItems() bool" in binary_parser
    assert "func (f DemoPacketFlags) WithHasItems(enabled bool) DemoPacketFlags" in binary_parser
    assert "func (f DemoPacketFlags) Mode() DemoPacketMode" in binary_parser
    assert "func (f DemoPacketFlags) WithMode(value DemoPacketMode) DemoPacketFlags" in binary_parser
    assert "DemoPacketFlagsReservedMask DemoPacketFlags = 4294967288" in binary_parser
    assert "func (f DemoPacketFlags) HasReservedBits() bool" in binary_parser
    assert "func (f DemoPacketFlags) Validate() error" in binary_parser
    assert "ClearReservedBits" not in binary_parser
    assert "DemoPacketFlagsReserved   DemoPacketFlags" not in binary_parser
    assert "func BytesOf" not in binary_parser
    assert "func BytesOf" in binary_runtime
    assert "binaryruntime.UnsafeString(sessionIDValue)" in binary_parser
    assert "SessionID    string" in binary_parser
    assert 'binary "example.com/generated/golang/routes/api/demo/_gen_binary"' in route_models
    assert "binary.DemoPacket" in route_models
    assert "BindBinary bool" in req_provider
    assert 'strings.Contains(data, "B")' in req_provider
    http_config = (output_dir / "transports" / "http" / "gen_config.go").read_text(encoding="utf-8")
    assert "BinaryContentDecoders" in http_config
    assert "map[string]BinaryContentDecoder" in http_config
    assert "gzip.NewReader" in http_runtime
    assert "custom := binaryContentDecoder(config, encoding)" in http_runtime
    assert "custom(ginCtx.Request.Body)" in http_runtime
    assert "decoder.DecodeBinary(reader)" in http_runtime
    assert "binaryContentEncodingAllowed(encoding, allowedContentEncodings)" in http_runtime
    assert "http.StatusUnsupportedMediaType" in http_runtime
    assert "http.StatusRequestEntityTooLarge" in http_runtime
    assert '"req=QB|handle|rsp=json@CodeMessageDataEnvelope"' in http_route
    assert "HTTP: sharedprovider.HTTPRouteInfo{" in http_route
    assert "Request: sharedprovider.HTTPRequestInfo{" in http_route
    assert 'BinaryContentEncodings: []string{"identity", "gzip", "br"}' in http_route
    assert "bindRequest(ginCtx, executor.Indexer.Req, executor.Route)" in http_runtime
    assert "route.HTTP.Request.BinaryContentEncodings" in http_runtime
    assert "firstBinaryContentEncodings" not in http_runtime

    if shutil.which("go") is None:
        pytest.skip("go toolchain is not available")

    assert not (output_dir / "routes" / "api" / "_gen_binary").exists()

    binary_test = output_dir / "routes" / "api" / "demo" / "_gen_binary" / "gen_binary_test.go"
    binary_test.write_text(
        r'''
package binary

import (
	"bytes"
	stdbinary "encoding/binary"
	"strings"
	"testing"
)

func demoPacketForTest(magic string, flags uint32, itemNum uint32, sessionID string, values ...uint32) []byte {
	var buf bytes.Buffer
	buf.WriteString(magic)
	_ = stdbinary.Write(&buf, stdbinary.LittleEndian, flags)
	_ = stdbinary.Write(&buf, stdbinary.LittleEndian, itemNum)
	_ = stdbinary.Write(&buf, stdbinary.LittleEndian, uint32(len(sessionID)))
	buf.WriteString(sessionID)
	for _, value := range values {
		_ = stdbinary.Write(&buf, stdbinary.LittleEndian, value)
	}
	return buf.Bytes()
}

func TestParseDemoPacketGenerated(t *testing.T) {
	parsed, err := ParseDemoPacket(bytes.NewReader(demoPacketForTest("DEMO", 1, 2, "session-a", 7, 9)))
	if err != nil {
		t.Fatalf("parse failed: %v", err)
	}
	if parsed.Body.SessionID != "session-a" {
		t.Fatalf("unexpected session id: %q", parsed.Body.SessionID)
	}
	if len(parsed.Body.Items) != 2 || parsed.Body.Items[0].Value != 7 || parsed.Body.Items[1].Value != 9 {
		t.Fatalf("unexpected items: %+v", parsed.Body.Items)
	}
}

func TestParseDemoPacketGeneratedErrors(t *testing.T) {
	if _, err := ParseDemoPacket(bytes.NewReader(demoPacketForTest("BAD!", 1, 1, "x", 1))); err == nil || !strings.Contains(err.Error(), "DemoPacket.header.magic: const mismatch") {
		t.Fatalf("expected magic error, got %v", err)
	}
	if _, err := ParseDemoPacket(bytes.NewReader(demoPacketForTest("DEMO", 8, 1, "x", 1))); err == nil || !strings.Contains(err.Error(), "DemoPacket.header.flags: const mismatch") {
		t.Fatalf("expected reserved flags error, got %v", err)
	}
	if _, err := ParseDemoPacket(bytes.NewReader(demoPacketForTest("DEMO", 1, 9, "x", 1))); err == nil || !strings.Contains(err.Error(), "DemoPacket.header.item_num: exceeds max") {
		t.Fatalf("expected max error, got %v", err)
	}
	if _, err := ParseDemoPacket(bytes.NewReader(demoPacketForTest("DEMO", 1, 1, "x", 101))); err == nil || !strings.Contains(err.Error(), "DemoPacket.body.items[0].value: exceeds max") {
		t.Fatalf("expected nested max error, got %v", err)
	}
}
'''.lstrip(),
        encoding="utf-8",
    )
    subprocess.run(["go", "test", "./golang/routes/api/demo/_gen_binary"], cwd=tmp_path, check=True)

def test_golang_server_generates_binary_schema_response_writer_and_file_default_filename(tmp_path):
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

    schema = parse_binary_schema(
        """
# packet AuditPacket

endian: little
content-type: application/vnd.audit-packet

## header

| field | type | count | rule | comment |
|---|---|---:|---|---|
| kind | u8 | 1 | const=2 | kind |
| item_count | u16 | 1 | min=1,max=4,sizeof=items | item count |

## body

| field | type | count | rule | comment |
|---|---|---:|---|---|
| items | AuditItem | item_count | | items |

## struct AuditItem

| field | type | count | rule | comment |
|---|---|---:|---|---|
| id | u32 | 1 | min=1 | item id |
        """.strip(),
        source_path="audit_packet.md",
    )
    bp = Blueprint(root="/api", providers=[provider.Req(), provider.Handle(), provider.Rsp()])
    with bp.group("/binary") as views:
        views.GET("/audit").RSP_BINARY_SCHEMA(schema)
        views.GET("/download").RSP_FILE(content_type="application/octet-stream", default_filename="audit.bin")

    writer = GolangWriter(output_dir)
    writer.register(bp)
    writer.gen()

    binary_text = (output_dir / "routes" / "api" / "binary" / "_gen_binary" / "gen_binary.go").read_text(
        encoding="utf-8"
    )
    route_types = (output_dir / "routes" / "api" / "binary" / "gen_types.go").read_text(encoding="utf-8")
    http_runtime = (output_dir / "transports" / "http" / "gen_engine.go").read_text(encoding="utf-8")
    http_route = (output_dir / "transports" / "http" / "api" / "binary" / "gen_interface.go").read_text(
        encoding="utf-8"
    )

    assert "func (msg *AuditPacket) WriteBinary(output io.Writer) error" in binary_text
    assert "func WriteAuditPacket(value *AuditPacket, writer *binaryruntime.Writer) error" in binary_text
    assert "type RSP_Audit = binary.AuditPacket" in route_types
    assert '"req|handle|rsp=binary_schema@CodeMessageDataEnvelope"' in http_route
    assert 'DefaultFilename: "audit.bin"' in http_route
    assert "writeBinarySchemaResponse" in http_runtime
    assert "writeRawResponse(ginCtx, rspProvider.Type, rspProvider.Route.HTTP.Response.DefaultFilename, response)" in http_runtime

    if shutil.which("go") is None:
        return

    result = subprocess.run(
        ["go", "test", "./routes/api/binary", "./runtime/binary"],
        cwd=output_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
