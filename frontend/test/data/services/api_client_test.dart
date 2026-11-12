// Tests for ApiClient error mapping: RFC 9457 problems become ApiException,
// a missing answer becomes ApiNetworkException, a bad 2xx body is a
// FormatException.
import 'dart:async';

import 'package:delphos_frontend/data/services/api_client.dart';
import 'package:delphos_frontend/data/services/api_exception.dart';
import 'package:delphos_frontend/data/services/api_network_exception.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../support/http_fakes.dart';

void main() {
  test('maps a problem response to an ApiException with its fields', () async {
    final api = fakeApi(
      (_) async => problemResponse(404, 'Not Found', 'Player not found'),
    );
    await expectLater(
      api.getJson('/players/9'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.statusCode, 'statusCode', 404)
            .having((e) => e.title, 'title', 'Not Found')
            .having((e) => e.detail, 'detail', 'Player not found')
            .having((e) => e.path, 'path', '/players/9')
            .having((e) => e.isNotFound, 'isNotFound', isTrue),
      ),
    );
  });

  test('maps a 503 without an active run to an ApiException', () async {
    final api = fakeApi(
      (_) async => problemResponse(
        503,
        'Service Unavailable',
        'No active model run published in database',
      ),
    );
    await expectLater(
      api.getJson('/clusters'),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 503)),
    );
  });

  test('falls back to the reason phrase for a non-JSON error body', () async {
    final api = fakeApi(
      (_) async => http.Response(
        '<html>Bad gateway</html>',
        502,
        reasonPhrase: 'Bad Gateway',
      ),
    );
    await expectLater(
      api.getJson('/players'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.statusCode, 'statusCode', 502)
            .having((e) => e.title, 'title', 'Bad Gateway')
            .having((e) => e.detail, 'detail', isNull),
      ),
    );
  });

  test('maps a failed connection to an ApiNetworkException', () async {
    final api = fakeApi(
      (_) async => throw http.ClientException('XMLHttpRequest error.'),
    );
    await expectLater(
      api.getJson('/players'),
      throwsA(
        isA<ApiNetworkException>()
            .having((e) => e.path, 'path', '/players')
            .having((e) => e.cause, 'cause', isA<http.ClientException>()),
      ),
    );
  });

  test('maps a timeout to an ApiNetworkException', () async {
    final never = Completer<http.Response>();
    final api = fakeApi((_) => never.future);
    await expectLater(
      api.getJson('/players', timeout: const Duration(milliseconds: 10)),
      throwsA(
        isA<ApiNetworkException>().having(
          (e) => e.cause,
          'cause',
          isA<TimeoutException>(),
        ),
      ),
    );
  });

  test('treats a 2xx body that is not a JSON object as contract drift', () {
    final api = fakeApi((_) async => jsonResponse([1, 2, 3]));
    expect(api.getJson('/players'), throwsA(isA<FormatException>()));
  });

  test('keeps a base path when joining the request path', () async {
    final log = <http.Request>[];
    final api = ApiClient(
      baseUrl: 'http://host.test/api/',
      httpClient: MockClient((request) async {
        log.add(request);
        return jsonResponse(<String, Object?>{});
      }),
    );
    await api.getJson('/clusters', query: {'page': '1'});
    expect(log.single.url.toString(), 'http://host.test/api/clusters?page=1');
  });
}
