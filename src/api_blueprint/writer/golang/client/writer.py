from __future__ import annotations

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
from api_blueprint.writer.core.templates import render
from api_blueprint.writer.golang.message_files import cleanup_stale_go_message_files, plan_go_message_files

from .model_decls import (
    GoClientTypeNames,
    go_code_literal,
    go_exported,
    go_type_name,
    group_model_declarations,
    runtime_model_declarations,
    variant_alias_name,
)
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
        type_names = GoClientTypeNames(schemas)
        groups = build_go_client_groups(routes, services)

        route_errors = route_api_errors_from_manifest(
            manifest,
            route_ids=[str(route.get("id") or "") for route in routes],
        )
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
        type_names: GoClientTypeNames,
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
                {"declarations": runtime_model_declarations(schemas, type_names)},
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
        type_names: GoClientTypeNames,
    ) -> None:
        route_dir = Path("routes").joinpath(*group.segments)
        model_declarations = group_model_declarations(group, schemas, type_names)
        self._write_generated(
            route_dir / "gen_types.go",
            render(
                "golang",
                "gen_types.go",
                {
                    "group": group,
                    "declarations": model_declarations,
                    "has_runtime_import": any(decl.uses_runtime_import for decl in model_declarations),
                    "runtime_import": self.runtime_import,
                },
                "client/routes",
            ),
        )
        self._cleanup_stale_generated(self.working_dir / route_dir / "gen_models.go")
        message_files = plan_go_message_files(_message_unions(group, type_names), _message_cases(group, type_names))
        cleanup_stale_go_message_files(
            self.working_dir / route_dir,
            keep={message_file.filename for message_file in message_files},
        )
        for message_file in message_files:
            self._write_generated(
                route_dir / message_file.filename,
                render(
                    "golang",
                    message_file.template_name,
                    {
                        **message_file.context,
                        "generated_label": "Go client",
                        "package_name": group.package,
                    },
                    "message",
                ),
            )
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
        base_url_code = self.base_url_expr if self.base_url_expr is not None else go_code_literal(self.base_url)
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


def _message_unions(group: GoClientGroup, type_names: GoClientTypeNames) -> list[dict[str, Any]]:
    return [
        {
            "name": helper.name,
            "variants": [
                _message_variant(helper.name, variant.key, variant.model, type_names)
                for variant in helper.variants
            ],
        }
        for helper in group.message_helpers()
    ]


def _message_cases(group: GoClientGroup, type_names: GoClientTypeNames) -> list[dict[str, Any]]:
    cases = []
    for helper in group.message_helpers():
        variants = [
            _message_variant(helper.name, variant.key, variant.model, type_names)
            for variant in helper.variants
        ]
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


def _message_variant(message_name: str, key: str, model: str, type_names: GoClientTypeNames) -> dict[str, str]:
    variant_name = go_exported(key)
    return {
        "key": key,
        "name": variant_name,
        "const": f"{message_name}Type{variant_name}",
        "ctor": f"New{message_name}{variant_name}",
        "decode": f"Decode{variant_name}",
        "data_type": variant_alias_name(message_name, key),
    }


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
        return f"*{go_type_name(str(route.response_binary_schema.get('name') or 'Packet'))}"
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
    if isinstance(route.request.get("path_model"), str):
        params.append(f"path {route.path_type}")
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
    if isinstance(route.request.get("path_model"), str):
        fields.append(("PathParams", "path"))
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
    fields.append(("BodyKind", f"runtime.RequestBodyKind({go_code_literal(route.body_kind)})"))
    fields.append(("ResponseKind", f"runtime.ResponseKind({go_code_literal(route.response_kind)})"))
    return fields


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
            field_name = go_exported("_".join(group.segments))
        facade_groups.append(RootFacadeGroup(group=group, import_alias=import_alias, field_name=field_name))
    return tuple(facade_groups)


def _root_package_name(module: str) -> str:
    if not module:
        return "client"
    return re.sub(r"[^0-9A-Za-z_]+", "_", module.rstrip("/").rsplit("/", 1)[-1]) or "client"
