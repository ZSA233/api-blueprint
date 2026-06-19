from __future__ import annotations

from .helpers import *
from api_blueprint.engine.model import Array, Int64


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

def test_contract_graph_uses_blueprint_name_for_rootless_route_identity():
    bp = Blueprint(name="legacy", root="")
    with bp.group("/account") as account:
        account.GET("/profile").RSP(message=String(description="message"))
    with bp.group("/room") as room:
        room.GET("/events").RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()

    assert [service["id"] for service in manifest["services"]] == [
        "legacy.account",
        "legacy.room",
    ]
    assert [route["id"] for route in manifest["routes"]] == [
        "legacy.account.get.profile",
        "legacy.room.get.events",
    ]
    assert [route["url"] for route in manifest["routes"]] == [
        "/account/profile",
        "/room/events",
    ]

def test_contract_graph_uses_api_name_for_explicit_rootless_v2_swift_identity():
    bp = Blueprint(name="api", root="")
    with bp.group("/api") as views:
        views.GET("/sample-action").RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()

    assert manifest["services"][0]["id"] == "api.api"
    assert manifest["routes"][0]["id"] == "api.api.get.sampleaction"
    assert manifest["routes"][0]["url"] == "/api/sample-action"

def test_contract_graph_preserves_non_empty_root_default_identity():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/ping").RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()

    assert manifest["services"][0]["id"] == "api.demo"
    assert manifest["routes"][0]["id"] == "api.demo.get.ping"

def test_contract_graph_records_rsp_empty_as_empty_object_response():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/update").RSP_EMPTY()

    manifest = build_contract_graph([bp]).to_manifest()

    route = manifest["routes"][0]
    schema_ref = route["response"]["model"]
    assert schema_ref in manifest["schemas"]
    assert route["response"]["envelope"]["kind"] == "code_message_data"
    assert manifest["schemas"][schema_ref]["type"] == "object"
    assert manifest["schemas"][schema_ref]["fields"] == {}

def test_contract_graph_rejects_duplicate_http_method_urls():
    first = Blueprint(name="first", root="")
    second = Blueprint(name="second", root="")
    with first.group("/account") as views:
        views.GET("/profile").RSP(message=String(description="message"))
    with second.group("/account") as views:
        views.GET("/profile").RSP(message=String(description="message"))

    with pytest.raises(ValueError, match=r"duplicate HTTP route GET /account/profile"):
        build_contract_graph([first, second])

def test_contract_graph_rejects_duplicate_logical_roots():
    first = Blueprint(name="legacy", root="")
    second = Blueprint(name="legacy", root="/legacy")
    first.GET("/ping").RSP(message=String(description="message"))
    second.GET("/pong").RSP(message=String(description="message"))

    with pytest.raises(ValueError, match="duplicate blueprint logical root 'legacy'"):
        build_contract_graph([first, second])

def test_contract_graph_rejects_root_group_and_named_group_surface_collision():
    bp = Blueprint(name="legacy", root="")
    bp.GET("/status").RSP(message=String(description="message"))
    with bp.group("/legacy") as views:
        views.GET("/other").RSP(message=String(description="message"))

    with pytest.raises(ValueError, match="duplicate generated service surface 'legacy.legacy'"):
        build_contract_graph([bp])

def test_contract_graph_rejects_duplicate_explicit_operation_names_in_same_group():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/events", operation_id="TaskEvents").RSP(message=String(description="message"))
        views.PUT("/events", operation_id="TaskEvents").RSP(message=String(description="message"))

    with pytest.raises(ValueError, match="duplicate operation name.*TaskEvents"):
        build_contract_graph([bp])

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

def test_contract_graph_disambiguates_auto_models_with_same_operation_name():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.GET("/abc").ARGS(arg1=String(description="arg1")).RSP(message=String(description="message"))
    with bp.group("/hello") as views:
        views.GET("/abc").ARGS(kind=String(description="kind")).RSP(message=String(description="message"))

    manifest = build_contract_graph([bp]).to_manifest()

    demo_route, hello_route = manifest["routes"]
    demo_query = demo_route["request"]["query_model"]
    hello_query = hello_route["request"]["query_model"]
    assert demo_query != hello_query
    assert "arg1" in manifest["schemas"][demo_query]["fields"]
    assert "kind" in manifest["schemas"][hello_query]["fields"]

def test_contract_graph_disambiguates_object_then_array_response_alias_collision():
    class Permission(Model):
        id = Int64(description="id")
        name = String(description="name")
        code = String(description="code")

    bp = Blueprint(root="/api")
    with bp.group("/base/role") as role:
        role.GET("/list").RSP(total=Int64(description="total"))
    with bp.group("/base/perm") as perm:
        perm.GET("/list").RSP(Array[Permission](description="permissions"))

    manifest = build_contract_graph([bp]).to_manifest()

    role_route, perm_route = manifest["routes"]
    role_schema = role_route["response"]["model"]
    perm_schema = perm_route["response"]["model"]
    assert role_schema != perm_schema
    assert role_schema in manifest["schemas"]
    assert perm_schema in manifest["schemas"]
    assert manifest["schemas"][role_schema]["type"] == "object"
    assert manifest["schemas"][perm_schema]["type"] == "alias"
    assert manifest["schemas"][perm_schema]["target"]["type"] == "array"
    assert manifest["schemas"][perm_schema]["target"]["items"] == {
        "type": "object",
        "ref": "Permission",
    }
    assert all(route["response"]["model"] in manifest["schemas"] for route in manifest["routes"])

def test_contract_graph_disambiguates_array_then_object_response_alias_collision():
    class Permission(Model):
        id = Int64(description="id")
        name = String(description="name")
        code = String(description="code")

    bp = Blueprint(root="/api")
    with bp.group("/base/perm") as perm:
        perm.GET("/list").RSP(Array[Permission](description="permissions"))
    with bp.group("/base/role") as role:
        role.GET("/list").RSP(total=Int64(description="total"))

    manifest = build_contract_graph([bp]).to_manifest()

    perm_route, role_route = manifest["routes"]
    perm_schema = perm_route["response"]["model"]
    role_schema = role_route["response"]["model"]
    assert perm_schema != role_schema
    assert perm_schema in manifest["schemas"]
    assert role_schema in manifest["schemas"]
    assert perm_schema.startswith("RSP_List#")
    assert manifest["schemas"][perm_schema]["type"] == "alias"
    assert manifest["schemas"][perm_schema]["target"]["type"] == "array"
    assert manifest["schemas"][role_schema]["type"] == "object"
    assert all(route["response"]["model"] in manifest["schemas"] for route in manifest["routes"])

def test_contract_route_contract_is_the_writer_core_compat_source():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.GET("/ping").RSP(message=String(description="message"))

    contract = route_contract(router)

    assert isinstance(contract, RouteContract)
    assert contract.route_id == "api.demo.get.ping"
    assert legacy_contracts.RouteContract is RouteContract
    assert legacy_contracts.route_contract is route_contract
