/// Turns a saved conversation's messages into completed chat turns.
library;

import '../../../../domain/models/chat_session_history.dart';
import '../../../../domain/models/chat_turn.dart';

/// One turn per question, paired with the answer stored right after it.
/// Tool steps are not stored, so the turns have none. A question without an
/// answer (the reply never finished) is a turn without an answer; an answer
/// with no question before it, and any other role, are dropped.
List<ChatTurn> chatTurnsFromHistory(ChatSessionHistory history) {
  final turns = <ChatTurn>[];
  for (final message in history.messages) {
    if (message.isUser) {
      turns.add(ChatTurn(userMessage: message.content));
    } else if (message.isAssistant &&
        turns.isNotEmpty &&
        turns.last.assistantMessage == null) {
      turns[turns.length - 1] = turns.last.copyWith(
        assistantMessage: message.content,
        players: message.players,
      );
    }
  }
  return turns;
}
