# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

语言: 中文 | [English](README_EN.md)

## 概述

`api-blueprint` 用 Python DSL 定义 API 契约，并从同一份协议真源生成文档服务、契约索引和多语言代码。

它把 HTTP API、`STREAM` / `CHANNEL` 消息、二进制协议、媒体上传、raw 响应、Wails 和 gRPC 放进一个可检查、可生成、可回归的工作流。

```text
Blueprint DSL -> ContractGraph -> api-gen check / inspect / generate -> generated code
```

## 适合什么场景

- 多端团队需要共享同一份 API 契约。
- 希望从协议真源生成 server scaffold、client SDK、文档和测试快照。
- 需要把历史接口的 JSON shape 漂移、typed error、binary schema、stream/channel 等能力纳入契约。
- 想让 AI 或人工审查优先阅读契约索引，而不是直接翻生成物。

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
api-doc-server -c api-blueprint.toml
api-gen check -c api-blueprint.toml
api-gen generate -c api-blueprint.toml
```

默认 `/` 与 `/docs` 都是 api-blueprint 文档中心；完整 OpenAPI 保留在 `/openapi.json`，消息协议可通过支持 interaction 关联的 `/docs/protocol` 与 `/docs/asyncapi` 查看。

## 常用目标

| 目标 | 状态 | 用途 |
|:---|:---:|:---|
| Contract / inspect | 可用 | 输出和查询协议索引 |
| Go server | 可用 | 生成 Go provider、HTTP/Wails adapter 与 server-side DTO |
| Go client / Python client | 预览 | 生成脚本、工具或服务侧客户端 |
| TypeScript client | 预览 | 生成 transport-neutral client 与 HTTP/Wails facade |
| Flutter client | 预览 | 生成纯 Dart package 与 HTTP/SSE/WebSocket client |
| Swift client | 预览 | 生成 Swift Package SDK |
| Kotlin client/server | 预览 | 生成 OkHttp client 与 Ktor server scaffold |
| Java client/server | 预览 | 生成 Java HttpClient client 与 Spring MVC contract entrypoints |
| Python server | 预览 | 生成 FastAPI server scaffold |
| Wails v2/v3 | 预览 / 实验性 | 生成 Go + TypeScript overlay |
| gRPC proto / stubs | 可用 | 生成 proto 与 Go/Python gRPC stub |
| IR plugin | 预览 | 让项目插件消费 ContractGraph 并生成自有产物 |

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

常用本地命令：

```sh
make test-fast
make example-validation
make example-conformance
make release-preflight RELEASE_TAG=vX.Y.Z
```

完整开发、示例验证、benchmark 和发布流程见上面的专题文档。
