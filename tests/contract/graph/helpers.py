from __future__ import annotations

import pytest

from api_blueprint.contract import (
    RouteContract,
    build_agent_manifest,
    build_contract_graph,
    build_contract_shards,
    render_agent_markdown,
    route_contract,
)

from api_blueprint.engine import Blueprint, Error, Toast

from api_blueprint.engine.binary_schema import parse_binary_schema

from api_blueprint.engine.connection import ConnectionDelivery, ConnectionScope

from api_blueprint.engine.model import FileField, Int, String, Model, field

from api_blueprint.writer.core import contracts as legacy_contracts

from api_blueprint.writer.core.contract_adapters import RouteContractIndex

class OpenRequest(Model):
    run_id = String(description="run id")

class StreamState(Model):
    status = String(description="status")

class StreamDone(Model):
    message = String(description="message")

class CloseInfo(Model):
    code = Int(description="code")
    reason = String(description="reason", omitempty=True)

class GenericContractPayload(Model):
    name = field(1, String(description="name"), optional=True)
    success = field(2, String(description="success"), choice="result")
    error = field(3, String(description="error"), choice="result")

class MediaUpload(Model):
    title = String(description="title")
    file = FileField(content_types=["image/jpeg"], max_size=1024, description="file")

__all__ = [name for name in globals() if not name.startswith('__') or name == '__version__']
