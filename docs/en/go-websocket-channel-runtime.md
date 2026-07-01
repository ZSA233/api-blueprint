# Go WebSocket Channel Runtime

This note records the runtime boundary of generated Go server `CHANNEL` code, so the handshake layer, raw connection, and route codec stay separate.

## Layers

Go WebSocket channels have three layers:

```text
gin route
  -> ConnectionHooks.AcceptChannel
  -> generated channel codec
  -> route impl / owner service
```

- `AcceptChannel` only owns the HTTP upgrade, origin, compression, and similar handshake policy. It returns a raw `provider.Connection`.
- `provider.Connection` only means a connection that can `ReadJSON`, `WriteJSON`, and `Close`. It does not store route envelope state.
- `CHANNEL(...)` creates the channel codec wrapper from the route `response_envelope`.
- Route implementations send and receive typed messages through `provider.Channel`; they do not depend directly on gorilla/coder websocket APIs.

## Envelope Semantics

By default, server channel messages are wrapped as:

```json
{"type":"message","data":{...}}
```

Close payloads are wrapped as:

```json
{"type":"close","data":{...}}
```

A channel declared with `response_envelope=NoEnvelope` skips this wrapper and reads or writes business JSON frames directly. This is useful when migrating an existing wire protocol such as `{"kind":"ping","payload":{...}}`.

## Why There Is No `SetEnvelope`

`HTTPWebSocketConnection` is a raw transport object and should not carry route-level mutable state. Generated code wraps it with the unexported `httpWebSocketChannelConnection`:

```text
raw provider.Connection
  -> httpWebSocketChannelConnection(envelope=true|false)
  -> provider.Channel
```

This keeps a few boundaries clear:

- `AcceptChannel` has a stable responsibility, so a custom hook does not need to know whether a route is `NoEnvelope`.
- Envelope behavior is route codec behavior, not connection handshake behavior.
- The runtime does not need an `interface{ SetEnvelope(bool) }` probe to mutate connection state.
- One hook can serve multiple routes without leaking envelope state between them.

## Integration Rules

- A custom `AcceptChannel` should return a raw connection and should not wrap frames as `{type,data}`.
- Use DSL `NoEnvelope` when a route must keep an existing business frame. Do not manually unwrap generated envelopes in the business implementation.
- Long-lived connection state, rooms, game loops, and reconnect policy belong in the owner service. api-blueprint provides the protocol entrypoint and typed channel.
- If a route needs a special binary protocol instead of raw WebSocket JSON frames, model it as a separate transport adapter instead of pretending it is a JSON channel.
