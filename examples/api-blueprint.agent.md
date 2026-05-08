# api-blueprint Agent Guide

先读 `api-blueprint.agent.json`，再读 route shard，最后才看生成物。

## Read Order
1. `api-blueprint.agent.json` - Compact cross-service index for routes, schemas, connections, targets, and artifacts.
2. `api-blueprint.contract.d/index.json` - Shard directory index; use it when the compact route summary is not enough.
3. `api-blueprint.contract.d/routes/<route_id>.json` - Open the route shard for request/response models, connection messages, and target imports.
4. `generated artifacts` - Only inspect generated source when the artifact/import index points to a target-specific entry.

## Counts
- `services`: 4
- `routes`: 20
- `schemas`: 37
- `connections`: 2
- `targets`: 13

## Routes
- `api.api.ws.ws` `legacy_ws` `/api/ws` -> `api-blueprint.contract.d/routes/api.api.ws.ws.json`
- `api.demo.get.abc` `rpc` `/api/demo/abc` -> `api-blueprint.contract.d/routes/api.demo.get.abc.json`
- `api.demo.post.testpost` `rpc` `/api/demo/test_post` -> `api-blueprint.contract.d/routes/api.demo.post.testpost.json`
- `api.demo.put.z1put` `rpc` `/api/demo/1put` -> `api-blueprint.contract.d/routes/api.demo.put.z1put.json`
- `api.demo.delete.delete` `rpc` `/api/demo/delete$` -> `api-blueprint.contract.d/routes/api.demo.delete.delete.json`
- `api.demo.ws.ws` `legacy_ws` `/api/demo/ws` -> `api-blueprint.contract.d/routes/api.demo.ws.ws.json`
- `api.demo.stream.sweepevents` `stream` `/api/demo/sweep-events` -> `api-blueprint.contract.d/routes/api.demo.stream.sweepevents.json`
- `api.demo.channel.assistantsession` `channel` `/api/demo/assistant-session` -> `api-blueprint.contract.d/routes/api.demo.channel.assistantsession.json`
- `api.demo.post.postdeprecated` `rpc` `/api/demo/post_deprecated` -> `api-blueprint.contract.d/routes/api.demo.post.postdeprecated.json`
- `api.demo.post.raw` `rpc` `/api/demo/raw` -> `api-blueprint.contract.d/routes/api.demo.post.raw.json`
- `api.demo.post.mapmodel` `rpc` `/api/demo/map_model` -> `api-blueprint.contract.d/routes/api.demo.post.mapmodel.json`
- `api.hello.get.abc` `rpc` `/api/hello/abc` -> `api-blueprint.contract.d/routes/api.hello.get.abc.json`
- `api.hello.get.mapenum` `rpc` `/api/hello/map-enum` -> `api-blueprint.contract.d/routes/api.hello.get.mapenum.json`
- `api.hello.get.listenum` `rpc` `/api/hello/list-enum` -> `api-blueprint.contract.d/routes/api.hello.get.listenum.json`
- `api.hello.get.string` `rpc` `/api/hello/string` -> `api-blueprint.contract.d/routes/api.hello.get.string.json`
- `api.hello.get.uint64` `rpc` `/api/hello/uint64` -> `api-blueprint.contract.d/routes/api.hello.get.uint64.json`
- `api.hello.get.stringemun` `rpc` `/api/hello/string-emun` -> `api-blueprint.contract.d/routes/api.hello.get.stringemun.json`
- `api.hello.get.helloway` `rpc` `/api/hello/hello-way` -> `api-blueprint.contract.d/routes/api.hello.get.helloway.json`
- `static.static.get.docjson` `rpc` `/static/doc.json` -> `api-blueprint.contract.d/routes/static.static.get.docjson.json`
- `static.static.get.dochaha` `rpc` `/static/dochaha` -> `api-blueprint.contract.d/routes/static.static.get.dochaha.json`

## Generated Artifacts
Use route `artifacts` entries for import paths and generated files. Do not start by reading generated source.
