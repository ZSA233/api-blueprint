from api_blueprint.includes import *
from blueprints.app import apibp
from blueprints.errors import DemoErr
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


class SweepOpen(Model):
    run_id = String(description='run id')
    replay_from = String(description='optional replay cursor', omitempty=True)


class SweepState(Model):
    status = String(description='current sweep state')


class SweepProgress(Model):
    current = Uint64(description='current step')
    total = Uint64(description='total steps')


class SweepLog(Model):
    level = String(description='log level')
    message = String(description='log message')


class ConnectionClose(Model):
    code = Int(description='logical close code')
    reason = String(description='close reason', omitempty=True)
    error = String(description='machine-readable error key', omitempty=True)


class AssistantOpen(Model):
    session_id = String(description='assistant session id')


class AssistantInput(Model):
    text = String(description='user input')


class AssistantCancel(Model):
    reason = String(description='cancel reason', omitempty=True)


class AssistantDelta(Model):
    text = String(description='assistant delta')


class AssistantDone(Model):
    message_id = String(description='final message id')


class RequestOptionsResponse(Model):
    status = String(description='request options status')
    delay_ms = Int(description='applied delay in milliseconds')


class PathEchoPath(Model):
    item = String(description='item path segment')
    badge = String(description='badge path segment')


class PathEchoResponse(Model):
    item = String(description='decoded item path segment')
    badge = String(description='decoded badge path segment')
    combined = String(description='combined path segments')


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

    views.POST(
        '/form-submit',
        operation_id='formSubmit',
        summary='Form body example',
        description='Covers application/x-www-form-urlencoded request generation',
    ).REQ_FORM(
        title   = String(description='title'),
        count   = Int(description='count', default=1),
        enabled = Bool(description='enabled', default=True),
    ).RSP(
        summary = String(description='summary'),
        count   = Int(description='count'),
        enabled = Bool(description='enabled'),
    )

    views.GET(
        '/request-options',
        operation_id='requestOptions',
        summary='Request options conformance endpoint',
        description='Used by generated clients to verify per-call headers and timeout behavior.',
        headers=NoneHeader,
    ).ARGS(
        delay_ms = Int(description='optional server delay in milliseconds', default=0),
    ).RSP(
        RequestOptionsResponse,
    )

    views.GET(
        '/path-echo/{item}/{badge}',
        operation_id='PathEcho',
        summary='Path parameter example',
        description='Covers typed path request generation.',
    ).REQ_PATH(
        PathEchoPath,
    ).RSP(
        PathEchoResponse,
    )

    views.POST(
        '/empty-response',
        summary='Empty response example',
        description='Successful envelope response with no business data.',
    ).RSP_EMPTY()

    views.PUT(
        '/1put', operation_id='putDemo', summary='这是put的summary', description='这是put的description'
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

    views.STREAM(
        '/sweep-events', scope=ConnectionScope.SESSION, summary='Sweep event stream',
        description='Transport-neutral server push stream example'
    ).OPEN(
        SweepOpen
    ).SERVER_MESSAGE(
        'SweepStreamMessage',
        state=SweepState,
        progress=SweepProgress,
        log=SweepLog,
    ).CLOSE(
        ConnectionClose
    )

    views.CHANNEL(
        '/assistant-session', scope=ConnectionScope.SESSION, summary='Assistant channel',
        description='Transport-neutral bidirectional channel example'
    ).OPEN(
        AssistantOpen
    ).CLIENT_MESSAGE(
        'AssistantClientMessage',
        input=AssistantInput,
        cancel=AssistantCancel,
    ).SERVER_MESSAGE(
        'AssistantServerMessage',
        delta=AssistantDelta,
        done=AssistantDone,
        log=SweepLog,
    ).CLOSE(
        ConnectionClose
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
    ).HTTP_RAW_RESPONSE()

    views.POST(
        '/map_model', summary='这是一个raw', description='这是一个raw description', headers=NoneHeader,
    ).RSP(
        Map[Int, ApiDemoMap](description='rsp')
    )

    views.GET(
        '/error-demo',
        summary='Typed error example',
        description='Shows declared, route-local and unknown business errors',
    ).ARGS(
        mode=String(description='ok/token/rate_limit/unknown', default='ok'),
    ).ERR(
        DemoErr,
    ).RSP(
        status=String(description='status'),
    )
