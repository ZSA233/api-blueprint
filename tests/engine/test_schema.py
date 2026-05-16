from __future__ import annotations

import enum
import warnings

from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import (
    Array,
    Enum,
    Field,
    Float64,
    Int,
    KV,
    Map,
    Model,
    String,
    Uint,
    create_model,
    iter_enum_classes,
    model_to_pydantic,
)
from api_blueprint.engine.envelope import CodeMessageDataEnvelope


class Color(enum.StrEnum):
    RED = "red"
    BLUE = "blue"


class Nested(Model):
    count = Int(default=1)


class Payload(Model):
    color = Enum[Color](description="color")
    nested = Nested(description="nested")
    mapping = Map[String, Nested](description="mapping")
    array = Array[Enum[Color]](description="array")


def test_iter_enum_classes_finds_nested_and_collection_enums():
    enums = set(iter_enum_classes(Payload))
    assert enums == {Color}


def test_model_to_pydantic_marks_default_fields_optional():
    pydantic_model = model_to_pydantic(Nested)
    field = pydantic_model.model_fields["count"]
    assert not field.is_required()


def test_model_to_pydantic_marks_omitempty_fields_optional():
    class OptionalPayload(Model):
        required = String(description="required")
        maybe = String(description="maybe", omitempty=True)

    pydantic_model = model_to_pydantic(OptionalPayload)
    schema = pydantic_model.model_json_schema()

    assert "required" in schema["required"]
    assert "maybe" not in schema.get("required", [])
    assert not pydantic_model.model_fields["maybe"].is_required()


def test_model_to_pydantic_allows_basemodel_shadow_field_without_warning():
    class SchemaPayload(Model):
        schema = String(description="schema")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pydantic_model = model_to_pydantic(SchemaPayload)

    warning_messages = [str(warning.message) for warning in caught]
    assert not any("shadows an attribute in parent" in message for message in warning_messages)
    assert "schema" in pydantic_model.model_fields
    assert "schema" in pydantic_model.model_json_schema()["properties"]
    assert pydantic_model.model_validate({"schema": "value"}).schema == "value"


def test_response_envelope_create_keeps_generic_data_field():
    wrapped = CodeMessageDataEnvelope.create(Payload)
    pydantic_model = model_to_pydantic(wrapped)
    schema = pydantic_model.model_json_schema()

    assert "data" in pydantic_model.model_fields
    assert pydantic_model.model_config.get("json_schema_extra") == {"xml": {"name": "response"}}
    assert "code" in schema["required"]
    assert "message" in schema["required"]
    assert "data" not in schema.get("required", [])
    assert "error" not in schema.get("required", [])


def test_response_envelope_cache_is_scoped_to_model_identity():
    first_model = create_model("Payload", {"name": String(description="name")}).__class__
    second_model = create_model("Payload", {"count": Int(description="count")}).__class__

    first_envelope = CodeMessageDataEnvelope.create(first_model)
    second_envelope = CodeMessageDataEnvelope.create(second_model)

    assert first_envelope is not second_envelope
    assert first_envelope.data.__class__ is first_model
    assert second_envelope.data.__class__ is second_model


def test_model_to_pydantic_keeps_route_named_anon_models_after_build():
    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        router = views.PUT("/1put").RSP(
            anon_kv=KV(
                kv1=Uint(description="kv1"),
                kv2=Array[Float64](description="kv2"),
            )
        )

    field = router.rsp_model["anon_kv"]
    assert field.get_obj() is not None
    assert getattr(field.get_obj(), "__name__", None) == "ANON_Func1put_anon_kv"

    # Route registration should keep the already materialized anonymous model stable.
    model_to_pydantic(router.rsp_model)
    assert getattr(field.get_obj(), "__name__", None) == "ANON_Func1put_anon_kv"
