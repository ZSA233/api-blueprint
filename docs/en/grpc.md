# gRPC

vNext gRPC no longer treats an existing `.proto` tree as an independent source of truth. The `grpc-proto` target emits `.proto` files and service definitions from ContractGraph, and ContractGraph still comes from Blueprint.

## Target

```toml
[[targets]]
id = "grpc.proto"
kind = "grpc-proto"
out_dir = "grpc/protos"
package = "example.api"
go_package_prefix = "example.com/project/grpc/go"
```

- `out_dir`: proto output directory.
- `package`: proto package.
- `go_package_prefix`: used to generate `option go_package`; files are split by Blueprint root/group.

## RPC Mapping

- Normal HTTP routes emit unary RPCs.
- `STREAM` emits server-streaming RPCs.
- `CHANNEL` emits bidirectional streaming RPCs.
- Single-model or union `SERVER_MESSAGE` / `CLIENT_MESSAGE` contracts enter the proto message set.

## CLI

```sh
api-gen generate -c api-blueprint.toml --target grpc.proto
api-gen manifest -c api-blueprint.toml --out api-blueprint.contract.json
api-gen diff old.contract.json new.contract.json
api-gen check -c api-blueprint.toml
```

Old raw proto targets/jobs are outside the vNext public mainline. When Go/Python gRPC compilation is needed, use the generated proto files as input to each language toolchain.
