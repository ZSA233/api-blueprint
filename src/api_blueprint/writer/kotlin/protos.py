from __future__ import annotations

import enum
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Type, Union, get_origin

from api_blueprint.engine.model import (
    AnyModel,
    AnonKV,
    Array,
    Bool,
    Byte,
    Enum as ModelEnum,
    Field,
    FieldWrappedModel,
    Float,
    Float32,
    Float64,
    Int,
    Int8,
    Int16,
    Int32,
    Int64,
    Map,
    Model,
    Null,
    String,
    Uint,
    Uint8,
    Uint16,
    Uint32,
    Uint64,
    iter_model_vars,
    model_to_pydantic,
    unwrap_model_type,
)
from api_blueprint.engine.utils import is_parametrized

from .naming import to_kotlin_property_name, to_kotlin_type_name


@dataclass
class KotlinResolvedType:
    text: str
    deps: set["KotlinProto"] = field(default_factory=set)
    serializer: str | None = None
    query_value: str = "to_string"

    def serializer_expr(self) -> str:
        if self.serializer is not None:
            return self.serializer
        return f"{self.text}.serializer()"

    def query_expr(self, receiver: str, *, optional: bool) -> str:
        accessor = "?." if optional else "."
        if self.query_value == "wire_value":
            return f"{receiver}{accessor}wireValue{accessor}toString()"
        return f"{receiver}{accessor}toString()"

    def as_nullable(self) -> "KotlinResolvedType":
        if self.text.endswith("?"):
            return self
        return KotlinResolvedType(
            self.text + "?",
            set(self.deps),
            serializer=f"{self.serializer_expr()}.nullable",
            query_value=self.query_value,
        )


@dataclass
class KotlinProtoField:
    name: str
    serial_name: str
    type: KotlinResolvedType
    optional: bool
    description: str | None = None


@dataclass(eq=False)
class KotlinProto:
    name: str
    model: Optional[AnyModel]
    kind: str
    module: str = "shared"
    alias_type: Optional[KotlinResolvedType] = None
    enum_members: Optional[list[tuple[str, Any]]] = None
    enum_wire_type: str | None = None
    fields: list[KotlinProtoField] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)

    def add_tag(self, tag: str | None) -> None:
        if tag:
            self.tags.add(tag)

    def dependencies(self) -> set["KotlinProto"]:
        deps: set[KotlinProto] = set()
        for proto_field in self.fields:
            deps |= proto_field.type.deps
        if self.alias_type is not None:
            deps |= self.alias_type.deps
        deps.discard(self)
        return deps

    def serializer_expr(self) -> str:
        if self.kind == "alias" and self.alias_type is not None:
            return self.alias_type.serializer_expr()
        return f"{self.name}.serializer()"

    def enum_wire_literal(self, value: Any) -> str:
        if self.enum_wire_type == "int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"[kotlin-client] Kotlin enum {self.name} 需要 int wire value")
            return str(value)
        return json.dumps(str(value))


class KotlinTypeResolver:
    def __init__(self, registry: "KotlinProtoRegistry"):
        self.registry = registry

    def resolve(self, field: Union[Field, Model, Type[Any], Any], *, module: str | None = None) -> KotlinResolvedType:
        if is_parametrized(field):
            field = field()

        if isinstance(field, type) and issubclass(field, Field):
            field = field()

        if isinstance(field, String):
            return KotlinResolvedType("String", serializer="String.serializer()")
        if isinstance(field, Bool):
            return KotlinResolvedType("Boolean", serializer="Boolean.serializer()")
        if isinstance(field, (Int64, Uint64)):
            return KotlinResolvedType("Long", serializer="Long.serializer()")
        if isinstance(field, (Int, Int32, Int16, Int8, Uint, Uint32, Uint16, Uint8, Byte)):
            return KotlinResolvedType("Int", serializer="Int.serializer()")
        if isinstance(field, Float64):
            return KotlinResolvedType("Double", serializer="Double.serializer()")
        if isinstance(field, (Float, Float32)):
            return KotlinResolvedType("Float", serializer="Float.serializer()")
        if isinstance(field, Null):
            return KotlinResolvedType(
                "kotlinx.serialization.json.JsonElement",
                serializer="kotlinx.serialization.json.JsonElement.serializer()",
            )
        if type(field) is Field:
            return KotlinResolvedType(
                "kotlinx.serialization.json.JsonElement",
                serializer="kotlinx.serialization.json.JsonElement.serializer()",
            )
        if isinstance(field, ModelEnum):
            enum_cls = field.enum_type()
            if isinstance(enum_cls, type) and issubclass(enum_cls, enum.Enum):
                proto = self.registry.ensure_enum(enum_cls)
                return KotlinResolvedType(
                    proto.name,
                    {proto},
                    serializer=f"{proto.name}.serializer()",
                    query_value="wire_value",
                )
            return KotlinResolvedType("String", serializer="String.serializer()")
        if isinstance(field, enum.EnumMeta):
            proto = self.registry.ensure_enum(field)
            return KotlinResolvedType(
                proto.name,
                {proto},
                serializer=f"{proto.name}.serializer()",
                query_value="wire_value",
            )
        if isinstance(field, Array):
            elem = field.elem_type()
            elem_type = self.resolve(elem, module=module)
            return KotlinResolvedType(
                f"List<{elem_type.text}>",
                set(elem_type.deps),
                serializer=f"ListSerializer({elem_type.serializer_expr()})",
            )
        if isinstance(field, Map):
            key_type = self.resolve(field.key_type(), module=module)
            value_type = self.resolve(field.value_type(), module=module)
            if key_type.text in {"String", "Int", "Long"}:
                key_text = key_type.text
                key_serializer = key_type.serializer_expr()
            else:
                key_text = "String"
                key_serializer = "String.serializer()"
            deps = set(key_type.deps) | set(value_type.deps)
            return KotlinResolvedType(
                f"Map<{key_text}, {value_type.text}>",
                deps,
                serializer=f"MapSerializer({key_serializer}, {value_type.serializer_expr()})",
            )
        if isinstance(field, AnonKV):
            obj = field.get_obj()
            if obj is None:
                return self.resolve(Map[String, Field](), module=module)
            return self.resolve(obj, module=module)
        if isinstance(field, FieldWrappedModel):
            return self.resolve(field.__field_type__, module=module)
        if isinstance(field, Model) or (isinstance(field, type) and issubclass(field, Model)):
            cls = unwrap_model_type(field)
            is_auto = bool(getattr(cls, "__auto__", False))
            owner_module = module if is_auto and module else "shared"
            owner_tag = "route" if owner_module != "shared" else "shared"
            proto = self.registry.ensure(field, tag=owner_tag, module=owner_module)
            if proto is None:
                return KotlinResolvedType(
                    "kotlinx.serialization.json.JsonElement",
                    serializer="kotlinx.serialization.json.JsonElement.serializer()",
                )
            return KotlinResolvedType(proto.name, {proto}, serializer=f"{proto.name}.serializer()")

        origin = get_origin(field)
        if origin and isinstance(origin, type):
            return self.resolve(origin, module=module)
        return KotlinResolvedType(
            "kotlinx.serialization.json.JsonElement",
            serializer="kotlinx.serialization.json.JsonElement.serializer()",
        )


class KotlinProtoRegistry:
    def __init__(self):
        self._resolver = KotlinTypeResolver(self)
        self._protos: "OrderedDict[tuple[Any, str | None], KotlinProto]" = OrderedDict()
        self._aliases: "OrderedDict[str, KotlinProto]" = OrderedDict()
        self._enums: "OrderedDict[type[enum.Enum], KotlinProto]" = OrderedDict()

    def resolver(self) -> KotlinTypeResolver:
        return self._resolver

    def protos(self) -> Iterable[KotlinProto]:
        yield from self._protos.values()
        yield from self._aliases.values()
        yield from self._enums.values()

    def filter(self, *, tag: str | None = None, module: str | None = None) -> list[KotlinProto]:
        result = []
        for proto in self.protos():
            if tag and tag not in proto.tags:
                continue
            if module and proto.module != module:
                continue
            result.append(proto)
        return sorted(result, key=lambda proto: proto.name)

    def ensure(
        self,
        model: Optional[Union[type[Model], Model]],
        *,
        name: str | None = None,
        tag: str | None = None,
        module: str | None = None,
    ) -> Optional[KotlinProto]:
        if model is None:
            return None

        effective_module = module or "shared"

        if isinstance(model, FieldWrappedModel):
            kotlin_name = to_kotlin_type_name(name or getattr(model, "__name__", "Alias"))
            proto = self._aliases.get(kotlin_name)
            if proto is not None:
                proto.add_tag(tag)
                return proto
            alias_type = self._resolver.resolve(model.__field_type__, module=effective_module)
            proto = KotlinProto(name=kotlin_name, model=None, kind="alias", alias_type=alias_type, module=effective_module)
            proto.add_tag(tag)
            self._aliases[kotlin_name] = proto
            return proto

        cls = unwrap_model_type(model)
        auto_flag = bool(getattr(cls, "__auto__", False))
        proto_key = (cls, name if auto_flag else None)
        proto = self._protos.get(proto_key)
        if proto is not None:
            proto.add_tag(tag)
            return proto

        kotlin_name = to_kotlin_type_name(name or getattr(cls, "__name__", "Model"))
        proto = KotlinProto(name=kotlin_name, model=cls, kind="data", module=effective_module)
        proto.add_tag(tag)
        self._protos[proto_key] = proto
        self._build_proto(proto)
        return proto

    def register_alias(
        self,
        name: str,
        type_expr: KotlinResolvedType,
        *,
        tag: str | None = None,
        module: str | None = None,
    ) -> KotlinProto:
        kotlin_name = to_kotlin_type_name(name)
        proto = self._aliases.get(kotlin_name)
        if proto is not None:
            proto.alias_type = type_expr
            proto.add_tag(tag)
            return proto
        proto = KotlinProto(name=kotlin_name, model=None, kind="alias", alias_type=type_expr, module=module or "shared")
        proto.add_tag(tag)
        self._aliases[kotlin_name] = proto
        return proto

    def ensure_enum(
        self,
        enum_cls: type[enum.Enum],
        *,
        module: str = "shared",
    ) -> KotlinProto:
        proto = self._enums.get(enum_cls)
        if proto is not None:
            return proto
        proto = KotlinProto(
            name=to_kotlin_type_name(enum_cls.__name__),
            model=None,
            kind="enum",
            module=module,
            enum_members=[(member.name, member.value) for member in enum_cls],
            enum_wire_type=detect_enum_wire_type(enum_cls),
        )
        proto.add_tag("shared")
        self._enums[enum_cls] = proto
        return proto

    def _build_proto(self, proto: KotlinProto) -> None:
        if proto.model is None:
            return

        pyd_model = model_to_pydantic(proto.model)
        for name, model_field in iter_model_vars(proto.model):
            if not isinstance(model_field, (Field, Model)):
                continue

            field_info = pyd_model.model_fields[name]
            extra = getattr(model_field, "__extra__", {}) or {}
            serial_name = extra.get("alias") or name
            resolved = self._resolver.resolve(model_field, module=proto.module)
            optional = (not field_info.is_required()) or bool(extra.get("omitempty", False))
            field_type = resolved
            if optional and not resolved.text.endswith("?"):
                field_type = resolved.as_nullable()
            proto.fields.append(
                KotlinProtoField(
                    name=to_kotlin_property_name(serial_name),
                    serial_name=serial_name,
                    type=field_type,
                    optional=optional,
                    description=field_info.description or "",
                )
            )


def detect_enum_wire_type(enum_cls: type[enum.Enum]) -> str:
    values = [member.value for member in enum_cls]
    if not values:
        raise ValueError(f"[kotlin-client] Kotlin enum {enum_cls.__name__} 没有可生成的成员")
    if all(isinstance(value, str) for value in values):
        return "string"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return "int"
    value_types = ", ".join(sorted({type(value).__name__ for value in values}))
    raise ValueError(
        f"[kotlin-client] Kotlin enum {enum_cls.__name__} 只支持 string/int wire value，当前类型: {value_types}"
    )
