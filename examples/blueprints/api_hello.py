from api_blueprint.includes import *
from blueprints.app import apibp
import enum



class WsMsgTypeEnum(enum.StrEnum):
    PING        = 'ping'
    PONG        = 'pong'
    JOIN        = 'join'
    LEAVE       = 'leave'
    FORGEROUND  = 'forgeround'
    UPGRADE     = 'upgrade'


class ApiHelloMap(Model):
    haha    = Int64(description='haha')


class WsMessage(Model):
    type    = Enum[WsMsgTypeEnum](description='消息类型')
    data    = Field(description='消息内容')


apibp.WS("/ws").SEND(
    WsMessage,
).RECV(
    WsMessage,
)


class MapEnum(enum.StrEnum):
    A = 'a'
    B = 'b'


class HelloWayEnum(enum.StrEnum):
    ASD = "ASD"


with apibp.group('/hello') as views:
    views.GET(
        '/abc', summary='这是abc的summary', description='这是abc的description'
    ).ARGS(
        arg1    = Bool(description='arg1', default=True),
        arg3    = String(description='arg3', omitempty=True),
        arg2    = Float(description='arg2', default=6.666),
        type    = Enum[WsMsgTypeEnum](description='消息类型'),
    ).RSP(Map[String, ApiHelloMap](description="map"))


    views.GET(
        '/map-enum', summary='map-enum', description='map-enum'
    ).RSP(Map[Enum[MapEnum], ApiHelloMap](description='mm'))

    views.GET(
        '/list-enum', summary='list-enum', description='list-enum'
    ).RSP(Array[Enum[MapEnum]](description='mm'))

    views.GET(
        '/string', summary='string', description='string'
    ).RSP(String(description='string'))

    views.GET(
        '/uint64', summary='uint64', description='uint64'
    ).RSP(Uint64(description='uint64'))

    views.GET(
        '/string-emun', summary='string-enum', description='string-enum'
    ).RSP(Enum[MapEnum](description='string-enum'))
    
    views.GET(
        '/hello-way', summary='hello-way', description='hello-way'
    ).ARGS(
        arg1    = Enum[HelloWayEnum](description='hello-way', default=HelloWayEnum.ASD),
    )