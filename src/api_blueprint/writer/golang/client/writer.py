from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Generator, Mapping, Sequence

from api_blueprint.contract import ContractGraph, build_contract_graph
from api_blueprint.route_selection import normalize_selection_rules
from api_blueprint.writer.core.base import BaseBlueprint, BaseWriter
from api_blueprint.writer.core.errors import ApiErrorEntry, api_errors_from_manifest, route_api_errors_from_manifest
from api_blueprint.writer.core.files import ensure_filepath_open
from api_blueprint.writer.core.go_naming import to_go_package_name
from api_blueprint.writer.core.planning import route_matches_rule
from api_blueprint.writer.core.sdk_names import go_exported_field_name
from api_blueprint.writer.core.templates import render

from .planner import GoClientGroup, GoClientRoute, build_go_client_groups


logger = logging.getLogger("GolangClientWriter")
logger.setLevel(logging.INFO)


JsonObject = dict[str, Any]
LEGACY_ROUTE_BINARY_DIRS = ("wire", "_gen_binary", "binary")


class GolangClientBlueprint(BaseBlueprint["GolangClientWriter"]):
    pass


@dataclass(frozen=True)
class RootFacadeGroup:
    group: GoClientGroup
    import_alias: str
    field_name: str


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
        errors = api_errors_from_manifest(manifest, route_ids=[str(route.get("id") or "") for route in routes])
        services = _mapping_of_maps_by_id(manifest.get("services"))
        type_names = _TypeNames(schemas)
        groups = build_go_client_groups(routes, services)

        route_errors = route_api_errors_from_manifest(manifest, route_ids=[str(route.get("id") or "") for route in routes])
        self._write_runtime_files(schemas, type_names, errors, route_errors, groups)
        for group in groups:
            self._write_group_files(group, schemas, type_names)
        self._write_http_files()
        self._write_root_facade(groups)
        self._format_written_files()

    def _route_selected(self, route: Mapping[str, Any]) -> bool:
        if self.include and not any(route_matches_rule(route, rule) for rule in self.include):
            return False
        return not any(route_matches_rule(route, rule) for rule in self.exclude)

    def _write_runtime_files(
        self,
        schemas: Mapping[str, JsonObject],
        type_names: "_TypeNames",
        errors: tuple[ApiErrorEntry, ...],
        route_errors: dict[str, tuple[ApiErrorEntry, ...]],
        groups: tuple[GoClientGroup, ...],
    ) -> None:
        self._write_generated("runtime/gen_client.go", render("golang", "gen_client.go", {}, "client/runtime"))
        self._write_generated(
            "runtime/gen_errors.go",
            render("golang", "gen_errors.go", {"errors": errors}, "client/runtime"),
        )
        self._write_generated(
            "runtime/gen_error_lookup.go",
            render("golang", "gen_error_lookup.go", {"errors": errors, "route_errors": route_errors}, "client/runtime"),
        )
        self._cleanup_stale_generated(self.working_dir / "runtime" / "gen_error_catalog.go")
        self._write_generated(
            "runtime/gen_types.go",
            render(
                "golang",
                "gen_types.go",
                {"lines": _runtime_model_lines(schemas, type_names)},
                "client/runtime",
            ),
        )
        self._cleanup_stale_generated(self.working_dir / "runtime" / "gen_models.go")
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
            route_dir / "gen_types.go",
            render(
                "golang",
                "gen_types.go",
                {
                    "group": group,
                    "has_runtime_import": any("runtime." in line for line in model_lines),
                    "lines": model_lines,
                    "runtime_import": self.runtime_import,
                },
                "client/routes",
            ),
        )
        self._cleanup_stale_generated(self.working_dir / route_dir / "gen_models.go")
        message_unions = _message_unions(group, type_names)
        if message_unions:
            self._write_generated(
                route_dir / "gen_messages.go",
                render(
                    "golang",
                    "gen_messages.go",
                    {"group": group, "message_unions": message_unions},
                    "client/routes",
                ),
            )
            self._write_generated(
                route_dir / "gen_message_cases.go",
                render(
                    "golang",
                    "gen_message_cases.go",
                    {"group": group, "message_cases": _message_cases(group, type_names)},
                    "client/routes",
                ),
            )
        else:
            self._cleanup_stale_generated(self.working_dir / route_dir / "gen_messages.go")
            self._cleanup_stale_generated(self.working_dir / route_dir / "gen_message_cases.go")
        self._write_generated(
            route_dir / "gen_client.go",
            render(
                "golang",
                "gen_client.go",
                {
                    "connection_method_name": _connection_method_name,
                    "connection_transport_method": _connection_transport_method,
                    "group": group,
                    "has_binary_schemas": bool(group.binary_schemas),
                    "has_request_binary_schemas": any(route.has_binary_schema for route in group.routes),
                    "route_params": _route_params,
                    "route_response_type": _route_response_type,
                    "route_response_value_type": _route_response_value_type,
                    "runtime_binary_import": self.runtime_binary_import,
                    "runtime_import": self.runtime_import,
                    "runtime_request_fields": _runtime_request_fields,
                },
                "client/routes",
            ),
        )
        if group.binary_schemas:
            self._write_generated(
                route_dir / "gen_binary.go",
                render(
                    "golang",
                    "gen_binary.go",
                    {
                        "binary_schemas": group.binary_schemas,
                        "group": group,
                        "runtime_binary_import": self.runtime_binary_import,
                    },
                    "client/routes/binary",
                ),
            )
            for legacy_dir in LEGACY_ROUTE_BINARY_DIRS:
                self._cleanup_legacy_binary_dir(self.working_dir / route_dir / legacy_dir)
        else:
            self._cleanup_stale_generated(self.working_dir / route_dir / "gen_binary.go")
            for stale_binary_dir in (
                *(self.working_dir / route_dir / legacy_dir for legacy_dir in LEGACY_ROUTE_BINARY_DIRS),
            ):
                self._cleanup_legacy_binary_dir(stale_binary_dir)
        self._write_user_file(
            route_dir / "client.go",
            render("golang", "client.go", {"group": group}, "client/routes"),
        )

    def _write_root_facade(self, groups: tuple[GoClientGroup, ...]) -> None:
        root_package = _root_package_name(self.module)
        self._write_generated(
            "gen_client.go",
            render(
                "golang",
                "gen_client.go",
                {
                    "groups": groups,
                    "root_groups": _root_facade_groups(groups),
                    "http_import": _join_import(self.module, "transports", "http"),
                    "module": self.module,
                    "runtime_import": self.runtime_import,
                    "route_import": _route_import,
                    "root_package": root_package,
                },
                "client",
            ),
        )
        self._write_user_file(
            "client.go",
            render("golang", "client.go", {"root_package": root_package}, "client"),
        )

    def _cleanup_legacy_binary_dir(self, binary_dir: Path) -> None:
        if not binary_dir.exists():
            return
        for generated_file in (binary_dir / "gen_binary.go",):
            if generated_file.exists():
                generated_file.unlink()
        try:
            binary_dir.rmdir()
        except OSError:
            return

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

    def _cleanup_stale_generated(self, path: Path) -> None:
        if path.exists():
            path.unlink()

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
        if isinstance(schema_name, str) and schema_name:
            schema = schemas.get(schema_name)
            if isinstance(schema, Mapping) and schema.get("auto") is True and schema.get("type") == "object":
                lines.extend(_render_route_schema(alias, schema, type_names))
            else:
                lines.append(f"type {alias} = runtime.{type_names.schema(schema_name)}")
    for message_key in ("server_message", "client_message"):
        message = route.connection.get(message_key)
        if isinstance(message, Mapping) and isinstance(message.get("name"), str):
            message_name = str(message["name"])
            if message_name in emitted_messages:
                continue
            emitted_messages.add(message_name)
            variants = message.get("variants")
            if isinstance(variants, list):
                for variant in variants:
                    if not isinstance(variant, Mapping):
                        continue
                    key = variant.get("key")
                    model = variant.get("model")
                    if isinstance(key, str) and key and isinstance(model, str) and model:
                        lines.append(f"type {_variant_alias_name(message_name, key)} = runtime.{type_names.schema(model)}")
    if lines:
        lines.append("")
    return lines


def _message_unions(group: GoClientGroup, type_names: _TypeNames) -> list[dict[str, Any]]:
    return [
        {
            "name": helper.name,
            "variants": [_message_variant(helper.name, variant.key, variant.model, type_names) for variant in helper.variants],
        }
        for helper in group.message_helpers()
    ]


def _message_cases(group: GoClientGroup, type_names: _TypeNames) -> list[dict[str, Any]]:
    cases = []
    for helper in group.message_helpers():
        variants = [_message_variant(helper.name, variant.key, variant.model, type_names) for variant in helper.variants]
        cases.append(
            {
                "name": helper.name,
                "case_interface": f"{helper.name}Case",
                "processor_type": f"{helper.name}Processor",
                "visitor": f"Visit{helper.name}",
                "error_type": f"{helper.name}Error",
                "error_kind_type": f"{helper.name}ErrorKind",
                "new_error": f"new{helper.name}Error",
                "wrap_error": f"wrap{helper.name}HandlerError",
                "variants": [
                    {
                        **variant,
                        "case_type": f"{helper.name}{variant['name']}Case",
                        "handler": f"On{variant['name']}",
                    }
                    for variant in variants
                ],
            }
        )
    return cases


def _message_variant(message_name: str, key: str, model: str, type_names: _TypeNames) -> dict[str, str]:
    variant_name = _go_exported(key)
    return {
        "key": key,
        "name": variant_name,
        "const": f"{message_name}Type{variant_name}",
        "ctor": f"New{message_name}{variant_name}",
        "decode": f"Decode{variant_name}",
        "data_type": _variant_alias_name(message_name, key),
    }


def _variant_alias_name(message_name: str, key: str) -> str:
    return f"{message_name}_{_go_exported(key)}_DATA"


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
    if route.kind == "stream":
        return f"Subscribe{route.operation}"
    if route.kind == "channel":
        return f"Open{route.operation}"
    return route.operation


def _connection_transport_method(route: GoClientRoute) -> str:
    if route.kind == "stream":
        return "StreamUnsupported"
    if route.kind == "channel":
        return "ChannelUnsupported"
    return "Do"


def _route_response_type(route: GoClientRoute) -> str:
    if route.response_kind == "byte_stream":
        return "*runtime.StreamResponse"
    if route.response_kind in {"bytes", "file"}:
        return "*runtime.RawResponse"
    if route.response_kind == "binary_schema" and route.response_binary_schema is not None:
        return f"*{_go_type_name(str(route.response_binary_schema.get('name') or 'Packet'))}"
    response_model = route.response.get("model")
    if isinstance(response_model, str) and response_model:
        return f"*{route.response_type}"
    return "any"


def _route_response_value_type(route: GoClientRoute) -> str:
    response_type = _route_response_type(route)
    if response_type.startswith("*"):
        return response_type[1:]
    return response_type


def _route_params(route: GoClientRoute, *, include_open: bool) -> list[str]:
    params: list[str] = []
    if isinstance(route.request.get("query_model"), str):
        params.append(f"query {route.query_type}")
    if isinstance(route.request.get("json_model"), str):
        params.append(f"jsonBody {route.json_type}")
    if isinstance(route.request.get("form_model"), str):
        params.append(f"formBody {route.form_type}")
    if isinstance(route.request.get("multipart_model"), str):
        params.append(f"multipartBody {route.multipart_type}")
    if route.has_binary_schema:
        params.append("binaryBody runtimebinary.Body")
    elif isinstance(route.request.get("binary_model"), str):
        params.append(f"binaryBody {route.binary_type}")
    if include_open and isinstance(route.connection.get("open_model"), str):
        params.append(f"openData {route.open_type}")
    return params


def _runtime_request_fields(route: GoClientRoute) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    if isinstance(route.request.get("query_model"), str):
        fields.append(("Query", "query"))
    if isinstance(route.request.get("json_model"), str):
        fields.append(("JSON", "jsonBody"))
    if isinstance(route.request.get("form_model"), str):
        fields.append(("Form", "formBody"))
    if isinstance(route.request.get("multipart_model"), str):
        fields.append(("Multipart", "multipartBody"))
    if route.has_binary_schema or isinstance(route.request.get("binary_model"), str):
        fields.append(("Binary", "binaryBody"))
    fields.append(("BodyKind", f"runtime.RequestBodyKind({_code_literal(route.body_kind)})"))
    fields.append(("ResponseKind", f"runtime.ResponseKind({_code_literal(route.response_kind)})"))
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
        "file": "MultipartFile",
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
    return go_exported_field_name(value, fallback="Value")


def _join_import(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part.strip("/"))


def _route_import(module: str, group: GoClientGroup) -> str:
    return _join_import(module, "routes", *group.segments)


def _root_facade_groups(groups: tuple[GoClientGroup, ...]) -> tuple[RootFacadeGroup, ...]:
    package_counts: dict[str, int] = {}
    field_counts: dict[str, int] = {}
    for group in groups:
        package_counts[group.package] = package_counts.get(group.package, 0) + 1
        field_name = group.client_class.removesuffix("Client")
        field_counts[field_name] = field_counts.get(field_name, 0) + 1

    facade_groups: list[RootFacadeGroup] = []
    for group in groups:
        import_alias = group.package
        if package_counts[group.package] > 1:
            import_alias = to_go_package_name("_".join(group.segments), fallback=group.package)
        field_name = group.client_class.removesuffix("Client")
        if field_counts[field_name] > 1:
            field_name = _go_exported("_".join(group.segments))
        facade_groups.append(RootFacadeGroup(group=group, import_alias=import_alias, field_name=field_name))
    return tuple(facade_groups)


def _root_package_name(module: str) -> str:
    if not module:
        return "client"
    return re.sub(r"[^0-9A-Za-z_]+", "_", module.rstrip("/").rsplit("/", 1)[-1]) or "client"


def _code_literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
