

from pydantic import BaseModel, Field
from pathlib import Path
import typing
import sys

if sys.version_info >= (3, 11):
    import tomllib as toml
else:
    import tomli as toml



class Config(BaseModel):
    blueprint: 'BlueprintConfig'

    golang: 'GolangConfig'

    @classmethod
    def load(cls, path: typing.Optional[typing.Union[str, Path]]) -> 'Config':
        with open(path, 'rb') as f:
            conf = toml.load(f)
        return cls(**conf)
    

class CodegenConfig(BaseModel):
    codegen_output: typing.Optional[str] = None


class UpstreamConfig(BaseModel):
    upstream: typing.Optional[str] = None


class GolangConfig(CodegenConfig, UpstreamConfig):
    pass


class BlueprintConfig(BaseModel):
    entrypoints: typing.Optional[typing.List[str]] = None
    docs_server: typing.Optional[str] = None
    docs_domain: typing.Optional[str] = None