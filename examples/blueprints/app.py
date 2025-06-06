from api_blueprint.includes import * 

from blueprints.errors import CommonErr
from blueprints.headers import GeneralHeader


apibp = Blueprint(
    root='/api',
    tags=['api'],
    providers=[
        provider.Req(),
        provider.Auth(),
        provider.Handle(),
        provider.Rsp(),
    ],
    errors=[
        CommonErr,
    ],
    response_wrapper=GeneralWrapper,
    headers=GeneralHeader,
)


staticbp = Blueprint(
    root='/static',
    tags=['static'],
    providers=[
        provider.Req(),
        provider.Handle(),
        provider.Rsp(),
    ],
    response_wrapper=NoneWrapper,
)