from __future__ import annotations

import enum
import json
import re
from typing import Any, Dict, Literal, Optional, Type, Union, get_origin

from pydantic.fields import FieldInfo

from api_blueprint.engine.model import AnonKV, Array, Enum, Field, Map, Model
from api_blueprint.engine.utils import is_parametrized
from api_blueprint.writer.core.files import SafeFmtter


LANG = "golang"
PROTO_STRUCT_TYPE = Literal["struct", "generic", "alias"]


class PackageName(str, enum.Enum):
    COM_PROTOS = "protos"
    COM_ENUMS = "enums"
    PROVIDER = "provider"
    ERROR = "errors"
    VIEWS = "views"


type_reg = re.compile(r"\{(\w+)_((imports|package)\$?)\}")


class GolangType(SafeFmtter):
    parents: Optional[list[str]] = None

    def __init__(self, value: str):
        super().__init__()
        parents = set()
        for result in type_reg.findall(str(value)):
            parents.add(result[0])
        self.parents = list(parents)

    def render(self, formatters: Optional[Dict[str, str]] = None) -> str:
        formatters = formatters or {}

        def repl(match: re.Match) -> str:
            key = f"{match.group(1)}_{match.group(2)}"
            return formatters.get(key, "")

        return type_reg.sub(repl, str(self))


class GolangTypeResolver:
    SIMPLE_TYPE_MAPPING = {
        "string": "string",
        "str": "string",
        "int": "int",
        "int64": "int64",
        "int32": "int32",
        "int16": "int16",
        "int8": "int8",
        "uint": "uint",
        "uint64": "uint64",
        "uint32": "uint32",
        "uint16": "uint16",
        "uint8": "uint8",
        "float": "float64",
        "float64": "float64",
        "float32": "float32",
        "boolean": "bool",
        "bool": "bool",
        "byte": "byte",
        "error": "error",
        "null": "nil",
    }

    def resolve(self, field: Union[Field, Model, Type[Any], Any], *, pointer_allowed: bool = True) -> str:
        kind = self._infer_kind(field)
        if kind in self.SIMPLE_TYPE_MAPPING:
            return self.SIMPLE_TYPE_MAPPING[kind]

        resolver = {
            "array": self._resolve_array,
            "enum": self._resolve_enum,
            "map": self._resolve_map,
            "anonkv": self._resolve_anon_kv,
            "object": self._resolve_object,
        }.get(kind)
        if resolver is not None:
            return resolver(field, pointer_allowed=pointer_allowed)

        if self._is_model(field):
            return self._resolve_object(field, pointer_allowed=pointer_allowed)
        return "any"

    def _infer_kind(self, field: Union[Field, Model, Type[Any], Any]) -> str:
        if isinstance(field, AnonKV):
            return "anonkv"

        candidate = field if isinstance(field, (Field, Model, type)) else field
        type_name = getattr(candidate, "__type__", None)
        if type_name:
            return type_name.lower()

        if isinstance(candidate, type):
            if issubclass(candidate, enum.Enum):
                return "enum"
            return candidate.__name__.lower()

        origin = get_origin(candidate)
        if origin:
            return self._infer_kind(origin)
        return candidate.__class__.__name__.lower()

    def _resolve_array(self, field: Union[Field, Type[Field], Any], *, pointer_allowed: bool) -> str:
        array_field = self._ensure_instance(field, Array)
        if not isinstance(array_field, Array):
            return "[]any"
        elem = array_field.elem_type()
        if self._is_generic(elem):
            elem = elem()
        elem_type = self.resolve(elem, pointer_allowed=False)
        if self._is_model(elem):
            return f"[]*{elem_type}"
        return f"[]{elem_type}"

    def _resolve_enum(self, field: Enum | enum.Enum, *, pointer_allowed: bool) -> str:
        if is_parametrized(field):
            field = field()
        base_type_getter = getattr(field, "enum_base_type", None)
        if base_type_getter is None:
            base_type_getter = Enum[field]().enum_base_type
        return self.resolve(base_type_getter(), pointer_allowed=pointer_allowed)

    def _resolve_map(self, field: Union[Map, Type[Map]], *, pointer_allowed: bool) -> str:
        map_field = self._ensure_instance(field, Map)
        if not isinstance(map_field, Map):
            return "map[string]any"
        key_type = map_field.key_type()
        value_type = map_field.value_type()
        resolved_key = self.resolve(key_type, pointer_allowed=False)
        resolved_value = self.resolve(value_type, pointer_allowed=False)
        if self._is_model(value_type):
            resolved_value = f"*{resolved_value}"
        return f"map[{resolved_key}]{resolved_value}"

    def _resolve_anon_kv(self, field: AnonKV, *, pointer_allowed: bool) -> str:
        return self.resolve(field.get_obj(), pointer_allowed=pointer_allowed)

    def _resolve_object(self, field: Union[Model, Type[Model]], *, pointer_allowed: bool) -> str:
        model_cls = field if isinstance(field, type) else field.__class__
        pointer = "*" if pointer_allowed else ""
        return GolangType(f"{pointer}{{protos_package$}}{model_cls.__name__}")

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


class GolangTagBuilder:
    DEFAULT_TAG_FIELDS = ("json", "xml", "form")

    @staticmethod
    def binding(field_info: FieldInfo, omitempty: bool = False) -> str:
        parts: list[str] = []
        if omitempty:
            parts.append("omitempty")
        elif field_info.is_required():
            parts.append("required")

        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            enum_values = " ".join(str(member.value) for member in list(annotation))
            parts.append(f"oneof={enum_values}")

        for meta in field_info.metadata:
            if getattr(meta, "gt", None) is not None:
                parts.append(f"gt={meta.gt}")
            if getattr(meta, "ge", None) is not None:
                parts.append(f"gte={meta.ge}")
            if getattr(meta, "lt", None) is not None:
                parts.append(f"lt={meta.lt}")
            if getattr(meta, "le", None) is not None:
                parts.append(f"lte={meta.le}")
            if getattr(meta, "min_length", None) is not None:
                parts.append(f"min={meta.min_length}")
            if getattr(meta, "max_length", None) is not None:
                parts.append(f"max={meta.max_length}")
            if getattr(meta, "regex", None) is not None:
                parts.append(f"regexp={meta.regex.pattern}")

        return ",".join(filter(None, parts))

    @classmethod
    def build(cls, name: str, field: Union[Field, Model], field_info: FieldInfo) -> str:
        extra = getattr(field, "__extra__", {}) or {}
        alias = extra.get("alias")
        omitempty = extra.get("omitempty", False)
        field_name = alias or name
        normal_val = field_name if not omitempty else f"{name},omitempty"

        tags: list[tuple[str, str]] = [(tag, normal_val) for tag in cls.DEFAULT_TAG_FIELDS]
        binding = cls.binding(field_info, omitempty)
        if binding:
            tags.append(("binding", binding))
        return " ".join(f'{tag}:"{value}"' for tag, value in tags)


def detect_go_base_type(value_type: Type[Any]) -> str:
    candidates: tuple[tuple[Type[Any], str], ...] = (
        (bool, "bool"),
        (int, "int"),
        (float, "float64"),
        (str, "string"),
    )
    for py_type, go_type in candidates:
        try:
            if issubclass(value_type, py_type):
                return go_type
        except TypeError:
            continue
    return "string"


def go_literal(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, default=str)
