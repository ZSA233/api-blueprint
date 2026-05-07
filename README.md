# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

语言: 中文 | [English](README_EN.md)

## 概述

`api-blueprint` 用 Python DSL 定义 API 契约，构建统一 `ContractGraph`，再基于同一份协议真源生成文档服务、Go server、TypeScript client、Kotlin Android client、Wails v2/v3 overlay、gRPC proto/service 定义，以及 protoc-backed Go/Python gRPC stub。

DSL 支持与 RPC 并列的 transport-neutral `STREAM` / `CHANNEL` 长连接消息契约；HTTP 可映射到 SSE / WebSocket，Wails 默认映射到 session-scoped runtime events，`CLOSE(Model)` 会生成 typed close lifecycle payload。

README 只保留上手路径。完整配置、Wails、gRPC、DSL 和 examples 验证说明见 [深入文档](#深入文档)。

## 支持的输出

| 目标 | 状态 | 命令 | 示例 |
|:---|:---:|:---|:---|
| Contract / agent manifest | 可用 | `api-gen` | `api-blueprint.contract.json` / `api-blueprint.agent.json` |
| Go server | 可用 | `api-gen` | `examples/golang` |
| TypeScript client | 预览 | `api-gen` | `examples/typescript` |
| Wails v3 | 实验性 | `api-gen` | `examples/{golang,typescript,wails-harness/v3,wails-hello}` |
| Wails v2 | 预览 | `api-gen` | `examples/{golang,typescript,wails-harness/v2}` |
| Kotlin Android client | 预览 | `api-gen` | `examples/kotlin` |
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

[[targets]]
id = "go.server"
kind = "go-server"
out_dir = "golang"

[[targets]]
id = "typescript.client"
kind = "typescript-client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[targets]]
id = "http"
kind = "http-transport"
server = "go.server"
clients = ["typescript.client"]
```

```sh
api-doc-server -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
```

## 最小配置

下面是常见多目标配置骨架；完整字段见 [配置说明](docs/zh/configuration.md)。

```toml
[blueprint]
entrypoints = ["blueprints.app:*"]

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
id = "http"
kind = "http-transport"
server = "go.server"
clients = ["typescript.client"]

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

[[targets.proto_files]]
file = "api/demo/v1/demo.proto"
package = "example.api.demo.v1"
go_package = "example.com/project/grpc/go/api/demo/v1;demopb"
schema_modules = ["blueprints.api.demo"]
route_paths = ["/api/demo/v1/**"]
service = "DemoService"

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

## 常用命令

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen list-targets -c examples/api-blueprint.toml
api-gen explain-target -c examples/api-blueprint.toml --target go.server
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
- `examples/golang/`、`examples/typescript/`、`examples/kotlin/`、`examples/api-blueprint.{contract,agent}.*`、`examples/api-blueprint.contract.d/`、`examples/grpc/protos/`、`examples/grpc/go/`、`examples/grpc/python/` 是生成快照。
- `examples/wails-hello/` 是独立 Wails v3 hello world 示例，演示不启动 HTTP 服务的 GUI 闭环。
- `gen_*` 文件由生成器拥有，重生成会覆盖。
- `impl_*` 与非 `gen_*` passthrough 文件是用户拥有扩展点，重生成时保留。
- Go / TypeScript 生成物按 `core + transports/<target>` 布局输出；`api-gen generate --target wails.v3` 不生成完整 Wails app shell，external frontend 需先加载 Wails runtime。
- Wails target 的 `include` / `exclude` 会裁剪 target overlay / facade；未选中 route 的 root 不生成 `transports/<overlay_name>`，共享契约层仍完整生成。
- Go `views/providers` 是全局 runtime；按 route 选择 provider 实现可使用 route-scoped provider factory，用户自定义 hook 为 `SelectProvider(spec, handler)`，详见生成器文档。
- `STREAM` / `CHANNEL` 是长连接契约入口；多消息类型生成单个判别联合消息，legacy `WS().RECV().SEND()` 不进入 1.0 主线。
- 默认 HTTP/Wails runtime 只完整支持 `ConnectionScope.SESSION`；`APP` / `TOPIC` 的广播或 topic routing 可通过自定义 connection hub / manager 扩展。
- `examples/golang/views/routes/api/demo/impl.go` 手写了 `STREAM` / `CHANNEL` 最小用法示例，展示 `Open()`、`Send()`、`Recv()`、typed `Close()` 与异常 `Abort()`。
- Go HTTP adapter 会尊重已由 Gin handler 写出的响应，适合少量 HTTP-only raw callback。
- 完整 `contract.json` 会记录 routes、schemas、connections、稳定 hashes、已解析 target plan 和 capability registry；`agent.json`、`agent.md` 与 `contract.d/` 提供 compact 入口、阅读顺序、分片和 target artifact/import 索引，方便 AI agent 先读 compact manifest 再按需深入。
- `[[targets]]` 是统一配置入口；transport target 使用 `kind = "http-transport"` / `kind = "wails-transport"` 并显式声明 `server` 与 `clients`。
- gRPC proto 可由 `grpc-proto` target 从 ContractGraph 输出；`[[targets.proto_files]]` 可把 DSL module/route 映射到 proto file/package/go_package/service。DSL 主线只表达通用契约：`field(1, String(...), optional=True)` 表示稳定字段身份，`choice="..."` 表示互斥选择，`DateTime`、`JSONValue`、`AnyValue` 表示通用语义类型。`grpc-go` / `grpc-python` 也可以省略 `proto` 并直接通过 `source_root` / `files` 编译手写 proto。

## 深入文档

| 主题 | 文档 |
|:---|:---|
| 快速开始 | [docs/zh/getting-started.md](docs/zh/getting-started.md) |
| 配置字段 | [docs/zh/configuration.md](docs/zh/configuration.md) |
| Blueprint DSL | [docs/zh/blueprint-dsl.md](docs/zh/blueprint-dsl.md) |
| Go / TypeScript / Kotlin | [docs/zh/generators.md](docs/zh/generators.md) |
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
