from __future__ import annotations

import os
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Set, Type, Union

from api_blueprint.engine.group import RouterGroup
from api_blueprint.engine.model import FieldWrappedModel, Model, iter_field_model_type, unwrap_model_type
from api_blueprint.engine.router import Router
from api_blueprint.engine.utils import is_parametrized, snake_to_pascal_case
from api_blueprint.engine.wrapper import NoneWrapper
from api_blueprint.writer.core.base import BaseBlueprint
from api_blueprint.writer.core.templates import render

from .naming import to_camel
from .protos import TypeScriptProto, TypeScriptProtoRegistry, TypeScriptResolvedType


class TypeScriptRoute:
    def __init__(self, router: Router, registry: TypeScriptProtoRegistry, *, route_prefix: str):
        self.router = router
        self.registry = registry
        self.route_prefix = route_prefix

        self.func_name = self._func_name()
        self.group_prefix = self._group_prefix()
        self.group_slug = self._group_slug()
        self.group_alias = self._group_alias()
        self.group_pascal = self._group_pascal()
        self.method_name = to_camel(self.func_name)
        self.url = router.url
        self.summary = router.extra.get("summary")
        self.description = router.extra.get("description")
        self.tags = router.tags
        self.deprecated = router.is_deprecated

        self.http_methods = [method for method in router.methods if method != "WS"]
        self.supports_ws = any(method == "WS" for method in router.methods)

        self.query_proto = self._ensure_model(router.req_query, "REQ", "QUERY")
        self.form_proto = self._ensure_model(router.req_form, "REQ", "FORM")
        self.json_proto = self._ensure_model(router.req_json, "REQ", "JSON")
        self.bin_proto = router.req_bin is not None

        self.response_media_type = router.rsp_media_type
        self.response_payload_proto = self._ensure_model(router.rsp_model, "RSP", "JSON")
        wrapper_cls = router.response_wrapper or NoneWrapper
        self.wrapper_proto = self.registry.ensure(wrapper_cls, tag="wrapper")
        self.response_alias = self._ensure_response_alias()

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

    def _func_name(self) -> str:
        if not self.router.leaf.strip("/"):
            return "Root"
        return snake_to_pascal_case(self.router.leaf, "", "Z")

    def _group_prefix(self) -> str:
        branch = (self.router.group.branch or "").strip("/")
        if branch:
            return re.sub(r"[^0-9A-Za-z]+", "_", branch).upper()
        root = (self.router.group.root or "").strip("/")
        if root:
            return re.sub(r"[^0-9A-Za-z]+", "_", root).upper()
        return "ROOT"

    def _group_slug(self) -> str:
        branch = (self.router.group.branch or "").strip("/")
        if branch:
            slug = re.sub(r"[^0-9A-Za-z]+", "_", branch.lower()) or "root"
        else:
            root = (self.router.group.root or "").strip("/")
            slug = "(root)" if root else "root"
        if slug == "shared":
            slug = "shared_group"
        return slug

    def _group_alias(self) -> str:
        branch = (self.router.group.branch or "").strip("/")
        if branch:
            alias = re.sub(r"[^0-9A-Za-z]+", "_", branch.lower()) or "root"
        else:
            root = (self.router.group.root or "").strip("/")
            alias = re.sub(r"[^0-9A-Za-z]+", "_", root.lower()) or "root" if root else "root"
        if alias == "shared":
            alias = "shared_group"
        return alias

    def _group_pascal(self) -> str:
        return snake_to_pascal_case(self.group_slug, "", "Group")

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
        module = self.group_slug if is_route_model else "shared"
        return self.registry.ensure(model, name=explicit, tag=tag, route=self.func_name, module=module)

    def _route_model_name(self, prefix: str, suffix: str) -> str:
        parts = [prefix, self.func_name]
        if suffix:
            parts.append(suffix)
        return "_".join(parts)

    def _type_expr(self, proto: Optional[TypeScriptProto]) -> str | None:
        if proto is None:
            return None
        namespace = "Models" if proto.module == self.group_slug else "Shared"
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
        return self.registry.register_alias(alias_base, alias_type, tag="route", route=self.func_name, module=self.group_slug)


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
    alias: str
    prefix: str
    routes: list[TypeScriptRoute] = field(default_factory=list)

    @property
    def client_class(self) -> str:
        base = snake_to_pascal_case(self.alias or "root", "", "Group")
        if not base.endswith("Client"):
            base += "Client"
        return base


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
                self._register_route(router)

    def _register_route(self, router: Router) -> None:
        self._register_common_models(router)
        ts_route = TypeScriptRoute(router, self.registry, route_prefix=self.package)
        self.routes.append(ts_route)
        group = self.groups.get(ts_route.group_slug)
        if group is None:
            group = TypeScriptViewGroup(slug=ts_route.group_slug, alias=ts_route.group_alias, prefix=ts_route.group_prefix)
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
                self.registry.ensure(nested, tag="shared")
            if getattr(model_cls, "__auto__", None) is False and not is_parametrized(model_cls):
                self.registry.ensure(model_cls, tag="shared")

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
        shared_models = [proto for proto in self.registry.filter(module="shared") if "wrapper" not in proto.tags]
        if shared_models:
            sections.append(("Shared Models", shared_models))
        wrappers = self.registry.filter(tag="wrapper", module="shared")
        if wrappers:
            sections.append(("Response Wrappers", wrappers))
        return sections

    def group_sections(self, module: str) -> list[tuple[str, list[TypeScriptProto]]]:
        protos = self.registry.filter(module=module)
        if not protos:
            return []
        return [("Route Contracts", protos)]

    def module_dirs(self, base_dir: Path) -> dict[str, Path]:
        dirs = {"shared": base_dir / "shared"}
        for slug in self.groups.keys():
            dirs[slug] = base_dir / slug
        return dirs

    def _relative_import_path(self, current_dir: Path, target_file: Path) -> str:
        rel = os.path.relpath(target_file.with_suffix(""), start=current_dir)
        return rel.replace("\\", "/")

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

    def gen(self) -> None:
        self.collect()
        base_dir = self.writer.working_dir / self.package
        base_dir.mkdir(parents=True, exist_ok=True)
        module_dirs = self.module_dirs(base_dir)

        shared_dir = module_dirs["shared"]
        shared_dir.mkdir(parents=True, exist_ok=True)
        shared_sections = self.shared_sections()
        shared_imports = self.build_imports("shared", module_dirs)
        shared_context = {"sections": shared_sections, "imports": shared_imports, "exports": []}
        for tmpl in ["gen_models.ts", "models.ts"]:
            with self.writer.write_file(shared_dir / tmpl, overwrite=tmpl.startswith("gen_")) as handle:
                if handle:
                    handle.write(render("typescript", tmpl, shared_context))

        for out_tmpl, tmpl in [("gen_client.ts", "gen_shared_client.ts"), ("client.ts", "client.ts")]:
            with self.writer.write_file(shared_dir / out_tmpl, overwrite=out_tmpl.startswith("gen_")) as handle:
                if handle:
                    handle.write(render("typescript", tmpl, {}))

        for tmpl in ["gen_index.ts", "index.ts"]:
            with self.writer.write_file(shared_dir / tmpl, overwrite=True) as handle:
                if handle:
                    handle.write(
                        render(
                            "typescript",
                            tmpl,
                            {
                                "client_class": None,
                                "extra_exports": ['export * from "./gen_client";'],
                            },
                        )
                    )

        for group in self.groups.values():
            group_dir = module_dirs[group.slug]
            group_dir.mkdir(parents=True, exist_ok=True)
            models_context = {
                "sections": self.group_sections(group.slug),
                "imports": self.build_imports(group.slug, module_dirs),
                "exports": [],
            }
            for tmpl in ["gen_models.ts", "models.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as handle:
                    if handle:
                        handle.write(render("typescript", tmpl, models_context))

            client_context = {"routes": group.routes, "writer": self.writer, "client_class": group.client_class}
            for tmpl in ["gen_client.ts", "client.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as handle:
                    if handle:
                        handle.write(render("typescript", tmpl, client_context))

            for tmpl in ["gen_index.ts", "index.ts"]:
                with self.writer.write_file(group_dir / tmpl, overwrite=tmpl.startswith("gen_")) as handle:
                    if handle:
                        handle.write(
                            render(
                                "typescript",
                                tmpl,
                                {
                                    "client_class": group.client_class,
                                    "extra_exports": [],
                                },
                            )
                        )

        exports = [{"alias": "Shared", "path": "./shared"}]
        second_exports: list[tuple[str, TypeScriptViewGroup]] = []
        seen_alias = set()
        for slug, group in self.groups.items():
            if slug != group.alias:
                second_exports.append((slug, group))
                continue
            alias = snake_to_pascal_case(group.alias, "", "Group")
            exports.append({"alias": alias, "path": f"./{slug}"})
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
            exports.append({"alias": alias, "path": f"./{slug}"})
            seen_alias.add(alias)

        exports = sorted(exports, key=lambda item: item["alias"])
        with self.writer.write_file(base_dir / "gen_index.ts", overwrite=True) as handle:
            if handle:
                handle.write(render("typescript", "gen_root_index.ts", {"modules": exports}))

        for out_tmpl, tmpl in [("gen_index.ts", "gen_root_index.ts"), ("index.ts", "index.ts")]:
            with self.writer.write_file(base_dir / out_tmpl, overwrite=out_tmpl.startswith("gen_")) as handle:
                if handle:
                    handle.write(render("typescript", tmpl, {"modules": exports}))
