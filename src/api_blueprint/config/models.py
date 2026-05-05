from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api_blueprint.config.grpc_python_package import validate_python_package_root
from api_blueprint.route_selection import validate_selection_rules


GrpcLayout = Literal["source_relative", "go_package"]
TransportKind = Literal["http", "wails"]
WailsVersion = Literal["v2", "v3"]
WailsFrontendMode = Literal["external", "none"]
GO_PACKAGE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
WAILS_OVERLAY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def default_wails_overlay_name(version: WailsVersion) -> str:
    return f"wails{version}"


class CodegenConfig(BaseModel):
    codegen_output: str | None = None


class UpstreamConfig(BaseModel):
    upstream: str | None = None


class GolangConfig(CodegenConfig, UpstreamConfig):
    module: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_golang_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if "provider_package" in data:
            raise ValueError(
                "golang.provider_package has been removed. The shared Go provider runtime "
                "is always generated at views/providers."
            )
        if "transport_adapters" in data:
            raise ValueError(
                "golang.transport_adapters has been replaced by [[transport.targets]]. "
                "Use no transport section for the default HTTP target, or add explicit "
                "transport targets with kind = 'http' / kind = 'wails'."
            )
        return data


class TypeScriptConfig(CodegenConfig, UpstreamConfig):
    base_url: str | None = None
    base_url_expr: str | None = None

    @model_validator(mode="after")
    def validate_base_url_fields(self) -> "TypeScriptConfig":
        if self.base_url is not None and self.base_url_expr is not None:
            raise ValueError("typescript.base_url and typescript.base_url_expr are mutually exclusive")
        return self


class KotlinConfig(CodegenConfig, UpstreamConfig):
    package: str
    base_url: str | None = None
    base_url_expr: str | None = None
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    client: Literal["okhttp"] = "okhttp"
    serialization: Literal["kotlinx"] = "kotlinx"
    allow_empty: bool = False

    @model_validator(mode="after")
    def validate_kotlin_fields(self) -> "KotlinConfig":
        if self.base_url is not None and self.base_url_expr is not None:
            raise ValueError("kotlin.base_url and kotlin.base_url_expr are mutually exclusive")
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


class WailsTargetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: WailsVersion
    overlay_name: str | None = None
    frontend_mode: WailsFrontendMode = "external"
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_output_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        legacy_fields = [name for name in ("go_out_dir", "typescript_out_dir") if name in data]
        if not legacy_fields:
            return data

        names = ", ".join(legacy_fields)
        raise ValueError(
            "wails.targets no longer supports legacy output fields "
            f"[{names}]. Use shared [golang]/[typescript] outputs plus "
            "`overlay_name`, `frontend_mode`, `include`, and `exclude` on each Wails target."
        )

    @model_validator(mode="after")
    def validate_overlay_contract(self) -> "WailsTargetConfig":
        if self.overlay_name is not None and not GO_PACKAGE_NAME_RE.fullmatch(self.overlay_name):
            raise ValueError(
                "wails.targets overlay_name must be Go package-safe: "
                "lowercase letters, digits, and underscores, and it cannot start with a digit"
            )

        validate_selection_rules(self.include, label="[gen_wails]")
        validate_selection_rules(self.exclude, label="[gen_wails]")
        return self


class WailsConfig(BaseModel):
    targets: list[WailsTargetConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_targets(self) -> "WailsConfig":
        if not self.targets:
            raise ValueError("wails section must define at least one wails.targets entry")

        target_ids = [target.id for target in self.targets]
        duplicate_ids = sorted({target_id for target_id in target_ids if target_ids.count(target_id) > 1})
        if duplicate_ids:
            raise ValueError(f"wails.targets contains duplicate ids: {', '.join(duplicate_ids)}")

        overlay_names = [target.overlay_name or default_wails_overlay_name(target.version) for target in self.targets]
        duplicate_overlay_names = sorted(
            {name for name in overlay_names if overlay_names.count(name) > 1}
        )
        if duplicate_overlay_names:
            raise ValueError(
                "wails.targets contains duplicate overlay_name values after defaults: "
                + ", ".join(duplicate_overlay_names)
            )

        return self


class TransportTargetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: TransportKind
    version: WailsVersion | None = None
    overlay_name: str | None = None
    frontend_mode: WailsFrontendMode = "external"
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target_contract(self) -> "TransportTargetConfig":
        if self.kind == "http":
            if self.version is not None:
                raise ValueError("transport.targets with kind='http' must not set version")
            if self.overlay_name is not None:
                raise ValueError("transport.targets with kind='http' must not set overlay_name")
            if self.include or self.exclude:
                raise ValueError("transport.targets with kind='http' does not support include/exclude filters")
            return self

        if self.version is None:
            raise ValueError("transport.targets with kind='wails' requires version = 'v2' or 'v3'")
        if self.overlay_name is not None and not GO_PACKAGE_NAME_RE.fullmatch(self.overlay_name):
            raise ValueError(
                "transport.targets overlay_name must be Go package-safe: "
                "lowercase letters, digits, and underscores, and it cannot start with a digit"
            )
        validate_selection_rules(self.include, label="[gen_wails]")
        validate_selection_rules(self.exclude, label="[gen_wails]")
        return self


class TransportConfig(BaseModel):
    targets: list[TransportTargetConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_targets(self) -> "TransportConfig":
        target_ids = [target.id for target in self.targets]
        duplicate_ids = sorted({target_id for target_id in target_ids if target_ids.count(target_id) > 1})
        if duplicate_ids:
            raise ValueError(f"transport.targets contains duplicate ids: {', '.join(duplicate_ids)}")

        overlay_names = [
            target.overlay_name or default_wails_overlay_name(target.version)
            for target in self.targets
            if target.kind == "wails" and target.version is not None
        ]
        duplicate_overlay_names = sorted({name for name in overlay_names if overlay_names.count(name) > 1})
        if duplicate_overlay_names:
            raise ValueError(
                "transport.targets contains duplicate Wails overlay_name values after defaults: "
                + ", ".join(duplicate_overlay_names)
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
    kotlin: KotlinConfig | None = None
    grpc: GrpcConfig | None = None
    transport: TransportConfig | None = None
    wails: WailsConfig | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_wails_section(cls, data: object) -> object:
        if isinstance(data, dict) and "wails" in data:
            raise ValueError(
                "[wails] / [[wails.targets]] has been replaced by [[transport.targets]] "
                "with kind = 'wails'."
            )
        return data

    @model_validator(mode="after")
    def validate_cross_section_contracts(self) -> "Config":
        if self.wails is not None:
            raise ValueError(
                "[wails] / [[wails.targets]] has been replaced by [[transport.targets]] "
                "with kind = 'wails'."
            )
        return self

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        from api_blueprint.config.loader import load_config

        return load_config(path)
