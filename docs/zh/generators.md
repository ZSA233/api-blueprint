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
- FastAPI/OpenAPI 对应的 Go HTTP 入口。

`gen_*` 文件由生成器拥有，重生成会覆盖。`impl_*` 与非 `gen_*` 文件是用户拥有扩展点，重生成时保留。

`[golang].provider_package` 控制共享 provider/runtime 包名，默认 `provider`。

## TypeScript

```sh
api-gen-typescript -c api-blueprint.toml
```

TypeScript 生成器输出：

- `models.ts` / `gen_models.ts`。
- request client class。
- transport-neutral `ApiClientConfig`。
- shared `createClients(config)` factory。
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
