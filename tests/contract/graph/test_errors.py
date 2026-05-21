from __future__ import annotations

from .helpers import *


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
