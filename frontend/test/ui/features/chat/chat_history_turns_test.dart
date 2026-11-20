// Rules of restoring a saved conversation: questions and answers pair into
// completed turns without tool steps, and stray messages are dropped.
import 'package:delphos_frontend/domain/models/chat_history_message.dart';
import 'package:delphos_frontend/domain/models/chat_session_history.dart';
import 'package:delphos_frontend/ui/features/chat/view_models/chat_history_turns.dart';
import 'package:flutter_test/flutter_test.dart';

ChatHistoryMessage msg(String role, String content) => ChatHistoryMessage(
  role: role,
  content: content,
  createdAt: DateTime.utc(2026, 11, 10),
);

ChatSessionHistory history(List<ChatHistoryMessage> messages) =>
    ChatSessionHistory(
      sessionId: 's',
      messages: messages,
      total: messages.length,
    );

void main() {
  test('pairs each question with the answer after it', () {
    final turns = chatTurnsFromHistory(
      history([
        msg('user', 'Busca delanteros'),
        msg('assistant', 'Hay dos.'),
        msg('user', 'Compara a Kane'),
        msg('assistant', 'Kane está infravalorado.'),
      ]),
    );

    expect(turns, hasLength(2));
    expect(turns[0].userMessage, 'Busca delanteros');
    expect(turns[0].assistantMessage, 'Hay dos.');
    expect(turns[1].assistantMessage, 'Kane está infravalorado.');
    for (final turn in turns) {
      expect(turn.steps, isEmpty);
      expect(turn.isStreaming, isFalse);
      expect(turn.errorMessage, isNull);
    }
  });

  test('keeps a question whose answer was never stored', () {
    final turns = chatTurnsFromHistory(
      history([
        msg('user', 'Busca delanteros'),
        msg('user', 'Compara a Kane'),
        msg('assistant', 'Respuesta.'),
      ]),
    );

    expect(turns, hasLength(2));
    expect(turns[0].assistantMessage, isNull);
    expect(turns[1].assistantMessage, 'Respuesta.');
  });

  test('drops a leading answer, a second answer and other roles', () {
    final turns = chatTurnsFromHistory(
      history([
        msg('assistant', 'Huérfana.'),
        msg('user', 'Hola'),
        msg('tool', 'ruido'),
        msg('assistant', 'Primera.'),
        msg('assistant', 'Segunda.'),
      ]),
    );

    expect(turns, hasLength(1));
    expect(turns.single.assistantMessage, 'Primera.');
  });

  test('an empty session has no turns', () {
    expect(chatTurnsFromHistory(history(const [])), isEmpty);
  });
}
