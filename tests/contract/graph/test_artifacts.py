from __future__ import annotations

from .helpers import *


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
            "id": "swift.client",
            "kind": "swift-client",
            "out_dir": "swift",
            "package": "ApiBlueprintExampleClient",
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
        "targets": 10,
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
        "kotlin/com/example/generated/api/routes/api/runs/GenRunsTypes.kt",
        "kotlin/com/example/generated/api/routes/api/runs/GenRunsApi.kt",
        "kotlin/com/example/generated/api/routes/api/runs/RunsApi.kt",
    ]
    assert stream_summary["artifacts"]["java.client"]["files"] == [
        "java/client/com/example/generated/api/routes/api/runs/GenRunsTypes.java",
        "java/client/com/example/generated/api/routes/api/runs/GenRunsApi.java",
        "java/client/com/example/generated/api/routes/api/runs/RunsApi.java",
        "java/client/com/example/generated/api/transports/http/GenJdkHttpApiTransport.java",
        "java/client/com/example/generated/api/transports/http/HttpApiClient.java",
    ]
    assert stream_summary["artifacts"]["java.client"]["imports"] == [
        "com.example.generated.api.routes.api.runs.RunsApi",
    ]
    assert stream_summary["artifacts"]["java.server"]["files"] == [
        "java/server/com/example/generated/api/annotations/ApiBlueprintOperation.java",
        "java/server/com/example/generated/api/annotations/api/runs/GenEvents.java",
        "java/server/com/example/generated/api/types/api/runs/GenRunsTypes.java",
        "java/server/com/example/generated/api/adapters/api/runs/GenRunsAdapters.java",
        "java/server/com/example/generated/api/spring/GenSpringMvcContractAssertions.java",
    ]
    assert stream_summary["artifacts"]["java.server"]["imports"] == [
        "com.example.generated.api.annotations.api.runs.GenEvents",
        "com.example.generated.api.types.api.runs.GenRunsTypes",
        "com.example.generated.api.adapters.api.runs.GenRunsAdapters",
        "com.example.generated.api.spring.GenSpringMvcContractAssertions",
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
    assert stream_summary["artifacts"]["swift.client"]["files"] == [
        "swift/Sources/ApiBlueprintExampleClientAPIRoutes/API/Routes/API/Runs/GenRunsTypes.swift",
        "swift/Sources/ApiBlueprintExampleClientAPIRoutes/API/Routes/API/Runs/GenRunsAPI.swift",
        "swift/Sources/ApiBlueprintExampleClientAPIRoutes/API/Routes/API/Runs/RunsAPI.swift",
        "swift/Sources/ApiBlueprintExampleClientRuntime/Transports/HTTP/GenURLSessionAPITransport.swift",
        "swift/Sources/ApiBlueprintExampleClient/Transports/HTTP/HTTPAPIClient.swift",
    ]
    assert stream_summary["artifacts"]["swift.client"]["imports"] == [
        "ApiBlueprintExampleClient",
        "ApiBlueprintExampleClientRuntime",
        "ApiBlueprintExampleClientAPIRoutes",
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
        {
            "id": "swift.client",
            "kind": "swift-client",
            "out_dir": "swift",
            "package": "ApiBlueprintExampleClient",
            "module": "ABClient",
        },
    ]

    agent = build_agent_manifest(manifest)
    route_summary = agent["routes"][0]

    assert route_summary["artifacts"]["kotlin.client"]["files"] == [
        "kotlin/com/example/generated/api/routes/api/GenApiTypes.kt",
        "kotlin/com/example/generated/api/routes/api/GenApiApi.kt",
        "kotlin/com/example/generated/api/routes/api/ApiApi.kt",
    ]
    assert route_summary["artifacts"]["java.client"]["files"] == [
        "java/client/com/example/generated/api/routes/api/GenApiTypes.java",
        "java/client/com/example/generated/api/routes/api/GenApiApi.java",
        "java/client/com/example/generated/api/routes/api/ApiApi.java",
        "java/client/com/example/generated/api/transports/http/GenJdkHttpApiTransport.java",
        "java/client/com/example/generated/api/transports/http/HttpApiClient.java",
    ]
    assert route_summary["artifacts"]["java.client"]["imports"] == [
        "com.example.generated.api.routes.api.ApiApi",
    ]
    assert route_summary["artifacts"]["java.server"]["files"] == [
        "java/server/com/example/generated/api/annotations/ApiBlueprintOperation.java",
        "java/server/com/example/generated/api/annotations/api/GenPing.java",
        "java/server/com/example/generated/api/types/api/GenApiTypes.java",
        "java/server/com/example/generated/api/adapters/api/GenApiAdapters.java",
        "java/server/com/example/generated/api/spring/GenSpringMvcContractAssertions.java",
    ]
    assert route_summary["artifacts"]["java.server"]["imports"] == [
        "com.example.generated.api.annotations.api.GenPing",
        "com.example.generated.api.types.api.GenApiTypes",
        "com.example.generated.api.adapters.api.GenApiAdapters",
        "com.example.generated.api.spring.GenSpringMvcContractAssertions",
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
    assert route_summary["artifacts"]["swift.client"]["files"] == [
        "swift/Sources/ABClientAPIRoutes/API/Routes/API/GenAPITypes.swift",
        "swift/Sources/ABClientAPIRoutes/API/Routes/API/GenAPIAPI.swift",
        "swift/Sources/ABClientAPIRoutes/API/Routes/API/APIAPI.swift",
        "swift/Sources/ABClientRuntime/Transports/HTTP/GenURLSessionAPITransport.swift",
        "swift/Sources/ABClient/Transports/HTTP/HTTPAPIClient.swift",
    ]
    assert route_summary["artifacts"]["swift.client"]["imports"] == [
        "ABClient",
        "ABClientRuntime",
        "ABClientAPIRoutes",
    ]


def test_swift_contract_artifacts_match_runtime_root_module_deduping():
    bp = Blueprint(root="/runtime")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()
    manifest["targets"] = [
        {
            "id": "swift.client",
            "kind": "swift-client",
            "out_dir": "swift",
            "package": "ApiBlueprintExampleClient",
        },
    ]

    agent = build_agent_manifest(manifest)
    route_summary = agent["routes"][0]

    assert route_summary["artifacts"]["swift.client"]["files"] == [
        "swift/Sources/ApiBlueprintExampleClientRuntimeRoutes/Runtime/Routes/Runtime/Demo/GenDemoTypes.swift",
        "swift/Sources/ApiBlueprintExampleClientRuntimeRoutes/Runtime/Routes/Runtime/Demo/GenDemoAPI.swift",
        "swift/Sources/ApiBlueprintExampleClientRuntimeRoutes/Runtime/Routes/Runtime/Demo/DemoAPI.swift",
        "swift/Sources/ApiBlueprintExampleClientRuntime/Transports/HTTP/GenURLSessionAPITransport.swift",
        "swift/Sources/ApiBlueprintExampleClient/Transports/HTTP/HTTPAPIClient.swift",
    ]
    assert route_summary["artifacts"]["swift.client"]["imports"] == [
        "ApiBlueprintExampleClient",
        "ApiBlueprintExampleClientRuntime",
        "ApiBlueprintExampleClientRuntimeRoutes",
    ]
