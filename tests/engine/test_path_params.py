from __future__ import annotations

import pytest
from fastapi import FastAPI

from api_blueprint.contract import build_contract_graph
from api_blueprint.engine import Blueprint, Model
from api_blueprint.engine.model import Array, String


class DeleteUserMedalPath(Model):
    user = String(description="user id")
    medal = String(description="medal id")


def test_req_path_generates_manifest_and_fastapi_path_parameters() -> None:
    app = FastAPI()
    bp = Blueprint(root="/api", app=app)
    with bp.group("/medal") as views:
        views.DELETE("/user/{user}/{medal}").REQ_PATH(DeleteUserMedalPath).RSP_EMPTY()

    graph = build_contract_graph([bp])
    route = graph.to_manifest()["routes"][0]
    assert route["request"]["path_model"] == "DeleteUserMedalPath"
    assert route["request"]["path_params"] == ["user", "medal"]
    assert route["request"]["path_model"] in graph.to_manifest()["schemas"]

    bp.build()
    operation = app.openapi()["paths"]["/api/medal/user/{user}/{medal}"]["delete"]
    path_parameters = [item for item in operation["parameters"] if item["in"] == "path"]
    assert [item["name"] for item in path_parameters] == ["user", "medal"]


def test_path_placeholder_requires_req_path_model() -> None:
    bp = Blueprint(root="/api")
    views = bp.group("/medal")
    views.DELETE("/user/{user}").RSP_EMPTY()

    with pytest.raises(ValueError, match="missing REQ_PATH"):
        build_contract_graph([bp])


def test_req_path_rejects_placeholder_model_mismatch() -> None:
    bp = Blueprint(root="/api")
    views = bp.group("/medal")
    with pytest.raises(ValueError, match="not declared"):
        views.DELETE("/user/{user}").REQ_PATH(medal=String())

    with pytest.raises(ValueError, match="missing path field"):
        views.DELETE("/medal/{user}/{medal}").REQ_PATH(user=String())


def test_req_path_rejects_invalid_placeholder_syntax_and_gin_style() -> None:
    bp = Blueprint(root="/api")
    views = bp.group("/medal")
    with pytest.raises(ValueError, match="Gin-style"):
        views.DELETE("/user/:user")

    with pytest.raises(ValueError, match="empty path placeholder"):
        views.DELETE("/user/{}").REQ_PATH(user=String())

    with pytest.raises(ValueError, match="duplicate path placeholder"):
        views.DELETE("/user/{user}/{user}").REQ_PATH(user=String())


def test_req_path_rejects_optional_and_non_scalar_fields() -> None:
    bp = Blueprint(root="/api")
    views = bp.group("/medal")
    with pytest.raises(ValueError, match="cannot be optional"):
        views.DELETE("/user/{user}").REQ_PATH(user=String(optional=True))

    with pytest.raises(ValueError, match="scalar path value"):
        views.DELETE("/medals/{ids}").REQ_PATH(ids=Array[String]())


def test_req_path_is_not_supported_by_connection_routes() -> None:
    bp = Blueprint(root="/api")
    views = bp.group("/events")
    with pytest.raises(ValueError, match="only supported by RPC HTTP routes"):
        views.STREAM("/{topic}").REQ_PATH(topic=String())
