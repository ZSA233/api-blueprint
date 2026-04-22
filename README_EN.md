# API Blueprint

[![GitHub Stars](https://img.shields.io/github/stars/zsa233/api-blueprint)](https://github.com/zsa233/api-blueprint/stargazers)
[![License](https://img.shields.io/github/license/zsa233/api-blueprint)](LICENSE)

🌍 Language: [中文](README.md) | English

## Overview

`api-blueprint` is a project that connects a Python DSL, FastAPI/OpenAPI, and multi-language code generation.

Its main workflow is:

1. Describe `Blueprint`, routes, request/response models, and error structures in Python.
2. Build a FastAPI application at runtime and expose OpenAPI documentation.
3. Generate Go and TypeScript code snapshots from the same blueprint source.

## Supported Outputs

| Target | Status | Command | Example Directory |
|:---|:---:|:---|:---|
| Go | Available | `api-gen-golang` | `examples/golang` |
| TypeScript | Preview | `api-gen-typescript` | `examples/typescript` |

Kotlin / Java / grpc are not exposed as public commands yet; they are reserved as internal extension points only.

## Installation

This repository currently maintains a GitHub-only install entrypoint; the stable install path is fixed to the `stable` branch.

```sh
uv pip install "git+https://github.com/zsa233/api-blueprint@stable"
```

## Core Workflow

- Define `Blueprint` objects and route DSLs in directories such as `examples/blueprints/`.
- Build the documentation service with `api-doc-server`, reusing FastAPI OpenAPI output.
- Generate language-side snapshot artifacts with `api-gen-golang` and `api-gen-typescript`.
- Run `uv run python scripts/example_validation.py` to regenerate examples, diff snapshots, compile TypeScript, and run Go tests in one loop.

## Configuration File

```toml
[blueprint]
docs_server = "0.0.0.0:2332"
docs_domain = ""
entrypoints = [
    "blueprints.app:*",
]

[golang]
codegen_output = "golang"
upstream = "http://localhost:2333"
module = ""

[typescript]
codegen_output = "typescript"
upstream = "http://localhost:2333"
base_url = "http://localhost:2333"
```

## Blueprint DSL Example

```python
from api_blueprint.includes import *
from blueprints.app import apibp


class ApiDemoSubA(Model):
    hello = Map[String, Int](description="hello")


class ApiDemoA(Model):
    bc = String(description="bc")
    a = Int(description="a")
    efg = Float32(description="efg")
    hijk = Array[Uint](description="hijk")
    lmnop = Array[ApiDemoSubA](description="lmnop", omitempty=True)


with apibp.group("/demo") as views:
    views.GET(
        "/abc",
        summary="这是 abc 的 summary",
        description="这是 abc 的 description",
    ).ARGS(
        arg1=Bool(description="arg1", default=True),
        arg2=Float(description="arg2", default=6.666),
    ).RSP(ApiDemoA)
```

## CLI Commands

```sh
api-doc-server -c examples/api-blueprint.toml
api-gen-golang -c examples/api-blueprint.toml
api-gen-typescript -c examples/api-blueprint.toml
```

## Generated Artifacts And Repository Rules

- `examples/blueprints/` is the blueprint source of truth.
- `examples/golang/` and `examples/typescript/` are generated snapshots and should not be hand-edited for business logic.
- `Blueprint(app=None)` shares the global `FastAPI` app by default; if you need separate documentation apps, you must pass `app` explicitly.
- `scripts/example_validation.py` regenerates examples in a temporary workspace, then runs snapshot diffs, `tsc --noEmit`, and `go test ./...`.
- `main.py` and `debug.py` are kept only as local helper scripts and are not part of the public release surface.

## Development

```sh
make sync
make test
uv run python scripts/example_validation.py
make build
```

## Release

- The documentation convergence order is fixed as `PRE_README.MD -> README.md -> README_EN.md`.
- The version source of truth is fixed as `release-version.toml` and `src/api_blueprint/_version.py`.
- The stable release workflow is bound to the GitHub `production` environment; if that environment has required reviewers configured, publication pauses for manual approval.
- See [`docs/release-process.md`](docs/release-process.md) for the detailed release rules.

```sh
make release-version-show
make release-preflight RELEASE_TAG=v0.0.1
make release-local RELEASE_TAG=v0.0.1
make release-install-check RELEASE_TAG=v0.0.1
```
