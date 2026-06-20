from __future__ import annotations

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

if TYPE_CHECKING:
    from api_blueprint.engine.blueprint.router import Router


_DOCS_INSTALLED = "api_blueprint_docs_installed"
_DOCS_GZIP_INSTALLED = "api_blueprint_docs_gzip_installed"
_DOCS_ROUTES = "api_blueprint_docs_routes"
_DOCS_CACHE = "api_blueprint_docs_openapi_cache"
_DOCS_VERSION = "api_blueprint_docs_version"

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


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


def ensure_docs_gzip(app: FastAPI) -> None:
    if getattr(app.state, _DOCS_GZIP_INSTALLED, False):
        return
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    setattr(app.state, _DOCS_GZIP_INSTALLED, True)


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

    @app.get("/docs/openapi.json", include_in_schema=False)
    async def api_blueprint_docs_openapi(request: Request) -> dict[str, Any]:
        return sliced_openapi(app, _filter_from_request(request))

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


def register_docs_route(app: FastAPI, router: Router, contract: DocsRouteContract) -> None:
    routes = _docs_routes(app)
    entry = _route_index_entry(router, contract)
    identity = (entry["id"], tuple(entry["methods"]), entry["path"])
    if any((item["id"], tuple(item["methods"]), item["path"]) == identity for item in routes):
        return
    routes.append(entry)
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
    spec = get_openapi(
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
    )
    cache[cache_key] = spec
    return spec


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
            }
            for variant in message.variants
        ],
    }


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


def _filter_from_request(request: Request) -> DocsFilter:
    params = request.query_params
    return DocsFilter(
        route_ids=tuple(params.getlist("route_id")),
        groups=tuple(params.getlist("group")),
        tags=tuple(params.getlist("tag")),
        kinds=tuple(params.getlist("kind")),
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
