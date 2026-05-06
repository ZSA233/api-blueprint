# gRPC

vNext gRPC 不再把已有 `.proto` 目录树作为独立真源。`grpc-proto` target 从 ContractGraph 输出 `.proto` 文件和 service 定义，ContractGraph 仍然来自 Blueprint。

## Target

```toml
[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"
```

- `out_dir`：proto 输出目录。
- `package`：proto package。
- `go_package_prefix`：用于生成 `option go_package`，文件按 Blueprint root/group 拆分。

## RPC 映射

- 普通 HTTP route 输出 unary RPC。
- `STREAM` 输出 server-streaming RPC。
- `CHANNEL` 输出 bidirectional streaming RPC。
- `SERVER_MESSAGE` / `CLIENT_MESSAGE` 的单模型或联合模型会进入 proto message 集合。

## CLI

```sh
api-gen generate -c api-blueprint.toml --target grpc.proto
api-gen manifest -c api-blueprint.toml --out api-blueprint.contract.json
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
```

旧 raw proto targets/jobs 不属于 vNext 公共主线；需要 Go/Python gRPC 编译时，应以生成出的 proto 作为输入交给各语言工具链。
