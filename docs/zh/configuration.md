# 配置说明

`api-blueprint.toml` 是文档服务和统一生成器的主配置文件。vNext 主线只使用 `Blueprint -> ContractGraph -> [[targets]]`。

## blueprint

```toml
[blueprint]
docs_server = "0.0.0.0:2332"
docs_domain = ""
entrypoints = ["blueprints.app:*"]
```

- `docs_server`：`api-doc-server` 监听地址。
- `docs_domain`：文档服务展示域名，可留空。
- `entrypoints`：需要加载的 Python 对象，支持 `module.path:attribute` 和 `module.path:*`。

`Blueprint(app=None)` 默认共享全局 FastAPI app。如果需要多个独立文档应用，应显式传入 `app`。

## targets

```toml
[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["json", "markdown"]

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"
module = "example.com/project/golang"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[targets]]
id = "kotlin.client"
kind = "kotlin-client"
out_dir = "kotlin"
package = "com.example.apiblueprint"

[[targets]]
id = "http"
kind = "http-transport"
server = "go.server"
clients = ["typescript.client", "kotlin.client"]

[[targets]]
id = "wails.v3"
kind = "wails-transport"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"

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

公共字段：

- `id`：target 唯一标识，供依赖和 `--target` 使用。
- `kind`：target 类型。
- `out_dir`：生成目录；transport target 通常不需要。

核心 target：

- `contract`：输出 `api-blueprint.contract.json` 和 / 或 `api-blueprint.contract.md`。
- `go-server`：生成 Go 服务端 core；Go client 本轮只预留 `go-client` target。
- `typescript-client`：生成只依赖 `ApiTransport` 的 TypeScript client core；`base_url` / `base_url_expr` 由 transport facade 注入。
- `kotlin-client`：首轮只支持 HTTP JSON RPC；`STREAM` / `CHANNEL`、form、binary、自定义 wrapper 会在 `api-gen check` 阶段失败。
- `grpc-proto`：从 ContractGraph 输出 `.proto` 和 service 定义。
- `grpc-go`：消费同配置内的 `grpc-proto` target，调用 `protoc` / `protoc-gen-go` / `protoc-gen-go-grpc` 生成 Go protobuf/gRPC stub。
- `grpc-python`：消费同配置内的 `grpc-proto` target，调用 `grpcio-tools` 生成 Python protobuf/gRPC stub；`python_package_root` 会把生成物放入指定包根并重写生成 import。

gRPC stub target 字段：

- `proto`：必须引用一个 `grpc-proto` target。
- `files`：相对 proto target `out_dir` 的 glob 列表，例如 `api/**/*.proto`。
- `source_root`：可选；让 `files` 相对此目录匹配，并把它作为 `protoc` 工作目录。省略时使用 proto target `out_dir`。迁移旧 proto 树时可设为 `grpc/protos/services/...` 来裁剪输出路径。
- `import_roots`：额外 proto include roots；proto target `out_dir` 会自动加入。
- `module`：`grpc-go` 可选；设置后使用 Go import path 输出模式，并按 `option go_package` 分目录输出。
- `python_package_root`：仅 `grpc-python` 使用，例如 `pb` 或 `generated.pb`。

transport target：

- `http-transport`：声明 HTTP server/client 组合。
- `wails-transport`：声明 Wails overlay，必须设置 `version`、`server` 和 `clients`。
- `frontend_mode = "external"` 生成外部前端使用的 Wails TypeScript facade；`none` 只生成 Go overlay。
- `include` / `exclude` 可裁剪 Wails target overlay / facade。

预留 target：

- `python-server`
- `python-client`
- `go-client`

这些 target 当前只进入 schema 和 capability registry，不生成业务代码。

## CLI

```sh
api-gen list-targets -c api-blueprint.toml
api-gen explain-target -c api-blueprint.toml --target go.server
api-gen manifest -c api-blueprint.toml --out api-blueprint.contract.json
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
api-gen generate -c api-blueprint.toml --target wails.v3
```

`api-gen manifest` 输出 routes、schemas、connections、稳定 hashes、已解析 target plan 和 capability registry；`api-gen check` 会先构建 ContractGraph，再做 target dependency 和 capability 校验。生成前失败比生成半套代码更容易维护。
