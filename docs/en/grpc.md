# gRPC

vNext gRPC no longer treats an existing `.proto` tree as an independent source of truth. The `grpc-proto` target emits `.proto` files and service definitions from ContractGraph, and ContractGraph still comes from Blueprint.

## Targets

```toml
[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"

[[targets]]
id = "grpc.go"
kind = "grpc-go"
proto = "grpc.proto"
out_dir = "grpc/go"
module = "example.com/project/grpc/go"
files = ["api/**/*.proto"]

[[targets]]
id = "grpc.python"
kind = "grpc-python"
proto = "grpc.proto"
out_dir = "grpc/python"
files = ["api/**/*.proto"]
python_package_root = "pb"
```

- `out_dir`: proto output directory.
- `package`: proto package.
- `go_package_prefix`: used to generate `option go_package`; files are split by Blueprint root/group.
- `proto` on `grpc-go` / `grpc-python` must reference a `grpc-proto` target in the same config.
- `files` matches relative to the proto target `out_dir`; the proto target `out_dir` is automatically added as an include root.
- `source_root` is optional; when set, `files` is matched relative to that directory, `protoc` runs there, and the proto target `out_dir` is still added as an include root.
- `module`: optional for `grpc-go`; when set, Go import-path output mode is used and generated files are split by `option go_package`, avoiding multiple proto files in the same Go package directory.
- `grpc-go` requires `protoc`, `protoc-gen-go`, and `protoc-gen-go-grpc`.
- `grpc-python` requires `grpcio-tools`; `python_package_root` places generated files under a package root and rewrites generated imports.

Go/Python targets generate only protobuf/gRPC stubs, not business service implementations.

The repository commits `examples/grpc/protos/`, `examples/grpc/go/`, and `examples/grpc/python/` snapshots so users can inspect actual proto, Go stub, and Python stub output. There is currently no `grpc-typescript` target; `examples/typescript/` demonstrates API Blueprint's TypeScript HTTP/Wails client artifacts, not gRPC TypeScript stubs.

## RPC Mapping

- Normal HTTP routes emit unary RPCs.
- `STREAM` emits server-streaming RPCs.
- `CHANNEL` emits bidirectional streaming RPCs.
- Single-model or union `SERVER_MESSAGE` / `CLIENT_MESSAGE` contracts enter the proto message set.

## Proto Metadata

Blueprint remains the source of truth, but models and fields can carry small proto metadata for migrating existing protocols:

```python
class SharedOptions(Model):
    __proto_file__ = "shared/browseragent/browser/v1/browser.proto"
    __proto_package__ = "browseragent.browser.v1"
    __proto_go_package__ = "example.com/project/grpc/go/shared/browseragent/browser/v1;browserpb"

    user = String(description="user", proto_number=1)


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

- `proto_number`: explicit field number. Duplicate field numbers fail during proto planning. Omitted field numbers are assigned automatically in declaration order.
- `proto_name`: explicit proto field name, useful when migrating a small number of existing camelCase proto fields. Omitted names are normalized from the DSL field name.
- `proto_optional`: renders a proto3 `optional` field.
- `proto_oneof`: renders fields with the same name as a proto `oneof`.
- `proto_type` / `proto_import`: map to a well-known type or external proto type.
- `__proto_file__` / `__proto_package__` / `__proto_go_package__`: emit a model into a specific proto file and automatically import it from referencing files.
- Numeric enums use Python enum member names and numeric values. Unprefixed names are prefixed with the enum name; names that already contain underscores or a full proto-style prefix are kept unchanged.

## CLI

```sh
api-gen generate -c api-blueprint.toml --target grpc.proto
api-gen generate -c api-blueprint.toml --target grpc.go
api-gen generate -c api-blueprint.toml --target grpc.python
api-gen manifest -c api-blueprint.toml --out api-blueprint.contract.json
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
```

Old raw proto targets/jobs are outside the vNext public mainline. When field numbers, oneof, well-known types, or cross-file imports are needed, express them as Blueprint DSL metadata and let `grpc-proto` emit the proto files.
