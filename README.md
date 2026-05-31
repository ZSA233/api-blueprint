# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

语言: 中文 | [English](README_EN.md)

## 概述

`api-blueprint` 用 Python DSL 定义 API 契约，再从同一份协议真源生成文档服务和多语言代码。它适合把 HTTP API、`STREAM` / `CHANNEL` 消息、二进制请求 / 响应体、媒体上传 / raw 响应和 gRPC proto 放在一个可检查、可生成、可回归的协议工作流里维护。

核心链路是：

```text
Blueprint DSL -> ContractGraph -> api-gen check / inspect / generate -> generated code
```

## 适合什么场景

- 后端、Web、Flutter、iOS Swift、Kotlin、脚本客户端需要共享同一份 API 契约。
- 希望先从协议生成 Go server，再生成 TypeScript、Flutter、Swift、Kotlin、Java、Go、Python client，或生成 Kotlin/Java/Python server scaffold。
- 需要文档服务、契约检查、生成快照和端到端示例一起维护。
- 需要把 Markdown Binary Schema、typed binary 响应、multipart 上传、raw bytes/file/stream 响应、Wails 或 gRPC 纳入同一套生成流程。

## 安装

稳定安装入口固定指向 GitHub `stable` 分支：

```sh
uv tool install "git+https://github.com/zsa233/api-blueprint@stable"
```

本仓库开发环境使用：

```sh
make
make sync
```

## 30 秒示例

定义一份 Blueprint：

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class PingResponse(Model):
    message = String(description="message")


with bp.group("/demo") as views:
    views.GET("/ping").RSP(PingResponse)
```

`root` 是 URL 前缀；需要把多个顶级 URL namespace 归入同一个生成根时，使用 `Blueprint(name="app", root="")` 并在 `group("/account")`、`group("/room")` 中定义路径。`name` 是 route id、service/module 和生成目录使用的逻辑协议身份。

创建 `api-blueprint.toml`：

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[go.server]]
id = "go.server"
out_dir = "golang/server/views"
module = "example.com/project/golang/server"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[transport.http]]
id = "http"
server = "go.server"
clients = ["typescript.client"]
```

启动文档服务、检查契约并生成代码：

```sh
api-doc-server --version
api-gen --version
api-doc-server -c api-blueprint.toml
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
```

更完整的项目目录、配置字段、DSL、生成器输出、typed error、Response Envelope、Markdown Binary Schema、Wails 和 gRPC 说明见 [快速开始](docs/zh/getting-started.md)、[配置说明](docs/zh/configuration.md) 与下面的专题文档。

## 常用目标

| 目标 | 状态 | 用途 |
|:---|:---:|:---|
| Contract / inspect | 可用 | 输出契约索引，并按 route、schema、error、文件归属查询协议细节 |
| Go server | 可用 | 生成 Go 路由、provider、长连接 message helper、HTTP/Wails adapter、multipart/raw media、binary schema 请求/响应和 runtime |
| TypeScript client | 预览 | 生成 transport-neutral client、长连接 message helper、HTTP multipart/raw adapter、binary schema 响应解码和 Wails facade |
| Flutter client | 预览 | 生成纯 Dart package、DTO、typed error、binary codec、HTTP multipart/raw/binary response client 和 SSE/WebSocket client |
| Swift client | 预览 | 生成 iOS Swift Package 多 target SDK、短 module stem、root routes module、DTO、typed error、字段级 binary codec、带限流/校验 knobs 的共享 URLSession HTTP/SSE/WebSocket transport 和 multipart/raw/binary response client，不生成 UI、鉴权、缓存或 session engine |
| Kotlin client/server | 预览 | 生成 OkHttp HTTP/SSE/WebSocket client、Ktor HTTP/SSE/WebSocket server scaffold、multipart/raw/binary request/response adapter、模型和长连接 message helper |
| Java client/server | 预览 | 生成 Java 17 HttpClient client、Spring MVC/SSE/WebSocket server scaffold、record DTO、HTTP multipart/raw/binary request/response adapter 和长连接 message helper |
| Go client / Python client | 预览 | 生成服务端之外的脚本或工具侧客户端；Python client 使用递归 dataclass DTO、共享 runtime codec，并提供 multipart/raw、长连接 message helper 与 binary writer/response codec |
| Python server | 预览 | 生成 FastAPI HTTP/SSE/WebSocket server scaffold、multipart/raw/binary request/response adapter、typed service contract 和长连接 message helper |
| Wails v2/v3 | 预览 / 实验性 | 生成 Go + TypeScript overlay；文件/stream 等能力使用 Wails RPC descriptor 或 STREAM/CHANNEL chunk 建模 |
| gRPC proto / stubs | 可用 | 从 ContractGraph 输出 proto，并生成 Go/Python stub；bytes/file/stream 使用 protobuf bytes 或 streaming chunk 建模 |

生成物 ownership、单次请求选项、stream/file 路径、server adapter 安全默认和生产逃生通道详见 [生成器与目录布局](docs/zh/generators.md)。默认 adapter 是协议桥接层，不是完整生产运行时；生产项目应优先使用具体 route/client/router 的窄入口，并通过原生 client、custom transport、service implementation、middleware 或 app shell 承载鉴权、限流、cookie、TLS/proxy、重试和文件权限策略。`include` / `exclude` 是稳定的生成期裁剪边界；不 import、不引用或只链接窄 product 属于语言工具链优化，不是跨语言结构体级 dead-strip 契约。

## 下一步

| 主题 | 文档 |
|:---|:---|
| 快速开始 | [docs/zh/getting-started.md](docs/zh/getting-started.md) |
| 配置字段 | [docs/zh/configuration.md](docs/zh/configuration.md) |
| Blueprint DSL | [docs/zh/blueprint-dsl.md](docs/zh/blueprint-dsl.md) |
| Markdown Binary Schema | [docs/zh/binary-schema.md](docs/zh/binary-schema.md) |
| 生成器与目录布局 | [docs/zh/generators.md](docs/zh/generators.md) |
| Wails | [docs/zh/wails.md](docs/zh/wails.md) |
| gRPC | [docs/zh/grpc.md](docs/zh/grpc.md) |
| Examples 验证 | [docs/zh/examples-validation.md](docs/zh/examples-validation.md) |
| Benchmark | [docs/zh/benchmarks.md](docs/zh/benchmarks.md) |
| 发布流程 | [docs/release-process.md](docs/release-process.md) |

## 开发和发布

开发期常用命令：

```sh
make
make test
make example-compile-check
make example-validation
make example-conformance
make benchmark-list
make example-golang-suite
make example-java-suite
```

`make example-conformance` 默认从真实 Go HTTP server 开始跑协议互通；可用 `EXAMPLE_CONFORMANCE_SERVERS`、`EXAMPLE_CONFORMANCE_CLIENTS`、`EXAMPLE_CONFORMANCE_SCENARIOS` 和 `EXAMPLE_CONFORMANCE_SWIFT_RUNTIME_PROFILE` 选择矩阵，完整矩阵可设为 `EXAMPLE_CONFORMANCE_SERVERS=all EXAMPLE_CONFORMANCE_CLIENTS=all`（Swift 场景需要可用 Swift toolchain）。benchmark 是可选趋势工具，不作为默认 CI 阈值；除 binary / protocol 外，也提供 generated client SDK smoke 与 Swift runtime microbench 入口，见 [Benchmark](docs/zh/benchmarks.md)。`example-golang-suite` 和 `example-java-suite` 是保留的手动端到端增强验证。正式发布前的版本、构建、安装和 GitHub Release 流程见 [发布流程](docs/release-process.md)。
