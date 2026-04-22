from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api_blueprint.engine.blueprint.router import Router


class ProviderName(str, Enum):
    REQ = "req"
    RSP = "rsp"
    AUTH = "auth"
    HANDLE = "handle"
    WS_HANDLE = "ws_handle"


class Provider:
    name: str
    data: Any

    def __init__(self, data: Any = None):
        self.data = data

    def __call__(self, *args: Any, **kwargs: Any):
        return None


class Req(Provider):
    name = ProviderName.REQ.value


class Rsp(Provider):
    name = ProviderName.RSP.value


class Auth(Provider):
    name = ProviderName.AUTH.value


class Handle(Provider):
    name = ProviderName.HANDLE.value


class WsHandle(Provider):
    name = ProviderName.WS_HANDLE.value
    data: list[str] = []


def ellipsis_replaces(bases: list[Provider], replaces: list[Provider]) -> list[Provider]:
    base_idx = 0
    base_name_idx = {
        base.name: index
        for index, base in enumerate(bases)
    }
    providers: list[Provider] = []

    follow = False
    for provider in replaces:
        if provider is ...:
            follow = True
            continue

        if follow:
            idx = base_name_idx.get(provider.name, -1)
            if idx < 0:
                providers.append(provider)
            else:
                for i in range(base_idx, idx + 1):
                    providers.append(bases[i])
                base_idx = idx + 1
        else:
            providers.append(provider)
            base_idx += 1
        follow = False

    if follow and base_idx <= len(bases):
        for i in range(base_idx, len(bases)):
            providers.append(bases[i])

    return providers
