import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:api_blueprint_example/api.dart' as api;
import 'package:api_blueprint_example/alt.dart' as alt;
import 'package:test/test.dart';

void main() {
  final baseUrl = Platform.environment['API_BLUEPRINT_BASE_URL'];
  final selected = _scenarioSet(Platform.environment['API_BLUEPRINT_SCENARIOS'] ??
      'rpc,binary,form,error,sse,websocket,naming,raw,xml,static,header,scalar,enum,map,deprecated,audit-binary,binary-response,media,single-channel');

  if (baseUrl == null || baseUrl.isEmpty) {
    test('conformance requires API_BLUEPRINT_BASE_URL', () {
      markTestSkipped('API_BLUEPRINT_BASE_URL is not set');
    });
    return;
  }

  late api.ApiClient client;
  late alt.ApiClient altClient;

  setUpAll(() {
    client = api.createHttpApiClient(config: api.HttpApiConfig(baseUrl: baseUrl));
    altClient = alt.createHttpApiClient(config: alt.HttpApiConfig(baseUrl: baseUrl));
  });

  if (selected.contains('rpc')) {
    test('RPC routes interoperate with Go server', () async {
      final post = await client.demo.testPost(json: const api.DemoTestPostJson(req1: 'flutter', req2: 7));
      expect(post.list, ['test_post', 'flutter']);
      expect(post.map?['req2']?.haha, 7);

      final put = await client.demo.putDemo(
        query: const api.DemoPutDemoQuery(arg1: 'query', arg2: 3.5),
        json: const api.DemoPutDemoJson(req1: 'body', req2: 9),
      );
      expect(put.list, ['query', 'body']);
      expect(put.anonKv?.kv1, 9);
    });
  }

  if (selected.contains('raw')) {
    test('raw response routes interoperate with Go server', () async {
      await _rawHttp(baseUrl, 'POST', '/api/demo/raw');
    });
  }

  if (selected.contains('xml')) {
    test('XML response route returns a stable payload', () async {
      final body = await _rawHttp(baseUrl, 'DELETE', '/api/demo/delete\$?arg1=flutter-xml&arg2=7');
      expect(body, contains('flutter-xml'));
    });
  }

  if (selected.contains('static')) {
    test('static no-envelope routes return stable payloads', () async {
      await _rawHttp(baseUrl, 'GET', '/static/doc.json');
      final body = await _rawHttp(baseUrl, 'GET', '/static/dochaha');
      expect(body, contains('hello world'));
    });
  }

  if (selected.contains('header')) {
    test('header routes receive transport headers', () async {
      final body = await _rawHttp(
        baseUrl,
        'GET',
        '/api/demo/abc',
        headers: const {'x-token': 'conformance-token'},
      );
      expect(body, contains('header-ok'));
    });
  }

  if (selected.contains('scalar')) {
    test('scalar response routes interoperate with Go server', () async {
      expect(await client.hello.string(), 'hello-string');
      expect(await client.hello.uint64(), 9007199254740991);
    });
  }

  if (selected.contains('enum')) {
    test('enum response routes interoperate with Go server', () async {
      expect(await client.hello.stringEmun(), api.MapEnum.a);
      expect(await client.hello.listEnum(), [api.MapEnum.a, api.MapEnum.b]);
    });
  }

  if (selected.contains('map')) {
    test('map response routes interoperate with Go server', () async {
      final model = await client.demo.mapModel();
      expect(model['1']?.haha, 101);
      final hello = await client.hello.abc(query: const api.HelloAbcQuery(type_: api.HelloChannelMsgTypeEnum.ping));
      expect(hello['ping']?.haha, 1);
      final enumMap = await client.hello.mapEnum();
      expect(enumMap['a']?.haha, 11);
    });
  }

  if (selected.contains('deprecated')) {
    test('deprecated route remains callable', () async {
      final rsp = await client.demo.postDeprecated(
        json: const api.DemoPostDeprecatedJson(req1: 'flutter-deprecated', req2: 3),
      );
      expect(rsp.list, ['flutter-deprecated']);
    });
  }

  if (selected.contains('form')) {
    test('form routes interoperate with Go server', () async {
      final rsp = await client.demo.formSubmit(
        form: const api.DemoFormSubmitForm(title: 'flutter-form', count: 4, enabled: true),
      );
      expect(rsp.summary, 'flutter-form');
      expect(rsp.count, 4);
      expect(rsp.enabled, isTrue);
    });
  }

  if (selected.contains('binary')) {
    test('binary schema routes interoperate with Go server', () async {
      final rsp = await client.binary.packet(
        query: const api.BinaryPacketQuery(trace: 'flutter-typed'),
        packet: _buildPacket(),
      );
      _expectBinaryResponse(rsp, 'flutter-typed');
    });
  }

  if (selected.contains('audit-binary')) {
    test('audit binary schema routes interoperate with Go server', () async {
      final rsp = await client.binary.auditPacket(
        query: const api.BinaryAuditPacketQuery(trace: 'flutter-audit'),
        auditPacket: _buildAuditPacket(),
      );
      expect(rsp.trace, 'flutter-audit');
      expect(rsp.itemCount, 2);
      expect(rsp.checksum, 2);
    });
  }

  if (selected.contains('binary-response')) {
    test('binary schema response routes interoperate with Go server', () async {
      final rsp = await client.binary.auditPacketResponse();
      expect(rsp.flags, api.AuditPacketFlagsValues.hasItems);
      expect(rsp.itemCount, 2);
      expect((rsp.items ?? const <api.AuditPacketItem>[]).map((item) => item.id), [11, 22]);
      expect(rsp.checksum, 2);
    });
  }

  if (selected.contains('media')) {
    test('raw media routes interoperate with Go server', () async {
      final preview = await client.media.mediaPreview(
        multipart: api.MediaPreviewRequest(
          title: 'flutter-media',
          image: api.ApiFilePart(
            filename: 'preview.jpg',
            contentType: 'image/jpeg',
            bytes: _sampleJpeg(),
          ),
        ),
      );
      expect(preview.contentType, startsWith('image/jpeg'));
      _expectBytesStartWith(preview.body, [0xff, 0xd8], 'media preview');

      final frame = await client.media.mediaFrame();
      expect(frame.contentType, startsWith('image/jpeg'));
      expect(frame.body, _sampleJpeg());

      final download = await client.media.mediaDownload();
      expect(download.filename, 'media-report.xlsx');
      _expectBytesStartWith(download.body, [0x50, 0x4b], 'media download');

      final dynamic = await client.media.mediaDownloadDynamic();
      expect(dynamic.filename, 'media-report-dynamic.xlsx');
      _expectBytesStartWith(dynamic.body, [0x50, 0x4b], 'media dynamic download');

      final stream = await client.media.mediaMjpeg();
      expect(latin1.decode(stream.body), contains('--frame'));
    });
  }

  if (selected.contains('error')) {
    test('typed errors interoperate with Go server', () async {
      final ok = await client.demo.errorDemo(query: const api.DemoErrorDemoQuery(mode: 'ok'));
      expect(ok.status, 'ok');

      final rateLimited = await _expectApiError(
        () => client.demo.errorDemo(query: const api.DemoErrorDemoQuery(mode: 'rate_limit')),
      );
      expect(rateLimited.payload.code, api.ApiErrorCode.rateLimited);
      expect(api.resolveApiToast(rateLimited.payload).text, '请等待 30 秒后重试');

      final unknown = await _expectApiError(
        () => client.demo.errorDemo(query: const api.DemoErrorDemoQuery(mode: 'unknown')),
      );
      expect(unknown.payload.id, '');
      expect(unknown.payload.code, 70001);
      expect(unknown.payload.message, 'example undefined business error');
    });
  }

  if (selected.contains('sse')) {
    test('SSE stream interoperates with Go server', () async {
      final bridge = client.demo.subscribeSweepEvents(open: const api.SweepOpen(runId: 'flutter-sse'));
      final message = _waitForMessage(bridge);
      final close = _waitForClose(bridge);
      await bridge.ready;

      final received = await message;
      expect(received, isA<api.SweepStreamMessageState>());
      final state = received as api.SweepStreamMessageState;
      expect(state.data.status, contains('flutter-sse'));

      final closed = await close;
      expect(closed.code, 1000);
      expect(closed.reason, 'example stream complete');
    });
  }

  if (selected.contains('websocket')) {
    test('WebSocket channel interoperates with Go server', () async {
      final channel = client.demo.openAssistantSession(open: const api.AssistantOpen(sessionId: 'flutter-ws'));
      final message = _waitForMessage(channel);
      final close = _waitForClose(channel);
      await channel.ready;
      await channel.send(api.AssistantClientMessageVariants.input(const api.AssistantInput(text: 'hello')));

      final received = await message;
      final text = api.dispatchAssistantServerMessage<String>(
        received,
        delta: (data, _) => data.text ?? '',
        done: (data, _) => data.messageId ?? '',
        log: (data, _) => '${data.level}:${data.message}',
      );
      expect(text, contains('flutter-ws'));
      expect(text, contains('hello'));

      await channel.send(api.AssistantClientMessageVariants.cancel(const api.AssistantCancel(reason: 'flutter done')));
      final closed = await close;
      expect(closed.code, 1000);
      expect(closed.reason, 'flutter done');
    });
  }

  if (selected.contains('single-channel')) {
    test('single model WebSocket channel interoperates with Go server', () async {
      final channel = client.api.openHelloChannel();
      final message = _waitForMessage(channel);
      final close = _waitForClose(channel);
      await channel.ready;
      await channel.send(const api.HelloChannelMessage(type_: api.HelloChannelMsgTypeEnum.ping, data: {'source': 'flutter'}));

      final received = await message;
      expect(received.type_, api.HelloChannelMsgTypeEnum.pong);
      final closed = await close;
      expect(closed.code, 1000);
    });
  }

  if (selected.contains('naming')) {
    test('naming conflicts and multi-root clients interoperate with Go server', () async {
      final apiRsp = await client.conflict.default_(query: const api.ConflictDefaultQuery(class_: 'flutter-api'));
      expect(apiRsp.default_, 'api-default');
      expect(apiRsp.class_, 'flutter-api');
      expect(apiRsp.enum_, api.KeywordEnum.default_);

      final altRsp =
          await altClient.conflict.default_(query: const alt.ConflictDefaultQuery(class_: 'flutter-alt'));
      expect(altRsp.default_, 'alt-default');
      expect(altRsp.class_, 'flutter-alt');
      expect(altRsp.enum_, alt.KeywordEnum.class_);
    });
  }
}

Set<String> _scenarioSet(String raw) =>
    raw.split(',').map((item) => item.trim()).where((item) => item.isNotEmpty).toSet();

api.DemoPacket _buildPacket() {
  final payload = Uint8List.fromList(utf8.encode('payload-ok'));
  return api.DemoPacket(
    flags: api.DemoPacketFlagsValues.hasPayload | api.DemoPacketFlagsValues.hasScores,
    shortCode: 0x010203,
    signedDelta: 7,
    itemCount: 2,
    payloadLen: payload.length,
    items: [
      api.DemoPacketItem(
        id: 11,
        enabled: true,
        value: 1.25,
        labelLen: 5,
        label: Uint8List.fromList(utf8.encode('alpha')),
      ),
      api.DemoPacketItem(
        id: 22,
        enabled: false,
        value: 2.5,
        labelLen: 4,
        label: Uint8List.fromList(utf8.encode('beta')),
      ),
    ],
    payload: payload,
    scores: const [3.5, 4.5],
    checksum: 12,
  );
}

api.AuditPacket _buildAuditPacket() {
  return const api.AuditPacket(
    flags: api.AuditPacketFlagsValues.hasItems,
    itemCount: 2,
    items: [
      api.AuditPacketItem(id: 11, code: 101),
      api.AuditPacketItem(id: 22, code: 202),
    ],
    checksum: 2,
  );
}

Uint8List _sampleJpeg() => Uint8List.fromList(const [
      0xff,
      0xd8,
      0xff,
      0xe0,
      0x00,
      0x10,
      0x4a,
      0x46,
      0x49,
      0x46,
      0x00,
      0x01,
      0x01,
      0x01,
      0x00,
      0x01,
      0x00,
      0x01,
      0x00,
      0x00,
      0xff,
      0xd9,
    ]);

void _expectBinaryResponse(api.BinaryPacketResponse rsp, String trace) {
  expect(rsp.trace, trace);
  expect(rsp.version, 1);
  expect(rsp.itemCount, 2);
  expect(rsp.payload, 'payload-ok');
  expect(rsp.scoreSum, 8);
  expect(rsp.firstLabel, 'alpha');
  expect(rsp.itemIds, [11, 22]);
  expect(rsp.checksum, 12);
}

void _expectBytesStartWith(Uint8List actual, List<int> prefix, String label) {
  expect(actual.length, greaterThanOrEqualTo(prefix.length), reason: label);
  for (var index = 0; index < prefix.length; index++) {
    expect(actual[index], prefix[index], reason: '$label[$index]');
  }
}

Future<String> _rawHttp(
  String baseUrl,
  String method,
  String path, {
  Map<String, String> headers = const {},
}) async {
  final uri = Uri.parse('$baseUrl$path');
  final client = HttpClient();
  try {
    final request = await client.openUrl(method, uri);
    headers.forEach(request.headers.set);
    final response = await request.close();
    final body = await utf8.decodeStream(response);
    expect(response.statusCode, 200, reason: body);
    return body;
  } finally {
    client.close(force: true);
  }
}

Future<api.ApiError> _expectApiError(Future<Object?> Function() action) async {
  try {
    await action();
  } on api.ApiError catch (error) {
    expect(error.routeId, 'api.demo.get.errordemo');
    return error;
  }
  fail('expected ApiError');
}

Future<R> _waitForMessage<R, C>(api.ApiStreamBridge<R, C> bridge) {
  late api.SocketUnsubscribe unsubscribe;
  final completer = Completer<R>();
  unsubscribe = bridge.onMessage((message) {
    unsubscribe();
    completer.complete(message);
  });
  return completer.future.timeout(const Duration(seconds: 5));
}

Future<C> _waitForClose<R, C>(api.ApiStreamBridge<R, C> bridge) {
  late api.SocketUnsubscribe unsubscribe;
  final completer = Completer<C>();
  unsubscribe = bridge.onClose((info) {
    unsubscribe();
    completer.complete(info);
  });
  return completer.future.timeout(const Duration(seconds: 5));
}
