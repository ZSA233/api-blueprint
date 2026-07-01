# Go WebSocket Channel Runtime

本文记录 Go server `CHANNEL` 生成物的运行时边界，避免后续把握手、连接对象和 route codec 混在一起。

## 分层

Go WebSocket channel 分成三层：

```text
gin route
  -> ConnectionHooks.AcceptChannel
  -> generated channel codec
  -> route impl / owner service
```

- `AcceptChannel` 只负责 HTTP upgrade、origin/compression 等握手策略，并返回一个 raw `provider.Connection`。
- `provider.Connection` 只表示可以 `ReadJSON` / `WriteJSON` / `Close` 的连接，不保存 route envelope 状态。
- `CHANNEL(...)` 根据 route 的 `response_envelope` 创建 channel codec wrapper。
- route impl 只通过 `provider.Channel` 收发 typed message，不直接依赖 gorilla/coder websocket。

## Envelope 语义

默认 channel 会把服务端发送消息包装成：

```json
{"type":"message","data":{...}}
```

关闭 payload 会包装成：

```json
{"type":"close","data":{...}}
```

声明为 `response_envelope=NoEnvelope` 的 channel 不做这层包装，直接读写业务 JSON frame。这用于已经存在外部 wire 协议的场景，例如迁移旧系统时保留已有的 `{"kind":"ping","payload":{...}}` frame。

## 为什么没有 `SetEnvelope`

`HTTPWebSocketConnection` 是 raw transport，不应带 route 级可变状态。生成物使用 unexported `httpWebSocketChannelConnection` 包装 raw connection：

```text
raw provider.Connection
  -> httpWebSocketChannelConnection(envelope=true|false)
  -> provider.Channel
```

这样有几个好处：

- `AcceptChannel` 的职责稳定，custom hook 不需要知道 route 是否 `NoEnvelope`。
- envelope 是 route codec 行为，不是连接握手行为。
- 不需要通过 `interface{ SetEnvelope(bool) }` 这类运行时探测修改连接状态。
- 多个 route 共用同一个 hook 时不会互相污染。

## 接入规则

- 自定义 `AcceptChannel` 应返回 raw connection，不要自行套 `{type,data}`。
- 需要兼容旧业务 frame 时，在 DSL 上声明 `NoEnvelope`，不要在业务 impl 里手动拆 generated envelope。
- 业务层需要长连接状态、房间、游戏循环或重连策略时，应在 owner service 中实现；api-blueprint 只提供协议入口和 typed channel。
- 如果 route 需要 raw WebSocket frame 之外的特殊二进制协议，应单独建模 transport adapter，不要伪装成 JSON channel。
