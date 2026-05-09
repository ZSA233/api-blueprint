# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

语言: 中文 | [English](README_EN.md)

## 概述

`api-blueprint` 用 Python DSL 定义 API 契约，构建统一 `ContractGraph`，再基于同一份协议真源和共享 target planner 生成文档服务、Go server/client、TypeScript client、Kotlin Android client、Python client/server、Wails v2/v3 overlay、gRPC proto/service 定义，以及 protoc-backed Go/Python gRPC stub。

DSL 支持与 RPC 并列的 transport-neutral `STREAM` / `CHANNEL` 长连接消息契约；HTTP 可映射到 SSE / WebSocket，Wails 默认映射到带 client-allocated `session_id` 握手的 session-scoped runtime events，`CLOSE(Model)` 会生成 typed close lifecycle payload。

长连接 route 还支持 `ConnectionDelivery`：默认 `ordered`。HTTP 下的 ordered 直接依赖 SSE / WebSocket 单连接顺序，不额外叠加 seq/reorder 机制；Wails ordered 路由才会补 transport-level 保序，并在遇到不可恢复的缺帧、协议错误或缓冲溢出时通过结构化 `onClose` fail-fast 暴露，是否 reopen 由业务决定。仅高频 telemetry 一类场景才建议显式切到 `unordered`；该选项当前主要影响 Wails transport。

README 只保留上手路径。完整配置、Wails、gRPC、DSL 和 examples 验证说明见 [深入文档](#深入文档)。

## 支持的输出

| 目标 | 状态 | 命令 | 示例 |
|:---|:---:|:---|:---|
| Inspect / contract index | 可用 | `api-gen` | `api-gen inspect` / `api-blueprint.index.json` |
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

`api-doc-server` 会在启动后额外打印实际入口地址；如果 `[blueprint].docs_server` 使用 `host:0`，输出会显示系统分配的真实端口，而不是 `:0`。

生成器扩展点、文件 ownership 与目录布局见 [生成器说明](docs/zh/generators.md)。

## 最小配置

下面是常见多目标配置骨架；完整字段见 [配置说明](docs/zh/configuration.md)。

```toml
[blueprint]
entrypoints = ["blueprints.app:*"]

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
api-gen inspect route api.demo.post.testpost api.demo.channel.assistantsession -c examples/api-blueprint.toml
api-gen inspect files -c examples/api-blueprint.toml --route api.demo.post.testpost --route api.demo.channel.assistantsession --target go.server
api-gen inspect schema ApiDemoA RSP_TestPost -c examples/api-blueprint.toml
api-gen inspect errors -c examples/api-blueprint.toml --route api.demo.post.testpost --route api.demo.channel.assistantsession
api-gen manifest -c examples/api-blueprint.toml --out api-blueprint.index.json
api-gen manifest -c examples/api-blueprint.toml --profile full --out api-blueprint.contract.json
api-gen manifest -c examples/api-blueprint.toml --profile agent --out api-blueprint.agent.json
api-gen manifest -c examples/api-blueprint.toml --shards-dir api-blueprint.contract.d
api-gen check -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml --target wails.v3
api-gen diff old.contract.json new.contract.json
```

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
