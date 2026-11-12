// Helpers for faking the backend with package:http's MockClient.
import 'dart:convert';

import 'package:delphos_frontend/data/services/api_client.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const testBaseUrl = 'http://api.test';

/// A JSON response encoded as UTF-8, with [contentType] as sent.
http.Response jsonResponse(
  Object? body, {
  int status = 200,
  String contentType = 'application/json',
}) => http.Response.bytes(
  utf8.encode(jsonEncode(body)),
  status,
  headers: {'content-type': contentType},
);

/// An RFC 9457 problem response, shaped like the backend's.
http.Response problemResponse(int status, String title, String detail) =>
    jsonResponse(
      {
        'type': 'about:blank',
        'title': title,
        'status': status,
        'detail': detail,
        'trace_id': null,
      },
      status: status,
      contentType: 'application/problem+json',
    );

/// An [ApiClient] whose every request goes to [handler]; the requests it
/// received are appended to [log] when given.
ApiClient fakeApi(
  Future<http.Response> Function(http.Request request) handler, {
  List<http.Request>? log,
}) => ApiClient(
  baseUrl: testBaseUrl,
  httpClient: MockClient((request) {
    log?.add(request);
    return handler(request);
  }),
);
