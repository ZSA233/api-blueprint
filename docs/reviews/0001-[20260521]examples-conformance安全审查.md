# examples/conformance 安全审查

- 编号：0001
- 状态：open
- 发现日期：2026-05-21
- 评估日期：2026-05-21
- 来源：examples DSL 覆盖面、example conformance 矩阵、生成服务端/客户端接口安全审查
- 影响范围：examples 生成物、Python server、Java server、Kotlin server、Python client、conformance 场景覆盖

## 背景

本次审查目标是确认 `examples/blueprints/` 是否已经覆盖真实使用中的边界场景，并检查各端生成的客户端/服务端接口在异常输入、长连接和跨端一致性下是否存在致命风险。

本记录不是必须全部修复的任务清单。每个条目都需要先判断问题是否真实存在、是否属于 bug、是否只是特征偏好、修复收益是否大于兼容性或实现风险。只有确认值得修复的条目才进入后续实现计划。

## 评估口径

- 真实 bug：当前生成物或 conformance 行为和已声明契约冲突，或会导致稳定性/安全边界问题。
- 测试债：DSL 或生成物已经覆盖某形态，但没有真实互通、异常输入或跨端一致性验证。
- 设计偏好：更一致、更强类型或更友好的行为，但当前行为未必违反契约。
- 暂缓修复：问题存在但修复会引入更大兼容性、复杂度或运行时边界风险，应先补验证或补文档。

## 评估摘要

| 条目 | 性质 | 存在性判断 | 是否建议修复 | 备注 |
| --- | --- | --- | --- | --- |
| Python server binary contract 与 adapter 不一致 | 真实 bug | 已确认 | 是 | 契约误导用户实现 |
| Python server 坏 JSON 未兜底 | 真实 bug | 已确认 | 是 | 需先明确错误响应策略 |
| Java WebSocket receive 长期阻塞 | 真实 bug | 已确认 | 是 | 修复需定义 close 后 receive 语义 |
| malformed WebSocket frame | bug + 协议策略 | 已确认风险 | 部分修复 | 至少避免泄漏/未处理异常，close payload 形态需谨慎 |
| Java/Kotlin decode 在 ApiError 捕获外 | 待验证风险 | 代码形态已确认 | 先补验证 | 不应为了 envelope 一致性强行扩大修复 |
| Python client 嵌套 DTO 不严格 | 设计/类型一致性问题 | 已确认 | 暂缓或低优先级 | 可能影响依赖 dict 的用户 |
| conformance 覆盖缺口 | 测试债 | 已确认 | 分阶段补齐 | 不等同于每个路由都有 bug |

## 评估详情

### 1. Python server binary service contract 与 HTTP adapter 不一致

- 风险等级：高
- 问题性质：真实 bug
- 存在性判断：已确认
- 是否建议修复：建议修复
- 涉及文件：
  - `examples/python/server/api_blueprint_example_server/api/routes/api/binary/gen_service.py`
  - `examples/python/server/api_blueprint_example_server/api/transports/http/gen_server.py`
  - `examples/python/conformance/server_app.py`
- 现象：生成的 `BinaryService` Protocol 声明 `binary: dict[str, Any] | None`，但 HTTP adapter 实际传入原始 `bytes`。当前 conformance preserved server 也按 bytes 实现，因此绕过了生成契约不一致问题。
- 复现场景：用户按生成的 `BinaryService` Protocol 实现 `packet(query, binary: dict | None)`，随后请求 `POST /api/binary/packet`，服务会收到 bytes 而不是 dict，业务实现容易抛异常并返回 500。
- 兼容性与修复风险：修复类型契约可能影响已经按当前错误类型提示写出的用户代码，但 Python server 仍是 preview target；保持错误契约会持续误导新实现，风险更高。
- 处置建议：修复 Python server binary service 类型契约，并补一个 conformance 或单测，确认 generated service contract 与 adapter 传参类型一致。

### 2. Python server 对坏 JSON 没有协议级兜底

- 风险等级：高
- 问题性质：真实 bug
- 存在性判断：已确认
- 是否建议修复：建议修复，但先明确错误响应策略
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
- 兼容性与修复风险：把 decode 错误统一包成业务 envelope 可能改变调用方对 400/500 的预期；直接返回 400 更符合 HTTP 输入错误，但需要确认各端 client 的错误解析路径。
- 处置建议：先补坏 JSON conformance，确认当前表现；再选择最小修复策略，优先避免未包装 500，而不是为了所有语言完全一致引入复杂错误策略。

### 3. Java server WebSocket receive 可能长期阻塞

- 风险等级：高
- 问题性质：真实 bug
- 存在性判断：已确认
- 是否建议修复：建议修复
- 涉及文件：
  - `examples/java/server/com/example/apiblueprint/api/transports/http/api/demo/GenDemoController.java`
  - `examples/java/conformance/ServerApp.java`
- 现象：`SpringWebSocketChannel.receive()` 使用 `incoming.take()` 无限阻塞。连接关闭时 handler 只移除 channel，没有向队列写入关闭哨兵或中断等待中的业务任务。示例服务端会连续调用两次 `receive()`。
- 复现场景：连接 `/api/demo/assistant-session?session_id=x`，发送一次 `input` 后直接断开，不发送 `cancel`。第二次 `receive()` 会长期挂住。重复连接可能累积异步任务或线程资源。
- 兼容性与修复风险：如果让 `receive()` 在关闭后返回 `null`，需要确认 `ApiServerChannel.receive()` 的 Java 契约是否允许空值；如果改成抛异常，需要确认 preserved service 的使用方式。不能为了修复泄漏而破坏用户已有服务代码的控制流。
- 处置建议：先把“连接关闭后 receive 如何结束”写成 Java server runtime 契约，再实现唤醒机制并补“连接提前断开”conformance。

### 4. Java/Kotlin/Python malformed WebSocket frame 没有稳定 close/error 协议

- 风险等级：高
- 问题性质：稳定性 bug + 协议策略待定
- 存在性判断：已确认风险；具体 close payload 是否必须统一仍需决策
- 是否建议修复：建议先修稳定性，不急于强制统一所有 close payload 形态
- 涉及文件：
  - `examples/java/server/com/example/apiblueprint/api/transports/http/api/demo/GenDemoController.java`
  - `examples/kotlin/server/com/example/apiblueprint/api/transports/ktor/api/demo/GenDemoKtorRoutes.kt`
  - `examples/python/server/api_blueprint_example_server/api/transports/http/gen_server.py`
- 现象：三端 WebSocket 接收路径都直接 decode 文本帧。收到 malformed JSON 或未知 shape 时，没有统一转换成稳定 close/abort 协议。
- 复现场景：连接 `/api/demo/assistant-session?session_id=x` 后发送 `not-json`。
- 当前风险：route coroutine/task 异常退出；Java 还可能和 receive 阻塞问题组合导致等待任务残留。
- 兼容性与修复风险：统一 close payload 是协议设计问题，可能影响已有 client 断言；但避免未处理异常、任务泄漏和连接悬挂属于稳定性修复，收益明确。
- 处置建议：第一阶段只要求 malformed frame 不造成未处理异常或任务泄漏，并用明确 close/abort 关闭连接；是否统一错误 payload 字段和 code 另行设计。

### 5. Java/Kotlin 请求 decode 多数发生在 ApiError 捕获范围外

- 风险等级：中
- 问题性质：待验证风险
- 存在性判断：代码形态已确认；实际是否违反契约需要运行验证
- 是否建议修复：先补验证，不直接修
- 涉及文件：
  - `examples/java/server/com/example/apiblueprint/api/transports/http/api/demo/GenDemoController.java`
  - `examples/kotlin/server/com/example/apiblueprint/api/transports/ktor/api/demo/GenDemoKtorRoutes.kt`
- 现象：query/json/form decode 通常在 `try/catch ApiError` 外执行。坏 query、坏 enum、坏 JSON 会进入框架异常路径，而不是协议层统一错误。
- 复现场景：

```bash
curl -i 'http://127.0.0.1:<port>/api/hello/abc?type=bad'
curl -i -X POST 'http://127.0.0.1:<port>/api/demo/test_post' -H 'Content-Type: application/json' --data '{'
```

- 兼容性与修复风险：很多 Web 框架本来就把 decode/binding error 映射为 400，这不一定是 bug。强行把所有 decode error 包成业务 envelope 可能混淆“协议输入错误”和“业务错误”，并改变 HTTP 语义。
- 处置建议：先补 conformance 验证各端状态码和 body 是否稳定、是否 500。只有出现 500、资源泄漏或 client 无法识别的非稳定行为时，再做最小修复。

### 6. Python client 嵌套 DTO 反序列化不严格

- 风险等级：中
- 问题性质：设计/类型一致性问题
- 存在性判断：已确认
- 是否建议修复：暂缓或低优先级，先补测试和兼容评估
- 涉及文件：
  - `examples/python/client/api_blueprint_example_client/api/routes/api/demo/gen_types.py`
  - `examples/python/client/api_blueprint_example_client/api/routes/api/demo/gen_client.py`
  - `examples/python/conformance/client.py`
- 现象：Python client 对嵌套 map/model 值没有严格还原为 dataclass。conformance 通过 `field()` helper 同时兼容 dict 和对象，说明类型行为与其他端不一致。
- 复现场景：调用 `api.demo.test_post(...)` 后读取 `post.map["req2"]`，该值可能是 dict，而不是生成 DTO。
- 兼容性与修复风险：把 dict 自动转成 dataclass 会提升类型体验，但可能破坏已经按 dict 使用 nested payload 的用户代码。Python client 是动态语言输出，是否强制深度 DTO 化属于 API 设计选择。
- 处置建议：先补 Python client nested DTO codec 测试，明确当前行为；后续如果要修，应考虑渐进策略或文档化的 breaking change，而不是直接切换所有 nested map/model 行为。

## 覆盖缺口评估

以下 DSL 或生成物场景已经存在，但当前 conformance 没有真实互通或异常路径覆盖。它们先按测试债处理，不默认判断为生成器 bug：

- header/auth：`GeneralHeader.x_token` 有定义，但没有断言 header 透传或 provider 行为。
- NoEnvelope static routes：`/static/**` 生成存在，但未进入 conformance。
- deprecated route：`/api/demo/post_deprecated` 未互通验证。
- raw response：`/api/demo/raw` 未互通验证。
- XML route：`/api/demo/delete$` 在 scenario registry 中列入 `rpc`，但多数 harness 没有实际调用。
- scalar/map/enum routes：`/api/hello/string`、`/api/hello/uint64`、`/api/hello/map-enum`、`/api/hello/list-enum`、`/api/hello/string-emun`、`/api/hello/hello-way` 未真实断言。
- 第二个 binary schema：`/api/binary/audit-packet` 只生成，未互通验证。
- `/api/ws` 单模型 channel 未真实互通验证；当前只测 named variant channel `/api/demo/assistant-session`。
- malformed input：坏 JSON、坏 enum、坏 query、截断 binary、错误 binary magic、WebSocket malformed frame、SSE 中断都未作为 conformance 场景。

覆盖缺口的处置原则：

1. 优先补会暴露服务端崩溃、资源泄漏或跨端协议破坏的场景。
2. 对 raw/XML/static/header/scalar/map/enum 等普通覆盖缺口，先补最小互通测试，再根据失败结果判断是否进入 bug 修复。
3. 不为了追求“覆盖所有路由”而生成大量脆弱测试；每个新增场景应对应一个明确 DSL 能力或历史风险。

## 后续建议

1. 先补服务端异常输入安全 conformance：坏 JSON、坏 query/enum、截断 binary、坏 WebSocket frame、连接提前断开。
2. 优先修复 Python server binary service contract，使 generated Protocol 与 HTTP adapter 类型一致。
3. 优先修复 Java WebSocket receive 阻塞泄漏风险，但先明确 close 后 receive 契约。
4. 对 malformed WebSocket frame，第一阶段只保证不泄漏、不悬挂、可关闭；错误 payload 是否统一另行设计。
5. 对 Java/Kotlin decode error，先验证是否 500 或不可预测，再决定是否修。
6. 对 Python client nested DTO，先作为类型一致性设计问题保留，不列入高优先级 bug 修复。
7. 扩展 examples conformance 时按风险分阶段覆盖 raw/XML/static/header/audit-packet/scalar/enum/map/`/api/ws`。

## 修复记录 / Resolution

当前状态为 open，尚未修复。修复闭环后将本文移动到 `docs/reviews/resolved/`，保留文件名，并在本节补充：

- 修复日期：
- 修复摘要：
- 验证命令：
- 相关 commit/PR：
