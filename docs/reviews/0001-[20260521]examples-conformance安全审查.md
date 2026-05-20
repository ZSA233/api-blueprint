# examples/conformance 安全审查

- 编号：0001
- 状态：open
- 发现日期：2026-05-21
- 来源：examples DSL 覆盖面、example conformance 矩阵、生成服务端/客户端接口安全审查
- 影响范围：examples 生成物、Python server、Java server、Kotlin server、Python client、conformance 场景覆盖

## 背景

本次审查目标是确认 `examples/blueprints/` 是否已经覆盖真实使用中的边界场景，并检查各端生成的客户端/服务端接口在异常输入、长连接和跨端一致性下是否存在致命风险。

审查结论：当前 examples DSL 已覆盖较多生成形态，但 conformance 只验证了主干互通，尚不能证明所有 DSL 场景、异常输入、安全边界和各端行为一致。

## 风险分级

- 高风险：可能导致服务端 500、长连接任务泄漏、用户按生成接口实现后直接踩到错误契约。
- 中风险：跨端行为不一致、异常输入没有稳定协议错误、客户端类型体验不一致。
- 覆盖缺口：DSL 已声明或生成物已存在，但没有真实互通或异常路径验证。

## 已确认问题

### 1. Python server binary service contract 与 HTTP adapter 不一致

- 风险等级：高
- 涉及文件：
  - `examples/python/server/api_blueprint_example_server/api/routes/api/binary/gen_service.py`
  - `examples/python/server/api_blueprint_example_server/api/transports/http/gen_server.py`
  - `examples/python/conformance/server_app.py`
- 现象：生成的 `BinaryService` Protocol 声明 `binary: dict[str, Any] | None`，但 HTTP adapter 实际传入原始 `bytes`。当前 conformance preserved server 也按 bytes 实现，因此绕过了生成契约不一致问题。
- 复现场景：用户按生成的 `BinaryService` Protocol 实现 `packet(query, binary: dict | None)`，随后请求 `POST /api/binary/packet`，服务会收到 bytes 而不是 dict，业务实现容易抛异常并返回 500。
- 处置建议：修复 Python server binary service 类型契约，并补一个 conformance 或单测，确认 generated service contract 与 adapter 传参类型一致。

### 2. Python server 对坏 JSON 没有协议级兜底

- 风险等级：高
- 涉及文件：
  - `examples/python/server/api_blueprint_example_server/api/transports/http/gen_server.py`
- 现象：`_json_body()` 直接执行 `json.loads(body.decode("utf-8"))`，且 route 在进入 `try/except ApiError` 之前调用它。坏 JSON 会成为未包装异常。
- 复现场景：

```bash
curl -i \
  -X POST 'http://127.0.0.1:<port>/api/demo/test_post' \
  -H 'Content-Type: application/json' \
  --data '{'
```

- 预期：返回稳定的协议错误或明确 4xx。
- 当前风险：返回未包装的 `JSONDecodeError` 路径，通常表现为 500。
- 处置建议：在 generated FastAPI adapter 中把 JSON decode 错误转成稳定错误响应，并补坏 JSON conformance 场景。

### 3. Java server WebSocket receive 可能长期阻塞

- 风险等级：高
- 涉及文件：
  - `examples/java/server/com/example/apiblueprint/api/transports/http/api/demo/GenDemoController.java`
  - `examples/java/conformance/ServerApp.java`
- 现象：`SpringWebSocketChannel.receive()` 使用 `incoming.take()` 无限阻塞。连接关闭时 handler 只移除 channel，没有向队列写入关闭哨兵或中断等待中的业务任务。示例服务端会连续调用两次 `receive()`。
- 复现场景：连接 `/api/demo/assistant-session?session_id=x`，发送一次 `input` 后直接断开，不发送 `cancel`。第二次 `receive()` 会长期挂住。重复连接可能累积异步任务或线程资源。
- 处置建议：连接关闭时唤醒等待中的 receive，或让 receive 支持关闭状态和超时/取消语义；补“连接提前断开”conformance 场景。

### 4. Java/Kotlin/Python malformed WebSocket frame 没有稳定 close/error 协议

- 风险等级：高
- 涉及文件：
  - `examples/java/server/com/example/apiblueprint/api/transports/http/api/demo/GenDemoController.java`
  - `examples/kotlin/server/com/example/apiblueprint/api/transports/ktor/api/demo/GenDemoKtorRoutes.kt`
  - `examples/python/server/api_blueprint_example_server/api/transports/http/gen_server.py`
- 现象：三端 WebSocket 接收路径都直接 decode 文本帧。收到 malformed JSON 或未知 shape 时，没有统一转换成稳定 close/abort 协议。
- 复现场景：连接 `/api/demo/assistant-session?session_id=x` 后发送 `not-json`。
- 预期：连接稳定关闭，并返回可识别 close payload 或明确 abort。
- 当前风险：route coroutine/task 异常退出；Java 还可能和 receive 阻塞问题组合导致等待任务残留。
- 处置建议：为 malformed frame 增加 decode 兜底和 close/abort 行为，并补 WebSocket malformed frame conformance。

### 5. Java/Kotlin 请求 decode 多数发生在 ApiError 捕获范围外

- 风险等级：中
- 涉及文件：
  - `examples/java/server/com/example/apiblueprint/api/transports/http/api/demo/GenDemoController.java`
  - `examples/kotlin/server/com/example/apiblueprint/api/transports/ktor/api/demo/GenDemoKtorRoutes.kt`
- 现象：query/json/form decode 通常在 `try/catch ApiError` 外执行。坏 query、坏 enum、坏 JSON 会进入框架异常路径，而不是协议层统一错误。
- 复现场景：

```bash
curl -i 'http://127.0.0.1:<port>/api/hello/abc?type=bad'
curl -i -X POST 'http://127.0.0.1:<port>/api/demo/test_post' -H 'Content-Type: application/json' --data '{'
```

- 处置建议：明确 decode 错误的协议策略，至少保证不以未包装 500 暴露；补 bad query/bad enum/bad JSON conformance。

### 6. Python client 嵌套 DTO 反序列化不严格

- 风险等级：中
- 涉及文件：
  - `examples/python/client/api_blueprint_example_client/api/routes/api/demo/gen_types.py`
  - `examples/python/client/api_blueprint_example_client/api/routes/api/demo/gen_client.py`
  - `examples/python/conformance/client.py`
- 现象：Python client 对嵌套 map/model 值没有严格还原为 dataclass。conformance 通过 `field()` helper 同时兼容 dict 和对象，说明类型行为与其他端不一致。
- 复现场景：调用 `api.demo.test_post(...)` 后读取 `post.map["req2"]`，该值可能是 dict，而不是生成 DTO。
- 处置建议：补 Python client nested DTO codec 测试，并统一嵌套 DTO 解码策略。

## 覆盖缺口

以下 DSL 或生成物场景已经存在，但当前 conformance 没有真实互通或异常路径覆盖：

- header/auth：`GeneralHeader.x_token` 有定义，但没有断言 header 透传或 provider 行为。
- NoEnvelope static routes：`/static/**` 生成存在，但未进入 conformance。
- deprecated route：`/api/demo/post_deprecated` 未互通验证。
- raw response：`/api/demo/raw` 未互通验证。
- XML route：`/api/demo/delete$` 在 scenario registry 中列入 `rpc`，但多数 harness 没有实际调用。
- scalar/map/enum routes：`/api/hello/string`、`/api/hello/uint64`、`/api/hello/map-enum`、`/api/hello/list-enum`、`/api/hello/string-emun`、`/api/hello/hello-way` 未真实断言。
- 第二个 binary schema：`/api/binary/audit-packet` 只生成，未互通验证。
- `/api/ws` 单模型 channel 未真实互通验证；当前只测 named variant channel `/api/demo/assistant-session`。
- malformed input：坏 JSON、坏 enum、坏 query、截断 binary、错误 binary magic、WebSocket malformed frame、SSE 中断都未作为 conformance 场景。

## 后续修复建议

1. 先补服务端异常输入安全 conformance：坏 JSON、坏 query/enum、截断 binary、坏 WebSocket frame、连接提前断开。
2. 修复 Python server binary service contract，使 generated Protocol 与 HTTP adapter 类型一致。
3. 修复 Java WebSocket receive 阻塞泄漏风险，并覆盖连接提前断开场景。
4. 为 Java/Kotlin/Python WebSocket decode 增加稳定 abort/close 行为。
5. 扩展 examples conformance 场景覆盖 raw/XML/static/header/audit-packet/scalar/enum/map/`/api/ws`。
6. 统一 Python client 嵌套 DTO 解码策略，移除 conformance 对 dict/object 双形态的容忍。

## 修复记录 / Resolution

当前状态为 open，尚未修复。修复闭环后将本文移动到 `docs/reviews/resolved/`，保留文件名，并在本节补充：

- 修复日期：
- 修复摘要：
- 验证命令：
- 相关 commit/PR：
