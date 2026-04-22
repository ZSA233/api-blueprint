from __future__ import annotations

from api_blueprint.engine.wrapper import GeneralWrapper
from api_blueprint.writer.golang import GolangResponseWrapper


def test_golang_response_wrapper_preserves_generic_type_parameters():
    wrapper = GolangResponseWrapper("RSP_JSON", GeneralWrapper)
    assert wrapper.proto_def_name == "RSP_JSON_GeneralWrapper[T any]"
    assert wrapper.generic_types(True) == "[T any]"
