import 'dart:convert';

import 'package:api_blueprint_example/api_blueprint_example.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:test/test.dart';

void main() {
  test('HTTP transport sends requests and unwraps response envelopes', () async {
    final httpClient = MockClient((request) async {
      expect(request.method, 'GET');
      expect(request.url.toString(), 'http://example.test/api/demo/abc?arg3=hello');
      return http.Response(
        jsonEncode({
          'code': 0,
          'message': 'ok',
          'data': {'bc': 'from-http', 'a': 3},
        }),
        200,
      );
    });
    final client = createHttpApiClient(
      config: HttpApiConfig(baseUrl: 'http://example.test', client: httpClient),
    );

    final response = await client.demo.abc(query: const DemoAbcQuery(arg3: 'hello'));

    expect(response.bc, 'from-http');
    expect(response.a, 3);
  });

  test('HTTP transport restores typed API errors', () async {
    final httpClient = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'code': ApiErrorCode.rateLimited,
          'message': 'rate limited',
          'data': null,
          'error': {
            'group': 'DemoErr',
            'key': 'RATE_LIMITED',
            'code': ApiErrorCode.rateLimited,
            'message': 'rate limited',
            'toast': {'text': 'retry later'},
          },
        }),
        200,
      );
    });
    final client = createHttpApiClient(
      config: HttpApiConfig(baseUrl: 'http://example.test', client: httpClient),
    );

    await expectLater(
      client.demo.errorDemo(),
      throwsA(
        isA<ApiError>()
            .having((error) => error.payload.code, 'code', ApiErrorCode.rateLimited)
            .having((error) => error.payload.message, 'message', 'rate limited')
            .having((error) => error.payload.toast.text, 'toast.text', 'retry later'),
      ),
    );
  });

  test('HTTP transport returns raw non-JSON success bodies', () async {
    final httpClient = MockClient((request) async {
      expect(request.method, 'DELETE');
      return http.Response('<ok/>', 200, headers: {'content-type': 'application/xml'});
    });
    final client = createHttpApiClient(
      config: HttpApiConfig(baseUrl: 'http://example.test', client: httpClient),
    );

    final response = await client.demo.delete();

    expect(response, '<ok/>');
  });

  test('HTTP stream bridge fails ready on non-2xx SSE response', () async {
    final httpClient = MockClient((request) async {
      return http.Response('blocked', 500);
    });
    final transport = HttpApiTransport(config: HttpApiConfig(baseUrl: 'http://example.test', client: httpClient));
    final bridge = transport.openStream<Object?, SocketCloseInfo>(
      StreamConnectOptions<Object?, SocketCloseInfo>(
        routeId: 'test.stream',
        connectionKind: 'stream',
        path: '/events',
        decodeMessage: (value) => value,
        decodeClose: (_) => const SocketCloseInfo(),
      ),
    );

    await expectLater(
      bridge.ready,
      throwsA(isA<ApiException>().having((error) => error.statusCode, 'statusCode', 500)),
    );
  });
}
