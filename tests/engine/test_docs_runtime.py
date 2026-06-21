from __future__ import annotations

import enum

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_blueprint.engine import Blueprint, reset_shared_app
from api_blueprint.engine.model import Array, Enum, Model, String


class Message(Model):
    text = String(description="message text")


class BusinessType(enum.IntEnum):
    BASIC = 1
    PREMIUM = 2


class Color(enum.StrEnum):
    RED = "red"
    BLUE = "blue"


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
        realtime.STREAM("/events", tags=["events"]).SERVER_MESSAGE(Message)
        realtime.CHANNEL("/chat", tags=["chat"]).SERVER_MESSAGE(Message).CLIENT_MESSAGE(Message)

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

        color = _schema_by_title(spec, "Color")
        assert color["enum"] == ["red", "blue"]
        assert color["x-enumNames"] == ["RED", "BLUE"]
        assert color["x-enum-varnames"] == ["RED", "BLUE"]

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
