from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any, Literal, Mapping

from api_blueprint.writer.core.sdk_names import go_exported_field_name

from .planner import GoClientGroup, GoClientRoute


JsonObject = dict[str, Any]
GoClientTypeDeclKind = Literal["alias", "enum", "struct"]


@dataclass(frozen=True)
class GoClientFieldDecl:
    name: str
    type: str
    tags: str

    @property
    def uses_runtime_import(self) -> bool:
        return "runtime." in self.type


@dataclass(frozen=True)
class GoClientEnumMemberDecl:
    name: str
    value_literal: str


@dataclass(frozen=True)
class GoClientTypeDecl:
    kind: GoClientTypeDeclKind
    name: str
    target: str = ""
    base_type: str = ""
    fields: tuple[GoClientFieldDecl, ...] = ()
    members: tuple[GoClientEnumMemberDecl, ...] = ()
    blank_after: bool = True

    @property
    def uses_runtime_import(self) -> bool:
        if "runtime." in self.target or "runtime." in self.base_type:
            return True
        return any(field.uses_runtime_import for field in self.fields)


class GoClientTypeNames:
    def __init__(self, schemas: Mapping[str, JsonObject]) -> None:
        base_names: dict[str, list[str]] = {}
        for name in schemas:
            base_names.setdefault(go_type_name(name), []).append(name)
        self._names = {
            name: (
                go_type_name(name)
                if len(base_names[go_type_name(name)]) == 1
                else go_type_name(name.replace(".", "_"))
            )
            for name in schemas
        }

    def schema(self, name: object) -> str:
        key = str(name or "")
        return self._names.get(key, go_type_name(key))

    def ref(self, value: Mapping[str, Any], *, pointer: bool = False) -> str:
        ref = value.get("ref")
        if isinstance(ref, str) and ref:
            target = self.schema(ref)
            return f"*{target}" if pointer else target
        return "any"


def runtime_model_declarations(
    schemas: Mapping[str, JsonObject],
    type_names: GoClientTypeNames,
) -> tuple[GoClientTypeDecl, ...]:
    declarations: list[GoClientTypeDecl] = []
    declarations.extend(_enum_declaration(enum) for enum in _collect_enums(schemas).values())
    declarations.extend(_schema_declaration(schema_name, schema, type_names) for schema_name, schema in schemas.items())
    return tuple(declarations)


def group_model_declarations(
    group: GoClientGroup,
    schemas: Mapping[str, JsonObject],
    type_names: GoClientTypeNames,
) -> tuple[GoClientTypeDecl, ...]:
    declarations: list[GoClientTypeDecl] = []
    emitted_messages: set[str] = set()
    for route in group.routes:
        declarations.extend(_route_declarations(route, schemas, type_names, emitted_messages))
    return tuple(declarations)


def variant_alias_name(message_name: str, key: str) -> str:
    return f"{message_name}_{go_exported(key)}_DATA"


def go_type_name(value: str) -> str:
    if "." in value:
        value = value.rsplit(".", 1)[-1]
    return go_exported(value)


def go_exported(value: str) -> str:
    return go_exported_field_name(value, fallback="Value")


def go_code_literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _schema_declaration(
    schema_name: str,
    schema: Mapping[str, Any],
    type_names: GoClientTypeNames,
) -> GoClientTypeDecl:
    name = type_names.schema(schema_name)
    if schema.get("kind") == "alias" or schema.get("type") == "alias":
        target = schema.get("target")
        target_type = _go_type_for_schema_value(target if isinstance(target, Mapping) else {}, type_names)
        return GoClientTypeDecl(kind="alias", name=name, target=target_type)
    if schema.get("type") != "object":
        return GoClientTypeDecl(kind="alias", name=name, target=_go_type_for_schema_value(schema, type_names))
    return GoClientTypeDecl(kind="struct", name=name, fields=_schema_fields(schema, type_names, runtime=False))


def _enum_declaration(enum: Mapping[str, Any]) -> GoClientTypeDecl:
    name = go_type_name(str(enum.get("enum") or enum.get("name") or "EnumValue"))
    members = []
    for member in enum.get("enum_values", []):
        if not isinstance(member, Mapping):
            continue
        member_name = go_exported(str(member.get("name") or member.get("value") or "Value"))
        members.append(GoClientEnumMemberDecl(name=member_name, value_literal=go_code_literal(member.get("value"))))
    return GoClientTypeDecl(kind="enum", name=name, base_type=_enum_base_type(enum), members=tuple(members))


def _route_declarations(
    route: GoClientRoute,
    schemas: Mapping[str, JsonObject],
    type_names: GoClientTypeNames,
    emitted_messages: set[str],
) -> tuple[GoClientTypeDecl, ...]:
    declarations: list[GoClientTypeDecl] = []
    aliases = (
        (route.path_type, route.request.get("path_model")),
        (route.query_type, route.request.get("query_model")),
        (route.json_type, route.request.get("json_model")),
        (route.form_type, route.request.get("form_model")),
        (route.multipart_type, route.request.get("multipart_model")),
        (route.binary_type, None if route.has_binary_schema else route.request.get("binary_model")),
        (route.open_type, route.connection.get("open_model")),
        (route.close_type, route.connection.get("close_model")),
        (
            route.response_type,
            None if route.response_kind in {"bytes", "file", "byte_stream", "binary_schema"} else route.response.get("model"),
        ),
    )
    for alias, schema_name in aliases:
        if not isinstance(schema_name, str) or not schema_name:
            continue
        schema = schemas.get(schema_name)
        if isinstance(schema, Mapping) and schema.get("auto") is True and schema.get("type") == "object":
            declarations.append(
                GoClientTypeDecl(
                    kind="struct",
                    name=alias,
                    fields=_schema_fields(schema, type_names, runtime=True),
                    blank_after=False,
                )
            )
        else:
            declarations.append(
                GoClientTypeDecl(
                    kind="alias",
                    name=alias,
                    target=f"runtime.{type_names.schema(schema_name)}",
                    blank_after=False,
                )
            )
    declarations.extend(_message_variant_aliases(route, type_names, emitted_messages))
    if declarations:
        declarations[-1] = replace(declarations[-1], blank_after=True)
    return tuple(declarations)


def _message_variant_aliases(
    route: GoClientRoute,
    type_names: GoClientTypeNames,
    emitted_messages: set[str],
) -> tuple[GoClientTypeDecl, ...]:
    declarations: list[GoClientTypeDecl] = []
    for message_key in ("server_message", "client_message"):
        message = route.connection.get(message_key)
        if not isinstance(message, Mapping) or not isinstance(message.get("name"), str):
            continue
        message_name = str(message["name"])
        if message_name in emitted_messages:
            continue
        emitted_messages.add(message_name)
        variants = message.get("variants")
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if not isinstance(variant, Mapping):
                continue
            key = variant.get("key")
            model = variant.get("model")
            if isinstance(key, str) and key and isinstance(model, str) and model:
                declarations.append(
                    GoClientTypeDecl(
                        kind="alias",
                        name=variant_alias_name(message_name, key),
                        target=f"runtime.{type_names.schema(model)}",
                        blank_after=False,
                    )
                )
    return tuple(declarations)


def _schema_fields(
    schema: Mapping[str, Any],
    type_names: GoClientTypeNames,
    *,
    runtime: bool,
) -> tuple[GoClientFieldDecl, ...]:
    fields = schema.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return ()
    declarations: list[GoClientFieldDecl] = []
    for field_name, field_schema in fields.items():
        if not isinstance(field_schema, Mapping):
            continue
        go_field = go_exported(str(field_schema.get("name") or field_name))
        go_type = (
            _go_type_for_route_schema_value(field_schema, type_names)
            if runtime
            else _go_type_for_schema_value(field_schema, type_names)
        )
        wire_name = str(field_schema.get("wire_name") or field_schema.get("name") or field_name)
        omitempty = ",omitempty" if field_schema.get("optional") else ""
        declarations.append(
            GoClientFieldDecl(
                name=go_field,
                type=go_type,
                tags=f'`json:"{wire_name}{omitempty}" form:"{wire_name}{omitempty}" uri:"{wire_name}{omitempty}"`',
            )
        )
    return tuple(declarations)


def _go_type_for_schema_value(value: Mapping[str, Any], type_names: GoClientTypeNames) -> str:
    value_type = str(value.get("type") or "any")
    if value_type == "object" and value.get("ref"):
        return type_names.ref(value, pointer=True)
    if value_type == "array":
        items = value.get("items")
        if isinstance(items, Mapping):
            item_type = _go_type_for_schema_value(items, type_names)
            return f"[]{item_type}"
        return "[]any"
    if value_type == "map":
        keys = value.get("keys")
        values = value.get("values")
        key_type = _go_type_for_schema_value(keys if isinstance(keys, Mapping) else {"type": "string"}, type_names)
        value_go_type = _go_type_for_schema_value(values if isinstance(values, Mapping) else {"type": "any"}, type_names)
        return f"map[{key_type}]{value_go_type}"
    if value_type == "enum":
        return go_type_name(str(value.get("enum") or "EnumValue"))
    return {
        "string": "string",
        "str": "string",
        "int": "int",
        "integer": "int",
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
        "number": "float64",
        "boolean": "bool",
        "bool": "bool",
        "binary": "[]byte",
        "coerce_string": "string",
        "file": "MultipartFile",
        "any": "any",
        "null": "any",
        "one_of": "any",
    }.get(value_type, "any")


def _go_type_for_route_schema_value(value: Mapping[str, Any], type_names: GoClientTypeNames) -> str:
    value_type = str(value.get("type") or "any")
    if value_type == "object" and value.get("ref"):
        return f"*runtime.{type_names.ref(value, pointer=False)}"
    if value_type == "array":
        items = value.get("items")
        if isinstance(items, Mapping):
            return f"[]{_go_type_for_route_schema_value(items, type_names)}"
        return "[]any"
    if value_type == "map":
        keys = value.get("keys")
        values = value.get("values")
        key_type = _go_type_for_route_schema_value(keys if isinstance(keys, Mapping) else {"type": "string"}, type_names)
        value_go_type = _go_type_for_route_schema_value(values if isinstance(values, Mapping) else {"type": "any"}, type_names)
        return f"map[{key_type}]{value_go_type}"
    if value_type == "enum":
        return f"runtime.{go_type_name(str(value.get('enum') or 'EnumValue'))}"
    if value_type == "file":
        return "runtime.MultipartFile"
    return _go_type_for_schema_value(value, type_names)


def _collect_enums(schemas: Mapping[str, JsonObject]) -> dict[str, Mapping[str, Any]]:
    enums: dict[str, Mapping[str, Any]] = {}

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            if value.get("type") == "enum" and isinstance(value.get("enum"), str):
                enums[str(value["enum"])] = value
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schemas)
    return enums


def _enum_base_type(enum: Mapping[str, Any]) -> str:
    values = enum.get("values")
    first = values[0] if isinstance(values, list) and values else None
    if isinstance(first, bool):
        return "bool"
    if isinstance(first, int):
        return "int"
    if isinstance(first, float):
        return "float64"
    return "string"
