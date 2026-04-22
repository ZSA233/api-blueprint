from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class CodegenConfig(BaseModel):
    codegen_output: str | None = None


class UpstreamConfig(BaseModel):
    upstream: str | None = None


class GolangConfig(CodegenConfig, UpstreamConfig):
    module: str | None = None


class TypeScriptConfig(CodegenConfig, UpstreamConfig):
    base_url: str | None = None


class BlueprintConfig(BaseModel):
    entrypoints: list[str] | None = None
    docs_server: str | None = None
    docs_domain: str | None = None


class Config(BaseModel):
    blueprint: BlueprintConfig
    golang: GolangConfig
    typescript: TypeScriptConfig | None = None

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        from api_blueprint.config.loader import load_config

        return load_config(path)
