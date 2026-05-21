# gRPC

gRPC 生成由 `grpc-proto` target 从 ContractGraph 输出 `.proto` 文件和 service 定义，ContractGraph 仍然来自 Blueprint。只需要把手写 proto 编译成 Go/Python stub 时，也可以省略 `grpc-proto`，让 `grpc-go` / `grpc-python` 直接消费 `source_root` 下的 proto 文件。

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

- `out_dir`：proto 输出目录。
- `package`：proto package。
- `go_package_prefix`：用于未命中 `proto_files` 规则时生成 `option go_package`，文件按 Blueprint root/group 拆分。
- `[[grpc.proto]]`、`[[grpc.go]]`、`[[grpc.python]]` 是快捷表，会 normalize 成 canonical `[[targets]]`；canonical 配置仍然兼容。
- `[[targets.proto_files]]` / `[[grpc.proto.proto_files]]`：可选布局规则；按配置顺序把 schema module/name 与 route path/id/service 映射到指定 proto file/package/go_package/service。
- `grpc-go` / `grpc-python` 的 `proto` 可引用同配置里的 `grpc-proto` target；省略 `proto` 时必须设置 `source_root`。
- `files` 相对 proto target 的 `out_dir` 或 `source_root` 匹配；引用 proto target 时，proto target `out_dir` 会自动作为 include root。
- `source_root` 用于手写 proto 或裁剪生成路径；设置后 `files` 相对此目录匹配，`protoc` 也在此目录执行。
- `module`：`grpc-go` 可选；设置后使用 Go import path 输出模式，生成目录会按 `option go_package` 的 import path 分包，避免多个 proto 文件落在同一 Go package 目录里。
- `grpc-go` 需要 `protoc`、`protoc-gen-go`、`protoc-gen-go-grpc`。
- `grpc-python` 需要 `grpcio-tools`；`python_package_root` 会把生成物放入包根并重写生成 import。快捷表中 `module = "pb"` 会映射为 `python_package_root = "pb"`。

Go/Python target 只生成 protobuf/gRPC stub，不生成业务 service 实现。

执行 `api-gen generate --target grpc.*` 时，`grpc-proto` 会记录每个写出的 `.proto` 文件，`grpc-go` / `grpc-python` 会记录 stub 工具链执行与完成。它们都属于生成器拥有输出，不使用内容级 skip 语义。

仓库示例提交了 `examples/grpc/protos/`、`examples/grpc/go/` 与 `examples/grpc/python/` 快照，可直接查看 proto、Go stub 和 Python stub 的实际输出。TypeScript 示例展示 API Blueprint 的 HTTP/Wails client 产物；gRPC TypeScript stub 不是生成目标。

手写 proto 直编示例：

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

## HTTP raw media 边界

gRPC 需要文件、bytes、stream 或 typed binary packet 这类能力，但这些能力不继承 HTTP raw contract。`multipart`、`Content-Disposition`、HTTP status/header、MIME download 和 HTTP byte stream 都属于 HTTP transport 语义；`grpc-proto` 遇到 HTTP raw media route 或 HTTP binary schema body/response 时会在 `api-gen check` 阶段报明确 unsupported，不会把它们自动投影为 proto。

推荐使用 proto-native 建模：

- 小型 bytes 或 typed binary packet：使用 protobuf `bytes` 字段承载。
- 保留 Markdown Binary Schema 精确 wire format：把 encoded packet 放入 `bytes payload`，不要自动展开成 proto fields。
- 文件下载：使用 server-streaming `FileChunk`；首包或 metadata 携带 `filename`、`content_type`、`size`、`sha256`，后续包携带 `bytes data`。
- 文件上传 / multipart：使用 client-streaming `UploadChunk`；首包携带文件 metadata，后续包携带 `bytes data`；普通表单字段应进入显式 request message。
- byte stream / MJPEG：使用 server-streaming chunk message，不生成 HTTP multipart boundary。

## RPC 映射

- 普通 HTTP route 输出 unary RPC。
- `STREAM` 输出 server-streaming RPC。
- `CHANNEL` 输出 bidirectional streaming RPC。
- `SERVER_MESSAGE` / `CLIENT_MESSAGE` 的单模型或联合模型会进入 proto message 集合。

## DSL 字段与布局

Blueprint 仍是真源。新协议推荐把 target-specific 布局放在 TOML，把通用契约语义放在字段声明旁边：

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

- `field(number, value)`：声明稳定 contract field id；gRPC writer 将它映射为 proto field number。
- `optional=True`：通用可缺省语义；gRPC 对 scalar/enum 输出 proto3 `optional`，message/repeated/map 不输出 proto optional。
- `choice="..."`：通用互斥选择语义；gRPC writer 将同名 choice 映射为 proto `oneof`。
- `alias`：需要改变序列化字段名时使用；gRPC 会把它原样保留为 proto field name。
- `DateTime` / `JSONValue` / `AnyValue`：通用语义类型；gRPC writer 分别映射到 `google.protobuf.Timestamp`、`google.protobuf.Struct`、`google.protobuf.Any` 并自动生成 import。
- 未显式声明 field id 时，gRPC 仍会按声明顺序自动分配字段号；对需要长期兼容的协议，推荐显式使用 `field()`。

### 兼容性说明

Proto-specific metadata 仍保留为迁移逃生口，但不作为新协议主线写法。新 DSL 不应为了 gRPC/proto/Go/TypeScript/Kotlin 等 target 写专用字段：

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

- `proto_number` / `proto_name` / `proto_optional`：字段级 metadata，适合兼容已有 proto。
- `proto_oneof`：proto oneof metadata；新代码使用通用 `choice`。
- `proto_type` / `proto_import`：外部类型 metadata；常见语义类型优先用 `DateTime`、`JSONValue`、`AnyValue`，跨文件 schema/enum 由 layout 自动解析。
- `__proto_file__` / `__proto_package__` / `__proto_go_package__`：把模型输出到指定 proto 文件，并在引用方自动生成 import。
- 数字枚举会使用 Python enum member name 与数字值；未带前缀的名称会补上 enum 前缀，已带下划线或完整前缀的 proto 风格名称会保持不变。

## CLI

```sh
api-gen generate -c api-blueprint.toml --target grpc.proto
api-gen generate -c api-blueprint.toml --target grpc.go
api-gen generate -c api-blueprint.toml --target grpc.python
api-gen manifest -c api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
```

只需要编译手写 proto 时，使用无 `proto` 的 `grpc-go` / `grpc-python` target。从 Blueprint 生成 proto 时，优先用 `proto_files` 表达布局，用 `field()` 表达稳定字段身份，用 `choice` 表达互斥选择，用通用语义字段类型表达时间、JSON 和任意载荷；`proto_*` metadata 仅作为兼容逃生口。
