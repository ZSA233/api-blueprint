from __future__ import annotations

import enum
import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, get_origin

from api_blueprint.engine import Blueprint
from api_blueprint.engine.connection import ConnectionKind, MessageContract, ModelRef
from api_blueprint.engine.model import (
    AnonKV,
    Array,
    Enum as ModelEnum,
    Field,
    FieldWrappedModel,
    Map,
    Model,
    iter_model_vars,
    model_to_pydantic,
    unwrap_model_type,
)
from api_blueprint.engine.router import Router

from .route import RouteContract, route_contract
from .runtime import ContractRouteRuntime


MANIFEST_VERSION = "vnext-1"


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
            "services": list(self.services),
            "routes": routes,
            "schemas": dict(self.schemas),
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
        self.route_runtime: dict[str, ContractRouteRuntime] = {}

    def build(self, blueprints: Iterable[Blueprint]) -> ContractGraph:
        for blueprint in blueprints:
            for _group, router in blueprint.iter_router():
                self.add_router(router)
        return ContractGraph(
            services=list(self.services.values()),
            routes=self.routes,
            schemas=self.schemas,
            route_runtime=dict(self.route_runtime),
        )

    def add_router(self, router: Router) -> None:
        router.validate_connection_contract()
        contract = route_contract(router)
        service = self._service_manifest(router, contract)
        self.services.setdefault(service["id"], service)
        route = self._route_manifest(router, contract)
        self.routes.append(route)
        self.route_runtime[contract.route_id] = self._route_runtime(router)

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
            "form_model": self._schema_ref(router.req_form),
            "binary_model": self._schema_ref(router.req_bin),
        }
        response = None
        if router.rsp_model is not None:
            response = {
                "media_type": router.rsp_media_type,
                "model": self._schema_ref(router.rsp_model),
                "wrapper": getattr(router.response_wrapper, "__name__", None),
            }

        connection = None
        if router.connection_kind in {ConnectionKind.STREAM, ConnectionKind.CHANNEL}:
            connection = self._connection_manifest(router)

        return {
            "id": contract.route_id,
            "service_id": service_id,
            "kind": _route_kind(router),
            "operation": contract.func_name,
            "method_name": contract.method_name,
            "methods": list(contract.http_methods),
            "path": router.leaf,
            "url": router.url,
            "deprecated": router.is_deprecated,
            "request": request,
            "response": response,
            "connection": connection,
            "proto": _proto_route_metadata(router),
        }

    def _connection_manifest(self, router: Router) -> JsonObject:
        close_model = router.effective_close_model
        return {
            "kind": router.connection_kind.value,
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
            form_model=router.req_form,
            binary_model=router.req_bin,
            open_model=router.open_model,
            response_model=router.rsp_model,
            response_media_type=router.rsp_media_type,
            response_wrapper=router.response_wrapper,
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
            variants.append(
                {
                    "key": variant.key,
                    "model": self._schema_ref(variant.model),
                }
            )
        name = message.name or (variants[0]["model"] if variants else None)
        return {
            "name": name,
            "variants": variants,
        }

    def _schema_ref(self, model: ModelRef | Field | None) -> str | None:
        if model is None:
            return None
        if isinstance(model, FieldWrappedModel):
            name = _model_name(model)
            if name not in self.schemas:
                self.schemas[name] = {
                    "name": name,
                    "kind": "alias",
                    "type": "alias",
                    "target": self._field_manifest(model.__field_type__),
                    "auto": bool(getattr(model, "__auto__", False)),
                }
            return name
        if isinstance(model, Field):
            name = _model_name(model)
            if name not in self.schemas:
                self.schemas[name] = {
                    "name": name,
                    "kind": "alias",
                    "type": "alias",
                    "target": self._field_manifest(model),
                    "auto": bool(getattr(model, "__auto__", False)),
                }
            return name

        model_cls = unwrap_model_type(model)
        name = _model_name(model_cls)
        if name in self.schemas:
            return name

        self.schemas[name] = {
            "name": name,
            "kind": "model",
            "type": "object",
            "fields": {},
            "auto": bool(getattr(model_cls, "__auto__", False)),
        }
        proto_model = _proto_model_metadata(model_cls)
        if proto_model:
            self.schemas[name]["proto"] = proto_model
        fields: dict[str, JsonObject] = {}
        pydantic_fields = _safe_pydantic_fields(model_cls)
        for field_name, field_value in iter_model_vars(model_cls):
            if not isinstance(field_value, (Field, Model)):
                continue
            extra = dict(getattr(field_value, "__extra__", {}) or {})
            alias = str(extra.get("alias") or field_name)
            pydantic_field = pydantic_fields.get(field_name)
            optional = bool(extra.get("omitempty", False))
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
            manifest.update(_proto_field_metadata(extra))
            fields[field_name] = manifest
        self.schemas[name]["fields"] = fields
        return name

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
                "values": values,
                "enum_values": _enum_value_manifest(enum_cls),
            }

        if isinstance(field_value, enum.EnumMeta):
            return {
                "type": "enum",
                "enum": field_value.__name__,
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
            return {
                "type": field_type,
                **_proto_field_metadata(getattr(field_value, "__extra__", {}) or {}),
            }

        if isinstance(field_value, type):
            return {"type": field_value.__name__.lower()}

        return {"type": "any"}


def build_contract_graph(blueprints: Iterable[Blueprint]) -> ContractGraph:
    return ContractGraphBuilder().build(blueprints)


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


def _contract_root_slug(contract: RouteContract) -> str:
    return contract.route_id.split(".", 1)[0] or "root"


def _model_name(model: object) -> str:
    value = getattr(model, "__name__", None)
    if isinstance(value, str) and value:
        return value
    return model.__class__.__name__


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
