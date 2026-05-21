from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api_blueprint.route_selection import validate_selection_rules


WailsVersion = Literal["v2", "v3"]
WailsFrontendMode = Literal["external", "none"]
TargetKind = Literal[
    "contract",
    "go-server",
    "go-client",
    "typescript-client",
    "kotlin-client",
    "kotlin-server",
    "java-server",
    "java-client",
    "flutter-client",
    "python-server",
    "python-client",
    "http-transport",
    "wails-transport",
    "grpc-proto",
    "grpc-go",
    "grpc-python",
]
GO_PACKAGE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def default_wails_overlay_name(version: WailsVersion) -> str:
    return f"wails{version}"


class TargetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: TargetKind
    out_dir: str | None = None
    module: str | None = None
    base_url: str | None = None
    base_url_expr: str | None = None
    package: str | None = None
    formats: list[Literal["index", "json", "markdown", "agent-json", "agent-markdown", "shards"]] = Field(
        default_factory=list
    )
    version: WailsVersion | None = None
    frontend_mode: WailsFrontendMode = "external"
    overlay_name: str | None = None
    server: str | None = None
    clients: list[str] = Field(default_factory=list)
    proto: str | None = None
    source_root: str | None = None
    files: list[str] = Field(default_factory=list)
    import_roots: list[str] = Field(default_factory=list)
    go_package_prefix: str | None = None
    python_package_root: str | None = None
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    proto_files: list["GrpcProtoFileConfig"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target_fields(self) -> "TargetConfig":
        if self.base_url is not None and self.base_url_expr is not None:
            raise ValueError(f"target[{self.id}] base_url and base_url_expr are mutually exclusive")
        if self.kind == "wails-transport":
            if self.version not in {"v2", "v3"}:
                raise ValueError(f"target[{self.id}] wails-transport requires version = 'v2' or 'v3'")
            if self.overlay_name is not None and not GO_PACKAGE_NAME_RE.fullmatch(self.overlay_name):
                raise ValueError(
                    f"target[{self.id}] overlay_name must be Go package-safe: "
                    "lowercase letters, digits, and underscores, and it cannot start with a digit"
                )
        if self.kind in {"kotlin-client", "kotlin-server"} and not self.package:
            raise ValueError(f"target[{self.id}] {self.kind} requires package")
        if self.kind in {"java-client", "java-server"} and not self.package:
            raise ValueError(f"target[{self.id}] {self.kind} requires package")
        if self.kind == "flutter-client" and not self.package:
            raise ValueError(f"target[{self.id}] flutter-client requires package")
        if self.kind == "grpc-proto" and not self.package:
            raise ValueError(f"target[{self.id}] grpc-proto requires package")
        if self.kind != "grpc-proto" and self.proto_files:
            raise ValueError(f"target[{self.id}] proto_files is only supported by grpc-proto targets")
        if self.kind in {"grpc-go", "grpc-python"}:
            if not self.proto and not self.source_root:
                raise ValueError(f"target[{self.id}] {self.kind} requires proto or source_root")
            if not self.out_dir:
                raise ValueError(f"target[{self.id}] {self.kind} requires out_dir")
            if not self.files:
                raise ValueError(f"target[{self.id}] {self.kind} requires files")
        validate_selection_rules(self.include, label=f"target[{self.id}]")
        validate_selection_rules(self.exclude, label=f"target[{self.id}]")
        return self


class GrpcProtoFileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    package: str | None = None
    go_package: str | None = None
    schema_modules: list[str] = Field(default_factory=list)
    schema_names: list[str] = Field(default_factory=list)
    route_paths: list[str] = Field(default_factory=list)
    route_ids: list[str] = Field(default_factory=list)
    service_ids: list[str] = Field(default_factory=list)
    service: str | None = None


class BlueprintConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entrypoints: list[str] | None = None
    docs_server: str | None = None
    docs_domain: str | None = None


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blueprint: BlueprintConfig | None = None
    targets: list[TargetConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_cross_section_contracts(self) -> "Config":
        target_ids = [target.id for target in self.targets]
        duplicate_target_ids = sorted({target_id for target_id in target_ids if target_ids.count(target_id) > 1})
        if duplicate_target_ids:
            raise ValueError(f"targets contains duplicate ids: {', '.join(duplicate_target_ids)}")
        return self

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        from api_blueprint.config.loader import load_config

        return load_config(path)
