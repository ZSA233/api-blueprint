from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .naming import to_java_constant_name, to_java_member_name, to_java_type_name


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class JavaEnumMember:
    name: str
    value: Any

    @property
    def java_name(self) -> str:
        return to_java_constant_name(self.name or str(self.value))

    @property
    def literal(self) -> str:
        if isinstance(self.value, str):
            return json.dumps(self.value, ensure_ascii=False)
        if isinstance(self.value, bool):
            return "true" if self.value else "false"
        return str(self.value)


@dataclass(frozen=True)
class JavaEnum:
    name: str
    values: tuple[JavaEnumMember, ...]
    wire_type: str

    @property
    def java_type(self) -> str:
        if self.wire_type == "int":
            return "Integer"
        if self.wire_type == "long":
            return "Long"
        if self.wire_type == "double":
            return "Double"
        if self.wire_type == "boolean":
            return "Boolean"
        return "String"


@dataclass(frozen=True)
class JavaSchemaField:
    name: str
    wire_name: str
    java_name: str
    java_type: str
    optional: bool


@dataclass(frozen=True)
class JavaSchema:
    name: str
    raw_name: str
    fields: tuple[JavaSchemaField, ...]


class JavaModelCatalog:
    def __init__(self, schemas: Mapping[str, JsonObject]) -> None:
        self.schemas = dict(schemas)
        self._type_names = self._build_type_names(self.schemas)
        self._enum_names = self._build_enum_names(self.schemas)

    def schema_class_name(self, schema_name: str) -> str:
        return self._type_names.get(schema_name, to_java_type_name(schema_name.rsplit(".", 1)[-1], fallback="Model"))

    def enum_class_name(self, enum_name: str) -> str:
        return self._enum_names.get(enum_name, to_java_type_name(enum_name, fallback="EnumValue"))

    def is_auto_schema(self, schema_name: str) -> bool:
        schema = self.schemas.get(schema_name)
        return bool(schema and schema.get("auto") is True)

    def shared_schemas(self) -> tuple[JavaSchema, ...]:
        return tuple(
            self.schema(schema_name, owner_group=None)
            for schema_name, schema in self.schemas.items()
            if isinstance(schema, Mapping) and not schema.get("auto")
        )

    def route_schemas(self, schema_names: set[str], *, owner_group: object | None = None) -> tuple[JavaSchema, ...]:
        schema_names = self._expand_auto_schema_names(schema_names)
        return tuple(
            self.schema(schema_name, owner_group=owner_group)
            for schema_name in self.schemas
            if schema_name in schema_names and self.is_auto_schema(schema_name)
        )

    def enums(self) -> tuple[JavaEnum, ...]:
        enums: dict[str, JavaEnum] = {}
        for schema in self.schemas.values():
            self._collect_enums(schema, enums)
        return tuple(enums[name] for name in sorted(enums))

    def schema(self, schema_name: str, *, owner_group: object | None) -> JavaSchema:
        schema = self.schemas.get(schema_name, {"name": schema_name, "fields": {}})
        fields = schema.get("fields")
        rendered_fields: list[JavaSchemaField] = []
        if isinstance(fields, Mapping):
            for field_name, field_schema in fields.items():
                if not isinstance(field_schema, Mapping):
                    continue
                wire_name = str(field_schema.get("wire_name") or field_schema.get("name") or field_name)
                java_name = to_java_member_name(str(field_schema.get("name") or field_name))
                rendered_fields.append(
                    JavaSchemaField(
                        name=str(field_name),
                        wire_name=wire_name,
                        java_name=java_name,
                        java_type=self.type_for_value(field_schema, owner_group=owner_group),
                        optional=bool(field_schema.get("optional")),
                    )
                )
        return JavaSchema(
            name=self._schema_class_name_for_owner(schema_name, owner_group=owner_group),
            raw_name=schema_name,
            fields=tuple(rendered_fields),
        )

    def type_for_schema_name(self, schema_name: str, *, owner_group: object | None = None) -> str:
        if self.is_auto_schema(schema_name) and owner_group is not None:
            types_class = str(getattr(owner_group, "types_class", "RouteTypes"))
            return f"{types_class}.{self._schema_class_name_for_owner(schema_name, owner_group=owner_group)}"
        runtime_types_ref = str(getattr(owner_group, "runtime_types_ref", "GenApiTypes"))
        return f"{runtime_types_ref}.{self.schema_class_name(schema_name)}"

    def class_literal_for_schema_name(self, schema_name: str, *, owner_group: object | None = None) -> str:
        return f"{self.type_for_schema_name(schema_name, owner_group=owner_group)}.class"

    def type_for_value(self, value: Mapping[str, Any], *, owner_group: object | None = None) -> str:
        value_type = str(value.get("type") or "any")
        ref = value.get("ref")
        if isinstance(ref, str) and ref:
            return self.type_for_schema_name(ref, owner_group=owner_group)
        if value_type == "enum":
            runtime_types_ref = str(getattr(owner_group, "runtime_types_ref", "GenApiTypes"))
            return f"{runtime_types_ref}.{self.enum_class_name(str(value.get('enum') or 'EnumValue'))}"
        if value_type == "array":
            items = value.get("items")
            if isinstance(items, Mapping):
                return f"List<{self.type_for_value(items, owner_group=owner_group)}>"
            return "List<Object>"
        if value_type == "map":
            keys = value.get("keys")
            values = value.get("values")
            key_type = self.type_for_value(keys if isinstance(keys, Mapping) else {"type": "string"}, owner_group=owner_group)
            value_java_type = self.type_for_value(
                values if isinstance(values, Mapping) else {"type": "any"},
                owner_group=owner_group,
            )
            if key_type not in {"String", "Integer", "Long"}:
                key_type = "String"
            return f"Map<{key_type}, {value_java_type}>"
        if value_type == "one_of":
            return "JsonNode"
        if value_type == "coerce_string":
            return "String"
        return {
            "string": "String",
            "str": "String",
            "int": "Integer",
            "integer": "Integer",
            "int8": "Integer",
            "int16": "Integer",
            "int32": "Integer",
            "uint": "Long",
            "uint8": "Integer",
            "uint16": "Integer",
            "uint32": "Long",
            "int64": "Long",
            "uint64": "Long",
            "float": "Float",
            "float32": "Float",
            "float64": "Double",
            "number": "Double",
            "boolean": "Boolean",
            "bool": "Boolean",
            "binary": "byte[]",
            "file": "GenApiFilePart",
            "object": "Object",
            "any": "Object",
            "null": "Object",
        }.get(value_type, "Object")

    def _schema_class_name_for_owner(self, schema_name: str, *, owner_group: object | None) -> str:
        if self.is_auto_schema(schema_name) and owner_group is not None and hasattr(owner_group, "schema_type_name"):
            return str(owner_group.schema_type_name(schema_name))
        return self.schema_class_name(schema_name)

    @staticmethod
    def _build_type_names(schemas: Mapping[str, JsonObject]) -> dict[str, str]:
        base_names: dict[str, list[str]] = {}
        for name in schemas:
            base = to_java_type_name(name.rsplit(".", 1)[-1], fallback="Model")
            base_names.setdefault(base, []).append(name)
        result: dict[str, str] = {}
        for name in schemas:
            base = to_java_type_name(name.rsplit(".", 1)[-1], fallback="Model")
            result[name] = base if len(base_names[base]) == 1 else to_java_type_name(name.replace(".", "_"), fallback="Model")
        return result

    @staticmethod
    def _build_enum_names(schemas: Mapping[str, JsonObject]) -> dict[str, str]:
        enum_keys: set[str] = set()

        def visit(value: object) -> None:
            if isinstance(value, Mapping):
                if value.get("type") == "enum" and isinstance(value.get("enum"), str):
                    enum_keys.add(str(value["enum"]))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(schemas)
        base_names: dict[str, list[str]] = {}
        for name in enum_keys:
            base_names.setdefault(to_java_type_name(name, fallback="EnumValue"), []).append(name)
        return {
            name: (
                to_java_type_name(name, fallback="EnumValue")
                if len(base_names[to_java_type_name(name, fallback="EnumValue")]) == 1
                else to_java_type_name(name.replace(".", "_"), fallback="EnumValue")
            )
            for name in enum_keys
        }

    def _collect_enums(self, value: object, enums: dict[str, JavaEnum]) -> None:
        if isinstance(value, Mapping):
            if value.get("type") == "enum" and isinstance(value.get("enum"), str):
                enum_name = str(value["enum"])
                if enum_name not in enums:
                    raw_members = value.get("enum_values")
                    members = [
                        JavaEnumMember(str(member.get("name") or member.get("value") or "VALUE"), member.get("value"))
                        for member in raw_members
                        if isinstance(member, Mapping)
                    ] if isinstance(raw_members, list) else []
                    enums[enum_name] = JavaEnum(
                        name=self.enum_class_name(enum_name),
                        values=tuple(members),
                        wire_type=_enum_wire_type(value.get("values")),
                    )
            for child in value.values():
                self._collect_enums(child, enums)
        elif isinstance(value, list):
            for child in value:
                self._collect_enums(child, enums)

    def _expand_auto_schema_names(self, schema_names: set[str]) -> set[str]:
        expanded = set(schema_names)
        changed = True
        while changed:
            changed = False
            for schema_name in tuple(expanded):
                schema = self.schemas.get(schema_name)
                if not isinstance(schema, Mapping):
                    continue
                for ref in self._iter_refs(schema):
                    if ref in expanded or not self.is_auto_schema(ref):
                        continue
                    expanded.add(ref)
                    changed = True
        return expanded

    def _iter_refs(self, value: object) -> list[str]:
        refs: list[str] = []
        if isinstance(value, Mapping):
            ref = value.get("ref")
            if isinstance(ref, str) and ref:
                refs.append(ref)
            for child in value.values():
                refs.extend(self._iter_refs(child))
        elif isinstance(value, list):
            for child in value:
                refs.extend(self._iter_refs(child))
        return refs


def _enum_wire_type(values: object) -> str:
    first = values[0] if isinstance(values, list) and values else None
    if isinstance(first, bool):
        return "boolean"
    if isinstance(first, int):
        return "int"
    if isinstance(first, float):
        return "double"
    return "string"
