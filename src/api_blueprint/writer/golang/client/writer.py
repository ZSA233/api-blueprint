from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Generator, Mapping, Sequence

from api_blueprint.contract import ContractGraph, build_contract_graph
from api_blueprint.route_selection import normalize_selection_rules
from api_blueprint.writer.core.base import BaseBlueprint, BaseWriter
from api_blueprint.writer.core.errors import ErrorCatalogEntry, error_catalog_from_manifest
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.planning import route_matches_rule
from api_blueprint.writer.core.templates import render

from .binary_schema import GoClientBinarySchema, unique_go_client_binary_schemas


logger = logging.getLogger("GolangClientWriter")
logger.setLevel(logging.INFO)


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class GoClientRoute:
    route: JsonObject

    @property
    def operation(self) -> str:
        return _go_exported(str(self.route.get("operation") or "Call"))

    @property
    def method(self) -> str:
        methods = self.route.get("methods")
        if isinstance(methods, list) and methods:
            return str(methods[0]).upper()
        return "GET"

    @property
    def url(self) -> str:
        return str(self.route.get("url") or "")

    @property
    def route_id(self) -> str:
        return str(self.route.get("id") or "")

    @property
    def kind(self) -> str:
        return str(self.route.get("kind") or "rpc")

    @property
    def request(self) -> Mapping[str, Any]:
        request = self.route.get("request")
        return request if isinstance(request, Mapping) else {}

    @property
    def response(self) -> Mapping[str, Any]:
        response = self.route.get("response")
        return response if isinstance(response, Mapping) else {}

    @property
    def connection(self) -> Mapping[str, Any]:
        connection = self.route.get("connection")
        return connection if isinstance(connection, Mapping) else {}

    @property
    def response_wrapper(self) -> str:
        wrapper = self.response.get("wrapper")
        return str(wrapper or "NoneWrapper")

    @property
    def binary_schema(self) -> Mapping[str, Any] | None:
        schema = self.request.get("binary_schema")
        return schema if isinstance(schema, Mapping) else None

    @property
    def has_binary_schema(self) -> bool:
        return self.binary_schema is not None


@dataclass
class GoClientGroup:
    segments: tuple[str, ...]
    package: str
    client_class: str
    routes: list[GoClientRoute] = field(default_factory=list)
    binary_schemas: list[GoClientBinarySchema] = field(default_factory=list)


class GolangClientBlueprint(BaseBlueprint["GolangClientWriter"]):
    pass


class GolangClientWriter(BaseWriter[GolangClientBlueprint]):
    def __init__(
        self,
        working_dir: str | Path = ".",
        *,
        module: str | None = None,
        base_url: str | None = None,
        base_url_expr: str | None = None,
        include: Sequence[str] = (),
        exclude: Sequence[str] = (),
        contract_graph: ContractGraph | None = None,
    ) -> None:
        super().__init__(working_dir)
        self.module = module or ""
        self.base_url = base_url or ""
        self.base_url_expr = base_url_expr
        self.include = normalize_selection_rules(include)
        self.exclude = normalize_selection_rules(exclude)
        self.contract_graph = contract_graph
        self._written_files: set[Path] = set()

    def gen(self) -> None:
        graph = self.contract_graph or build_contract_graph([bp.bp for bp in self.bps])
        manifest = graph.to_manifest()
        routes = [dict(route) for route in _list_of_maps(manifest.get("routes")) if self._route_selected(route)]
        schemas = _mapping_of_maps(manifest.get("schemas"))
        errors = error_catalog_from_manifest(manifest, route_ids=[str(route.get("id") or "") for route in routes])
        services = _mapping_of_maps_by_id(manifest.get("services"))
        type_names = _TypeNames(schemas)
        groups = _build_groups(routes, services)

        self._write_runtime_files(schemas, type_names, errors, groups)
        for group in groups:
            self._write_group_files(group, schemas, type_names)
        self._write_http_files()
        self._format_written_files()

    def _route_selected(self, route: Mapping[str, Any]) -> bool:
        if self.include and not any(route_matches_rule(route, rule) for rule in self.include):
            return False
        return not any(route_matches_rule(route, rule) for rule in self.exclude)

    def _write_runtime_files(
        self,
        schemas: Mapping[str, JsonObject],
        type_names: "_TypeNames",
        errors: tuple[ErrorCatalogEntry, ...],
        groups: tuple[GoClientGroup, ...],
    ) -> None:
        self._write_generated("runtime/gen_client.go", render("golang", "gen_client.go", {}, "client/runtime"))
        self._write_generated(
            "runtime/gen_errors.go",
            render("golang", "gen_errors.go", {"errors": errors}, "client/runtime"),
        )
        self._write_generated(
            "runtime/gen_error_catalog.go",
            render("golang", "gen_error_catalog.go", {"errors": errors}, "client/runtime"),
        )
        self._write_generated(
            "runtime/gen_models.go",
            render(
                "golang",
                "gen_models.go",
                {"lines": _runtime_model_lines(schemas, type_names)},
                "client/runtime",
            ),
        )
        self._write_generated(
            "runtime/binary/gen_runtime.go",
            render("golang", "gen_runtime.go", {}, "client/runtime/binary"),
        )

    def _write_group_files(
        self,
        group: GoClientGroup,
        schemas: Mapping[str, JsonObject],
        type_names: "_TypeNames",
    ) -> None:
        route_dir = Path("routes").joinpath(*group.segments)
        model_lines = _group_model_lines(group, schemas, type_names)
        self._write_generated(
            route_dir / "gen_models.go",
            render(
                "golang",
                "gen_models.go",
                {
                    "group": group,
                    "has_runtime_import": any("runtime." in line for line in model_lines),
                    "lines": model_lines,
                    "runtime_import": self.runtime_import,
                },
                "client/routes",
            ),
        )
        self._write_generated(
            route_dir / "gen_client.go",
            render(
                "golang",
                "gen_client.go",
                {
                    "client_class_for_route": _client_class_for_route,
                    "connection_method_name": _connection_method_name,
                    "connection_transport_method": _connection_transport_method,
                    "group": group,
                    "has_binary_schemas": any(route.has_binary_schema for route in group.routes),
                    "route_params": _route_params,
                    "route_response_type": _route_response_type,
                    "response_wrapper_name": _response_wrapper_name,
                    "runtime_binary_import": self.runtime_binary_import,
                    "runtime_import": self.runtime_import,
                    "runtime_request_fields": _runtime_request_fields,
                },
                "client/routes",
            ),
        )
        if group.binary_schemas:
            self._write_generated(
                route_dir / "binary" / "gen_binary.go",
                render(
                    "golang",
                    "gen_binary.go",
                    {
                        "binary_schemas": group.binary_schemas,
                        "runtime_binary_import": self.runtime_binary_import,
                    },
                    "client/routes/binary",
                ),
            )
        else:
            stale_binary_dir = self.working_dir / route_dir / "binary"
            if stale_binary_dir.exists():
                shutil.rmtree(stale_binary_dir)
        self._write_user_file(
            route_dir / "client.go",
            render("golang", "client.go", {"group": group}, "client/routes"),
        )

    def _write_http_files(self) -> None:
        base_url_code = self.base_url_expr if self.base_url_expr is not None else _code_literal(self.base_url)
        self._write_generated(
            "transports/http/gen_config.go",
            render("golang", "gen_config.go", {"base_url_code": base_url_code}, "client/transports/http"),
        )
        self._write_generated(
            "transports/http/gen_transport.go",
            render(
                "golang",
                "gen_transport.go",
                {
                    "runtime_binary_import": self.runtime_binary_import,
                    "runtime_import": self.runtime_import,
                },
                "client/transports/http",
            ),
        )
        self._write_user_file(
            "transports/http/client.go",
            render("golang", "client.go", {"runtime_import": self.runtime_import}, "client/transports/http"),
        )

    @property
    def runtime_import(self) -> str:
        return _join_import(self.module, "runtime")

    @property
    def runtime_binary_import(self) -> str:
        return _join_import(self.module, "runtime", "binary")

    @contextmanager
    def write_file(self, filepath: str | Path, overwrite: bool = False) -> Generator[IO[str] | None, None, None]:
        path = self.working_dir / filepath
        path.parent.mkdir(parents=True, exist_ok=True)
        wrote = False
        with ensure_filepath_open(str(path), "w", overwrite=overwrite) as handle:
            if handle:
                wrote = True
            yield handle
        if wrote:
            self._written_files.add(path)
            logger.info("[+] Written: %s", path)
        else:
            logger.info("[.] Skipped: %s", path)

    def _write_generated(self, path: str | Path, source: str) -> None:
        with self.write_file(path, overwrite=True) as handle:
            if handle:
                handle.write(source)

    def _write_user_file(self, path: str | Path, source: str) -> None:
        with self.write_file(path, overwrite=False) as handle:
            if handle:
                handle.write(source)

    def _format_written_files(self) -> None:
        if not self._written_files or shutil.which("gofmt") is None:
            return
        subprocess.run(["gofmt", "-w", *[str(path) for path in sorted(self._written_files)]], check=True)


class _TypeNames:
    def __init__(self, schemas: Mapping[str, JsonObject]) -> None:
        base_names: dict[str, list[str]] = {}
        for name in schemas:
            base_names.setdefault(_go_type_name(name), []).append(name)
        self._names = {
            name: (_go_type_name(name) if len(base_names[_go_type_name(name)]) == 1 else _go_type_name(name.replace(".", "_")))
            for name in schemas
        }

    def schema(self, name: object) -> str:
        key = str(name or "")
        return self._names.get(key, _go_type_name(key))

    def ref(self, value: Mapping[str, Any], *, pointer: bool = False) -> str:
        ref = value.get("ref")
        if isinstance(ref, str) and ref:
            target = self.schema(ref)
            return f"*{target}" if pointer else target
        return "any"


def _runtime_model_lines(schemas: Mapping[str, JsonObject], type_names: _TypeNames) -> list[str]:
    enums = _collect_enums(schemas)
    lines: list[str] = []
    for enum in enums.values():
        lines.extend(_render_enum(enum))
        lines.append("")
    for schema_name, schema in schemas.items():
        lines.extend(_render_schema(schema_name, schema, type_names))
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _render_schema(schema_name: str, schema: Mapping[str, Any], type_names: _TypeNames) -> list[str]:
    name = type_names.schema(schema_name)
    if schema.get("kind") == "alias" or schema.get("type") == "alias":
        target = schema.get("target")
        target_type = _go_type_for_schema_value(target if isinstance(target, Mapping) else {}, type_names)
        return [f"type {name} = {target_type}"]
    if schema.get("type") != "object":
        return [f"type {name} = {_go_type_for_schema_value(schema, type_names)}"]
    fields = schema.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return [f"type {name} struct {{}}"]
    lines = [f"type {name} struct {{"]
    for field_name, field_schema in fields.items():
        if not isinstance(field_schema, Mapping):
            continue
        go_field = _go_exported(str(field_schema.get("name") or field_name))
        go_type = _go_type_for_schema_value(field_schema, type_names)
        wire_name = str(field_schema.get("wire_name") or field_schema.get("name") or field_name)
        omitempty = ",omitempty" if field_schema.get("optional") else ""
        tags = f'`json:"{wire_name}{omitempty}" form:"{wire_name}{omitempty}"`'
        lines.append(f"\t{go_field} {go_type} {tags}")
    lines.append("}")
    return lines


def _render_enum(enum: Mapping[str, Any]) -> list[str]:
    name = _go_type_name(str(enum.get("enum") or enum.get("name") or "EnumValue"))
    base_type = _enum_base_type(enum)
    lines = [f"type {name} {base_type}", "", "const ("]
    for member in enum.get("enum_values", []):
        if not isinstance(member, Mapping):
            continue
        member_name = _go_exported(str(member.get("name") or member.get("value") or "Value"))
        lines.append(f"\t{name}{member_name} {name} = {_code_literal(member.get('value'))}")
    lines.append(")")
    return lines


def _group_model_lines(
    group: GoClientGroup,
    schemas: Mapping[str, JsonObject],
    type_names: _TypeNames,
) -> list[str]:
    body: list[str] = []
    emitted_messages: set[str] = set()
    for route in group.routes:
        body.extend(_route_aliases(route, schemas, type_names, emitted_messages))
    while body and body[-1] == "":
        body.pop()
    return body


def _route_aliases(
    route: GoClientRoute,
    schemas: Mapping[str, JsonObject],
    type_names: _TypeNames,
    emitted_messages: set[str],
) -> list[str]:
    lines: list[str] = []
    operation = route.operation
    aliases = (
        (f"REQ_{operation}_QUERY", route.request.get("query_model")),
        (f"REQ_{operation}_JSON", route.request.get("json_model")),
        (f"REQ_{operation}_FORM", route.request.get("form_model")),
        (f"REQ_{operation}_BINARY", None if route.has_binary_schema else route.request.get("binary_model")),
        (f"OPEN_{operation}", route.connection.get("open_model")),
        (f"CLOSE_{operation}", route.connection.get("close_model")),
        (f"RSP_{operation}_BODY", route.response.get("model")),
    )
    for alias, schema_name in aliases:
        if isinstance(schema_name, str) and schema_name:
            schema = schemas.get(schema_name)
            if isinstance(schema, Mapping) and schema.get("auto") is True and schema.get("type") == "object":
                lines.extend(_render_route_schema(alias, schema, type_names))
            else:
                lines.append(f"type {alias} = runtime.{type_names.schema(schema_name)}")
    for message_key in ("server_message", "client_message"):
        message = route.connection.get(message_key)
        if isinstance(message, Mapping) and isinstance(message.get("name"), str):
            if message["name"] in emitted_messages:
                continue
            emitted_messages.add(str(message["name"]))
            lines.append(f"type {message['name']} struct {{")
            lines.append("\tType string `json:\"type\"`")
            lines.append("\tData any `json:\"data,omitempty\"`")
            lines.append("}")
    if lines:
        lines.append("")
    return lines


def _render_route_schema(alias: str, schema: Mapping[str, Any], type_names: _TypeNames) -> list[str]:
    fields = schema.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return [f"type {alias} struct {{}}"]
    lines = [f"type {alias} struct {{"]
    for field_name, field_schema in fields.items():
        if not isinstance(field_schema, Mapping):
            continue
        go_field = _go_exported(str(field_schema.get("name") or field_name))
        go_type = _go_type_for_route_schema_value(field_schema, type_names)
        wire_name = str(field_schema.get("wire_name") or field_schema.get("name") or field_name)
        omitempty = ",omitempty" if field_schema.get("optional") else ""
        tags = f'`json:"{wire_name}{omitempty}" form:"{wire_name}{omitempty}"`'
        lines.append(f"\t{go_field} {go_type} {tags}")
    lines.append("}")
    return lines


def _connection_method_name(route: GoClientRoute) -> str:
    if route.kind == "legacy_ws":
        return f"Connect{route.operation}"
    if route.kind == "stream":
        return f"Subscribe{route.operation}"
    if route.kind == "channel":
        return f"Open{route.operation}"
    return route.operation


def _connection_transport_method(route: GoClientRoute) -> str:
    if route.kind == "legacy_ws":
        return "ConnectUnsupported"
    if route.kind == "stream":
        return "StreamUnsupported"
    if route.kind == "channel":
        return "ChannelUnsupported"
    return "Do"


def _route_response_type(route: GoClientRoute) -> str:
    response_model = route.response.get("model")
    if isinstance(response_model, str) and response_model:
        return f"*RSP_{route.operation}_BODY"
    return "any"


def _response_wrapper_name(route: GoClientRoute) -> str:
    return route.response_wrapper


def _client_class_for_route(route: GoClientRoute) -> str:
    service_id = str(route.route.get("service_id") or "api")
    group = service_id.split(".", 1)[1] if "." in service_id else service_id
    return f"{_go_exported(group or service_id)}Client"


def _route_params(route: GoClientRoute, *, include_open: bool) -> list[str]:
    params: list[str] = []
    if isinstance(route.request.get("query_model"), str):
        params.append(f"query *REQ_{route.operation}_QUERY")
    if isinstance(route.request.get("json_model"), str):
        params.append(f"jsonBody *REQ_{route.operation}_JSON")
    if isinstance(route.request.get("form_model"), str):
        params.append(f"formBody *REQ_{route.operation}_FORM")
    if route.has_binary_schema:
        params.append("binaryBody runtimebinary.Body")
    elif isinstance(route.request.get("binary_model"), str):
        params.append(f"binaryBody *REQ_{route.operation}_BINARY")
    if include_open and isinstance(route.connection.get("open_model"), str):
        params.append(f"openData *OPEN_{route.operation}")
    return params


def _runtime_request_fields(route: GoClientRoute) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    if isinstance(route.request.get("query_model"), str):
        fields.append(("Query", "query"))
    if isinstance(route.request.get("json_model"), str):
        fields.append(("JSON", "jsonBody"))
    if isinstance(route.request.get("form_model"), str):
        fields.append(("Form", "formBody"))
    if route.has_binary_schema or isinstance(route.request.get("binary_model"), str):
        fields.append(("Binary", "binaryBody"))
    return fields


def _go_type_for_schema_value(value: Mapping[str, Any], type_names: _TypeNames) -> str:
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
        return _go_type_name(str(value.get("enum") or "EnumValue"))
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
        "any": "any",
        "null": "any",
    }.get(value_type, "any")


def _go_type_for_route_schema_value(value: Mapping[str, Any], type_names: _TypeNames) -> str:
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
        return f"runtime.{_go_type_name(str(value.get('enum') or 'EnumValue'))}"
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


def _build_groups(routes: Sequence[JsonObject], services: Mapping[str, JsonObject]) -> tuple[GoClientGroup, ...]:
    groups: dict[tuple[str, ...], GoClientGroup] = {}
    for route in routes:
        service = services.get(str(route.get("service_id") or ""), {})
        root = _path_segment(str(service.get("root") or _service_root(route)), default="api")
        group_name = _path_segment(str(service.get("group") or root), default=root)
        segments = (root,) if group_name == root else (root, group_name)
        group = groups.get(segments)
        if group is None:
            package = _go_package_name(segments[-1])
            group = GoClientGroup(
                segments=segments,
                package=package,
                client_class=f"{_go_exported(group_name)}Client",
            )
            groups[segments] = group
        client_route = GoClientRoute(route)
        group.routes.append(client_route)
        if client_route.binary_schema is not None:
            group.binary_schemas = unique_go_client_binary_schemas(
                [schema.raw for schema in group.binary_schemas] + [client_route.binary_schema]
            )
    return tuple(groups.values())


def _service_root(route: Mapping[str, Any]) -> str:
    service_id = str(route.get("service_id") or "api")
    return service_id.split(".", 1)[0]


def _list_of_maps(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _mapping_of_maps(value: object) -> dict[str, JsonObject]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): dict(item) for key, item in value.items() if isinstance(item, Mapping)}


def _mapping_of_maps_by_id(value: object) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for item in _list_of_maps(value):
        item_id = item.get("id")
        if isinstance(item_id, str):
            result[item_id] = item
    return result


def _go_type_name(value: str) -> str:
    if "." in value:
        value = value.rsplit(".", 1)[-1]
    return _go_exported(value)


def _go_exported(value: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z_]+", value) if part]
    if not parts:
        return "Value"
    result = "".join(part[:1].upper() + part[1:] for part in parts)
    if result[:1].isdigit():
        result = "Value" + result
    return result


def _go_package_name(value: str) -> str:
    package = re.sub(r"[^0-9A-Za-z_]+", "_", value.lower()).strip("_")
    if not package:
        return "api"
    if package[0].isdigit():
        package = "p_" + package
    return package


def _path_segment(value: str, *, default: str) -> str:
    segment = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip("/").lower()).strip("_")
    return segment or default


def _join_import(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part.strip("/"))


def _code_literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
