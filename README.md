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

Go / Wails Go 的 route 目录、Go import path 和 `package` 声明使用 Go-safe route package segment，例如 `/api-v1` -> `api_v1`、`/admin/v1` -> `admin_v1`；它们不保证逐级镜像 URL slash 层级，URL、route path 和 selection/filter 语义不变。

默认 `CodeMessageDataEnvelope` 使用企业/APP 常见 `{ code, message, data, error? }` wire shape：成功为 `{ code: 0, message: "ok", data }`，失败携带 `{ code, message, data: null, error: { id, group, key, toast } }`。ContractGraph manifest `2.0` 会在 route 上直接输出 `id/group/key/code/message/toast` error refs，默认客户端 transport 按 envelope spec 自动还原并抛出/返回 `ApiError`；严格 `{ code, message, data }` 旧形态可显式选择 `LegacyCodeMessageDataEnvelope`。

示例工程的 `/api/demo/error-demo` 展示了全局错误、route-local 错误、动态 `toast.text` 覆盖和未声明错误码 fallback；Go / TypeScript / Python / Java suite 都包含 generated client catch `ApiError` 的用法。

生成物 SDK 的推荐入口是 public facade：Go 使用 `apiclient.NewHTTP(...)` 和 `demo.ErrorDemoQuery`，Python 使用 `async with create_client(base_url) as api` 并返回 dataclass response，Java 使用 `HttpApiClient.create(baseUrl)` 和 `DemoTypes.ErrorDemoQuery`。协议类型统一使用 `types` 命名：Go `gen_types.go`、TypeScript `types.ts` / `gen_types.ts`、Python `gen_types.py`、Java/Kotlin `<Group>Types`；二进制 schema 不再公开 `wire` namespace，业务代码从同 route package/module 的 public types 入口使用 packet / writer helper。业务错误判断推荐使用 grouped `ApiErrors` entry，而不是直接 switch catalog 表。

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
