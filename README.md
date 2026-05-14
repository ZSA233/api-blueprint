# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

语言: 中文 | [English](README_EN.md)

## 概述

`api-blueprint` 用 Python DSL 定义 API 契约，再从同一份协议真源生成文档服务和多语言代码。它适合把 HTTP API、长连接消息、二进制请求体和 gRPC proto 放在一个可检查、可生成、可回归的协议工作流里维护。

核心链路是：

```text
Blueprint DSL -> ContractGraph -> api-gen check / inspect / generate -> generated code
```

## 适合什么场景

- 后端、Web、Android、脚本客户端需要共享同一份 API 契约。
- 希望先从协议生成 Go server，再生成 TypeScript、Kotlin、Java、Go、Python client。
- 需要文档服务、契约检查、生成快照和端到端示例一起维护。
- 需要把 Markdown Binary Schema、Wails 或 gRPC 纳入同一套生成流程。

## 安装

稳定安装入口固定指向 GitHub `stable` 分支：

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

本仓库开发环境使用：

```sh
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

更完整的项目目录、Go client、Kotlin、Java、Python、Wails 和 gRPC 配置见 [快速开始](docs/zh/getting-started.md) 与 [配置说明](docs/zh/configuration.md)。

## 常用目标

| 目标 | 状态 | 用途 |
|:---|:---:|:---|
| Contract / inspect | 可用 | 输出契约索引，并按 route、schema、error、文件归属查询协议细节 |
| Go server | 可用 | 生成 Go 路由、provider、HTTP/Wails adapter 和 runtime |
| TypeScript client | 预览 | 生成 transport-neutral client、HTTP adapter 和 Wails facade |
| Kotlin Android client | 预览 | 生成 OkHttp client、模型、binary writer 和 route facade |
| Java client/server | 预览 | 生成 Java 17 HttpClient client、Spring MVC server scaffold、record DTO 和 HTTP adapter |
| Go / Python client | 预览 | 生成服务端之外的脚本或工具侧客户端 |
| Python server | 预览 | 生成 FastAPI server scaffold 和 service contract |
| Wails v2/v3 | 预览 / 实验性 | 生成 Go + TypeScript overlay，用于桌面 GUI |
| gRPC proto / stubs | 可用 | 从 ContractGraph 输出 proto，并生成 Go/Python stub |

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
| 发布流程 | [docs/release-process.md](docs/release-process.md) |

## 开发和发布

开发期常用命令：

```sh
make test
make example-compile-check
make example-validation
make example-golang-suite
make example-java-suite
```

`example-golang-suite` 和 `example-java-suite` 是手动端到端增强验证，不进入默认测试、发布预检或 CI。正式发布前的版本、构建、安装和 GitHub Release 流程见 [发布流程](docs/release-process.md)。
