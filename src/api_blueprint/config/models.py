from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


GrpcLayout = Literal["source_relative", "go_package"]


class CodegenConfig(BaseModel):
    codegen_output: str | None = None


class UpstreamConfig(BaseModel):
    upstream: str | None = None


class GolangConfig(CodegenConfig, UpstreamConfig):
    module: str | None = None


class TypeScriptConfig(CodegenConfig, UpstreamConfig):
    base_url: str | None = None
    base_url_expr: str | None = None

    @model_validator(mode="after")
    def validate_base_url_fields(self) -> "TypeScriptConfig":
        if self.base_url is not None and self.base_url_expr is not None:
            raise ValueError("typescript.base_url and typescript.base_url_expr are mutually exclusive")
        return self


class GrpcJobConfig(BaseModel):
    name: str
    preset: Literal["go", "python"]
    output: str
    proto_root: str | None = None
    protos: list[str]
    include_paths: list[str] = Field(default_factory=list)
    layout: GrpcLayout = "source_relative"
    module: str | None = None

    @model_validator(mode="after")
    def validate_layout_options(self) -> "GrpcJobConfig":
        if self.preset == "python":
            if self.layout == "go_package":
                raise ValueError("grpc python jobs do not support layout=go_package")
            if self.module is not None:
                raise ValueError("grpc python jobs do not support module")
            return self

        if self.module is not None and self.layout != "go_package":
            raise ValueError("grpc go jobs can only set module when layout=go_package")
        return self


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
