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
      'rpc,binary,form,error,sse,websocket,naming');

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
