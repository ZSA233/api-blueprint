# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

语言: 中文 | [English](README_EN.md)

## 概述

`api-blueprint` 用 Python DSL 定义 API 契约，并基于同一份契约生成文档服务、Go、TypeScript、Kotlin Android、Wails v2/v3 overlay，以及已有 `.proto` 树的 gRPC 产物。

README 只保留上手路径。完整配置、Wails、gRPC、DSL 和 examples 验证说明见 [深入文档](#深入文档)。

## 支持的输出

| 目标 | 状态 | 命令 | 示例 |
|:---|:---:|:---|:---|
| Go | 可用 | `api-gen-golang` | `examples/golang` |
| TypeScript | 预览 | `api-gen-typescript` | `examples/typescript` |
| Wails v3 | 实验性 | `api-gen-wails` | `examples/{golang,typescript,wails-harness/v3,wails-hello}` |
| Wails v2 | 预览 | `api-gen-wails` | `examples/{golang,typescript,wails-harness/v2}` |
| Kotlin Android | 预览 | `api-gen-kotlin` | `examples/kotlin` |
| gRPC | 可用 | `api-gen-grpc` | `examples/grpc/{go,python}` |


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

[golang]
codegen_output = "golang"
upstream = "http://localhost:2333"

[typescript]
codegen_output = "typescript"
base_url = "http://localhost:2333"
```

```sh
api-doc-server -c api-blueprint.toml
api-gen-golang -c api-blueprint.toml
api-gen-typescript -c api-blueprint.toml
```

## 最小配置

下面是常见多目标配置骨架；完整字段见 [配置说明](docs/zh/configuration.md)。

```toml
[blueprint]
entrypoints = ["blueprints.app:*"]

[golang]
codegen_output = "golang"
upstream = "http://localhost:2333"
provider_package = "provider"

[typescript]
codegen_output = "typescript"
base_url = "http://localhost:2333"

[[wails.targets]]
id = "wails.v3"
version = "v3"
frontend_mode = "external"

[grpc]
source_root = "grpc/protos"
import_roots = []

[[grpc.targets]]
id = "go.greeter"
lang = "go"
out_dir = "grpc/go"
files = ["greeterpb/greeter.proto"]
```

## 常用命令

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen-golang -c examples/api-blueprint.toml
api-gen-typescript -c examples/api-blueprint.toml
api-gen-kotlin -c examples/api-blueprint.toml
api-gen-wails -c examples/api-blueprint.toml --list-targets
api-gen-wails -c examples/api-blueprint.toml --target wails.v3
api-gen-grpc -c examples/api-blueprint.toml --list-targets
api-gen-grpc -c examples/api-blueprint.toml --target go.*
```

## 生成产物与用户文件

- `examples/blueprints/` 与 `examples/grpc/protos/` 是示例真源。
- `examples/golang/`、`examples/typescript/`、`examples/kotlin/`、`examples/grpc/go/`、`examples/grpc/python/` 是生成快照。
- `examples/wails-hello/` 是独立 Wails v3 hello world 示例，演示不启动 HTTP 服务的 GUI 闭环。
- `gen_*` 文件由生成器拥有，重生成会覆盖。
- `impl_*` 与非 `gen_*` passthrough 文件是用户拥有扩展点，重生成时保留。
- Wails overlay 生成在共享 Go / TypeScript 输出树的相邻保留目录中；`api-gen-wails` 不生成完整 Wails app shell，external frontend 需先加载 Wails runtime。
- gRPC 只编译已有 `.proto` 树，不会从 Blueprint DSL 反推 proto/service。

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
make release-preflight RELEASE_TAG=v0.0.1
make release-local RELEASE_TAG=v0.0.1
make release-install-check RELEASE_TAG=v0.0.1
```
