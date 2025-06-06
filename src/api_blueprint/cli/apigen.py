from api_blueprint.config import Config
from api_blueprint.writer import golang
from api_blueprint.helper import load_entrypoints
from api_blueprint.cli.apidoc import run_apidoc_server
from pathlib import Path
import typing
import click


@click.command()
@click.option('-c', '--config', default='./api-blueprint.toml', help='配置文件')
@click.option('-d', '--doc', default=False, is_flag=True, help='是否同时运行docs服务')
def gen_golang(config: typing.Optional[str] = './api-blueprint.toml', doc: bool = False):
    c = Path(config).resolve()
    if c.is_dir():
        c /= 'api-blueprint.toml'
    if not c.exists():
        raise FileNotFoundError(f'[gen_golang] --config 配置文件[{c}]不存在')
    conf = Config.load(c)
    goconf = conf.golang

    relative_path: Path = c.parent
    output = Path(goconf.codegen_output)
    if not output.is_absolute():
        output = (c.parent / output).resolve()
    
    if not output.exists():
        raise FileNotFoundError(f'[gen_golang] --output 输出路径[{output}]不存在')
    
    entrypoints = load_entrypoints(conf.blueprint.entrypoints, relative_path)
    if not entrypoints:
        raise ModuleNotFoundError(f'[gen_golang] 未指定蓝图entrypoints')

    for ep in entrypoints:
        ep.build()

    writer = golang.GolangWriter(
        output,
    )
    writer.register(*entrypoints)
    writer.gen()

    if doc:
        run_apidoc_server(conf, entrypoints)
