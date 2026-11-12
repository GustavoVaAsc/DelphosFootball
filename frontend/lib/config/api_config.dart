/// Build-time configuration of the backend URL (ADR-029).
///
/// The value is compiled in with
/// `--dart-define=DELPHOS_API_URL=<url>`. The browser calls the API from the
/// user's machine, so the default is the host URL of the compose backend.
library;

/// The backend base URL the app was built against.
abstract final class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'DELPHOS_API_URL',
    defaultValue: 'http://localhost:8000',
  );
}
