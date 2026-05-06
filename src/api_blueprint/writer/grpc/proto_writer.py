from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Mapping

from api_blueprint.contract import ContractGraph


@dataclass
class ProtoServiceFile:
    root: str
    group: str
    package: str
    go_package_prefix: str
    service_name: str
    rpcs: list[str] = field(default_factory=list)
    messages: "OrderedDict[str, Mapping[str, Any] | None]" = field(default_factory=OrderedDict)
    enums: "OrderedDict[str, list[object]]" = field(default_factory=OrderedDict)

    @property
    def path(self) -> str:
        return f"{self.root}/{self.group}.proto"

    @property
    def go_package(self) -> str:
        if not self.go_package_prefix:
            return self.root
        return f"{self.go_package_prefix.rstrip('/')}/{self.root};{self.root}"


def render_proto_files(
    graph: ContractGraph,
    *,
    package: str,
    go_package_prefix: str,
) -> dict[str, str]:
    manifest = graph.to_manifest()
    schemas = manifest["schemas"]
    files: "OrderedDict[str, ProtoServiceFile]" = OrderedDict()

    for route in manifest["routes"]:
        service_id = str(route["service_id"])
        root, group = _split_service_id(service_id)
        service_file = files.get(service_id)
        if service_file is None:
            service_file = ProtoServiceFile(
                root=root,
                group=group,
                package=_service_package(package, root, group),
                go_package_prefix=go_package_prefix,
                service_name=f"{_pascal(group)}Service",
            )
            files[service_id] = service_file

        rpc_name = _pascal(str(route["operation"]))
        if route["kind"] == "rpc":
            request_name = f"{rpc_name}Request"
            response_name = f"{rpc_name}Response"
            _register_message_schema(
                service_file,
                request_name,
                _schema_for_route_request(route, schemas),
                schemas,
            )
            _register_message_schema(
                service_file,
                response_name,
                _schema_for_route_response(route, schemas),
                schemas,
            )
            service_file.rpcs.append(f"  rpc {rpc_name} ({request_name}) returns ({response_name});")
            continue

        if route["kind"] == "stream":
            connection = route["connection"]
            request_name = f"{rpc_name}Request"
            response_name = _message_name(connection["server_message"])
            _register_message_schema(
                service_file,
                request_name,
                _schema_by_name(connection.get("open_model"), schemas),
                schemas,
            )
            _register_message_contract(service_file, connection["server_message"], schemas)
            service_file.rpcs.append(f"  rpc {rpc_name} ({request_name}) returns (stream {response_name});")
            continue

        if route["kind"] == "channel":
            connection = route["connection"]
            request_name = _message_name(connection["client_message"])
            response_name = _message_name(connection["server_message"])
            _register_message_contract(service_file, connection["client_message"], schemas)
            _register_message_contract(service_file, connection["server_message"], schemas)
            service_file.rpcs.append(
                f"  rpc {rpc_name} (stream {request_name}) returns (stream {response_name});"
            )

    return {service_file.path: _render_file(service_file) for service_file in files.values()}


def _render_file(service_file: ProtoServiceFile) -> str:
    lines = [
        'syntax = "proto3";',
        "",
        f"package {service_file.package};",
        "",
        f'option go_package = "{service_file.go_package}";',
        "",
        f"service {service_file.service_name} {{",
        *service_file.rpcs,
        "}",
        "",
    ]
    rendered_messages: set[str] = set()
    while len(rendered_messages) < len(service_file.messages):
        for name, schema in list(service_file.messages.items()):
            if name in rendered_messages:
                continue
            lines.extend(_render_message(service_file, name, schema))
            lines.append("")
            rendered_messages.add(name)
    for name, values in service_file.enums.items():
        lines.extend(_render_enum(name, values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_message(service_file: ProtoServiceFile, name: str, schema: Mapping[str, Any] | None) -> list[str]:
    lines = [f"message {_proto_type_name(name)} {{"]
    fields = _message_fields(schema)
    if isinstance(fields, Mapping):
        index = 1
        for field_name, field in fields.items():
            if not isinstance(field, Mapping):
                continue
            wire_name = field.get("wire_name") or field_name
            field_context = f"{_proto_type_name(name)}{_proto_type_name(str(wire_name))}"
            lines.append(
                f"  {_proto_type(field, service_file=service_file, context=field_context)} "
                f"{_proto_field_name(str(wire_name))} = {index};"
            )
            index += 1
    lines.append("}")
    return lines


def _render_enum(name: str, values: list[object]) -> list[str]:
    enum_name = _proto_type_name(name)
    prefix = _constant_name(enum_name)
    lines = [
        f"enum {enum_name} {{",
        f"  {prefix}_UNSPECIFIED = 0;",
    ]
    used = {f"{prefix}_UNSPECIFIED"}
    for index, value in enumerate(values, start=1):
        value_name = f"{prefix}_{_constant_name(str(value))}"
        if value_name in used:
            value_name = f"{value_name}_{index}"
        used.add(value_name)
        lines.append(f"  {value_name} = {index};")
    lines.append("}")
    return lines


def _message_fields(schema: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(schema, Mapping):
        return {}
    fields = schema.get("fields")
    if isinstance(fields, Mapping):
        return fields
    if schema.get("kind") == "alias" and isinstance(schema.get("target"), Mapping):
        return {
            "value": {
                **schema["target"],
                "wire_name": "value",
            }
        }
    return {}


def _proto_type(
    field: Mapping[str, Any],
    *,
    service_file: ProtoServiceFile | None = None,
    context: str = "Value",
) -> str:
    field_type = field.get("type")
    if field_type == "array":
        items = field.get("items", {})
        if isinstance(items, Mapping):
            return f"repeated {_proto_type(items, service_file=service_file, context=context + 'Item')}"
        return "repeated string"
    if field_type == "map":
        values = field.get("values", {})
        value_type = _proto_map_value_type(values, service_file=service_file, context=context)
        return f"map<string, {value_type}>"
    if field.get("ref"):
        return _proto_type_name(str(field["ref"]))
    if field_type == "enum":
        return _proto_type_name(str(field.get("enum") or "Enum"))
    return {
        "string": "string",
        "str": "string",
        "int": "int64",
        "int64": "int64",
        "int32": "int32",
        "int16": "int32",
        "int8": "int32",
        "uint": "uint64",
        "uint64": "uint64",
        "uint32": "uint32",
        "uint16": "uint32",
        "uint8": "uint32",
        "float": "float",
        "float32": "float",
        "float64": "double",
        "boolean": "bool",
        "bool": "bool",
        "byte": "bytes",
    }.get(str(field_type), "string")


def _proto_map_value_type(
    field: object,
    *,
    service_file: ProtoServiceFile | None,
    context: str,
) -> str:
    if not isinstance(field, Mapping):
        return "string"
    if field.get("type") not in {"array", "map"}:
        return _proto_type(field, service_file=service_file, context=context + "Value")
    if service_file is None:
        return "string"

    wrapper_name = _unique_message_name(service_file, f"{context}Value")
    if wrapper_name not in service_file.messages:
        service_file.messages[wrapper_name] = {
            "kind": "model",
            "type": "object",
            "fields": OrderedDict(
                [
                    (
                        "value",
                        {
                            **field,
                            "wire_name": "value",
                        },
                    )
                ]
            ),
            "auto": True,
        }
    return wrapper_name


def _unique_message_name(service_file: ProtoServiceFile, base_name: str) -> str:
    name = _proto_type_name(base_name)
    if name not in service_file.messages:
        return name

    index = 2
    while f"{name}{index}" in service_file.messages:
        index += 1
    return f"{name}{index}"


def _register_message_schema(
    service_file: ProtoServiceFile,
    name: str,
    schema: Mapping[str, Any] | None,
    schemas: Mapping[str, Any],
) -> None:
    if name in service_file.messages:
        return
    service_file.messages[name] = schema
    _register_schema_dependencies(service_file, schema, schemas)


def _register_message_contract(
    service_file: ProtoServiceFile,
    message: Mapping[str, Any] | None,
    schemas: Mapping[str, Any],
) -> None:
    if message is None:
        return
    name = _message_name(message)
    variants = message.get("variants", [])
    if len(variants) == 1 and isinstance(variants[0], Mapping):
        _register_message_schema(service_file, name, _schema_by_name(variants[0].get("model"), schemas), schemas)
        return
    _register_message_schema(service_file, name, None, schemas)
    for variant in variants:
        if not isinstance(variant, Mapping):
            continue
        model_name = variant.get("model")
        if isinstance(model_name, str):
            _register_message_schema(service_file, model_name, _schema_by_name(model_name, schemas), schemas)


def _register_schema_dependencies(
    service_file: ProtoServiceFile,
    schema: Mapping[str, Any] | None,
    schemas: Mapping[str, Any],
) -> None:
    for field in _message_fields(schema).values():
        if isinstance(field, Mapping):
            _register_field_dependencies(service_file, field, schemas)


def _register_field_dependencies(
    service_file: ProtoServiceFile,
    field: Mapping[str, Any],
    schemas: Mapping[str, Any],
) -> None:
    field_type = field.get("type")
    if field_type == "array":
        items = field.get("items")
        if isinstance(items, Mapping):
            _register_field_dependencies(service_file, items, schemas)
        return
    if field_type == "map":
        keys = field.get("keys")
        values = field.get("values")
        if isinstance(keys, Mapping):
            _register_field_dependencies(service_file, keys, schemas)
        if isinstance(values, Mapping):
            _register_field_dependencies(service_file, values, schemas)
        return
    if field_type == "enum":
        enum_name = field.get("enum")
        values = field.get("values", [])
        if isinstance(enum_name, str) and isinstance(values, list):
            service_file.enums.setdefault(enum_name, list(values))
        return
    ref = field.get("ref")
    if isinstance(ref, str):
        _register_message_schema(service_file, ref, _schema_by_name(ref, schemas), schemas)


def _schema_for_route_response(route: Mapping[str, Any], schemas: Mapping[str, Any]) -> Mapping[str, Any] | None:
    response = route.get("response")
    if not isinstance(response, Mapping):
        return None
    return _schema_by_name(response.get("model"), schemas)


def _schema_for_route_request(route: Mapping[str, Any], schemas: Mapping[str, Any]) -> Mapping[str, Any] | None:
    request = route.get("request")
    if not isinstance(request, Mapping):
        return None
    model_slots = [
        ("query", request.get("query_model")),
        ("json", request.get("json_model")),
        ("form", request.get("form_model")),
        ("binary", request.get("binary_model")),
    ]
    present = [(slot, model_name) for slot, model_name in model_slots if isinstance(model_name, str)]
    if len(present) == 1:
        return _schema_by_name(present[0][1], schemas)
    if not present:
        return None
    fields: "OrderedDict[str, Mapping[str, Any]]" = OrderedDict()
    for slot, model_name in present:
        fields[slot] = {
            "type": "object",
            "ref": model_name,
            "wire_name": slot,
            "optional": False,
            "description": "",
        }
    return {
        "kind": "model",
        "type": "object",
        "fields": fields,
        "auto": True,
    }


def _schema_by_name(name: object, schemas: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if not isinstance(name, str):
        return None
    schema = schemas.get(name)
    return schema if isinstance(schema, Mapping) else None


def _message_name(message: Mapping[str, Any] | None) -> str:
    if message is None:
        return "Empty"
    name = message.get("name")
    return str(name) if name else "Empty"


def _split_service_id(service_id: str) -> tuple[str, str]:
    if "." not in service_id:
        return "root", service_id
    root, group = service_id.split(".", 1)
    return root or "root", group or "root"


def _service_package(base_package: str, root: str, group: str) -> str:
    clean_base = base_package.strip(".")
    segments = [segment for segment in (_proto_field_name(root), _proto_field_name(group)) if segment]
    if clean_base:
        base_segments = clean_base.split(".")
        if segments and base_segments[-1] == segments[0]:
            segments = segments[1:]
        return ".".join([clean_base, *segments])
    return ".".join(segments) or "api"


def _pascal(value: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Root"


def _proto_type_name(value: str) -> str:
    normalized = _pascal(value)
    if normalized[0].isdigit():
        return f"Type{normalized}"
    return normalized


def _proto_field_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").lower()
    if not normalized:
        return "field"
    if normalized[0].isdigit():
        return f"field_{normalized}"
    return normalized


def _constant_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").upper()
    if not normalized:
        return "VALUE"
    if normalized[0].isdigit():
        return f"VALUE_{normalized}"
    return normalized
