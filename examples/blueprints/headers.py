from api_blueprint.includes import *


class GeneralHeader(HeaderModel):
    x_token     = APIKeyHeader(name="x-token", description='登录态token')