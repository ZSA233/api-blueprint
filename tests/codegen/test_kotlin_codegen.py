from __future__ import annotations

import enum

import pytest

from api_blueprint.engine import Blueprint
from api_blueprint.engine.model import Array, Enum, Int64, Map, Model, String
from api_blueprint.writer.kotlin import KotlinProtoRegistry, KotlinRouteSelection, KotlinWriter, to_kotlin_property_name, to_kotlin_type_name


class WireEnum(enum.StrEnum):
    FIRST = "first"
    SECOND = "second"


class StatusEnum(enum.IntEnum):
    PENDING = 1
    RUNNING = 2


class Payload(Model):
    user_id = String(alias="user_id", description="user id")
    scores = Array[Int64](description="scores")


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


def test_kotlin_registry_filter_by_module():
    from api_blueprint.engine.model import String

    registry = KotlinProtoRegistry()
    shared = registry.ensure(Payload, tag="shared", module="shared")
    # User-defined models always stay in shared, even if re-requested with a route module
    route = registry.ensure(Payload, name="RoutePayload", tag="route", module="demo")
    assert route is shared
    assert route.module == "shared"

    assert len(registry.filter(module="shared")) >= 1
    # Only in shared, not in demo (user-defined model class key is deduplicated)
    assert len(registry.filter(module="demo")) == 0


def test_kotlin_selection_matches_path_tag_group_method_and_name(example_entrypoints):
    _config, entrypoints = example_entrypoints
    router = next(router for bp in entrypoints for _group, router in bp.iter_router() if router.url == "/api/demo/abc")

    assert KotlinRouteSelection(include=("path:/api/demo/*",)).includes(router, route_name="Abc")
    assert KotlinRouteSelection(include=("tag:api",)).includes(router, route_name="Abc")
    assert KotlinRouteSelection(include=("group:demo",)).includes(router, route_name="Abc")
    assert KotlinRouteSelection(include=("method:GET",)).includes(router, route_name="Abc")
    assert KotlinRouteSelection(include=("name:Abc",)).includes(router, route_name="Abc")
    assert not KotlinRouteSelection(include=("tag:api",), exclude=("path:/api/demo/*",)).includes(
        router,
        route_name="Abc",
    )


def test_kotlin_writer_rejects_long_connection_routes(tmp_path):
    class StreamMessage(Model):
        message = String(description="message")

    bp = Blueprint(root="/api")
    with bp.group("/demo") as views:
        views.STREAM("/events").SERVER_MESSAGE(StreamMessage)

    writer = KotlinWriter(tmp_path / "kotlin", package="com.example.generated")
    writer.register(bp)

    with pytest.raises(ValueError, match="暂不支持长连接 route"):
        writer.gen()
