# gRPC

1.0 gRPC emits `.proto` files and service definitions from ContractGraph through the `grpc-proto` target by default, and ContractGraph still comes from Blueprint. When you only need to compile handwritten proto files into Go/Python stubs, `grpc-go` / `grpc-python` can omit `grpc-proto` and consume files under `source_root` directly.

## Targets

```toml
[[grpc.proto]]
id = "grpc.proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"

[[grpc.proto.proto_files]]
file = "api/demo/v1/demo.proto"
package = "example.api.demo.v1"
go_package = "example.com/project/grpc/go/api/demo/v1;demopb"
schema_modules = ["blueprints.api.demo"]
route_paths = ["/api/demo/v1/**"]
service = "DemoService"

[[grpc.go]]
id = "grpc.go"
proto = "grpc.proto"
out_dir = "grpc/go"
module = "example.com/project/grpc/go"
files = ["api/**/*.proto"]

[[grpc.python]]
id = "grpc.python"
proto = "grpc.proto"
out_dir = "grpc/python"
files = ["api/**/*.proto"]
module = "pb"
```

- `out_dir`: proto output directory.
- `package`: proto package.
- `go_package_prefix`: used to generate `option go_package` when no `proto_files` rule matches; files are split by Blueprint root/group.
- `[[grpc.proto]]`, `[[grpc.go]]`, and `[[grpc.python]]` are shortcut tables that normalize to canonical `[[targets]]`; canonical config remains supported.
- `[[targets.proto_files]]` / `[[grpc.proto.proto_files]]`: optional layout rules. Rules are evaluated in order and map schema module/name plus route path/id/service to a specific proto file/package/go_package/service.
- `proto` on `grpc-go` / `grpc-python` can reference a `grpc-proto` target in the same config. When `proto` is omitted, `source_root` is required.
- `files` matches relative to the proto target `out_dir` or `source_root`; when a proto target is referenced, its `out_dir` is automatically added as an include root.
- `source_root` is used for handwritten proto files or trimmed generated paths. When set, `files` is matched relative to that directory and `protoc` runs there.
- `module`: optional for `grpc-go`; when set, Go import-path output mode is used and generated files are split by `option go_package`, avoiding multiple proto files in the same Go package directory.
- `grpc-go` requires `protoc`, `protoc-gen-go`, and `protoc-gen-go-grpc`.
- `grpc-python` requires `grpcio-tools`; `python_package_root` places generated files under a package root and rewrites generated imports. In the shortcut table, `module = "pb"` maps to `python_package_root = "pb"`.

Go/Python targets generate only protobuf/gRPC stubs, not business service implementations.

The repository commits `examples/grpc/protos/`, `examples/grpc/go/`, and `examples/grpc/python/` snapshots so users can inspect actual proto, Go stub, and Python stub output. There is currently no `grpc-typescript` target; `examples/typescript/` demonstrates API Blueprint's TypeScript HTTP/Wails client artifacts, not gRPC TypeScript stubs.

Handwritten proto direct compilation example:

```toml
[[grpc.go]]
id = "grpc.go"
source_root = "protocols/grpc"
out_dir = "grpc/go"
files = ["**/*.proto"]
import_roots = ["third_party/protos"]

[[grpc.python]]
id = "grpc.python"
source_root = "protocols/grpc"
out_dir = "grpc/python"
files = ["**/*.proto"]
module = "pb"
```

## RPC Mapping

- Normal HTTP routes emit unary RPCs.
- `STREAM` emits server-streaming RPCs.
- `CHANNEL` emits bidirectional streaming RPCs.
- Single-model or union `SERVER_MESSAGE` / `CLIENT_MESSAGE` contracts enter the proto message set.

## DSL Fields And Layout

Blueprint remains the source of truth. New protocols should keep target-specific layout in TOML and keep generic contract semantics next to field declarations:

```python
from api_blueprint.includes import *


class SharedOptions(Model):
    user = field(1, String(description="user"))
    display_name = field(2, String(description="display name"), optional=True)


class ExternalPayload(Model):
    occurred_at = field(1, DateTime(description="occurred at"))
    payload = field(2, AnyValue(description="payload"))
    metadata = field(3, JSONValue(description="metadata"))


class CallbackMessage(Model):
    hello = field(1, Hello(description="hello"), choice="msg")
    task = field(2, TaskCallback(description="task"), choice="msg")
```

- `field(number, value)`: declares a stable contract field id. The gRPC writer maps it to a proto field number.
- `optional=True`: generic optional field semantics. gRPC renders proto3 `optional` for scalar/enum fields; message/repeated/map fields do not render proto optional.
- `choice="..."`: generic mutually exclusive choice semantics. The gRPC writer maps same-name choices to proto `oneof`.
- `alias`: use it when the serialized field name must differ from the DSL field name. gRPC preserves it as the proto field name.
- `DateTime` / `JSONValue` / `AnyValue`: semantic value types. The gRPC writer maps them to `google.protobuf.Timestamp`, `google.protobuf.Struct`, and `google.protobuf.Any`, with imports generated automatically.
- Omitted field ids are still assigned as proto field numbers in declaration order. Use `field()` for protocols that need long-term compatibility.

Legacy proto metadata remains available as a migration escape hatch, but it is not the recommended style for new protocols. New DSL should not add gRPC/proto/Go/TypeScript/Kotlin-specific fields:

```python
class CallbackMessage(Model):
    hello = HelloMessage(description="hello", proto_oneof="msg", proto_number=1)
    task = TaskCallbackMessage(description="task", proto_oneof="msg", proto_number=2)


class ExternalPayload(Model):
    occurred_at = Object(
        description="occurred at",
        proto_type="google.protobuf.Timestamp",
        proto_import="google/protobuf/timestamp.proto",
        proto_number=6,
    )


class CookiePartitionKey(Model):
    top_level_site = String(description="top level site", proto_name="topLevelSite", proto_number=1)
    same_party = Bool(description="same party", proto_optional=True, proto_number=2)
```

- `proto_number` / `proto_name` / `proto_optional`: legacy field metadata for existing proto compatibility.
- `proto_oneof`: legacy proto oneof metadata. New code should use generic `choice`.
- `proto_type` / `proto_import`: legacy external type metadata. Prefer `DateTime`, `JSONValue`, and `AnyValue` for common semantic types; cross-file schema/enum references should come from layout resolution.
- `__proto_file__` / `__proto_package__` / `__proto_go_package__`: emit a model into a specific proto file and automatically import it from referencing files.
- Numeric enums use Python enum member names and numeric values. Unprefixed names are prefixed with the enum name; names that already contain underscores or a full proto-style prefix are kept unchanged.

## CLI

```sh
api-gen generate -c api-blueprint.toml --target grpc.proto
api-gen generate -c api-blueprint.toml --target grpc.go
api-gen generate -c api-blueprint.toml --target grpc.python
api-gen manifest -c api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
```

Old raw proto targets/jobs are outside the 1.0 public mainline. When you only need to compile handwritten proto files, use `grpc-go` / `grpc-python` targets without `proto`. For Blueprint-generated proto, prefer `proto_files` for layout, `field()` for stable field identity, `choice` for mutually exclusive choices, and generic semantic field types for time, JSON, and arbitrary payloads; legacy `proto_*` metadata is only a compatibility escape hatch.
