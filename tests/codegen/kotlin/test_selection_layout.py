from __future__ import annotations

from .helpers import *


def test_kotlin_selection_matches_path_tag_group_method_and_name(example_entrypoints):
    _config, entrypoints = example_entrypoints
    router = next(router for bp in entrypoints for _group, router in bp.iter_router() if router.url == "/api/demo/abc")

    assert KotlinRouteSelection(include=("path:/api/demo/*",)).includes(router, route_name="Abc")
    assert KotlinRouteSelection(include=("tag:api",)).includes(router, route_name="Abc")
    assert KotlinRouteSelection(include=("group:demo",)).includes(router, route_name="Abc")
    assert KotlinRouteSelection(include=("method:GET",)).includes(router, route_name="Abc")
    assert KotlinRouteSelection(include=("name:Abc",)).includes(router, route_name="Abc")
    assert not KotlinRouteSelection(include=("tag:api",), exclude=("path:/api/demo/*",)).includes(
        router,
        route_name="Abc",
    )

def test_kotlin_writer_name_filter_uses_resolved_operation_name_for_same_path_methods(tmp_path):
    bp = Blueprint(root="/api")
    with bp.group("/settings") as views:
        views.GET("/current").RSP(message=String(description="message"))
        views.PUT("/current").RSP(message=String(description="message"))

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated", include=("name:CurrentGet",))
    writer.register(bp)
    writer.gen()

    route_text = (
        tmp_path
        / "kotlin"
        / "com"
        / "example"
        / "generated"
        / "api"
        / "routes"
        / "api"
        / "settings"
        / "GenSettingsApi.kt"
    ).read_text(encoding="utf-8")
    assert "public open suspend fun currentGet(" in route_text
    assert "public open suspend fun currentPut(" not in route_text

def test_kotlin_writer_replaces_stale_generated_runtime_client_with_default_facade(tmp_path):
    class SubmitResponse(Model):
        status = String(description="status")

    bp = Blueprint(root="/api")
    bp.group("/demo").GET("/status").RSP(SubmitResponse)
    bp.is_built = True

    runtime_dir = tmp_path / "kotlin" / "com" / "example" / "generated" / "api" / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "ApiClient.kt").write_text(
        "\n".join(
            (
                "package com.example.generated.api.runtime",
                "",
                "public class ApiClient(",
                "    private val transport: ApiTransport,",
                ") {",
                "    public val demo: DemoApi = DemoApi(transport)",
                "}",
                "",
            )
        ),
        encoding="utf-8",
    )

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated")
    writer.register(bp)
    writer.gen()

    client_facade_text = (runtime_dir / "ApiClient.kt").read_text(encoding="utf-8")

    assert ": GenApiClient(transport)" in client_facade_text
    assert "private val transport: ApiTransport" not in client_facade_text

def test_kotlin_contract_graph_adapter_owns_request_and_response_models(tmp_path):
    class SubmitJson(Model):
        value = String(description="value")

    class SubmitResponse(Model):
        status = String(description="status")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.POST("/submit").ARGS(q=String(description="q")).REQ(SubmitJson).RSP(SubmitResponse)

    graph = build_contract_graph([bp])
    router.req_query = None
    router.req_json = None
    router.rsp_model = None

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated", contract_graph=graph)
    writer.register(bp)
    writer.gen()

    route_text = (
        tmp_path / "kotlin" / "com" / "example" / "generated" / "api" / "routes" / "api" / "demo" / "GenDemoApi.kt"
    ).read_text(encoding="utf-8")
    models_text = (
        tmp_path / "kotlin" / "com" / "example" / "generated" / "api" / "routes" / "api" / "demo" / "GenDemoTypes.kt"
    ).read_text(encoding="utf-8")
    assert "query: DemoSubmitQuery," in route_text
    assert "json: SubmitJson," in route_text
    assert "): SubmitResponse {" in route_text
    assert "public data class DemoSubmitQuery" in models_text
