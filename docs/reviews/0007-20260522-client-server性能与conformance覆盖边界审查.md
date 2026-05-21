# Client / Server 性能与 Conformance 覆盖边界审查

## 状态

待修复 / 建议优化。

本次审查未发现跨所有 target 的致命性能设计缺陷，但确认 Go HTTP client multipart 上传存在一个真实性能缺口：`runtime.MultipartFile.Reader` 暴露了流式输入能力，当前 transport 却会先把完整 multipart body 写入内存 `bytes.Buffer`，大文件上传会在请求发出前产生与文件大小同量级的内存峰值。

因此本记录保留在 `docs/reviews/` 顶层，不移动到 `resolved/`。

## 发现日期

2026-05-22

## 背景

前序审查已经补齐安全默认、能力覆盖、逃生通道、request options、真流式 `byte_stream` 和 generated ownership。本次从性能角度重新检查 client/server 生成物，重点判断：

- 各端在长耗时请求、并发请求、大文件、raw media、binary schema、`byte_stream`、SSE、WebSocket 下是否有明显瓶颈。
- 是否存在因为 generated 代码不可手改而无法规避的性能缺口。
- 当前 conformance 与 benchmark 是否覆盖了所有能力边界，还是只覆盖协议正确性和 smoke 路径。
- 是否存在冗余 abstraction、聚合入口、默认实现策略导致的性能恶化或不可裁剪问题。

## 风险分级

中。

- 阻塞风险：未确认。
- 中风险：Go HTTP client multipart 上传会全量 buffer，即使用户传入 `io.Reader` 文件输入。
- 低风险：benchmark / conformance 当前缺少大 multipart、长 `byte_stream`、长连接回压、generated SDK 吞吐的性能回归覆盖。
- 可接受限制：JSON、form、typed binary schema、raw `bytes` / `file` response 的 buffered 行为属于当前契约或便利 API 边界；生产大流量场景应使用 `byte_stream`、stream/file part 或自定义 transport。

## 问题性质

性能与覆盖边界审查记录。

本记录不是协议正确性 bug 的复盘，也不是安全审查的重复。重点是确认默认生成物是否会在真实生产负载下因为实现方式、内存模型、连接生命周期、聚合入口或测试盲区产生性能风险。

## 存在性判断

确认存在一个需要修复的性能缺口。

Go client runtime 已经公开 `runtime.MultipartFile{Reader io.Reader, Bytes []byte}`，这会让使用者合理预期大文件可以走 reader stream。但 HTTP transport 的 `encodeMultipart` 目前使用 `bytes.Buffer` 和 `multipart.NewWriter(&buffer)`，`writeMultipartFile` 虽然对文件执行 `io.Copy(part, reader)`，最终仍写入内存 buffer。也就是说，stream API 被 transport 实现抵消。

其它端未确认同等级缺口：

- Java client multipart 使用 `BodyPublishers.ofInputStream`，文件 part 可通过 input stream 发送。
- Kotlin client multipart 使用 OkHttp `MultipartBody` / `RequestBody`，file path 不需要预先整体读入内存。
- Flutter client 支持 `ApiFilePart.fromStream`，在提供 length 时交给 `http.MultipartFile` stream。
- Python client multipart 使用 async iterator 分块读取 file-like payload。
- TypeScript browser/client transport 使用 `FormData`，具体 streaming/buffering 由 runtime/fetch 实现决定；有 custom fetcher / custom transport 逃生通道。

## 复现场景 / 性能视角

Go 用户调用 media multipart route，并传入大文件 reader：

```go
file, err := os.Open("large.bin")
if err != nil {
	return err
}
defer file.Close()

result, err := api.Media.Preview(ctx, media.PreviewMultipart{
	File: runtime.MultipartFile{
		Filename:    "large.bin",
		ContentType: "application/octet-stream",
		Reader:      file,
	},
})
```

当前生成的 Go transport 路径：

- `examples/golang/client/runtime/gen_client.go:81` 定义 `MultipartFile.Reader io.Reader`。
- `examples/golang/client/transports/http/gen_transport.go:175` 的 `encodeMultipart` 创建 `bytes.Buffer`。
- `examples/golang/client/transports/http/gen_transport.go:177` 将 `multipart.Writer` 绑定到该 buffer。
- `examples/golang/client/transports/http/gen_transport.go:185` 返回 `&buffer` 和 `int64(buffer.Len())`。
- `examples/golang/client/transports/http/gen_transport.go:240` 附近的 `writeMultipartFile` 对 reader 做 `io.Copy(part, reader)`，但 `part` 实际写入的是内存 buffer。

性能后果：

- 大文件会在 HTTP request 发出前完整进入进程内存。
- 并发上传时内存峰值接近 `并发数 * multipart body size`。
- 用户即使选择 `Reader` 而不是 `Bytes` 也无法获得预期的流式发送。
- context cancellation 只能中断之后的 HTTP 请求，不能避免编码阶段已经发生的内存放大。

## 影响范围

确认影响：

- Go HTTP generated client。
- multipart request body。
- 使用 `runtime.MultipartFile.Reader` 或 `Bytes` 的文件上传路径。

不影响：

- Go server multipart 接收侧的安全上限和 server config。
- Go binary schema request body，当前已使用 `io.Pipe` 写入。
- Go `byte_stream` response，当前返回 `io.ReadCloser`。
- Java / Kotlin / Flutter / Python 的 multipart stream/file 输入路径。
- TypeScript 的 `FormData` 路径，因为其内存模型由目标 runtime 决定，且可通过 custom fetcher / transport 替换。

## Client 端性能评估

| Target | 结论 | 说明 |
| --- | --- | --- |
| Go HTTP | 存在中风险 multipart 缺口。 | `context.Context`、`*http.Client` 注入、raw stream response 都成立；问题集中在 multipart encoder 全量 buffer。 |
| TypeScript HTTP/Wails | 未确认生成器层致命瓶颈。 | HTTP `fetcher` / `RequestInit` 可替换底层策略；Wails timeout 只控制前端等待，不是 native cancellation。浏览器 `FormData` 的 buffering 属于 runtime 边界。 |
| Flutter HTTP | 未确认致命瓶颈。 | `Stream<List<int>>` response 和 `ApiFilePart.fromStream` 可用；`readAllBytes()` 是便利方法，不应作为大流默认路径。 |
| Kotlin HTTP | 未确认致命瓶颈。 | OkHttp client 可注入；multipart/file 与 stream response 走原生机制。per-call timeout 当前通过 `httpClient.newBuilder().callTimeout(...).build()`，有对象创建成本，但属于低风险、可通过默认 timeout 或注入 client 优化。 |
| Java HTTP | 未确认致命瓶颈。 | JDK `HttpClient` 可注入；`byte_stream` 使用 `BodyHandlers.ofInputStream()`；typed binary body 调用 `toBytes()` 是 binary schema buffered 契约，不等同于 raw stream。 |
| Python HTTP | 未确认致命瓶颈。 | `httpx.AsyncClient` 可注入；multipart file-like payload 分块读取；stream response 需要用户按协议关闭。 |
| gRPC client | 不属于 api-blueprint generated client 范围。 | 性能、deadline、backpressure 使用 native gRPC client/channel/interceptor。 |

## Server 端性能评估

| Target | 结论 | 说明 |
| --- | --- | --- |
| Go HTTP | 未确认新增性能缺口。 | 已有 server config 覆盖 request body、multipart memory/file、decompressed binary、WebSocket origin/compression 等边界；长连接仍由业务正确关闭和宿主 server 配置兜底。 |
| Java Spring | 未确认新增性能缺口。 | 已有 `GenSpringServerConfig`、bounded inbound queue、executor hook、multipart limit；默认 executor fallback 仍是生产调优点，但有 bean 覆盖路径。 |
| Kotlin Ktor | 未确认新增性能缺口。 | `ApiServerConfig` 提供 multipart/binary/WebSocket limit；file part 使用 stream/file wrapper 后避免无条件 bytes 展开。 |
| Python FastAPI | 未确认新增性能缺口。 | `ApiServerConfig` 覆盖 body/multipart/SSE queue/WebSocket message；JSON/binary body buffered 是 unary request 契约。 |
| Wails | 不复用 HTTP raw media server adapter。 | 性能瓶颈主要属于 app shell、Go service、IPC 消息大小和宿主业务实现。 |
| gRPC | 不生成额外 server runtime guard。 | streaming backpressure、max message size、flow control、deadline 走 native gRPC 配置。 |

## 冗余设计 / 过度设计评估

未确认存在会导致普遍性能恶化的过度抽象。

当前生成物的 route client、transport interface、request options、raw response wrapper、stream wrapper 和 error helper 都有明确职责。它们会带来少量对象分配，但换取了跨端一致协议契约、可测试性和可替换 transport，不属于需要立即移除的冗余层。

需要注意的边界：

- 聚合 client / barrel / facade 适合发现能力，不适合极致裁剪；生产项目应按 0005 / 0006 的结论使用窄入口。
- `readAllBytes()` / `readBytes()` / `toBytes()` 便利方法只适合小对象或测试；大响应、大文件、大流应使用 stream API。
- SDK smoke 不是吞吐压测，不能证明 generated client 在高并发下没有性能回归。

## Conformance 覆盖边界

当前 conformance 覆盖面较广，已包含：

- 常规 RPC、raw、XML、static、header、scalar、enum、map、deprecated、form。
- binary schema request / response、audit binary、bad binary。
- media multipart、file/raw response、byte stream、filename edge、raw success / typed error。
- request options。
- SSE、WebSocket、single-channel、malformed websocket、early close。
- bad JSON、bad query、naming conflict。

这些覆盖可以证明协议正确性和跨端互操作，但不能等价为性能覆盖。当前明确边界是：

- `protocol` benchmark 直打 server HTTP 路径，不通过 generated clients。
- `sdk-smoke` 只覆盖 generated client 最小热路径，不输出吞吐、延迟分位或内存指标。
- 没有大 multipart 上传的内存回归测试。
- 没有 `byte_stream` 长流、首 chunk 后取消、客户端关闭后的 server 释放性能测试。
- 没有 SSE / WebSocket 高并发、慢消费者、队列回压、消息大小边界的 benchmark。
- Java / Python client 对长连接场景显示为 `unsupported-contract`，这是显式能力边界，不是隐藏缺口；Go 长连接 client 当前是 raw probe，不是 native generated long-connection client。

## Benchmark 覆盖边界

当前 benchmark 工具可用，但定位是趋势和 smoke：

- `binary` 覆盖 Go / TypeScript / Python / Kotlin / Java binary schema codec。
- `protocol` 覆盖 Go / Java / Kotlin / Python server 的 `rpc-json`、`form`、`binary`、`typed-error`，使用 `httpx.AsyncClient` 直打 server。
- `sdk-smoke` 覆盖 request options、binary response、media 的 generated client 调用 smoke。

已执行验证：

```bash
uv run python -m scripts.example_conformance list
uv run python -m scripts.example_benchmark list
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark binary --target all --count 1
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark protocol --servers go --scenario rpc-json,binary --requests 5 --concurrency 2 --warmup 1
```

结果摘要：

- conformance registry 可列出 servers、clients 和 scenarios。
- benchmark registry 可列出 binary targets、protocol scenarios、sdk smoke scenarios。
- binary smoke 全 target 通过。
- Go protocol smoke 的 `rpc-json` / `binary` 都返回 `errors=0`。

## 兼容性 / 修复风险

Go multipart 修复建议保持 public API 不变：

- 保留 `runtime.MultipartFile{Reader, Bytes}`。
- 将 `encodeMultipart` 改为基于 `io.Pipe` + `multipart.Writer` 的 streaming encoder。
- 对无法预计算 length 的 multipart 返回 `contentLength = -1`，使用 chunked transfer。
- 对 bytes-only 小文件可继续允许正常发送，但不应为了计算 content length 而强制整体 buffer。
- goroutine 中写 multipart 时用 `CloseWithError` 传播 `writeMultipartFields` / `writer.Close()` 错误。

潜在风险：

- 某些 server 或 proxy 可能更偏好固定 `Content-Length`，但 Go `net/http` 对 unknown length request body 是正常支持路径。
- 如果后续需要固定 length，可在只包含 strings / bytes / known-size files 时单独实现 length precompute，不能牺牲 reader stream 语义。
- 测试需要覆盖 reader 在 request 消费前不会被完整读完，避免只做文本断言。

## 是否建议修复

建议修复。

Go multipart issue 是确认的性能语义缺口，且与 public API 的 `Reader` 预期相冲突。修复可以不破坏现有 API，只调整 transport 内部编码方式。

同时建议补充性能覆盖，但不建议把 conformance 变成负载测试。更合理的方式是新增 benchmark/probe 层：

- generated SDK multipart 大文件 / reader streaming smoke。
- `byte_stream` 首 chunk 后关闭 / 取消 smoke。
- SSE / WebSocket 慢消费者和 bounded queue probe。
- generated SDK request-options / media / binary-response 的轻量吞吐 benchmark。

## 后续处置建议

1. 新增 plan 修复 Go client multipart streaming encoder。
2. 为 Go client transport 增加 codegen/runtime 测试，证明 multipart reader 不再通过 `bytes.Buffer` 全量编码。
3. 扩展 benchmark 或新增 probe，覆盖大 multipart、`byte_stream` cancel、长连接慢消费者。
4. 修复完成后运行：

```bash
uv run pytest tests/codegen/go tests/codegen/shared -q
uv run python -m compileall src/api_blueprint -q
uv run api-gen check -c examples/api-blueprint.toml
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_validation --mode refresh --scope blueprint
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_conformance run --servers go,java,kotlin,python --clients go,typescript,kotlin,flutter,java,python --scenario request-options,media,media-filename-edge,media-error,binary-response,audit-binary
env GOROOT=/Users/zsa/.gvm/gos/go1.25.2 uv run python -m scripts.example_benchmark binary --target all --count 1
```

修复闭环后，将本记录移动到 `docs/reviews/resolved/`，并追加 Resolution，记录 Go multipart streaming 修复、覆盖补测和验证命令。
