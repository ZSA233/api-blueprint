# 生成器说明

本文概述非 Wails、非 gRPC 的主要生成器。Wails 见 [Wails 说明](wails.md)，gRPC 见 [gRPC 说明](grpc.md)。

## Go

```sh
api-gen-golang -c api-blueprint.toml
```

Go 生成器输出：

- route interface 与默认 `impl.go`。
- 请求 / 响应 / 上下文结构。
- provider runtime 与 wrapper。
- transport-neutral Go core。
- 可选 HTTP/Gin adapter。

`gen_*` 文件由生成器拥有，重生成会覆盖。`impl_*` 与非 `gen_*` 文件是用户拥有扩展点，重生成时保留。

`[[transport.targets]]` 控制 Go transport 输出；未声明 target 时默认生成 HTTP target。HTTP 入口生成在 `views/transports/http/<root>` 中，例如 `views/transports/http/api.NewBlueprint(engine)`；Wails-only 项目只声明 `kind = "wails"` target，HTTP + Wails 项目同时声明 `kind = "http"` 与 `kind = "wails"`。

Go route core 固定生成在 `views/routes/**`，provider runtime 固定生成在 `views/providers`。这两个目录名不再通过配置自定义，业务 root 可以安全使用 `/providers` 或 `/transports` 这类路径。

`views/providers` 是全局 transport-neutral runtime，不按 blueprint root 拆分。TypeScript 的 per-root `runtime` 主要服务模型和 client 命名隔离，和 Go provider hook 不是同一类职责。

需要按 root、route 或 transport 切换 provider 实现时，不要解析请求 path。生成器会在每个 route executor 构造期写入 `RouteInfo`，并把它挂到 `Context.Route` 与 `ProviderSpec.Route`：

```go
providers.RegisterProviderFactory(providers.PROV_RSP, func(spec providers.ProviderSpec) providers.Provider {
	if spec.Route.Root != "static" {
		return nil
	}
	// 可选：spec.Handler 是当前 route 的 typed handler，可在确实需要时做类型断言。
	return NewCachedRspProvider(spec.Data)
})
```

自定义 provider 可以在 DSL 中使用 `provider.Custom(name, data)` 加入 pipeline：

```python
from api_blueprint.engine import Blueprint, provider

bp = Blueprint(
    root="/static",
    providers=[
        provider.Req(),
        provider.Custom("cache", "ttl=60s"),
        provider.Handle(),
        provider.Rsp(),
    ],
)
```

provider factory 应在应用启动或包 `init()` 阶段注册。provider sequence 只在 executor 创建期解析，factory 也只在创建期运行；高并发请求路径只执行已缓存 provider 实例。如果需要不用全局 registry 的项目内选择逻辑，直接在用户拥有的 `views/providers/impl_provider.go` 中实现 `SelectProvider(spec, handler)`；旧的 `Select(key, value, handler)` hook 已移除。

HTTP adapter 只在 blueprint root 存在直接 routes 时导入 root router。handler 如果已经通过 Gin 写出响应，adapter 不再追加自动响应；否则没有 `rsp` provider 的 route 仍保持旧行为，由 adapter 写出 handler 返回值。

需要由 handler 完全接管 HTTP 成功响应时，使用 `HTTP_RAW_RESPONSE()`。该语义只影响 HTTP adapter：成功时不自动写响应，错误时如果 Gin writer 尚未写出则返回 500；它不是 shared provider，也不会改变 Wails overlay。

## TypeScript

```sh
api-gen-typescript -c api-blueprint.toml
```

TypeScript 生成器输出：

- `models.ts` / `gen_models.ts`。
- request client class。
- transport-neutral `ApiClientConfig`。
- transport facade `createClients(config)` factory。
- user-owned passthrough 文件，例如 `client.ts`、`transport.ts`、`factory.ts`。

`base_url_expr` 会原样写入生成代码，适合 Vite、Next.js 等运行时配置；它与 `base_url` 互斥。

## Kotlin Android

```sh
api-gen-kotlin -c api-blueprint.toml
```

Kotlin 生成器输出 OkHttp + kotlinx.serialization Android 客户端。

当前版本主要覆盖 JSON REST route。`include` / `exclude` 可裁剪输出接口面。

## Java

Java 目标目前不作为公共 CLI 暴露，只保留内部扩展位。

## examples 快照

`examples/golang/`、`examples/typescript/` 与 `examples/kotlin/` 是生成快照，不是业务真源。需要接受预期生成变化时，使用：

```sh
make example-refresh
```
