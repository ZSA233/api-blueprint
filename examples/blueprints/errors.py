from api_blueprint.includes import *
from api_blueprint.engine.model import Model


class CommonErr(Model):
    UNKNOWN         = Error(-1, '未知错误')
    TOKEN_EXPIRE    = Error(
        55555,
        'token登录态失效',
        toast=Toast(
            key='auth.token_expire',
            default='登录状态已失效，请重新登录',
            level='warning',
        ),
    )


class DemoErr(Model):
    UNKNOWN = Error(70002, 'demo unknown error')
    RATE_LIMITED = Error(
        42901,
        '请求过于频繁',
        toast=Toast(
            key='demo.rate_limited',
            default='请求过于频繁，请稍后再试',
            level='warning',
        ),
    )
