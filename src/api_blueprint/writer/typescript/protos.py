from __future__ import annotations

import enum
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Type, TypeVar, Union, get_origin, get_type_hints

from api_blueprint.engine.model import (
    AnyModel,
    AnonKV,
    Array,
    Enum as ModelEnum,
    Field,
    FieldWrappedModel,
    Map,
    Model,
    Null,
    iter_model_vars,
    model_to_pydantic,
    unwrap_model_type,
)
from api_blueprint.engine.utils import inc_to_letters, is_parametrized

from .naming import to_ts_identifier, to_ts_name


@dataclass
class TypeScriptResolvedType:
    text: str
    deps: set["TypeScriptProto"] = field(default_factory=set)


class TypeScriptTypeResolver:
    SIMPLE_TYPE_MAPPING: dict[str, str] = {
        "string": "string",
        "str": "string",
        "int": "number",
        "int64": "number",
        "int32": "number",
        "int16": "number",
        "int8": "number",
        "uint": "number",
        "uint64": "number",
        "uint32": "number",
        "uint16": "number",
        "uint8": "number",
        "float": "number",
        "float64": "number",
        "float32": "number",
        "boolean": "boolean",
        "bool": "boolean",
        "byte": "number",
        "null": "null",
        "any": "any",
    }

    def __init__(self, registry: "TypeScriptProtoRegistry"):
        self.registry = registry

    def resolve(self, field: Union[Field, Model, Type[Any], Any]) -> TypeScriptResolvedType:
        kind = self._infer_kind(field)
        if kind in self.SIMPLE_TYPE_MAPPING:
            return TypeScriptResolvedType(self.SIMPLE_TYPE_MAPPING[kind])

        resolver = {
            "array": self._resolve_array,
            "enum": self._resolve_enum,
            "map": self._resolve_map,
            "anonkv": self._resolve_anon_kv,
            "object": self._resolve_object,
        }.get(kind)
        if resolver is not None:
            return resolver(field)
        if self._is_model(field):
            return self._resolve_object(field)
        return TypeScriptResolvedType("any")

    def _infer_kind(self, field: Union[Field, Model, Type[Any], Any]) -> str:
        if isinstance(field, AnonKV):
            return "anonkv"

        candidate = field if isinstance(field, (Field, Model, type)) else field
        type_name = getattr(candidate, "__type__", None)
        if type_name:
            return type_name.lower()
        if isinstance(candidate, type):
            return candidate.__name__.lower()
        origin = get_origin(candidate)
        if origin:
            return self._infer_kind(origin)
        return candidate.__class__.__name__.lower()

    def _resolve_array(self, field: Union[Field, Type[Field], Any]) -> TypeScriptResolvedType:
        array_field = self._ensure_instance(field, Array)
        if not isinstance(array_field, Array):
            return TypeScriptResolvedType("any[]")
        elem = array_field.elem_type()
        if self._is_generic(elem):
            elem = elem()
        elem_type = self.resolve(elem)
        return TypeScriptResolvedType(f"Array<{elem_type.text}>", set(elem_type.deps))

    def _resolve_enum(self, field: Union[Field, Type[Field], enum.EnumMeta]) -> TypeScriptResolvedType:
        enum_cls = None
        if isinstance(field, ModelEnum):
            enum_cls = field.enum_type()
        elif isinstance(field, type) and issubclass(field, enum.Enum):
            enum_cls = field
        elif isinstance(field, Field) and isinstance(field.__class__, enum.EnumMeta):
            enum_cls = field.__class__

        if enum_cls is None:
            return TypeScriptResolvedType("string")

        values = [member.value for member in list(enum_cls)]
        if not values:
            return TypeScriptResolvedType("string")

        proto = self.registry.ensure_enum(enum_cls)
        return TypeScriptResolvedType(proto.name, {proto})

    def _resolve_map(self, field: Union[Map, Type[Map]]) -> TypeScriptResolvedType:
        map_field = self._ensure_instance(field, Map)
        if not isinstance(map_field, Map):
            return TypeScriptResolvedType("Record<string, any>")

        key_type = self.resolve(map_field.key_type())
        value_type = self.resolve(map_field.value_type())
        key_text = self._normalize_record_key(key_type.text)
        deps = set(key_type.deps) | set(value_type.deps)
        return TypeScriptResolvedType(f"Record<{key_text}, {value_type.text}>", deps)

    def _resolve_anon_kv(self, field: AnonKV) -> TypeScriptResolvedType:
        return self.resolve(field.get_obj())

    def _resolve_object(self, field: Union[Model, Type[Model]]) -> TypeScriptResolvedType:
        model_cls = unwrap_model_type(field)
        proto = self.registry.ensure(model_cls, tag="shared")
        return TypeScriptResolvedType(proto.name, {proto} if proto else set())

    def _ensure_instance(self, field: Any, expected: Type[Any]) -> Any:
        if isinstance(field, expected):
            return field
        if isinstance(field, type) and issubclass(field, expected):
            return field()
        if self._is_generic(field):
            return field()
        return field

    def _is_model(self, field: Any) -> bool:
        if isinstance(field, Model):
            return True
        if isinstance(field, type) and issubclass(field, Model):
            return True
        origin = get_origin(field)
        if origin:
            return self._is_model(origin)
        return False

    def _is_generic(self, field: Any) -> bool:
        return get_origin(field) is not None

    def _normalize_record_key(self, key: str) -> str:
        if key in {"number", "string", "symbol"}:
            return key
        if key == "boolean":
            return "string"
        return "string"


@dataclass
class TypeScriptProtoField:
    identifier: str
    json_name: str
    type: TypeScriptResolvedType
    optional: bool
    description: str | None = None


@dataclass(eq=False)
class TypeScriptProto:
    name: str
    model: Optional[AnyModel]
    kind: str
    module: str
    alias_type: Optional[TypeScriptResolvedType] = None
    enum_members: Optional[list[tuple[str, Any]]] = None
    fields: list[TypeScriptProtoField] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    routes: set[str] = field(default_factory=set)
    generic_params: "OrderedDict[Any, str]" = field(default_factory=OrderedDict)

    def add_tag(self, tag: str | None) -> None:
        if tag:
            self.tags.add(tag)

    def add_route(self, route: str | None) -> None:
        if route:
            self.routes.add(route)

    def type_reference(self, args: Optional[list[str]] = None, default_any: bool = True) -> str:
        if not self.generic_params:
            return self.name
        if args is None:
            args = ["any"] * len(self.generic_params) if default_any else []
        return f"{self.name}<{', '.join(args)}>"

    def dependencies(self) -> set["TypeScriptProto"]:
        deps: set[TypeScriptProto] = set()
        for field in self.fields:
            deps |= {dep for dep in field.type.deps if dep}
        if self.alias_type:
            deps |= {dep for dep in self.alias_type.deps if dep}
        deps.discard(self)
        return deps


class TypeScriptProtoRegistry:
    def __init__(self):
        self._resolver = TypeScriptTypeResolver(self)
        self._protos: dict[Any, TypeScriptProto] = {}
        self._aliases: dict[tuple[str, str], TypeScriptProto] = {}
        self._enums: dict[type[enum.Enum], TypeScriptProto] = {}

    def resolver(self) -> TypeScriptTypeResolver:
        return self._resolver

    def protos(self) -> Iterable[TypeScriptProto]:
        yield from self._protos.values()
        yield from self._aliases.values()
        yield from self._enums.values()

    def filter(self, *, tag: str | None = None, module: str | None = None) -> list[TypeScriptProto]:
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
        route: str | None = None,
        module: str | None = None,
    ) -> Optional[TypeScriptProto]:
        if model is None:
            return None

        if isinstance(model, FieldWrappedModel):
            ts_name = to_ts_name(name or getattr(model, "__name__", "AnonMap"))
            alias_module = module or "shared"
            proto = self._aliases.get((alias_module, ts_name))
            if proto:
                proto.add_tag(self._filter_tag(tag, model))
                proto.add_route(route)
                return proto
            alias_type = self._resolver.resolve(model.__field_type__)
            proto = TypeScriptProto(name=ts_name, model=None, kind="alias", alias_type=alias_type, module=alias_module)
            proto.add_tag(self._filter_tag(tag, model))
            proto.add_route(route)
            self._aliases[(alias_module, ts_name)] = proto
            return proto

        cls = unwrap_model_type(model)
        proto = self._protos.get(cls)
        if proto:
            proto.add_tag(self._filter_tag(tag, cls))
            proto.add_route(route)
            return proto

        ts_name = to_ts_name(name or getattr(cls, "__name__", "AnonModel"))
        target_module = module or "shared"
        proto = TypeScriptProto(name=ts_name, model=cls, kind="interface", module=target_module)
        proto.add_tag(self._filter_tag(tag, cls))
        proto.add_route(route)
        self._protos[cls] = proto
        self._build_proto(proto)
        return proto

    def register_alias(
        self,
        name: str,
        type_expr: TypeScriptResolvedType,
        *,
        tag: str | None = None,
        route: str | None = None,
        module: str | None = None,
    ) -> TypeScriptProto:
        alias_module = module or "shared"
        ts_name = to_ts_name(name)
        proto = self._aliases.get((alias_module, ts_name))
        if proto:
            proto.alias_type = type_expr
            proto.add_tag(tag)
            proto.add_route(route)
            return proto

        proto = TypeScriptProto(name=ts_name, model=None, kind="alias", alias_type=type_expr, module=alias_module)
        proto.add_tag(tag)
        proto.add_route(route)
        self._aliases[(alias_module, ts_name)] = proto
        return proto

    def ensure_enum(self, enum_cls: type[enum.Enum], *, module: str = "shared") -> TypeScriptProto:
        proto = self._enums.get(enum_cls)
        if proto:
            return proto
        members = [(member.name, member.value) for member in enum_cls]
        proto = TypeScriptProto(
            name=enum_cls.__name__,
            model=None,
            kind="enum",
            module=module,
            enum_members=members,
        )
        proto.add_tag("shared")
        self._enums[enum_cls] = proto
        return proto

    def _filter_tag(self, tag: str | None, model: Optional[Union[type[Model], Model]]) -> str | None:
        if tag != "shared" or model is None:
            return tag
        model_cls = unwrap_model_type(model)
        name = getattr(model_cls, "__name__", "") or ""
        if any(name.startswith(prefix) for prefix in ("REQ_", "RSP_", "CTX_")):
            return None
        return tag

    def _build_proto(self, proto: TypeScriptProto) -> None:
        if proto.model is None:
            return

        annotations = resolve_annotations(proto.model)
        proto.generic_params = self._collect_generic_params(proto.model, annotations)
        pyd_model = model_to_pydantic(proto.model)
        resolver = self._resolver

        for name, field in iter_model_vars(proto.model):
            if not isinstance(field, (Field, Model)):
                continue

            model_field = pyd_model.model_fields[name]
            field_value = field or Null()
            ts_type = self._resolve_field_type(name, field_value, annotations, proto.generic_params, resolver, proto.module)
            extra = getattr(field_value, "__extra__", {}) or {}
            alias = extra.get("alias") or name
            optional = (not model_field.is_required()) or extra.get("omitempty", False)
            proto.fields.append(
                TypeScriptProtoField(
                    identifier=to_ts_identifier(alias),
                    json_name=alias,
                    type=ts_type,
                    optional=optional,
                    description=model_field.description or "",
                )
            )

            if isinstance(field_value, Model) and field_value.__class__ is not proto.model:
                self.ensure(field_value.__class__, tag="shared")

    def _collect_generic_params(self, model: type[Model], annotations: dict[str, Any]) -> "OrderedDict[Any, str]":
        generics: "OrderedDict[Any, str]" = OrderedDict()
        generic_chars = "TUVWXYZABCDEFGHIJKLMNOPQRS"
        for name in annotations.keys():
            annotation = annotations.get(name)
            if isinstance(annotation, TypeVar) and annotation not in generics:
                generics[annotation] = inc_to_letters(len(generics), generic_chars)
        return generics

    def _resolve_field_type(
        self,
        name: str,
        field: Union[Field, Model],
        annotations: dict[str, Any],
        generic_params: "OrderedDict[Any, str]",
        resolver: TypeScriptTypeResolver,
        module: str,
    ) -> TypeScriptResolvedType:
        if type(field) is Field:
            annotation = annotations.get(name)
            if annotation in generic_params:
                return TypeScriptResolvedType(generic_params[annotation])
        if isinstance(field, Model):
            target_module = module if getattr(field.__class__, "__auto__", False) else "shared"
            proto = self.ensure(field.__class__, tag="shared" if target_module == "shared" else None, module=target_module)
            if proto is None:
                return TypeScriptResolvedType("any")
            return TypeScriptResolvedType(proto.name, {proto})
        return resolver.resolve(field)


def resolve_annotations(model: Any) -> dict[str, Any]:
    target = model if isinstance(model, type) else get_origin(model)
    if target is None:
        return getattr(model, "__annotations__", {})
    try:
        return get_type_hints(target)
    except TypeError:
        return getattr(target, "__annotations__", {})
