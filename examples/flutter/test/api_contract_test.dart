import 'package:api_blueprint_example/api_blueprint_example.dart';
import 'package:test/test.dart';

void main() {
  test('route client sends typed request metadata and decodes DTOs', () async {
    final transport = _CapturingTransport({'bc': 'ok', 'a': 7});
    final client = ApiClient(transport);

    final response = await client.demo.abc(
      query: const DemoAbcQuery(arg1: true, arg3: 'hello', arg2: 1.5),
    );

    expect(response.bc, 'ok');
    expect(response.a, 7);
    expect(transport.lastRequest?.routeId, 'api.demo.get.abc');
    expect(transport.lastRequest?.method, 'GET');
    expect(transport.lastRequest?.path, '/api/demo/abc');
    expect(transport.lastRequest?.query['arg1'], 'true');
    expect(transport.lastRequest?.query['arg3'], 'hello');
  });

  test('sealed message helpers encode and dispatch variants', () {
    final message = AssistantServerMessageVariants.delta(const AssistantDelta(text: 'hi'));
    final json = message.toJson();
    final decoded = AssistantServerMessage.fromJsonValue(json);

    final text = dispatchAssistantServerMessage<String>(
      decoded,
      delta: (data, _) => data.text ?? '',
      done: (data, message) => 'done',
      log: (data, message) => 'log',
    );

    expect(text, 'hi');
    expect(json['type'], 'delta');
  });
}

class _CapturingTransport implements ApiTransport {
  final Object? payload;
  ApiRequest<Object?>? lastRequest;

  _CapturingTransport(this.payload);

  @override
  Future<T> request<T>(ApiRequest<T> request) async {
    lastRequest = request as ApiRequest<Object?>;
    return request.decode(payload);
  }

  @override
  ApiStreamBridge<Recv, Close> openStream<Recv, Close>(StreamConnectOptions<Recv, Close> options) {
    throw UnimplementedError();
  }

  @override
  ApiChannelBridge<Recv, Send, Close> openChannel<Recv, Send, Close>(
    ChannelConnectOptions<Recv, Send, Close> options,
  ) {
    throw UnimplementedError();
  }
}
