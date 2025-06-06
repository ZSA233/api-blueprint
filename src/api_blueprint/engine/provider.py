from enum import Enum
import typing


if typing.TYPE_CHECKING:
    from api_blueprint.engine.router import Router


class ProviderName(str, Enum):
    REQ         = 'req'
    RSP         = 'rsp'
    AUTH        = 'auth'
    HANDLE      = 'handle'
    WS_HANDLE   = 'ws_handle'


class Provider:
    name: str
    data: str
    
    def __init__(self, data: str = None):
        self.data = data
    
    def __call__(self, *args, **kwargs):
        pass


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
    data: typing.List[str] = []


def ellipsis_replaces(bases: typing.List[Provider], replaces: typing.List[Provider]) -> typing.List[Provider]:
    base_idx = 0
    base_name_idx: typing.Dict[str, int] = {
        b.name: i
        for i, b in enumerate(bases)
    }
    providers: typing.List[Provider] = []
    
    follow: bool = False
    for prov in replaces:
        if prov is ...:
            follow = True
        else:
            if follow:
                idx = base_name_idx.get(prov.name, -1)
                if idx < 0:
                    providers.append(prov)
                else:
                    for i in range(base_idx, idx + 1):
                        providers.append(bases[i])
                
                    base_idx = idx + 1
            else:
                providers.append(prov)
                base_idx += 1
            follow = False
    
    if follow and base_idx <= len(bases):
        for i in range(base_idx, len(bases)):
            providers.append(bases[i])

    return providers