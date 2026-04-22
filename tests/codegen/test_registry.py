from __future__ import annotations

from api_blueprint.writer import get_target, iter_targets


def test_generator_registry_exposes_implemented_and_placeholder_targets():
    targets = {target.name: target for target in iter_targets()}
    assert targets["golang"].implemented is True
    assert targets["typescript"].implemented is True
    assert targets["kotlin"].implemented is False
    assert targets["java"].implemented is False
    assert targets["grpc"].implemented is False
    assert get_target("golang").writer_factory is not None
