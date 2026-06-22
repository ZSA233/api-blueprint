from __future__ import annotations

import enum

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_blueprint.engine import Blueprint, message_variant, reset_shared_app
from api_blueprint.engine.model import Array, Enum, Int, Model, String
from api_blueprint.engine.runtime.docs import set_protocol_docs_plugins


class MessageMeta(Model):
    trace_id = String(description="trace id")


class Message(Model):
    text = String(description="message text")
    meta = MessageMeta(description="message metadata")


class BusinessType(enum.IntEnum):
    BASIC = 1  # Basic tier
    PREMIUM = 2  # Premium tier


class Color(enum.StrEnum):
    RED = "red"  # Red color
    BLUE = "blue"  # Blue color


class EnumBody(Model):
    business_type = Enum[BusinessType](description="business type")
    colors = Array[Enum[Color]](description="colors")


class EnumResponse(Model):
    business_type = Enum[BusinessType](description="business type")
    color = Enum[Color](description="color")


def _build_docs_blueprint() -> Blueprint:
    reset_shared_app()
    bp = Blueprint(root="/api", tags=["root"])

    with bp.group("/demo") as demo:
        demo.GET("/ping", tags=["demo"], summary="Ping").RSP(message=String(description="message"))
    with bp.group("/admin") as admin:
        admin.GET("/users", tags=["admin"], summary="Users").RSP(message=String(description="message"))
    with bp.group("/activity/a") as activity_a:
        activity_a.GET("/one", tags=["activity"], summary="Activity A").RSP(message=String(description="message"))
    with bp.group("/activity/b") as activity_b:
        activity_b.GET("/two", tags=["activity"], summary="Activity B").RSP(message=String(description="message"))
    with bp.group("/realtime") as realtime:
        realtime.STREAM("/events", tags=["events"]).SERVER_MESSAGE(
            "EventMessage",
            event=message_variant(
                Message,
                op=2001,
                name="Event pushed",
                auth="session",
                description="Server event payload",
                example={"text": "event"},
            ),
        )
        realtime.CHANNEL("/chat", tags=["chat"]).SERVER_MESSAGE(
            "ServerChatMessage",
            update=message_variant(
                Message,
                op=3002,
                name="Chat update",
                interaction="chat.send",
                role="response",
                auth="session",
                description="Server chat update",
                example={"text": "hello"},
            ),
        ).CLIENT_MESSAGE(
            "ClientChatMessage",
            send=message_variant(
                Message,
                op=3001,
                name="Send chat",
                interaction="chat.send",
                role="request",
                auth="session",
                description="Client chat message",
                example={"text": "hello"},
            ),
        )

    bp.build()
    return bp


def _build_enum_docs_blueprint() -> Blueprint:
    reset_shared_app()
    bp = Blueprint(root="/api", tags=["root"])

    with bp.group("/enum") as views:
        views.GET("/query", tags=["enum"]).ARGS(business_type=Enum[BusinessType]()).RSP(EnumResponse)
        views.GET("/path/{business_type}", tags=["enum"]).REQ_PATH(
            business_type=Enum[BusinessType]()
        ).RSP(EnumResponse)
        views.POST("/body", tags=["enum"]).REQ(EnumBody).RSP(EnumResponse)
        views.POST("/form", tags=["enum"]).REQ_FORM(color=Enum[Color]()).RSP(EnumResponse)

    bp.build()
    return bp


def _build_repeated_model_docs_blueprint() -> Blueprint:
    reset_shared_app()
    bp = Blueprint(root="/api", tags=["root"])
    leaf_names = ("config", "list", "data", "detail", "record", "search", "summary", "items")

    for index in range(160):
        with bp.group(f"/feature/{index}") as views:
            views.GET(f"/{leaf_names[index % len(leaf_names)]}").ARGS(
                **_repeated_query_fields(index)
            ).RSP(message=String(description="message"))

    bp.build()
    return bp


def _repeated_query_fields(index: int) -> dict[str, object]:
    pattern = index % 8
    if pattern == 0:
        return {"id": Int(omitempty=True)}
    if pattern == 1:
        return {"page": Int(omitempty=True), "size": Int(omitempty=True)}
    if pattern == 2:
        return {"id": Int(omitempty=True), "page": Int(omitempty=True), "size": Int(omitempty=True)}
    if pattern == 3:
        return {
            "id": Int(omitempty=True),
            "status": Int(omitempty=True),
            "page": Int(omitempty=True),
            "size": Int(omitempty=True),
        }
    if pattern == 4:
        return {"account": String(omitempty=True), "page": Int(omitempty=True), "size": Int(omitempty=True)}
    if pattern == 5:
        return {"name": String(omitempty=True), "status": Int(omitempty=True)}
    if pattern == 6:
        return {"start_time": String(omitempty=True), "end_time": String(omitempty=True)}
    return {"id": Int(omitempty=True), "category": String(omitempty=True)}


def test_default_docs_center_routes_and_index_are_available() -> None:
    bp = _build_docs_blueprint()
    client = TestClient(bp.app)

    home = client.get("/")
    assert home.status_code == 200
    assert 'fetch("/docs/index.json")' in home.text
    assert "ReDoc" not in home.text
    assert "api-blueprint-docs-theme" in home.text
    assert "api-blueprint-docs-sidebar-width" in home.text
    assert "buildGroupTree" in home.text
    assert "theme-toggle" in home.text
    assert "Protocol Catalog" in home.text
    assert "/docs/protocol" in home.text
    assert "/docs/protocol.json" in home.text
    assert "/docs/asyncapi" in home.text
    assert "Try-out console is planned" in home.text
    assert "Open in Protocol UI" in home.text
    assert 'asyncapi.href = "/docs/asyncapi?" + swaggerQuery.toString();' in home.text
    assert 'window.location.href = "/docs/protocol?route_id="' in home.text
    assert "message-table" not in home.text
    assert "MESSAGE_LABEL_LIMIT" not in home.text
    assert "MESSAGE_TABLE_LIMIT" not in home.text
    assert "renderMessageSummary" not in home.text
    assert "message-toggle" not in home.text
    assert "Server messages" in home.text
    assert "Client messages" in home.text
    assert "/static/all.min.css" not in home.text
    assert "webfonts" not in home.text
    assert "fa-solid" not in home.text
    assert "sidebar-resizer" in home.text
    assert "scrollbar-gutter: stable" in home.text
    assert 'class="icon"' in home.text
    assert 'data-section-toggle="groups"' in home.text
    assert 'data-section-toggle="kinds"' in home.text
    assert 'data-section-toggle="tags"' in home.text
    assert "chevron-right" in home.text
    assert "moon" in home.text
    assert "Light</button>" not in home.text
    assert "Dark</button>" not in home.text

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert 'fetch("/docs/index.json")' in docs.text
    assert 'fetch("/openapi.json")' not in docs.text
    assert "ReDoc" not in docs.text

    index = client.get("/docs/index.json").json()
    assert index["route_count"] == 6
    assert {route["kind"] for route in index["routes"]} == {"rpc", "stream", "channel"}
    assert "api.realtime.channel.chat" in {route["id"] for route in index["routes"]}
    chat = next(route for route in index["routes"] if route["id"] == "api.realtime.channel.chat")
    assert chat["connection"]["client_message"]["variants"][0]["op"] == 3001
    assert chat["connection"]["client_message"]["variants"][0]["metadata"]["auth"] == "session"


def test_protocol_and_asyncapi_visual_pages_are_available() -> None:
    bp = _build_docs_blueprint()
    client = TestClient(bp.app)

    protocol = client.get("/docs/protocol?route_id=api.realtime.channel.chat")
    assert protocol.status_code == 200
    assert "Protocol UI" in protocol.text
    assert "protocol-search" in protocol.text
    assert "operation-list" in protocol.text
    assert "Schema Explorer" in protocol.text
    assert "schema-explorer" in protocol.text
    assert "schema-search" in protocol.text
    assert "schema-toggle" in protocol.text
    assert "api-blueprint-schema-drawer" in protocol.text
    assert "payload-tree" in protocol.text
    assert "jumpToSchema" in protocol.text
    assert "schema-collapsed" in protocol.text
    assert "grid-template-rows: auto minmax(0, 1fr)" in protocol.text
    assert "grid-auto-rows: max-content" in protocol.text
    assert "Raw Protocol JSON" in protocol.text
    assert "fetch(protocolUrl())" in protocol.text
    assert "route-scope" in protocol.text
    assert "All protocol routes" in protocol.text
    assert "opFlowLabel" in protocol.text
    assert "api-blueprint-docs-theme" in protocol.text
    assert "theme-toggle" in protocol.text
    assert "iconSvg" in protocol.text
    assert ".badge.flow" in protocol.text
    assert "unpaired" in protocol.text

    asyncapi = client.get("/docs/asyncapi")
    assert asyncapi.status_code == 200
    assert "AsyncAPI UI" in asyncapi.text
    assert "AsyncAPI export preview" in asyncapi.text
    assert "asyncapi-search" in asyncapi.text
    assert "asyncapi-operation-list" in asyncapi.text
    assert "Schema Explorer" in asyncapi.text
    assert "schema-search" in asyncapi.text
    assert "schema-toggle" in asyncapi.text
    assert "api-blueprint-schema-drawer" in asyncapi.text
    assert "payload-tree" in asyncapi.text
    assert "jumpToSchema" in asyncapi.text
    assert "schema-collapsed" in asyncapi.text
    assert "grid-auto-rows: max-content" in asyncapi.text
    assert "Raw AsyncAPI JSON" in asyncapi.text
    assert 'fetch("/asyncapi.json")' in asyncapi.text
    assert "route-scope" in asyncapi.text
    assert "All AsyncAPI operations" in asyncapi.text
    assert "ASYNCAPI FLOW" in asyncapi.text
    assert 'protocol-link").href = "/docs/protocol?route_id="' in asyncapi.text
    assert "api-blueprint-docs-theme" in asyncapi.text
    assert "theme-toggle" in asyncapi.text
    assert "iconSvg" in asyncapi.text
    assert "direction-filter" in asyncapi.text
    assert "model-filter" in asyncapi.text
    assert "x-api-blueprint-interactions" in asyncapi.text


def test_protocol_catalog_exposes_connection_messages_and_metadata() -> None:
    bp = _build_docs_blueprint()
    client = TestClient(bp.app)

    protocol = client.get("/docs/protocol.json")
    assert protocol.status_code == 200
    payload = protocol.json()
    assert payload["route_count"] == 2
    assert {route["kind"] for route in payload["routes"]} == {"stream", "channel"}
    assert payload["plugins"] == [{"name": "metadata-interactions"}]
    assert [interaction["id"] for interaction in payload["interactions"]] == [
        "api.realtime.channel.chat:chat.send"
    ]
    assert payload["interactions"][0]["request"]["op"] == 3001
    assert payload["interactions"][0]["responses"][0]["op"] == 3002
    assert any(message["route_id"] == "api.realtime.stream.events" for message in payload["unpaired_messages"])
    assert _schema_by_title(payload, "Message") is not None
    assert _schema_by_title(payload, "MessageMeta") is not None

    chat = next(route for route in payload["routes"] if route["route_id"] == "api.realtime.channel.chat")
    assert chat["scope"] == "session"
    assert chat["delivery"] == "ordered"
    client_message = next(message for message in chat["messages"] if message["direction"] == "client")
    assert client_message["name"] == "ClientChatMessage"
    assert client_message["variants"] == [
        {
            "key": "send",
            "model": "Message",
            "metadata": {
                "op": 3001,
                "name": "Send chat",
                "interaction": "chat.send",
                "role": "request",
                "auth": "session",
                "description": "Client chat message",
                "example": {"text": "hello"},
            },
            "op": 3001,
            "name": "Send chat",
            "description": "Client chat message",
            "auth": "session",
            "example": {"text": "hello"},
            "interaction": "chat.send",
            "role": "request",
        }
    ]
    assert any(message["direction"] == "close" for message in chat["messages"])


def test_protocol_catalog_filters_routes_and_message_operations() -> None:
    bp = _build_docs_blueprint()
    client = TestClient(bp.app)

    by_route = client.get("/docs/protocol.json?route_id=api.realtime.channel.chat").json()
    assert by_route["route_count"] == 1
    assert by_route["routes"][0]["route_id"] == "api.realtime.channel.chat"

    by_group = client.get("/docs/protocol.json?group=/api/realtime").json()
    assert by_group["route_count"] == 2

    by_direction = client.get("/docs/protocol.json?direction=client").json()
    assert by_direction["route_count"] == 1
    assert by_direction["routes"][0]["route_id"] == "api.realtime.channel.chat"
    assert [message["direction"] for message in by_direction["routes"][0]["messages"]] == ["client"]

    by_op = client.get("/docs/protocol.json?op=3001").json()
    assert by_op["route_count"] == 1
    assert by_op["routes"][0]["route_id"] == "api.realtime.channel.chat"
    assert by_op["routes"][0]["messages"] == [
        {
            "direction": "client",
            "name": "ClientChatMessage",
            "variants": [
                {
                    "key": "send",
                    "model": "Message",
                    "metadata": {
                        "op": 3001,
                        "name": "Send chat",
                        "interaction": "chat.send",
                        "role": "request",
                        "auth": "session",
                        "description": "Client chat message",
                        "example": {"text": "hello"},
                    },
                    "op": 3001,
                    "name": "Send chat",
                    "description": "Client chat message",
                    "auth": "session",
                    "example": {"text": "hello"},
                    "interaction": "chat.send",
                    "role": "request",
                }
            ],
        }
    ]
    assert by_op["interactions"][0]["request"]["op"] == 3001
    assert by_op["interactions"][0]["responses"][0]["op"] == 3002


def test_protocol_docs_plugin_can_project_custom_interactions() -> None:
    reset_shared_app()
    bp = Blueprint(root="/socket")
    with bp.group("/demo") as demo:
        demo.CHANNEL("/session").SERVER_MESSAGE(
            "ServerMessage",
            result=message_variant(Message, op=5002, name="Result"),
        ).CLIENT_MESSAGE(
            "ClientMessage",
            command=message_variant(Message, op=5001, name="Command"),
        )
    bp.build()

    def custom_interaction_plugin(catalog):
        route = catalog["routes"][0]
        client = next(message for message in route["messages"] if message["direction"] == "client")
        server = next(message for message in route["messages"] if message["direction"] == "server")
        request_variant = client["variants"][0]
        response_variant = server["variants"][0]
        request = {
            "route_id": route["route_id"],
            "direction": "client",
            "message": client["name"],
            "variant_key": request_variant["key"],
            "model": request_variant["model"],
            "op": request_variant["op"],
            "name": request_variant["name"],
            "metadata": request_variant["metadata"],
        }
        response = {
            "route_id": route["route_id"],
            "direction": "server",
            "message": server["name"],
            "variant_key": response_variant["key"],
            "model": response_variant["model"],
            "op": response_variant["op"],
            "name": response_variant["name"],
            "metadata": response_variant["metadata"],
        }
        return {
            "interactions": [
                {
                    "id": f"{route['route_id']}:plugin.command",
                    "name": "Plugin command",
                    "route_id": route["route_id"],
                    "kind": route["kind"],
                    "group": route["group"],
                    "group_path": route["group_path"],
                    "path": route["path"],
                    "tags": route["tags"],
                    "request": request,
                    "responses": [response],
                    "messages": [request, response],
                }
            ]
        }

    set_protocol_docs_plugins(bp.app, [custom_interaction_plugin])
    payload = TestClient(bp.app).get("/docs/protocol.json").json()

    assert payload["plugins"] == [
        {"name": "metadata-interactions"},
        {"name": "custom_interaction_plugin"},
    ]
    assert payload["interactions"][0]["id"] == "socket.demo.channel.session:plugin.command"
    assert payload["interactions"][0]["request"]["op"] == 5001
    assert payload["interactions"][0]["responses"][0]["op"] == 5002
    assert all(message.get("op") not in {5001, 5002} for message in payload["unpaired_messages"])


def test_asyncapi_exports_message_protocol_without_http_rpc_routes() -> None:
    bp = _build_docs_blueprint()
    client = TestClient(bp.app)

    spec = client.get("/asyncapi.json")
    assert spec.status_code == 200
    payload = spec.json()
    assert payload["asyncapi"] == "3.0.0"
    assert "channels" in payload
    assert "operations" in payload
    assert "components" in payload
    assert payload["x-api-blueprint-interactions"][0]["id"] == "api.realtime.channel.chat:chat.send"
    assert payload["x-api-blueprint-interactions"][0]["request"]["op"] == 3001
    assert payload["x-api-blueprint-interactions"][0]["responses"][0]["op"] == 3002
    assert _schema_by_title(payload, "Message") is not None
    assert _schema_by_title(payload, "MessageMeta") is not None
    assert all("ping" not in channel.get("address", "") for channel in payload["channels"].values())

    messages = payload["components"]["messages"]
    send_message = next(message for message in messages.values() if message.get("x-api-blueprint-op") == 3001)
    assert send_message["x-api-blueprint-route-id"] == "api.realtime.channel.chat"
    assert send_message["x-api-blueprint-direction"] == "client"
    assert send_message["x-api-blueprint-variant-key"] == "send"
    assert send_message["x-api-blueprint-metadata"]["auth"] == "session"
    assert send_message["payload"] == {"$ref": "#/components/schemas/Message"}


def test_channel_routes_are_not_forced_into_openapi_paths() -> None:
    reset_shared_app()
    bp = Blueprint(root="/socket")
    with bp.group("/app") as app:
        app.CHANNEL("/session").SERVER_MESSAGE(
            "ServerMessage",
            update=message_variant(Message, op=4002, description="Server update"),
        ).CLIENT_MESSAGE(
            "ClientMessage",
            send=message_variant(Message, op=4001, description="Client command"),
        )
    bp.build()
    client = TestClient(bp.app)

    assert client.get("/openapi.json").status_code == 200
    assert client.get("/openapi.json").json()["paths"] == {}
    assert client.get("/docs/openapi.json").json()["paths"] == {}
    assert client.get("/docs/protocol.json").json()["route_count"] == 1


def test_asyncapi_without_message_routes_is_valid_empty_document() -> None:
    reset_shared_app()
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))
    bp.build()
    client = TestClient(bp.app)

    payload = client.get("/asyncapi.json").json()
    assert payload["asyncapi"] == "3.0.0"
    assert payload["channels"] == {}
    assert payload["operations"] == {}
    assert payload["components"]["messages"] == {}


def test_sliced_openapi_filters_by_group_tag_kind_and_route_id() -> None:
    bp = _build_docs_blueprint()
    client = TestClient(bp.app)

    by_group = client.get("/docs/openapi.json?group=demo").json()
    assert "/api/demo/ping" in by_group["paths"]
    assert "/api/admin/users" not in by_group["paths"]

    by_parent_group = client.get("/docs/openapi.json?group=/api/activity").json()
    assert "/api/activity/a/one" in by_parent_group["paths"]
    assert "/api/activity/b/two" in by_parent_group["paths"]
    assert "/api/demo/ping" not in by_parent_group["paths"]

    by_tag = client.get("/docs/openapi.json?tag=admin").json()
    assert "/api/admin/users" in by_tag["paths"]
    assert "/api/demo/ping" not in by_tag["paths"]

    by_stream_kind = client.get("/docs/openapi.json?kind=stream").json()
    assert "/api/realtime/events" in by_stream_kind["paths"]

    by_channel_kind = client.get("/docs/openapi.json?kind=channel").json()
    assert by_channel_kind["paths"] == {}

    by_route = client.get("/docs/openapi.json?route_id=api.demo.get.ping").json()
    assert list(by_route["paths"]) == ["/api/demo/ping"]


def test_sliced_openapi_cache_is_keyed_by_filter() -> None:
    bp = _build_docs_blueprint()
    client = TestClient(bp.app)

    client.get("/docs/openapi.json?group=demo")
    cache = bp.app.state.api_blueprint_docs_openapi_cache
    assert len(cache) == 1

    client.get("/docs/openapi.json?group=demo")
    assert len(cache) == 1

    client.get("/docs/openapi.json?group=admin")
    assert len(cache) == 2


def test_full_openapi_handles_repeated_route_local_model_names() -> None:
    bp = _build_repeated_model_docs_blueprint()
    client = TestClient(bp.app)

    full = client.get("/openapi.json")
    assert full.status_code == 200
    full_spec = full.json()
    assert "/api/feature/0/config" in full_spec["paths"]

    docs = client.get("/docs/openapi.json")
    assert docs.status_code == 200
    assert "/api/feature/0/config" in docs.json()["paths"]

    config_parameters = full_spec["paths"]["/api/feature/0/config"]["get"]["parameters"]
    assert [(param["name"], param["in"]) for param in config_parameters] == [("id", "query")]
    list_parameters = full_spec["paths"]["/api/feature/1/list"]["get"]["parameters"]
    assert [(param["name"], param["in"]) for param in list_parameters] == [("page", "query"), ("size", "query")]


def test_openapi_enum_values_and_names_are_exposed_in_full_and_sliced_specs() -> None:
    bp = _build_enum_docs_blueprint()
    client = TestClient(bp.app)

    full = client.get("/openapi.json").json()
    sliced = client.get("/docs/openapi.json?group=enum").json()

    for spec in (full, sliced):
        business_type = _schema_by_title(spec, "BusinessType")
        assert business_type["enum"] == [1, 2]
        assert business_type["x-enumNames"] == ["BASIC", "PREMIUM"]
        assert business_type["x-enum-varnames"] == ["BASIC", "PREMIUM"]
        assert business_type["x-enumDescriptions"] == ["Basic tier", "Premium tier"]
        assert business_type["x-enum-descriptions"] == ["Basic tier", "Premium tier"]

        color = _schema_by_title(spec, "Color")
        assert color["enum"] == ["red", "blue"]
        assert color["x-enumNames"] == ["RED", "BLUE"]
        assert color["x-enum-varnames"] == ["RED", "BLUE"]
        assert color["x-enumDescriptions"] == ["Red color", "Blue color"]
        assert color["x-enum-descriptions"] == ["Red color", "Blue color"]

    assert "/api/enum/query" in sliced["paths"]
    assert "/api/enum/path/{business_type}" in sliced["paths"]
    assert "/api/enum/body" in sliced["paths"]
    assert "/api/enum/form" in sliced["paths"]


def test_docs_routes_reject_invalid_enum_values() -> None:
    bp = _build_enum_docs_blueprint()
    client = TestClient(bp.app)

    assert client.get("/api/enum/query?business_type=99").status_code == 422
    assert client.get("/api/enum/path/99").status_code == 422
    assert client.post("/api/enum/body", json={"business_type": 99, "colors": ["red"]}).status_code == 422
    assert client.post("/api/enum/form", data={"color": "green"}).status_code == 422


def test_swagger_uses_sliced_openapi_url_and_redoc_redirects_home() -> None:
    bp = _build_docs_blueprint()
    client = TestClient(bp.app)

    swagger = client.get("/docs/swagger?group=demo")
    assert swagger.status_code == 200
    assert "/docs/openapi.json?group=demo" in swagger.text
    assert "docExpansion" in swagger.text
    assert "defaultModelsExpandDepth" in swagger.text

    assert client.get("/docs/redoc").status_code == 404
    redoc = client.get("/redoc", follow_redirects=False)
    assert redoc.status_code in {307, 308}
    assert redoc.headers["location"] == "/"


def test_explicit_fastapi_app_keeps_its_native_docs_route() -> None:
    app = FastAPI()
    bp = Blueprint(root="/api", app=app)

    with bp.group("/demo") as demo:
        demo.GET("/ping").RSP(message=String(description="message"))

    bp.build()
    paths = {route.path for route in app.routes if getattr(route, "path", None)}
    assert "/docs" in paths
    assert "/docs/index.json" not in paths


def _schema_by_title(spec: dict, title: str) -> dict:
    for schema in spec.get("components", {}).get("schemas", {}).values():
        if schema.get("title") == title:
            return schema
    raise AssertionError(f"schema with title {title!r} not found")
