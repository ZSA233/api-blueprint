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

## 安装

当前仓库只维护 GitHub 安装入口；稳定安装路径固定指向 `stable` 分支。

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

## 核心工作流

- 在 `examples/blueprints/` 这类目录中定义 `Blueprint` 与路由 DSL。
- 通过 `api-doc-server` 构建文档服务，复用 FastAPI 的 OpenAPI 输出。
- 通过 `api-gen-golang` 与 `api-gen-typescript` 生成语言侧快照产物。

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
- `main.py` 与 `debug.py` 仅作为本地辅助脚本保留，不属于公共发布面。

## 开发

```sh
make sync
make test
make build
```

## 发布

- 文档收束顺序固定为 `PRE_README.MD -> README.md -> README_EN.md`。
- 版本真源固定为 `release-version.toml` 与 `src/api_blueprint/_version.py`。
- stable 正式发布 workflow 绑定 GitHub `production` environment；若仓库给它配置了 required reviewers，则发布前需要人工审核。
- 详细发布规范见 [`docs/release-process.md`](docs/release-process.md)。

```sh
make release-version-show
make release-preflight RELEASE_TAG=v0.0.1
make release-local RELEASE_TAG=v0.0.1
make release-install-check RELEASE_TAG=v0.0.1
```
