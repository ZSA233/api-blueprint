from api_blueprint.includes import *
from blueprints.app import apibp
import enum




class ColorEnum(enum.StrEnum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class StatusEnum(enum.IntEnum):
    PENDING = 1
    RUNNING = 2
    FINISHED = 3


class ApiDemoSubA(Model):
    hello   = Map[String, Int](description='hello')
    amap    = Array['ApiDemoMap'](description='amap')


class ApiDemoA(Model):
    bc          = String(description='bc')
    a           = Int(description='a')
    efg         = Float32(description='efg')
    hijk        = Array[Uint](description='hijk')
    lmnop       = Array[ApiDemoSubA](description='lmnop', omitempty=True)
    enum_color  = Enum[ColorEnum](description='color', omitempty=True)
    enum_status = Enum[StatusEnum](description='status')
    enum_list   = Array[Enum[StatusEnum]](description='status')


class ApiDemoMap(Model):
    haha    = Int64(description='haha')


class WSRecv(Model):
    data    = String(description='data')

class WSSend(Model):
    ws_recv = WSRecv(description='ws_recv')


T = TypeVar('T')

class WSResponse(Model, Generic[T]):
    code        = Int(description='code')
    msg         = String(description='msg')
    data: T     = Field(description='data')


with apibp.group('/demo') as views:
    views.GET(
        '/abc', summary='这是abc的summary', description='这是abc的description'
    ).ARGS(
        arg1    = Bool(description='arg1', default=True),
        arg3    = String(description='arg3', omitempty=True),
        arg2    = Float(description='arg2', default=6.666),
    ).RSP(ApiDemoA)

    views.POST(
        '/test_post', summary='这是post的summary', description='这是post的description'
    ).REQ(
        req1    = String(description='req1'),
        req2    = Int(description='req2', default=2333),
    ).RSP(
        list    = Array[String](description='list'),
        map     = Map[String, ApiDemoMap](description='map')
    )

    views.PUT(
        '/1put', summary='这是put的summary', description='这是put的description'
    ).ARGS(
        arg1    = String(description='arg1', default='put-arg1'),
        arg2    = Float(description='arg2', default=6.666),
        arg3    = String(description='arg3', omitempty=True),
    ).REQ(
        req1    = String(description='req1'),
        req2    = Int(description='req2', default=2333),
    ).RSP(
        list        = Array[String](description='list'),
        anon_kv     = KV(
            kv1 = Uint(description='kv1'),
            kv2 = Array[Float64](description='kv2'),
        )
    )

    views.DELETE(
        '/delete$', summary='这是delete的summary', description='这是delete的description'
    ).ARGS(
        arg1    = String(description='arg1', default='put-arg1'),
        arg2    = Float(description='arg2', default=6.666),
    ).RSP_XML(
        list    = Array[String](description='list'),
        anon_list = ArrayKV(
            kv1 = Int64(description='kv1'),
            kv2 = Array[String](description='kv2'),
        ),
    )

    views.WS(
        '/ws', summary='这是ws的summary', description='这是ws的description'
    ).ARGS(
        ApiDemoSubA
    ).RECV(
        WSRecv,
    ).SEND(
        WSResponse[WSSend],
    )

    views.POST(
        '/post_deprecated', summary='这是一个summary', description='这是一个description', headers=NoneHeader,
    ).REQ(
        req1    = String(description='req1'),
        req2    = Int(description='req2', default=2333),
    ).RSP(
        list    = Array[String](description='list')
    ).DEPRECATED()


    views.POST(
        '/raw', summary='这是一个raw', description='这是一个raw description', headers=NoneHeader,
    ).RSP(
        list    = Array[String](description='list'),
        list2   = Map[Int64, Array[ApiDemoA]](description='list2'),
    )

    views.POST(
        '/map_model', summary='这是一个raw', description='这是一个raw description', headers=NoneHeader,
    ).RSP(
        Map[Int, ApiDemoMap](description='rsp')
    )
