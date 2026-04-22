from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CodegenConfig(BaseModel):
    codegen_output: str | None = None


class UpstreamConfig(BaseModel):
    upstream: str | None = None


class GolangConfig(CodegenConfig, UpstreamConfig):
    module: str | None = None


class TypeScriptConfig(CodegenConfig, UpstreamConfig):
    base_url: str | None = None


class GrpcJobConfig(BaseModel):
    name: str
    preset: Literal["go", "python"]
    output: str
    protos: list[str]
    include_paths: list[str] = Field(default_factory=list)


class GrpcConfig(BaseModel):
    proto_root: str
    include_paths: list[str] = Field(default_factory=list)
    jobs: list[GrpcJobConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_job_names(self) -> "GrpcConfig":
        names = [job.name for job in self.jobs]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"grpc.jobs contains duplicate names: {', '.join(duplicates)}")
        return self


class BlueprintConfig(BaseModel):
    entrypoints: list[str] | None = None
    docs_server: str | None = None
    docs_domain: str | None = None


class Config(BaseModel):
    blueprint: BlueprintConfig | None = None
    golang: GolangConfig | None = None
    typescript: TypeScriptConfig | None = None
    grpc: GrpcConfig | None = None

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        from api_blueprint.config.loader import load_config

        return load_config(path)
