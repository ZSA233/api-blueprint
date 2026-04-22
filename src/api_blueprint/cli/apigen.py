import click

from api_blueprint.application.generation import (
    explain_grpc_target,
    generate_golang,
    generate_grpc,
    generate_typescript,
    list_grpc_jobs,
    list_grpc_targets,
)


@click.command()
@click.option('-c', '--config', default='./api-blueprint.toml', help='配置文件')
@click.option('-d', '--doc', default=False, is_flag=True, help='是否同时运行docs服务')
def gen_golang(config: str = './api-blueprint.toml', doc: bool = False):
    generate_golang(config, doc=doc)


@click.command()
@click.option('-c', '--config', default='./api-blueprint.toml', help='配置文件')
@click.option('-d', '--doc', default=False, is_flag=True, help='是否同时运行docs服务')
def gen_typescript(config: str = './api-blueprint.toml', doc: bool = False):
    generate_typescript(config, doc=doc)


@click.command()
@click.option('-c', '--config', default='./api-blueprint.toml', help='配置文件')
@click.option('--target', 'targets', multiple=True, help='仅生成匹配的 gRPC target，支持 shell-style pattern')
@click.option('--list-targets', default=False, is_flag=True, help='列出配置中的 gRPC targets')
@click.option('--explain-target', default=None, help='解释指定 gRPC target 的生效配置')
@click.option('--job', 'jobs', multiple=True, help='仅生成匹配的 legacy/raw gRPC job，支持 shell-style pattern')
@click.option('--list-jobs', default=False, is_flag=True, help='列出配置中的 legacy/raw gRPC jobs')
def gen_grpc(
    config: str = './api-blueprint.toml',
    targets: tuple[str, ...] = (),
    list_targets: bool = False,
    explain_target: str | None = None,
    jobs: tuple[str, ...] = (),
    list_jobs: bool = False,
):
    if explain_target is not None:
        plan = explain_grpc_target(config, target_id=explain_target)
        click.echo(f"id: {plan.name}")
        click.echo(f"lang: {plan.lang}")
        click.echo(f"effective source_root: {plan.source_root}")
        click.echo(
            "effective import_roots: "
            + (", ".join(path.as_posix() for path in plan.import_roots) if plan.import_roots else "(none)")
        )
        click.echo(f"effective out_dir: {plan.out_dir}")
        click.echo("selected files:")
        for proto_file in plan.proto_files:
            click.echo(f"- {proto_file.as_posix()}")
        if plan.lang == "python":
            sample = plan.proto_files[0] if plan.proto_files else None
            if sample is not None:
                sample_output = plan.out_dir / sample.parent / f"{sample.stem}_pb2.py"
                click.echo(f"example output path: {sample_output.as_posix()}")
        else:
            click.echo(f"module_root: {plan.module_root}")
            click.echo(f"module_path: {plan.module}")
            click.echo(f"expected go_package prefix: {plan.expected_go_package_prefix}")
        return

    listed = False
    if list_targets:
        for target in list_grpc_targets(config, target_filters=targets):
            click.echo(f"{target.id}\t{target.lang}\t{target.out_dir}")
        listed = True
    if list_jobs:
        for job in list_grpc_jobs(config, job_filters=jobs):
            click.echo(f"{job.name}\t{job.preset}\t{job.output}")
        listed = True

    if listed:
        return

    generate_grpc(config, target_filters=targets, job_filters=jobs)
