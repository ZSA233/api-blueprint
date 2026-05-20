import '../../runtime/api_client.dart';
import '../../runtime/gen_api_transport.dart';
import 'gen_http_api_config.dart';
import 'gen_http_api_transport.dart';

ApiClient createHttpApiClient({
  HttpApiConfig config = const HttpApiConfig(),
  ApiTransport? transport,
}) {
  return ApiClient(transport ?? HttpApiTransport(config: config));
}
