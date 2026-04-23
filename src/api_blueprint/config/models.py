from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api_blueprint.config.grpc_python_package import validate_python_package_root


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


class GrpcTargetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lang: Literal["go", "python"]
    out_dir: str
    files: list[str]
    source_root: str | None = None
    import_roots: list[str] = Field(default_factory=list)
    python_package_root: str | None = None

    @model_validator(mode="after")
    def validate_python_package_root(self) -> "GrpcTargetConfig":
        if self.python_package_root is None:
            return self
        if self.lang != "python":
            raise ValueError("grpc python_package_root is only supported for python targets")
        validate_python_package_root(self.python_package_root)
        return self


class GrpcConfig(BaseModel):
    source_root: str | None = None
    import_roots: list[str] = Field(default_factory=list)
    targets: list[GrpcTargetConfig] = Field(default_factory=list)
    proto_root: str | None = None
    include_paths: list[str] = Field(default_factory=list)
    jobs: list[GrpcJobConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entries(self) -> "GrpcConfig":
        if not self.targets and not self.jobs:
            raise ValueError("grpc section must define at least one grpc.targets or grpc.jobs entry")

        names = [job.name for job in self.jobs]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"grpc.jobs contains duplicate names: {', '.join(duplicates)}")

        target_ids = [target.id for target in self.targets]
        duplicate_ids = sorted({target_id for target_id in target_ids if target_ids.count(target_id) > 1})
        if duplicate_ids:
            raise ValueError(f"grpc.targets contains duplicate ids: {', '.join(duplicate_ids)}")

        target_root = self.source_root or self.proto_root
        if self.targets and target_root is None:
            missing_target_roots = [target.id for target in self.targets if target.source_root is None]
            if missing_target_roots:
                raise ValueError(
                    "grpc.targets requires grpc.source_root (or grpc.proto_root for fallback) "
                    f"when targets omit source_root: {', '.join(missing_target_roots)}"
                )

        job_root = self.proto_root or self.source_root
        if self.jobs and job_root is None:
            missing_job_roots = [job.name for job in self.jobs if job.proto_root is None]
            if missing_job_roots:
                raise ValueError(
                    "legacy grpc.jobs requires grpc.proto_root (or grpc.source_root for fallback) "
                    f"when jobs omit proto_root: {', '.join(missing_job_roots)}"
                )

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
