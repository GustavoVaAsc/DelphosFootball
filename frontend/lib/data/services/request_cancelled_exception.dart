/// The error the API client throws when its caller cancelled the request,
/// for example when the reader switches player during a report generation.
library;

/// The caller cancelled the request; the browser's `fetch` was aborted.
///
/// This is not a failure to show: the caller asked for it, so a ViewModel
/// drops the result instead of mapping it to an error state.
class RequestCancelledException implements Exception {
  const RequestCancelledException(this.path);

  /// The request path that was cancelled.
  final String path;

  @override
  String toString() => 'RequestCancelledException(at $path)';
}
