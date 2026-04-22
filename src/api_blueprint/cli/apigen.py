import click

from api_blueprint.application.generation import generate_golang, generate_typescript


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
