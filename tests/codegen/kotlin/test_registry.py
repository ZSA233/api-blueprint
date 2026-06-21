from __future__ import annotations

from .helpers import *


def test_kotlin_name_helpers_preserve_expected_output():
    assert to_kotlin_type_name("/api/demo/1put") == "ApiDemo1put"
    assert to_kotlin_property_name("delete$") == "delete"
    assert to_kotlin_property_name("class") == "`class`"

def test_kotlin_registry_builds_serializable_model_fields():
    registry = KotlinProtoRegistry()
    proto = registry.ensure(Payload, tag="shared")

    assert proto is not None
    assert proto.name == "Payload"
    assert proto.module == "shared"
    assert [field.name for field in proto.fields] == ["userId", "scores"]
    assert [field.serial_name for field in proto.fields] == ["user_id", "scores"]
    assert [field.type.text for field in proto.fields] == ["String", "List<Long>"]

def test_kotlin_registry_builds_serializers_for_alias_and_enum_types():
    registry = KotlinProtoRegistry()
    enum_type = registry.resolver().resolve(Enum[WireEnum]())
    map_type = registry.resolver().resolve(Map[String, Array[Enum[WireEnum]]]())
    int_enum_proto = registry.ensure_enum(StatusEnum)

    assert enum_type.serializer_expr() == "WireEnum.serializer()"
    assert enum_type.query_expr("kind", optional=False) == "kind.wireValue.toString()"
    assert enum_type.query_expr("kind", optional=True) == "kind?.wireValue?.toString()"
    assert map_type.serializer_expr() == "MapSerializer(String.serializer(), ListSerializer(WireEnum.serializer()))"
    assert int_enum_proto.enum_wire_type == "int"
    assert int_enum_proto.enum_wire_literal(StatusEnum.PENDING.value) == "1"
    assert int_enum_proto.enum_members[0].comment == "Pending status"


def test_kotlin_generated_enums_include_member_comments(tmp_path):
    class EnumPayload(Model):
        status = Enum[StatusEnum](description="status")
        wire = Enum[WireEnum](description="wire")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.POST("/enum").REQ(EnumPayload).RSP(EnumPayload)

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated")
    writer.register(bp)
    writer.gen()

    runtime_types = (
        tmp_path / "kotlin" / "com" / "example" / "generated" / "api" / "runtime" / "GenApiTypes.kt"
    ).read_text(encoding="utf-8")
    assert "/** Pending status */" in runtime_types
    assert "PENDING(1)" in runtime_types
    assert "/** First option */" in runtime_types
    assert 'FIRST("first")' in runtime_types

def test_kotlin_uses_declarative_response_envelope_spec():
    spec = CodeMessageDataEnvelope.envelope_spec()

    assert spec["kind"] == "code_message_data"
    assert spec["error_identity"] == "nested"
    assert spec["fields"]["data"] == "data"
    assert spec["fields"]["error"] == "error"

def test_kotlin_registry_filter_by_module():
    registry = KotlinProtoRegistry()
    shared = registry.ensure(Payload, tag="shared", module="shared")
    # User-defined models always stay in shared, even if re-requested with a route module
    route = registry.ensure(Payload, name="RoutePayload", tag="route", module="demo")
    assert route is shared
    assert route.module == "shared"

    assert len(registry.filter(module="shared")) >= 1
    # Only in shared, not in demo (user-defined model class key is deduplicated)
    assert len(registry.filter(module="demo")) == 0
