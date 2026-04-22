from __future__ import annotations

from api_blueprint.engine.model import Enum, Model, String
from api_blueprint.engine.wrapper import GeneralWrapper
from api_blueprint.writer.typescript import TypeScriptProtoRegistry, to_ts_identifier, to_ts_name


class Payload(Model):
    value = String(description="value")


def test_typescript_name_helpers_preserve_expected_output():
    assert to_ts_name("REQ_Ws_QUERY") == "ReqWsQuery"
    assert to_ts_identifier("delete$") == '"delete$"'


def test_typescript_registry_builds_wrapper_alias_with_generics():
    registry = TypeScriptProtoRegistry()
    proto = registry.ensure(GeneralWrapper, tag="wrapper")
    assert proto is not None
    assert proto.type_reference(["Payload"]) == "GeneralWrapper<Payload>"
