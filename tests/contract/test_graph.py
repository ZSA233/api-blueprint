from __future__ import annotations

import pytest

from api_blueprint.contract import (
    RouteContract,
    build_agent_manifest,
    build_contract_graph,
    build_contract_shards,
    render_agent_markdown,
    route_contract,
)
from api_blueprint.engine import Blueprint, Error, Toast
from api_blueprint.engine.connection import ConnectionDelivery, ConnectionScope
from api_blueprint.engine.model import Int, String, Model, field
from api_blueprint.writer.core import contracts as legacy_contracts
from api_blueprint.writer.core.contract_adapters import RouteContractIndex


class OpenRequest(Model):
    run_id = String(description="run id")


class StreamState(Model):
    status = String(description="status")


class StreamDone(Model):
    message = String(description="message")


class CloseInfo(Model):
    code = Int(description="code")
    reason = String(description="reason", omitempty=True)


class GenericContractPayload(Model):
    name = field(1, String(description="name"), optional=True)
    success = field(2, String(description="success"), choice="result")
    error = field(3, String(description="error"), choice="result")


def test_contract_graph_manifest_captures_rpc_and_connection_routes():
    bp = Blueprint(root="/api")
    with bp.group("/runs") as views:
        views.GET("/status").RSP(message=String(description="message"))
        views.STREAM("/events", scope=ConnectionScope.SESSION).OPEN(OpenRequest).SERVER_MESSAGE(
            "RunStreamMessage",
            state=StreamState,
            done=StreamDone,
        ).CLOSE(CloseInfo)

    graph = build_contract_graph([bp])
    manifest = graph.to_manifest()

    assert manifest["version"] == "2.0"
    assert manifest["generator"]["name"] == "api-blueprint"
    assert [service["id"] for service in manifest["services"]] == ["api.runs"]
    route_ids = [route["id"] for route in manifest["routes"]]
    assert route_ids == ["api.runs.get.status", "api.runs.stream.events"]

    status = manifest["routes"][0]
    assert status["kind"] == "rpc"
    assert status["response"]["media_type"] == "application/json"
    assert status["response"]["model"] == "RSP_Status"

    stream = manifest["routes"][1]
    assert stream["kind"] == "stream"
    assert stream["connection"]["scope"] == "session"
    assert stream["connection"]["delivery"] == "ordered"
    assert stream["connection"]["open_model"] == "OpenRequest"
    assert stream["connection"]["close_model"] == "CloseInfo"
    assert stream["connection"]["server_message"]["name"] == "RunStreamMessage"
    assert [variant["key"] for variant in stream["connection"]["server_message"]["variants"]] == ["state", "done"]

    schema = manifest["schemas"]["CloseInfo"]
    assert schema["fields"]["reason"]["optional"] is True
    assert len(manifest["hashes"]["routes"]["api.runs.stream.events"]) == 64


def test_contract_graph_manifest_carries_declared_connection_delivery():
    bp = Blueprint(root="/api")
    with bp.group("/runs") as views:
        views.STREAM("/events").SERVER_MESSAGE(StreamState)
        views.CHANNEL("/chat", delivery=ConnectionDelivery.UNORDERED).SERVER_MESSAGE(StreamState).CLIENT_MESSAGE(
            StreamDone
        )

    manifest = build_contract_graph([bp]).to_manifest()
    routes = {route["id"]: route for route in manifest["routes"]}

    assert routes["api.runs.stream.events"]["connection"]["delivery"] == "ordered"
    assert routes["api.runs.channel.chat"]["connection"]["delivery"] == "unordered"


def test_route_contract_preserves_explicit_operation_id_casing_variants():
    bp = Blueprint(root="/api")
    with bp.group("/pascal") as views:
        pascal_router = views.GET("/events", operation_id="TaskEvents").RSP(message=String(description="message"))
    with bp.group("/camel") as views:
        camel_router = views.GET("/events", operation_id="taskEvents").RSP(message=String(description="message"))
    with bp.group("/snake") as views:
        snake_router = views.GET("/events", operation_id="task_events").RSP(message=String(description="message"))

    assert route_contract(pascal_router).func_name == "TaskEvents"
    assert route_contract(camel_router).func_name == "TaskEvents"
    assert route_contract(snake_router).func_name == "TaskEvents"


def test_contract_graph_disambiguates_same_path_http_methods_and_route_contract_index_resolves_them():
    bp = Blueprint(root="/api")
    with bp.group("/settings") as views:
        get_router = views.GET("/current").RSP(message=String(description="message"))
        put_router = views.PUT("/current").RSP(message=String(description="message"))

    graph = build_contract_graph([bp])
    manifest = graph.to_manifest()
    routes_by_id = {route["id"]: route for route in manifest["routes"]}

    assert routes_by_id["api.settings.get.current"]["operation"] == "CurrentGet"
    assert routes_by_id["api.settings.get.current"]["method_name"] == "currentGet"
    assert routes_by_id["api.settings.put.current"]["operation"] == "CurrentPut"
    assert routes_by_id["api.settings.put.current"]["method_name"] == "currentPut"

    route_index = RouteContractIndex.from_graph(graph)
    assert route_index.protocol_for_router(get_router).route.func_name == "CurrentGet"
    assert route_index.protocol_for_router(put_router).route.func_name == "CurrentPut"


def test_contract_graph_rejects_duplicate_explicit_operation_names_in_same_group():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/events", operation_id="TaskEvents").RSP(message=String(description="message"))
        views.PUT("/events", operation_id="TaskEvents").RSP(message=String(description="message"))

    with pytest.raises(ValueError, match="duplicate operation name.*TaskEvents"):
        build_contract_graph([bp])


def test_contract_graph_manifest_captures_error_catalog_and_route_visibility():
    class CommonErr(Model):
        UNKNOWN = Error(-1, "unknown")
        TOKEN_EXPIRE = Error(
            55555,
            "token登录态失效",
            toast=Toast(
                key="auth.token_expire",
                default="登录状态已失效，请重新登录",
                level="warning",
            ),
        )

    class DemoErr(Model):
        BOOM = Error(1001, "boom")

    bp = Blueprint(root="/api", errors=[CommonErr])
    with bp.group("/demo") as views:
        views.GET("/ping").ERR(DemoErr).RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()
    agent = build_agent_manifest(manifest)
    shards = build_contract_shards(manifest)

    assert manifest["errors"] == [
        {
            "id": "CommonErr.UNKNOWN",
            "group": "CommonErr",
            "key": "UNKNOWN",
            "code": -1,
            "message": "unknown",
            "toast": {
                "key": "CommonErr.UNKNOWN",
                "default": "unknown",
                "level": "error",
            },
        },
        {
            "id": "CommonErr.TOKEN_EXPIRE",
            "group": "CommonErr",
            "key": "TOKEN_EXPIRE",
            "code": 55555,
            "message": "token登录态失效",
            "toast": {
                "key": "auth.token_expire",
                "default": "登录状态已失效，请重新登录",
                "level": "warning",
            },
        },
        {
            "id": "DemoErr.BOOM",
            "group": "DemoErr",
            "key": "BOOM",
            "code": 1001,
            "message": "boom",
            "toast": {
                "key": "DemoErr.BOOM",
                "default": "boom",
                "level": "error",
            },
        },
    ]
    assert "translations" not in manifest["errors"][1]["toast"]
    assert [error["id"] for error in manifest["routes"][0]["errors"]] == [
        "CommonErr.UNKNOWN",
        "CommonErr.TOKEN_EXPIRE",
        "DemoErr.BOOM",
    ]
    assert manifest["routes"][0]["errors"][1] == manifest["errors"][1]
    assert agent["counts"]["errors"] == 3
    assert agent["errors"] == manifest["errors"]
    assert agent["routes"][0]["errors"] == manifest["routes"][0]["errors"]
    assert shards["index.json"]["counts"]["errors"] == 3
    assert shards["routes/api.demo.get.ping.json"]["errors"] == manifest["routes"][0]["errors"]


def test_contract_graph_keeps_distinct_identities_for_same_named_models():
    AlphaPayload = type(
        "SharedPayload",
        (Model,),
        {
            "__module__": "blueprints.alpha",
            "value": String(description="value"),
        },
    )
    BetaPayload = type(
        "SharedPayload",
        (Model,),
        {
            "__module__": "blueprints.beta",
            "code": Int(description="code"),
        },
    )
    GammaPayload = type(
        "SharedPayload",
        (Model,),
        {
            "__module__": "blueprints.gamma",
            "label": String(description="label"),
        },
    )

    bp = Blueprint(root="/api")
    with bp.group("/alpha") as views:
        views.POST("/submit").REQ(AlphaPayload).RSP(message=String(description="message"))
    with bp.group("/beta") as views:
        views.POST("/submit").REQ(BetaPayload).RSP(message=String(description="message"))
    with bp.group("/gamma") as views:
        views.POST("/submit").REQ(GammaPayload).RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()

    alpha_route, beta_route, gamma_route = manifest["routes"]
    alpha_schema = alpha_route["request"]["json_model"]
    beta_schema = beta_route["request"]["json_model"]
    gamma_schema = gamma_route["request"]["json_model"]
    assert alpha_schema != beta_schema
    assert beta_schema != gamma_schema
    assert gamma_schema == "blueprints.gamma.SharedPayload"
    assert manifest["schemas"][alpha_schema]["identity"] == "blueprints.alpha.SharedPayload"
    assert manifest["schemas"][beta_schema]["identity"] == "blueprints.beta.SharedPayload"
    assert manifest["schemas"][gamma_schema]["identity"] == "blueprints.gamma.SharedPayload"
    assert manifest["schemas"][alpha_schema]["module"] == "blueprints.alpha"
    assert manifest["schemas"][beta_schema]["module"] == "blueprints.beta"
    assert manifest["schemas"][gamma_schema]["module"] == "blueprints.gamma"


def test_contract_graph_rewrites_same_route_same_named_model_refs():
    RequestPayload = type(
        "SharedPayload",
        (Model,),
        {
            "__module__": "blueprints.request",
            "value": String(description="value"),
        },
    )
    ResponsePayload = type(
        "SharedPayload",
        (Model,),
        {
            "__module__": "blueprints.response",
            "message": String(description="message"),
        },
    )

    bp = Blueprint(root="/api")
    with bp.group("/shared") as views:
        views.POST("/submit").REQ(RequestPayload).RSP(ResponsePayload)

    manifest = build_contract_graph([bp]).to_manifest()

    route = manifest["routes"][0]
    assert route["request"]["json_model"] == "blueprints.request.SharedPayload"
    assert route["response"]["model"] == "blueprints.response.SharedPayload"
    assert set(manifest["schemas"]) >= {
        "blueprints.request.SharedPayload",
        "blueprints.response.SharedPayload",
    }


def test_contract_graph_uses_generic_field_contract_metadata():
    bp = Blueprint(root="/api")
    with bp.group("/contract") as views:
        views.POST("/submit").REQ(GenericContractPayload).RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()

    fields = manifest["schemas"]["GenericContractPayload"]["fields"]
    assert fields["name"]["contract"] == {"field_id": 1, "optional": True}
    assert fields["success"]["contract"] == {"field_id": 2, "choice": "result"}
    assert fields["error"]["contract"] == {"field_id": 3, "choice": "result"}
    assert "wire" not in fields["name"]
    assert "proto" not in fields["success"]


def test_agent_manifest_and_shards_are_compact_navigation_layers():
    bp = Blueprint(root="/api")
    with bp.group("/runs") as views:
        views.GET("/status").RSP(message=String(description="message"))
        views.STREAM("/events", scope=ConnectionScope.SESSION).OPEN(OpenRequest).SERVER_MESSAGE(
            "RunStreamMessage",
            state=StreamState,
            done=StreamDone,
        ).CLOSE(CloseInfo)

    graph = build_contract_graph([bp])
    graph.targets = [
        {
            "id": "go.server",
            "kind": "go-server",
            "out_dir": "golang",
            "module": "example.com/project/golang",
        },
        {
            "id": "go.client",
            "kind": "go-client",
            "out_dir": "golang/client",
            "module": "example.com/project/golang/client",
        },
        {
            "id": "typescript.client",
            "kind": "typescript-client",
            "out_dir": "typescript",
        },
        {
            "id": "kotlin.client",
            "kind": "kotlin-client",
            "out_dir": "kotlin",
            "package": "com.example.generated",
        },
        {
            "id": "java.client",
            "kind": "java-client",
            "out_dir": "java/client",
            "package": "com.example.generated",
        },
        {
            "id": "java.server",
            "kind": "java-server",
            "out_dir": "java/server",
            "package": "com.example.generated",
        },
        {
            "id": "python.client",
            "kind": "python-client",
            "out_dir": "python/client",
            "python_package_root": "client_app",
        },
        {
            "id": "python.server",
            "kind": "python-server",
            "out_dir": "python/server",
            "python_package_root": "server_app",
        },
        {
            "id": "grpc.python",
            "kind": "grpc-python",
            "out_dir": "grpc/python",
            "python_package_root": "pb",
        },
    ]
    manifest = graph.to_manifest()

    agent = build_agent_manifest(manifest)
    shards = build_contract_shards(manifest)
    markdown = render_agent_markdown(manifest)

    assert agent["version"] == "2.0"
    assert agent["generator"]["name"] == "api-blueprint"
    assert agent["counts"] == {
        "services": 1,
        "routes": 2,
        "schemas": 5,
        "errors": 0,
        "connections": 1,
        "targets": 9,
    }
    assert agent["read_order"][0]["path"] == "api-gen inspect"
    assert agent["shards"]["index"] == "api-blueprint.contract.d/index.json"
    stream_summary = next(route for route in agent["routes"] if route["id"] == "api.runs.stream.events")
    assert stream_summary["shard"] == "api-blueprint.contract.d/routes/api.runs.stream.events.json"
    assert stream_summary["schemas"] == ["CloseInfo", "OpenRequest", "StreamDone", "StreamState"]
    assert stream_summary["artifacts"]["go.server"]["files"] == [
        "golang/routes/api/runs/gen_interface.go",
        "golang/routes/api/runs/gen_types.go",
    ]
    assert stream_summary["artifacts"]["go.server"]["imports"] == [
        "example.com/project/golang/routes/api/runs",
    ]
    assert stream_summary["artifacts"]["go.client"]["files"] == [
        "golang/client/routes/api/runs/gen_types.go",
        "golang/client/routes/api/runs/gen_client.go",
        "golang/client/routes/api/runs/client.go",
        "golang/client/transports/http/gen_transport.go",
        "golang/client/transports/http/client.go",
    ]
    assert stream_summary["artifacts"]["go.client"]["imports"] == [
        "example.com/project/golang/client/routes/api/runs",
    ]
    assert stream_summary["artifacts"]["grpc.python"]["imports"] == [
        "pb.api.runs_pb2",
        "pb.api.runs_pb2_grpc",
    ]
    assert stream_summary["artifacts"]["kotlin.client"]["files"] == [
        "kotlin/com/example/generated/api/routes/api/runs/RunsTypes.kt",
        "kotlin/com/example/generated/api/routes/api/runs/GenRunsApi.kt",
        "kotlin/com/example/generated/api/routes/api/runs/RunsApi.kt",
    ]
    assert stream_summary["artifacts"]["java.client"]["files"] == [
        "java/client/com/example/generated/api/routes/api/runs/RunsTypes.java",
        "java/client/com/example/generated/api/routes/api/runs/GenRunsApi.java",
        "java/client/com/example/generated/api/routes/api/runs/RunsApi.java",
        "java/client/com/example/generated/api/transports/http/GenJdkHttpApiTransport.java",
        "java/client/com/example/generated/api/transports/http/HttpApiClient.java",
    ]
    assert stream_summary["artifacts"]["java.client"]["imports"] == [
        "com.example.generated.api.routes.api.runs.RunsApi",
    ]
    assert stream_summary["artifacts"]["java.server"]["files"] == [
        "java/server/com/example/generated/api/routes/api/runs/GenRunsService.java",
        "java/server/com/example/generated/api/routes/api/runs/RunsTypes.java",
        "java/server/com/example/generated/api/routes/api/runs/RunsServiceStub.java",
        "java/server/com/example/generated/api/routes/api/runs/RunsService.java",
        "java/server/com/example/generated/api/transports/http/api/runs/GenRunsController.java",
    ]
    assert stream_summary["artifacts"]["java.server"]["imports"] == [
        "com.example.generated.api.routes.api.runs.RunsService",
        "com.example.generated.api.transports.http.api.runs.GenRunsController",
    ]
    assert stream_summary["artifacts"]["python.client"]["files"] == [
        "python/client/client_app/api/routes/api/runs/gen_client.py",
        "python/client/client_app/api/routes/api/runs/gen_types.py",
        "python/client/client_app/api/routes/api/runs/client.py",
        "python/client/client_app/api/transports/http/gen_client.py",
    ]
    assert stream_summary["artifacts"]["python.server"]["files"] == [
        "python/server/server_app/api/routes/api/runs/gen_service.py",
        "python/server/server_app/api/routes/api/runs/service.py",
        "python/server/server_app/api/transports/http/gen_server.py",
        "python/server/server_app/api/transports/http/server.py",
    ]
    route_shard = shards["routes/api.runs.stream.events.json"]
    assert sorted(route_shard["schemas"]) == ["CloseInfo", "OpenRequest", "StreamDone", "StreamState"]
    assert route_shard["connection"]["kind"] == "stream"
    assert route_shard["artifacts"]["typescript.client"]["files"]
    assert shards["index.json"]["counts"]["routes"] == 2
    assert "优先使用 `api-gen inspect` 按需查询 route/schema/files/errors" in markdown
    assert "`api-gen inspect route <route_id> [<route_id> ...] -c api-blueprint.toml`" in markdown


def test_contract_artifacts_use_shared_selection_and_python_root_group_paths():
    bp = Blueprint(root="/api")
    with bp.group("/") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()
    manifest["routes"][0]["tags"] = ["api"]
    manifest["targets"] = [
        {
            "id": "kotlin.client",
            "kind": "kotlin-client",
            "out_dir": "kotlin",
            "package": "com.example.generated",
            "include": ["tag:api"],
        },
        {
            "id": "java.client",
            "kind": "java-client",
            "out_dir": "java/client",
            "package": "com.example.generated",
        },
        {
            "id": "java.server",
            "kind": "java-server",
            "out_dir": "java/server",
            "package": "com.example.generated",
        },
        {
            "id": "python.client",
            "kind": "python-client",
            "out_dir": "python/client",
            "python_package_root": "client_app",
        },
        {
            "id": "python.server",
            "kind": "python-server",
            "out_dir": "python/server",
            "python_package_root": "server_app",
        },
    ]

    agent = build_agent_manifest(manifest)
    route_summary = agent["routes"][0]

    assert route_summary["artifacts"]["kotlin.client"]["files"] == [
        "kotlin/com/example/generated/api/routes/api/ApiTypes.kt",
        "kotlin/com/example/generated/api/routes/api/GenApiApi.kt",
        "kotlin/com/example/generated/api/routes/api/ApiApi.kt",
    ]
    assert route_summary["artifacts"]["java.client"]["files"] == [
        "java/client/com/example/generated/api/routes/api/ApiTypes.java",
        "java/client/com/example/generated/api/routes/api/GenApiApi.java",
        "java/client/com/example/generated/api/routes/api/ApiApi.java",
        "java/client/com/example/generated/api/transports/http/GenJdkHttpApiTransport.java",
        "java/client/com/example/generated/api/transports/http/HttpApiClient.java",
    ]
    assert route_summary["artifacts"]["java.client"]["imports"] == [
        "com.example.generated.api.routes.api.ApiApi",
    ]
    assert route_summary["artifacts"]["java.server"]["files"] == [
        "java/server/com/example/generated/api/routes/api/GenApiService.java",
        "java/server/com/example/generated/api/routes/api/ApiTypes.java",
        "java/server/com/example/generated/api/routes/api/ApiServiceStub.java",
        "java/server/com/example/generated/api/routes/api/ApiService.java",
        "java/server/com/example/generated/api/transports/http/api/GenApiController.java",
    ]
    assert route_summary["artifacts"]["java.server"]["imports"] == [
        "com.example.generated.api.routes.api.ApiService",
        "com.example.generated.api.transports.http.api.GenApiController",
    ]
    assert route_summary["artifacts"]["python.client"]["files"] == [
        "python/client/client_app/api/routes/api/gen_client.py",
        "python/client/client_app/api/routes/api/gen_types.py",
        "python/client/client_app/api/routes/api/client.py",
        "python/client/client_app/api/transports/http/gen_client.py",
    ]
    assert route_summary["artifacts"]["python.client"]["imports"] == [
        "client_app.api.routes.api.client",
    ]
    assert route_summary["artifacts"]["python.server"]["files"] == [
        "python/server/server_app/api/routes/api/gen_service.py",
        "python/server/server_app/api/routes/api/service.py",
        "python/server/server_app/api/transports/http/gen_server.py",
        "python/server/server_app/api/transports/http/server.py",
    ]


def test_contract_artifacts_do_not_claim_grpc_outputs_for_legacy_ws_routes():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.WS("/ws").SEND(StreamState).RECV(StreamDone)

    manifest = build_contract_graph([bp]).to_manifest()
    manifest["targets"] = [
        {
            "id": "grpc.proto",
            "kind": "grpc-proto",
            "out_dir": "grpc/protos",
        },
        {
            "id": "grpc.python",
            "kind": "grpc-python",
            "out_dir": "grpc/python",
            "python_package_root": "pb",
        },
    ]

    agent = build_agent_manifest(manifest)

    assert agent["routes"][0]["kind"] == "legacy_ws"
    assert "grpc.proto" not in agent["routes"][0]["artifacts"]
    assert "grpc.python" not in agent["routes"][0]["artifacts"]


def test_contract_route_contract_is_the_writer_core_compat_source():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.GET("/ping").RSP(message=String(description="message"))

    contract = route_contract(router)

    assert isinstance(contract, RouteContract)
    assert contract.route_id == "api.demo.get.ping"
    assert legacy_contracts.RouteContract is RouteContract
    assert legacy_contracts.route_contract is route_contract


def test_contract_graph_diff_classifies_breaking_and_compatible_changes():
    before = {
        "routes": [
            {"id": "api.demo.get.ping", "hash": "old"},
            {"id": "api.demo.get.removed", "hash": "gone"},
        ],
        "schemas": {
            "Payload": {
                "fields": {
                    "name": {"type": "string", "optional": False},
                }
            }
        },
    }
    after = {
        "routes": [
            {"id": "api.demo.get.ping", "hash": "new"},
        ],
        "schemas": {
            "Payload": {
                "fields": {
                    "name": {"type": "string", "optional": False},
                    "nickname": {"type": "string", "optional": True},
                    "required_extra": {"type": "string", "optional": False},
                }
            }
        },
    }

    diff = build_contract_graph.diff_manifests(before, after)

    assert "route removed: api.demo.get.removed" in diff["breaking"]
    assert "route changed: api.demo.get.ping" in diff["risky"]
    assert "optional field added: Payload.nickname" in diff["compatible"]
    assert "required field added: Payload.required_extra" in diff["breaking"]
