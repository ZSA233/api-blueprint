from __future__ import annotations

from .helpers import *


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
