from __future__ import annotations

import enum
import warnings

import pytest

from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import (
    Array,
    CoerceString,
    Enum,
    Field,
    Float,
    Float32,
    Float64,
    Int,
    Int32,
    Int64,
    KV,
    LegacyStringID,
    Map,
    Model,
    OneOf,
    String,
    StringOrIntAsString,
    Uint,
    Uint64,
    create_model,
    iter_enum_classes,
    model_to_pydantic,
)
from api_blueprint.engine.schema import enum_schema_extensions
from api_blueprint.engine.envelope import CodeMessageDataEnvelope


class Color(enum.StrEnum):
    RED = "red"
    BLUE = "blue"


class BusinessType(enum.IntEnum):
    BASIC = 1
    PREMIUM = 2


class ActionKind(enum.IntEnum):
    CREATE = 1  # Create item
    UPDATE = 2  # Update item


class Nested(Model):
    count = Int(default=1)
    status = Enum[BusinessType](description="nested status")


class Payload(Model):
    color = Enum[Color](description="color")
    status = Enum[BusinessType](description="status")
    nested = Nested(description="nested")
    mapping = Map[String, Nested](description="mapping")
    array = Array[Enum[Color]](description="array")
    status_map = Map[String, Enum[BusinessType]](description="status map")


class ActionPayload(Model):
    action = Enum[ActionKind](description="action")


def test_iter_enum_classes_finds_nested_and_collection_enums():
    enums = set(iter_enum_classes(Payload))
    assert enums == {Color, BusinessType}


def test_model_to_pydantic_preserves_enum_schema_and_validation():
    pydantic_model = model_to_pydantic(Payload)
    schema = pydantic_model.model_json_schema()

    color_schema = schema["$defs"]["Color"]
    assert color_schema["enum"] == ["red", "blue"]

    business_type_schema = schema["$defs"]["BusinessType"]
    assert business_type_schema["enum"] == [1, 2]

    assert schema["properties"]["color"]["x-enumNames"] == ["RED", "BLUE"]
    assert schema["properties"]["color"]["x-enum-varnames"] == ["RED", "BLUE"]
    assert schema["properties"]["status"]["x-enumNames"] == ["BASIC", "PREMIUM"]
    assert schema["properties"]["status"]["x-enum-varnames"] == ["BASIC", "PREMIUM"]
    assert schema["properties"]["array"]["items"]["$ref"] == "#/$defs/Color"
    assert schema["properties"]["status_map"]["additionalProperties"]["$ref"] == "#/$defs/BusinessType"
    nested_schema = _schema_by_title(schema["$defs"], "Nested")
    assert nested_schema["properties"]["status"]["$ref"] == "#/$defs/BusinessType"

    valid = pydantic_model.model_validate(
        {
            "color": "red",
            "status": 1,
            "nested": {"status": 2},
            "mapping": {"primary": {"status": 1}},
            "array": ["blue"],
            "status_map": {"primary": 2},
        }
    )
    assert valid.color is Color.RED
    assert valid.status is BusinessType.BASIC
    assert valid.nested.status is BusinessType.PREMIUM
    assert valid.array == [Color.BLUE]
    assert valid.status_map == {"primary": BusinessType.PREMIUM}
    assert valid.model_dump(mode="json")["status_map"] == {"primary": 2}

    with pytest.raises(Exception):
        pydantic_model.model_validate(
            {
                "color": "green",
                "status": 1,
                "nested": {"status": 2},
                "mapping": {"primary": {"status": 1}},
                "array": ["blue"],
                "status_map": {"primary": 2},
            }
        )

    with pytest.raises(Exception):
        pydantic_model.model_validate(
            {
                "color": "red",
                "status": 99,
                "nested": {"status": 2},
                "mapping": {"primary": {"status": 1}},
                "array": ["blue"],
                "status_map": {"primary": 2},
            }
        )


def test_model_to_pydantic_exposes_enum_member_descriptions():
    pydantic_model = model_to_pydantic(ActionPayload)
    schema = pydantic_model.model_json_schema()
    action_schema = schema["properties"]["action"]

    assert action_schema["x-enumNames"] == ["CREATE", "UPDATE"]
    assert action_schema["x-enum-varnames"] == ["CREATE", "UPDATE"]
    assert action_schema["x-enumDescriptions"] == ["Create item", "Update item"]
    assert action_schema["x-enum-descriptions"] == ["Create item", "Update item"]


def test_model_to_pydantic_exposes_numeric_wire_formats():
    class NumericPayload(Model):
        small = Int32(description="small")
        large = Int64(description="large")
        unsigned = Uint64(description="unsigned")
        ratio = Float32(description="ratio")
        precise = Float64(description="precise")

    schema = model_to_pydantic(NumericPayload).model_json_schema()
    properties = schema["properties"]

    assert properties["small"]["format"] == "int32"
    assert properties["large"]["format"] == "int64"
    assert properties["unsigned"]["x-api-blueprint-format"] == "uint64"
    assert properties["ratio"]["format"] == "float"
    assert properties["precise"]["format"] == "double"


def test_dynamic_enum_schema_extensions_do_not_require_source_comments():
    dynamic_kind = enum.IntEnum("DynamicKind", {"CREATE": 1, "UPDATE": 2})

    assert enum_schema_extensions(dynamic_kind) == {
        "x-enumNames": ["CREATE", "UPDATE"],
        "x-enum-varnames": ["CREATE", "UPDATE"],
    }


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


def test_model_to_pydantic_isolates_same_named_dynamic_model_identity():
    first_model = create_model("REQ_Config_QUERY", {"id": Int(omitempty=True)}).__class__
    second_model = create_model(
        "REQ_Config_QUERY",
        {
            "page": Int(omitempty=True),
            "size": Int(omitempty=True),
        },
    ).__class__

    first_pydantic = model_to_pydantic(first_model)
    second_pydantic = model_to_pydantic(second_model)

    assert first_pydantic.__name__.startswith("REQ_Config_QUERY__")
    assert second_pydantic.__name__.startswith("REQ_Config_QUERY__")
    assert first_pydantic.__name__ != second_pydantic.__name__
    assert first_pydantic.model_json_schema()["title"] == "REQ_Config_QUERY"
    assert second_pydantic.model_json_schema()["title"] == "REQ_Config_QUERY"


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


def test_legacy_json_compat_fields_support_nested_shapes():
    class LegacyPayload(Model):
        target = OneOf(String(), Array[String](), description="target")
        ids = Array[OneOf(String(), Int())](description="ids")
        normalized = Array[LegacyStringID](description="normalized ids")

    pydantic_model = model_to_pydantic(LegacyPayload)

    assert LegacyPayload.target.__type__ == "one_of"
    assert [getattr(variant, "__type__", "") for variant in LegacyPayload.target.variants] == ["string", "array"]
    assert LegacyPayload.ids.elem_type().__type__ == "one_of"
    assert LegacyPayload.normalized.elem_type().__type__ == "coerce_string"
    assert set(pydantic_model.model_fields) == {"target", "ids", "normalized"}


def test_string_or_int_as_string_is_deprecated_alias_for_legacy_string_id():
    with pytest.warns(DeprecationWarning, match="StringOrIntAsString is deprecated"):
        field = StringOrIntAsString(description="legacy id")

    assert isinstance(field, LegacyStringID)
    assert field.__type__ == "coerce_string"
    assert [getattr(variant, "__type__", "") for variant in field.accepts] == ["string", "int"]


def test_legacy_json_compat_fields_reject_unsupported_variants():
    with pytest.raises(ValueError, match="OneOf requires"):
        OneOf()

    with pytest.raises(ValueError, match="CoerceString only accepts"):
        CoerceString(accepts=(String, Float))


def _schema_by_title(definitions: dict, title: str) -> dict:
    for schema in definitions.values():
        if schema.get("title") == title:
            return schema
    raise AssertionError(f"schema with title {title!r} not found")
