# 快速开始

本文面向第一次接入 `api-blueprint` 的用户，目标是从一份 Python Blueprint 生成 Go、TypeScript 与文档服务。

## 安装

当前稳定安装入口固定指向 GitHub `stable` 分支：

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

开发本仓库时使用：

```sh
make sync
```

## 目录建议

一个最小项目通常包含：

```text
your-project/
  api-blueprint.toml
  blueprints/
    __init__.py
    app.py
  golang/
    server/
    client/
  typescript/
```

`blueprints/` 是 API 契约真源，`golang/server`、`golang/client` 和 `typescript/` 是生成产物目录。

## 定义 Blueprint

```python
from api_blueprint.includes import *

bp = Blueprint(root="/api")


class HelloResponse(Model):
    message = String(description="message")


with bp.group("/demo") as views:
    views.GET("/hello").RSP(HelloResponse)
```

## 编写最小配置

```toml
[blueprint]
entrypoints = ["blueprints.app:bp"]

[[go.server]]
id = "go.server"
out_dir = "golang/server/views"
module = "example.com/project/golang/server"

[[go.client]]
id = "go.client"
out_dir = "golang/client"
base_url = "http://localhost:2333"

[[typescript.client]]
id = "typescript.client"
out_dir = "typescript"
base_url = "http://localhost:2333"

[[transport.http]]
id = "http"
server = "go.server"
clients = ["go.client", "typescript.client"]
```

## 启动文档服务

```sh
api-doc-server -c api-blueprint.toml
```

默认文档服务会加载 `[blueprint].entrypoints`，构建 FastAPI/OpenAPI 输出。

## 生成代码

```sh
api-gen generate -c api-blueprint.toml
```

如果使用仓库示例配置，可以直接运行：

```sh
api-gen list-targets -c examples/api-blueprint.toml
api-gen check -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml
api-gen generate -c examples/api-blueprint.toml --target wails.v3
```

## 下一步

- 配置字段见 [配置说明](configuration.md)。
- DSL 写法见 [Blueprint DSL](blueprint-dsl.md)。
- 生成目标差异见 [生成器说明](generators.md)。
- Wails 接入见 [Wails 说明](wails.md)。
- gRPC target 见 [gRPC 说明](grpc.md)。
