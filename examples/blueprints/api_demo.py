from api_blueprint.includes import *
from blueprints.app import apibp


class ApiDemoSubA(Model):
    hello   = Map[String, Int](description='hello')


class ApiDemoA(Model):
    a       = Int(description='a')
    bc      = String(description='bc')
    efg     = Float32(description='efg')
    hijk    = Array[Uint](description='hijk')
    lmnop   = Array[ApiDemoSubA](description='lmnop', omitempty=True)


with apibp.group('/demo') as views:
    views.GET(
        '/abc', summary='这是abc的summary', description='这是abc的description'
    ).ARGS(
        arg1    = Bool(description='arg1', default=True),
        arg2    = Float(description='arg2', default=6.666),
    ).RSP(ApiDemoA)

    views.POST(
        '/test_post', summary='这是post的summary', description='这是post的description'
    ).REQ(
        req1    = String(description='req1'),
        req2    = Int(description='req2', default=2333),
    ).RSP(
        list    = Array[String](description='list')
    )

    views.PUT(
        '/1put', summary='这是put的summary', description='这是put的description'
    ).ARGS(
        arg1    = String(description='arg1', default='put-arg1'),
        arg2    = Float(description='arg2', default=6.666),
    ).REQ(
        req1    = String(description='req1'),
        req2    = Int(description='req2', default=2333),
    ).RSP(
        list    = Array[String](description='list')
    )

    views.DELETE(
        '/delete$', summary='这是delete的summary', description='这是delete的description'
    ).ARGS(
        arg1    = String(description='arg1', default='put-arg1'),
        arg2    = Float(description='arg2', default=6.666),
    ).RSP_XML(
        list    = Array[String](description='list')
    )

    views.WS(
        '/ws', summary='这是ws的summary', description='这是ws的description'
    ).ARGS(ApiDemoSubA)

    views.POST(
        '/post_deprecated', summary='这是一个summary', description='这是一个description', headers=NoneHeader,
    ).REQ(
        req1    = String(description='req1'),
        req2    = Int(description='req2', default=2333),
    ).RSP(
        list    = Array[String](description='list')
    ).DEPRECATED()





