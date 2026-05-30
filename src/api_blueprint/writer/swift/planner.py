from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .naming import to_swift_module_name
from .protos import SwiftProto

if TYPE_CHECKING:
    from .blueprint import SwiftApiGroup, SwiftBlueprint
    from .writer import SwiftWriter


@dataclass(frozen=True)
class SwiftRuntimePlan:
    module_name: str
    directory: Path
    generated_files: tuple[tuple[str, str], ...]
    user_files: tuple[tuple[str, str], ...]
    types_file: Path
    shared_protos: tuple[SwiftProto, ...]
    binary_runtime_file: Path


@dataclass(frozen=True)
class SwiftRuntimeHttpTransportPlan:
    directory: Path
    generated_files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SwiftAggregateHttpFacadePlan:
    directory: Path
    user_files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SwiftRouteGroupPlan:
    group: "SwiftApiGroup"
    directory: Path
    client_file: Path
    facade_file: Path
    types_file: Path
    types_facade_file: Path
    binary_file: Path
    protos: tuple[SwiftProto, ...]


@dataclass(frozen=True)
class SwiftBlueprintPlan:
    bp: "SwiftBlueprint"
    module_name: str
    aggregate_property_name: str
    source_directory: Path
    root_directory: Path
    root_client_file: Path
    root_facade_file: Path
    route_groups: tuple[SwiftRouteGroupPlan, ...]


@dataclass(frozen=True)
class SwiftAggregatePlan:
    module_name: str
    directory: Path
    generated_facade_file: Path
    facade_file: Path
    http_facade: SwiftAggregateHttpFacadePlan
    excludes: tuple[str, ...]


@dataclass(frozen=True)
class SwiftPackagePlan:
    aggregate: SwiftAggregatePlan
    runtime: SwiftRuntimePlan
    runtime_http_transport: SwiftRuntimeHttpTransportPlan
    roots: tuple[SwiftBlueprintPlan, ...]


def build_swift_package_plan(writer: "SwiftWriter", bps: tuple["SwiftBlueprint", ...]) -> SwiftPackagePlan:
    used_modules = {writer.package, writer.runtime_module}
    root_modules: dict["SwiftBlueprint", str] = {}
    for bp in bps:
        root_modules[bp] = _unique_root_module_name(writer.package, bp.root_type, used_modules)
    root_properties = _unique_root_property_names(bps)

    runtime_dir = writer.runtime_source_dir
    aggregate_dir = writer.source_dir
    return SwiftPackagePlan(
        aggregate=SwiftAggregatePlan(
            module_name=writer.package,
            directory=aggregate_dir,
            generated_facade_file=aggregate_dir / f"Gen{writer.package}.swift",
            facade_file=aggregate_dir / f"{writer.package}.swift",
            http_facade=SwiftAggregateHttpFacadePlan(
                directory=aggregate_dir / "Transports" / "HTTP",
                user_files=(("HTTPAPIClient.swift", "HTTPAPIClient.swift"),),
            ),
            excludes=_aggregate_excludes(aggregate_dir, bps),
        ),
        runtime=SwiftRuntimePlan(
            module_name=writer.runtime_module,
            directory=runtime_dir,
            generated_files=(
                ("GenAPITransport.swift", "GenAPITransport.swift"),
                ("GenAPIClient.swift", "GenAPIClient.swift"),
                ("GenAPIErrors.swift", "GenAPIErrors.swift"),
                ("GenAPIErrorLookup.swift", "GenAPIErrorLookup.swift"),
            ),
            user_files=(("APICoding.swift", "APICoding.swift"),),
            types_file=runtime_dir / "GenAPITypes.swift",
            shared_protos=_shared_protos(bps),
            binary_runtime_file=runtime_dir / "Binary" / "GenBinaryRuntime.swift",
        ),
        runtime_http_transport=SwiftRuntimeHttpTransportPlan(
            directory=runtime_dir / "Transports" / "HTTP",
            generated_files=(
                ("GenHTTPAPIConfig.swift", "GenHTTPAPIConfig.swift"),
                ("GenURLSessionAPITransport.swift", "GenURLSessionAPITransport.swift"),
                ("GenHTTPConnection.swift", "GenHTTPConnection.swift"),
            ),
        ),
        roots=tuple(
            build_swift_blueprint_plan(
                writer,
                bp,
                module_name=root_modules[bp],
                aggregate_property_name=root_properties[bp],
            )
            for bp in bps
        ),
    )


def build_swift_blueprint_plan(
    writer: "SwiftWriter",
    bp: "SwiftBlueprint",
    *,
    module_name: str,
    aggregate_property_name: str,
) -> SwiftBlueprintPlan:
    source_dir = writer.swift_sources_dir / module_name
    root_directory = source_dir / bp.root_path
    routes_dir = root_directory / "Routes"
    route_groups = tuple(
        SwiftRouteGroupPlan(
            group=group,
            directory=routes_dir / group.path,
            client_file=routes_dir / group.path / f"Gen{group.type_stem}API.swift",
            facade_file=routes_dir / group.path / f"{group.type_stem}API.swift",
            types_file=routes_dir / group.path / f"Gen{group.type_stem}Types.swift",
            types_facade_file=routes_dir / group.path / f"{group.type_stem}Types.swift",
            binary_file=routes_dir / group.path / "GenBinary.swift",
            protos=tuple(bp.registry.filter(module=group.slug)),
        )
        for group in bp.groups.values()
    )
    return SwiftBlueprintPlan(
        bp=bp,
        module_name=module_name,
        aggregate_property_name=aggregate_property_name,
        source_directory=source_dir,
        root_directory=root_directory,
        root_client_file=root_directory / f"Gen{bp.root_client}.swift",
        root_facade_file=root_directory / f"{bp.root_client}.swift",
        route_groups=route_groups,
    )


def _unique_root_module_name(package: str, root_type: str, used: set[str]) -> str:
    base = to_swift_module_name(f"{package}{root_type}Routes")
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _unique_root_property_names(bps: tuple["SwiftBlueprint", ...]) -> dict["SwiftBlueprint", str]:
    used: set[str] = set()
    result: dict["SwiftBlueprint", str] = {}
    for bp in bps:
        base = bp.root_property
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}{suffix}"
            suffix += 1
        used.add(candidate)
        result[bp] = candidate
    return result


def _aggregate_excludes(aggregate_dir: Path, bps: tuple["SwiftBlueprint", ...]) -> tuple[str, ...]:
    excludes: list[str] = []
    for bp in bps:
        root_path = bp.root_path
        if root_path not in excludes and (aggregate_dir / root_path).exists():
            excludes.append(root_path)
    return tuple(excludes)


def _shared_protos(bps: tuple["SwiftBlueprint", ...]) -> tuple[SwiftProto, ...]:
    by_name: "OrderedDict[str, SwiftProto]" = OrderedDict()
    signatures: dict[str, tuple[object, ...]] = {}
    for bp in bps:
        for proto in bp.registry.filter(module="shared"):
            signature = _proto_signature(proto)
            previous = signatures.get(proto.name)
            if previous is not None and previous != signature:
                raise ValueError(
                    "[swift-client] shared Swift type name collision: "
                    f"{proto.name}. Rename the source model or route-local auto model before generation."
                )
            signatures[proto.name] = signature
            by_name.setdefault(proto.name, proto)
    return tuple(by_name.values())


def _proto_signature(proto: SwiftProto) -> tuple[object, ...]:
    if proto.kind == "enum":
        return (
            proto.kind,
            proto.raw_value_type,
            tuple(proto.enum_members or ()),
        )
    if proto.kind == "alias" and proto.alias_type is not None:
        return (proto.kind, proto.alias_type.text)
    return (
        proto.kind,
        tuple((field.name, field.wire_name, field.swift_type) for field in proto.fields),
    )
