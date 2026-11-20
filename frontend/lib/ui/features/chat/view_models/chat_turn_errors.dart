/// The Spanish message of each way a chat turn can fail. The backend's own
/// detail is never shown.
library;

import '../../../../data/services/api_exception.dart';
import '../../../../data/services/api_network_exception.dart';

/// The message for [error], whatever the request threw.
String chatErrorMessage(Object error) => switch (error) {
  ApiException() => chatApiErrorMessage(error),
  ApiNetworkException() =>
    'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo '
        'de nuevo.',
  FormatException() =>
    'La respuesta del asistente llegó incompleta. Inténtalo de nuevo.',
  _ =>
    'No se pudo completar la consulta. Inténtalo de nuevo o reformula '
        'la pregunta.',
};

/// The message for an API error.
String chatApiErrorMessage(ApiException error) {
  if (error.statusCode == 503) {
    return 'El asistente no está disponible en este momento. Inténtalo de '
        'nuevo en unos minutos.';
  }
  return 'No se pudo completar la consulta. Inténtalo de nuevo o reformula '
      'la pregunta.';
}
