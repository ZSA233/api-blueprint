# 配置说明

`api-blueprint.toml` 是文档服务和统一生成器的主配置文件。1.0 主线只使用 `Blueprint -> ContractGraph -> [[targets]]`。

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
formats = ["json", "markdown", "agent-json", "agent-markdown", "shards"]

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
id = "python.server"
kind = "python-server"
out_dir = "python/server"
python_package_root = "api_blueprint_example_server"

[[targets]]
id = "python.client"
kind = "python-client"
out_dir = "python/client"
python_package_root = "api_blueprint_example_client"
base_url = "http://localhost:2333"

[[targets]]
id = "http"
kind = "http-transport"
server = "go.server"
clients = ["typescript.client", "kotlin.client", "python.client"]

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

- `contract`：输出 `api-blueprint.contract.json`、`api-blueprint.contract.md`、`api-blueprint.agent.json`、`api-blueprint.agent.md` 和 / 或 `api-blueprint.contract.d/` shards。
- `go-server`：生成 Go 服务端 core；Go client 本轮只预留 `go-client` target。
- `typescript-client`：生成只依赖 `ApiTransport` 的 TypeScript client core；`base_url` / `base_url_expr` 由 transport facade 注入。
- `kotlin-client`：生成 OkHttp + kotlinx.serialization Android client；通过共享 transport abstraction 生成 RPC、legacy WS、STREAM、CHANNEL route surface，支持 query/json/form/binary/open request kind，以及 none/general/custom response wrapper。`base_url` / `base_url_expr` 由生成的 OkHttp HTTP adapter config 使用，route/runtime client 保持 transport-neutral。内置 OkHttp adapter 以 RPC 为主，长连接 bridge 属于 preview/custom transport surface。
- `python-server`：生成 Python route service contracts/stubs 与 FastAPI HTTP adapter scaffold；使用 `python_package_root` 控制生成包根。
- `python-client`：生成 async-first Python HTTP client；使用 `python_package_root` 控制生成包根，`base_url` / `base_url_expr` 由 HTTP transport adapter 使用。默认 httpx adapter 实现 RPC 请求，WS/STREAM/CHANNEL 连接 transport 是 preview/custom 扩展点。
- `grpc-proto`：从 ContractGraph 输出 `.proto` 和 service 定义；可通过 `[[targets.proto_files]]` 把 DSL schema module/name 与 route path/id/service 映射到指定 proto file/package/go_package/service。
- `grpc-go`：消费同配置内的 `grpc-proto` target，或直接消费手写 proto，调用 `protoc` / `protoc-gen-go` / `protoc-gen-go-grpc` 生成 Go protobuf/gRPC stub。
- `grpc-python`：消费同配置内的 `grpc-proto` target，或直接消费手写 proto，调用 `grpcio-tools` 生成 Python protobuf/gRPC stub；`python_package_root` 会把生成物放入指定包根并重写生成 import。

Kotlin / Python client/server、`api-gen check` 和 contract / agent artifact projection 使用同一份 planner / capability metadata。若 target capability 不支持某个 route、request kind 或 wrapper，应在生成前失败，而不是生成半套产物。

Kotlin client 输出目录是 `<package>/<root>/runtime/*`、`<package>/<root>/routes/<root>/<group...>/*`、`<package>/<root>/transports/http/*`。`Gen*.kt` 文件由生成器拥有；非 `Gen*` façade / extension 文件由用户拥有。这是相对旧 `<package>/ApiClient.kt`、`endpoints/`、`models/`、`internal/` 的破坏性布局变更。

Python client/server 输出目录是 `<python_package_root>/<root>/runtime/*`、`<python_package_root>/<root>/routes/<root>/<group...>/*`、`<python_package_root>/<root>/transports/http/*`。root-level route 生成在 `routes/<root>`，不生成 `routes/root`。如果省略 `python_package_root`，生成器使用默认包根。

gRPC stub target 字段：

- `proto`：可选；引用一个 `grpc-proto` target 时会先生成 proto 再生成 stub。
- `source_root`：当省略 `proto` 时必填，用来直接编译手写 proto；设置后 `files` 相对此目录匹配，并把它作为 `protoc` 工作目录。
- `files`：相对 proto target `out_dir` 或 `source_root` 的 glob 列表，例如 `api/**/*.proto`。
- `import_roots`：额外 proto include roots；proto target `out_dir` 会自动加入。
- `module`：`grpc-go` 可选；设置后使用 Go import path 输出模式，并按 `option go_package` 分目录输出。
- `python_package_root`：`python-client` / `python-server` / `grpc-python` 使用，例如 `api_client`、`generated.server`、`pb` 或 `generated.pb`。
- `proto_files`：仅 `grpc-proto` 使用；每条规则支持 `file`、`package`、`go_package`、`schema_modules`、`schema_names`、`route_paths`、`route_ids`、`service_ids`、`service`。

transport target：

- `http-transport`：声明 HTTP server/client 组合；`server` 可引用 `go-server` 或 `python-server`，`clients` 可引用 TypeScript、Kotlin 或 Python client。
- `wails-transport`：声明 Wails overlay，必须设置 `version`、`server` 和 `clients`；Wails 保持 Go + TypeScript only，不接入 Kotlin / Python client。
- `frontend_mode = "external"` 生成外部前端使用的 Wails TypeScript facade；`none` 只生成 Go overlay。
- `include` / `exclude` 可裁剪 Wails target overlay / facade。

预留 target：

- `go-client`

该 target 当前只进入 schema 和 capability registry，不生成业务代码。

## CLI

```sh
api-gen list-targets -c api-blueprint.toml
api-gen explain-target -c api-blueprint.toml --target go.server
api-gen manifest -c api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen manifest -c api-blueprint.toml --profile agent --out api-blueprint.agent.json
api-gen manifest -c api-blueprint.toml --shards-dir api-blueprint.contract.d
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
api-gen generate -c api-blueprint.toml --target wails.v3
```

`api-gen manifest --profile full` 输出完整 manifest；`--profile agent` 输出 compact agent manifest；`--shards-dir` 输出按 service / route / schema 拆分的 shards。`manifest.version` 是 manifest schema 兼容版本，例如 `1.0`；`manifest.generator.version` 来自包版本真源。`api-gen check` 会先构建 ContractGraph，再使用共享 planner / capability metadata 做 target dependency、route、request kind 和 wrapper 校验。生成前失败比生成半套代码更容易维护。
