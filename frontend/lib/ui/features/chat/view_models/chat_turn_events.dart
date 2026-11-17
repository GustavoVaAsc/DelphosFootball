/// How one server-sent event changes a chat turn, and the Spanish message of
/// each failure. Pure functions, kept out of `ChatViewModel` so it stays about
/// state and streaming.
library;

import '../../../../data/models/chat_sse_event.dart';
import '../../../../data/services/api_exception.dart';
import '../../../../domain/models/chat_tool_step.dart';
import '../../../../domain/models/chat_turn.dart';
import '../../../core/labels/chat_tool_labels.dart';

/// [turn] after [event]. [sessionId] is called with a new session id when a
/// `message` event carries one.
ChatTurn applyChatEvent(
  ChatTurn turn,
  ChatSseEvent event, {
  required void Function(String sessionId) onSession,
}) {
  switch (event.event) {
    case 'tool':
      final tool = event.data['tool'] as String?;
      final ok = event.data['ok'] as bool? ?? true;
      final step = ChatToolStep(
        stepTitle: chatToolStepTitle(tool),
        summary: chatToolStepSummary(tool, event.data['summary'] as String?),
        isError: !ok,
      );
      return turn.copyWith(steps: [...turn.steps, step]);
    case 'message':
      final nextSession = event.data['session_id'] as String?;
      if (nextSession != null && nextSession.isNotEmpty) {
        onSession(nextSession);
      }
      final tools = (event.data['tools_called'] as List<Object?>? ?? const [])
          .whereType<String>();
      final steps = turn.steps.isNotEmpty
          ? turn.steps
          : [
              for (final t in tools)
                ChatToolStep(
                  stepTitle: chatToolStepTitle(t),
                  summary: chatToolStepSummary(t, null),
                ),
            ];
      return turn.copyWith(
        steps: steps,
        assistantMessage: event.data['message'] as String? ?? '',
        isStreaming: false,
      );
    case 'error':
      return turn.copyWith(
        errorMessage:
            'PitIA se interrumpió antes de terminar la respuesta. '
            'Inténtalo de nuevo.',
        isStreaming: false,
      );
  }
  return turn;
}

/// The message for an API error.
String chatApiErrorMessage(ApiException error) {
  if (error.statusCode == 503) {
    return 'PitIA no está disponible en este momento. Inténtalo de '
        'nuevo en unos minutos.';
  }
  return 'No se pudo completar la consulta. Inténtalo de nuevo o reformula '
      'la pregunta.';
}
