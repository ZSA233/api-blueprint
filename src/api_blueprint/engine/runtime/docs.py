from __future__ import annotations

import copy
import enum
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Protocol

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.routing import BaseRoute

from api_blueprint.engine.connection import ConnectionKind, MessageContract, ModelRef
from api_blueprint.engine.runtime.protocol_docs import (
    ProtocolDocsPlugin,
    ProtocolDocsPluginFn,
    apply_protocol_docs_plugins,
    load_protocol_docs_plugins,
)
from api_blueprint.engine.schema import iter_enum_classes
from api_blueprint.engine.schema.enum_metadata import enum_value_metadata

if TYPE_CHECKING:
    from api_blueprint.engine.blueprint.router import Router


_DOCS_INSTALLED = "api_blueprint_docs_installed"
_DOCS_GZIP_INSTALLED = "api_blueprint_docs_gzip_installed"
_DOCS_ROUTES = "api_blueprint_docs_routes"
_DOCS_CACHE = "api_blueprint_docs_openapi_cache"
_DOCS_ENUMS = "api_blueprint_docs_enums"
_DOCS_SCHEMAS = "api_blueprint_docs_schemas"
_DOCS_SCHEMA_CONTEXTS = "api_blueprint_docs_schema_contexts"
_DOCS_PROTOCOL_PLUGINS = "api_blueprint_docs_protocol_plugins"
_DOCS_OPENAPI_WRAPPED = "api_blueprint_docs_openapi_wrapped"
_DOCS_VERSION = "api_blueprint_docs_version"

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
_HASHED_SCHEMA_NAME_RE = re.compile(r"__[0-9a-f]{8,}$")
_OPENAPI_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


class DocsRouteContract(Protocol):
    route_id: str
    group_alias: str
    func_name: str
    http_methods: tuple[str, ...]


@dataclass(frozen=True)
class DocsFilter:
    route_ids: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.route_ids or self.groups or self.tags or self.kinds)

    @property
    def cache_key(self) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        return (
            tuple(sorted(self.route_ids)),
            tuple(sorted(self.groups)),
            tuple(sorted(self.tags)),
            tuple(sorted(self.kinds)),
        )


@dataclass(frozen=True)
class ProtocolFilter:
    route_ids: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ()
    directions: tuple[str, ...] = ()
    ops: tuple[str, ...] = ()

    @property
    def has_message_filters(self) -> bool:
        return bool(self.directions or self.ops)


def ensure_docs_gzip(app: FastAPI) -> None:
    if getattr(app.state, _DOCS_GZIP_INSTALLED, False):
        return
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    setattr(app.state, _DOCS_GZIP_INSTALLED, True)


def configure_protocol_docs_plugins(app: FastAPI, plugin_specs: list[str] | tuple[str, ...]) -> None:
    set_protocol_docs_plugins(app, load_protocol_docs_plugins(plugin_specs))


def set_protocol_docs_plugins(
    app: FastAPI,
    plugins: tuple[ProtocolDocsPlugin | ProtocolDocsPluginFn, ...] | list[ProtocolDocsPlugin | ProtocolDocsPluginFn],
) -> None:
    setattr(app.state, _DOCS_PROTOCOL_PLUGINS, tuple(plugins))


def install_api_blueprint_docs(app: FastAPI) -> None:
    if getattr(app.state, _DOCS_INSTALLED, False):
        return
    setattr(app.state, _DOCS_INSTALLED, True)

    @app.get("/", include_in_schema=False)
    async def api_blueprint_docs_home(request: Request):
        return _docs_center_response(request, app)

    @app.get("/docs", include_in_schema=False)
    async def api_blueprint_docs(request: Request):
        return _docs_center_response(request, app)

    @app.get("/docs/index.json", include_in_schema=False)
    async def api_blueprint_docs_index() -> dict[str, Any]:
        return docs_index(app)

    @app.get("/docs/protocol.json", include_in_schema=False)
    async def api_blueprint_docs_protocol(request: Request) -> dict[str, Any]:
        return protocol_index(app, _protocol_filter_from_request(request))

    @app.get("/docs/openapi.json", include_in_schema=False)
    async def api_blueprint_docs_openapi(request: Request) -> dict[str, Any]:
        return sliced_openapi(app, _filter_from_request(request))

    @app.get("/asyncapi.json", include_in_schema=False)
    async def api_blueprint_asyncapi(request: Request) -> dict[str, Any]:
        return asyncapi_document(app, _protocol_filter_from_request(request))

    @app.get("/docs/swagger", include_in_schema=False)
    async def api_blueprint_docs_swagger(request: Request):
        return get_swagger_ui_html(
            openapi_url=_docs_openapi_url(request),
            title=f"{app.title or 'api-blueprint'} - Swagger",
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css",
            swagger_ui_parameters={
                "docExpansion": "none",
                "filter": True,
                "defaultModelsExpandDepth": -1,
                "validatorUrl": None,
                "syntaxHighlight": False,
            },
        )

    @app.get("/docs/protocol", include_in_schema=False)
    async def api_blueprint_docs_protocol_ui(request: Request):
        return _protocol_docs_response(request, app)

    @app.get("/docs/asyncapi", include_in_schema=False)
    async def api_blueprint_docs_asyncapi_ui(request: Request):
        return _asyncapi_docs_response(request, app)

    @app.get("/redoc", include_in_schema=False)
    async def legacy_redoc():
        return RedirectResponse(url="/")


def docs_home_path(app: FastAPI) -> str:
    if getattr(app.state, _DOCS_INSTALLED, False):
        return "/"
    return app.docs_url or "/docs"


def _docs_center_response(request: Request, app: FastAPI):
    return _TEMPLATES.TemplateResponse(
        request,
        "docs_index.html",
        {
            "title": app.title or "api-blueprint",
        },
    )


def _protocol_docs_response(request: Request, app: FastAPI):
    return _TEMPLATES.TemplateResponse(
        request,
        "docs_protocol.html",
        {
            "title": app.title or "api-blueprint",
        },
    )


def _asyncapi_docs_response(request: Request, app: FastAPI):
    return _TEMPLATES.TemplateResponse(
        request,
        "docs_asyncapi.html",
        {
            "title": app.title or "api-blueprint",
        },
    )


def register_docs_route(app: FastAPI, router: Router, contract: DocsRouteContract) -> None:
    _install_openapi_enrichment(app)
    routes = _docs_routes(app)
    entry = _route_index_entry(router, contract)
    identity = (entry["id"], tuple(entry["methods"]), entry["path"])
    if any((item["id"], tuple(item["methods"]), item["path"]) == identity for item in routes):
        return
    routes.append(entry)
    _register_route_enums(app, router)
    _register_route_schemas(app, router, str(entry["id"]))
    app.openapi_schema = None
    setattr(app.state, _DOCS_VERSION, getattr(app.state, _DOCS_VERSION, 0) + 1)
    _docs_cache(app).clear()


def docs_route_count(app: FastAPI) -> int:
    return len(_docs_routes(app))


def docs_index(app: FastAPI) -> dict[str, Any]:
    routes = sorted(_docs_routes(app), key=lambda item: (str(item["group_path"]), str(item["path"]), str(item["id"])))
    groups: dict[str, dict[str, Any]] = {}
    tags: dict[str, int] = {}
    kinds: dict[str, int] = {}
    roots: dict[str, int] = {}

    for route in routes:
        root = str(route["root"])
        group = str(route["group"])
        group_item = groups.setdefault(
            group,
            {
                "id": group,
                "root": root,
                "path": route["group_path"],
                "label": route["group_label"],
                "route_count": 0,
            },
        )
        group_item["route_count"] += 1
        roots[root] = roots.get(root, 0) + 1
        kind = str(route["kind"])
        kinds[kind] = kinds.get(kind, 0) + 1
        for tag in route["tags"]:
            tag_text = str(tag)
            tags[tag_text] = tags.get(tag_text, 0) + 1

    return {
        "title": app.title,
        "route_count": len(routes),
        "roots": [{"id": key, "route_count": value} for key, value in sorted(roots.items())],
        "groups": sorted(groups.values(), key=lambda item: (str(item["root"]), str(item["path"]))),
        "tags": [{"id": key, "route_count": value} for key, value in sorted(tags.items())],
        "kinds": [{"id": key, "route_count": value} for key, value in sorted(kinds.items())],
        "routes": routes,
    }


def protocol_index(app: FastAPI, protocol_filter: ProtocolFilter | None = None) -> dict[str, Any]:
    protocol_filter = protocol_filter or ProtocolFilter()
    routes: list[dict[str, Any]] = []
    for route in _matching_protocol_docs_routes(app, protocol_filter):
        entry = _protocol_route_entry(route)
        if entry["messages"]:
            routes.append(entry)
    raw_schemas = dict(sorted(_docs_schema_registry(app).items()))
    schema_contexts = _docs_schema_contexts(app)
    schemas, schema_name_map = _public_schema_components(raw_schemas, schema_contexts)
    routes = _public_protocol_route_models(routes, raw_schemas, schema_contexts, schema_name_map)
    catalog = {
        "title": app.title,
        "route_count": len(routes),
        "routes": routes,
        "schemas": {
            name: {"$ref": f"#/components/schemas/{name}"}
            for name in schemas
        },
        "components": {"schemas": schemas},
    }
    return _filter_protocol_catalog(
        apply_protocol_docs_plugins(catalog, _protocol_docs_plugins(app)),
        protocol_filter,
    )


def asyncapi_document(app: FastAPI, protocol_filter: ProtocolFilter | None = None) -> dict[str, Any]:
    protocol = protocol_index(app, protocol_filter)
    channels: dict[str, Any] = {}
    operations: dict[str, Any] = {}
    messages: dict[str, Any] = {}

    for route in protocol["routes"]:
        channel_key = _asyncapi_channel_key(route, channels)
        message_refs: list[dict[str, str]] = []

        for message in route.get("messages", []):
            for variant in message["variants"]:
                message_key = _asyncapi_message_key(route, message, variant)
                messages[message_key] = _asyncapi_message(route, message, variant)
                message_refs.append({"$ref": f"#/components/messages/{message_key}"})

        channels[channel_key] = {
            "address": route["path"],
            "messages": {ref["$ref"].rsplit("/", 1)[-1]: ref for ref in message_refs},
            "x-api-blueprint-route-id": route["id"],
            "x-api-blueprint-kind": route["kind"],
            "x-api-blueprint-scope": (route.get("connection") or {}).get("scope"),
            "x-api-blueprint-delivery": (route.get("connection") or {}).get("delivery"),
        }

        for message in route.get("messages", []):
            refs = [
                {"$ref": f"#/components/messages/{_asyncapi_message_key(route, message, variant)}"}
                for variant in message["variants"]
            ]
            if not refs:
                continue
            operation_key = _asyncapi_operation_key(route, message)
            operations[operation_key] = {
                "action": _asyncapi_action_for_direction(str(message["direction"])),
                "channel": {"$ref": f"#/channels/{channel_key}"},
                "messages": refs,
                "x-api-blueprint-route-id": route["id"],
                "x-api-blueprint-direction": message["direction"],
                "x-api-blueprint-delivery": (route.get("connection") or {}).get("delivery"),
                "x-api-blueprint-scope": (route.get("connection") or {}).get("scope"),
            }

    return {
        "asyncapi": "3.0.0",
        "info": {
            "title": app.title,
            "version": app.version,
        },
        "channels": channels,
        "operations": operations,
        "components": {
            "messages": messages,
            "schemas": protocol["components"]["schemas"],
        },
        "x-api-blueprint-source": "protocol-catalog",
        "x-api-blueprint-interactions": protocol.get("interactions", []),
        "x-api-blueprint-unpaired-messages": protocol.get("unpaired_messages", []),
    }


def sliced_openapi(app: FastAPI, docs_filter: DocsFilter) -> dict[str, Any]:
    if docs_filter.is_empty:
        return app.openapi()

    version = getattr(app.state, _DOCS_VERSION, 0)
    cache_key = (version, docs_filter.cache_key)
    cache = _docs_cache(app)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    route_keys = {
        (str(route["path"]), method)
        for route in _matching_docs_routes(app, docs_filter)
        if route["include_in_openapi"]
        for method in route["methods"]
    }
    selected_routes = [
        route
        for route in app.routes
        if _base_route_matches(route, route_keys)
    ]
    spec = public_openapi_schema(
        app,
        get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            summary=app.summary,
            description=app.description,
            routes=selected_routes,
            webhooks=app.webhooks.routes,
            tags=app.openapi_tags,
            servers=app.servers,
            terms_of_service=app.terms_of_service,
            contact=app.contact,
            license_info=app.license_info,
            separate_input_output_schemas=app.separate_input_output_schemas,
        ),
    )
    cache[cache_key] = spec
    return spec


def enrich_openapi_enum_metadata(app: FastAPI, spec: dict[str, Any]) -> dict[str, Any]:
    registry = _docs_enum_registry(app)
    if not registry:
        return spec

    values_index: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    name_index: dict[str, list[dict[str, Any]]] = {}
    for enum_meta in registry.values():
        values_index.setdefault(tuple(enum_meta["values"]), []).append(enum_meta)
        name_index.setdefault(str(enum_meta["name"]), []).append(enum_meta)

    def visit(node: object) -> None:
        if isinstance(node, dict):
            enum_values = node.get("enum")
            if isinstance(enum_values, list):
                enum_meta = _enum_meta_for_schema(node, name_index, values_index)
                if enum_meta is not None:
                    node["x-enumNames"] = list(enum_meta["names"])
                    node["x-enum-varnames"] = list(enum_meta["names"])
                    descriptions = enum_meta.get("descriptions")
                    if isinstance(descriptions, list) and any(descriptions):
                        node["x-enumDescriptions"] = list(descriptions)
                        node["x-enum-descriptions"] = list(descriptions)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(spec.get("components", {}).get("schemas", {}))
    visit(spec.get("paths", {}))
    return spec


def public_openapi_schema(app: FastAPI, spec: dict[str, Any]) -> dict[str, Any]:
    return remap_public_schema_names(enrich_openapi_enum_metadata(app, spec))


def remap_public_schema_names(spec: dict[str, Any]) -> dict[str, Any]:
    schemas = spec.get("components", {}).get("schemas")
    if not isinstance(schemas, dict) or not schemas:
        return spec
    contexts = _openapi_schema_contexts(spec, schemas)
    public_schemas, name_map = _public_schema_components(schemas, contexts)
    _rewrite_schema_refs_and_names(spec, name_map)
    spec.setdefault("components", {})["schemas"] = public_schemas
    return spec


def _public_schema_components(
    schemas: Mapping[str, Any],
    contexts: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    contexts = contexts or {}
    name_map = _public_schema_name_map(schemas, contexts)
    public_schemas: dict[str, Any] = {}
    for old_name, schema in schemas.items():
        public_name = name_map.get(old_name, old_name)
        schema = copy.deepcopy(schema)
        if isinstance(schema, dict):
            schema["title"] = public_name
        public_schemas[public_name] = schema
    _rewrite_schema_refs_and_names(public_schemas, name_map)
    return public_schemas, name_map


def _public_schema_name_map(
    schemas: Mapping[str, Any],
    contexts: Mapping[str, Mapping[str, str]],
) -> dict[str, str]:
    base_by_key = {
        key: _schema_public_base_name(key, schema)
        for key, schema in schemas.items()
    }
    duplicates: dict[str, int] = {}
    for base in base_by_key.values():
        duplicates[base] = duplicates.get(base, 0) + 1

    used: set[str] = set()
    result: dict[str, str] = {}
    for key, base in base_by_key.items():
        candidate = base
        if duplicates.get(base, 0) > 1:
            suffix = _schema_context_suffix(contexts.get(key, {}))
            candidate = f"{base}{suffix}" if suffix else base
        candidate = _unique_schema_name(candidate or "Schema", used)
        used.add(candidate)
        result[key] = candidate
    return result


def _schema_public_base_name(key: str, schema: object) -> str:
    if isinstance(schema, Mapping):
        title = schema.get("title")
        if isinstance(title, str) and title.strip():
            return _clean_schema_name(title.strip())
    return _clean_schema_name(str(key))


def _clean_schema_name(value: str) -> str:
    return _HASHED_SCHEMA_NAME_RE.sub("", value)


def _schema_context_suffix(context: Mapping[str, str]) -> str:
    parts = [
        context.get("path", ""),
        context.get("method", ""),
        context.get("role", ""),
    ]
    return _pascal_identifier(" ".join(part for part in parts if part))


def _unique_schema_name(candidate: str, used: set[str]) -> str:
    if candidate not in used:
        return candidate
    index = 2
    while f"{candidate}{index}" in used:
        index += 1
    return f"{candidate}{index}"


def _pascal_identifier(value: str) -> str:
    parts = [
        part
        for part in re.split(r"[^0-9A-Za-z]+", value)
        if part
    ]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _rewrite_schema_refs_and_names(node: object, name_map: Mapping[str, str]) -> None:
    if not name_map:
        return
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            prefix = "#/components/schemas/"
            if ref.startswith(prefix):
                old_name = ref[len(prefix):]
                if old_name in name_map:
                    node["$ref"] = prefix + name_map[old_name]
        for key, value in list(node.items()):
            if key == "$ref":
                continue
            if isinstance(value, str):
                node[key] = _replace_schema_name_text(value, name_map)
            else:
                _rewrite_schema_refs_and_names(value, name_map)
    elif isinstance(node, list):
        for item in node:
            _rewrite_schema_refs_and_names(item, name_map)


def _replace_schema_name_text(value: str, name_map: Mapping[str, str]) -> str:
    result = value
    for old_name, public_name in name_map.items():
        if old_name != public_name and old_name in result:
            result = result.replace(old_name, public_name)
    return result


def _openapi_schema_contexts(spec: Mapping[str, Any], schemas: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    dependency_graph = {
        key: _schema_refs(schema)
        for key, schema in schemas.items()
    }
    contexts: dict[str, dict[str, str]] = {}
    paths = spec.get("paths")
    if not isinstance(paths, Mapping):
        return contexts
    for path, path_item in paths.items():
        if not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            if str(method).lower() not in _OPENAPI_METHODS or not isinstance(operation, Mapping):
                continue
            base_context = {
                "path": str(path),
                "method": str(method).lower(),
                "kind": "rpc",
            }
            role_nodes = [
                ("parameter", operation.get("parameters")),
                ("request", operation.get("requestBody")),
                ("response", operation.get("responses")),
            ]
            assigned: set[str] = set()
            for role, node in role_nodes:
                context = dict(base_context)
                context["role"] = role
                for ref in sorted(_schema_refs(node)):
                    assigned.add(ref)
                    _assign_schema_context(ref, context, dependency_graph, contexts)
            context = dict(base_context)
            context["role"] = "operation"
            for ref in sorted(_schema_refs(operation) - assigned):
                _assign_schema_context(ref, context, dependency_graph, contexts)
    return contexts


def _assign_schema_context(
    schema_name: str,
    context: Mapping[str, str],
    dependency_graph: Mapping[str, set[str]],
    contexts: dict[str, dict[str, str]],
) -> None:
    if schema_name in contexts:
        return
    contexts[schema_name] = dict(context)
    for child in sorted(dependency_graph.get(schema_name, ())):
        _assign_schema_context(child, context, dependency_graph, contexts)


def _schema_refs(node: object) -> set[str]:
    refs: set[str] = set()
    if isinstance(node, Mapping):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            refs.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            refs.update(_schema_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.update(_schema_refs(item))
    return refs


def _install_openapi_enrichment(app: FastAPI) -> None:
    if getattr(app.state, _DOCS_OPENAPI_WRAPPED, False):
        return
    original_openapi = app.openapi

    def api_blueprint_openapi() -> dict[str, Any]:
        return public_openapi_schema(app, original_openapi())

    app.openapi = api_blueprint_openapi  # type: ignore[method-assign]
    setattr(app.state, _DOCS_OPENAPI_WRAPPED, True)


def _enum_meta_for_schema(
    schema: Mapping[str, Any],
    name_index: Mapping[str, list[dict[str, Any]]],
    values_index: Mapping[tuple[Any, ...], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    for key in (schema.get("title"), schema.get("name")):
        matches = name_index.get(key) if isinstance(key, str) else None
        if matches is not None and len(matches) == 1:
            return matches[0]

    enum_values = schema.get("enum")
    if not isinstance(enum_values, list):
        return None
    matches = values_index.get(tuple(enum_values), [])
    if len(matches) == 1:
        return matches[0]
    return None


def _register_route_enums(app: FastAPI, router: Router) -> None:
    registry = _docs_enum_registry(app)
    for source in _route_enum_sources(router):
        for enum_cls in iter_enum_classes(source):
            if not isinstance(enum_cls, enum.EnumMeta):
                continue
            values = [member.value for member in enum_cls]
            identity = f"{enum_cls.__module__}.{enum_cls.__qualname__}:{values!r}"
            registry.setdefault(
                identity,
                {
                    "name": enum_cls.__name__,
                    "names": [member.name for member in enum_cls],
                    "values": values,
                    "descriptions": [
                        item.description or ""
                        for item in enum_value_metadata(enum_cls)
                    ],
                },
            )


def _register_route_schemas(app: FastAPI, router: Router, route_id: str) -> None:
    if router.connection_kind not in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
        return
    registry = _docs_schema_registry(app)
    contexts = _docs_schema_contexts(app)
    for source, role in _route_schema_sources(router):
        _register_schema_source(registry, contexts, source, router, route_id, role)


def _register_schema_source(
    registry: dict[str, Any],
    contexts: dict[str, dict[str, str]],
    source: ModelRef | None,
    router: Router,
    route_id: str,
    role: str,
) -> None:
    if source is None:
        return
    model_cls = source.__class__ if not isinstance(source, type) else source
    try:
        root_key, schema, definitions = _model_to_schema(model_cls, router)
    except Exception:
        return
    context = _schema_context(router, route_id, role)
    for name, definition in definitions.items():
        if isinstance(name, str) and name and isinstance(definition, dict):
            definition.setdefault("title", _clean_schema_name(name))
            registry.setdefault(name, definition)
            contexts.setdefault(name, context)
    if root_key and isinstance(schema, dict):
        schema.setdefault("title", _clean_schema_name(root_key))
        registry.setdefault(root_key, schema)
        contexts.setdefault(root_key, context)


def _model_to_schema(model_cls: type[Any], router: Router) -> tuple[str, dict[str, Any], dict[str, Any]]:
    from api_blueprint.engine.schema import model_to_pydantic

    pydantic_model = model_to_pydantic(model_cls, router=router)
    schema = pydantic_model.model_json_schema(ref_template="#/components/schemas/{model}")
    definitions = schema.pop("$defs", {})
    if not isinstance(definitions, dict):
        definitions = {}
    return pydantic_model.__name__, schema, definitions


def _schema_context(router: Router, route_id: str, role: str) -> dict[str, str]:
    methods = ",".join(str(method).lower() for method in getattr(router, "methods", ()) or ())
    if not methods:
        methods = router.connection_kind.value
    return {
        "route_id": route_id,
        "path": router.url,
        "method": methods,
        "kind": router.connection_kind.value,
        "role": role,
    }


def _route_enum_sources(router: Router) -> list[object]:
    sources: list[object] = [
        router.req_path,
        router.req_query,
        router.req_urlencoded,
        router.req_multipart,
        router.req_json,
        router.rsp_model,
        router.open_model,
        router.effective_close_model,
    ]
    for message in (router.server_message, router.client_message):
        if message is None:
            continue
        sources.extend(variant.model for variant in message.variants)
    return sources


def _route_schema_sources(router: Router) -> list[tuple[ModelRef | None, str]]:
    sources: list[tuple[ModelRef | None, str]] = [
        (router.req_path, "request_path"),
        (router.req_query, "request_query"),
        (router.req_urlencoded, "request_form"),
        (router.req_multipart, "request_multipart"),
        (router.req_json, "request_json"),
        (router.open_model, "open"),
        (router.rsp_model, "response"),
        (router.effective_close_model, "close"),
    ]
    for direction, message in (("server", router.server_message), ("client", router.client_message)):
        if message is None:
            continue
        sources.extend((variant.model, f"{direction}_{variant.key}") for variant in message.variants)
    return sources


def _docs_routes(app: FastAPI) -> list[dict[str, Any]]:
    routes = getattr(app.state, _DOCS_ROUTES, None)
    if routes is None:
        routes = []
        setattr(app.state, _DOCS_ROUTES, routes)
    return routes


def _docs_cache(app: FastAPI) -> dict[object, dict[str, Any]]:
    cache = getattr(app.state, _DOCS_CACHE, None)
    if cache is None:
        cache = {}
        setattr(app.state, _DOCS_CACHE, cache)
    return cache


def _docs_enum_registry(app: FastAPI) -> dict[str, dict[str, Any]]:
    registry = getattr(app.state, _DOCS_ENUMS, None)
    if registry is None:
        registry = {}
        setattr(app.state, _DOCS_ENUMS, registry)
    return registry


def _docs_schema_registry(app: FastAPI) -> dict[str, Any]:
    registry = getattr(app.state, _DOCS_SCHEMAS, None)
    if registry is None:
        registry = {}
        setattr(app.state, _DOCS_SCHEMAS, registry)
    return registry


def _docs_schema_contexts(app: FastAPI) -> dict[str, dict[str, str]]:
    contexts = getattr(app.state, _DOCS_SCHEMA_CONTEXTS, None)
    if contexts is None:
        contexts = {}
        setattr(app.state, _DOCS_SCHEMA_CONTEXTS, contexts)
    return contexts


def _protocol_docs_plugins(app: FastAPI) -> tuple[ProtocolDocsPlugin | ProtocolDocsPluginFn, ...]:
    plugins = getattr(app.state, _DOCS_PROTOCOL_PLUGINS, None)
    if plugins is None:
        return ()
    return tuple(plugins)


def _route_index_entry(router: Router, contract: DocsRouteContract) -> dict[str, Any]:
    kind = router.connection_kind.value
    methods = _docs_methods(router, contract)
    branch = (router.group.branch or "").strip("/")
    group_path = router.group.prefix
    return {
        "id": contract.route_id,
        "root": router.bp.root_slug,
        "group": contract.group_alias,
        "group_path": group_path,
        "group_label": branch or group_path,
        "kind": kind,
        "operation": contract.func_name,
        "methods": methods,
        "path": router.url,
        "leaf": router.leaf,
        "tags": list(router.tags),
        "summary": _optional_string(router.extra.get("summary")),
        "description": _optional_string(router.extra.get("description")),
        "deprecated": router.is_deprecated,
        "include_in_openapi": router.connection_kind != ConnectionKind.CHANNEL,
        "errors": _route_error_summary(router),
        "request": {
            "path_model": _model_ref_name(router.req_path),
            "query_model": _model_ref_name(router.req_query),
            "body_kind": router.request_body_kind,
            "json_model": _model_ref_name(router.req_json),
            "form_model": _model_ref_name(router.req_urlencoded),
            "multipart_model": _model_ref_name(router.req_multipart),
        },
        "response": {
            "kind": router.response_kind,
            "media_type": router.rsp_media_type,
            "model": _model_ref_name(router.rsp_model),
        },
        "connection": _connection_summary(router),
    }


def _docs_methods(router: Router, contract: DocsRouteContract) -> list[str]:
    if router.connection_kind == ConnectionKind.STREAM:
        return ["GET"]
    if router.connection_kind == ConnectionKind.CHANNEL:
        return []
    return list(contract.http_methods)


def _connection_summary(router: Router) -> dict[str, Any] | None:
    if router.connection_kind not in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
        return None
    return {
        "scope": router.connection_scope.value if router.connection_scope is not None else "session",
        "delivery": router.connection_delivery.value if router.connection_delivery is not None else "ordered",
        "open_model": _model_ref_name(router.open_model),
        "close_model": _model_ref_name(router.effective_close_model),
        "server_message": _message_summary(router.server_message),
        "client_message": _message_summary(router.client_message),
    }


def _message_summary(message: MessageContract | None) -> dict[str, Any] | None:
    if message is None:
        return None
    return {
        "name": message.name,
        "variants": [
            {
                "key": variant.key,
                "model": _model_ref_name(variant.model),
                "metadata": _json_safe_mapping(variant.metadata or {}),
                **_variant_metadata_fields(variant.metadata or {}),
            }
            for variant in message.variants
        ],
    }


def _variant_metadata_fields(metadata: Mapping[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in ("op", "name", "description", "auth", "example", "interaction", "interaction_id", "role"):
        if key in metadata:
            fields[key] = _json_safe_value(metadata[key])
    return fields


def _route_error_summary(router: Router) -> list[dict[str, Any]]:
    seen: set[tuple[int, str]] = set()
    result: list[dict[str, Any]] = []
    for errors_by_code in (router.bp.errors, router.errors):
        for errors in errors_by_code.values():
            for err in errors:
                marker = (int(err.code), str(getattr(err, "__key__", err.message)))
                if marker in seen:
                    continue
                seen.add(marker)
                result.append(
                    {
                        "code": int(err.code),
                        "message": str(err.message),
                    }
                )
    return result


def _protocol_docs_routes(app: FastAPI) -> list[Mapping[str, Any]]:
    return [route for route in _docs_routes(app) if route.get("connection") is not None]


def _matching_protocol_docs_routes(app: FastAPI, protocol_filter: ProtocolFilter) -> list[Mapping[str, Any]]:
    docs_filter = DocsFilter(
        route_ids=protocol_filter.route_ids,
        groups=protocol_filter.groups,
        tags=protocol_filter.tags,
        kinds=protocol_filter.kinds,
    )
    return [
        route
        for route in _protocol_docs_routes(app)
        if _route_matches_filter(route, docs_filter)
    ]


def _protocol_route_entry(route: Mapping[str, Any], protocol_filter: ProtocolFilter | None = None) -> dict[str, Any]:
    connection = route.get("connection") or {}
    return {
        "route_id": route["id"],
        "id": route["id"],
        "kind": route["kind"],
        "root": route["root"],
        "group": route["group"],
        "group_path": route["group_path"],
        "path": route["path"],
        "summary": route.get("summary"),
        "description": route.get("description"),
        "tags": list(route.get("tags") or []),
        "deprecated": bool(route.get("deprecated")),
        "scope": connection.get("scope"),
        "delivery": connection.get("delivery"),
        "errors": list(route.get("errors") or []),
        "messages": _protocol_messages(route, protocol_filter),
    }


def _public_protocol_route_models(
    routes: list[dict[str, Any]],
    raw_schemas: Mapping[str, Any],
    schema_contexts: Mapping[str, Mapping[str, str]],
    schema_name_map: Mapping[str, str],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for route in routes:
        item = dict(route)
        item["messages"] = [
            _public_protocol_message_models(
                message,
                route,
                raw_schemas,
                schema_contexts,
                schema_name_map,
            )
            for message in list(route.get("messages") or [])
            if isinstance(message, Mapping)
        ]
        result.append(item)
    return result


def _public_protocol_message_models(
    message: Mapping[str, Any],
    route: Mapping[str, Any],
    raw_schemas: Mapping[str, Any],
    schema_contexts: Mapping[str, Mapping[str, str]],
    schema_name_map: Mapping[str, str],
) -> dict[str, Any]:
    item = dict(message)
    direction = str(item.get("direction") or "")
    item["variants"] = [
        _public_protocol_variant_model(
            variant,
            route,
            direction,
            raw_schemas,
            schema_contexts,
            schema_name_map,
        )
        for variant in list(item.get("variants") or [])
        if isinstance(variant, Mapping)
    ]
    return item


def _public_protocol_variant_model(
    variant: Mapping[str, Any],
    route: Mapping[str, Any],
    direction: str,
    raw_schemas: Mapping[str, Any],
    schema_contexts: Mapping[str, Mapping[str, str]],
    schema_name_map: Mapping[str, str],
) -> dict[str, Any]:
    item = dict(variant)
    model = item.get("model")
    if isinstance(model, str) and model:
        role = direction if direction in {"open", "close"} else f"{direction}_{item.get('key') or ''}"
        item["model"] = _public_schema_name_for_model(
            model,
            str(route.get("route_id") or route.get("id") or ""),
            role,
            raw_schemas,
            schema_contexts,
            schema_name_map,
        )
    return item


def _public_schema_name_for_model(
    model_name: str,
    route_id: str,
    role: str,
    raw_schemas: Mapping[str, Any],
    schema_contexts: Mapping[str, Mapping[str, str]],
    schema_name_map: Mapping[str, str],
) -> str:
    candidates = [
        key
        for key, schema in raw_schemas.items()
        if _schema_public_base_name(str(key), schema) == model_name
    ]
    if not candidates:
        return schema_name_map.get(model_name, model_name)

    route_candidates = [
        key
        for key in candidates
        if schema_contexts.get(key, {}).get("route_id") == route_id
    ]
    if route_candidates:
        candidates = route_candidates

    if role:
        role_candidates = [
            key
            for key in candidates
            if schema_contexts.get(key, {}).get("role") == role
        ]
        if role_candidates:
            candidates = role_candidates

    return schema_name_map.get(candidates[0], model_name)


def _filter_protocol_catalog(catalog: dict[str, Any], protocol_filter: ProtocolFilter) -> dict[str, Any]:
    if not protocol_filter.has_message_filters:
        return catalog

    matching_interactions = [
        interaction
        for interaction in catalog.get("interactions", [])
        if isinstance(interaction, Mapping) and _interaction_matches_protocol_filter(interaction, protocol_filter)
    ]
    matching_interaction_ids = {
        str(interaction.get("id"))
        for interaction in matching_interactions
        if isinstance(interaction, Mapping) and interaction.get("id") is not None
    }

    routes: list[dict[str, Any]] = []
    for route in catalog.get("routes", []):
        if not isinstance(route, Mapping):
            continue
        messages = _filter_protocol_messages(list(route.get("messages") or []), protocol_filter)
        route_interactions = [
            interaction_id
            for interaction_id in route.get("interactions", [])
            if str(interaction_id) in matching_interaction_ids
        ]
        if not messages and not route_interactions:
            continue
        item = dict(route)
        item["messages"] = messages
        item["interactions"] = route_interactions
        routes.append(item)

    catalog["routes"] = routes
    catalog["route_count"] = len(routes)
    catalog["interactions"] = matching_interactions
    catalog["unpaired_messages"] = [
        message
        for message in catalog.get("unpaired_messages", [])
        if isinstance(message, Mapping) and _message_ref_matches_protocol_filter(message, protocol_filter)
    ]
    return catalog


def _filter_protocol_messages(messages: list[dict[str, Any]], protocol_filter: ProtocolFilter) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        direction = str(message.get("direction") or "")
        if protocol_filter.directions and direction not in protocol_filter.directions:
            continue
        variants = [
            variant
            for variant in list(message.get("variants") or [])
            if isinstance(variant, Mapping) and _variant_matches_protocol_filter(variant, protocol_filter)
        ]
        if variants:
            item = dict(message)
            item["variants"] = variants
            result.append(item)
    return result


def _interaction_matches_protocol_filter(interaction: Mapping[str, Any], protocol_filter: ProtocolFilter) -> bool:
    messages: list[Mapping[str, Any]] = []
    for key in ("messages", "responses", "errors", "pushes", "opens", "closes"):
        values = interaction.get(key)
        if isinstance(values, list):
            messages.extend(value for value in values if isinstance(value, Mapping))
    request = interaction.get("request")
    if isinstance(request, Mapping):
        messages.append(request)
    return any(_message_ref_matches_protocol_filter(message, protocol_filter) for message in messages)


def _message_ref_matches_protocol_filter(message: Mapping[str, Any], protocol_filter: ProtocolFilter) -> bool:
    direction = str(message.get("direction") or "")
    if protocol_filter.directions and direction not in protocol_filter.directions:
        return False
    if not protocol_filter.ops:
        return True
    op = message.get("op")
    return op is not None and str(op) in protocol_filter.ops


def _protocol_messages(route: Mapping[str, Any], protocol_filter: ProtocolFilter | None = None) -> list[dict[str, Any]]:
    protocol_filter = protocol_filter or ProtocolFilter()
    connection = route.get("connection") or {}
    result: list[dict[str, Any]] = []
    for direction, key in (
        ("open", "open_model"),
        ("server", "server_message"),
        ("client", "client_message"),
        ("close", "close_model"),
    ):
        value = connection.get(key)
        if not value:
            continue
        if protocol_filter.directions and direction not in protocol_filter.directions:
            continue
        if key.endswith("_model"):
            if protocol_filter.ops:
                continue
            result.append(
                {
                    "direction": direction,
                    "name": value,
                    "variants": [
                        {
                            "key": direction,
                            "model": value,
                            "metadata": {},
                        }
                    ],
                }
            )
        else:
            variants = list(value.get("variants") or []) if isinstance(value, Mapping) else []
            variants = [
                variant
                for variant in variants
                if _variant_matches_protocol_filter(variant, protocol_filter)
            ]
            if not variants:
                continue
            result.append(
                {
                    "direction": direction,
                    "name": value.get("name") if isinstance(value, Mapping) else None,
                    "variants": variants,
                }
            )
    return result


def _variant_matches_protocol_filter(variant: Mapping[str, Any], protocol_filter: ProtocolFilter) -> bool:
    if not protocol_filter.ops:
        return True
    op = variant.get("op")
    metadata = variant.get("metadata") if isinstance(variant.get("metadata"), Mapping) else {}
    if op is None:
        op = metadata.get("op")
    return op is not None and str(op) in protocol_filter.ops


def _asyncapi_channel_key(route: Mapping[str, Any], channels: Mapping[str, Any]) -> str:
    preferred = _identifier(str(route.get("path") or route["id"]))
    if preferred and preferred not in channels:
        return preferred
    fallback = _identifier(str(route["id"]))
    if fallback and fallback not in channels:
        return fallback
    index = 2
    while f"{fallback}{index}" in channels:
        index += 1
    return f"{fallback}{index}"


def _asyncapi_operation_key(route: Mapping[str, Any], message: Mapping[str, Any]) -> str:
    return _identifier(f"{route['id']}.{message['direction']}")


def _asyncapi_message_key(route: Mapping[str, Any], message: Mapping[str, Any], variant: Mapping[str, Any]) -> str:
    suffix = variant.get("key") or variant.get("model") or message.get("direction")
    return _identifier(f"{route['id']}.{message['direction']}.{suffix}")


def _asyncapi_message(route: Mapping[str, Any], message: Mapping[str, Any], variant: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(variant.get("metadata") or {})
    model = variant.get("model")
    item: dict[str, Any] = {
        "name": variant.get("name") or variant.get("key") or model or message.get("name"),
        "title": variant.get("description") or variant.get("name") or variant.get("key") or model,
        "payload": {"$ref": f"#/components/schemas/{model}"} if model else {},
        "x-api-blueprint-route-id": route["id"],
        "x-api-blueprint-direction": message["direction"],
        "x-api-blueprint-variant-key": variant.get("key") or "",
        "x-api-blueprint-delivery": (route.get("connection") or {}).get("delivery"),
        "x-api-blueprint-scope": (route.get("connection") or {}).get("scope"),
    }
    if "op" in metadata:
        item["x-api-blueprint-op"] = metadata["op"]
    if metadata:
        item["x-api-blueprint-metadata"] = metadata
    return item


def _asyncapi_action_for_direction(direction: str) -> str:
    if direction in {"client", "open"}:
        return "send"
    return "receive"


def _identifier(value: str) -> str:
    parts = [
        part
        for part in "".join(char if char.isalnum() else " " for char in value).split()
        if part
    ]
    if not parts:
        return "route"
    return parts[0].lower() + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _model_ref_name(model: ModelRef | None) -> str | None:
    if model is None:
        return None
    if isinstance(model, type):
        return model.__name__
    return model.__class__.__name__


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _filter_from_request(request: Request) -> DocsFilter:
    params = request.query_params
    return DocsFilter(
        route_ids=tuple(params.getlist("route_id")),
        groups=tuple(params.getlist("group")),
        tags=tuple(params.getlist("tag")),
        kinds=tuple(params.getlist("kind")),
    )


def _protocol_filter_from_request(request: Request) -> ProtocolFilter:
    params = request.query_params
    return ProtocolFilter(
        route_ids=tuple(params.getlist("route_id")),
        groups=tuple(params.getlist("group")),
        tags=tuple(params.getlist("tag")),
        kinds=tuple(params.getlist("kind")),
        directions=tuple(params.getlist("direction")),
        ops=tuple(params.getlist("op")),
    )


def _docs_openapi_url(request: Request) -> str:
    query = request.url.query
    return "/docs/openapi.json" + (f"?{query}" if query else "")


def _matching_docs_routes(app: FastAPI, docs_filter: DocsFilter) -> list[Mapping[str, Any]]:
    return [
        route
        for route in _docs_routes(app)
        if _route_matches_filter(route, docs_filter)
    ]


def _route_matches_filter(route: Mapping[str, Any], docs_filter: DocsFilter) -> bool:
    if docs_filter.route_ids and str(route["id"]) not in docs_filter.route_ids:
        return False
    if docs_filter.groups:
        if not any(_route_matches_group_filter(route, group) for group in docs_filter.groups):
            return False
    if docs_filter.tags and not any(tag in route["tags"] for tag in docs_filter.tags):
        return False
    if docs_filter.kinds and str(route["kind"]) not in docs_filter.kinds:
        return False
    return True


def _route_matches_group_filter(route: Mapping[str, Any], group: str) -> bool:
    route_group = str(route["group"])
    route_group_path = str(route["group_path"])
    if group == route_group or group == route_group_path:
        return True
    if not group.startswith("/"):
        return False
    prefix = group.rstrip("/")
    if not prefix:
        return False
    return route_group_path.startswith(f"{prefix}/")


def _base_route_matches(route: BaseRoute, route_keys: set[tuple[str, str]]) -> bool:
    path = getattr(route, "path", None)
    methods = getattr(route, "methods", None)
    if not isinstance(path, str) or not methods:
        return False
    return any((path, str(method).upper()) in route_keys for method in methods)
