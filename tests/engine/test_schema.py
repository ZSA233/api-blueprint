from __future__ import annotations

import enum

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
from api_blueprint.engine.wrapper import GeneralWrapper


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


def test_response_wrapper_create_keeps_generic_data_field():
    wrapped = GeneralWrapper.create(Payload)
    pydantic_model = model_to_pydantic(wrapped)
    assert "data" in pydantic_model.model_fields
    assert pydantic_model.model_config.get("json_schema_extra") == {"xml": {"name": "response"}}


def test_response_wrapper_cache_is_scoped_to_model_identity():
    first_model = create_model("Payload", {"name": String(description="name")}).__class__
    second_model = create_model("Payload", {"count": Int(description="count")}).__class__

    first_wrapper = GeneralWrapper.create(first_model)
    second_wrapper = GeneralWrapper.create(second_model)

    assert first_wrapper is not second_wrapper
    assert first_wrapper.data.__class__ is first_model
    assert second_wrapper.data.__class__ is second_model


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
