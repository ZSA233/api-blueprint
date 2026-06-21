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

from .naming import to_swift_identifier, to_swift_type_name


@dataclass
class SwiftResolvedType:
    text: str
    deps: set["SwiftProto"] = field(default_factory=set)
    contains_one_of: bool = False

    def optional_text(self) -> str:
        return self.text if self.text.endswith("?") else f"{self.text}?"


@dataclass
class SwiftEnumMember:
    name: str
    value: Any
    description: str | None = None

    @property
    def comment(self) -> str:
        return enum_comment_text(self.description)


@dataclass
class SwiftProtoField:
    name: str
    wire_name: str
    type: SwiftResolvedType
    optional: bool
    description: str | None = None
    coerce_string: bool = False
    coerce_string_array: bool = False
    contains_one_of: bool = False

    @property
    def swift_type(self) -> str:
        return self.type.optional_text() if self.optional else self.type.text


@dataclass(eq=False)
class SwiftProto:
    name: str
    model: Optional[object]
    kind: str
    module: str = "shared"
    alias_type: Optional[SwiftResolvedType] = None
    enum_members: Optional[list[SwiftEnumMember]] = None
    enum_wire_type: str | None = None
    one_of_variants: Optional[list["SwiftOneOfVariant"]] = None
    fields: list[SwiftProtoField] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)

    def add_tag(self, tag: str | None) -> None:
        if tag:
            self.tags.add(tag)

    def dependencies(self) -> set["SwiftProto"]:
        deps: set[SwiftProto] = set()
        for proto_field in self.fields:
            deps |= proto_field.type.deps
        if self.alias_type is not None:
            deps |= self.alias_type.deps
        deps.discard(self)
        return deps

    @property
    def raw_value_type(self) -> str:
        return "Int" if self.enum_wire_type == "int" else "String"

    def enum_wire_literal(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @property
    def requires_custom_decode(self) -> bool:
        return any(field.coerce_string or field.coerce_string_array or field.contains_one_of for field in self.fields)


@dataclass
class SwiftOneOfVariant:
    case_name: str
    type: SwiftResolvedType

    @property
    def swift_type(self) -> str:
        return self.type.text


class SwiftTypeResolver:
    def __init__(self, registry: "SwiftProtoRegistry"):
        self.registry = registry

    def resolve(self, field: Union[Field, Model, Type[Any], Any], *, module: str | None = None) -> SwiftResolvedType:
        if is_parametrized(field):
            field = field()

        if isinstance(field, type) and issubclass(field, Field):
            field = field()

        if isinstance(field, CoerceString):
            return SwiftResolvedType("String")
        if isinstance(field, String):
            return SwiftResolvedType("String")
        if isinstance(field, FileField):
            return SwiftResolvedType("APIFilePart")
        if isinstance(field, Bool):
            return SwiftResolvedType("Bool")
        if isinstance(field, (Int, Int64, Int32, Int16, Int8, Uint, Uint64, Uint32, Uint16, Uint8, Byte)):
            return SwiftResolvedType("Int")
        if isinstance(field, (Float, Float32, Float64)):
            return SwiftResolvedType("Double")
        if isinstance(field, Null) or type(field) is Field:
            return SwiftResolvedType("APIJSONValue")
        if isinstance(field, ModelEnum):
            enum_cls = field.enum_type()
            if isinstance(enum_cls, type) and issubclass(enum_cls, enum.Enum):
                proto = self.registry.ensure_enum(enum_cls)
                return SwiftResolvedType(proto.name, {proto})
            return SwiftResolvedType("String")
        if isinstance(field, enum.EnumMeta):
            proto = self.registry.ensure_enum(field)
            return SwiftResolvedType(proto.name, {proto})
        if isinstance(field, Array):
            elem_type = self.resolve(field.elem_type(), module=module)
            return SwiftResolvedType(f"[{elem_type.text}]", set(elem_type.deps), elem_type.contains_one_of)
        if isinstance(field, Map):
            value_type = self.resolve(field.value_type(), module=module)
            return SwiftResolvedType(f"[String: {value_type.text}]", set(value_type.deps), value_type.contains_one_of)
        if isinstance(field, AnonKV):
            obj = field.get_obj()
            if obj is None:
                return SwiftResolvedType("[String: APIJSONValue]")
            return self.resolve(obj, module=module)
        if isinstance(field, FieldWrappedModel):
            return self.resolve(field.__field_type__, module=module)
        if isinstance(field, OneOf):
            proto = self.registry.ensure_one_of(field, module=module or "shared")
            return SwiftResolvedType(proto.name, {proto}, True)
        if isinstance(field, Model) or (isinstance(field, type) and issubclass(field, Model)):
            cls = unwrap_model_type(field)
            is_auto = bool(getattr(cls, "__auto__", False))
            owner_module = module if is_auto and module else "shared"
            owner_tag = "route" if owner_module != "shared" else "shared"
            proto = self.registry.ensure(field, tag=owner_tag, module=owner_module)
            if proto is None:
                return SwiftResolvedType("APIJSONValue")
            return SwiftResolvedType(proto.name, {proto})

        origin = get_origin(field)
        if origin and isinstance(origin, type):
            return self.resolve(origin, module=module)
        return SwiftResolvedType("APIJSONValue")


class SwiftProtoRegistry:
    def __init__(self):
        self._resolver = SwiftTypeResolver(self)
        self._protos: "OrderedDict[tuple[Any, str | None], SwiftProto]" = OrderedDict()
        self._aliases: "OrderedDict[str, SwiftProto]" = OrderedDict()
        self._enums: "OrderedDict[type[enum.Enum], SwiftProto]" = OrderedDict()
        self._one_ofs: "OrderedDict[tuple[str, ...], SwiftProto]" = OrderedDict()

    def resolver(self) -> SwiftTypeResolver:
        return self._resolver

    def protos(self) -> Iterable[SwiftProto]:
        yield from self._protos.values()
        yield from self._aliases.values()
        yield from self._enums.values()
        yield from self._one_ofs.values()

    def filter(self, *, tag: str | None = None, module: str | None = None) -> list[SwiftProto]:
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
    ) -> Optional[SwiftProto]:
        if model is None:
            return None

        effective_module = module or "shared"

        if isinstance(model, FieldWrappedModel):
            swift_name = to_swift_type_name(name or getattr(model, "__name__", "Alias"))
            proto = self._aliases.get(swift_name)
            if proto is not None:
                proto.add_tag(tag)
                return proto
            alias_type = self._resolver.resolve(model.__field_type__, module=effective_module)
            proto = SwiftProto(name=swift_name, model=None, kind="alias", alias_type=alias_type, module=effective_module)
            proto.add_tag(tag)
            self._aliases[swift_name] = proto
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

        swift_name = to_swift_type_name(name or getattr(cls, "__name__", "Model"))
        proto = SwiftProto(name=swift_name, model=cls, kind="data", module=effective_module)
        proto.add_tag(tag)
        self._protos[proto_key] = proto
        self._build_proto(proto)
        return proto

    def register_alias(
        self,
        name: str,
        type_expr: SwiftResolvedType,
        *,
        tag: str | None = None,
        module: str | None = None,
    ) -> SwiftProto:
        swift_name = to_swift_type_name(name)
        proto = self._aliases.get(swift_name)
        if proto is not None:
            proto.alias_type = type_expr
            proto.add_tag(tag)
            return proto
        proto = SwiftProto(name=swift_name, model=None, kind="alias", alias_type=type_expr, module=module or "shared")
        proto.add_tag(tag)
        self._aliases[swift_name] = proto
        return proto

    def ensure_enum(self, enum_cls: type[enum.Enum], *, module: str = "shared") -> SwiftProto:
        proto = self._enums.get(enum_cls)
        if proto is not None:
            return proto
        proto = SwiftProto(
            name=to_swift_type_name(enum_cls.__name__),
            model=None,
            kind="enum",
            module=module,
            enum_members=build_enum_members(enum_cls),
            enum_wire_type=detect_enum_wire_type(enum_cls),
        )
        proto.add_tag("shared")
        self._enums[enum_cls] = proto
        return proto

    def ensure_one_of(self, field: OneOf, *, module: str = "shared") -> SwiftProto:
        resolved_variants = [self._resolver.resolve(variant, module=module) for variant in field.variants]
        key = tuple(variant.text for variant in resolved_variants)
        existing = self._one_ofs.get(key)
        if existing is not None:
            existing.add_tag("shared" if module == "shared" else "route")
            return existing
        name = _swift_one_of_type_name(key)
        variants = [
            SwiftOneOfVariant(case_name=_swift_one_of_case_name(variant.text, index), type=variant)
            for index, variant in enumerate(resolved_variants)
        ]
        proto = SwiftProto(
            name=name,
            model=None,
            kind="one_of",
            module=module,
            one_of_variants=variants,
        )
        proto.add_tag("shared" if module == "shared" else "route")
        self._one_ofs[key] = proto
        return proto

    def _build_proto(self, proto: SwiftProto) -> None:
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
                SwiftProtoField(
                    name=to_swift_identifier(wire_name),
                    wire_name=wire_name,
                    type=resolved,
                    optional=optional,
                    description=field_info.description or "",
                    coerce_string=isinstance(model_field, CoerceString),
                    coerce_string_array=_is_coerce_string_array(model_field),
                    contains_one_of=resolved.contains_one_of,
                )
            )


def detect_enum_wire_type(enum_cls: type[enum.Enum]) -> str:
    values = [member.value for member in enum_cls]
    if values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return "int"
    return "string"


def build_enum_members(enum_cls: type[enum.Enum]) -> list[SwiftEnumMember]:
    used: set[str] = set()
    members: list[SwiftEnumMember] = []
    for member in enum_value_metadata(enum_cls):
        base_name = to_swift_identifier(member.name, fallback="value")
        name = base_name
        suffix = 2
        while name in used:
            name = f"{base_name}{suffix}"
            suffix += 1
        used.add(name)
        members.append(SwiftEnumMember(name, member.value, member.description))
    return members


def _swift_one_of_type_name(parts: tuple[str, ...]) -> str:
    raw = "Or".join(_swift_one_of_type_part(part) for part in parts) or "Value"
    return to_swift_type_name(f"API{raw}OneOf", fallback="APIOneOf")


def _swift_one_of_type_part(value: str) -> str:
    if value.startswith("[") and value.endswith("]"):
        return "ArrayOf" + _swift_one_of_type_part(value[1:-1].strip())
    if value.startswith("[String: ") and value.endswith("]"):
        return "MapOf" + _swift_one_of_type_part(value[len("[String: ") : -1].strip())
    cleaned = value.replace("?", " Optional")
    return to_swift_type_name(cleaned, fallback="Value")


def _swift_one_of_case_name(value: str, index: int) -> str:
    name = to_swift_identifier(_swift_one_of_type_part(value), fallback=f"value{index + 1}")
    return name[0].lower() + name[1:] if name else f"value{index + 1}"


def _is_coerce_string_array(field: object) -> bool:
    if not isinstance(field, Array):
        return False
    item = field.elem_type()
    if is_parametrized(item):
        item = item()
    if isinstance(item, type) and issubclass(item, Field):
        item = item()
    return isinstance(item, CoerceString)
