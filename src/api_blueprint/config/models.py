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
    "python-server",
    "python-client",
    "http-transport",
    "wails-transport",
    "grpc-proto",
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
    formats: list[Literal["json", "markdown"]] = Field(default_factory=list)
    version: WailsVersion | None = None
    frontend_mode: WailsFrontendMode = "external"
    overlay_name: str | None = None
    server: str | None = None
    clients: list[str] = Field(default_factory=list)
    go_package_prefix: str | None = None
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

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
        if self.kind == "kotlin-client" and not self.package:
            raise ValueError(f"target[{self.id}] kotlin-client requires package")
        if self.kind == "grpc-proto" and not self.package:
            raise ValueError(f"target[{self.id}] grpc-proto requires package")
        validate_selection_rules(self.include, label=f"target[{self.id}]")
        validate_selection_rules(self.exclude, label=f"target[{self.id}]")
        return self


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
