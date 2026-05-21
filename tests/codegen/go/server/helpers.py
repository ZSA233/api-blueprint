from __future__ import annotations

import shutil

import subprocess

from pathlib import Path

import pytest

from api_blueprint.contract import build_contract_graph

from api_blueprint.engine import Blueprint, Error, Model, Toast, provider

from api_blueprint.engine.binary_schema import parse_binary_schema

from api_blueprint.engine.model import FileField, String

from api_blueprint.engine.envelope import CodeMessageDataEnvelope

from api_blueprint.writer.golang import GolangResponseEnvelope

from api_blueprint.writer.golang import GolangWriter

from tests.support import REPO_ROOT

PROJECT_ROOT = REPO_ROOT

class MediaUpload(Model):
    title = String(description="title")
    image = FileField(content_types=["image/jpeg"], description="image")

__all__ = [name for name in globals() if not name.startswith('__') or name == '__version__']
