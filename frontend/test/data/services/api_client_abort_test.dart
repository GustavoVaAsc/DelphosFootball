// Tests that ApiClient cancels a timed-out or caller-cancelled request
// through the abort trigger of http.AbortableRequest, instead of leaving it
// running.
import 'dart:async';

import 'package:delphos_frontend/data/services/api_client.dart';
import 'package:delphos_frontend/data/services/api_network_exception.dart';
import 'package:delphos_frontend/data/services/request_cancelled_exception.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../support/http_fakes.dart';

void main() {
  test('aborts the request itself when the timeout fires', () async {
    final client = _AbortRecordingClient();
    final api = ApiClient(baseUrl: testBaseUrl, httpClient: client);
    await expectLater(
      api.postJson('/reports/generate', {
        'player_id': 1,
      }, timeout: const Duration(milliseconds: 10)),
      throwsA(isA<ApiNetworkException>()),
    );
    expect(client.sawAbortTrigger, isTrue);
    // The trigger's listeners run asynchronously, as in the browser client.
    await Future<void>.delayed(Duration.zero);
    expect(client.aborted, isTrue);
  });

  test('aborts the request and throws when the caller cancels', () async {
    final client = _AbortRecordingClient();
    final api = ApiClient(baseUrl: testBaseUrl, httpClient: client);
    final cancel = Completer<void>();
    final call = api.postJson(
      '/reports/generate',
      {'player_id': 1},
      timeout: const Duration(minutes: 5),
      cancel: cancel.future,
    );
    cancel.complete();
    await expectLater(call, throwsA(isA<RequestCancelledException>()));
    await Future<void>.delayed(Duration.zero);
    expect(client.aborted, isTrue);
  });
}

/// A client that never answers but honours `Abortable.abortTrigger`, the way
/// the browser client cancels its `fetch`.
class _AbortRecordingClient extends http.BaseClient {
  bool sawAbortTrigger = false;
  bool aborted = false;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    final result = Completer<http.StreamedResponse>();
    if (request case http.Abortable(:final abortTrigger?)) {
      sawAbortTrigger = true;
      abortTrigger.whenComplete(() {
        aborted = true;
        result.completeError(http.RequestAbortedException(request.url));
      });
    }
    return result.future;
  }
}
