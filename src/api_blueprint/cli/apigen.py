from __future__ import annotations

from pathlib import Path

import click

from api_blueprint.application import vnext


@click.group()
def api_gen() -> None:
    """Unified api-blueprint vNext generator."""


@api_gen.command("list-targets")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
def list_targets(config: str = "./api-blueprint.toml") -> None:
    for target in vnext.list_targets(config):
        click.echo(f"{target.id}\t{target.kind}\t{target.out_dir or ''}")


@api_gen.command("explain-target")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--target", "target_id", required=True, help="target id")
def explain_target(config: str = "./api-blueprint.toml", target_id: str = "") -> None:
    target = vnext.explain_target(config, target_id)
    click.echo(f"id: {target.id}")
    click.echo(f"kind: {target.kind}")
    click.echo(f"out_dir: {target.out_dir or '(none)'}")
    if target.server is not None:
        click.echo(f"server: {target.server}")
    if target.clients:
        click.echo(f"clients: {', '.join(target.clients)}")
    if target.package is not None:
        click.echo(f"package: {target.package}")
    if target.module is not None:
        click.echo(f"module: {target.module}")
    if target.proto is not None:
        click.echo(f"proto: {target.proto}")
    if target.source_root is not None:
        click.echo(f"source_root: {target.source_root}")
    if target.files:
        click.echo(f"files: {', '.join(target.files)}")
    if target.import_roots:
        click.echo(f"import_roots: {', '.join(path.as_posix() for path in target.import_roots)}")
    if target.go_package_prefix is not None:
        click.echo(f"go_package_prefix: {target.go_package_prefix}")
    if target.python_package_root is not None:
        click.echo(f"python_package_root: {target.python_package_root}")


@api_gen.command("manifest")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path), help="manifest 输出路径")
def manifest(config: str = "./api-blueprint.toml", out_path: Path | None = None) -> None:
    if out_path is None:
        raise ValueError("--out is required")
    vnext.write_manifest(config, out_path)


@api_gen.command("diff")
@click.argument("before", type=click.Path(path_type=Path))
@click.argument("after", type=click.Path(path_type=Path))
def diff_command(before: Path, after: Path) -> None:
    diff = vnext.diff_files(before, after)
    _echo_diff(diff)
    if diff["breaking"]:
        raise click.exceptions.Exit(1)


@api_gen.command("check")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
def check(config: str = "./api-blueprint.toml") -> None:
    vnext.check(config)
    click.echo("ok")


@api_gen.command("generate")
@click.option("-c", "--config", default="./api-blueprint.toml", help="配置文件")
@click.option("--target", "target_ids", multiple=True, help="仅生成指定 target id")
def generate(config: str = "./api-blueprint.toml", target_ids: tuple[str, ...] = ()) -> None:
    vnext.generate(config, target_ids=target_ids)


def _echo_diff(diff: dict[str, list[str]]) -> None:
    for label, key in (("BREAKING", "breaking"), ("RISKY", "risky"), ("COMPATIBLE", "compatible")):
        entries = diff.get(key, [])
        if not entries:
            continue
        click.echo(label)
        for entry in entries:
            click.echo(f"- {entry}")
