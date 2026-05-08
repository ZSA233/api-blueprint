# 配置说明

`api-blueprint.toml` 是文档服务和统一生成器的主配置文件。1.0 主线使用 `Blueprint -> ContractGraph -> targets`；`[[targets]]` 是 canonical 入口，`[[contract]]`、`[[go.server]]`、`[[go.client]]`、`[[python.server]]`、`[[transport.http]]`、`[[grpc.proto]]`、`[[grpc.go]]` 等快捷表会在加载时 normalize 成同一个 target 列表。

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
[[contract]]
id = "contract"
out_dir = "."

[[go.server]]
id = "go.server"
out_dir = "golang/server/views"
module = "example.com/project/golang/server"

[[go.client]]
id = "go.client"
out_dir = "golang/client"
module = "example.com/project/golang/client"
base_url = "http://localhost:2333"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[kotlin.client]]
id = "kotlin.client"
out_dir = "kotlin"
module = "com.example.apiblueprint"

[[python.server]]
id = "python.server"
out_dir = "python/server"
module = "api_blueprint_example_server"

[[python.client]]
id = "python.client"
out_dir = "python/client"
module = "api_blueprint_example_client"
base_url = "http://localhost:2333"

[[transport.http]]
id = "http"
server = "go.server"
clients = ["go.client", "typescript.client", "kotlin.client", "python.client"]

[[transport.wails]]
id = "wails.v3"
version = "v3"
server = "go.server"
clients = ["typescript.client"]
frontend_mode = "external"

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

公共字段：

- `id`：target 唯一标识，供依赖和 `--target` 使用。
- `kind`：target 类型。
- `out_dir`：生成目录；Go server 中它就是生成包根，不再隐式追加 `views`；transport target 通常不需要。

快捷表会推导 `kind`，因此不允许手写 `kind`。`id` 仍必填。快捷表中的 Go `module` 保持 Go module；Python `module` 会映射到 `python_package_root`；Kotlin `module` 会映射到 `package`，也可以继续写显式 `package`；`[[grpc.python]] module` 同样映射到 `python_package_root`。

核心 target：

- `contract`：省略 `formats` 时默认只输出轻量 `api-blueprint.index.json`，用于 AI agent 和人工维护者离线获得 service / route / target 目录以及推荐 `api-gen inspect` 查询命令；它不内联 schema、error catalog、route artifact 或 shard 明细。`formats = ["json"]` 才输出完整 `api-blueprint.contract.json`，用于 diff、归档或兜底全量检查；`markdown`、`agent-*` 与 `shards` 适合离线导航包、归档或需要分片快照时开启。
- `go-server`：生成 Go 服务端 core。`out_dir` 是包根；route/provider/transport/error 产物分别位于 `routes`、`providers`、`transports`、`runtime/errors`，如果需要包路径包含 `/views`，应显式把 `out_dir` 写成 `.../views`。
- `go-client`：生成 preview Go client；RPC/query/json/form/binary HTTP 调用可用，legacy WS / STREAM / CHANNEL 生成 transport-neutral surface，默认 HTTP adapter 返回明确 unsupported error，便于项目替换自定义 transport。
- `typescript-client`：生成只依赖 `ApiTransport` 的 TypeScript client core；`base_url` / `base_url_expr` 由 transport facade 注入。
- `kotlin-client`：生成 OkHttp + kotlinx.serialization Android client；通过共享 transport abstraction 生成 RPC、legacy WS、STREAM、CHANNEL route surface，支持 query/json/form/binary/open request kind，以及 none/general/custom response wrapper。`base_url` / `base_url_expr` 由生成的 OkHttp HTTP adapter config 使用，route/runtime client 保持 transport-neutral。内置 OkHttp adapter 以 RPC 为主，长连接 bridge 属于 preview/custom transport surface。
- `python-server`：生成 Python route service contracts/stubs 与 FastAPI HTTP adapter scaffold；使用 `python_package_root` 控制生成包根。
- `python-client`：生成 async-first Python HTTP client；使用 `python_package_root` 控制生成包根，`base_url` / `base_url_expr` 由 HTTP transport adapter 使用。默认 httpx adapter 实现 RPC 请求，WS/STREAM/CHANNEL 连接 transport 是 preview/custom 扩展点。
- `grpc-proto`：从 ContractGraph 输出 `.proto` 和 service 定义；可通过 `[[targets.proto_files]]` 或快捷表 `[[grpc.proto.proto_files]]` 把 DSL schema module/name 与 route path/id/service 映射到指定 proto file/package/go_package/service。
- `grpc-go`：消费同配置内的 `grpc-proto` target，或直接消费手写 proto，调用 `protoc` / `protoc-gen-go` / `protoc-gen-go-grpc` 生成 Go protobuf/gRPC stub。
- `grpc-python`：消费同配置内的 `grpc-proto` target，或直接消费手写 proto，调用 `grpcio-tools` 生成 Python protobuf/gRPC stub；`python_package_root` 会把生成物放入指定包根并重写生成 import。

Kotlin / Python client/server、`api-gen check` 和 contract / agent artifact projection 使用同一份 planner / capability metadata。若 target capability 不支持某个 route、request kind 或 wrapper，应在生成前失败，而不是生成半套产物。

ContractGraph 会从 `Blueprint(errors=...)` 和 route `.ERR(...)` 收集语言无关 error catalog。每个错误包含协议级 `message` 与用户展示层 `toast.key/default/level`；生成器只输出这些稳定字段，不生成内置多语言表。业务 i18n 系统按 toast key 取当前语言，客户端 helper 按 `toast.text`、外部 i18n、`toast.default`、`message` 兜底。各主生成器会输出 typed error constants/catalog；Go server 的业务 error 实现位于 `runtime/errors`，Go client、TypeScript、Kotlin、Python client/server 在 runtime 中输出对应 catalog。业务错误码不默认等价于 HTTP status，也不会默认把 wrapper code 转成异常。

Kotlin client 输出目录是 `<package>/<root>/runtime/*`、`<package>/<root>/routes/<root>/<group...>/*`、`<package>/<root>/transports/http/*`。`Gen*.kt` 文件由生成器拥有；非 `Gen*` façade / extension 文件由用户拥有。这是相对旧 `<package>/ApiClient.kt`、`endpoints/`、`models/`、`internal/` 的破坏性布局变更。

Go client 输出目录是 `runtime/*`、`routes/<root>/<group...>/*`、`transports/http/*`。`gen_*.go` 由生成器拥有，`client.go` façade 由用户拥有并在重生成时保留。`base_url` / `base_url_expr` 只进入 HTTP transport config，不进入 route/runtime client。

Python client/server 输出目录是 `<python_package_root>/<root>/runtime/*`、`<python_package_root>/<root>/routes/<root>/<group...>/*`、`<python_package_root>/<root>/transports/http/*`。root-level route 生成在 `routes/<root>`，不生成 `routes/root`。如果省略 `python_package_root`，生成器使用默认包根。

gRPC stub target 字段：

- `proto`：可选；引用一个 `grpc-proto` target 时会先生成 proto 再生成 stub。
- `source_root`：当省略 `proto` 时必填，用来直接编译手写 proto；设置后 `files` 相对此目录匹配，并把它作为 `protoc` 工作目录。
- `files`：相对 proto target `out_dir` 或 `source_root` 的 glob 列表，例如 `api/**/*.proto`。
- `import_roots`：额外 proto include roots；proto target `out_dir` 会自动加入。
- `module`：`grpc-go` 可选；设置后使用 Go import path 输出模式，并按 `option go_package` 分目录输出。
- `python_package_root`：`python-client` / `python-server` / `grpc-python` 使用，例如 `api_client`、`generated.server`、`pb` 或 `generated.pb`；快捷表里可写 `module`。
- `proto_files`：仅 `grpc-proto` 使用；每条规则支持 `file`、`package`、`go_package`、`schema_modules`、`schema_names`、`route_paths`、`route_ids`、`service_ids`、`service`；快捷表写作 `[[grpc.proto.proto_files]]`。

transport target：

- `http-transport`：声明 HTTP server/client 组合；`server` 可引用 `go-server` 或 `python-server`，`clients` 可引用 Go、TypeScript、Kotlin 或 Python client。
- `wails-transport`：声明 Wails overlay，必须设置 `version`、`server` 和 `clients`；Wails 保持 Go + TypeScript only，不接入 Kotlin / Python client。
- `frontend_mode = "external"` 生成外部前端使用的 Wails TypeScript facade；`none` 只生成 Go overlay。
- `include` / `exclude` 可裁剪 Wails target overlay / facade。

## CLI

```sh
api-gen list-targets -c api-blueprint.toml
api-gen explain-target -c api-blueprint.toml --target go.server
api-gen inspect routes -c api-blueprint.toml
api-gen inspect route api.demo.post.testpost api.demo.channel.assistantsession -c api-blueprint.toml
api-gen inspect files -c api-blueprint.toml --route api.demo.post.testpost --route api.demo.channel.assistantsession --target go.server
api-gen inspect schema ApiDemoA RSP_TestPost -c api-blueprint.toml
api-gen inspect errors -c api-blueprint.toml --route api.demo.post.testpost --route api.demo.channel.assistantsession
api-gen manifest -c api-blueprint.toml --out api-blueprint.index.json
api-gen manifest -c api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen manifest -c api-blueprint.toml --profile agent --out api-blueprint.agent.json
api-gen manifest -c api-blueprint.toml --shards-dir api-blueprint.contract.d
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
api-gen generate -c api-blueprint.toml --target wails.v3
```

`api-gen inspect` 直接从配置加载 Blueprint 并构建 ContractGraph，适合按 route、schema、error 或 target 文件索引查询，不需要先生成 `contract.d` 或打开生成代码。`route` / `schema` 子命令可一次传多个查询，`files` / `errors` 可重复 `--route`，便于 agent 在一次命令中拿到一组相关接口的细节。`inspect` 只返回 live ContractGraph 查询结果，不暗示 shard 文件存在，也不会返回默认 shard 路径；需要离线 shard 导航时，应显式生成 `api-blueprint.agent.json` 或 `api-blueprint.contract.d`。`api-gen explain-target` 输出 effective target summary，而不是原始 TOML 片段；它会显示当前 target kind 的关键字段和关键生效值，例如 contract target 省略 `formats` 时仍会显示 `formats = ["index"]`，Wails target 会显示 `version`、`overlay_name`、`frontend_mode`、`include`、`exclude`。`api-gen manifest` 默认输出只含目录的轻量 index；`--profile full` 输出完整 manifest；`--profile agent` 输出 compact agent manifest；`--shards-dir` 输出按 service / route / schema 拆分的 shards。`manifest.version` 是 manifest schema 兼容版本，例如 `1.0`；`manifest.generator.version` 来自包版本真源。`api-gen check` 会先构建 ContractGraph，再使用共享 planner / capability metadata 做 target dependency、route、request kind 和 wrapper 校验。生成前失败比生成半套代码更容易维护。
