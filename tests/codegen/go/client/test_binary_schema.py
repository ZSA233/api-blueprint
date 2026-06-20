from __future__ import annotations

from .helpers import *


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

@pytest.mark.toolchain_smoke
def test_golang_client_generates_binary_schema_response_decoder(tmp_path):
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
    bp = Blueprint(root="/api", response_envelope=CodeMessageDataEnvelope)
    with bp.group("/binary") as views:
        views.GET("/audit").RSP_BINARY_SCHEMA(schema)

    output_dir = tmp_path / "client"
    writer = GolangClientWriter(output_dir, module="example.com/generated/client")
    writer.register(bp)
    writer.gen()

    route_text = (output_dir / "routes" / "api" / "binary" / "gen_client.go").read_text(encoding="utf-8")
    schema_text = (output_dir / "routes" / "api" / "binary" / "gen_binary.go").read_text(encoding="utf-8")
    runtime_text = (output_dir / "runtime" / "gen_client.go").read_text(encoding="utf-8")
    binary_runtime = (output_dir / "runtime" / "binary" / "gen_runtime.go").read_text(encoding="utf-8")
    transport_text = (output_dir / "transports" / "http" / "gen_transport.go").read_text(encoding="utf-8")

    assert (
        "func (client *GenBinaryClient) Audit(ctx context.Context, opts ...runtime.RequestOption) "
        "(*AuditPacket, error)"
    ) in route_text
    assert 'ResponseKind:     runtime.ResponseKind("binary_schema")' in route_text
    assert "var response AuditPacket" in route_text
    assert "func ParseAuditPacket(r io.Reader) (*AuditPacket, error)" in schema_text
    assert "func (value *AuditPacket) DecodeBinary(r io.Reader) error" in schema_text
    assert 'ResponseBinarySchema ResponseKind = "binary_schema"' in runtime_text
    assert "type DecodeError struct" in binary_runtime
    assert "func decodeBinarySchemaResponse" in transport_text

    if shutil.which("go") is None:
        return

    (output_dir / "go.mod").write_text("module example.com/generated/client\n\ngo 1.23.8\n", encoding="utf-8")
    result = subprocess.run(
        ["go", "test", "./..."],
        cwd=output_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

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
    assert 'runtimebinary.RequireRange("item_count", uint64(value.ItemCount), 0, uint64(1))' in schema_text
    assert 'runtimebinary.RequireRange("id", uint64(value.ID), uint64(1), ^uint64(0))' in schema_text
    assert "value.Item_count" not in schema_text
    assert "value.Id" not in schema_text
    assert "runtimebinary.JoinPath(path," not in schema_text
    assert "runtimebinary.IndexPath(" not in schema_text
    assert "func WrapField(path string, err error) error" in runtime_text
    assert "func IndexPath(path string, index int) string" in runtime_text

@pytest.mark.toolchain_smoke
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
