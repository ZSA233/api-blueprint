import click

from api_blueprint.application.docs import run_docs_server as run_apidoc_server
from api_blueprint.application.project import build_entrypoints, load_project


@click.command()
@click.option('-c', '--config', default='./api-blueprint.toml', help='配置文件')
def apidoc_server(config: str = './api-blueprint.toml'):
    project = load_project(config, command="apidoc_server")
    if not project.entrypoints:
        raise ModuleNotFoundError('[apidoc_server] 未指定蓝图entrypoints')
    build_entrypoints(project.entrypoints)
    run_apidoc_server(project.config, project.entrypoints)
