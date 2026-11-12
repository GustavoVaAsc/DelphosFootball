/// The error the API client throws when the backend answers with a non-2xx
/// status, carrying the RFC 9457 problem details the backend sends.
library;

/// A non-2xx answer from the backend.
///
/// [title] and [detail] come from the `application/problem+json` body. When
/// the body is not a problem document (a proxy error page, for example),
/// [title] falls back to the HTTP reason phrase and [detail] is `null`.
/// They are diagnostic text in English and are never shown to the user.
class ApiException implements Exception {
  const ApiException({
    required this.statusCode,
    required this.title,
    this.detail,
    this.path,
  });

  /// The HTTP status code of the response.
  final int statusCode;

  /// The problem title, or the HTTP reason phrase.
  final String title;

  /// The problem detail, when the body carried one.
  final String? detail;

  /// The request path that failed, for diagnostics.
  final String? path;

  /// Whether the requested resource does not exist (404).
  bool get isNotFound => statusCode == 404;

  @override
  String toString() =>
      'ApiException($statusCode $title${detail == null ? '' : ': $detail'}'
      '${path == null ? '' : ' at $path'})';
}
