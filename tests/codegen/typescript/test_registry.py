from __future__ import annotations

from .helpers import *


def test_typescript_name_helpers_preserve_expected_output():
    assert to_ts_name("REQ_Ws_QUERY") == "ReqWsQuery"
    assert to_ts_identifier("delete$") == '"delete$"'

def test_typescript_registry_builds_wrapper_alias_with_generics():
    registry = TypeScriptProtoRegistry()
    proto = registry.ensure(CodeMessageDataEnvelope, tag="wrapper")
    assert proto is not None
    assert proto.type_reference(["Payload"]) == "CodeMessageDataEnvelope<Payload>"
