from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Sequence

from api_blueprint.config import ResolvedApiTargetConfig

if TYPE_CHECKING:
    from api_blueprint.contract import ContractGraph


RouteManifest = Mapping[str, object]


@dataclass(frozen=True)
class TargetCapability:
    implemented: bool
    routes: tuple[str, ...] = ()
    ignored_routes: tuple[str, ...] = ()
    requests: tuple[str, ...] = ()
    envelopes: tuple[str, ...] = ()
    reserved: bool = False
    transport: str | None = None
    outputs: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    frontend_modes: tuple[str, ...] = ()
    responses: tuple[str, ...] = ()

    def to_manifest(self) -> dict[str, object]:
        manifest: dict[str, object] = {"implemented": self.implemented, "routes": list(self.routes)}
        if self.ignored_routes:
            manifest["ignored_routes"] = list(self.ignored_routes)
        if self.requests:
            manifest["requests"] = list(self.requests)
        if self.envelopes:
            manifest["envelopes"] = list(self.envelopes)
        if self.reserved:
            manifest["reserved"] = True
        if self.transport is not None:
            manifest["transport"] = self.transport
        if self.outputs:
            manifest["outputs"] = list(self.outputs)
        if self.inputs:
            manifest["inputs"] = list(self.inputs)
        if self.frontend_modes:
            manifest["frontend_modes"] = list(self.frontend_modes)
        if self.responses:
            manifest["responses"] = list(self.responses)
        return manifest


TARGET_CAPABILITIES: dict[str, TargetCapability] = {
    "contract": TargetCapability(implemented=True, outputs=("json", "markdown", "agent-json", "agent-markdown", "shards")),
    "go-server": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("path", "query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "go-client": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("path", "query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        transport="injected",
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "typescript-client": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        transport="injected",
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "kotlin-client": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        transport="injected",
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "kotlin-server": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "java-server": TargetCapability(
        implemented=True,
        routes=("rpc",),
        requests=("query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
        outputs=("spring-controllers", "java-types", "adapters", "spring-contract-assertions"),
    ),
    "java-client": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        transport="injected",
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "flutter-client": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        transport="injected",
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "swift-client": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        transport="injected",
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "python-server": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "python-client": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("path", "query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        transport="injected",
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
    ),
    "http-transport": TargetCapability(implemented=True, routes=("rpc", "stream", "channel")),
    "wails-transport": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "open"),
        responses=("json", "xml"),
        frontend_modes=("external", "none"),
    ),
    "grpc-proto": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("query", "json", "form", "urlencoded", "binary", "open"),
        responses=("json", "xml"),
        outputs=("proto",),
    ),
    "grpc-go": TargetCapability(implemented=True, inputs=("proto",), outputs=("go", "grpc-go")),
    "grpc-python": TargetCapability(implemented=True, inputs=("proto",), outputs=("python", "grpc-python")),
    "ir-plugin": TargetCapability(
        implemented=True,
        routes=("rpc", "stream", "channel"),
        requests=("path", "query", "json", "form", "urlencoded", "multipart", "binary", "binary-schema", "open"),
        envelopes=("none", "code_message_data", "ok_data_error"),
        transport="plugin",
        responses=("json", "xml", "bytes", "file", "byte_stream", "binary_schema"),
        outputs=("plugin",),
    ),
}


def target_capability_manifest() -> dict[str, dict[str, object]]:
    return {kind: capability.to_manifest() for kind, capability in TARGET_CAPABILITIES.items()}


def capability_errors(
    graph: "ContractGraph",
    targets: Sequence[ResolvedApiTargetConfig],
) -> list[str]:
    routes = graph.to_manifest()["routes"]
    errors: list[str] = []
    for target in targets:
        capability = TARGET_CAPABILITIES.get(target.kind)
        if capability is None:
            errors.append(f"{target.kind} unsupported target capability: target[{target.id}]")
            continue
        if not capability.implemented:
            errors.append(f"{target.kind} is reserved but not implemented: target[{target.id}]")
            continue
        for route in routes:
            if not isinstance(route, Mapping):
                continue
            if not target_selects_route(target, route):
                continue
            errors.extend(_route_capability_errors(target, capability, route))
    return errors


def target_selects_route(target: ResolvedApiTargetConfig, route: RouteManifest) -> bool:
    if target.include and not any(route_matches_rule(route, rule) for rule in target.include):
        return False
    return not any(route_matches_rule(route, rule) for rule in target.exclude)


def route_matches_rule(route: RouteManifest, rule: str) -> bool:
    if ":" not in rule:
        key = "path"
        pattern = rule
    else:
        key, pattern = rule.split(":", 1)

    if key == "path":
        return fnmatch.fnmatchcase(_route_str(route, "url"), pattern)
    if key == "tag":
        tags = route.get("tags", [])
        return isinstance(tags, list) and any(fnmatch.fnmatchcase(str(tag), pattern) for tag in tags)
    if key == "group":
        return fnmatch.fnmatchcase(_route_str(route, "service_id").rsplit(".", 1)[-1], pattern.strip("/"))
    if key == "method":
        methods = route.get("methods", [])
        return isinstance(methods, list) and any(fnmatch.fnmatchcase(str(method), pattern.upper()) for method in methods)
    if key == "name":
        return fnmatch.fnmatchcase(_route_str(route, "operation"), pattern)
    if key == "kind":
        return fnmatch.fnmatchcase(_route_str(route, "kind"), pattern)
    return False


def _route_capability_errors(
    target: ResolvedApiTargetConfig,
    capability: TargetCapability,
    route: RouteManifest,
) -> list[str]:
    route_id = _route_str(route, "id")
    errors: list[str] = []
    route_kind = _route_str(route, "kind") or "rpc"
    if route_kind in capability.ignored_routes:
        return errors
    if capability.routes and route_kind not in capability.routes:
        errors.append(f"{target.kind} does not support {route_kind} route: {route_id}")

    request = route.get("request") or {}
    if capability.requests and isinstance(request, Mapping):
        for request_kind, manifest_key in (
            ("path", "path_model"),
            ("query", "query_model"),
            ("json", "json_model"),
            ("form", "form_model"),
            ("urlencoded", "urlencoded_model"),
            ("multipart", "multipart_model"),
            ("binary", "binary_model"),
            ("binary-schema", "binary_schema"),
            ("open", "open_model"),
        ):
            if request.get(manifest_key) is not None and request_kind not in capability.requests:
                errors.append(
                    f"{target.kind} does not support {request_kind} request route: {route_id}"
                    f"{_native_modeling_hint(target.kind, request_kind)}"
                )

    response = route.get("response") or {}
    if capability.responses and isinstance(response, Mapping):
        response_kind = str(response.get("kind") or "json")
        if response_kind not in capability.responses:
            errors.append(
                f"{target.kind} does not support {response_kind} response route: {route_id}"
                f"{_native_modeling_hint(target.kind, response_kind)}"
            )
    if capability.envelopes and isinstance(response, Mapping):
        response_envelope = response.get("envelope")
        envelope = _envelope_kind(response_envelope)
        if envelope not in capability.envelopes:
            errors.append(f"{target.kind} does not support {envelope} response envelope route: {route_id}")
        if _envelope_error_identity(response_envelope) == "none":
            duplicate_codes = _duplicate_route_error_codes(route)
            if duplicate_codes:
                rendered = ", ".join(str(code) for code in duplicate_codes)
                errors.append(
                    f"{target.kind} route {route_id} uses a no-id response envelope with duplicate error code(s): {rendered}"
                )
    return errors


def _envelope_kind(envelope: object) -> str:
    if not isinstance(envelope, Mapping):
        return "none"
    return str(envelope.get("kind") or "custom")


def _envelope_error_identity(envelope: object) -> str:
    if not isinstance(envelope, Mapping):
        return "none"
    return str(envelope.get("error_identity") or "nested")


def _duplicate_route_error_codes(route: RouteManifest) -> tuple[int, ...]:
    raw_errors = route.get("errors")
    if not isinstance(raw_errors, list):
        return ()
    seen: set[int] = set()
    duplicates: set[int] = set()
    for raw_error in raw_errors:
        if not isinstance(raw_error, Mapping):
            continue
        code = raw_error.get("code")
        if not isinstance(code, int):
            continue
        if code in seen:
            duplicates.add(code)
        seen.add(code)
    return tuple(sorted(duplicates))


def _route_str(route: RouteManifest, key: str) -> str:
    value = route.get(key)
    return "" if value is None else str(value)


def _native_modeling_hint(target_kind: str, contract_kind: str) -> str:
    if target_kind == "grpc-proto" and contract_kind in {
        "multipart",
        "binary-schema",
        "binary_schema",
        "bytes",
        "file",
        "byte_stream",
    }:
        return "; model this as protobuf bytes fields or explicit client/server-streaming chunk messages"
    if target_kind == "wails-transport" and contract_kind in {
        "multipart",
        "binary-schema",
        "binary_schema",
        "bytes",
        "file",
        "byte_stream",
    }:
        return "; model this as Wails RPC file descriptors, serializable bytes, or STREAM/CHANNEL chunks"
    return ""
