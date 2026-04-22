# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

🌍 语言: 中文 | [English](README_EN.md)

## 概述

`api-blueprint` 是一个把 Python DSL、FastAPI/OpenAPI 和多语言代码生成串起来的项目。

它的主线工作流是：

1. 用 Python 描述 `Blueprint`、路由、请求/响应模型与错误结构。
2. 运行时构建 FastAPI 应用并暴露 OpenAPI 文档。
3. 基于同一份蓝图生成 Go 与 TypeScript 代码快照。
4. 基于 `api-blueprint.toml` 里的 gRPC target 配置编译已有 `.proto` 目录树，并兼容 legacy/raw job 模式。

## 支持的输出

| 目标 | 状态 | 命令 | 示例目录 |
|:---|:---:|:---|:---|
| Go | 可用 | `api-gen-golang` | `examples/golang` |
| gRPC | 可用 | `api-gen-grpc` | `examples/grpc/{go,python}` |
| TypeScript | 预览 | `api-gen-typescript` | `examples/typescript` |

当前不会对外暴露 Kotlin / Java 命令；这些目标只保留内部扩展位。

## 安装

当前仓库只维护 GitHub 安装入口；稳定安装路径固定指向 `stable` 分支。

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

## 核心工作流

- 在 `examples/blueprints/` 这类目录中定义 `Blueprint` 与路由 DSL。
- 在 `examples/grpc/` 下查看公开的 proto 树和 Go / Python gRPC 快照；对应的 `[grpc]` 示例配置与 Blueprint 示例共用 `examples/api-blueprint.toml`。
- 通过 `api-doc-server` 构建文档服务，复用 FastAPI 的 OpenAPI 输出。
- 通过 `api-gen-golang` 与 `api-gen-typescript` 生成语言侧快照产物。
- 通过 `api-gen-grpc` 按 target 编译已有 proto 树；如需兼容旧配置，仍可调用 legacy/raw jobs。
- 功能开发期可通过 `make example-compile-check` 做“Blueprint + gRPC examples 重生成 -> 编译/导入 smoke”校验。
- 需要接受预期生成变更时使用 `make example-refresh` 刷新 examples snapshots。
- 需要严格确认 snapshots 已收敛时使用 `make example-validation`。

## 配置文件

```toml
[blueprint]
docs_server = '0.0.0.0:2332'
docs_domain = ''
entrypoints = [
    'blueprints.app:*',
]

[golang]
codegen_output = 'golang'
upstream = 'http://localhost:2333'
module = ''

[typescript]
codegen_output = 'typescript'
upstream = 'http://localhost:2333'
# literal URL fallback
base_url = 'http://localhost:2333'
# raw runtime expression, mutually exclusive with base_url
# base_url_expr = 'import.meta.env.VITE_API_BASE_URL'

[grpc]
source_root = 'grpc/protos'
import_roots = []

[[grpc.targets]]
id = 'python.greeter'
lang = 'python'
out_dir = 'grpc/python'
files = ['**/*.proto']

[[grpc.targets]]
id = 'go.greeter'
lang = 'go'
out_dir = 'grpc/go'
files = [
    'commonpb/common.proto',
    'greeterpb/greeter.proto',
]
```

## gRPC 语义模型

- `id` 只负责 target 选择，供 `--target`、`--list-targets` 与 `--explain-target` 使用。
- `source_root` 只负责解释 `files` 的相对路径，同时也是 `protoc` 的工作根。
- `import_roots` 只负责 import 查找，不参与输出目录计算。
- `out_dir` 永远表示最终生成目录，不再表示 Go module 根目录。

### Advanced / Legacy Mode

- `[[grpc.jobs]]` 仍然可用，但它只保留为 legacy/raw mode，不再是 README 主路径。
- `--job` 与 `--list-jobs` 继续保留，适合已经依赖 `proto_root`、`include_paths`、`layout`、`module` 的旧配置。

## Go target 与 module

- Go target 会从 `out_dir` 向上自动发现最近的 `go.mod`，并解析 module path。
- 工具会根据 `out_dir` 推导期望的 `go_package` import path 前缀，再校验每个选中 proto 的 `option go_package`。
- 公开配置不再要求手填 `module` 或 `layout`；如果 `go_package` 与 `out_dir` 不一致，会直接报出 `out_dir`、`module_root`、`module_path` 和期望前缀。

## Python source_root 与输出路径

- Python target 的 `source_root` 会直接作为 `grpc_tools.protoc` 的工作根和第一条 `-I`。
- 生成文件仍按 source-relative 方式落盘，所以 `source_root` 会直接影响最终输出目录层级。
- `import_roots` 只补充 import 查找，不改变 Python 生成文件的落盘路径。

## 蓝图 DSL 示例

```python
from api_blueprint.includes import *
from blueprints.app import apibp


class ApiDemoSubA(Model):
    hello = Map[String, Int](description="hello")


class ApiDemoA(Model):
    bc = String(description="bc")
    a = Int(description="a")
    efg = Float32(description="efg")
    hijk = Array[Uint](description="hijk")
    lmnop = Array[ApiDemoSubA](description="lmnop", omitempty=True)


with apibp.group("/demo") as views:
    views.GET(
        "/abc",
        summary="这是 abc 的 summary",
        description="这是 abc 的 description",
    ).ARGS(
        arg1=Bool(description="arg1", default=True),
        arg2=Float(description="arg2", default=6.666),
    ).RSP(ApiDemoA)
```

## CLI 命令

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen-golang -c examples/api-blueprint.toml
api-gen-grpc -c examples/api-blueprint.toml --list-targets
api-gen-grpc -c examples/api-blueprint.toml --target go.*
api-gen-grpc -c examples/api-blueprint.toml --explain-target go.greeter
api-gen-grpc -c examples/api-blueprint.toml --list-jobs
api-gen-typescript -c examples/api-blueprint.toml
```

## 生成产物与仓库约束

- `examples/blueprints/` 是蓝图真源。
- `examples/golang/` 与 `examples/typescript/` 是 Blueprint 生成快照，不应该手改业务内容。
- `examples/grpc/protos/` 是 gRPC 示例真源，`examples/grpc/go/` 与 `examples/grpc/python/` 是对应的生成快照。
- `api-gen-grpc` 只负责编排已有 `.proto` 树的编译，不会从 Blueprint DSL 反推出 gRPC proto/service。
- `api-gen-grpc` 可以只依赖 `[grpc]` 段落，不要求 `[blueprint]`、`[golang]` 或 `[typescript]` 同时存在。
- `[typescript]` 支持字面量 `base_url` 和原样 TypeScript 表达式 `base_url_expr`；两者互斥，解析优先级固定为 `base_url_expr -> base_url -> upstream -> ""`。
- Python gRPC target 需要额外安装 `grpcio-tools`；Go gRPC target 需要 `protoc`、`protoc-gen-go` 与 `protoc-gen-go-grpc` 在 `PATH` 中可用；`grpcio-tools` 不属于运行时依赖。
- legacy/raw `[[grpc.jobs]]` 默认仍按 `proto_root` 解释 proto 展开根目录；Go legacy job 继续支持 `layout = "go_package"` 与 `module`，Python legacy job 仍不支持它们。
- `Blueprint(app=None)` 默认共享全局 `FastAPI` app；如果需要拆成多个独立文档应用，必须显式传入 `app`。
- example snapshot drift 表示“当前生成器输出和已提交快照不一致”，它是变更信号，不自动等于 bug。
- `make example-compile-check` 允许 drift，只检查重生成结果是否仍可编译。
- `make example-refresh` 会接受预期变化，直接刷新仓库中的 examples snapshots。
- `make example-validation` 会包装 `scripts/example_validation.py` 的严格模式，在临时目录重生成 Blueprint 与 gRPC examples，再执行 snapshot diff、`tsc --noEmit`、`go test ./...` 和 Python gRPC import smoke。
- Blueprint examples 的严格重生成依赖 `go-enum`；gRPC examples 依赖 `protoc`、`protoc-gen-go`、`protoc-gen-go-grpc` 与 Python `grpc_tools`。
- `make release-preflight` 必须包含严格的 `make example-validation`，因为到发版前，预期的 snapshot 变化应已经被接受并提交。
- `examples/api-blueprint.toml` 同时承载 Blueprint 与 gRPC 的公开示例配置，`examples/grpc/go/` 与 `examples/grpc/python/` 属于 committed examples snapshot contract。
- `main.py` 与 `debug.py` 仅作为本地辅助脚本保留，不属于公共发布面。

## 开发

```sh
make sync
make test
make example-compile-check
make example-refresh
make example-validation
make build
```

## 发布

- 文档收束顺序固定为 `PRE_README.MD -> README.md -> README_EN.md`。
- 版本真源固定为 `release-version.toml` 与 `src/api_blueprint/_version.py`。
- `make release-preflight` 会同时执行 release contract、`make test` 与 `make example-validation`。
- 如果 release 前发现 example drift 是预期变化，应先执行 `make example-refresh` 并提交结果，再重新运行 `make release-preflight`。
- stable 正式发布 workflow 绑定 GitHub `production` environment；若仓库给它配置了 required reviewers，则发布前需要人工审核。
- 详细发布规范见 [`docs/release-process.md`](docs/release-process.md)。

```sh
make release-version-show
make release-preflight RELEASE_TAG=v0.0.1
make release-local RELEASE_TAG=v0.0.1
make release-install-check RELEASE_TAG=v0.0.1
```
