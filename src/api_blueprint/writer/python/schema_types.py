from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Mapping

from .naming import to_py_class_name, to_py_identifier


@dataclass(frozen=True)
class PythonResolvedType:
    annotation: str
    decoder: str = "_decode_any"

    def decode_expr(self, value_expr: str, path_expr: str) -> str:
        decoder = f"({self.decoder})" if self.decoder.strip().startswith("lambda ") else self.decoder
        return f"{decoder}({value_expr}, {path_expr})"


@dataclass(frozen=True)
class PythonDtoField:
    name: str
    wire_name: str
    type: PythonResolvedType
    optional: bool

    @property
    def wire_literal(self) -> str:
        return json.dumps(self.wire_name, ensure_ascii=False)

    @property
    def path_expr(self) -> str:
        return f"_field_path(path, {self.wire_literal})"

    @property
    def decode_expr(self) -> str:
        raw_expr = f"value.get({self.wire_literal}, _MISSING)"
        helper = "_decode_optional" if self.optional else "_decode_required"
        return f"{helper}({self.type.decoder}, {raw_expr}, {self.path_expr})"


@dataclass(frozen=True)
class PythonDtoModel:
    class_name: str
    schema_name: str
    fields: tuple[PythonDtoField, ...]


@dataclass(frozen=True)
class PythonEnumMember:
    name: str
    value: Any

    @property
    def value_literal(self) -> str:
        return json.dumps(self.value, ensure_ascii=False)


@dataclass(frozen=True)
class PythonEnumModel:
    class_name: str
    base_class: str
    members: tuple[PythonEnumMember, ...]


class PythonSchemaRegistry:
    def __init__(self, schemas: Mapping[str, Any]):
        self.schemas = schemas
        self._models: "OrderedDict[tuple[str, str], PythonDtoModel]" = OrderedDict()
        self._enums: "OrderedDict[str, PythonEnumModel]" = OrderedDict()
        self._used_names: dict[str, int] = {}

    def models(self) -> tuple[PythonDtoModel, ...]:
        return tuple(self._models.values())

    def enums(self) -> tuple[PythonEnumModel, ...]:
        return tuple(self._enums.values())

    def resolve_schema(self, schema_name: str | None, *, class_name: str | None = None) -> PythonResolvedType | None:
        if not schema_name:
            return None
        schema = self.schemas.get(schema_name)
        if not isinstance(schema, Mapping):
            return None
        if schema.get("kind") == "alias" or schema.get("type") == "alias":
            target = schema.get("target")
            return self.resolve_value(target) if isinstance(target, Mapping) else PythonResolvedType("Any")
        if schema.get("type") == "object":
            model = self.ensure_model(schema_name, class_name=class_name)
            return PythonResolvedType(model.class_name, f"{model.class_name}.from_value")
        return self.resolve_value(schema)

    def ensure_model(self, schema_name: str, *, class_name: str | None = None) -> PythonDtoModel:
        preferred_name = class_name or _schema_class_name(schema_name, self.schemas.get(schema_name))
        key = (schema_name, preferred_name)
        existing = self._models.get(key)
        if existing is not None:
            return existing

        schema = self.schemas.get(schema_name)
        if not isinstance(schema, Mapping):
            class_text = self._unique_name(preferred_name)
            model = PythonDtoModel(class_name=class_text, schema_name=schema_name, fields=())
            self._models[key] = model
            return model

        class_text = self._unique_name(preferred_name)
        placeholder = PythonDtoModel(class_name=class_text, schema_name=schema_name, fields=())
        self._models[key] = placeholder

        fields: list[PythonDtoField] = []
        raw_fields = schema.get("fields")
        if isinstance(raw_fields, Mapping):
            for raw_name, raw_field in raw_fields.items():
                if not isinstance(raw_field, Mapping):
                    continue
                wire_name = str(raw_field.get("wire_name") or raw_field.get("name") or raw_name)
                field_name = to_py_identifier(str(raw_field.get("name") or raw_name), default="value")
                fields.append(
                    PythonDtoField(
                        name=field_name,
                        wire_name=wire_name,
                        type=self.resolve_value(raw_field),
                        optional=bool(raw_field.get("optional")),
                    )
                )
        model = PythonDtoModel(class_name=class_text, schema_name=schema_name, fields=tuple(fields))
        self._models[key] = model
        return model

    def resolve_value(self, value: Mapping[str, Any] | None) -> PythonResolvedType:
        if not isinstance(value, Mapping):
            return PythonResolvedType("Any")
        if value.get("ref"):
            ref = str(value["ref"])
            model = self.ensure_model(ref)
            return PythonResolvedType(model.class_name, f"{model.class_name}.from_value")
        value_type = str(value.get("type") or "any")
        if value_type == "array":
            item_type = self.resolve_value(_mapping(value.get("items")))
            return PythonResolvedType(
                f"list[{item_type.annotation}]",
                f"lambda item, path: _decode_list(item, path, {item_type.decoder})",
            )
        if value_type == "map":
            key_type = self.resolve_value(_mapping(value.get("keys")) or {"type": "string"})
            item_type = self.resolve_value(_mapping(value.get("values")))
            return PythonResolvedType(
                f"dict[{key_type.annotation}, {item_type.annotation}]",
                f"lambda item, path: _decode_map(item, path, {key_type.decoder}, {item_type.decoder})",
            )
        if value_type == "enum" or value.get("enum_values") or value.get("enum"):
            enum_model = self.ensure_enum(value)
            return PythonResolvedType(enum_model.class_name, f"{enum_model.class_name}.from_value")
        return _PRIMITIVE_TYPES.get(value_type, PythonResolvedType("Any"))

    def ensure_enum(self, value: Mapping[str, Any]) -> PythonEnumModel:
        identity = str(value.get("enum_identity") or value.get("enum") or "Enum")
        existing = self._enums.get(identity)
        if existing is not None:
            return existing

        enum_name = self._unique_name(to_py_class_name(str(value.get("enum") or "Enum"), default="Enum"))
        raw_values = value.get("enum_values")
        members: list[PythonEnumMember] = []
        if isinstance(raw_values, list) and raw_values:
            for index, item in enumerate(raw_values):
                if isinstance(item, Mapping):
                    member_name = _enum_member_name(str(item.get("name") or f"VALUE_{index + 1}"))
                    members.append(PythonEnumMember(member_name, item.get("value")))
        else:
            values = value.get("values")
            if isinstance(values, list):
                for index, item in enumerate(values):
                    members.append(PythonEnumMember(_enum_member_name(str(item or f"VALUE_{index + 1}")), item))
        members = _dedupe_enum_members(members)
        if all(isinstance(member.value, str) for member in members):
            base_class = "StrEnum"
        elif all(isinstance(member.value, int) and not isinstance(member.value, bool) for member in members):
            base_class = "IntEnum"
        else:
            base_class = "Enum"
        enum_model = PythonEnumModel(enum_name, base_class, tuple(members))
        self._enums[identity] = enum_model
        return enum_model

    def _unique_name(self, preferred: str) -> str:
        base = preferred or "Model"
        count = self._used_names.get(base, 0) + 1
        self._used_names[base] = count
        if count == 1:
            return base
        return f"{base}{count}"


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _schema_class_name(schema_name: str, schema: object) -> str:
    if isinstance(schema, Mapping):
        raw_name = str(schema.get("name") or schema_name)
    else:
        raw_name = schema_name
    return to_py_class_name(raw_name.rsplit(".", 1)[-1], default="Model")


def _enum_member_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_").upper()
    if not normalized:
        normalized = "VALUE"
    if normalized[0].isdigit():
        normalized = f"VALUE_{normalized}"
    return normalized


def _dedupe_enum_members(members: list[PythonEnumMember]) -> tuple[PythonEnumMember, ...]:
    counts: dict[str, int] = {}
    result: list[PythonEnumMember] = []
    for member in members:
        count = counts.get(member.name, 0) + 1
        counts[member.name] = count
        name = member.name if count == 1 else f"{member.name}_{count}"
        result.append(PythonEnumMember(name, member.value))
    return tuple(result)


_PRIMITIVE_TYPES: dict[str, PythonResolvedType] = {
    "any": PythonResolvedType("Any"),
    "object": PythonResolvedType("dict[str, Any]", "_decode_object"),
    "string": PythonResolvedType("str", "_decode_str"),
    "str": PythonResolvedType("str", "_decode_str"),
    "int": PythonResolvedType("int", "_decode_int"),
    "integer": PythonResolvedType("int", "_decode_int"),
    "int8": PythonResolvedType("int", "_decode_int"),
    "int16": PythonResolvedType("int", "_decode_int"),
    "int32": PythonResolvedType("int", "_decode_int"),
    "int64": PythonResolvedType("int", "_decode_int"),
    "uint": PythonResolvedType("int", "_decode_int"),
    "uint8": PythonResolvedType("int", "_decode_int"),
    "uint16": PythonResolvedType("int", "_decode_int"),
    "uint32": PythonResolvedType("int", "_decode_int"),
    "uint64": PythonResolvedType("int", "_decode_int"),
    "float": PythonResolvedType("float", "_decode_float"),
    "float32": PythonResolvedType("float", "_decode_float"),
    "float64": PythonResolvedType("float", "_decode_float"),
    "number": PythonResolvedType("float", "_decode_float"),
    "boolean": PythonResolvedType("bool", "_decode_bool"),
    "bool": PythonResolvedType("bool", "_decode_bool"),
    "binary": PythonResolvedType("bytes", "_decode_bytes"),
    "file": PythonResolvedType("ApiUploadFile", "_decode_file"),
}
