# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

语言: 中文 | [English](README_EN.md)

## 概述

`api-blueprint` 用 Python DSL 定义 API 契约，构建统一 `ContractGraph`，再基于同一份协议真源和共享 target planner 生成文档服务、Go server/client、TypeScript client、Kotlin Android client、Python client/server、Wails v2/v3 overlay、gRPC proto/service 定义，以及 protoc-backed Go/Python gRPC stub。

DSL 支持与 RPC 并列的 transport-neutral `STREAM` / `CHANNEL` 长连接消息契约；HTTP 可映射到 SSE / WebSocket，Wails 默认映射到 session-scoped runtime events，`CLOSE(Model)` 会生成 typed close lifecycle payload。

README 只保留上手路径。完整配置、Wails、gRPC、DSL 和 examples 验证说明见 [深入文档](#深入文档)。

## 支持的输出

| 目标 | 状态 | 命令 | 示例 |
|:---|:---:|:---|:---|
| Inspect / contract manifest | 可用 | `api-gen` | `api-gen inspect` / `api-blueprint.contract.json` |
| Go server | 可用 | `api-gen` | `examples/golang/server` |
| Go client | 预览 | `api-gen` | `examples/golang/client` |
| TypeScript client | 预览 | `api-gen` | `examples/typescript` |
| Wails v3 | 实验性 | `api-gen` | `examples/{golang/server,typescript,wails-harness/v3,wails-hello}` |
| Wails v2 | 预览 | `api-gen` | `examples/{golang/server,typescript,wails-harness/v2}` |
| Kotlin Android client | 预览 | `api-gen` | `examples/kotlin` |
| Python client/server | 预览 | `api-gen` | `python_package_root` package layout |
| gRPC proto | 可用 | `api-gen` | `examples/grpc/protos` |
| gRPC Go/Python stubs | 可用 | `api-gen` | `examples/grpc/{go,python}` |


## 安装

稳定安装入口固定指向 GitHub `stable` 分支：

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

## 快速开始

定义一份 Blueprint：

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class HelloResponse(Model):
    message = String(description="message")


with bp.group("/demo") as views:
    views.GET("/hello").RSP(HelloResponse)
```

创建最小配置并生成代码：

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[go.server]]
id = "go.server"
out_dir = "golang"

[[go.client]]
id = "go.client"
out_dir = "golang-client"
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
```

```sh
api-doc-server -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
```

TypeScript、Kotlin、Python client 的 `base_url` / `base_url_expr` 由 HTTP transport adapter / factory 使用；共享 route/runtime client 保持 transport-neutral。

## 最小配置

下面是常见多目标配置骨架；完整字段见 [配置说明](docs/zh/configuration.md)。

```toml
[blueprint]
entrypoints = ["blueprints.app:*"]

[[targets]]
id = "contract"
kind = "contract"
out_dir = "."
formats = ["json"]

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

[[transport.http]]
id = "http"
server = "go.server"
clients = ["go.client", "typescript.client"]

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

## 常用命令

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen list-targets -c examples/api-blueprint.toml
api-gen explain-target -c examples/api-blueprint.toml --target go.server
api-gen inspect routes -c examples/api-blueprint.toml
api-gen inspect route api.demo.post.testpost -c examples/api-blueprint.toml
api-gen inspect files -c examples/api-blueprint.toml --route api.demo.post.testpost --target go.server
api-gen inspect schema ApiDemoA -c examples/api-blueprint.toml
api-gen inspect errors -c examples/api-blueprint.toml --route api.demo.post.testpost
api-gen manifest -c examples/api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen manifest -c examples/api-blueprint.toml --profile agent --out api-blueprint.agent.json
api-gen manifest -c examples/api-blueprint.toml --shards-dir api-blueprint.contract.d
api-gen check -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml --target wails.v3
api-gen diff old.contract.json new.contract.json
```

## 生成产物与用户文件

- `examples/blueprints/` 是示例 Blueprint 真源。
- `examples/blueprints/api_demo.py` 包含 `STREAM` / `CHANNEL` 长连接示例。
- `examples/golang/server/`、`examples/golang/client/`、`examples/typescript/`、`examples/kotlin/`、`examples/api-blueprint.{contract,agent}.*`、`examples/api-blueprint.contract.d/`、`examples/grpc/protos/`、`examples/grpc/go/`、`examples/grpc/python/` 是生成快照。
- `examples/wails-hello/` 是独立 Wails v3 hello world 示例，演示不启动 HTTP 服务的 GUI 闭环。
- Go / TypeScript / Python 的 `gen_*` 文件由生成器拥有，重生成会覆盖；Kotlin 的 `Gen*.kt` 文件由生成器拥有并带 generated header。
- `impl_*`、Python `client.py` / `service.py`、Kotlin 非 `Gen*` façade/extension 文件是用户拥有扩展点，重生成时保留。
- Go server 的 `out_dir` 是生成包根，不再隐式追加 `views`；示例使用 `golang/server/views`，因此 server 产物位于 `views/routes`、`views/providers`、`views/runtime/errors`、`views/transports`。Go client 生成物按 `runtime`、`routes/<root>/<group...>`、`transports/http` 输出，`base_url` 只属于 HTTP transport config；Kotlin 使用 `<package>/<root>/runtime`、`<package>/<root>/routes/<root>/<group...>`、`<package>/<root>/transports/http` 新布局，旧 `<package>/ApiClient.kt`、`endpoints/`、`models/`、`internal/` 布局已破坏性变更。
- Python client/server 使用 `python_package_root` 包根；route 输出完整镜像 path，例如 `routes/api/demo`，root-level route 位于 `routes/api`，不再使用 `routes/root`；client 是 async-first HTTP client，server 输出 route service contracts/stubs 与 FastAPI HTTP adapter scaffold。
- `api-gen check` 与 writer 共享 planner / capability metadata；contract / agent artifacts 的 target 文件索引会指向 Kotlin / Python 新的完整 route path 输出路径。
- `api-gen generate --target wails.v3` 不生成完整 Wails app shell，external frontend 需先加载 Wails runtime；Wails target 仍只组合 Go server 与 TypeScript client。
- Wails target 的 `include` / `exclude` 会裁剪 target overlay / facade；未选中 route 的 root 不生成 `transports/<overlay_name>`，共享契约层仍完整生成。
- Go `providers` 是生成包根下的全局 runtime；按 route 选择 provider 实现可使用 route-scoped provider factory，用户自定义 hook 为 `SelectProvider(spec, handler)`，详见生成器文档。
- `STREAM` / `CHANNEL` 是长连接契约入口；多消息类型生成单个判别联合消息，legacy `WS().RECV().SEND()` 不进入 1.0 主线。
- 默认 HTTP/Wails runtime 只完整支持 `ConnectionScope.SESSION`；`APP` / `TOPIC` 的广播或 topic routing 可通过自定义 connection hub / manager 扩展。
- `examples/golang/server/views/routes/api/demo/impl.go` 手写了 `STREAM` / `CHANNEL` 最小用法示例，展示 `Open()`、`Send()`、`Recv()`、typed `Close()` 与异常 `Abort()`。
- Go HTTP adapter 会尊重已由 Gin handler 写出的响应，适合少量 HTTP-only raw callback。
- AI agent 与人类维护者应优先使用 `api-gen inspect routes/route/files/schema/errors` 按需查询 ContractGraph；`contract.json`、`agent.json`、`agent.md` 与 `contract.d/` 主要用于离线快照、归档和 diff。完整 `contract.json` 会记录 routes、schemas、connections、error catalog、稳定 hashes、已解析 target plan 和 capability registry；agent/shards 提供 compact 入口、阅读顺序、分片和 target artifact/import 索引。
- ContractGraph 会把 `Blueprint(errors=...)` 和 route `.ERR(...)` 收束为 language-agnostic error catalog，并为每个错误输出 `message` 与 `toast.key/default/level`。生成代码不内置多语言表；业务 i18n 通过 toast key 解析当前语言，客户端 helper 按 `toast.text`、外部 i18n、`toast.default`、`message` 的顺序兜底。Go client、TypeScript、Kotlin、Python client/server 会把 runtime 错误类型/helper 与静态 catalog 数据拆到独立 generated 文件；Go server 只生成 runtime 类型和分组错误值，避免 root catalog 与分组错误值重复。业务 wrapper code 不会被默认转换成异常。
- `[[targets]]` 是 canonical 配置入口；也可以使用 `[[go.server]]`、`[[go.client]]`、`[[python.server]]`、`[[transport.http]]`、`[[grpc.proto]]`、`[[grpc.go]]`、`[[grpc.python]]` 等快捷表，加载时会 normalize 成 targets。快捷表中的 Python `module` 映射到 `python_package_root`，Kotlin `module` 映射到 `package`，`[[grpc.python]] module` 同样映射到 `python_package_root`。
- gRPC proto 可由 `grpc-proto` target 从 ContractGraph 输出；`[[targets.proto_files]]` 或快捷表 `[[grpc.proto.proto_files]]` 可把 DSL module/route 映射到 proto file/package/go_package/service。DSL 主线只表达通用契约：`field(1, String(...), optional=True)` 表示稳定字段身份，`choice="..."` 表示互斥选择，`DateTime`、`JSONValue`、`AnyValue` 表示通用语义类型。`grpc-go` / `grpc-python` 也可以省略 `proto` 并直接通过 `source_root` / `files` 编译手写 proto。

## 深入文档

| 主题 | 文档 |
|:---|:---|
| 快速开始 | [docs/zh/getting-started.md](docs/zh/getting-started.md) |
| 配置字段 | [docs/zh/configuration.md](docs/zh/configuration.md) |
| Blueprint DSL | [docs/zh/blueprint-dsl.md](docs/zh/blueprint-dsl.md) |
| Go / TypeScript / Kotlin / Python | [docs/zh/generators.md](docs/zh/generators.md) |
| Wails | [docs/zh/wails.md](docs/zh/wails.md) |
| gRPC | [docs/zh/grpc.md](docs/zh/grpc.md) |
| Examples 验证 | [docs/zh/examples-validation.md](docs/zh/examples-validation.md) |
| 发布流程 | [docs/release-process.md](docs/release-process.md) |

## 开发

```sh
make sync
make test
make example-compile-check
make example-refresh
make example-validation
make wails-hello-dev
make wails-hello-check
```

`example-compile-check` 适合开发期验证，`example-refresh` 用于接受预期生成变化，`example-validation` 用于严格确认 snapshots 收敛。`wails-hello-dev` 会重生成 hello overlay 并启动 Wails v3 GUI；`wails-hello-check` 只严格验证独立 hello 示例。

## 发布

详细发布规范见 [docs/release-process.md](docs/release-process.md)。

```sh
make release-version-show
make release-preflight RELEASE_TAG=v1.0.0
make release-local RELEASE_TAG=v1.0.0
make release-install-check RELEASE_TAG=v1.0.0
```
