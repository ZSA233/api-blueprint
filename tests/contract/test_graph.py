from __future__ import annotations

from api_blueprint.contract import RouteContract, build_contract_graph, route_contract
from api_blueprint.engine import Blueprint
from api_blueprint.engine.connection import ConnectionScope
from api_blueprint.engine.model import Int, String, Model
from api_blueprint.writer.core import contracts as legacy_contracts


class OpenRequest(Model):
    run_id = String(description="run id")


class StreamState(Model):
    status = String(description="status")


class StreamDone(Model):
    message = String(description="message")


class CloseInfo(Model):
    code = Int(description="code")
    reason = String(description="reason", omitempty=True)


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

    assert manifest["version"] == "vnext-1"
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
    assert stream["connection"]["open_model"] == "OpenRequest"
    assert stream["connection"]["close_model"] == "CloseInfo"
    assert stream["connection"]["server_message"]["name"] == "RunStreamMessage"
    assert [variant["key"] for variant in stream["connection"]["server_message"]["variants"]] == ["state", "done"]

    schema = manifest["schemas"]["CloseInfo"]
    assert schema["fields"]["reason"]["optional"] is True
    assert len(manifest["hashes"]["routes"]["api.runs.stream.events"]) == 64


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
