from __future__ import annotations

import shutil

import subprocess

from api_blueprint.contract import build_contract_graph

from api_blueprint.engine import Blueprint, Error, CodeMessageDataEnvelope, Model, Toast

from api_blueprint.engine.binary_schema import parse_binary_schema

from api_blueprint.engine.model import FileField, String

from api_blueprint.writer.golang.client import GolangClientWriter

class MediaUpload(Model):
    title = String(description="title")
    image = FileField(content_types=["image/jpeg"], description="image")

__all__ = [name for name in globals() if not name.startswith('__') or name == '__version__']
