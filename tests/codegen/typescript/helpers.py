from __future__ import annotations

from pathlib import Path

import pytest

from api_blueprint.contract import build_contract_graph

from api_blueprint.engine.binary_schema import parse_binary_schema

from api_blueprint.engine.model import FileField, Model, String

from api_blueprint.engine import Blueprint, ConnectionDelivery, Error, Toast

from api_blueprint.engine.envelope import CodeMessageDataEnvelope

from api_blueprint.writer.core.contracts import route_contract

from api_blueprint.writer.typescript import TypeScriptProtoRegistry, to_ts_identifier, to_ts_name

from api_blueprint.writer.typescript.writer import TypeScriptWriter

class Payload(Model):
    value = String(description="value")

class MediaUpload(Model):
    title = String(description="title")
    image = FileField(content_types=["image/jpeg"], description="image")

def _max_consecutive_blank_lines(text: str) -> int:
    current = 0
    maximum = 0
    for line in text.splitlines():
        if line.strip():
            current = 0
            continue
        current += 1
        maximum = max(maximum, current)
    return maximum

__all__ = [name for name in globals() if not name.startswith('__') or name == '__version__']
