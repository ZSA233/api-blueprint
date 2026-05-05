from __future__ import annotations

import os
import re
import shutil
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Set, Type, Union, TYPE_CHECKING

from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.model import FieldWrappedModel, Model, iter_field_model_type, unwrap_model_type
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import is_parametrized, snake_to_pascal_case
from api_blueprint.engine.wrapper import NoneWrapper
from api_blueprint.route_selection import matches_selection_rule
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.contracts import RouteContract, route_contract
from api_blueprint.writer.core.templates import render

from .naming import to_camel
from .protos import RUNTIME_MODULE, TypeScriptProto, TypeScriptProtoRegistry, TypeScriptResolvedType

if TYPE_CHECKING:
    from .writer import TypeScriptWriter

SHARED_MODULE = RUNTIME_MODULE


def _group_module_key(slug: str, *, root: bool = False) -> str:
    prefix = "root" if root else "group"
    return f"{prefix}:{slug}"


class TypeScriptRoute:
    def __init__(self, router: Router, registry: TypeScriptProtoRegistry, *, route_prefix: str):
        self.router = router
        self.registry = registry
        self.route_prefix = route_prefix
        self.contract: RouteContract = route_contract(router)
        branch = (router.group.branch or "").strip("/")

        self.func_name = self.contract.func_name
        self.group_prefix = self.contract.group_prefix
        self.group_slug = self.contract.group_slug
        self.group_path = "" if not branch else self.contract.group_slug
        self.group_alias = self.contract.group_alias
        self.group_pascal = self.contract.group_pascal
        self.method_name = self.contract.method_name
        self.group_module = _group_module_key(self.group_slug, root=not branch)
        self.url = router.url
        self.summary = router.extra.get("summary")
        self.description = router.extra.get("description")
        self.tags = router.tags
        self.deprecated = router.is_deprecated
        self.route_id = self.contract.route_id
        self.service_name = self.contract.service_name
        self.namespace = self.contract.namespace

        self.http_methods = list(self.contract.http_methods)
        self.supports_ws = self.contract.supports_ws

        self.query_proto = self._ensure_model(router.req_query, "REQ", "QUERY")
        self.form_proto = self._ensure_model(router.req_form, "REQ", "FORM")
        self.json_proto = self._ensure_model(router.req_json, "REQ", "JSON")
        self.bin_proto = router.req_bin is not None

        self.response_media_type = router.rsp_media_type
        self.response_payload_proto = self._ensure_model(router.rsp_model, "RSP", "JSON")
        wrapper_cls = router.response_wrapper or NoneWrapper
        self.wrapper_proto = self.registry.ensure(wrapper_cls, tag="wrapper")
        self.response_alias = self._ensure_response_alias()
        self.ws_recv_alias = self._ensure_ws_message_alias("WS", "RECV", router.recvs)
        self.ws_send_alias = self._ensure_ws_message_alias("WS", "SEND", router.sends)

    @property
    def http_method(self) -> str:
        if self.http_methods:
            return self.http_methods[0]
        if self.supports_ws:
            return "WS"
        return "GET"

    @property
    def has_body(self) -> bool:
        return bool(self.json_proto or self.form_proto or self.bin_proto)

    @property
    def query_type_expr(self) -> str | None:
        return self._type_expr(self.query_proto)

    @property
    def json_type_expr(self) -> str | None:
        return self._type_expr(self.json_proto)

    @property
    def form_type_expr(self) -> str | None:
        return self._type_expr(self.form_proto)

    @property
    def response_type_expr(self) -> str:
        return self._type_expr(self.response_alias) or "void"

    @property
    def response_type_name(self) -> str:
        return self.response_alias.name if self.response_alias else "void"

    def _ensure_model(self, model: Optional[Union[Type[Model], Model]], prefix: str, suffix: str) -> Optional[TypeScriptProto]:
        if model is None:
            return None
        auto_flag = getattr(model, "__auto__", False)
        is_route_model = auto_flag or isinstance(model, FieldWrappedModel)
        if is_route_model:
            explicit = self._route_model_name(prefix, suffix)
        else:
            explicit = getattr(model, "__name__", None) or self._route_model_name(prefix, suffix)
        tag = "route" if is_route_model else "shared"
        module = self.group_slug if is_route_model else SHARED_MODULE
        if tag == "route":
            module = self.group_module
        return self.registry.ensure(model, name=explicit, tag=tag, route=self.func_name, module=module)

    def _route_model_name(self, prefix: str, suffix: str) -> str:
        parts = [prefix, self.func_name]
        if suffix:
            parts.append(suffix)
        return "_".join(parts)

    def _type_expr(self, proto: Optional[TypeScriptProto]) -> str | None:
        if proto is None:
            return None
        namespace = "Models" if proto.module == self.group_module else "Shared"
        return f"{namespace}.{proto.name}"

    def _ensure_response_alias(self) -> Optional[TypeScriptProto]:
        alias_base = self._route_model_name("RSP", "")
        if self.response_media_type != "application/json":
            alias_type = TypeScriptResolvedType("string")
        else:
            payload_proto = self.response_payload_proto
            payload_type = "void"
            payload_deps: set[TypeScriptProto] = set()
            if payload_proto:
                payload_type = payload_proto.name
                payload_deps.add(payload_proto)

            alias_text = payload_type
            deps = set(payload_deps)
            if self.wrapper_proto and self.wrapper_proto.fields:
                alias_text = self.wrapper_proto.type_reference([payload_type])
                deps.add(self.wrapper_proto)
            alias_type = TypeScriptResolvedType(alias_text, deps)
        return self.registry.register_alias(alias_base, alias_type, tag="route", route=self.func_name, module=self.group_module)

    @property
    def ws_recv_type_expr(self) -> str:
        return self._type_expr(self.ws_recv_alias) or "unknown"

    @property
    def ws_send_type_expr(self) -> str:
        return self._type_expr(self.ws_send_alias) or "unknown"

    @property
    def connect_method_name(self) -> str:
        if self.contract.ws is None:
            return "connect"
        return to_camel(self.contract.ws.connect_method)

    @property
    def connect_raw_method_name(self) -> str:
        if self.contract.ws is None:
            return "connectRaw"
        return to_camel(self.contract.ws.connect_raw_method)

    def _ensure_ws_message_alias(
        self,
        prefix: str,
        suffix: str,
        models: list[Union[Type[Model], Model]],
    ) -> Optional[TypeScriptProto]:
        if not models:
            return None

        deps: set[TypeScriptProto] = set()
        protos: list[TypeScriptProto] = []
        for index, model in enumerate(models, start=1):
            explicit = self._route_model_name(prefix, suffix if len(models) == 1 else f"{suffix}{index}")
            proto = self.registry.ensure(model, name=explicit, tag="route", route=self.func_name, module=self.group_module)
            if proto is None:
                continue
            deps.add(proto)
            protos.append(proto)

        if not protos:
            return None
        if len(protos) == 1:
            return protos[0]

        return self.registry.register_alias(
            self._route_model_name(prefix, suffix),
            TypeScriptResolvedType(" | ".join(proto.name for proto in protos), deps),
            tag="route",
            route=self.func_name,
            module=self.group_module,
        )


class TypeScriptRouterGroup:
    def __init__(self, bp: "TypeScriptBlueprint", group: RouterGroup):
        self.bp = bp
        self.group = group

    @property
    def routers(self) -> list[Router]:
        return list(self.group)


@dataclass
class TypeScriptViewGroup:
    slug: str
    path: str
    alias: str
    prefix: str
    module_key: str
    routes: list[TypeScriptRoute] = field(default_factory=list)

    @property
    def client_class(self) -> str:
        base = snake_to_pascal_case(self.alias or "root", "", "Group")
        if not base.endswith("Client"):
            base += "Client"
        return base


@dataclass(frozen=True)
class TypeScriptClientFactoryEntry:
    identifier: str
    class_name: str
    import_path: str


@dataclass(frozen=True)
class TypeScriptOverlayFactoryEntry:
    identifier: str
    client_type_name: str
    type_import_path: str
    factory_import_path: str
    factory_alias: str


class TypeScriptBlueprint(BaseBlueprint["TypeScriptWriter"]):
    def __init__(self, writer: "TypeScriptWriter", bp):
        super().__init__(writer, bp)
        self.router_groups: Optional[list[TypeScriptRouterGroup]] = None
        self.registry = TypeScriptProtoRegistry()
        self.routes: list[TypeScriptRoute] = []
        self.groups: "OrderedDict[str, TypeScriptViewGroup]" = OrderedDict()

    @property
    def package(self) -> str:
        return self.bp.root.strip("/") or "root"

    def get_router_groups(self) -> list[TypeScriptRouterGroup]:
        if self.router_groups is None:
            seen: Set[RouterGroup] = set()
            groups = []
            for group, _router in self.iter_router():
                if group in seen:
                    continue
                seen.add(group)
                groups.append(TypeScriptRouterGroup(self, group))
            self.router_groups = groups
        return self.router_groups

    def collect(self) -> None:
        self.routes = []
        self.groups = OrderedDict()
        for group in self.get_router_groups():
            for router in group.routers:
                if self.writer.overlay_name is not None:
                    route_name = route_contract(router).func_name
                    if self.writer.include and not any(
                        matches_selection_rule(router, rule, route_name=route_name, label="[gen_wails]")
                        for rule in self.writer.include
                    ):
                        continue
                    if any(
                        matches_selection_rule(router, rule, route_name=route_name, label="[gen_wails]")
                        for rule in self.writer.exclude
                    ):
                        continue
                self._register_route(router)

    def _register_route(self, router: Router) -> None:
        self._register_common_models(router)
        ts_route = TypeScriptRoute(router, self.registry, route_prefix=self.package)
        self.routes.append(ts_route)
        group = self.groups.get(ts_route.group_slug)
        if group is None:
            group = TypeScriptViewGroup(
                slug=ts_route.group_slug,
                path=ts_route.group_path,
                alias=ts_route.group_alias,
                prefix=ts_route.group_prefix,
                module_key=ts_route.group_module,
            )
            self.groups[ts_route.group_slug] = group
        group.routes.append(ts_route)

    def _register_common_models(self, router: Router) -> None:
        def collect(model: Optional[Union[Type[Model], Model]]):
            if model is None:
                return
            model_cls = unwrap_model_type(model)
            for nested in iter_field_model_type(model):
                if nested is model_cls:
                    continue
                self.registry.ensure(nested, tag="shared", module=SHARED_MODULE)
            if getattr(model_cls, "__auto__", None) is False and not is_parametrized(model_cls):
                self.registry.ensure(model_cls, tag="shared", module=SHARED_MODULE)

        collect(router.req_query)
        collect(router.req_form)
        collect(router.req_json)
        collect(router.rsp_model)
        for recv in router.recvs:
            collect(recv)
        for send in router.sends:
            collect(send)

    def shared_sections(self) -> list[tuple[str, list[TypeScriptProto]]]:
        sections = []
        shared_models = [proto for proto in self.registry.filter(module=SHARED_MODULE) if "wrapper" not in proto.tags]
        if shared_models:
            sections.append(("Shared Models", shared_models))
        wrappers = self.registry.filter(tag="wrapper", module=SHARED_MODULE)
        if wrappers:
            sections.append(("Response Wrappers", wrappers))
        return sections

    def group_sections(self, module: str) -> list[tuple[str, list[TypeScriptProto]]]:
        protos = self.registry.filter(module=module)
        if not protos:
            return []
        return [("Route Contracts", protos)]

    def module_dirs(self, root_dir: Path) -> dict[str, Path]:
        route_root_dir = root_dir / self.writer.routes_dir_name / self.package
        dirs = {SHARED_MODULE: root_dir / self.writer.runtime_dir_name}
        for group in self.groups.values():
            dirs[group.module_key] = route_root_dir / group.path if group.path else route_root_dir
        return dirs

    def _relative_import_path(self, current_dir: Path, target_file: Path) -> str:
        rel = os.path.relpath(target_file.with_suffix(""), start=current_dir)
        rel = rel.replace("\\", "/")
        if not rel.startswith("."):
            rel = f"./{rel}"
        return rel

    def build_imports(self, module: str, module_dirs: dict[str, Path]) -> list[dict[str, Any]]:
        current_dir = module_dirs[module]
        protos = self.registry.filter(module=module)
        deps_map: dict[str, set[str]] = OrderedDict()
        for proto in protos:
            for dep in proto.dependencies():
                dep_module = dep.module
                if dep_module == module or dep_module not in module_dirs:
                    continue
                path = self._relative_import_path(current_dir, module_dirs[dep_module] / "models.ts")
                deps_map.setdefault(path, set()).add(dep.name)
        return [{"path": path, "names": sorted(names)} for path, names in sorted(deps_map.items(), key=lambda item: item[0])]

    def render_reexport(self, current_dir: Path, target_file: Path) -> str:
        target = self._relative_import_path(current_dir, target_file)
        return (
            "/* eslint-disable */\n"
            "// Code generated by api-blueprint (TypeScript); DO NOT EDIT.\n\n"
            f'export * from "{target}";\n'
        )

    def render_generated_export(self, target: str) -> str:
        return (
            "/* eslint-disable */\n"
            "// Code generated by api-blueprint (TypeScript); DO NOT EDIT.\n\n"
            f'export * from "{target}";\n'
        )

    def render_passthrough(self, target: str) -> str:
        return f'\n\nexport * from "{target}";\n'

    def transport_root_exports(self, root_dir: Path, *extra_transports: str) -> list[dict[str, str]]:
        transports_dir = root_dir / self.writer.transports_dir_name
        names = set(extra_transports)
        if transports_dir.exists():
            names.update(path.name for path in transports_dir.iterdir() if path.is_dir())
        exports: list[dict[str, str]] = []
        for name in sorted(names):
            exports.append({"alias": snake_to_pascal_case(name, "", "Transport"), "path": f"./{name}"})
        return exports

    def write_transports_index(self, root_dir: Path, *extra_transports: str) -> None:
        transports_dir = root_dir / self.writer.transports_dir_name
        transports_dir.mkdir(parents=True, exist_ok=True)
        exports = self.transport_root_exports(root_dir, *extra_transports)
        with self.writer.write_file(transports_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                handle.write(render(self.writer.template_lang, "gen_root_index.ts", {"modules": exports, "extra_exports": []}))
        with self.writer.write_file(transports_dir / "index.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_index"))

    def write_root_index(self, root_dir: Path) -> None:
        root_exports = [
            {"alias": "Runtime", "path": f"./{self.writer.runtime_dir_name}"},
            {"alias": "Routes", "path": f"./{self.writer.routes_dir_name}"},
        ]
        transports_dir = root_dir / self.writer.transports_dir_name
        if transports_dir.exists() and any(path.is_dir() for path in transports_dir.iterdir()):
            root_exports.append({"alias": "Transports", "path": f"./{self.writer.transports_dir_name}"})
        with self.writer.write_file(root_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                handle.write(render(self.writer.template_lang, "gen_root_index.ts", {"modules": root_exports, "extra_exports": []}))
        with self.writer.write_file(root_dir / "index.ts", overwrite=False) as handle:
            if handle:
                handle.write(render(self.writer.template_lang, "index.ts", {"modules": root_exports}))

    def factory_entries(self, module_dirs: dict[str, Path]) -> list[TypeScriptClientFactoryEntry]:
        shared_dir = module_dirs[SHARED_MODULE]
        entries: list[TypeScriptClientFactoryEntry] = []
        seen_identifiers: set[str] = set()
        for group in self.groups.values():
            base_identifier = to_camel(group.client_class)
            identifier = base_identifier
            if identifier in seen_identifiers:
                for index in range(1, 100):
                    candidate = f"{base_identifier}{index}"
                    if candidate not in seen_identifiers:
                        identifier = candidate
                        break
                else:
                    raise RuntimeError(f"Failed to generate unique client factory identifier for group {group.alias}")
            seen_identifiers.add(identifier)
            entries.append(
                TypeScriptClientFactoryEntry(
                    identifier=identifier,
                    class_name=group.client_class,
                    import_path=self._relative_import_path(shared_dir, module_dirs[group.module_key] / "client.ts"),
                )
            )
        return sorted(entries, key=lambda entry: entry.identifier)

    def facade_factory_entries(self, module_dirs: dict[str, Path], current_dir: Path) -> list[TypeScriptClientFactoryEntry]:
        entries: list[TypeScriptClientFactoryEntry] = []
        seen_identifiers: set[str] = set()
        for group in self.groups.values():
            base_identifier = to_camel(group.client_class)
            identifier = base_identifier
            if identifier in seen_identifiers:
                for index in range(1, 100):
                    candidate = f"{base_identifier}{index}"
                    if candidate not in seen_identifiers:
                        identifier = candidate
                        break
                else:
                    raise RuntimeError(f"Failed to generate unique client factory identifier for group {group.alias}")
            seen_identifiers.add(identifier)
            entries.append(
                TypeScriptClientFactoryEntry(
                    identifier=identifier,
                    class_name=group.client_class,
                    import_path=self._relative_import_path(current_dir, module_dirs[group.module_key] / "client.ts"),
                )
            )
        return sorted(entries, key=lambda entry: entry.identifier)

    def overlay_factory_entries(self, module_dirs: dict[str, Path], overlay_dir_name: str) -> list[TypeScriptOverlayFactoryEntry]:
        overlay_root_dir = (
            self.writer.working_dir
            / self.package
            / self.writer.transports_dir_name
            / overlay_dir_name
            / self.package
        )
        entries: list[TypeScriptOverlayFactoryEntry] = []
        seen_identifiers: set[str] = set()
        for group in self.groups.values():
            base_identifier = to_camel(group.client_class)
            identifier = base_identifier
            if identifier in seen_identifiers:
                for index in range(1, 100):
                    candidate = f"{base_identifier}{index}"
                    if candidate not in seen_identifiers:
                        identifier = candidate
                        break
                else:
                    raise RuntimeError(f"Failed to generate unique overlay factory identifier for group {group.alias}")
            seen_identifiers.add(identifier)
            group_dir = overlay_root_dir / group.path if group.path else overlay_root_dir
            overlay_client_file = group_dir / "client.ts"
            entries.append(
                TypeScriptOverlayFactoryEntry(
                    identifier=identifier,
                    client_type_name=group.client_class,
                    type_import_path=self._relative_import_path(overlay_root_dir, overlay_client_file),
                    factory_import_path=self._relative_import_path(overlay_root_dir, overlay_client_file),
                    factory_alias=f"create{group.client_class}",
                )
            )
        return sorted(entries, key=lambda entry: entry.identifier)

    def gen_overlay(self) -> None:
        root_dir = self.writer.working_dir / self.package
        module_dirs = self.module_dirs(root_dir)
        overlay_name = self.writer.overlay_name
        if overlay_name is None:
            raise RuntimeError("overlay_name is required for TypeScript overlay generation")

        transport_dir = root_dir / self.writer.transports_dir_name / self.writer.overlay_dir_name
        transport_dir.mkdir(parents=True, exist_ok=True)
        with self.writer.write_file(transport_dir / "gen_transport.ts", overwrite=True) as handle:
            if handle:
                handle.write(
                    render(
                        self.writer.template_lang,
                        "gen_transport.ts",
                        {
                            "writer": self.writer,
                            "client_api_path": self._relative_import_path(transport_dir, module_dirs[SHARED_MODULE] / "client.ts"),
                        },
                    )
                )
        with self.writer.write_file(transport_dir / "transport.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_transport"))
        with self.writer.write_file(transport_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                handle.write(self.render_generated_export("./transport"))
        with self.writer.write_file(transport_dir / "index.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_index"))

        overlay_root_dir = transport_dir / self.package
        overlay_root_dir.mkdir(parents=True, exist_ok=True)
        for group in self.groups.values():
            parent_group_dir = module_dirs[group.module_key]
            group_dir = overlay_root_dir / group.path if group.path else overlay_root_dir
            group_dir.mkdir(parents=True, exist_ok=True)

            client_context = {
                "routes": group.routes,
                "writer": self.writer,
                "client_class": group.client_class,
                "shared_client_api_path": self._relative_import_path(group_dir, module_dirs[SHARED_MODULE] / "client.ts"),
                "transport_path": self._relative_import_path(group_dir, transport_dir / "transport.ts"),
                "shared_client_path": self._relative_import_path(group_dir, parent_group_dir / "client.ts"),
                "raw_ws_method_names": [route.connect_raw_method_name for route in group.routes if route.supports_ws],
            }
            with self.writer.write_file(group_dir / "gen_client.ts", overwrite=True) as handle:
                if handle:
                    handle.write(render(self.writer.template_lang, "gen_client_overlay.ts", client_context))
            with self.writer.write_file(group_dir / "client.ts", overwrite=False) as handle:
                if handle:
                    handle.write(self.render_passthrough("./gen_client"))
            with self.writer.write_file(group_dir / "gen_index.ts", overwrite=True) as handle:
                if handle:
                    handle.write(self.render_generated_export("./client"))
            with self.writer.write_file(group_dir / "index.ts", overwrite=False) as handle:
                if handle:
                    handle.write(self.render_passthrough("./gen_index"))

        root_overlay_dir = overlay_root_dir
        root_overlay_dir.mkdir(parents=True, exist_ok=True)
        exports: list[dict[str, str]] = []
        second_exports: list[tuple[str, TypeScriptViewGroup]] = []
        seen_alias = set()
        for slug, group in self.groups.items():
            path = "." if not group.path else f"./{group.path}"
            if group.path and slug != group.alias:
                second_exports.append((slug, group))
                continue
            alias = snake_to_pascal_case(group.alias, "", "Group")
            exports.append({"alias": alias, "path": path if path != "." else "./client"})
            seen_alias.add(alias)

        for slug, group in second_exports:
            alias = snake_to_pascal_case(group.alias, "", "Group")
            if alias in seen_alias:
                for index in range(1, 100):
                    alias = snake_to_pascal_case(f"{group.alias}{index}", "", "Group")
                    if alias not in seen_alias:
                        break
                else:
                    raise RuntimeError(f"Failed to generate unique alias for group {group.alias}")
            exports.append({"alias": alias, "path": f"./{group.path}"})
            seen_alias.add(alias)

        exports = sorted(exports, key=lambda item: item["alias"])
        overlay_factory_entries = self.overlay_factory_entries(module_dirs, self.writer.overlay_dir_name)
        with self.writer.write_file(root_overlay_dir / "gen_factory.ts", overwrite=True) as handle:
            if handle:
                handle.write(
                    render(
                        self.writer.template_lang,
                        "gen_overlay_factory.ts",
                        {
                            "writer": self.writer,
                            "client_api_path": self._relative_import_path(root_overlay_dir, module_dirs[SHARED_MODULE] / "client.ts"),
                            "clients": overlay_factory_entries,
                        },
                    )
                )
        with self.writer.write_file(root_overlay_dir / "factory.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_factory"))
        with self.writer.write_file(root_overlay_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                extra_exports = ['export * from "./factory";']
                if any(not group.path for group in self.groups.values()):
                    extra_exports.insert(0, 'export * from "./client";')
                handle.write(
                    render(
                        self.writer.template_lang,
                        "gen_root_index.ts",
                        {
                            "modules": [
                                export
                                for export in exports
                                if export["path"] != "./client"
                            ],
                            "extra_exports": extra_exports,
                        },
                    )
                )
        with self.writer.write_file(root_overlay_dir / "index.ts", overwrite=False) as handle:
            if handle:
                handle.write(render(self.writer.template_lang, "index.ts", {"modules": exports}))

        with self.writer.write_file(transport_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                handle.write(
                    render(
                        self.writer.template_lang,
                        "gen_root_index.ts",
                        {
                            "modules": [{"alias": snake_to_pascal_case(self.package, "", "Group"), "path": f"./{self.package}"}],
                            "extra_exports": ['export * from "./transport";'],
                        },
                    )
                )
        self.write_transports_index(root_dir, self.writer.overlay_dir_name)
        self.write_root_index(root_dir)

    def cleanup_unselected_overlay(self) -> None:
        root_dir = self.writer.working_dir / self.package
        transports_dir = root_dir / self.writer.transports_dir_name
        if self.writer.overlay_name is not None:
            overlay_dir = transports_dir / self.writer.overlay_dir_name
            if overlay_dir.exists():
                shutil.rmtree(overlay_dir)
        if not root_dir.exists() or not transports_dir.exists():
            return
        if any(path.is_dir() for path in transports_dir.iterdir()):
            self.write_transports_index(root_dir)
        else:
            for index_file in ("gen_index.ts", "index.ts"):
                stale_index = transports_dir / index_file
                if stale_index.exists():
                    stale_index.unlink()
            try:
                transports_dir.rmdir()
            except OSError:
                pass
        self.write_root_index(root_dir)

    def gen_http_facade(self, root_dir: Path, module_dirs: dict[str, Path]) -> None:
        http_dir = root_dir / self.writer.transports_dir_name / "http"
        http_dir.mkdir(parents=True, exist_ok=True)
        with self.writer.write_file(http_dir / "gen_transport.ts", overwrite=True) as handle:
            if handle:
                handle.write(
                    render(
                        self.writer.template_lang,
                        "gen_transport.ts",
                        {
                            "writer": self.writer,
                            "client_api_path": self._relative_import_path(http_dir, module_dirs[SHARED_MODULE] / "client.ts"),
                        },
                    )
                )
        with self.writer.write_file(http_dir / "transport.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_transport"))

        facade_dir = http_dir / self.package
        facade_dir.mkdir(parents=True, exist_ok=True)
        clients = self.facade_factory_entries(module_dirs, facade_dir)
        with self.writer.write_file(facade_dir / "gen_factory.ts", overwrite=True) as handle:
            if handle:
                handle.write(
                    render(
                        self.writer.template_lang,
                        "gen_http_factory.ts",
                        {
                            "writer": self.writer,
                            "client_api_path": self._relative_import_path(facade_dir, module_dirs[SHARED_MODULE] / "client.ts"),
                            "transport_path": self._relative_import_path(facade_dir, http_dir / "transport.ts"),
                            "clients": clients,
                        },
                    )
                )
        with self.writer.write_file(facade_dir / "factory.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_factory"))
        with self.writer.write_file(facade_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                handle.write(
                    render(
                        self.writer.template_lang,
                        "gen_root_index.ts",
                        {
                            "modules": [],
                            "extra_exports": [
                                'export * from "./factory";',
                            ],
                        },
                    )
                )
        with self.writer.write_file(facade_dir / "index.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_index"))

        with self.writer.write_file(http_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                handle.write(
                    render(
                        self.writer.template_lang,
                        "gen_root_index.ts",
                        {
                            "modules": [{"alias": snake_to_pascal_case(self.package, "", "Group"), "path": f"./{self.package}"}],
                            "extra_exports": ['export * from "./transport";'],
                        },
                    )
                )
        with self.writer.write_file(http_dir / "index.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_index"))

    def gen(self) -> None:
        self.collect()
        self.cleanup_legacy_root_layout()
        if self.writer.overlay_name is not None:
            if not self.routes:
                self.cleanup_unselected_overlay()
                return
            self.gen_overlay()
            return

        root_dir = self.writer.working_dir / self.package
        root_dir.mkdir(parents=True, exist_ok=True)
        module_dirs = self.module_dirs(root_dir)

        shared_dir = module_dirs[SHARED_MODULE]
        shared_dir.mkdir(parents=True, exist_ok=True)
        for stale_runtime_file in ("gen_factory.ts", "factory.ts", "gen_transport.ts", "transport.ts"):
            stale_path = shared_dir / stale_runtime_file
            if stale_path.exists():
                stale_path.unlink()
        shared_sections = self.shared_sections()
        shared_imports = self.build_imports(SHARED_MODULE, module_dirs)
        shared_context = {"sections": shared_sections, "imports": shared_imports, "exports": []}
        for tmpl in ["gen_models.ts", "models.ts"]:
            with self.writer.write_file(shared_dir / tmpl, overwrite=tmpl.startswith("gen_")) as handle:
                if handle:
                    handle.write(render(self.writer.template_lang, tmpl, shared_context))

        for out_tmpl, tmpl in [
            ("gen_client.ts", "gen_shared_client.ts"),
            ("client.ts", "client.ts"),
        ]:
            with self.writer.write_file(shared_dir / out_tmpl, overwrite=out_tmpl.startswith("gen_")) as handle:
                if handle:
                    context = {
                        "writer": self.writer,
                        "client_api_path": "./client",
                        "clients": self.factory_entries(module_dirs),
                    }
                    handle.write(render(self.writer.template_lang, tmpl, context))

        for tmpl in ["gen_index.ts", "index.ts"]:
            with self.writer.write_file(shared_dir / tmpl, overwrite=True) as handle:
                if handle:
                    handle.write(
                        render(
                            self.writer.template_lang,
                            tmpl,
                            {
                                "client_class": None,
                                "extra_exports": [
                                    'export * from "./gen_client";',
                                ],
                            },
                        )
                    )

        for group in self.groups.values():
            group_dir = module_dirs[group.module_key]
            group_dir.mkdir(parents=True, exist_ok=True)
            models_context = {
                "sections": self.group_sections(group.module_key),
                "imports": self.build_imports(group.module_key, module_dirs),
                "exports": [],
            }
            for tmpl in ["gen_models.ts", "models.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as handle:
                    if handle:
                        handle.write(render(self.writer.template_lang, tmpl, models_context))

            client_context = {
                "routes": group.routes,
                "writer": self.writer,
                "client_class": group.client_class,
                "shared_models_path": self._relative_import_path(group_dir, shared_dir / "models.ts"),
                "shared_client_path": self._relative_import_path(group_dir, shared_dir / "client.ts"),
            }
            for tmpl in ["gen_client.ts", "client.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as handle:
                    if handle:
                        handle.write(render(self.writer.template_lang, tmpl, client_context))

            for tmpl in ["gen_index.ts", "index.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as handle:
                    if handle:
                        handle.write(
                            render(
                                self.writer.template_lang,
                                tmpl,
                                {
                                    "client_class": group.client_class,
                                    "extra_exports": [],
                                },
                            )
                        )

        exports: list[dict[str, str]] = []
        second_exports: list[tuple[str, TypeScriptViewGroup]] = []
        seen_alias = set()
        for slug, group in self.groups.items():
            path = f"./{self.package}" if not group.path else f"./{self.package}/{group.path}"
            if group.path and slug != group.alias:
                second_exports.append((slug, group))
                continue
            alias = snake_to_pascal_case(group.alias, "", "Group")
            exports.append({"alias": alias, "path": path})
            seen_alias.add(alias)

        for slug, group in second_exports:
            alias = snake_to_pascal_case(group.alias, "", "Group")
            if alias in seen_alias:
                for index in range(1, 100):
                    alias = snake_to_pascal_case(f"{group.alias}{index}", "", "Group")
                    if alias not in seen_alias:
                        break
                else:
                    raise RuntimeError(f"Failed to generate unique alias for group {group.alias}")
            exports.append({"alias": alias, "path": f"./{self.package}/{group.path}"})
            seen_alias.add(alias)

        exports = sorted(exports, key=lambda item: item["alias"])
        routes_dir = root_dir / self.writer.routes_dir_name
        routes_dir.mkdir(parents=True, exist_ok=True)
        with self.writer.write_file(routes_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                handle.write(render(self.writer.template_lang, "gen_root_index.ts", {"modules": exports, "extra_exports": []}))
        with self.writer.write_file(routes_dir / "index.ts", overwrite=False) as handle:
            if handle:
                handle.write(self.render_passthrough("./gen_index"))

        if self.writer.emit_http_facade:
            self.gen_http_facade(root_dir, module_dirs)
            self.write_transports_index(root_dir, "http")
        else:
            http_dir = root_dir / self.writer.transports_dir_name / "http"
            if http_dir.exists():
                shutil.rmtree(http_dir)

        self.write_root_index(root_dir)

    def cleanup_legacy_root_layout(self) -> None:
        root_dir = self.writer.working_dir / self.package
        if not root_dir.exists():
            return
        legacy_shared = root_dir / "(shared)"
        if legacy_shared.exists():
            shutil.rmtree(legacy_shared)
        legacy_core = root_dir / "core"
        if legacy_core.exists():
            shutil.rmtree(legacy_core)
        for legacy_transport in ("http", "wailsv2", "wailsv3"):
            legacy_dir = root_dir / legacy_transport
            if legacy_dir.exists():
                shutil.rmtree(legacy_dir)
        for group in self.groups.values():
            legacy_group = root_dir / group.slug
            if legacy_group.exists():
                shutil.rmtree(legacy_group)
            legacy_root_group = root_dir / self.writer.routes_dir_name / "_root"
            if legacy_root_group.exists():
                shutil.rmtree(legacy_root_group)
