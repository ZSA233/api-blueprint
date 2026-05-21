from __future__ import annotations

import asyncio

import enum

import importlib

import py_compile

import sys

from pathlib import Path

import httpx

import pytest

from api_blueprint.contract import build_contract_graph

from api_blueprint.engine import Blueprint, Error, Toast

from api_blueprint.engine.binary_schema import parse_binary_schema

from api_blueprint.engine.model import Array, Enum, FileField, Map, Model, String

from api_blueprint.writer.python import PythonClientWriter, PythonServerWriter

class Payload(Model):
    value = String(description="value")

class Result(Model):
    status = String(description="status")

class MediaUpload(Model):
    title = String(description="title")
    image = FileField(content_types=["image/jpeg"], description="image")

def _compile_generated_files(root: Path) -> None:
    for path in root.rglob("*.py"):
        py_compile.compile(str(path), doraise=True)

def _import_generated_module(output_dir: Path, module_name: str):
    for name in list(sys.modules):
        if name == "api_blueprint_generated" or name.startswith("api_blueprint_generated."):
            del sys.modules[name]
    sys.path.insert(0, str(output_dir))
    try:
        return importlib.import_module(module_name)
    finally:
        sys.path.remove(str(output_dir))

__all__ = [name for name in globals() if not name.startswith('__') or name == '__version__']
