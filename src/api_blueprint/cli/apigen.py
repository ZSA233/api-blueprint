from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import click

from api_blueprint.application import generator
from api_blueprint.application import inspection


@click.group()
def api_gen() -> None:
    """Unified api-blueprint 1.0 generator."""


@api_gen.command("list-targets")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
def list_targets(config: str = "./api-blueprint.toml") -> None:
    for target in generator.list_targets(config):
        click.echo(f"{target.id}\t{target.kind}\t{target.out_dir or ''}")


@api_gen.command("explain-target")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--target", "target_id", required=True, help="target id")
def explain_target(config: str = "./api-blueprint.toml", target_id: str = "") -> None:
    summary = generator.explain_target_summary(config, target_id)
    for key, value in summary.items():
        click.echo(f"{key}: {_format_explain_target_value(value)}")


@api_gen.command("manifest")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option(
    "--profile",
    type=click.Choice(("index", "full", "agent")),
    default="index",
    show_default=True,
    help="manifest profile",
)
@click.option("--out", "out_path", required=False, type=click.Path(path_type=Path), help="manifest 输出路径")
@click.option("--shards-dir", type=click.Path(path_type=Path), help="contract shards 输出目录")
def manifest(
    config: str = "./api-blueprint.toml",
    profile: str = "index",
    out_path: Path | None = None,
    shards_dir: Path | None = None,
) -> None:
    if out_path is None and shards_dir is None:
        raise click.UsageError("--out or --shards-dir is required")
    generator.write_manifest(config, out_path, profile=profile, shards_dir=shards_dir)


@api_gen.command("diff")
@click.argument("before", type=click.Path(path_type=Path))
@click.argument("after", type=click.Path(path_type=Path))
def diff_command(before: Path, after: Path) -> None:
    diff = generator.diff_files(before, after)
    _echo_diff(diff)
    if diff["breaking"]:
        raise click.exceptions.Exit(1)


@api_gen.command("check")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
def check(config: str = "./api-blueprint.toml") -> None:
    generator.check(config)
    click.echo("ok")


@api_gen.command("generate")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--target", "target_ids", multiple=True, help="仅生成指定 target id")
def generate(config: str = "./api-blueprint.toml", target_ids: tuple[str, ...] = ()) -> None:
    generator.generate(config, target_ids=target_ids)


@api_gen.group("inspect")
def inspect_group() -> None:
    """Query compact ContractGraph views before reading generated source."""


@inspect_group.command("routes")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def inspect_routes(config: str = "./api-blueprint.toml", as_json: bool = False) -> None:
    payload = _inspection_call(lambda: inspection.inspect_routes(config))
    _emit_inspection(payload, as_json=as_json, formatter=_format_inspect_routes)


@inspect_group.command("route")
@click.argument("routes", nargs=-1, required=True)
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def inspect_route(routes: tuple[str, ...], config: str = "./api-blueprint.toml", as_json: bool = False) -> None:
    payload = _inspection_call(
        lambda: inspection.inspect_route(config, routes[0])
        if len(routes) == 1
        else inspection.inspect_routes_detail(config, routes)
    )
    _emit_inspection(payload, as_json=as_json, formatter=_format_inspect_route)


@inspect_group.command("files")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--route", "routes", multiple=True, required=True, help="route id / path / operation")
@click.option("--target", "target_id", required=False, help="target id")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def inspect_files(
    routes: tuple[str, ...],
    config: str = "./api-blueprint.toml",
    target_id: str | None = None,
    as_json: bool = False,
) -> None:
    payload = _inspection_call(
        lambda: inspection.inspect_files(config, routes[0], target_id=target_id)
        if len(routes) == 1
        else inspection.inspect_files_many(config, routes, target_id=target_id)
    )
    _emit_inspection(payload, as_json=as_json, formatter=_format_inspect_files)


@inspect_group.command("schema")
@click.argument("schemas", nargs=-1, required=True)
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def inspect_schema(schemas: tuple[str, ...], config: str = "./api-blueprint.toml", as_json: bool = False) -> None:
    payload = _inspection_call(
        lambda: inspection.inspect_schema(config, schemas[0])
        if len(schemas) == 1
        else inspection.inspect_schemas(config, schemas)
    )
    _emit_inspection(payload, as_json=as_json, formatter=_format_inspect_schema)


@inspect_group.command("errors")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--route", "routes", multiple=True, required=False, help="route id / path / operation")
@click.option("--json", "as_json", is_flag=True, help="输出 JSON")
def inspect_errors(config: str = "./api-blueprint.toml", routes: tuple[str, ...] = (), as_json: bool = False) -> None:
    payload = _inspection_call(
        lambda: inspection.inspect_errors(config, route_query=None)
        if not routes
        else inspection.inspect_errors(config, route_query=routes[0])
        if len(routes) == 1
        else inspection.inspect_errors_many(config, routes)
    )
    _emit_inspection(payload, as_json=as_json, formatter=_format_inspect_errors)


def _echo_diff(diff: dict[str, list[str]]) -> None:
    for label, key in (("BREAKING", "breaking"), ("RISKY", "risky"), ("COMPATIBLE", "compatible")):
        entries = diff.get(key, [])
        if not entries:
            continue
        click.echo(label)
        for entry in entries:
            click.echo(f"- {entry}")


def _inspection_call(callback: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return callback()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _emit_inspection(
    payload: dict[str, Any],
    *,
    as_json: bool,
    formatter: Callable[[dict[str, Any]], list[str]],
) -> None:
    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    for line in formatter(payload):
        click.echo(line)


def _format_explain_target_value(value: object) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_explain_target_scalar(item) for item in value) + "]"
    return _format_explain_target_scalar(value)


def _format_explain_target_scalar(value: object) -> str:
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


def _format_inspect_routes(payload: dict[str, Any]) -> list[str]:
    lines = [f"routes: {payload.get('count', 0)}"]
    for route in _list_of_maps(payload.get("routes")):
        methods = ",".join(str(method) for method in route.get("methods", [])) or "-"
        lines.append(f"- {route.get('id')} {methods} {route.get('url')} ({route.get('kind')})")
        _append_optional_list(lines, "  schemas", route.get("schemas", []))
        _append_optional_list(lines, "  errors", route.get("errors", []))
        _append_optional_list(lines, "  targets", route.get("targets", []))
    return lines


def _format_inspect_route(payload: dict[str, Any]) -> list[str]:
    if isinstance(payload.get("routes"), Sequence) and not isinstance(payload.get("routes"), (str, bytes)):
        lines = [f"routes: {payload.get('count', 0)}"]
        for route in _list_of_maps(payload.get("routes")):
            if len(lines) > 1:
                lines.append("")
            lines.extend(_format_inspect_route(route))
        return lines

    lines = [f"route: {payload.get('id')}"]
    methods = ",".join(str(method) for method in payload.get("methods", [])) or "-"
    lines.append(f"http: {methods} {payload.get('url')}")
    lines.append(f"kind: {payload.get('kind')}")
    lines.append(f"operation: {payload.get('operation')}")
    _append_optional_list(lines, "request", payload.get("request_models", []))
    if payload.get("response_model"):
        lines.append(f"response: {payload.get('response_model')}")
    connection = payload.get("connection")
    if isinstance(connection, Mapping):
        summary = " ".join(
            part
            for part in (
                str(connection.get("kind") or ""),
                f"scope={connection.get('scope')}" if connection.get("scope") else "",
            )
            if part
        )
        if summary:
            lines.append(f"connection: {summary}")
    _append_optional_list(lines, "errors", payload.get("errors", []))
    _append_optional_list(lines, "schemas", payload.get("schemas", []))
    lines.extend(_format_artifacts(payload.get("artifacts", {})))
    return lines


def _format_inspect_files(payload: dict[str, Any]) -> list[str]:
    if isinstance(payload.get("routes"), Sequence) and not isinstance(payload.get("routes"), (str, bytes)):
        lines = [f"routes: {payload.get('count', 0)}"]
        for route in _list_of_maps(payload.get("routes")):
            if len(lines) > 1:
                lines.append("")
            lines.extend(_format_inspect_files(route))
        return lines

    lines = [f"route: {payload.get('route')}"]
    lines.extend(_format_artifacts(payload.get("targets", {})))
    return lines


def _format_inspect_schema(payload: dict[str, Any]) -> list[str]:
    if isinstance(payload.get("schemas"), Sequence) and not isinstance(payload.get("schemas"), (str, bytes)):
        lines = [f"schemas: {payload.get('count', 0)}"]
        for schema in _list_of_maps(payload.get("schemas")):
            if len(lines) > 1:
                lines.append("")
            lines.extend(_format_inspect_schema(schema))
        return lines

    schema = payload.get("schema") if isinstance(payload.get("schema"), Mapping) else {}
    lines = [f"schema: {payload.get('name')}", f"type: {schema.get('type') or schema.get('kind') or 'unknown'}"]
    fields = schema.get("fields")
    if isinstance(fields, Mapping) and fields:
        lines.append("fields:")
        for field_name, field in fields.items():
            field_type = _schema_value_type(field)
            lines.append(f"- {field_name}: {field_type}")
    _append_optional_list(lines, "inbound routes", payload.get("inbound_routes", []))
    return lines


def _format_inspect_errors(payload: dict[str, Any]) -> list[str]:
    if isinstance(payload.get("routes"), Sequence) and not isinstance(payload.get("routes"), (str, bytes)):
        lines = [f"routes: {payload.get('count', 0)}"]
        for route in _list_of_maps(payload.get("routes")):
            if len(lines) > 1:
                lines.append("")
            lines.extend(_format_inspect_errors(route))
        return lines

    lines: list[str] = []
    if payload.get("route"):
        lines.append(f"route: {payload['route']}")
    lines.append(f"errors: {payload.get('count', 0)}")
    for error in _list_of_maps(payload.get("errors")):
        lines.append(f"- {error.get('id')} code={error.get('code')} message={error.get('message')}")
        toast = error.get("toast")
        if isinstance(toast, Mapping):
            lines.append(
                "  toast: "
                f"key={toast.get('key')} "
                f"level={toast.get('level')} "
                f"default={toast.get('default')}"
            )
    return lines


def _format_artifacts(value: object) -> list[str]:
    artifacts = value if isinstance(value, Mapping) else {}
    if not artifacts:
        return []
    lines = ["generated files:"]
    for target_id, artifact in artifacts.items():
        if not isinstance(artifact, Mapping):
            continue
        lines.append(f"[{target_id}]")
        for file_path in artifact.get("files", []):
            lines.append(f"- {file_path}")
        imports = artifact.get("imports", [])
        if imports:
            lines.append("imports:")
            for import_path in imports:
                lines.append(f"- {import_path}")
    return lines


def _append_optional_list(lines: list[str], label: str, values: object) -> None:
    items = [str(item) for item in values] if isinstance(values, Sequence) and not isinstance(values, (str, bytes)) else []
    if items:
        lines.append(f"{label}: {', '.join(items)}")


def _schema_value_type(value: object) -> str:
    if not isinstance(value, Mapping):
        return "unknown"
    if value.get("ref"):
        return str(value["ref"])
    if value.get("enum"):
        return str(value["enum"])
    value_type = str(value.get("type") or value.get("kind") or "unknown")
    if value_type == "array" and isinstance(value.get("items"), Mapping):
        return f"array[{_schema_value_type(value['items'])}]"
    if value_type == "map" and isinstance(value.get("values"), Mapping):
        return f"map[string,{_schema_value_type(value['values'])}]"
    return value_type


def _list_of_maps(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]
