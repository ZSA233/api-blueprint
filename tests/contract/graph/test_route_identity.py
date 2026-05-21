from __future__ import annotations

from .helpers import *


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

def test_contract_route_contract_is_the_writer_core_compat_source():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.GET("/ping").RSP(message=String(description="message"))

    contract = route_contract(router)

    assert isinstance(contract, RouteContract)
    assert contract.route_id == "api.demo.get.ping"
    assert legacy_contracts.RouteContract is RouteContract
    assert legacy_contracts.route_contract is route_contract
