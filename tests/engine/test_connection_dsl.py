import pytest

from api_blueprint.engine import Blueprint, ConnectionDelivery, ConnectionScope, DefaultConnectionClose
from api_blueprint.engine.model import Model, String
from api_blueprint.writer.core.contracts import route_contract


class Open(Model):
    value = String(description="value")


class ServerMessage(Model):
    value = String(description="value")


class ClientMessage(Model):
    value = String(description="value")


class CloseMessage(Model):
    value = String(description="value")


def test_stream_rejects_client_message():
    bp = Blueprint(root="/api")
    route = bp.STREAM("/events").OPEN(Open).SERVER_MESSAGE(ServerMessage)

    with pytest.raises(ValueError, match="STREAM.*CLIENT_MESSAGE"):
        route.CLIENT_MESSAGE(ClientMessage)


def test_channel_requires_both_message_directions():
    bp = Blueprint(root="/api")
    route = bp.CHANNEL("/chat").OPEN(Open).SERVER_MESSAGE(ServerMessage)

    with pytest.raises(ValueError, match="requires CLIENT_MESSAGE"):
        route.validate_connection_contract()


def test_channel_requires_server_message():
    bp = Blueprint(root="/api")
    route = bp.CHANNEL("/chat").OPEN(Open).CLIENT_MESSAGE(ClientMessage)

    with pytest.raises(ValueError, match="requires SERVER_MESSAGE"):
        route.validate_connection_contract()


def test_message_direction_can_only_be_declared_once():
    bp = Blueprint(root="/api")
    route = bp.STREAM("/events").OPEN(Open).SERVER_MESSAGE(ServerMessage)

    with pytest.raises(ValueError, match="SERVER_MESSAGE.*once"):
        route.SERVER_MESSAGE(ServerMessage)


def test_client_message_can_only_be_declared_once():
    bp = Blueprint(root="/api")
    route = bp.CHANNEL("/chat").CLIENT_MESSAGE(ClientMessage).SERVER_MESSAGE(ServerMessage)

    with pytest.raises(ValueError, match="CLIENT_MESSAGE.*once"):
        route.CLIENT_MESSAGE(ClientMessage)


def test_close_model_can_only_be_declared_once():
    bp = Blueprint(root="/api")
    route = bp.STREAM("/events").SERVER_MESSAGE(ServerMessage).CLOSE(CloseMessage)

    with pytest.raises(ValueError, match="CLOSE.*once"):
        route.CLOSE(CloseMessage)


def test_multi_variant_message_requires_named_keyword_variants():
    bp = Blueprint(root="/api")

    with pytest.raises(ValueError, match="single messages require exactly one model argument"):
        bp.STREAM("/events").SERVER_MESSAGE(ServerMessage, ClientMessage)

    with pytest.raises(ValueError, match="at least one keyword variant"):
        bp.STREAM("/events-with-name").SERVER_MESSAGE("ServerUnion")

    route = bp.STREAM("/events2").SERVER_MESSAGE("ServerUnion", state=ServerMessage)
    assert route.server_message is not None
    assert route.server_message.name == "ServerUnion"
    assert route.server_message.variants[0].key == "state"


def test_connection_scope_accepts_declared_scope_values():
    bp = Blueprint(root="/api")
    route = bp.STREAM("/events", scope=ConnectionScope.TOPIC).SERVER_MESSAGE(ServerMessage)

    assert route.connection_scope == ConnectionScope.TOPIC


def test_connection_routes_default_to_ordered_delivery():
    bp = Blueprint(root="/api")
    stream = bp.STREAM("/events").SERVER_MESSAGE(ServerMessage)
    channel = bp.CHANNEL("/chat").SERVER_MESSAGE(ServerMessage).CLIENT_MESSAGE(ClientMessage)

    assert stream.connection_delivery == ConnectionDelivery.ORDERED
    assert channel.connection_delivery == ConnectionDelivery.ORDERED


def test_connection_delivery_accepts_declared_delivery_values():
    bp = Blueprint(root="/api")
    route = bp.STREAM("/events", delivery="unordered").SERVER_MESSAGE(ServerMessage)

    assert route.connection_delivery == ConnectionDelivery.UNORDERED


def test_connection_route_contract_carries_declared_scope():
    bp = Blueprint(root="/api")
    route = bp.CHANNEL("/chat", scope=ConnectionScope.APP).SERVER_MESSAGE(ServerMessage).CLIENT_MESSAGE(ClientMessage)

    contract = route_contract(route)

    assert contract.connection_scope == ConnectionScope.APP
    assert contract.channel is not None
    assert contract.channel.scope == ConnectionScope.APP


def test_connection_route_contract_carries_declared_delivery():
    bp = Blueprint(root="/api")
    route = (
        bp.CHANNEL("/chat", delivery=ConnectionDelivery.UNORDERED)
        .SERVER_MESSAGE(ServerMessage)
        .CLIENT_MESSAGE(ClientMessage)
    )

    contract = route_contract(route)

    assert contract.connection_delivery == ConnectionDelivery.UNORDERED
    assert contract.channel is not None
    assert contract.channel.delivery == ConnectionDelivery.UNORDERED


def test_connection_uses_default_close_model_when_not_declared():
    bp = Blueprint(root="/api")
    route = bp.STREAM("/events").SERVER_MESSAGE(ServerMessage)

    contract = route_contract(route)

    assert route.close_model is None
    assert route.effective_close_model is DefaultConnectionClose
    assert contract.connection_close_model is DefaultConnectionClose
    assert contract.stream is not None
    assert contract.stream.close_model is DefaultConnectionClose


def test_connection_route_contract_carries_declared_close_model():
    bp = Blueprint(root="/api")
    route = bp.CHANNEL("/chat").SERVER_MESSAGE(ServerMessage).CLIENT_MESSAGE(ClientMessage).CLOSE(CloseMessage)

    contract = route_contract(route)

    assert route.effective_close_model is CloseMessage
    assert contract.connection_close_model is CloseMessage
    assert contract.channel is not None
    assert contract.channel.close_model is CloseMessage


def test_legacy_ws_dsl_is_not_exposed():
    bp = Blueprint(root="/api")
    group = bp.group("/demo")
    route = bp.CHANNEL("/chat")

    assert not hasattr(bp, "WS")
    assert not hasattr(group, "WS")
    assert not hasattr(route, "RECV")
    assert not hasattr(route, "SEND")
