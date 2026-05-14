from __future__ import annotations

import api_blueprint.writer.python  # noqa: F401
from api_blueprint.writer import get_target, iter_targets


def test_generator_registry_exposes_implemented_and_placeholder_targets():
    targets = {target.name: target for target in iter_targets()}
    assert targets["golang"].implemented is True
    assert targets["typescript"].implemented is True
    assert targets["grpc"].implemented is False
    assert targets["grpc-proto"].implemented is True
    assert targets["kotlin"].implemented is True
    assert targets["wails"].implemented is True
    assert targets["python-client"].implemented is True
    assert targets["python-server"].implemented is True
    assert targets["java"].implemented is False
    assert targets["java-client"].implemented is True
    assert targets["java-server"].implemented is True
    assert get_target("golang").writer_factory is not None
    assert get_target("grpc-proto").writer_factory is not None
    assert get_target("kotlin").writer_factory is not None
    assert get_target("wails").writer_factory is not None
    assert get_target("python-client").writer_factory is not None
    assert get_target("python-server").writer_factory is not None
    assert get_target("java-client").writer_factory is not None
    assert get_target("java-server").writer_factory is not None
