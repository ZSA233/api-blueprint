from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from api_blueprint.writer.core.go_naming import to_go_exported_name, to_go_package_name, to_go_package_path
from api_blueprint.writer.core.message_helpers import MessageHelperDescriptor, unique_named_message_helpers
from api_blueprint.writer.core.sdk_names import RoutePublicNames

from .binary_schema import GoClientBinarySchema, unique_go_client_binary_schemas


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class GoClientRoute:
    route: JsonObject

    @property
    def operation(self) -> str:
        return self.public_names.operation

    @property
    def public_names(self) -> RoutePublicNames:
        return RoutePublicNames.from_operation(self.route.get("operation"), fallback="Call")

    @property
    def query_type(self) -> str:
        return self.public_names.query

    @property
    def json_type(self) -> str:
        return self.public_names.json

    @property
    def form_type(self) -> str:
        return self.public_names.form

    @property
    def binary_type(self) -> str:
        return self.public_names.binary

    @property
    def open_type(self) -> str:
        return self.public_names.open

    @property
    def close_type(self) -> str:
        return self.public_names.close

    @property
    def response_type(self) -> str:
        return self.public_names.response

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
    def response_envelope(self) -> Mapping[str, Any]:
        envelope = self.response.get("envelope")
        if isinstance(envelope, Mapping):
            return envelope
        return {
            "name": "NoEnvelope",
            "kind": "none",
            "error_identity": "none",
            "success_code": 0,
            "success_message": "ok",
            "fields": {},
        }

    @property
    def response_envelope_go_literal(self) -> str:
        spec = self.response_envelope
        fields = spec.get("fields")
        field_map = fields if isinstance(fields, Mapping) else {}
        return (
            "runtime.ApiResponseEnvelope{"
            f"Name: {_code_literal(str(spec.get('name') or 'NoEnvelope'))}, "
            f"Kind: {_code_literal(str(spec.get('kind') or 'none'))}, "
            f"ErrorIdentity: {_code_literal(str(spec.get('error_identity') or 'none'))}, "
            f"SuccessCode: runtime.ApiErrorCode({int(spec.get('success_code') or 0)}), "
            f"SuccessMessage: {_code_literal(str(spec.get('success_message') or 'ok'))}, "
            "Fields: runtime.ApiResponseEnvelopeFields{"
            f"Code: {_code_literal(str(field_map.get('code') or 'code'))}, "
            f"Message: {_code_literal(str(field_map.get('message') or 'message'))}, "
            f"Data: {_code_literal(str(field_map.get('data') or 'data'))}, "
            f"Error: {_code_literal(str(field_map.get('error') or 'error'))}, "
            f"Ok: {_code_literal(str(field_map.get('ok') or 'ok'))}, "
            "}, "
            "}"
        )

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

    def message_helpers(self) -> tuple[MessageHelperDescriptor, ...]:
        return unique_named_message_helpers([route.route for route in self.routes])


def build_go_client_groups(
    routes: Sequence[JsonObject],
    services: Mapping[str, JsonObject],
) -> tuple[GoClientGroup, ...]:
    groups: dict[tuple[str, ...], GoClientGroup] = {}
    for route in routes:
        service = services.get(str(route.get("service_id") or ""), {})
        root = to_go_package_path(str(service.get("root") or _service_root(route)), fallback="api")
        group_name = to_go_package_path(str(service.get("group") or root), fallback=root)
        segments = (root,) if group_name == root else (root, group_name)
        group = groups.get(segments)
        if group is None:
            group = GoClientGroup(
                segments=segments,
                package=to_go_package_name(segments[-1], fallback="api"),
                client_class=f"{to_go_exported_name(group_name)}Client",
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


def _code_literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
