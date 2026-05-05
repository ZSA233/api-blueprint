# 配置说明

`api-blueprint.toml` 是生成器和文档服务的主配置文件。示例配置见 [`examples/api-blueprint.toml`](../../examples/api-blueprint.toml)。

## blueprint

```toml
[blueprint]
docs_server = "0.0.0.0:2332"
docs_domain = ""
entrypoints = ["blueprints.app:*"]
```

- `docs_server`：`api-doc-server` 监听地址。
- `docs_domain`：文档服务展示域名，可留空。
- `entrypoints`：需要加载的 Python 对象，支持模块路径加对象名。

`Blueprint(app=None)` 默认共享全局 FastAPI app。如果需要多个独立文档应用，应显式传入 `app`。

## golang

```toml
[golang]
codegen_output = "golang"
upstream = "http://localhost:2333"
module = ""
```

- `codegen_output`：Go 生成目录。
- `upstream`：生成 wrapper 中使用的后端地址。
- `module`：可选 Go module 覆盖；通常留空，由工具解析。

Go core 始终生成在 `views/routes/**`，包含 route interface、models 与用户 `impl.go`；provider runtime 固定生成在 `views/providers`。具体 HTTP / Wails 输出由 `[[transport.targets]]` 控制。

## typescript

```toml
[typescript]
codegen_output = "typescript"
upstream = "http://localhost:2333"
base_url = "http://localhost:2333"
# base_url_expr = "import.meta.env.VITE_API_BASE_URL"
```

- `codegen_output`：TypeScript 生成目录。
- `upstream`：兼容默认地址来源。
- `base_url`：字面量 base URL。
- `base_url_expr`：原样输出到 TypeScript 的表达式。

`base_url_expr` 与 `base_url` 互斥，解析优先级为 `base_url_expr -> base_url -> upstream -> ""`。

## kotlin

```toml
[kotlin]
codegen_output = "kotlin"
package = "com.example.apiblueprint"
base_url = "http://localhost:2333"
include = ["tag:api"]
exclude = ["path:/static/**"]
```

Kotlin 生成 OkHttp + kotlinx.serialization Android 客户端。当前版本面向 JSON REST route，暂不覆盖 WebSocket、form 与 binary route。

`include` / `exclude` 支持 `path:`、`tag:`、`group:`、`method:`、`name:` 规则。

## transport

```toml
[[transport.targets]]
id = "http"
kind = "http"

[[transport.targets]]
id = "desktop.v3"
kind = "wails"
version = "v3"
frontend_mode = "external"
# overlay_name = "wailsv3"
# include = ["group:demo"]
# exclude = ["path:/api/internal/**"]
```

未声明任何 `[[transport.targets]]` 时默认生成一个 HTTP target。显式声明 target 后，生成器只生成列出的 transport。

- `kind = "http"`：生成 Gin HTTP adapter，入口位于 `views/transports/http/<root>`，例如 `views/transports/http/api.NewBlueprint(engine)`。
- `kind = "wails"`：生成 Wails target；至少需要 `id`、`kind` 与 `version`。`version` 支持 `v3` 和 `v2`。

- `overlay_name`：默认 `wailsv3` / `wailsv2`，必须在所有 target 内唯一。
- `frontend_mode`：默认 `external`；`none` 表示只生成 Go Wails overlay，不生成 Wails TypeScript overlay。
- `include` / `exclude`：裁剪 Wails target overlay / facade；没有 selected route 的 root 不生成 `transports/<overlay_name>`，但共享 Go / TypeScript 契约层仍完整生成。

详细布局与 hook 见 [Wails 说明](wails.md)。

## grpc

```toml
[grpc]
source_root = "grpc/protos"
import_roots = []

[[grpc.targets]]
id = "go.greeter"
lang = "go"
out_dir = "grpc/go"
files = ["commonpb/common.proto", "greeterpb/greeter.proto"]

[[grpc.targets]]
id = "python.greeter"
lang = "python"
out_dir = "grpc/python"
files = ["**/*.proto"]
python_package_root = "examplegrpc_pb"
```

gRPC target 编译已有 `.proto` 树，不会从 Blueprint DSL 反推 proto/service。

详细 target 行为见 [gRPC 说明](grpc.md)。
