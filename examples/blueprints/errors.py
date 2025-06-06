from api_blueprint.includes import *
from api_blueprint.engine.model import Model


class CommonErr(Model):
    UNKNOWN         = Error(-1, '未知错误')
    TOKEN_EXPIRE    = Error(55555, 'token登录态失效')
