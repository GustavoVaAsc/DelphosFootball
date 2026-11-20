/// How one server-sent event changes a chat turn, and the Spanish message of
/// each failure. Pure functions, kept out of `ChatViewModel` so it stays about
/// state and streaming.
library;

import '../../../../data/models/chat_sse_event.dart';
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
    case 'tool_start':
      return _startStep(turn, event.data);
    case 'tool':
      return _finishStep(turn, event.data);
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
        steps: [for (final s in steps) s.settled(failed: false)],
        assistantMessage: event.data['message'] as String? ?? '',
        isStreaming: false,
      );
    case 'error':
      return turn.copyWith(
        steps: [for (final s in turn.steps) s.settled(failed: true)],
        errorMessage:
            'El asistente se interrumpió antes de terminar la respuesta. '
            'Inténtalo de nuevo.',
        isStreaming: false,
      );
  }
  return turn;
}

/// [turn] with a running step for a `tool_start` event.
ChatTurn _startStep(ChatTurn turn, Map<String, Object?> data) {
  final tool = data['tool'] as String?;
  final step = ChatToolStep(
    id: data['step'] as int?,
    stepTitle: chatToolStepDescription(tool, data['description'] as String?),
    summary: '',
    state: ChatStepState.running,
  );
  return turn.copyWith(steps: [...turn.steps, step]);
}

/// [turn] with the result of a `tool` event. A step that started is replaced
/// in place, matched by its number; an older backend sends only this event,
/// so its step is appended.
ChatTurn _finishStep(ChatTurn turn, Map<String, Object?> data) {
  final tool = data['tool'] as String?;
  final id = data['step'] as int?;
  final steps = [...turn.steps];
  final at = id == null
      ? -1
      : steps.indexWhere((step) => step.id == id && step.isRunning);
  final described =
      (data['description'] as String?)?.trim().isNotEmpty ?? false;
  final finished = ChatToolStep(
    id: id,
    // The sentence of the step that started stays when this event has none.
    stepTitle: at >= 0 && !described
        ? steps[at].stepTitle
        : chatToolStepDescription(tool, data['description'] as String?),
    summary: chatToolStepSummary(tool, data['summary'] as String?),
    state: (data['ok'] as bool? ?? true)
        ? ChatStepState.done
        : ChatStepState.failed,
  );
  if (at < 0) {
    steps.add(finished);
  } else {
    steps[at] = finished;
  }
  return turn.copyWith(steps: steps);
}
