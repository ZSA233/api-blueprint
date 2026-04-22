import click

from api_blueprint.application.generation import generate_golang, generate_grpc, generate_typescript, list_grpc_jobs


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
@click.option('--job', 'jobs', multiple=True, help='仅生成匹配的gRPC job，支持 shell-style pattern')
@click.option('--list-jobs', default=False, is_flag=True, help='列出配置中的gRPC jobs')
def gen_grpc(config: str = './api-blueprint.toml', jobs: tuple[str, ...] = (), list_jobs: bool = False):
    if list_jobs:
        for job in list_grpc_jobs(config, job_filters=jobs):
            click.echo(f"{job.name}\t{job.preset}\t{job.output}")
        return

    generate_grpc(config, job_filters=jobs)
