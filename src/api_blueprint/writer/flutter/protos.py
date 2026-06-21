from __future__ import annotations

import enum
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Type, Union, get_origin

from api_blueprint.engine.model import (
    AnonKV,
    Array,
    Bool,
    Byte,
    CoerceString,
    Enum as ModelEnum,
    Field,
    FieldWrappedModel,
    FileField,
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
    OneOf,
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
from api_blueprint.engine.schema.enum_metadata import enum_comment_text, enum_value_metadata
from api_blueprint.engine.utils import is_parametrized

from .naming import to_dart_identifier, to_dart_type_name


@dataclass
class DartResolvedType:
    text: str
    deps: set["DartProto"] = field(default_factory=set)
    decoder: str = "apiBlueprintReadAny"

    def nullable_text(self) -> str:
        return self.text if self.text.endswith("?") else f"{self.text}?"

    def decode_expr(self, value_expr: str) -> str:
        if self.decoder.startswith("("):
            return f"({self.decoder})({value_expr})"
        return f"{self.decoder}({value_expr})"

    def decode_required_expr(self, value_expr: str, label: str | None = None) -> str:
        type_label = label or self.text
        return f"apiBlueprintRequire<{self.text}>({self.decode_expr(value_expr)}, {json.dumps(type_label)})"


@dataclass
class DartEnumMember:
    name: str
    value: Any
    description: str | None = None

    @property
    def comment(self) -> str:
        return enum_comment_text(self.description)


@dataclass
class DartProtoField:
    name: str
    wire_name: str
    type: DartResolvedType
    optional: bool
    description: str | None = None


@dataclass(eq=False)
class DartProto:
    name: str
    model: Optional[object]
    kind: str
    module: str = "shared"
    alias_type: Optional[DartResolvedType] = None
    enum_members: Optional[list[DartEnumMember]] = None
    enum_wire_type: str | None = None
    fields: list[DartProtoField] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)

    def add_tag(self, tag: str | None) -> None:
        if tag:
            self.tags.add(tag)

    def dependencies(self) -> set["DartProto"]:
        deps: set[DartProto] = set()
        for proto_field in self.fields:
            deps |= proto_field.type.deps
        if self.alias_type is not None:
            deps |= self.alias_type.deps
        deps.discard(self)
        return deps

    def enum_wire_literal(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)


class DartTypeResolver:
    def __init__(self, registry: "DartProtoRegistry"):
        self.registry = registry

    def resolve(self, field: Union[Field, Model, Type[Any], Any], *, module: str | None = None) -> DartResolvedType:
        if is_parametrized(field):
            field = field()

        if isinstance(field, type) and issubclass(field, Field):
            field = field()

        if isinstance(field, CoerceString):
            return DartResolvedType("String", decoder="apiBlueprintReadCoerceString")
        if isinstance(field, String):
            return DartResolvedType("String", decoder="apiBlueprintReadString")
        if isinstance(field, FileField):
            return DartResolvedType("ApiFilePart", decoder="ApiFilePart.fromJson")
        if isinstance(field, Bool):
            return DartResolvedType("bool", decoder="apiBlueprintReadBool")
        if isinstance(field, (Int, Int64, Int32, Int16, Int8, Uint, Uint64, Uint32, Uint16, Uint8, Byte)):
            return DartResolvedType("int", decoder="apiBlueprintReadInt")
        if isinstance(field, (Float, Float32, Float64)):
            return DartResolvedType("double", decoder="apiBlueprintReadDouble")
        if isinstance(field, Null) or type(field) is Field:
            return DartResolvedType("Object?", decoder="apiBlueprintReadAny")
        if isinstance(field, ModelEnum):
            enum_cls = field.enum_type()
            if isinstance(enum_cls, type) and issubclass(enum_cls, enum.Enum):
                proto = self.registry.ensure_enum(enum_cls)
                return DartResolvedType(proto.name, {proto}, decoder=f"{proto.name}FromJson")
            return DartResolvedType("String", decoder="apiBlueprintReadString")
        if isinstance(field, enum.EnumMeta):
            proto = self.registry.ensure_enum(field)
            return DartResolvedType(proto.name, {proto}, decoder=f"{proto.name}FromJson")
        if isinstance(field, Array):
            elem_type = self.resolve(field.elem_type(), module=module)
            return DartResolvedType(
                f"List<{elem_type.text}>",
                set(elem_type.deps),
                decoder=f"(value) => apiBlueprintReadList<{elem_type.text}>(value, {elem_type.decoder})",
            )
        if isinstance(field, Map):
            value_type = self.resolve(field.value_type(), module=module)
            return DartResolvedType(
                f"Map<String, {value_type.text}>",
                set(value_type.deps),
                decoder=f"(value) => apiBlueprintReadStringMap<{value_type.text}>(value, {value_type.decoder})",
            )
        if isinstance(field, AnonKV):
            obj = field.get_obj()
            if obj is None:
                return DartResolvedType("Map<String, Object?>", decoder="apiBlueprintReadObject")
            return self.resolve(obj, module=module)
        if isinstance(field, FieldWrappedModel):
            return self.resolve(field.__field_type__, module=module)
        if isinstance(field, OneOf):
            return DartResolvedType("Object?", decoder="apiBlueprintReadAny")
        if isinstance(field, Model) or (isinstance(field, type) and issubclass(field, Model)):
            cls = unwrap_model_type(field)
            is_auto = bool(getattr(cls, "__auto__", False))
            owner_module = module if is_auto and module else "shared"
            owner_tag = "route" if owner_module != "shared" else "shared"
            proto = self.registry.ensure(field, tag=owner_tag, module=owner_module)
            if proto is None:
                return DartResolvedType("Object?", decoder="apiBlueprintReadAny")
            return DartResolvedType(proto.name, {proto}, decoder=f"{proto.name}.fromJsonValue")

        origin = get_origin(field)
        if origin and isinstance(origin, type):
            return self.resolve(origin, module=module)
        return DartResolvedType("Object?", decoder="apiBlueprintReadAny")


class DartProtoRegistry:
    def __init__(self):
        self._resolver = DartTypeResolver(self)
        self._protos: "OrderedDict[tuple[Any, str | None], DartProto]" = OrderedDict()
        self._aliases: "OrderedDict[str, DartProto]" = OrderedDict()
        self._enums: "OrderedDict[type[enum.Enum], DartProto]" = OrderedDict()

    def resolver(self) -> DartTypeResolver:
        return self._resolver

    def protos(self) -> Iterable[DartProto]:
        yield from self._protos.values()
        yield from self._aliases.values()
        yield from self._enums.values()

    def filter(self, *, tag: str | None = None, module: str | None = None) -> list[DartProto]:
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
    ) -> Optional[DartProto]:
        if model is None:
            return None

        effective_module = module or "shared"

        if isinstance(model, FieldWrappedModel):
            dart_name = to_dart_type_name(name or getattr(model, "__name__", "Alias"))
            proto = self._aliases.get(dart_name)
            if proto is not None:
                proto.add_tag(tag)
                return proto
            alias_type = self._resolver.resolve(model.__field_type__, module=effective_module)
            proto = DartProto(name=dart_name, model=None, kind="alias", alias_type=alias_type, module=effective_module)
            proto.add_tag(tag)
            self._aliases[dart_name] = proto
            return proto

        cls = unwrap_model_type(model)
        origin = get_origin(cls)
        if origin is not None:
            try:
                if issubclass(origin, Model):
                    cls = origin
            except TypeError:
                pass
        auto_flag = bool(getattr(cls, "__auto__", False))
        proto_key = (cls, name if auto_flag else None)
        proto = self._protos.get(proto_key)
        if proto is not None:
            proto.add_tag(tag)
            return proto

        dart_name = to_dart_type_name(name or getattr(cls, "__name__", "Model"))
        proto = DartProto(name=dart_name, model=cls, kind="data", module=effective_module)
        proto.add_tag(tag)
        self._protos[proto_key] = proto
        self._build_proto(proto)
        return proto

    def register_alias(
        self,
        name: str,
        type_expr: DartResolvedType,
        *,
        tag: str | None = None,
        module: str | None = None,
    ) -> DartProto:
        dart_name = to_dart_type_name(name)
        proto = self._aliases.get(dart_name)
        if proto is not None:
            proto.alias_type = type_expr
            proto.add_tag(tag)
            return proto
        proto = DartProto(name=dart_name, model=None, kind="alias", alias_type=type_expr, module=module or "shared")
        proto.add_tag(tag)
        self._aliases[dart_name] = proto
        return proto

    def ensure_enum(self, enum_cls: type[enum.Enum], *, module: str = "shared") -> DartProto:
        proto = self._enums.get(enum_cls)
        if proto is not None:
            return proto
        proto = DartProto(
            name=to_dart_type_name(enum_cls.__name__),
            model=None,
            kind="enum",
            module=module,
            enum_members=build_enum_members(enum_cls),
            enum_wire_type=detect_enum_wire_type(enum_cls),
        )
        proto.add_tag("shared")
        self._enums[enum_cls] = proto
        return proto

    def _build_proto(self, proto: DartProto) -> None:
        if proto.model is None:
            return

        pyd_model = model_to_pydantic(proto.model)
        for name, model_field in iter_model_vars(proto.model):
            if not isinstance(model_field, (Field, Model)):
                continue
            field_info = pyd_model.model_fields[name]
            extra = getattr(model_field, "__extra__", {}) or {}
            wire_name = extra.get("alias") or name
            resolved = self._resolver.resolve(model_field, module=proto.module)
            optional = (not field_info.is_required()) or bool(extra.get("omitempty", False))
            proto.fields.append(
                DartProtoField(
                    name=to_dart_identifier(wire_name),
                    wire_name=wire_name,
                    type=resolved,
                    optional=optional,
                    description=field_info.description or "",
                )
            )


def detect_enum_wire_type(enum_cls: type[enum.Enum]) -> str:
    values = [member.value for member in enum_cls]
    if values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return "int"
    return "string"


def build_enum_members(enum_cls: type[enum.Enum]) -> list[DartEnumMember]:
    used: set[str] = set()
    members: list[DartEnumMember] = []
    for member in enum_value_metadata(enum_cls):
        base_name = to_dart_identifier(member.name, fallback="value")
        name = base_name
        suffix = 2
        while name in used:
            name = f"{base_name}{suffix}"
            suffix += 1
        used.add(name)
        members.append(DartEnumMember(name, member.value, member.description))
    return members
