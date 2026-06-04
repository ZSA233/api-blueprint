from __future__ import annotations

import pytest
from fastapi import FastAPI

from api_blueprint.engine import Blueprint, reset_shared_app
from api_blueprint.engine.model import String


def test_example_blueprints_build_into_shared_fastapi_app(example_entrypoints):
    _config, entrypoints = example_entrypoints

    for bp in entrypoints:
        bp.build()

    apps = {bp.app for bp in entrypoints}
    assert len(apps) == 1

    app = entrypoints[0].app
    paths = {route.path for route in app.routes if getattr(route, "path", None)}
    assert "/docs" in paths
    assert "/redoc" in paths
    assert "/openapi.json" in paths
    assert "/api/demo/abc" in paths
    assert "/api/demo/error-demo" in paths
    assert "/api/demo/request-options" in paths
    assert "/api/demo/sweep-events" in paths
    assert "/api/demo/assistant-session" in paths
    assert "/api/binary/packet" in paths
    assert "/api/media/preview" in paths
    assert "/api/media/mjpeg" in paths
    assert "/api/media/download-filename-edge" in paths
    assert "/api/media/error-frame" in paths
    assert "/account/profile" in paths
    assert "/room/list" in paths
    assert "/api/hello/hello-way" in paths
    assert "/runtime/status/current" in paths
    assert "/static/doc.json" in paths
    assert len(paths) == 43

    openapi = app.openapi()
    assert "text/event-stream" in openapi["paths"]["/api/demo/sweep-events"]["get"]["responses"]["200"]["content"]

    for bp in entrypoints:
        bp.build()

    paths_after_rebuild = {route.path for route in app.routes if getattr(route, "path", None)}
    assert paths_after_rebuild == paths


def test_explicit_fastapi_app_breaks_default_shared_app_behavior():
    reset_shared_app()
    app_a = FastAPI()
    app_b = FastAPI()

    bp_a = Blueprint(root="/a", app=app_a)
    bp_b = Blueprint(root="/b", app=app_b)

    assert bp_a.app is app_a
    assert bp_b.app is app_b
    assert bp_a.app is not bp_b.app


def test_rootless_blueprint_uses_name_for_shared_app_and_keeps_group_urls():
    reset_shared_app()
    bp = Blueprint(name="legacy", root="")

    with bp.group("/account") as account:
        account.GET("/profile").RSP(message=String(description="message"))
    with bp.group("/room") as room:
        room.GET("/events").RSP(message=String(description="message"))

    bp.build()

    paths = {route.path for route in bp.app.routes if getattr(route, "path", None)}
    assert bp.app.title == "legacy"
    assert "/account/profile" in paths
    assert "/room/events" in paths
    assert "/legacy/account/profile" not in paths

    openapi = bp.app.openapi()
    assert "/account/profile" in openapi["paths"]
    assert "/room/events" in openapi["paths"]


def test_rootless_blueprint_without_name_requires_explicit_name():
    reset_shared_app()

    with pytest.raises(ValueError, match="rootless Blueprint requires explicit name"):
        Blueprint(root="")


def test_rootless_blueprint_can_use_api_name_for_legacy_swift_identity():
    reset_shared_app()
    bp = Blueprint(name="api", root="")

    with bp.group("/account") as account:
        account.GET("/profile").RSP(message=String(description="message"))

    bp.build()

    paths = {route.path for route in bp.app.routes if getattr(route, "path", None)}
    assert bp.name == "api"
    assert bp.root_slug == "api"
    assert bp.app.title == "api"
    assert "/account/profile" in paths
    assert "/api/account/profile" not in paths


def test_route_tags_preserve_declared_order_and_dedupe():
    reset_shared_app()
    bp = Blueprint(root="/api", tags=["api", "legacy"])

    group = bp.group("/demo")
    route = group.GET("/ping", tags=["demo", "api"])

    assert route.tags == ["demo", "api", "legacy"]


def test_response_envelope_omitempty_fields_are_optional_in_openapi():
    app = FastAPI()
    bp = Blueprint(root="/api", app=app)
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    bp.build()
    openapi = app.openapi()
    path_spec = openapi["paths"]["/api/demo/ping"]["get"]
    response_schema = path_spec["responses"]["200"]["content"]["application/json"]["schema"]
    rsp_schema_ref = response_schema["$ref"]
    rsp_schema_name = rsp_schema_ref.rsplit("/", 1)[-1]
    required = openapi["components"]["schemas"][rsp_schema_name]["required"]

    assert "code" in required
    assert "message" in required
    assert "data" not in required
    assert "error" not in required
