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

## 支持的输出

| 目标 | 状态 | 命令 | 示例目录 |
|:---|:---:|:---|:---|
| Go | 可用 | `api-gen-golang` | `examples/golang` |
| TypeScript | 预览 | `api-gen-typescript` | `examples/typescript` |

当前不会对外暴露 Kotlin / Java / grpc 命令；这些目标只保留内部扩展位。

## 安装

当前仓库只维护 GitHub 安装入口；稳定安装路径固定指向 `stable` 分支。

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

## 核心工作流

- 在 `examples/blueprints/` 这类目录中定义 `Blueprint` 与路由 DSL。
- 通过 `api-doc-server` 构建文档服务，复用 FastAPI 的 OpenAPI 输出。
- 通过 `api-gen-golang` 与 `api-gen-typescript` 生成语言侧快照产物。
- 功能开发期可通过 `make example-compile-check` 做“重生成 -> TypeScript 编译 -> Go 测试”校验。
- 需要接受预期生成变更时使用 `make example-refresh` 刷新 examples snapshots。
- 需要严格确认 snapshots 已收敛时使用 `make example-validation`。

## 配置文件

```toml
[blueprint]
docs_server = "0.0.0.0:2332"
docs_domain = ""
entrypoints = [
    "blueprints.app:*",
]

[golang]
codegen_output = "golang"
upstream = "http://localhost:2333"
module = ""

[typescript]
codegen_output = "typescript"
upstream = "http://localhost:2333"
base_url = "http://localhost:2333"
```

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
api-gen-typescript -c examples/api-blueprint.toml
```

## 生成产物与仓库约束

- `examples/blueprints/` 是蓝图真源。
- `examples/golang/` 与 `examples/typescript/` 是生成快照，不应该手改业务内容。
- `Blueprint(app=None)` 默认共享全局 `FastAPI` app；如果需要拆成多个独立文档应用，必须显式传入 `app`。
- example snapshot drift 表示“当前生成器输出和已提交快照不一致”，它是变更信号，不自动等于 bug。
- `make example-compile-check` 允许 drift，只检查重生成结果是否仍可编译。
- `make example-refresh` 会接受预期变化，直接刷新仓库中的 examples snapshots。
- `make example-validation` 会包装 `scripts/example_validation.py` 的严格模式，在临时目录重生成 examples，再执行 snapshot diff、`tsc --noEmit` 和 `go test ./...`。
- `make release-preflight` 必须包含严格的 `make example-validation`，因为到发版前，预期的 snapshot 变化应已经被接受并提交。
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
