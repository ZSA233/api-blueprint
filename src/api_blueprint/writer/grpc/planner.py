from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from api_blueprint.contract import ContractGraph
from api_blueprint.engine.schema.enum_metadata import enum_comment_text
from api_blueprint.writer.core.planning import route_matches_rule
from api_blueprint.writer.grpc.layout import GrpcProtoFileRule, GrpcProtoLayout, ProtoFileLayout


JsonObject = Mapping[str, Any]


@dataclass
class ProtoFieldPlan:
    type_name: str
    name: str
    number: int
    label: str = ""

    @property
    def declaration(self) -> str:
        prefix = f"{self.label} " if self.label else ""
        return f"{prefix}{self.type_name} {self.name} = {self.number};"


@dataclass
class ProtoOneofPlan:
    name: str
    fields: list[ProtoFieldPlan] = field(default_factory=list)


@dataclass
class ProtoMessagePlan:
    name: str
    fields: list[ProtoFieldPlan] = field(default_factory=list)
    oneofs: list[ProtoOneofPlan] = field(default_factory=list)


@dataclass
class ProtoEnumValuePlan:
    name: str
    number: int
    description: str = ""

    @property
    def declaration(self) -> str:
        return f"{self.name} = {self.number};"

    @property
    def comment(self) -> str:
        return enum_comment_text(self.description)


@dataclass
class ProtoEnumPlan:
    name: str
    values: list[ProtoEnumValuePlan]

    @property
    def declarations(self) -> list[str]:
        return [value.declaration for value in self.values]


@dataclass
class ProtoRpcPlan:
    name: str
    request_type: str
    response_type: str
    request_stream: bool = False
    response_stream: bool = False

    @property
    def declaration(self) -> str:
        request_prefix = "stream " if self.request_stream else ""
        response_prefix = "stream " if self.response_stream else ""
        return f"rpc {self.name} ({request_prefix}{self.request_type}) returns ({response_prefix}{self.response_type});"


@dataclass
class ProtoServicePlan:
    name: str
    rpcs: list[ProtoRpcPlan] = field(default_factory=list)


@dataclass
class ProtoFilePlan:
    path: str
    package: str
    go_package: str
    services: "OrderedDict[str, ProtoServicePlan]" = field(default_factory=OrderedDict)
    messages: "OrderedDict[str, ProtoMessagePlan]" = field(default_factory=OrderedDict)
    enums: "OrderedDict[str, ProtoEnumPlan]" = field(default_factory=OrderedDict)
    imports: "OrderedDict[str, None]" = field(default_factory=OrderedDict)

    @property
    def import_paths(self) -> list[str]:
        return list(self.imports)

    @property
    def service_list(self) -> list[ProtoServicePlan]:
        return list(self.services.values())

    @property
    def message_list(self) -> list[ProtoMessagePlan]:
        return list(self.messages.values())

    @property
    def enum_list(self) -> list[ProtoEnumPlan]:
        return list(self.enums.values())

    def add_import(self, path: str) -> None:
        if path and path != self.path:
            self.imports.setdefault(path, None)


class ProtoPlanner:
    def __init__(
        self,
        graph: ContractGraph,
        *,
        package: str,
        go_package_prefix: str,
        proto_files: Sequence[GrpcProtoFileRule] = (),
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
    ) -> None:
        manifest = graph.to_manifest()
        self.schemas = manifest["schemas"] if isinstance(manifest.get("schemas"), Mapping) else {}
        self.package = package
        self.go_package_prefix = go_package_prefix
        self.layout = GrpcProtoLayout(proto_files)
        self.files: "OrderedDict[str, ProtoFilePlan]" = OrderedDict()
        self._building_messages: set[tuple[str, str]] = set()
        self.routes = manifest["routes"] if isinstance(manifest.get("routes"), list) else []
        self.include = tuple(include)
        self.exclude = tuple(exclude)

    def plan(self) -> "OrderedDict[str, ProtoFilePlan]":
        for route in self.routes:
            if isinstance(route, Mapping) and self._route_selected(route):
                self._add_route(route)
        return self.files

    def _route_selected(self, route: JsonObject) -> bool:
        if self.include and not any(route_matches_rule(route, rule) for rule in self.include):
            return False
        return not any(route_matches_rule(route, rule) for rule in self.exclude)

    def _add_route(self, route: JsonObject) -> None:
        route_layout = self.layout.route_file(route)
        service_file = self._route_file(route, route_layout)
        service_name = (
            (route_layout.service if route_layout is not None else None)
            or _route_proto_name(route, "service")
            or f"{_pascal(_route_group(route))}Service"
        )
        service = service_file.services.setdefault(service_name, ProtoServicePlan(name=service_name))
        rpc_name = _route_proto_name(route, "rpc") or _pascal(str(route["operation"]))

        if route["kind"] == "rpc":
            request_name = f"{rpc_name}Request"
            response_name = f"{rpc_name}Response"
            request_type = self._register_message_schema(
                service_file,
                request_name,
                _schema_for_route_request(route, self.schemas),
            )
            response_type = self._register_message_schema(
                service_file,
                response_name,
                _schema_for_route_response(route, self.schemas),
            )
            service.rpcs.append(ProtoRpcPlan(rpc_name, request_type, response_type))
            return

        if route["kind"] == "stream":
            connection = route["connection"]
            request_name = f"{rpc_name}Request"
            request_type = self._register_message_schema(
                service_file,
                request_name,
                _schema_by_name(connection.get("open_model"), self.schemas),
            )
            response_type = self._register_message_contract(service_file, connection["server_message"])
            service.rpcs.append(ProtoRpcPlan(rpc_name, request_type, response_type, response_stream=True))
            return

        if route["kind"] == "channel":
            connection = route["connection"]
            request_type = self._register_message_contract(service_file, connection["client_message"])
            response_type = self._register_message_contract(service_file, connection["server_message"])
            service.rpcs.append(
                ProtoRpcPlan(rpc_name, request_type, response_type, request_stream=True, response_stream=True)
            )

    def _route_file(self, route: JsonObject, route_layout: ProtoFileLayout | None) -> ProtoFilePlan:
        root, group = _split_service_id(str(route["service_id"]))
        route_proto = _proto_metadata(route)
        path = str(
            (route_layout.file if route_layout is not None else None)
            or route_proto.get("file")
            or f"{root}/{group}.proto"
        )
        return self._ensure_file(
            path,
            package=str(
                (route_layout.package if route_layout is not None else None)
                or route_proto.get("package")
                or _service_package(self.package, root, group)
            ),
            go_package=str(
                (route_layout.go_package if route_layout is not None else None)
                or route_proto.get("go_package")
                or _go_package_for_path(self.go_package_prefix, path)
            ),
        )

    def _ensure_file(self, path: str, *, package: str, go_package: str) -> ProtoFilePlan:
        existing = self.files.get(path)
        if existing is not None:
            if existing.package != package:
                raise ValueError(f"proto file package mismatch for {path}: {existing.package} != {package}")
            if existing.go_package != go_package:
                raise ValueError(f"proto file go_package mismatch for {path}: {existing.go_package} != {go_package}")
            return existing
        plan = ProtoFilePlan(path=path, package=package, go_package=go_package)
        self.files[path] = plan
        return plan

    def _file_for_schema_contract(self, schema: JsonObject | None, default_file: ProtoFilePlan) -> ProtoFilePlan:
        schema_proto = _proto_metadata(schema)
        schema_layout = self.layout.schema_file(schema or {})
        path = (schema_layout.file if schema_layout is not None else None) or schema_proto.get("file")
        if not isinstance(path, str) or not path:
            return default_file
        return self._ensure_file(
            path,
            package=str(
                (schema_layout.package if schema_layout is not None else None)
                or schema_proto.get("package")
                or _package_for_path(self.package, path)
            ),
            go_package=str(
                (schema_layout.go_package if schema_layout is not None else None)
                or schema_proto.get("go_package")
                or _go_package_for_path(self.go_package_prefix, path)
            ),
        )

    def _register_message_contract(self, service_file: ProtoFilePlan, message: JsonObject | None) -> str:
        if message is None:
            return self._register_message_schema(service_file, "Empty", None)
        name = _message_name(message)
        variants = message.get("variants", [])
        if len(variants) == 1 and isinstance(variants[0], Mapping):
            return self._register_message_schema(service_file, name, _schema_by_name(variants[0].get("model"), self.schemas))
        fields: "OrderedDict[str, Mapping[str, Any]]" = OrderedDict()
        for variant in variants:
            if not isinstance(variant, Mapping) or not isinstance(variant.get("model"), str):
                continue
            key = str(variant.get("key") or variant["model"])
            fields[key] = {
                "type": "object",
                "ref": variant["model"],
                "wire_name": _proto_field_name(key),
                "optional": False,
                "description": "",
                "contract": {"choice": "message"},
            }
        schema = {
            "kind": "model",
            "type": "object",
            "fields": fields,
            "auto": True,
        }
        return self._register_message_schema(service_file, name, schema)

    def _register_message_schema(
        self,
        service_file: ProtoFilePlan,
        name: str,
        schema: JsonObject | None,
    ) -> str:
        message_name = _proto_type_name(name)
        message_file = service_file
        if schema is not None:
            schema_name = _schema_message_name(schema)
            if schema_name is not None:
                message_file = self._file_for_schema_contract(schema, service_file)
                if message_file.path != service_file.path:
                    service_file.add_import(message_file.path)
                    message_name = _proto_type_name(schema_name)
        type_reference = _message_type_reference(service_file, message_file, message_name)

        if message_name in message_file.messages:
            return type_reference

        key = (message_file.path, message_name)
        if key in self._building_messages:
            return type_reference
        self._building_messages.add(key)
        message = ProtoMessagePlan(name=message_name)
        message_file.messages[message_name] = message
        self._populate_message(message_file, message, schema)
        self._building_messages.remove(key)
        return type_reference

    def _populate_message(
        self,
        service_file: ProtoFilePlan,
        message: ProtoMessagePlan,
        schema: JsonObject | None,
    ) -> None:
        fields = _message_fields(schema)
        if not isinstance(fields, Mapping):
            return

        used_numbers: set[int] = set()
        pending: list[tuple[str, Mapping[str, Any], int | None]] = []
        for field_name, field in fields.items():
            if not isinstance(field, Mapping):
                continue
            number = _explicit_field_number(field)
            if number is not None:
                if number in used_numbers:
                    raise ValueError(f"duplicate proto field number {number} in message {message.name}")
                used_numbers.add(number)
            pending.append((str(field_name), field, number))

        next_number = 1
        oneofs: "OrderedDict[str, ProtoOneofPlan]" = OrderedDict()
        for field_name, field, number in pending:
            if number is None:
                while next_number in used_numbers:
                    next_number += 1
                number = next_number
                used_numbers.add(number)
                next_number += 1
            wire_name = str(field.get("wire_name") or field_name)
            field_context = f"{message.name}{_proto_type_name(wire_name)}"
            type_name = self._proto_type(field, service_file=service_file, context=field_context)
            label = _field_label(field)
            plan = ProtoFieldPlan(
                type_name=type_name.removeprefix("repeated "),
                name=_field_proto_name(field, wire_name),
                number=number,
                label="" if _field_oneof(field) else label,
            )
            oneof = _field_oneof(field)
            if oneof:
                if label:
                    raise ValueError(f"oneof field {message.name}.{plan.name} must not be repeated or optional")
                oneofs.setdefault(oneof, ProtoOneofPlan(name=oneof)).fields.append(plan)
            else:
                if type_name.startswith("repeated "):
                    plan.type_name = type_name.removeprefix("repeated ")
                    plan.label = "repeated"
                message.fields.append(plan)
        message.oneofs = list(oneofs.values())

    def _proto_type(self, field: JsonObject, *, service_file: ProtoFilePlan, context: str = "Value") -> str:
        proto = _proto_metadata(field)
        proto_type = proto.get("type")
        if isinstance(proto_type, str) and proto_type:
            proto_import = proto.get("import")
            if isinstance(proto_import, str) and proto_import:
                service_file.add_import(proto_import)
            return proto_type

        field_type = field.get("type")
        if field_type == "one_of":
            raise ValueError(
                f"gRPC target does not support legacy JSON OneOf at {context}; "
                "model it with protobuf oneof explicitly or use JSONValue"
            )
        if field_type == "coerce_string":
            return "string"
        if field_type == "array":
            items = field.get("items", {})
            if isinstance(items, Mapping):
                return f"repeated {self._proto_type(items, service_file=service_file, context=context + 'Item')}"
            return "repeated string"
        if field_type == "map":
            values = field.get("values", {})
            value_type = self._proto_map_value_type(values, service_file=service_file, context=context)
            return f"map<string, {value_type}>"
        ref = field.get("ref")
        if isinstance(ref, str):
            return self._message_reference(service_file, ref)
        if field_type == "enum":
            enum_name = _proto_type_name(str(field.get("enum") or "Enum"))
            enum_file = self._file_for_enum_contract(field, service_file)
            self._register_enum_contract(enum_file, field)
            if enum_file.path == service_file.path:
                return enum_name
            service_file.add_import(enum_file.path)
            if enum_file.package == service_file.package:
                return enum_name
            return f"{enum_file.package}.{enum_name}"
        if field_type in {"timestamp", "date_time"}:
            service_file.add_import("google/protobuf/timestamp.proto")
            return "google.protobuf.Timestamp"
        if field_type in {"struct", "json_value"}:
            service_file.add_import("google/protobuf/struct.proto")
            return "google.protobuf.Struct"
        if field_type in {"any_payload", "any_value"}:
            service_file.add_import("google/protobuf/any.proto")
            return "google.protobuf.Any"
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

    def _message_reference(self, service_file: ProtoFilePlan, ref: str) -> str:
        schema = _schema_by_name(ref, self.schemas)
        message_file = self._file_for_schema_contract(schema, service_file)
        message_name = self._register_message_schema(message_file, _schema_message_name(schema) or ref, schema)
        if message_file.path == service_file.path:
            return message_name
        service_file.add_import(message_file.path)
        if message_file.package == service_file.package:
            return message_name
        return f"{message_file.package}.{message_name}"

    def _file_for_enum_contract(self, enum_field: JsonObject, default_file: ProtoFilePlan) -> ProtoFilePlan:
        enum_layout = self.layout.enum_file(enum_field)
        if enum_layout is None:
            return default_file
        return self._ensure_file(
            enum_layout.file,
            package=str(enum_layout.package or _package_for_path(self.package, enum_layout.file)),
            go_package=str(enum_layout.go_package or _go_package_for_path(self.go_package_prefix, enum_layout.file)),
        )

    def _register_enum_contract(self, enum_file: ProtoFilePlan, enum_field: JsonObject) -> str:
        enum_name = _proto_type_name(str(enum_field.get("enum") or "Enum"))
        values = enum_field.get("values", [])
        enum_values = enum_field.get("enum_values", [])
        if isinstance(enum_values, list):
            enum_file.enums.setdefault(
                enum_name,
                ProtoEnumPlan(enum_name, _proto_enum_values(enum_name, enum_values, values)),
            )
        return enum_name

    def _proto_map_value_type(self, field: object, *, service_file: ProtoFilePlan, context: str) -> str:
        if not isinstance(field, Mapping):
            return "string"
        if field.get("type") not in {"array", "map"}:
            return self._proto_type(field, service_file=service_file, context=context + "Value")

        wrapper_name = _unique_message_name(service_file, f"{context}Value")
        if wrapper_name not in service_file.messages:
            schema = {
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
            self._register_message_schema(service_file, wrapper_name, schema)
        return wrapper_name


def plan_proto_files(
    graph: ContractGraph,
    *,
    package: str,
    go_package_prefix: str,
    proto_files: Sequence[GrpcProtoFileRule] = (),
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
) -> "OrderedDict[str, ProtoFilePlan]":
    return ProtoPlanner(
        graph,
        package=package,
        go_package_prefix=go_package_prefix,
        proto_files=proto_files,
        include=include,
        exclude=exclude,
    ).plan()


def _message_fields(schema: JsonObject | None) -> Mapping[str, Any]:
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


def _schema_for_route_response(route: JsonObject, schemas: JsonObject) -> JsonObject | None:
    response = route.get("response")
    if not isinstance(response, Mapping):
        return None
    return _schema_by_name(response.get("model"), schemas)


def _schema_for_route_request(route: JsonObject, schemas: JsonObject) -> JsonObject | None:
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


def _schema_by_name(name: object, schemas: JsonObject) -> JsonObject | None:
    if not isinstance(name, str):
        return None
    schema = schemas.get(name)
    if isinstance(schema, Mapping):
        return schema

    exact_matches = [
        candidate
        for candidate in schemas.values()
        if isinstance(candidate, Mapping)
        and name in {candidate.get("identity"), candidate.get("qualname")}
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    name_matches = [
        candidate
        for candidate in schemas.values()
        if isinstance(candidate, Mapping) and candidate.get("name") == name
    ]
    if len(name_matches) == 1:
        return name_matches[0]
    return None


def _schema_message_name(schema: JsonObject | None) -> str | None:
    if not isinstance(schema, Mapping):
        return None
    for name in ("name",):
        value = schema.get(name)
        if isinstance(value, str) and value:
            return value
    return None


def _message_name(message: JsonObject | None) -> str:
    if message is None:
        return "Empty"
    name = message.get("name")
    return str(name) if name else "Empty"


def _split_service_id(service_id: str) -> tuple[str, str]:
    if "." not in service_id:
        return "root", service_id
    root, group = service_id.split(".", 1)
    return root or "root", group or "root"


def _route_group(route: JsonObject) -> str:
    service_id = str(route.get("service_id") or "root")
    return _split_service_id(service_id)[1]


def _route_proto_name(route: JsonObject, key: str) -> str | None:
    proto = _proto_metadata(route)
    value = proto.get(key)
    return str(value) if value else None


def _service_package(base_package: str, root: str, group: str) -> str:
    clean_base = base_package.strip(".")
    segments = [segment for segment in (_proto_field_name(root), _proto_field_name(group)) if segment]
    if clean_base:
        base_segments = clean_base.split(".")
        if segments and base_segments[-1] == segments[0]:
            segments = segments[1:]
        return ".".join([clean_base, *segments])
    return ".".join(segments) or "api"


def _package_for_path(base_package: str, path: str) -> str:
    segments = [_proto_field_name(part) for part in path.removesuffix(".proto").split("/") if part]
    clean_base = base_package.strip(".")
    return ".".join([clean_base, *segments]) if clean_base else ".".join(segments) or "api"


def _go_package_for_path(go_package_prefix: str, path: str) -> str:
    if not go_package_prefix:
        return path.removesuffix(".proto")
    package_path = path.removesuffix(".proto")
    package_name = _proto_field_name(package_path.rsplit("/", 1)[-1])
    return f"{go_package_prefix.rstrip('/')}/{package_path};{package_name}"


def _proto_metadata(value: object) -> JsonObject:
    if not isinstance(value, Mapping):
        return {}
    proto = value.get("proto")
    return proto if isinstance(proto, Mapping) else {}


def _explicit_field_number(field: JsonObject) -> int | None:
    contract = field.get("contract")
    value = contract.get("field_id") if isinstance(contract, Mapping) else None
    if value is None:
        wire = field.get("wire")
        value = wire.get("number") if isinstance(wire, Mapping) else None
    if value is None:
        value = _proto_metadata(field).get("number")
    if value is None:
        return None
    number = int(value)
    if number <= 0:
        raise ValueError(f"proto field number must be positive: {number}")
    return number


def _field_oneof(field: JsonObject) -> str | None:
    contract = field.get("contract")
    value = contract.get("choice") if isinstance(contract, Mapping) else None
    if value is None:
        value = _proto_metadata(field).get("oneof")
    return str(value) if value else None


def _field_proto_name(field: JsonObject, fallback: str) -> str:
    value = _proto_metadata(field).get("name")
    if isinstance(value, str) and value:
        return _proto_identifier(value)
    source_name = field.get("name")
    if isinstance(source_name, str) and fallback and fallback != source_name:
        return _proto_identifier(fallback)
    return _proto_field_name(fallback)


def _field_label(field: JsonObject) -> str:
    proto = _proto_metadata(field)
    if proto.get("optional") is True:
        return "optional"
    contract = field.get("contract")
    if isinstance(contract, Mapping) and contract.get("optional") is True and _field_allows_proto_optional(field):
        return "optional"
    wire = field.get("wire")
    if isinstance(wire, Mapping) and wire.get("optional") is True and _field_allows_proto_optional(field):
        return "optional"
    return ""


def _field_allows_proto_optional(field: JsonObject) -> bool:
    if field.get("ref"):
        return False
    field_type = field.get("type")
    return str(field_type) not in {
        "array",
        "map",
        "object",
        "one_of",
        "timestamp",
        "date_time",
        "struct",
        "json_value",
        "any_payload",
        "any_value",
    }


def _unique_message_name(service_file: ProtoFilePlan, base_name: str) -> str:
    name = _proto_type_name(base_name)
    if name not in service_file.messages:
        return name

    index = 2
    while f"{name}{index}" in service_file.messages:
        index += 1
    return f"{name}{index}"


def _pascal(value: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Root"


def _message_type_reference(reference_file: ProtoFilePlan, message_file: ProtoFilePlan, message_name: str) -> str:
    if message_file.path == reference_file.path:
        return message_name
    if message_file.package == reference_file.package:
        return message_name
    return f"{message_file.package}.{message_name}"


def _proto_enum_values(
    enum_name: str,
    enum_values: list[object],
    fallback_values: object,
) -> list[ProtoEnumValuePlan]:
    prefix = _constant_name(enum_name)
    values: list[ProtoEnumValuePlan] = []
    used_names: set[str] = set()
    used_numbers: set[int] = set()

    for index, item in enumerate(enum_values, start=1):
        raw_name: object | None = None
        raw_value: object | None = None
        description = ""
        if isinstance(item, Mapping):
            raw_name = item.get("name")
            raw_value = item.get("value")
            description = str(item.get("description") or "")
        number = raw_value if isinstance(raw_value, int) and raw_value >= 0 else index
        if number in used_numbers:
            raise ValueError(f"duplicate proto enum number {number} in enum {enum_name}")
        value_name = _proto_enum_value_name(prefix, raw_name, raw_value)
        value_name = _unique_enum_value_name(value_name, used_names, suffix=number)
        used_numbers.add(number)
        used_names.add(value_name)
        values.append(ProtoEnumValuePlan(value_name, int(number), description))

    if not values and isinstance(fallback_values, list):
        for index, raw_value in enumerate(fallback_values, start=1):
            value_name = _unique_enum_value_name(
                f"{prefix}_{_constant_name(str(raw_value))}",
                used_names,
                suffix=index,
            )
            used_names.add(value_name)
            used_numbers.add(index)
            values.append(ProtoEnumValuePlan(value_name, index))

    if 0 not in used_numbers:
        default_name = _unique_enum_value_name(f"{prefix}_UNSPECIFIED", used_names, suffix=0)
        values.insert(0, ProtoEnumValuePlan(default_name, 0))
    return values


def _proto_enum_value_name(prefix: str, raw_name: object | None, raw_value: object | None) -> str:
    if isinstance(raw_value, int) and isinstance(raw_name, str) and raw_name:
        name = _constant_name(raw_name)
        if name.startswith(f"{prefix}_") or "_" in name:
            return name
        return f"{prefix}_{name}"
    source = raw_value if raw_value is not None else raw_name
    value_name = _constant_name(str(source))
    if value_name.startswith(f"{prefix}_"):
        return value_name
    return f"{prefix}_{value_name}"


def _unique_enum_value_name(value_name: str, used_names: set[str], *, suffix: int) -> str:
    if value_name not in used_names:
        return value_name
    return f"{value_name}_{suffix}"


def _proto_type_name(value: str) -> str:
    normalized = _pascal(value)
    if normalized[0].isdigit():
        return f"Type{normalized}"
    return normalized


def _proto_identifier(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][0-9A-Za-z_]*", value):
        return value
    return _proto_field_name(value)


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
