from __future__ import annotations

import enum
import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, get_origin

from api_blueprint._version import __version__
from api_blueprint.engine import Blueprint
from api_blueprint.engine.connection import ConnectionDelivery, ConnectionKind, MessageContract, ModelRef
from api_blueprint.engine.model import (
    AnonKV,
    Array,
    CoerceString,
    Enum as ModelEnum,
    Error,
    Field,
    FieldWrappedModel,
    Map,
    Model,
    OneOf,
    iter_model_vars,
    model_to_pydantic,
    unwrap_model_type,
)
from api_blueprint.engine.router import Router

from .route import RouteContract, resolve_route_contracts, route_contract
from .runtime import ContractRouteRuntime


MANIFEST_VERSION = "2.0"


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ContractGraphDiff:
    breaking: list[str] = field(default_factory=list)
    compatible: list[str] = field(default_factory=list)
    risky: list[str] = field(default_factory=list)

    def to_manifest(self) -> JsonObject:
        return {
            "breaking": list(self.breaking),
            "compatible": list(self.compatible),
            "risky": list(self.risky),
        }


@dataclass
class ContractGraph:
    services: list[JsonObject]
    routes: list[JsonObject]
    schemas: "OrderedDict[str, JsonObject]"
    exported_models: list[JsonObject] = field(default_factory=list)
    errors: list[JsonObject] = field(default_factory=list)
    targets: list[JsonObject] = field(default_factory=list)
    capabilities: dict[str, JsonObject] = field(default_factory=dict)
    route_runtime: dict[str, ContractRouteRuntime] = field(default_factory=dict, repr=False)

    def to_manifest(self) -> JsonObject:
        route_hashes: dict[str, str] = {}
        routes: list[JsonObject] = []
        for route in self.routes:
            normalized_route = _without_hash(route)
            digest = _stable_hash(normalized_route)
            materialized = dict(route)
            materialized["hash"] = digest
            routes.append(materialized)
            route_hashes[materialized["id"]] = digest

        schema_hashes = {name: _stable_hash(schema) for name, schema in self.schemas.items()}
        return {
            "version": MANIFEST_VERSION,
            "generator": {
                "name": "api-blueprint",
                "version": __version__,
            },
            "services": list(self.services),
            "routes": routes,
            "schemas": dict(self.schemas),
            "exported_models": list(self.exported_models),
            "errors": list(self.errors),
            "connections": [
                {
                    "route_id": route["id"],
                    **route["connection"],
                }
                for route in routes
                if route.get("connection") is not None
            ],
            "targets": list(self.targets),
            "capabilities": dict(self.capabilities),
            "hashes": {
                "routes": route_hashes,
                "schemas": schema_hashes,
            },
        }


class ContractGraphBuilder:
    def __init__(self) -> None:
        self.services: "OrderedDict[str, JsonObject]" = OrderedDict()
        self.routes: list[JsonObject] = []
        self.schemas: "OrderedDict[str, JsonObject]" = OrderedDict()
        self.exported_models: list[JsonObject] = []
        self.errors: "OrderedDict[str, JsonObject]" = OrderedDict()
        self.route_runtime: dict[str, ContractRouteRuntime] = {}
        self._qualified_schema_names: set[str] = set()
        self._schema_ref_rewrites: dict[str, str] = {}

    def build(self, blueprints: Iterable[Blueprint]) -> ContractGraph:
        blueprint_list = list(blueprints)
        blueprint_roots: dict[str, Blueprint] = {}
        routers: list[Router] = []
        for blueprint in blueprint_list:
            existing_blueprint = blueprint_roots.setdefault(blueprint.root_slug, blueprint)
            if existing_blueprint is not blueprint:
                raise ValueError(
                    "duplicate blueprint logical root "
                    f"'{blueprint.root_slug}' for Blueprint(name={blueprint.name!r}, root={blueprint.root!r}) "
                    f"and Blueprint(name={existing_blueprint.name!r}, root={existing_blueprint.root!r}). "
                    "Set unique Blueprint(name=...) values or merge routes into one Blueprint."
                )
            self.add_errors(blueprint.errors)
            for _group, router in blueprint.iter_router():
                router.validate_connection_contract()
                routers.append(router)
        contracts = resolve_route_contracts(routers)
        _validate_route_identity_conflicts(routers, contracts)
        for router in routers:
            self.add_router(router, contract=contracts[router])
        for blueprint in blueprint_list:
            self.add_exported_models(blueprint)
        return ContractGraph(
            services=list(self.services.values()),
            routes=self.routes,
            schemas=self.schemas,
            exported_models=list(self.exported_models),
            errors=list(self.errors.values()),
            route_runtime=dict(self.route_runtime),
        )

    def add_router(self, router: Router, *, contract: RouteContract | None = None) -> None:
        router.validate_connection_contract()
        contract = contract or route_contract(router)
        service = self._service_manifest(router, contract)
        self.services.setdefault(service["id"], service)
        route = self._route_manifest(router, contract)
        self.routes.append(route)
        self.route_runtime[contract.route_id] = self._route_runtime(router)
        self.add_errors(router.errors)

    def add_errors(self, errors_by_code: Mapping[int, list[Error]]) -> None:
        for err in _iter_declared_errors(errors_by_code):
            manifest = _error_manifest(err)
            self.errors.setdefault(manifest["id"], manifest)

    def add_exported_models(self, blueprint: Blueprint) -> None:
        for exported in blueprint.exported_models:
            schema_ref = self._schema_ref(exported.model)
            if schema_ref is None:
                continue
            item: JsonObject = {
                "model": schema_ref,
                "metadata": _json_safe_mapping(exported.metadata, label="exported model metadata"),
            }
            if item not in self.exported_models:
                self.exported_models.append(item)

    def _service_manifest(self, router: Router, contract: RouteContract) -> JsonObject:
        root_slug = _contract_root_slug(contract)
        return {
            "id": f"{root_slug}.{contract.group_alias}",
            "root": root_slug,
            "group": contract.group_alias,
            "name": contract.service_name,
            "path": router.group.prefix,
        }

    def _route_manifest(self, router: Router, contract: RouteContract) -> JsonObject:
        service_id = f"{_contract_root_slug(contract)}.{contract.group_alias}"
        request = {
            "query_model": self._schema_ref(router.req_query),
            "json_model": self._schema_ref(router.req_json),
            "form_model": self._schema_ref(router.req_urlencoded),
            "urlencoded_model": self._schema_ref(router.req_urlencoded),
            "multipart_model": self._schema_ref(router.req_multipart),
            "binary_model": self._schema_ref(router.req_bin),
            "binary_schema": router.req_binary_schema.to_manifest(include_html=True)
            if router.req_binary_schema is not None
            else None,
            "body_kind": router.request_body_kind,
        }
        response = None
        if router.rsp_model is not None or router.response_kind in {"bytes", "file", "byte_stream", "binary_schema"}:
            response = {
                "kind": router.response_kind,
                "media_type": router.rsp_media_type,
                "model": self._schema_ref(router.rsp_model),
                "binary_schema": router.rsp_binary_schema.to_manifest(include_html=True)
                if router.rsp_binary_schema is not None
                else None,
                "envelope": router.response_envelope.envelope_spec(),
                "content_type": router.rsp_media_type,
                "headers": _raw_response_headers(router),
                "download": router.response_kind == "file",
                "streaming": router.response_kind == "byte_stream",
                "filename": router.rsp_filename,
                "default_filename": router.rsp_filename,
                "success_enveloped": router.response_kind not in {"bytes", "file", "byte_stream", "binary_schema"},
            }

        connection = None
        if router.connection_kind in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
            connection = self._connection_manifest(router)

        route = {
            "id": contract.route_id,
            "service_id": service_id,
            "kind": _route_kind(router),
            "operation": contract.func_name,
            "method_name": contract.method_name,
            "methods": list(contract.http_methods),
            "path": router.leaf,
            "url": router.url,
            "tags": list(router.tags),
            "providers": [_provider_manifest(provider) for provider in router.providers],
            "deprecated": router.is_deprecated,
            "errors": self._route_error_refs(router),
            "request": request,
            "response": response,
            "connection": connection,
            "proto": _proto_route_metadata(router),
        }
        self._apply_schema_ref_rewrites(route)
        return route

    def _route_error_refs(self, router: Router) -> list[JsonObject]:
        seen: set[str] = set()
        result: list[JsonObject] = []
        for errors_by_code in (router.bp.errors, router.errors):
            for err in _iter_declared_errors(errors_by_code):
                manifest = _error_manifest(err)
                self.errors.setdefault(manifest["id"], manifest)
                if manifest["id"] in seen:
                    continue
                seen.add(manifest["id"])
                result.append(dict(manifest))
        return result

    def _connection_manifest(self, router: Router) -> JsonObject:
        close_model = router.effective_close_model
        return {
            "kind": router.connection_kind.value,
            "delivery": (router.connection_delivery.value if router.connection_delivery is not None else ConnectionDelivery.ORDERED.value),
            "scope": (router.connection_scope.value if router.connection_scope is not None else "session"),
            "open_model": self._schema_ref(router.open_model),
            "close_model": self._schema_ref(close_model),
            "server_message": self._message_manifest(router.server_message),
            "client_message": self._message_manifest(router.client_message),
        }

    def _route_runtime(self, router: Router) -> ContractRouteRuntime:
        return ContractRouteRuntime(
            query_model=router.req_query,
            json_model=router.req_json,
            form_model=router.req_urlencoded,
            multipart_model=router.req_multipart,
            body_kind=router.request_body_kind,
            binary_model=router.req_bin,
            binary_schema=router.req_binary_schema,
            open_model=router.open_model,
            response_model=router.rsp_model,
            response_binary_schema=router.rsp_binary_schema,
            response_kind=router.response_kind,
            response_media_type=router.rsp_media_type,
            response_filename=router.rsp_filename,
            response_envelope=router.response_envelope,
            recvs=tuple(router.recvs),
            sends=tuple(router.sends),
            server_message=router.server_message,
            client_message=router.client_message,
            close_model=router.effective_close_model,
        )

    def _message_manifest(self, message: MessageContract | None) -> JsonObject | None:
        if message is None:
            return None
        variants: list[JsonObject] = []
        for variant in message.variants:
            item = {
                "key": variant.key,
                "model": self._schema_ref(variant.model),
            }
            if variant.metadata:
                item["metadata"] = _json_safe_mapping(
                    variant.metadata,
                    label=f"message variant[{variant.key}] metadata",
                )
            variants.append(item)
        name = message.name or (variants[0]["model"] if variants else None)
        return {
            "name": name,
            "variants": variants,
        }

    def _schema_ref(self, model: ModelRef | Field | None) -> str | None:
        if model is None:
            return None
        if isinstance(model, FieldWrappedModel):
            return self._alias_schema_ref(
                _model_name(model),
                self._field_manifest(model.__field_type__),
                auto=bool(getattr(model, "__auto__", False)),
            )
        if isinstance(model, Field):
            return self._alias_schema_ref(
                _model_name(model),
                self._field_manifest(model),
                auto=bool(getattr(model, "__auto__", False)),
            )

        model_cls = unwrap_model_type(model)
        name = _model_name(model_cls)
        schema_id = self._schema_id(model_cls)
        if schema_id in self.schemas:
            return schema_id

        module = _model_module(model_cls)
        qualname = _model_qualname(model_cls)
        identity = _model_identity(model_cls)
        self.schemas[schema_id] = {
            "name": name,
            "module": module,
            "qualname": qualname,
            "identity": identity,
            "kind": "model",
            "type": "object",
            "fields": {},
            "auto": bool(getattr(model_cls, "__auto__", False)),
        }
        proto_model = _proto_model_metadata(model_cls)
        if proto_model:
            self.schemas[schema_id]["proto"] = proto_model
        fields: dict[str, JsonObject] = {}
        pydantic_fields = _safe_pydantic_fields(model_cls)
        for field_name, field_value in iter_model_vars(model_cls):
            if not isinstance(field_value, (Field, Model)):
                continue
            extra = dict(getattr(field_value, "__extra__", {}) or {})
            alias = str(extra.get("alias") or field_name)
            pydantic_field = pydantic_fields.get(field_name)
            optional = bool(extra.get("optional", False) or extra.get("omitempty", False))
            description = str(extra.get("description") or "")
            if pydantic_field is not None:
                optional = optional or not pydantic_field.is_required()
                description = pydantic_field.description or description
            manifest = self._field_manifest(field_value)
            manifest.update(
                {
                    "name": field_name,
                    "wire_name": alias,
                    "optional": optional,
                    "description": description,
                }
            )
            manifest.update(_contract_field_metadata(extra))
            manifest.update(_proto_field_metadata(extra))
            fields[field_name] = manifest
        self.schemas[schema_id]["fields"] = fields
        return schema_id

    def _alias_schema_ref(self, name: str, target: JsonObject, *, auto: bool) -> str:
        identity = _alias_identity(name, target)
        schema_id = self._schema_id_for_identity(name, identity)
        if schema_id in self.schemas:
            return schema_id
        self.schemas[schema_id] = {
            "name": name,
            "identity": identity,
            "kind": "alias",
            "type": "alias",
            "target": target,
            "auto": auto,
        }
        return schema_id

    def _schema_id(self, model_cls: type[Model]) -> str:
        return self._schema_id_for_identity(_model_name(model_cls), _model_identity(model_cls))

    def _schema_id_for_identity(self, name: str, identity: str) -> str:
        if name in self._qualified_schema_names:
            return identity
        existing = self.schemas.get(name)
        if existing is None:
            if identity in self.schemas:
                return identity
            return name
        if existing.get("identity") == identity:
            return name

        existing_identity = str(existing.get("identity") or name)
        if existing_identity != name and existing_identity not in self.schemas:
            self._qualified_schema_names.add(name)
            self._schema_ref_rewrites[name] = existing_identity
            self.schemas[existing_identity] = existing
            del self.schemas[name]
            self._replace_schema_ref(name, existing_identity)
        return identity

    def _replace_schema_ref(self, old: str, new: str) -> None:
        for route in self.routes:
            _replace_schema_ref_value(route, old, new)
        for schema in self.schemas.values():
            _replace_schema_ref_value(schema, old, new)
        for exported in self.exported_models:
            _replace_schema_ref_value(exported, old, new)

    def _apply_schema_ref_rewrites(self, value: JsonObject) -> None:
        for old, new in self._schema_ref_rewrites.items():
            _replace_schema_ref_value(value, old, new)

    def _field_manifest(self, field_value: Any) -> JsonObject:
        if _is_parametrized_field(field_value):
            field_value = field_value()

        if isinstance(field_value, type) and issubclass(field_value, Field):
            field_value = field_value()

        if isinstance(field_value, AnonKV):
            obj = field_value.get_obj()
            return self._field_manifest(obj) if obj is not None else {"type": "object"}

        if isinstance(field_value, FieldWrappedModel):
            return self._field_manifest(field_value.__field_type__)

        if isinstance(field_value, OneOf):
            return {
                "type": "one_of",
                "variants": [self._field_manifest(variant) for variant in field_value.variants],
            }

        if isinstance(field_value, CoerceString):
            return {
                "type": "coerce_string",
                "canonical": {"type": "string"},
                "accepts": [self._field_manifest(variant) for variant in field_value.accepts],
            }

        if isinstance(field_value, Array):
            return {
                "type": "array",
                "items": self._field_manifest(field_value.elem_type()),
            }

        if isinstance(field_value, Map):
            return {
                "type": "map",
                "keys": self._field_manifest(field_value.key_type()),
                "values": self._field_manifest(field_value.value_type()),
            }

        if isinstance(field_value, ModelEnum):
            enum_cls = field_value.enum_type()
            values = [member.value for member in enum_cls] if isinstance(enum_cls, enum.EnumMeta) else []
            return {
                "type": "enum",
                "enum": getattr(enum_cls, "__name__", "Enum"),
                **_enum_contract_metadata(enum_cls),
                "values": values,
                "enum_values": _enum_value_manifest(enum_cls),
            }

        if isinstance(field_value, enum.EnumMeta):
            return {
                "type": "enum",
                "enum": field_value.__name__,
                **_enum_contract_metadata(field_value),
                "values": [member.value for member in field_value],
                "enum_values": _enum_value_manifest(field_value),
            }

        if isinstance(field_value, Model) or (isinstance(field_value, type) and issubclass(field_value, Model)):
            return {
                "type": "object",
                "ref": self._schema_ref(field_value),
            }

        field_type = getattr(field_value, "__type__", None)
        if isinstance(field_type, str) and field_type:
            manifest = {
                "type": field_type,
                **_contract_field_metadata(getattr(field_value, "__extra__", {}) or {}),
                **_proto_field_metadata(getattr(field_value, "__extra__", {}) or {}),
            }
            if field_type == "file":
                extra = getattr(field_value, "__extra__", {}) or {}
                manifest["content_types"] = list(extra.get("content_types") or [])
                if extra.get("max_size") is not None:
                    manifest["max_size"] = int(extra["max_size"])
            return manifest

        if isinstance(field_value, type):
            return {"type": field_value.__name__.lower()}

        return {"type": "any"}


def build_contract_graph(blueprints: Iterable[Blueprint]) -> ContractGraph:
    return ContractGraphBuilder().build(blueprints)


def _provider_manifest(provider: Any) -> JsonObject:
    name = str(getattr(provider, "name", "") or "").strip()
    if not name:
        raise ValueError("route provider name is required")
    manifest: JsonObject = {"name": name}
    data = getattr(provider, "data", None)
    if data is not None:
        try:
            manifest["data"] = json.loads(json.dumps(data, ensure_ascii=False, sort_keys=True))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"route provider[{name}] data must be JSON-serializable") from exc
    return manifest


def _json_safe_mapping(value: Mapping[str, Any], *, label: str) -> JsonObject:
    try:
        return json.loads(json.dumps(dict(value), ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON-serializable") from exc


def _validate_route_identity_conflicts(
    routers: Iterable[Router],
    contracts: Mapping[Router, RouteContract],
) -> None:
    routes_by_id: dict[str, Router] = {}
    routes_by_method_url: dict[tuple[str, str], Router] = {}
    services_by_id: dict[str, tuple[str, Router]] = {}

    for router in routers:
        contract = contracts[router]
        existing_route = routes_by_id.get(contract.route_id)
        if existing_route is not None:
            raise ValueError(
                "duplicate route id "
                f"'{contract.route_id}' for routes {existing_route.methods} {existing_route.url} "
                f"and {router.methods} {router.url}. "
                "Set unique Blueprint(name=...), group paths, methods, or operation_id values."
            )
        routes_by_id[contract.route_id] = router

        for method in _effective_http_methods(router):
            key = (method, router.url)
            existing_route = routes_by_method_url.get(key)
            if existing_route is not None:
                raise ValueError(
                    "duplicate HTTP route "
                    f"{method} {router.url} for route ids "
                    f"{contracts[existing_route].route_id!r} and {contract.route_id!r}."
                )
            routes_by_method_url[key] = router

        service_id = f"{_contract_root_slug(contract)}.{contract.group_alias}"
        group_prefix = router.group.prefix
        existing_service = services_by_id.get(service_id)
        if existing_service is not None and existing_service[0] != group_prefix:
            existing_prefix, existing_router = existing_service
            raise ValueError(
                "duplicate generated service surface "
                f"'{service_id}' for group prefixes {existing_prefix!r} and {group_prefix!r}. "
                f"Routes {contracts[existing_router].route_id!r} and {contract.route_id!r} would share "
                "one package/module; use a different Blueprint(name=...) or group path."
            )
        services_by_id.setdefault(service_id, (group_prefix, router))


def _effective_http_methods(router: Router) -> tuple[str, ...]:
    if router.connection_kind == ConnectionKind.STREAM:
        return ("GET",)
    if router.connection_kind == ConnectionKind.CHANNEL:
        return ()
    return tuple(method for method in router.methods if method in {"GET", "POST", "PUT", "DELETE", "HEAD"})


def diff_manifests(before: Mapping[str, Any], after: Mapping[str, Any]) -> JsonObject:
    diff = ContractGraphDiff()
    before_routes = _route_hashes(before)
    after_routes = _route_hashes(after)

    for route_id in sorted(before_routes.keys() - after_routes.keys()):
        diff.breaking.append(f"route removed: {route_id}")
    for route_id in sorted(after_routes.keys() - before_routes.keys()):
        diff.compatible.append(f"route added: {route_id}")
    for route_id in sorted(before_routes.keys() & after_routes.keys()):
        if before_routes[route_id] != after_routes[route_id]:
            diff.risky.append(f"route changed: {route_id}")

    before_schemas = _schema_fields(before)
    after_schemas = _schema_fields(after)
    for schema_name in sorted(before_schemas.keys() | after_schemas.keys()):
        before_fields = before_schemas.get(schema_name, {})
        after_fields = after_schemas.get(schema_name, {})
        for field_name in sorted(before_fields.keys() - after_fields.keys()):
            diff.breaking.append(f"field removed: {schema_name}.{field_name}")
        for field_name in sorted(after_fields.keys() - before_fields.keys()):
            field_manifest = after_fields[field_name]
            if bool(field_manifest.get("optional", False)):
                diff.compatible.append(f"optional field added: {schema_name}.{field_name}")
            else:
                diff.breaking.append(f"required field added: {schema_name}.{field_name}")
        for field_name in sorted(before_fields.keys() & after_fields.keys()):
            if before_fields[field_name] != after_fields[field_name]:
                diff.risky.append(f"field changed: {schema_name}.{field_name}")

    return diff.to_manifest()


setattr(build_contract_graph, "diff_manifests", diff_manifests)


def _route_kind(router: Router) -> str:
    if router.connection_kind == ConnectionKind.RPC:
        return "rpc"
    return router.connection_kind.value


def _iter_declared_errors(errors_by_code: Mapping[int, list[Error]]) -> Iterable[Error]:
    for errors in errors_by_code.values():
        for err in errors:
            yield err


def _error_manifest(err: Error) -> JsonObject:
    group, key = _error_group_key(err)
    return {
        "id": f"{group}.{key}",
        "group": group,
        "key": key,
        "code": int(err.code),
        "message": str(err.message),
        "toast": _error_toast_manifest(err, group, key),
    }


def _error_toast_manifest(err: Error, group: str, key: str) -> JsonObject:
    toast = getattr(err, "toast", None)
    if toast is None:
        return {
            "key": f"{group}.{key}",
            "default": str(err.message),
            "level": "error",
        }
    return {
        "key": str(toast.key or f"{group}.{key}"),
        "default": str(toast.default or err.message),
        "level": str(toast.level or "error"),
    }


def _error_group_key(err: Error) -> tuple[str, str]:
    raw_key = getattr(err, "__key__", None)
    if (
        isinstance(raw_key, tuple)
        and len(raw_key) == 2
        and isinstance(raw_key[0], str)
        and isinstance(raw_key[1], str)
        and raw_key[0]
        and raw_key[1]
    ):
        return raw_key
    code = int(err.code)
    suffix = f"NEG_{abs(code)}" if code < 0 else str(code)
    return "Error", f"CODE_{suffix}"


def _contract_root_slug(contract: RouteContract) -> str:
    return contract.route_id.split(".", 1)[0] or "root"


def _raw_response_headers(router: Router) -> JsonObject:
    if router.response_kind != "file":
        return {}
    return {
        "Content-Disposition": {
            "description": "File download disposition",
            "required": False,
        }
    }


def _model_name(model: object) -> str:
    value = getattr(model, "__name__", None)
    if isinstance(value, str) and value:
        return value
    return model.__class__.__name__


def _model_module(model: object) -> str:
    value = getattr(model, "__module__", "")
    return value if isinstance(value, str) else ""


def _model_qualname(model: object) -> str:
    value = getattr(model, "__qualname__", None)
    if isinstance(value, str) and value:
        return value
    return _model_name(model)


def _model_identity(model: object) -> str:
    module = _model_module(model)
    qualname = _model_qualname(model)
    identity = f"{module}.{qualname}" if module else qualname
    if bool(getattr(model, "__auto__", False)):
        digest = hashlib.sha256(
            json.dumps(_auto_model_signature(model), ensure_ascii=False, sort_keys=True, default=repr).encode("utf-8")
        ).hexdigest()[:12]
        return f"{identity}#{digest}"
    return identity


def _alias_identity(name: str, target: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {"name": name, "target": target},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=repr,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"{name}#{digest}"


def _auto_model_signature(model: object) -> JsonObject:
    fields: list[JsonObject] = []
    for field_name, field_value in iter_model_vars(model):
        if not isinstance(field_value, (Field, Model)):
            continue
        fields.append(
            {
                "name": field_name,
                "field": _field_signature(field_value),
                "extra": _json_safe(getattr(field_value, "__extra__", {}) or {}),
            }
        )
    return {
        "name": _model_name(model),
        "fields": sorted(fields, key=lambda item: str(item.get("name"))),
    }


def _field_signature(field_value: object) -> object:
    if _is_parametrized_field(field_value):
        field_value = field_value()
    if isinstance(field_value, type) and issubclass(field_value, Field):
        field_value = field_value()
    if isinstance(field_value, AnonKV):
        obj = field_value.get_obj()
        return {"type": "anon", "value": _field_signature(obj) if obj is not None else None}
    if isinstance(field_value, FieldWrappedModel):
        return {"type": "wrapped", "value": _field_signature(field_value.__field_type__)}
    if isinstance(field_value, OneOf):
        return {"type": "one_of", "variants": [_field_signature(variant) for variant in field_value.variants]}
    if isinstance(field_value, CoerceString):
        return {"type": "coerce_string", "accepts": [_field_signature(variant) for variant in field_value.accepts]}
    if isinstance(field_value, Array):
        return {"type": "array", "items": _field_signature(field_value.elem_type())}
    if isinstance(field_value, Map):
        return {
            "type": "map",
            "keys": _field_signature(field_value.key_type()),
            "values": _field_signature(field_value.value_type()),
        }
    if isinstance(field_value, ModelEnum):
        enum_cls = field_value.enum_type()
        return {"type": "enum", "identity": _model_identity(enum_cls)}
    if isinstance(field_value, enum.EnumMeta):
        return {"type": "enum", "identity": _model_identity(field_value)}
    if isinstance(field_value, Model) or (isinstance(field_value, type) and issubclass(field_value, Model)):
        return {"type": "object", "identity": _model_identity(unwrap_model_type(field_value))}
    field_type = getattr(field_value, "__type__", None)
    if isinstance(field_type, str) and field_type:
        signature: dict[str, object] = {"type": field_type}
        if field_type == "file":
            extra = getattr(field_value, "__extra__", {}) or {}
            signature["content_types"] = list(extra.get("content_types") or [])
            signature["max_size"] = extra.get("max_size")
        return signature
    if isinstance(field_value, type):
        return {"type": field_value.__name__.lower()}
    return {"type": type(field_value).__name__}


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, enum.Enum):
        return {"enum": _model_identity(value.__class__), "value": value.value}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if isinstance(value, type):
        return _model_identity(value)
    return repr(value)


def _safe_pydantic_fields(model_cls: type[Model]) -> Mapping[str, Any]:
    try:
        return model_to_pydantic(model_cls).model_fields
    except Exception:
        return {}


def _proto_route_metadata(router: Router) -> JsonObject:
    metadata: JsonObject = {}
    group_extra = dict(getattr(router.group, "extra", {}) or {})
    route_extra = dict(getattr(router, "extra", {}) or {})
    for source in (group_extra, route_extra):
        for key, value in source.items():
            if not key.startswith("proto_") or value is None or value == "":
                continue
            metadata[key.removeprefix("proto_")] = value
    return metadata


def _proto_model_metadata(model_cls: type[Model]) -> JsonObject:
    metadata: JsonObject = {}
    for attr, manifest_key in (
        ("__proto_file__", "file"),
        ("__proto_package__", "package"),
        ("__proto_go_package__", "go_package"),
    ):
        value = getattr(model_cls, attr, None)
        if isinstance(value, str) and value:
            metadata[manifest_key] = value
    return metadata


def _proto_field_metadata(extra: Mapping[str, Any]) -> JsonObject:
    metadata: JsonObject = {}
    for key, value in extra.items():
        if not key.startswith("proto_") or value is None or value == "":
            continue
        metadata[key.removeprefix("proto_")] = value
    return {"proto": metadata} if metadata else {}


def _contract_field_metadata(extra: Mapping[str, Any]) -> JsonObject:
    metadata: JsonObject = {}
    number = extra.get("contract_field_id")
    if number is None:
        number = extra.get("wire_number")
    if number is not None:
        metadata["field_id"] = int(number)
    if extra.get("optional") is True:
        metadata["optional"] = True
    choice = extra.get("contract_choice")
    if isinstance(choice, str) and choice:
        metadata["choice"] = choice
    return {"contract": metadata} if metadata else {}


def _enum_contract_metadata(enum_cls: object) -> JsonObject:
    if not isinstance(enum_cls, enum.EnumMeta):
        return {}
    module = _model_module(enum_cls)
    qualname = _model_qualname(enum_cls)
    identity = _model_identity(enum_cls)
    return {
        "enum_module": module,
        "enum_qualname": qualname,
        "enum_identity": identity,
    }


def _replace_schema_ref_value(value: object, old: str, new: str) -> None:
    if isinstance(value, dict):
        for key, item in list(value.items()):
            if key in {
                "query_model",
                "json_model",
                "form_model",
                "urlencoded_model",
                "multipart_model",
                "binary_model",
                "open_model",
                "close_model",
                "model",
                "ref",
            } and item == old:
                value[key] = new
                continue
            _replace_schema_ref_value(item, old, new)
    elif isinstance(value, list):
        for item in value:
            _replace_schema_ref_value(item, old, new)


def _enum_value_manifest(enum_cls: object) -> list[JsonObject]:
    if not isinstance(enum_cls, enum.EnumMeta):
        return []
    return [
        {
            "name": member.name,
            "value": member.value,
        }
        for member in enum_cls
    ]


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _without_hash(route: Mapping[str, Any]) -> JsonObject:
    return {key: value for key, value in route.items() if key != "hash"}


def _route_hashes(manifest: Mapping[str, Any]) -> dict[str, str]:
    explicit = manifest.get("hashes", {})
    if isinstance(explicit, Mapping):
        routes = explicit.get("routes", {})
        if isinstance(routes, Mapping) and routes:
            return {str(key): str(value) for key, value in routes.items()}

    result: dict[str, str] = {}
    for route in manifest.get("routes", []):
        if not isinstance(route, Mapping):
            continue
        route_id = route.get("id")
        if route_id is None:
            continue
        route_hash = route.get("hash")
        result[str(route_id)] = str(route_hash) if route_hash is not None else _stable_hash(_without_hash(route))
    return result


def _schema_fields(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    schemas = manifest.get("schemas", {})
    if not isinstance(schemas, Mapping):
        return result
    for name, schema in schemas.items():
        if not isinstance(schema, Mapping):
            continue
        fields = schema.get("fields", {})
        if isinstance(fields, Mapping):
            result[str(name)] = fields
    return result


def _is_parametrized_field(value: object) -> bool:
    origin = get_origin(value)
    return origin is not None and isinstance(origin, type)
