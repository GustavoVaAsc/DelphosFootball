/// The one HTTP client of the app, written by hand against the backend's
/// OpenAPI contract (ADR-025).
///
/// It sends JSON, decodes JSON as UTF-8 whatever the declared charset, and
/// turns every failure into one of two errors: [ApiException] when the
/// backend answered with a non-2xx status, and [ApiNetworkException] when no
/// answer arrived. A request whose `cancel` future completes is aborted and
/// throws [RequestCancelledException]. A 2xx body that is not a JSON object is a
/// [FormatException]: the contract drifted. Whoever creates a client owns it
/// and calls [close].
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/problem_details_dto.dart';
import 'api_exception.dart';
import 'api_network_exception.dart';
import 'request_cancelled_exception.dart';

/// Sends requests to the backend and returns decoded JSON objects.
class ApiClient {
  ApiClient({required String baseUrl, http.Client? httpClient})
    : _baseUrl = Uri.parse(baseUrl),
      _http = httpClient ?? http.Client();

  /// Read requests are database lookups; anything slower is an outage.
  static const Duration readTimeout = Duration(seconds: 20);

  final Uri _baseUrl;
  final http.Client _http;

  /// `GET path?query`, returning the decoded JSON object.
  Future<Map<String, Object?>> getJson(
    String path, {
    Map<String, String> query = const {},
    Duration timeout = readTimeout,
    Future<void>? cancel,
  }) => _send('GET', path, timeout, cancel, query: query);

  /// `POST path` with a JSON [body], returning the decoded JSON object.
  Future<Map<String, Object?>> postJson(
    String path,
    Map<String, Object?> body, {
    Duration timeout = readTimeout,
    Future<void>? cancel,
  }) => _send('POST', path, timeout, cancel, body: body);

  /// `POST path` expecting a `text/event-stream` response, yielding UTF-8 chunks.
  Stream<String> postEventStream(
    String path,
    Map<String, Object?> body, {
    Duration timeout = const Duration(seconds: 120),
    Future<void>? cancel,
  }) async* {
    final abort = Completer<void>();
    final request = _buildRequest(
      'POST',
      path,
      abort,
      accept: 'text/event-stream',
      body: body,
    );
    final streamed = await _guard(
      path,
      timeout,
      cancel,
      abort,
      () => _http.send(request),
    );
    if (streamed.statusCode < 200 || streamed.statusCode > 299) {
      _throwForDecoded(await http.Response.fromStream(streamed), path);
    }
    try {
      await for (final chunk in streamed.stream.transform(utf8.decoder)) {
        yield chunk;
      }
    } on http.ClientException catch (error) {
      throw ApiNetworkException(error.message, path: path, cause: error);
    }
  }

  /// Releases the underlying connection pool.
  void close() => _http.close();

  http.AbortableRequest _buildRequest(
    String method,
    String path,
    Completer<void> abort, {
    required String accept,
    Map<String, String> query = const {},
    Map<String, Object?>? body,
  }) {
    final request = http.AbortableRequest(
      method,
      _uriFor(path, query),
      abortTrigger: abort.future,
    )..headers['Accept'] = accept;
    if (body != null) {
      request
        ..headers['Content-Type'] = 'application/json; charset=utf-8'
        ..body = jsonEncode(body);
    }
    return request;
  }

  Future<T> _guard<T>(
    String path,
    Duration timeout,
    Future<void>? cancel,
    Completer<void> abort,
    Future<T> Function() start,
  ) async {
    try {
      final sent = start();
      return await (cancel == null
              ? sent
              : Future.any([sent, _cancelled(cancel, abort, path)]))
          .timeout(timeout, onTimeout: () => throw _timedOut(abort, timeout));
    } on TimeoutException catch (error) {
      throw ApiNetworkException(error.message ?? '', path: path, cause: error);
    } on http.ClientException catch (error) {
      throw ApiNetworkException(error.message, path: path, cause: error);
    }
  }

  /// Sends one JSON request and returns the decoded JSON object.
  Future<Map<String, Object?>> _send(
    String method,
    String path,
    Duration timeout,
    Future<void>? cancel, {
    Map<String, String> query = const {},
    Map<String, Object?>? body,
  }) async {
    final abort = Completer<void>();
    final request = _buildRequest(
      method,
      path,
      abort,
      accept: 'application/json',
      query: query,
      body: body,
    );
    final response = await _guard(
      path,
      timeout,
      cancel,
      abort,
      () => _http.send(request).then(http.Response.fromStream),
    );
    if (response.statusCode < 200 || response.statusCode > 299) {
      _throwForDecoded(response, path);
    }
    return switch (_decode(response)) {
      final Map<String, Object?> object => object,
      _ => throw FormatException('Expected a JSON object from $path'),
    };
  }

  static Never _throwForDecoded(http.Response response, String path) {
    final problem = ProblemDetailsDto.tryParse(_decode(response));
    throw ApiException(
      statusCode: response.statusCode,
      title: problem?.title ?? response.reasonPhrase ?? 'HTTP error',
      detail: problem?.detail,
      path: path,
    );
  }

  /// Fires the abort trigger and returns the timeout to throw.
  static TimeoutException _timedOut(Completer<void> abort, Duration timeout) {
    if (!abort.isCompleted) abort.complete();
    return TimeoutException('No response within ${timeout.inSeconds} s');
  }

  /// Fires the abort trigger when [cancel] completes, then throws.
  static Future<Never> _cancelled(
    Future<void> cancel,
    Completer<void> abort,
    String path,
  ) async {
    await cancel;
    if (!abort.isCompleted) abort.complete();
    throw RequestCancelledException(path);
  }

  Uri _uriFor(String path, Map<String, String> query) {
    final basePath = _baseUrl.path.endsWith('/')
        ? _baseUrl.path.substring(0, _baseUrl.path.length - 1)
        : _baseUrl.path;
    return _baseUrl.replace(
      path: '$basePath$path',
      queryParameters: query.isEmpty ? null : query,
    );
  }

  /// The JSON body, or `null` when the body is empty or not JSON (an error
  /// page from a proxy, for example).
  static Object? _decode(http.Response response) {
    if (response.bodyBytes.isEmpty) return null;
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      return null;
    }
  }
}
