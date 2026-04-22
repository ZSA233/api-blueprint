from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Dict, Generator, Optional, Type, TypeVar, Union, get_origin, get_type_hints

from pydantic.fields import FieldInfo

from api_blueprint.engine.model import (
    BASIC_FIELD_TYPES,
    AnyModel,
    AnonKV,
    Field,
    FieldWrappedModel,
    Map,
    Model,
    Null,
    Proto,
    create_model,
    get_forward_ref_type,
    iter_enum_classes,
    iter_field_model_type,
    iter_model_vars,
    model_to_pydantic,
)
from api_blueprint.engine.utils import inc_to_letters, is_parametrized, join_path_imports, snake_to_pascal_case
from api_blueprint.engine.wrapper import ResponseWrapper

from .common import (
    PROTO_STRUCT_TYPE,
    GolangTagBuilder,
    GolangType,
    GolangTypeResolver,
    detect_go_base_type,
    go_literal,
)


@dataclass(frozen=True)
class GolangProtoField:
    name: str
    field: str
    type: GolangType
    tags: str

    def render(self, formatters: dict[str, str]) -> "GolangProtoFieldView":
        return GolangProtoFieldView(
            name=self.name,
            field=self.field,
            type=self.type.render(formatters),
            tags=self.tags,
        )

    def import_specs(self, formatters: dict[str, str]) -> list[str]:
        parents = getattr(self.type, "parents", [])
        imports = []
        for parent in parents:
            package = formatters.get(f"{parent}_package", "")
            spec = formatters.get(f"{parent}_imports", "")
            if package and spec:
                imports.append(f'{package} "{spec}"')
        return imports


@dataclass(frozen=True)
class GolangProtoFieldView:
    name: str
    field: str
    type: str
    tags: str


@dataclass(frozen=True)
class GolangEnumMember:
    name: str
    value: Any

    @property
    def go_value_literal(self) -> str:
        return go_literal(self.value)


@dataclass(frozen=True)
class GolangEnum:
    name: str
    base_type: str
    members: list[GolangEnumMember]

    @classmethod
    def from_enum(cls, enum_cls: Type[enum.Enum]) -> Optional["GolangEnum"]:
        members = [GolangEnumMember(name=member.name, value=member.value) for member in enum_cls]
        if not members:
            return None
        return cls(name=enum_cls.__name__, base_type=detect_go_base_type(type(members[0].value)), members=members)


@dataclass(frozen=True)
class GolangPackageLayout:
    module_import: str
    views_package: str
    provider_package: str
    errors_package: str

    @property
    def views_imports(self) -> str:
        return join_path_imports(self.module_import, self.views_package)

    @property
    def provider_imports(self) -> str:
        return join_path_imports(self.views_imports, self.provider_package)

    @property
    def errors_imports(self) -> str:
        return join_path_imports(self.module_import, self.errors_package)

    def formatters(self, update: Optional[dict[str, str]] = None) -> dict[str, str]:
        formatters = {
            "views_package": self.views_package,
            "views_imports": self.views_imports,
            "provider_package": self.provider_package,
            "provider_imports": self.provider_imports,
            "errors_package": self.errors_package,
            "errors_imports": self.errors_imports,
        }
        formatters.update({key + "$": value + "." for key, value in formatters.items() if key.endswith("_package")})
        if update:
            formatters.update(update)
        return formatters


@dataclass
class GolangProtoStruct:
    _resolver = GolangTypeResolver()

    @staticmethod
    def get_field_type(field: Union[Field, Model, Type[Any], Any], is_sub: bool = False) -> str:
        return GolangProtoStruct._resolver.resolve(field, pointer_allowed=not is_sub)

    @staticmethod
    def get_binding_tag(field: FieldInfo, omitempty: bool = False) -> str:
        return GolangTagBuilder.binding(field, omitempty)

    @staticmethod
    def get_field_tags(name: str, field: Union[Field, Model], field_info: FieldInfo) -> str:
        return GolangTagBuilder.build(name, field, field_info)


@dataclass
class GolangProtoGeneric:
    name: GolangType
    types: list[Union["GolangProto", GolangType]]

    def type_reference(self, formatters: dict[str, str]) -> str:
        return self.name.render(formatters)

    def import_specs(self, formatters: dict[str, str]) -> list[str]:
        parents = list(self.name.parents or [])
        for proto in self.types:
            if isinstance(proto, GolangProto):
                parents += proto.import_specs(formatters)
        imports = []
        for parent in parents:
            package = formatters.get(f"{parent}_package", "")
            spec = formatters.get(f"{parent}_imports", "")
            if package and spec:
                imports.append(f'{package} "{spec}"')
        return imports


@dataclass
class GolangProtoAlias:
    name: GolangType
    proto: Optional["GolangProto"] = None
    new_type: bool = False

    def type_reference(self, formatters: dict[str, str]) -> str:
        return self.name.render(formatters)

    def import_specs(self, formatters: dict[str, str]) -> list[str]:
        parents = list(self.name.parents or [])
        if self.proto is not None:
            parents += self.proto.import_specs(formatters)
        imports = []
        for parent in parents:
            package = formatters.get(f"{parent}_package", "")
            spec = formatters.get(f"{parent}_imports", "")
            if package and spec:
                imports.append(f'{package} "{spec}"')
        return imports


class GolangFieldWrappedModel(FieldWrappedModel):
    @property
    def __name__(self) -> str:
        return GolangProtoStruct.get_field_type(self.__field_type__)

    @__name__.setter
    def __name__(self, *args) -> None:
        return None


class GolangResponseWrapper:
    prefix: str
    response_wrapper: type[ResponseWrapper]
    _proto: Optional["GolangProto"] = None

    def __init__(self, prefix: str, response_wrapper: type[ResponseWrapper]):
        self.prefix = prefix
        self.response_wrapper = response_wrapper

    @property
    def proto_def_name(self) -> str:
        name = self.proto_name
        name += self.generic_types(True)
        return name

    @property
    def proto(self) -> "GolangProto":
        if self._proto is not None:
            return self._proto

        fields = [value for _key, value in iter_model_vars(self.response_wrapper) if isinstance(value, (Model, Field))]
        alias: Optional[GolangProtoAlias] = None
        struct: Optional[GolangProtoStruct] = None
        if fields:
            struct_type = "struct"
            struct = GolangProtoStruct()
        else:
            struct_type = "alias"
            alias = GolangProtoAlias(name=GolangType("any"))

        self._proto = GolangProto(
            name=self.prefix,
            model=self.response_wrapper,
            struct_type=struct_type,
            struct=struct,
            alias=alias,
        )
        return self._proto

    @property
    def proto_name(self) -> str:
        return f"{self.prefix}_{self.response_wrapper.__name__}"

    @property
    def proto_type(self) -> PROTO_STRUCT_TYPE:
        return self.proto.struct_type

    def proto_fields(self) -> list[GolangProtoField]:
        return self.proto.fields()

    def proto_fields_for(self, formatters: dict[str, str]) -> list[GolangProtoFieldView]:
        return self.proto.fields_for(formatters)

    @property
    def class_name(self) -> str:
        return self.response_wrapper.__name__

    def generic_types(self, with_any: bool = False) -> str:
        generic_types = self.proto.generic_types()
        if generic_types:
            suffix = " any" if with_any else ""
            return f'[{", ".join(generic_types.values())}{suffix}]'
        return ""

    def json_factory(self, **kwargs: Any) -> str:
        return self.response_factory("json", **kwargs)

    def xml_factory(self, **kwargs: Any) -> str:
        return self.response_factory("xml", **kwargs)

    def response_factory(self, typ: str, **kwargs: Any) -> str:
        return self.response_wrapper.golang_factory(typ).format(**kwargs)


class GolangProto(Proto):
    struct_type: PROTO_STRUCT_TYPE
    struct: Optional[GolangProtoStruct]
    generic: Optional[GolangProtoGeneric]
    alias: Optional[GolangProtoAlias]

    def __init__(
        self,
        name: str,
        model: AnyModel,
        struct_type: PROTO_STRUCT_TYPE = "struct",
        *,
        struct: Optional[GolangProtoStruct] = None,
        generic: Optional[GolangProtoGeneric] = None,
        alias: Optional[GolangProtoAlias] = None,
    ):
        super().__init__(name, model)
        self.struct_type = struct_type
        self.struct = struct
        self.generic = generic
        self.alias = alias

    @property
    def def_name(self) -> str:
        generic_types = self.generic_types()
        if generic_types:
            return f'{self.name}[{", ".join(generic_types.values())} any]'
        return self._name

    @classmethod
    def from_model(cls, model: AnyModel, **kwargs: Any) -> "GolangProto":
        return cls(model.__name__, model, **kwargs)

    @classmethod
    def from_model_ref(cls, ref_model: AnyModel, name: str, **kwargs: Any) -> "GolangProto":
        is_autocreate = ref_model.__auto__
        is_field_ref = isinstance(ref_model, GolangFieldWrappedModel)
        if is_autocreate and not is_field_ref:
            return GolangProto(name, ref_model, "struct", struct=GolangProtoStruct(), **kwargs)

        alias_is_com = not is_field_ref
        alias_proto = GolangProto.from_model(ref_model, **kwargs)
        alias_name = alias_proto.name
        if alias_is_com:
            alias_name = f"{{protos_package}}.{alias_proto.name}"
        return GolangProto(
            name,
            ref_model,
            "alias",
            alias=GolangProtoAlias(name=GolangType(alias_name), proto=alias_proto),
            **kwargs,
        )

    def generic_types(self) -> dict[TypeVar, str]:
        if self.model_type is None:
            return {}
        generic_types: dict[TypeVar, str] = {}
        annotations = resolve_annotations(self.model_type)
        for name, field in iter_model_vars(self.model_type):
            if not isinstance(field, (Field, Model)):
                continue
            if field is None:
                field = Null()
            if type(field) is Field:
                annotation = annotations.get(name)
                if isinstance(annotation, TypeVar):
                    generic_types[annotation] = inc_to_letters(len(generic_types), "TUVWXYZABCDEFGHIJKLMNOPQRS")
        return generic_types

    def fields(self) -> list[GolangProtoField]:
        proto_fields: list[GolangProtoField] = []
        pydmodel = model_to_pydantic(self.model_type)
        generic_types = self.generic_types()
        annotations = resolve_annotations(self.model_type)

        for name, field in iter_model_vars(self.model_type):
            if not isinstance(field, (Field, Model)):
                continue

            model_field = pydmodel.model_fields[name]
            field_value = field or Null()
            go_type = self._resolve_field_type(name, field_value, generic_types, annotations)
            extra = getattr(field_value, "__extra__", {}) or {}
            field_name = extra.get("alias") or name

            proto_fields.append(
                GolangProtoField(
                    name=snake_to_pascal_case(name),
                    field=field_name,
                    type=GolangType(go_type),
                    tags=GolangProtoStruct.get_field_tags(name, field_value, model_field),
                )
            )
        return proto_fields

    def fields_for(self, formatters: dict[str, str]) -> list[GolangProtoFieldView]:
        return [field.render(formatters) for field in self.fields()]

    def _resolve_field_type(
        self,
        name: str,
        field: Union[Field, Model],
        generic_types: dict[TypeVar, str],
        annotations: dict[str, Any],
    ) -> str:
        if type(field) is Field:
            annotation = annotations.get(name)
            if isinstance(annotation, TypeVar):
                generic_name = generic_types.get(annotation)
                if generic_name:
                    return f"*{generic_name}"
        return GolangProtoStruct.get_field_type(field)

    def generics(self, formatters: dict[str, str]) -> Generator[str, None, None]:
        for proto in self.generic.types:
            if isinstance(proto, GolangType):
                yield proto.render(formatters)
            else:
                yield GolangType(proto.name).render(formatters)

    def com_protos(self) -> Generator["GolangProto", None, None]:
        for model_type in iter_field_model_type(self.model_type):
            if model_type is self.model_type:
                continue
            yield GolangProto.from_model(model_type)

        if (
            getattr(self.model_type, "__auto__", None) is False
            and not is_parametrized(self.model_type)
            and self.model_type not in BASIC_FIELD_TYPES
        ):
            yield GolangProto.from_model(self.model_type)

    def import_specs(self, formatters: dict[str, str]) -> list[str]:
        specs: list[str] = []
        if self.generic:
            specs += self.generic.import_specs(formatters)
        if self.alias:
            specs += self.alias.import_specs(formatters)
        return list(set(specs))

    def __iter__(self) -> Generator["GolangProto", None, None]:
        for model_type in iter_field_model_type(self.model_type):
            yield GolangProto.from_model(model_type)


def ensure_model(model_or_map: Union[AnyModel, FieldWrappedModel]) -> Union[GolangFieldWrappedModel, AnyModel]:
    if isinstance(model_or_map, FieldWrappedModel) or (
        isinstance(model_or_map, type) and FieldWrappedModel is model_or_map
    ):
        return GolangFieldWrappedModel(model_or_map.__field_type__)
    return model_or_map


def resolve_annotations(model: Any) -> dict[str, Any]:
    target = model if isinstance(model, type) else get_origin(model)
    if target is None:
        return getattr(model, "__annotations__", {})
    try:
        return get_type_hints(target)
    except TypeError:
        return getattr(target, "__annotations__", {})
