from __future__ import annotations

from dataclasses import dataclass

from api_blueprint.engine.connection import MessageContract, ModelRef
from api_blueprint.engine.binary_schema import BinarySchema
from api_blueprint.engine.wrapper import ResponseWrapper


@dataclass(frozen=True)
class ContractRouteRuntime:
    query_model: ModelRef | None
    json_model: ModelRef | None
    form_model: ModelRef | None
    binary_model: ModelRef | None
    binary_schema: BinarySchema | None
    open_model: ModelRef | None
    response_model: ModelRef | None
    response_media_type: str
    response_wrapper: type[ResponseWrapper]
    recvs: tuple[ModelRef, ...]
    sends: tuple[ModelRef, ...]
    server_message: MessageContract | None
    client_message: MessageContract | None
    close_model: ModelRef | None
