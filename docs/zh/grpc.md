# gRPC

vNext gRPC 不再把已有 `.proto` 目录树作为独立真源。`grpc-proto` target 从 ContractGraph 输出 `.proto` 文件和 service 定义，ContractGraph 仍然来自 Blueprint。

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

- `out_dir`：proto 输出目录。
- `package`：proto package。
- `go_package_prefix`：用于生成 `option go_package`，文件按 Blueprint root/group 拆分。
- `grpc-go` / `grpc-python` 的 `proto` 必须引用同配置里的 `grpc-proto` target。
- `files` 相对 proto target 的 `out_dir` 匹配；proto target `out_dir` 会自动作为 include root。
- `source_root` 可选；设置后 `files` 相对此目录匹配，`protoc` 也在此目录执行，同时 proto target `out_dir` 仍会自动加入 include root。
- `module`：`grpc-go` 可选；设置后使用 Go import path 输出模式，生成目录会按 `option go_package` 的 import path 分包，避免多个 proto 文件落在同一 Go package 目录里。
- `grpc-go` 需要 `protoc`、`protoc-gen-go`、`protoc-gen-go-grpc`。
- `grpc-python` 需要 `grpcio-tools`；`python_package_root` 会把生成物放入包根并重写生成 import。

Go/Python target 只生成 protobuf/gRPC stub，不生成业务 service 实现。

仓库示例提交了 `examples/grpc/protos/`、`examples/grpc/go/` 与 `examples/grpc/python/` 快照，可直接查看 proto、Go stub 和 Python stub 的实际输出。当前没有 `grpc-typescript` target；`examples/typescript/` 展示的是 API Blueprint 的 TypeScript HTTP/Wails client 产物，不是 gRPC TypeScript stub。

## RPC 映射

- 普通 HTTP route 输出 unary RPC。
- `STREAM` 输出 server-streaming RPC。
- `CHANNEL` 输出 bidirectional streaming RPC。
- `SERVER_MESSAGE` / `CLIENT_MESSAGE` 的单模型或联合模型会进入 proto message 集合。

## Proto 元数据

Blueprint 仍是真源，但模型和字段可以携带少量 proto 元数据，以便迁移已有协议：

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

- `proto_number`：显式字段号；重复字段号会在 proto planning 阶段失败。未指定字段号时自动按声明顺序分配可用编号。
- `proto_name`：显式 proto 字段名，适合迁移少量已有 camelCase proto 字段；未指定时仍按 DSL 字段名规范化。
- `proto_optional`：输出 proto3 `optional` 字段。
- `proto_oneof`：把同名字段组渲染为 proto `oneof`。
- `proto_type` / `proto_import`：映射到 well-known type 或外部 proto 类型。
- `__proto_file__` / `__proto_package__` / `__proto_go_package__`：把模型输出到指定 proto 文件，并在引用方自动生成 import。
- 数字枚举会使用 Python enum member name 与数字值；未带前缀的名称会补上 enum 前缀，已带下划线或完整前缀的 proto 风格名称会保持不变。

## CLI

```sh
api-gen generate -c api-blueprint.toml --target grpc.proto
api-gen generate -c api-blueprint.toml --target grpc.go
api-gen generate -c api-blueprint.toml --target grpc.python
api-gen manifest -c api-blueprint.toml --out api-blueprint.contract.json
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
```

旧 raw proto targets/jobs 不属于 vNext 公共主线；需要指定字段号、oneof、well-known type 或跨文件 import 时，应在 Blueprint DSL 元数据里表达，再由 `grpc-proto` 输出。
