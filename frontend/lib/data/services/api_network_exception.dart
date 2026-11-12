/// The error the API client throws when the backend cannot be reached at
/// all: no answer, a refused connection, a CORS rejection or a timeout.
library;

/// The request never produced an HTTP response.
///
/// The UI maps this to the "No se pudo conectar con el servidor de datos"
/// state (DESIGN.md §7), distinct from an `ApiException`, which is an error
/// the backend answered.
class ApiNetworkException implements Exception {
  const ApiNetworkException(this.message, {this.path, this.cause});

  /// What failed, in English, for diagnostics.
  final String message;

  /// The request path that failed.
  final String? path;

  /// The underlying error (a `ClientException` or a `TimeoutException`).
  final Object? cause;

  @override
  String toString() =>
      'ApiNetworkException($message${path == null ? '' : ' at $path'})';
}
